from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from processing.rag import (
    search_folder, load_template, load_all_templates_in_folder
)
from processing.field_split import validate_excel_structure, build_field_values_bulk_row
from processing.renderer import render_poster
from validation.excel_validator import validate_excel_file
from jobs.job_tracker import init_db, create_job, update_job, get_job
from config import settings
import pandas as pd
import io
import uuid
import zipfile
import csv
import time
import os
import json
import copy
import re

router = APIRouter()
init_db()


def _overlay_values_path(job_id: str) -> str:
    return os.path.join(settings.output_dir, f"{job_id}_overlay_values.json")


def _safe_emp_id(emp_id: str) -> str:
    # Same characters allowed in output filenames elsewhere in this app.
    return re.sub(r"[^A-Za-z0-9_\-]", "_", emp_id)


@router.post("/bulk")
async def bulk_generate(
    background_tasks: BackgroundTasks,
    prompt: str = Form(...),
    excel: UploadFile = File(...),
    folder: str = Form(None),
    template_id: str = Form(None)
):
    prompt = prompt.strip()[:settings.max_prompt_length]
    content = await excel.read()

    try:
        if excel.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
    except Exception:
        raise HTTPException(
            422, "Could not read file. Upload .xlsx or .csv"
        )

    validate_excel_file(df)

    if folder and template_id:
        template = load_template(folder, template_id)
        if not template:
            raise HTTPException(404, "Template not found.")
        resolved_template_id = template_id
    else:
        matches = search_folder(prompt)
        if not matches:
            return {"status": "no_match", "trigger_phase2": True}

        top = matches[0]
        second_score = matches[1]["score"] if len(matches) > 1 else 0

        if (
            len(matches) > 1
            and top["score"] > 0
            and (top["score"] - second_score) < settings.ambiguity_gap
        ):
            return {
                "status": "ambiguous",
                "matches": [
                    {
                        "folder": m["folder"],
                        "display_name": m["display_name"]
                    }
                    for m in matches
                ]
            }

        folder = top["folder"]

        if len(top["templates"]) == 1:
            resolved_template_id = top["templates"][0]
            template = load_template(folder, resolved_template_id)
        else:
            all_templates = load_all_templates_in_folder(folder)
            return {
                "status": "gallery",
                "folder": folder,
                "display_name": top["display_name"],
                "templates": [
                    {
                        "template_id": t["template_id"],
                        "description": t["description"]
                    }
                    for t in all_templates
                ]
            }

    structure_error = validate_excel_structure(
        template, df.columns.tolist()
    )
    if structure_error:
        return structure_error

    job_id = uuid.uuid4().hex
    rows = df.to_dict(orient="records")
    # NOTE: folder/resolved_template_id are persisted on the job so that a
    # later /bulk-restyle call knows which template's style rules to apply,
    # without the frontend having to re-send or remember them.
    create_job(job_id, len(rows), folder=folder, template_id=resolved_template_id)
    background_tasks.add_task(
        run_bulk_job, job_id, template, resolved_template_id, folder, prompt, rows
    )

    return {
        "status": "queued",
        "job_id": job_id,
        "total_rows": len(rows)
    }


@router.get("/job-status/{job_id}")
def job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.get("/bulk-preview-info/{job_id}")
def bulk_preview_info(job_id: str):
    """
    Returns the folder/template_id used for this job plus the list of
    emp_ids that rendered successfully, so the frontend can build an
    emp_id picker and know which template's fields to show style controls
    for.
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    ov_path = _overlay_values_path(job_id)
    if not os.path.exists(ov_path):
        return {
            "folder": job["folder"],
            "template_id": job["template_id"],
            "emp_ids": []
        }

    with open(ov_path, encoding="utf-8") as f:
        row_map = json.load(f)

    return {
        "folder": job["folder"],
        "template_id": job["template_id"],
        "emp_ids": sorted(row_map.keys())
    }


@router.get("/bulk-poster/{job_id}/{emp_id}")
def bulk_poster(job_id: str, emp_id: str):
    """Serves one already-rendered poster from a completed bulk job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    template_id = job["template_id"]
    safe_emp_id = _safe_emp_id(emp_id)
    out_path = os.path.join(
        settings.output_dir, f"{template_id}_{safe_emp_id}.png"
    )
    if not os.path.exists(out_path):
        raise HTTPException(404, "Poster not found for this emp_id.")

    return FileResponse(out_path, media_type="image/png", filename=f"{emp_id}.png")


class BulkRestyleRequest(BaseModel):
    job_id: str
    style_overrides: list[dict] = []  # [{field_id, font_family, font_size, font_weight, color, align}]


@router.post("/bulk-restyle")
def bulk_restyle(req: BulkRestyleRequest):
    """
    Re-renders every poster in a completed job with style overrides applied.
    Does NOT call the LLM again — reuses the exact overlay_values that were
    already resolved during the original bulk run.
    """
    job = get_job(req.job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job["status"] != "done":
        raise HTTPException(409, "Job is still processing.")

    folder = job["folder"]
    template_id = job["template_id"]
    template = load_template(folder, template_id)
    if not template:
        raise HTTPException(404, "Template not found.")

    ov_path = _overlay_values_path(req.job_id)
    if not os.path.exists(ov_path):
        raise HTTPException(
            404,
            "No saved field values found for this job — it may predate "
            "the restyle feature, or nothing rendered successfully."
        )
    with open(ov_path, encoding="utf-8") as f:
        row_map = json.load(f)

    if not row_map:
        raise HTTPException(422, "No successful rows to restyle.")

    modified = copy.deepcopy(template)
    override_map = {o.get("field_id"): o for o in req.style_overrides}

    for layer in modified.get("overlay_layers", []):
        fid = layer.get("id")
        if fid in override_map:
            ov = override_map[fid]
            style = layer.setdefault("style", {})
            for key in ("font_family", "font_size", "font_weight", "color", "align"):
                if ov.get(key) is not None:
                    style[key] = ov[key]

    restyle_id = uuid.uuid4().hex
    output_files = []

    for emp_id, overlay_values in row_map.items():
        safe_emp_id = _safe_emp_id(emp_id)
        out_path = os.path.join(
            settings.output_dir,
            f"{template_id}_{safe_emp_id}_restyled.png"
        )
        try:
            render_poster(modified, overlay_values, out_path)
            output_files.append(out_path)
        except Exception as e:
            print(f"Restyle render failed for emp_id={emp_id}: {e}")

    if not output_files:
        raise HTTPException(500, "Restyle failed for all rows.")

    zip_path = os.path.join(
        settings.output_dir, f"{req.job_id}_restyled_{restyle_id}.zip"
    )
    with zipfile.ZipFile(zip_path, "w") as zf:
        for fp in output_files:
            zf.write(fp, os.path.basename(fp))

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename="posters_restyled.zip"
    )


def run_bulk_job(
    job_id: str,
    template: dict,
    template_id: str,
    folder: str,
    prompt: str,
    rows: list[dict]
):
    output_files = []
    audit_rows = []
    skipped_rows = []
    completed = skipped = failed = 0

    # emp_id -> resolved overlay_values, persisted to disk so /bulk-restyle
    # can re-render later without calling the LLM again.
    row_overlay_map: dict[str, dict] = {}

    os.makedirs(settings.output_dir, exist_ok=True)

    for idx, row in enumerate(rows):
        emp_id = str(row.get("emp_id", "")).strip()
        row_num = idx + 2
        safe_emp_id = _safe_emp_id(emp_id)
        out_path = os.path.join(
            settings.output_dir,
            f"{template_id}_{safe_emp_id}.png"
        )
        status = "success"
        skip_reason = ""

        overlay_values, skip_reasons = build_field_values_bulk_row(
            template, prompt, row
        )

        if skip_reasons:
            skipped += 1
            status = "skipped"
            skip_reason = "; ".join(r["reason"] for r in skip_reasons)
            skipped_rows.append({
                "row": row_num,
                "emp_id": emp_id,
                "reasons": skip_reasons
            })
        else:
            try:
                render_poster(template, overlay_values, out_path)
                output_files.append(out_path)
                row_overlay_map[emp_id] = overlay_values
                completed += 1
            except Exception as e:
                failed += 1
                status = "failed_render"
                skip_reason = str(e)

        audit_rows.append({
            "emp_id": emp_id,
            "template": template_id,
            "status": status,
            "output_file": out_path if status == "success" else "",
            "skip_reason": skip_reason,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S")
        })

        update_job(job_id, completed, skipped, failed)
        time.sleep(settings.bulk_row_delay_ms / 1000)

    # Write audit CSV — utf-8-sig for Excel compatibility with Hindi names
    audit_path = os.path.join(
        settings.output_dir, f"{job_id}_audit.csv"
    )
    with open(audit_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "emp_id", "template", "status",
                "output_file", "skip_reason", "generated_at"
            ]
        )
        writer.writeheader()
        writer.writerows(audit_rows)

    # Write skipped rows JSON
    skipped_path = os.path.join(
        settings.output_dir, f"{job_id}_skipped.json"
    )
    with open(skipped_path, "w", encoding="utf-8") as f:
        json.dump(skipped_rows, f, indent=2, ensure_ascii=False)

    # Persist resolved overlay values per emp_id for later restyling.
    with open(_overlay_values_path(job_id), "w", encoding="utf-8") as f:
        json.dump(row_overlay_map, f, indent=2, ensure_ascii=False)

    # ZIP everything
    zip_path = os.path.join(
        settings.output_dir, f"{job_id}_posters.zip"
    )
    with zipfile.ZipFile(zip_path, "w") as zf:
        for fp in output_files:
            if os.path.exists(fp):
                zf.write(fp, os.path.basename(fp))
        zf.write(audit_path, os.path.basename(audit_path))
        zf.write(skipped_path, os.path.basename(skipped_path))

    update_job(
        job_id, completed, skipped, failed,
        done=True, zip_path=zip_path
    )