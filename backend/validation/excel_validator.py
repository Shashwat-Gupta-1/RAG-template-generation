"""
Excel Validator
---------------
Runs BEFORE any processing begins.
Catches every structural and row-level problem upfront.

Design rule: reject the ENTIRE batch if any check fails.
Partial batches create untraceable output files.

Two stages:
  Stage 1 — structural checks (file readable, columns exist)
  Stage 2 — row-level checks (blank/duplicate emp_id)
"""

from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


# emp_id is always required — used for output file naming
ALWAYS_REQUIRED = ["emp_id"]


def read_excel(file_bytes: bytes) -> Tuple[Optional[pd.DataFrame], List[str]]:
    """
    Parse the uploaded Excel file into a DataFrame.
    Returns (dataframe, errors).
    If errors is non-empty, dataframe is None.
    """
    errors: List[str] = []

    # ── Try reading the file ───────────────────────────────────────────────
    try:
        df = pd.read_excel(BytesIO(file_bytes), dtype=str)
    except Exception as exc:
        return None, [
            f"Could not read the file: {exc}. "
            "Accepted formats: .xlsx, .xls"
        ]

    # ── Strip whitespace from column names ────────────────────────────────
    df.columns = [str(c).strip() for c in df.columns]

    # ── Check file has data rows ───────────────────────────────────────────
    if df.empty or len(df) == 0:
        return None, ["The uploaded file has no data rows."]

    # ── Strip whitespace from all cell values ──────────────────────────────
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)

    return df, []


def validate_structure(
    df: pd.DataFrame,
    overlay: Dict[str, Any],
) -> List[str]:
    """
    Stage 1 — Structural checks.

    Checks:
      - emp_id column exists
      - All required overlay fields have matching columns
        (required = llm_can_invent is false AND type is not image)

    Returns list of error strings. Empty = pass.
    """
    errors: List[str] = []
    excel_cols_lower = {c.lower(): c for c in df.columns}

    # ── emp_id must always exist ───────────────────────────────────────────
    for required_col in ALWAYS_REQUIRED:
        if required_col.lower() not in excel_cols_lower:
            errors.append(
                f"Required column '{required_col}' is missing. "
                f"Columns found: {list(df.columns)}"
            )

    # ── Check overlay required fields have matching columns ────────────────
    overlay_layers = overlay.get("overlay_layers") or []
    missing_cols: List[str] = []

    for layer in overlay_layers:
        field_id   = str(layer.get("id", "")).strip()
        field_type = str(layer.get("type", "text")).lower()
        can_invent = bool(layer.get("llm_can_invent", False))

        if not field_id:
            continue
        if field_type == "image":
            continue    # image fields use uploaded photo, not Excel
        if can_invent:
            continue    # LLM will generate these, no Excel column needed

        # This field is required from Excel
        if field_id.lower() not in excel_cols_lower:
            missing_cols.append(field_id)

    if missing_cols:
        errors.append(
            f"These overlay fields have no matching Excel column: {missing_cols}. "
            f"Columns found: {list(df.columns)}"
        )

    return errors


def validate_rows(df: pd.DataFrame) -> List[str]:
    """
    Stage 2 — Row-level checks.

    Checks:
      - No blank emp_id cells
      - No duplicate emp_id values

    Returns list of error strings. Empty = pass.
    """
    errors: List[str] = []

    # Find emp_id column (case-insensitive)
    emp_col = next(
        (col for col in df.columns if col.lower() == "emp_id"),
        None
    )
    if emp_col is None:
        return []   # already caught in validate_structure

    # ── Blank emp_id cells ─────────────────────────────────────────────────
    blank_mask = df[emp_col].isna() | (df[emp_col].astype(str).str.strip() == "")
    blank_rows = df[blank_mask].index.tolist()
    if blank_rows:
        # +2 because Excel rows are 1-indexed and have a header row
        excel_rows = [r + 2 for r in blank_rows]
        errors.append(
            f"Blank emp_id found in Excel rows: {excel_rows}. "
            "Every row must have an emp_id for output file naming."
        )

    # ── Duplicate emp_ids ──────────────────────────────────────────────────
    dupes = df[df[emp_col].duplicated(keep=False)][emp_col].dropna().unique().tolist()
    if dupes:
        errors.append(
            f"Duplicate emp_id values found: {dupes}. "
            "Each emp_id must be unique — duplicates would overwrite output files."
        )

    return errors


def validate_excel(
    file_bytes: bytes,
    overlay: Dict[str, Any],
) -> Tuple[Optional[pd.DataFrame], List[str]]:
    """
    Full validation pipeline.
    Call this from the bulk route.

    Returns (dataframe, errors).
    If errors is non-empty → reject the batch, return errors to user.
    If errors is empty → dataframe is safe to process row by row.

    Example usage in route:
        df, errors = validate_excel(file_bytes, overlay)
        if errors:
            return JSONResponse(status_code=422, content={"errors": errors})
    """
    # Stage 0 — parse file
    df, parse_errors = read_excel(file_bytes)
    if parse_errors:
        return None, parse_errors

    # Stage 1 — structural checks
    struct_errors = validate_structure(df, overlay)
    if struct_errors:
        return None, struct_errors

    # Stage 2 — row-level checks
    row_errors = validate_rows(df)
    if row_errors:
        return None, row_errors

    return df, []


def get_excel_template(overlay: Dict[str, Any]) -> pd.DataFrame:
    """
    Generate a blank Excel template the user can download and fill in.
    Columns = emp_id + all required overlay fields.

    This helps users know exactly what columns to include.
    """
    columns = ["emp_id"]
    overlay_layers = overlay.get("overlay_layers") or []

    for layer in overlay_layers:
        field_id   = str(layer.get("id", "")).strip()
        field_type = str(layer.get("type", "text")).lower()
        if field_id and field_type != "image":
            columns.append(field_id)

    return pd.DataFrame(columns=columns)