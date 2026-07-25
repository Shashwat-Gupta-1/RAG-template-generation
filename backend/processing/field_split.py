"""
Field Split Engine
------------------
For each field in overlay.json, decides where the value comes from.

Priority order:
  1. Excel column has a value        → copy directly, no LLM
  2. llm_can_invent = true           → LLM generates creative text
  3. llm_can_invent = false, no value → return None (triggers fallback/skip)
  4. type = image                    → uploaded photo bytes used directly

This module never calls the LLM directly.
It only decides WHAT SOURCE each field uses.
The actual LLM call happens in llm.py.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

# Sentinel values — replaced by llm.py in the next step
NEEDS_LLM_INVENT  = "__LLM_INVENT__"    # LLM should generate creative content
NEEDS_LLM_EXTRACT = "__LLM_EXTRACT__"   # LLM should extract from prompt
NEEDS_IMAGE       = "__IMAGE__"          # Use uploaded photo bytes


def get_overlay_fields(overlay: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return all layers from overlay.json."""
    return overlay.get("overlay_layers") or []


def build_column_map(overlay: Dict[str, Any], excel_columns: List[str]) -> Dict[str, str]:
    """
    Match overlay field IDs to Excel column names.
    Supports case-insensitive matching and image column alias resolution.
    Returns { field_id: excel_column_name }
    """
    column_map: Dict[str, str] = {}
    lower_columns = {col.lower(): col for col in excel_columns}

    image_aliases = {"image", "photo", "pic", "picture", "logo", "qr", "qr_code", "pattern", "link", "url", "image_url"}

    for layer in get_overlay_fields(overlay):
        field_id = layer.get("id", "").strip()
        if not field_id:
            continue

        field_type = layer.get("type", "text")
        field_id_lower = field_id.lower()

        # Try exact match (case-insensitive)
        matched_col = lower_columns.get(field_id_lower)
        if matched_col:
            column_map[field_id] = matched_col
            continue

        # If it's an image layer or image alias field, check image aliases in Excel
        if field_type == "image" or field_id_lower in image_aliases:
            for alias in ("image", "photo", "picture", "url", "link", "image_url", "pic", "logo"):
                if alias in lower_columns:
                    column_map[field_id] = lower_columns[alias]
                    break

    # Auto-match emp_id if present in Excel columns
    if "emp_id" not in column_map:
        for emp_alias in ("emp_id", "employee_id", "id", "emp_no", "sr_no", "code", "user_id"):
            if emp_alias in lower_columns:
                column_map["emp_id"] = lower_columns[emp_alias]
                break

    return column_map



def validate_excel_columns(
    overlay: Dict[str, Any],
    excel_columns: List[str],
) -> List[str]:
    """
    Check that every non-inventable, non-image field in the overlay
    has a matching column in the Excel file.

    Returns a list of error messages.
    Empty list = valid, proceed.
    Non-empty list = reject the batch.

    This is a HARD check — if required columns are missing,
    the entire batch is rejected before a single row is processed.
    """
    errors: List[str] = []
    column_map = build_column_map(overlay, excel_columns)

    for layer in get_overlay_fields(overlay):
        field_id    = layer.get("id", "").strip()
        field_type  = layer.get("type", "text")
        can_invent  = layer.get("llm_can_invent", False)

        if not field_id or field_type == "image":
            continue   # image fields use uploaded photo, not Excel

        if not can_invent and field_id not in column_map:
            errors.append(
                f"Required column '{field_id}' not found in Excel. "
                f"Columns present: {excel_columns}"
            )

    return errors


import math

def is_valid_value(val: Any) -> bool:
    if val is None:
        return False
    if isinstance(val, float) and math.isnan(val):
        return False
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "null", "undefined", "<na>"):
        return False
    return True


def split_row(
    overlay: Dict[str, Any],
    excel_row: Dict[str, Any],
    column_map: Dict[str, str],
    prompt: str = "",
) -> Dict[str, Any]:
    """
    For one Excel row, build the values dict.

    Returns:
      {
        "field_id": "Rahul Kumar",          # copied from Excel
        "greeting_line": "__LLM_INVENT__",  # LLM will generate this
        "photo": "__IMAGE__",               # use uploaded photo
      }

    The sentinels (__LLM_INVENT__, __IMAGE__) are replaced
    by llm.py and the route handler respectively.
    """
    values: Dict[str, Any] = {}

    for layer in get_overlay_fields(overlay):
        field_id   = layer.get("id", "").strip()
        field_type = layer.get("type", "text")
        can_invent = layer.get("llm_can_invent", False)

        if not field_id:
            continue

        # ── Image field ───────────────────────────────────────────────────
        if field_type == "image":
            excel_col = column_map.get(field_id)
            if excel_col and excel_col in excel_row:
                cell_value = excel_row[excel_col]
                if is_valid_value(cell_value):
                    values[field_id] = str(cell_value).strip()
                    continue
            values[field_id] = NEEDS_IMAGE
            continue


        # ── Excel has the value ───────────────────────────────────────────
        excel_col = column_map.get(field_id)
        if excel_col and excel_col in excel_row:
            cell_value = excel_row[excel_col]
            if is_valid_value(cell_value):
                values[field_id] = str(cell_value).strip()
                continue

        # ── LLM can invent it ─────────────────────────────────────────────
        if can_invent:
            values[field_id] = NEEDS_LLM_INVENT
            continue

        # ── Required field missing from Excel row ─────────────────────────
        # Soft skip for bulk — row will be flagged in audit CSV
        values[field_id] = None

    return values



def split_single(
    overlay: Dict[str, Any],
    prompt: str,
) -> Dict[str, Any]:
    """
    For single poster generation (no Excel).
    All non-inventable fields need LLM extraction from the prompt.
    All inventable fields need LLM generation.
    """
    values: Dict[str, Any] = {}

    for layer in get_overlay_fields(overlay):
        field_id   = layer.get("id", "").strip()
        field_type = layer.get("type", "text")
        can_invent = layer.get("llm_can_invent", False)

        if not field_id:
            continue

        if field_type == "image":
            values[field_id] = NEEDS_IMAGE
            continue

        if can_invent:
            values[field_id] = NEEDS_LLM_INVENT
        else:
            values[field_id] = NEEDS_LLM_EXTRACT

    return values


def has_missing_required(overlay: Dict[str, Any], values: Dict[str, Any]) -> List[str]:
    """
    After LLM fill, check if any required (non-inventable) field is still None.
    Returns list of missing field IDs.
    Used to trigger fallback form in single generation.
    """
    missing = []
    for layer in get_overlay_fields(overlay):
        field_id   = layer.get("id", "").strip()
        can_invent = layer.get("llm_can_invent", False)
        field_type = layer.get("type", "text")

        if not field_id or can_invent or field_type == "image":
            continue

        v = values.get(field_id)
        if v is None or str(v).strip() == "" or v in (NEEDS_LLM_EXTRACT, NEEDS_LLM_INVENT):
            missing.append(field_id)

    return missing


def build_field_values_single(
    template: Dict[str, Any],
    prompt: str,
    existing_values: Dict[str, Any] = None,
    caption_instruction: str = None,
    field_prompts: Dict[str, str] = None,
) -> tuple[Dict[str, Any], List[str]]:
    """Compatibility helper for the single-poster route.

    Args:
        template: The overlay template dict.
        prompt: The user's natural language prompt.
        existing_values: Field values already known (from prior submissions or session state).
            Any field with a real value here will NOT be sent to the LLM.
        caption_instruction: Optional user-written prompt to override the template's
            caption generation instruction. Used when the user clicks 'Regenerate Caption'.
    """
    from backend.processing.llm import fill_values

    values = split_single(template, prompt)
    if existing_values:
        for k, v in existing_values.items():
            if v is not None and v != "":
                values[k] = v  # replaces sentinel with real value → LLM skips it

    # Build per-field instruction overrides dict
    field_instruction_overrides: Dict[str, str] = {}
    if caption_instruction and "caption" in values:
        field_instruction_overrides["caption"] = f"GENERATE — {caption_instruction}"

    if field_prompts:
        for fid, prompt_text in field_prompts.items():
            if prompt_text and str(prompt_text).strip():
                field_instruction_overrides[fid] = f"GENERATE — {str(prompt_text).strip()}"

    values = fill_values(template, values, prompt=prompt, field_instruction_overrides=field_instruction_overrides)
    missing = has_missing_required(template, values)
    return values, missing