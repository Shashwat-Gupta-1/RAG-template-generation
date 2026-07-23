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

from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile, Depends, Request
from fastapi.responses import FileResponse, JSONResponse
import base64
import uuid

from backend.config import settings
from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.database.models import User
from backend.services import job_service, history_service
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from backend.processing.field_split import (
    NEEDS_IMAGE,
    build_column_map,
    split_row,
)
from backend.processing.llm import fill_invent_fields_only
from backend.processing.rag import retrieve_template_overlay, load_template, load_all_templates_in_folder, search_folder
from backend.processing.renderer import render_overlay
from backend.validation.excel_validator import validate_excel, get_excel_template

router = APIRouter()

async def _fetch_image_bytes(url: str) -> Optional[bytes]:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8"
        }
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url.strip(), headers=headers)
            resp.raise_for_status()
            return resp.content
    except Exception as e:
        print(f"Warning: Failed to fetch image from URL {url}: {e}")
        return None

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

    # Check if this is per-layer override (at least one value is a dict)
    is_per_layer = any(isinstance(v, dict) for v in overrides.values())

    for layer in patched.get("overlay_layers") or []:
        if str(layer.get("type", "")).lower() != "text":
            continue
        
        lid = layer.get("id")
        style = layer.setdefault("style", {})

        if is_per_layer:
            if lid and lid in overrides:
                layer_overrides = overrides[lid]
                for key in allowed_keys:
                    val = layer_overrides.get(key)
                    if val is not None and val != "":
                        style[key] = val
        else:
            for key in allowed_keys:
                val = overrides.get(key)
                if val is not None and val != "":
                    style[key] = val

    return patched

def _apply_layout_overrides(template: dict, overrides: dict) -> dict:
    """
    Return a deep-copied template with customized layer coordinates.
    """
    import copy
    if not overrides:
        return template

    patched = copy.deepcopy(template)

    for layer in patched.get("overlay_layers") or []:
        layer_id = layer.get("id")
        if layer_id in overrides:
            layer_override = overrides[layer_id]
            box = layer.setdefault("box", {})
            for key in ("x", "y", "width", "height"):
                if key in layer_override:
                    try:
                        box[key] = int(layer_override[key])
                    except (ValueError, TypeError):
                        pass

    return patched

async def _run_bulk_job(
    job_id: str,
    overlay: Dict[str, Any],
    df,                        # pandas DataFrame
    column_map: Dict[str, str],
    photo_bytes: Optional[bytes],
    prompt: str,
    extra_inputs: Dict[str, str] = None,
    direct_caption: Optional[str] = None,
) -> None:
    extra_inputs = extra_inputs or {}
    """
    Runs in the background after HTTP response is sent.
    Processes every row, renders a PNG, zips them all.
    """
    from backend.database.session import AsyncSessionLocal
    output_dir = Path(settings.output_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / f"{job_id}.zip"

    # Audit records — rows that were skipped due to missing required fields
    skipped_rows = []
    completed   = 0
    total       = len(df)

    async with AsyncSessionLocal() as db:
        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for idx, (_, row) in enumerate(df.iterrows()):
                    row_dict = row.to_dict()
                    row_dict.update(extra_inputs)
                    emp_id   = str(row_dict.get("emp_id", f"row_{idx}")).strip()

                    # ── Build values dict for this row ─────────────────────────
                    values = split_row(overlay, row_dict, column_map, prompt=prompt)

                    # ── Apply extra_inputs directly (replaces sentinels, LLM skips them) ──
                    for k, v in extra_inputs.items():
                        if v is not None and str(v).strip() != "":
                            values[k] = str(v).strip()

                    # ── Apply direct_caption — highest priority, always wins ───
                    if direct_caption and direct_caption.strip():
                        if "caption" in values:   # only if template has a caption field
                            values["caption"] = direct_caption.strip()
                            print(f"[bulk] Row {idx}: caption locked to '{direct_caption.strip()}'")

                    # ── Fill inventable fields via LLM ─────────────────────────
                    context = json.dumps(
                        {k: v for k, v in row_dict.items() if k != "emp_id" and not isinstance(v, bytes)},
                        ensure_ascii=False
                    )
                    values = fill_invent_fields_only(overlay, values, context=context)

                    # ── Re-apply direct_caption after LLM (final guard) ────────
                    if direct_caption and direct_caption.strip() and "caption" in values:
                        values["caption"] = direct_caption.strip()

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
                        await job_service.update_progress(db, uuid.UUID(job_id), completed, skipped=len(skipped_rows))
                        continue

                    # ── Resolve image zones (URL or Photo Bytes) ────────────────
                    for fid, val in values.items():
                        if val == NEEDS_IMAGE:
                            values[fid] = photo_bytes  # None if no photo uploaded
                        elif isinstance(val, str) and (val.startswith("http://") or val.startswith("https://")):
                            # It's a URL from Excel, fetch it
                            fetched = await _fetch_image_bytes(val)
                            if fetched:
                                values[fid] = fetched
                            else:
                                values[fid] = photo_bytes # fallback

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

                    await job_service.update_progress(db, uuid.UUID(job_id), completed, skipped=len(skipped_rows))

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

            await job_service.mark_done(db, uuid.UUID(job_id), zip_path=str(zip_path), download_url=f"/download/{job_id}")

        except Exception as exc:
            await job_service.mark_failed(db, uuid.UUID(job_id), error=str(exc))


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/bulk")
async def bulk_generate(
    background_tasks: BackgroundTasks,
    request: Request,
    prompt: str = Form(...),
    excel_file: UploadFile = File(...),
    photo: Optional[UploadFile] = File(None),
    style_overrides: str = Form(None),
    layout_overrides: str = Form(None),
    column_mapping: str = Form(None),
    folder: Optional[str] = Form(None),
    template_id: Optional[str] = Form(None),
    direct_caption: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    # Step 1 — Find matching template
    if template_id and folder:
        overlay = load_template(folder, template_id)
        if overlay:
            overlay["folder"] = folder
    else:
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

    # Apply layout overrides
    if layout_overrides:
        try:
            parsed_layout = json.loads(layout_overrides)
            overlay = _apply_layout_overrides(overlay, parsed_layout)
        except (json.JSONDecodeError, TypeError):
            pass

    custom_column_map = None
    if column_mapping:
        try:
            custom_column_map = json.loads(column_mapping)
        except (json.JSONDecodeError, TypeError):
            pass

    # Step 2 — Read and validate Excel
    file_bytes = await excel_file.read()
    df, errors = validate_excel(file_bytes, overlay, custom_column_map)
    if errors:
        return JSONResponse(
            status_code=422,
            content={"errors": errors}
        )

    form_data = await request.form()
    extra_inputs = {}
    for key, value in form_data.items():
        if key not in {"prompt", "template_id", "folder", "photo", "style_overrides", "layout_overrides", "column_mapping", "excel_file"}:
            if isinstance(value, str):
                extra_inputs[key] = value.strip()

    # Step 3 — Build column map once for entire batch
    if custom_column_map:
        column_map = custom_column_map
    else:
        column_map = build_column_map(overlay, list(df.columns) + list(extra_inputs.keys()))

    # Step 4 — Read photo if provided
    photo_bytes = await photo.read() if photo else None

    # Step 5 — Create job and hand off to background
    job_convo = await job_service.create_job(
        db,
        user_id=current_user.id,
        total_rows=len(df),
        template_folder=overlay.get("folder"),
        template_id=overlay.get("template_id"),
        title=f"{prompt[:50]} ({len(df)} rows)" if prompt else f"Bulk: {len(df)} rows"
    )
    job_id = str(job_convo.id)
    
    # Save the user's message to conversation history
    await history_service.add_message(
        db,
        conversation_id=job_convo.id,
        role="user",
        content=f"Bulk generation: {prompt}"
    )

    background_tasks.add_task(
        _run_bulk_job,
        job_id,
        overlay,
        df,
        column_map,
        photo_bytes,
        prompt,
        extra_inputs,
        direct_caption.strip() if direct_caption and direct_caption.strip() else None,
    )

    return JSONResponse(content={
        "job_id":     job_id,
        "status":     "queued",
        "total_rows": len(df),
        "message":    f"Job started. {len(df)} rows queued."
    })


@router.post("/bulk/preview")
async def bulk_preview(
    request: Request,
    prompt: str = Form(...),
    excel_file: UploadFile = File(...),
    photo: Optional[UploadFile] = File(None),
    style_overrides: str = Form(None),
    layout_overrides: str = Form(None),
    column_mapping: str = Form(None),
    folder: Optional[str] = Form(None),
    template_id: Optional[str] = Form(None),
    direct_caption: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
):
    """
    Generate a preview poster for the first row of an Excel sheet.
    """
    overlay = None

    # 1. Direct template match
    if template_id and folder:
        overlay = load_template(folder, template_id)
        if overlay:
            overlay["folder"] = folder
        else:
            return JSONResponse(
                status_code=200,
                content={
                    "error": "Template not found.",
                    "suggest_create": True,
                }
            )

    # 2. Match folder templates
    elif folder:
        all_templates = load_all_templates_in_folder(folder)
        if not all_templates:
            return JSONResponse(
                status_code=200,
                content={
                    "error": "No templates in matched folder.",
                    "suggest_create": True,
                }
            )
        if len(all_templates) == 1:
            overlay = all_templates[0]
            overlay["folder"] = folder
        else:
            return JSONResponse(
                status_code=200,
                content={
                    "status": "gallery",
                    "folder": folder,
                    "display_name": folder.replace("_", " ").title(),
                    "templates": [
                        {
                            "template_id": t["template_id"],
                            "description": t["description"],
                            "base_image": t.get("base_image"),
                        }
                        for t in all_templates
                    ],
                }
            )

    # 3. Full RAG search with ambiguity gap check
    else:
        matches = search_folder(prompt, top_k=3)
        if not matches:
            return JSONResponse(
                status_code=200,
                content={
                    "status": "no_match",
                    "suggest_create": True,
                }
            )

        # Ambiguity check
        if (len(matches) > 1 and
                matches[0]["score"] - matches[1]["score"] < settings.ambiguity_gap):
            best_score = matches[0]["score"]
            ambiguous_matches = [
                m for m in matches
                if best_score - m["score"] < settings.ambiguity_gap
            ]
            # Check if the user explicitly mentioned exactly one of the folder names in the query
            mentioned = [m for m in ambiguous_matches if m["folder"].lower() in prompt.lower()]
            if len(mentioned) == 1:
                best = mentioned[0]
            else:
                return JSONResponse(
                    status_code=200,
                    content={
                        "status": "ambiguous",
                        "matches": [
                            {
                                "folder": m["folder"],
                                "display_name": m["display_name"],
                                "score": m["score"],
                            }
                            for m in ambiguous_matches
                        ],
                    }
                )
        else:
            best = matches[0]

        best_folder = best["folder"]
        all_templates = load_all_templates_in_folder(best_folder)
        if not all_templates:
            return JSONResponse(
                status_code=200,
                content={
                    "error": "No templates in matched folder.",
                    "suggest_create": True,
                }
            )

        if len(all_templates) == 1:
            overlay = all_templates[0]
            overlay["folder"] = best_folder
        else:
            return JSONResponse(
                status_code=200,
                content={
                    "status": "gallery",
                    "folder": best_folder,
                    "display_name": best["display_name"],
                    "templates": [
                        {
                            "template_id": t["template_id"],
                            "description": t["description"],
                            "base_image": t.get("base_image"),
                        }
                        for t in all_templates
                    ],
                }
            )

    # Apply style overrides
    if style_overrides:
        try:
            parsed_overrides = json.loads(style_overrides)
            overlay = _apply_style_overrides(overlay, parsed_overrides)
        except (json.JSONDecodeError, TypeError):
            pass

    # Apply layout overrides
    if layout_overrides:
        try:
            parsed_layout = json.loads(layout_overrides)
            overlay = _apply_layout_overrides(overlay, parsed_layout)
        except (json.JSONDecodeError, TypeError):
            pass

    custom_column_map = None
    if column_mapping:
        try:
            custom_column_map = json.loads(column_mapping)
        except (json.JSONDecodeError, TypeError):
            pass

    file_bytes = await excel_file.read()
    df, errors = validate_excel(file_bytes, overlay, custom_column_map)
    if errors:
        excel_cols = []
        try:
            from backend.validation.excel_validator import read_excel
            df_cols, _ = read_excel(file_bytes)
            if df_cols is not None:
                excel_cols = list(df_cols.columns)
        except Exception:
            pass

        default_map = custom_column_map if custom_column_map else build_column_map(overlay, excel_cols)
        return JSONResponse(
            status_code=422,
            content={
                "errors": errors,
                "template_id": overlay.get("template_id"),
                "folder": overlay.get("folder"),
                "overlay_layers": overlay.get("overlay_layers"),
                "column_map": default_map,
                "excel_columns": excel_cols,
            }
        )

    if df.empty:
        return JSONResponse(
            status_code=400,
            content={"error": "Excel file is empty."}
        )

    form_data = await request.form()
    extra_inputs = {}
    for key, value in form_data.items():
        if key not in {"prompt", "template_id", "folder", "photo", "style_overrides", "layout_overrides", "column_mapping", "excel_file"}:
            if isinstance(value, str):
                extra_inputs[key] = value.strip()

    if custom_column_map:
        column_map = custom_column_map
    else:
        column_map = build_column_map(overlay, list(df.columns) + list(extra_inputs.keys()))

    photo_bytes = await photo.read() if photo else None

    # Get first row data
    first_row = df.iloc[0].to_dict()
    first_row.update(extra_inputs)
    values = split_row(overlay, first_row, column_map, prompt=prompt)

    # Apply extra_inputs directly (replaces sentinels so LLM skips them)
    for k, v in extra_inputs.items():
        if v is not None and str(v).strip() != "":
            values[k] = str(v).strip()

    # Apply direct_caption — highest priority, before LLM
    if direct_caption and direct_caption.strip() and "caption" in values:
        values["caption"] = direct_caption.strip()
        print(f"[bulk/preview] caption locked to '{direct_caption.strip()}'")

    # Fill inventable fields via LLM
    context = json.dumps(
        {k: v for k, v in first_row.items() if k != "emp_id" and not isinstance(v, bytes)},
        ensure_ascii=False
    )
    values = fill_invent_fields_only(overlay, values, context=context)

    # Re-apply direct_caption after LLM (final guard)
    if direct_caption and direct_caption.strip() and "caption" in values:
        values["caption"] = direct_caption.strip()

    # Replace image zones
    for fid, val in values.items():
        if val == NEEDS_IMAGE:
            print(f"[DEBUG] Field {fid} was NEEDS_IMAGE, using global photo.")
            values[fid] = photo_bytes
        elif isinstance(val, bytes):
            print(f"[DEBUG] Field {fid} received bytes from Excel (length: {len(val)})")
        elif isinstance(val, str) and (val.startswith("http://") or val.startswith("https://")):
            print(f"[DEBUG] Field {fid} received URL from Excel. Fetching...")
            fetched = await _fetch_image_bytes(val)
            if fetched:
                print(f"[DEBUG] Successfully fetched URL for {fid}")
                values[fid] = fetched
            else:
                print(f"[DEBUG] Failed to fetch URL for {fid}, falling back to photo_bytes.")
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
            "canvas": overlay.get("canvas"),
            "overlay_layers": overlay.get("overlay_layers"),
            "column_map": column_map,
            "excel_columns": list(df.columns),
        })
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to render preview: {exc}"}
        )


@router.get("/job-status/{job_id}")
async def job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Poll for bulk job progress.

    Response:
        {
            job_id, status, total, completed, skipped, failed,
            download_url (when done), error (if failed)
        }
    """
    try:
        job = await job_service.get_job(db, uuid.UUID(job_id), current_user.id)
    except Exception:
        job = None
        
    if not job:
        return JSONResponse(
            status_code=404,
            content={"error": f"Job {job_id} not found"}
        )
    return JSONResponse(content=job)


@router.get("/download/{job_id}")
async def download_zip(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Serve the completed ZIP file."""
    # Verify ownership
    try:
        await job_service.get_job(db, uuid.UUID(job_id), current_user.id)
    except Exception:
        return JSONResponse(
            status_code=404,
            content={"error": "Job not found or access denied."}
        )

    zip_path = Path(settings.output_path) / f"{job_id}.zip"
    if not zip_path.exists():
        return JSONResponse(
            status_code=404,
            content={"error": "File not ready or job still processing"}
        )
    return FileResponse(
        path=str(zip_path),
        media_type="application/zip",
        filename=f"posters_{job_id[:8]}.zip"
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