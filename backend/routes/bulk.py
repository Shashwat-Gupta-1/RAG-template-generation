"""
Bulk Excel Route
----------------
POST /bulk
  - Accepts: prompt + Excel file + optional shared photo
  - Validates Excel structure against the matched template's overlay.json
  - Runs all rows as a background job
  - Returns job_id immediately — user polls for progress

GET /job-status/{job_id}
  - Returns current job status, progress, and download URL when done

GET /download/{job_id}
  - Serves the completed ZIP file

The key design: Excel columns are DYNAMIC per template.
  - Holi poster Excel: emp_id, name
  - Grand opening Excel: emp_id, branch_name, venue, time
  - Loan offer Excel: emp_id, name, mobile_number, city

The validator reads the overlay.json to know which columns are required.
No hardcoding of column names anywhere.
"""

from __future__ import annotations

import csv
import io
import json
import os
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
import base64

from backend.config import settings
from backend.jobs.job_tracker import (
    create_job,
    get_job,
    mark_done,
    mark_failed,
    update_progress,
)
from backend.processing.field_split import (
    NEEDS_IMAGE,
    build_column_map,
    split_row,
)
from backend.processing.llm import fill_invent_fields_only
from backend.processing.rag import retrieve_template_overlay
from backend.processing.renderer import render_overlay
from backend.validation.excel_validator import validate_excel, get_excel_template

router = APIRouter()


# ── Background job ────────────────────────────────────────────────────────────

def _apply_style_overrides(template: dict, overrides: dict) -> dict:
    """
    Return a deep-copied template with user style overrides patched into
    every text layer's style block.
    """
    import copy
    if not overrides:
        return template

    patched = copy.deepcopy(template)
    allowed_keys = {"font_family", "font_size", "font_weight", "color"}

    for layer in patched.get("overlay_layers") or []:
        if str(layer.get("type", "")).lower() != "text":
            continue
        style = layer.setdefault("style", {})
        for key in allowed_keys:
            val = overrides.get(key)
            if val is not None and val != "":
                style[key] = val

    return patched

def _run_bulk_job(
    job_id: str,
    overlay: Dict[str, Any],
    df,                        # pandas DataFrame
    column_map: Dict[str, str],
    photo_bytes: Optional[bytes],
    prompt: str,
) -> None:
    """
    Runs in the background after HTTP response is sent.
    Processes every row, renders a PNG, zips them all.
    """
    output_dir = Path(settings.output_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / f"{job_id}.zip"

    # Audit records — rows that were skipped due to missing required fields
    skipped_rows = []
    completed   = 0
    total       = len(df)

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for idx, (_, row) in enumerate(df.iterrows()):
                row_dict = row.to_dict()
                emp_id   = str(row_dict.get("emp_id", f"row_{idx}")).strip()

                # ── Build values dict for this row ─────────────────────────
                values = split_row(overlay, row_dict, column_map, prompt=prompt)

                # ── Fill inventable fields via LLM ─────────────────────────
                # Build context string so LLM has name/branch info for creative text
                context = json.dumps(
                    {k: v for k, v in row_dict.items() if k != "emp_id"},
                    ensure_ascii=False
                )
                values = fill_invent_fields_only(overlay, values, context=context)

                # ── Check for missing required fields ──────────────────────
                missing = [
                    fid for fid, val in values.items()
                    if val is None and fid != "emp_id"
                ]
                if missing:
                    skipped_rows.append({
                        "emp_id": emp_id,
                        "row": idx + 2,   # Excel row number
                        "missing_fields": missing,
                        "reason": "Required field(s) missing in Excel and cannot be invented"
                    })
                    update_progress(job_id, completed)
                    continue

                # ── Replace image sentinel with actual photo bytes ─────────
                for fid, val in values.items():
                    if val == NEEDS_IMAGE:
                        values[fid] = photo_bytes  # None if no photo uploaded

                # ── Render poster ──────────────────────────────────────────
                try:
                    image = render_overlay(overlay, values)
                    img_bytes = io.BytesIO()
                    image.convert("RGB").save(img_bytes, format="PNG")
                    zf.writestr(f"{emp_id}.png", img_bytes.getvalue())
                    completed += 1
                except Exception as render_err:
                    skipped_rows.append({
                        "emp_id": emp_id,
                        "row": idx + 2,
                        "missing_fields": [],
                        "reason": f"Render error: {render_err}"
                    })

                update_progress(job_id, completed)

            # ── Write audit CSV into the ZIP ───────────────────────────────
            if skipped_rows:
                audit_buf = io.StringIO()
                writer = csv.DictWriter(
                    audit_buf,
                    fieldnames=["emp_id", "row", "missing_fields", "reason"]
                )
                writer.writeheader()
                for rec in skipped_rows:
                    rec["missing_fields"] = ", ".join(rec["missing_fields"])
                    writer.writerow(rec)
                zf.writestr(
                    "audit_skipped.csv",
                    audit_buf.getvalue().encode("utf-8-sig")  # BOM for Excel
                )

        mark_done(job_id, download_url=f"/download/{job_id}")

    except Exception as exc:
        mark_failed(job_id, error=str(exc))


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/bulk")
async def bulk_generate(
    background_tasks: BackgroundTasks,
    prompt: str = Form(...),
    excel_file: UploadFile = File(...),
    photo: Optional[UploadFile] = File(None),
    style_overrides: str = Form(None),
):
    """
    Start a bulk generation job.

    Request:
        prompt      — natural language describing the poster type
        excel_file  — .xlsx with emp_id + template-specific columns
        photo       — optional shared photo for image zones

    Response:
        { job_id, status, total_rows }
    """
    # Step 1 — Find matching template from prompt
    overlay = retrieve_template_overlay(prompt)
    if not overlay:
        return JSONResponse(
            status_code=200,
            content={
                "error": "No matching template found for this prompt.",
                "suggest_create": True,
            }
        )

    # Apply style overrides
    if style_overrides:
        try:
            parsed_overrides = json.loads(style_overrides)
            overlay = _apply_style_overrides(overlay, parsed_overrides)
        except (json.JSONDecodeError, TypeError):
            pass

    # Step 2 — Read and validate Excel
    file_bytes = await excel_file.read()
    df, errors = validate_excel(file_bytes, overlay)
    if errors:
        return JSONResponse(
            status_code=422,
            content={"errors": errors}
        )

    # Step 3 — Build column map once for entire batch
    # This maps overlay field IDs to Excel column names
    # e.g. { "name": "Name", "branch_name": "Branch Name" }
    column_map = build_column_map(overlay, list(df.columns))

    # Step 4 — Read photo if provided
    photo_bytes = await photo.read() if photo else None

    # Step 5 — Create job and hand off to background
    job_id = create_job(total_rows=len(df))
    background_tasks.add_task(
        _run_bulk_job,
        job_id,
        overlay,
        df,
        column_map,
        photo_bytes,
        prompt,
    )

    return JSONResponse(content={
        "job_id":     job_id,
        "status":     "queued",
        "total_rows": len(df),
        "message":    f"Job started. {len(df)} rows queued."
    })


@router.post("/bulk/preview")
async def bulk_preview(
    prompt: str = Form(...),
    excel_file: UploadFile = File(...),
    photo: Optional[UploadFile] = File(None),
    style_overrides: str = Form(None),
):
    """
    Generate a preview poster for the first row of an Excel sheet.
    """
    overlay = retrieve_template_overlay(prompt)
    if not overlay:
        return JSONResponse(
            status_code=200,
            content={
                "error": "No matching template found for this prompt.",
                "suggest_create": True,
            }
        )

    # Apply style overrides
    if style_overrides:
        try:
            parsed_overrides = json.loads(style_overrides)
            overlay = _apply_style_overrides(overlay, parsed_overrides)
        except (json.JSONDecodeError, TypeError):
            pass

    file_bytes = await excel_file.read()
    df, errors = validate_excel(file_bytes, overlay)
    if errors:
        return JSONResponse(
            status_code=422,
            content={"errors": errors}
        )

    if df.empty:
        return JSONResponse(
            status_code=400,
            content={"error": "Excel file is empty."}
        )

    column_map = build_column_map(overlay, list(df.columns))
    photo_bytes = await photo.read() if photo else None

    # Get first row data
    first_row = df.iloc[0].to_dict()
    values = split_row(overlay, first_row, column_map, prompt=prompt)

    # Fill inventable fields via LLM
    context = json.dumps(
        {k: v for k, v in first_row.items() if k != "emp_id"},
        ensure_ascii=False
    )
    values = fill_invent_fields_only(overlay, values, context=context)

    # Replace image zones
    for fid, val in values.items():
        if val == NEEDS_IMAGE:
            values[fid] = photo_bytes

    try:
        image = render_overlay(overlay, values)
        img_bytes = io.BytesIO()
        image.convert("RGB").save(img_bytes, format="PNG")
        b64_str = base64.b64encode(img_bytes.getvalue()).decode("utf-8")
        
        return JSONResponse(content={
            "preview_image": b64_str,
            "total_rows": len(df),
            "template_id": overlay.get("template_id"),
            "folder": overlay.get("folder"),
        })
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to render preview: {exc}"}
        )


@router.get("/job-status/{job_id}")
async def job_status(job_id: str):
    """
    Poll for bulk job progress.

    Response:
        {
            job_id, status, total_rows, completed_rows,
            download_url (when done), error (if failed)
        }
    """
    job = get_job(job_id)
    if not job:
        return JSONResponse(
            status_code=404,
            content={"error": f"Job {job_id} not found"}
        )
    return JSONResponse(content=job)


@router.get("/download/{job_id}")
async def download_zip(job_id: str):
    """Serve the completed ZIP file."""
    zip_path = Path(settings.output_path) / f"{job_id}.zip"
    if not zip_path.exists():
        return JSONResponse(
            status_code=404,
            content={"error": "File not ready or job still processing"}
        )
    return FileResponse(
        path=str(zip_path),
        media_type="application/zip",
        filename=f"posters_{job_id}.zip"
    )


@router.get("/excel-template/{template_id}")
async def download_excel_template(template_id: str):
    """
    Download a blank Excel template pre-populated with the correct column headers
    for a given template. Helps users know what columns to fill in.

    Usage: User selects a template → downloads this → fills it in → uploads for bulk.
    """
    import importlib, json as _json
    from pathlib import Path as _Path

    # Find the overlay.json for this template
    templates_dir = _Path(settings.templates_dir)
    overlay_path  = None

    for candidate in templates_dir.rglob("overlay.json"):
        data = _json.loads(candidate.read_text(encoding="utf-8"))
        if data.get("template_id") == template_id:
            overlay_path = candidate
            overlay      = data
            break

    if not overlay_path:
        return JSONResponse(
            status_code=404,
            content={"error": f"Template '{template_id}' not found"}
        )

    df = get_excel_template(overlay)

    # Write to bytes buffer
    buf = io.BytesIO()
    with importlib.import_module("openpyxl").Workbook() as wb:
        ws = wb.active
        ws.append(list(df.columns))   # header row
        wb.save(buf)

    buf.seek(0)
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={template_id}_template.xlsx"}
    )