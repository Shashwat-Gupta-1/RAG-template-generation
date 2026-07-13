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
    Case-insensitive exact match.
    Returns { field_id: excel_column_name }

    Example:
        overlay field: "name"
        Excel columns: ["Name", "emp_id", "City"]
        Result: {"name": "Name"}
    """
    column_map: Dict[str, str] = {}
    lower_columns = {col.lower(): col for col in excel_columns}

    for layer in get_overlay_fields(overlay):
        field_id = layer.get("id", "").strip()
        if not field_id or layer.get("type") == "image":
            continue
        # Try exact match (case-insensitive)
        matched_col = lower_columns.get(field_id.lower())
        if matched_col:
            column_map[field_id] = matched_col

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
            values[field_id] = NEEDS_IMAGE
            continue

        # ── Excel has the value ───────────────────────────────────────────
        excel_col = column_map.get(field_id)
        if excel_col and excel_col in excel_row:
            cell_value = excel_row[excel_col]
            if cell_value is not None and str(cell_value).strip() != "":
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

    values = fill_values(template, values, prompt=prompt, field_instruction_overrides=field_instruction_overrides)
    missing = has_missing_required(template, values)
    return values, missing