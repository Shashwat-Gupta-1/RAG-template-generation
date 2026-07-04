from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from processing.rag import search_folder, load_template, load_all_templates_in_folder
from processing.field_split import validate_excel_structure, build_field_values_bulk_row
from processing.renderer import render_poster
from validation.excel_validator import validate_excel_file
from jobs.job_tracker import init_db, create_job, update_job, get_job
from config import settings
import pandas as pd, io, uuid, zipfile, csv, time, os, json

router = APIRouter()
init_db()

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
        raise HTTPException(422, "Could not read file. Upload .xlsx or .csv")

    validate_excel_file(df)

    if folder and template_id:
        template = load_template(folder, template_id)
        if not template:
            raise HTTPException(404, "Template not found.")
    else:
        matches = search_folder(prompt)
        if not matches:
            return {"status": "no_match", "trigger_phase2": True}

        if (len(matches) > 1 and
                matches[0]["score"] - matches[1]["score"] < settings.ambiguity_gap):
            return {"status": "ambiguous", "matches": [
                {"folder": m["folder"], "display_name": m["display_name"]}
                for m in matches
            ]}

        best = matches[0]
        folder = best["folder"]

        if len(best["templates"]) == 1:
            template = load_template(folder, best["templates"][0])
        else:
            all_templates = load_all_templates_in_folder(folder)
            return {
                "status": "gallery",
                "folder": folder,
                "display_name": best["display_name"],
                "templates": [
                    {"template_id": t["template_id"], "description": t["description"]}
                    for t in all_templates
                ]
            }

    structure_error = validate_excel_structure(template, df.columns.tolist())
    if structure_error:
        return structure_error

    job_id = uuid.uuid4().hex
    rows = df.to_dict(orient="records")
    create_job(job_id, len(rows))
    background_tasks.add_task(run_bulk_job, job_id, template, prompt, rows)
    return {"status": "queued", "job_id": job_id, "total_rows": len(rows)}

@router.get("/job-status/{job_id}")
def job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job

def run_bulk_job(job_id: str, template: dict, prompt: str, rows: list[dict]):
    template_id = template["template_id"]
    output_files, audit_rows, skipped_rows = [], [], []
    completed = skipped = failed = 0

    os.makedirs(settings.output_dir, exist_ok=True)

    for idx, row in enumerate(rows):
        emp_id = str(row.get("emp_id", "")).strip()
        row_num = idx + 2
        out_path = os.path.join(settings.output_dir, f"{template_id}_{emp_id}.png")
        status = "success"
        skip_reason = ""

        overlay_values, skip_reasons = build_field_values_bulk_row(template, prompt, row)

        if skip_reasons:
            skipped += 1
            status = "skipped"
            skip_reason = "; ".join(r["reason"] for r in skip_reasons)
            skipped_rows.append({"row": row_num, "emp_id": emp_id, "reasons": skip_reasons})
        else:
            try:
                render_poster(template, overlay_values, out_path)
                output_files.append(out_path)
                completed += 1
            except Exception as e:
                failed += 1
                status = "failed_render"
                skip_reason = str(e)

        audit_rows.append({
            "emp_id": emp_id, "template": template_id, "status": status,
            "output_file": out_path if status == "success" else "",
            "skip_reason": skip_reason,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S")
        })
        update_job(job_id, completed, skipped, failed)
        time.sleep(settings.bulk_row_delay_ms / 1000)

    audit_path = os.path.join(settings.output_dir, f"{job_id}_audit.csv")
    with open(audit_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f, fieldnames=["emp_id", "template", "status",
                           "output_file", "skip_reason", "generated_at"]
        )
        writer.writeheader()
        writer.writerows(audit_rows)

    skipped_path = os.path.join(settings.output_dir, f"{job_id}_skipped.json")
    with open(skipped_path, "w", encoding="utf-8") as f:
        json.dump(skipped_rows, f, indent=2, ensure_ascii=False)

    zip_path = os.path.join(settings.output_dir, f"{job_id}_posters.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        for fp in output_files:
            if os.path.exists(fp):
                zf.write(fp, os.path.basename(fp))
        zf.write(audit_path, os.path.basename(audit_path))
        zf.write(skipped_path, os.path.basename(skipped_path))

    update_job(job_id, completed, skipped, failed, done=True, zip_path=zip_path)