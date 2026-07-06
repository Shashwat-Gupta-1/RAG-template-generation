"""
Test the bulk Excel flow end to end WITHOUT running FastAPI.
Tests: Excel validation → field split → column mapping → values dict assembly.

Run from project root:
    python test_bulk_flow.py
"""

import json
import pandas as pd
from io import BytesIO
from pathlib import Path

from backend.processing.field_split import (
    build_column_map,
    validate_excel_columns,
    split_row,
    has_missing_required,
)
from backend.validation.excel_validator import validate_excel, get_excel_template


# ── Helpers ────────────────────────────────────────────────────────────────

def load_overlay(template_id: str) -> dict:
    templates_root = Path(__file__).resolve().parent / "templates"
    matches = list(templates_root.rglob(f"{template_id}/overlay.json"))
    if not matches:
        raise FileNotFoundError(f"overlay.json not found for {template_id}")
    with matches[0].open(encoding="utf-8") as f:
        return json.load(f)


def make_excel(data: list) -> bytes:
    """Turn a list of dicts into Excel bytes."""
    df = pd.DataFrame(data)
    buf = BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


def get_emp_id(row, df) -> str:
    """Get emp_id value case-insensitively — handles eMP_id, EMP_ID, emp_id etc."""
    emp_col = next(
        (col for col in df.columns if col.lower() == "emp_id"),
        None
    )
    return row[emp_col] if emp_col else "unknown"


# ── Test 1: Holi poster — only 'name' needed ──────────────────────────────

print("\n=== TEST 1: Holi poster ===")
try:
    overlay = load_overlay("holi001")
    print(f"Overlay loaded: {overlay['template_id']}")
    print(f"Fields: {[l['id'] for l in overlay.get('overlay_layers', [])]}")

    holi_data = [
        {"emp_id": "E001", "name": "Rahul Kumar"},
        {"emp_id": "E002", "name": "Priya Sharma"},
        {"emp_id": "E003", "name": "Amit Singh"},
    ]
    excel_bytes = make_excel(holi_data)
    df, errors = validate_excel(excel_bytes, overlay)

    if errors:
        print(f"VALIDATION ERRORS: {errors}")
    else:
        print(f"Validation passed — {len(df)} rows")
        col_map = build_column_map(overlay, list(df.columns))
        print(f"Column map: {col_map}")
        for _, row in df.iterrows():
            values = split_row(overlay, row.to_dict(), col_map)
            print(f"  emp_id={get_emp_id(row, df)}  values={values}")

except FileNotFoundError as e:
    print(f"SKIP: {e}")


# ── Test 2: Grand opening — uses real overlay fields ───────────────────────

print("\n=== TEST 2: Grand opening poster ===")
try:
    overlay = load_overlay("grand_opening")
    print(f"Overlay loaded: {overlay['template_id']}")

    required_fields = [
        l["id"] for l in overlay.get("overlay_layers", [])
        if l.get("type") != "image" and not l.get("llm_can_invent", False)
    ]
    print(f"Required fields from overlay: {required_fields}")

    row1 = {"emp_id": "B001"}
    row2 = {"emp_id": "B002"}
    for field in required_fields:
        row1[field] = f"Sample {field} for Jaipur"
        row2[field] = f"Sample {field} for Jodhpur"

    opening_data = [row1, row2]
    excel_bytes = make_excel(opening_data)
    df, errors = validate_excel(excel_bytes, overlay)

    if errors:
        print(f"VALIDATION ERRORS: {errors}")
    else:
        print(f"Validation passed — {len(df)} rows")
        col_map = build_column_map(overlay, list(df.columns))
        print(f"Column map: {col_map}")
        for _, row in df.iterrows():
            values = split_row(overlay, row.to_dict(), col_map)
            print(f"  emp_id={get_emp_id(row, df)}  values={values}")

except FileNotFoundError as e:
    print(f"SKIP: {e}")


# ── Test 3: Missing required column (should fail) ─────────────────────────

print("\n=== TEST 3: Missing required column (should fail) ===")
try:
    overlay = load_overlay("holi001")
    bad_data = [{"emp_id": "E001", "wrong_column": "Rahul Kumar"}]
    excel_bytes = make_excel(bad_data)
    df, errors = validate_excel(excel_bytes, overlay)

    if errors:
        print(f"Correctly rejected: {errors}")
    else:
        print("ERROR: Should have been rejected but wasn't")

except FileNotFoundError as e:
    print(f"SKIP: {e}")


# ── Test 4: Duplicate emp_id (should fail) ────────────────────────────────

print("\n=== TEST 4: Duplicate emp_id (should fail) ===")
try:
    overlay = load_overlay("holi001")
    bad_data = [
        {"emp_id": "E001", "name": "Rahul Kumar"},
        {"emp_id": "E001", "name": "Priya Sharma"},
    ]
    excel_bytes = make_excel(bad_data)
    df, errors = validate_excel(excel_bytes, overlay)

    if errors:
        print(f"Correctly rejected: {errors}")
    else:
        print("ERROR: Should have been rejected but wasn't")

except FileNotFoundError as e:
    print(f"SKIP: {e}")


# ── Test 5: Blank Excel template ──────────────────────────────────────────

print("\n=== TEST 5: Blank Excel template for holi001 ===")
try:
    overlay = load_overlay("holi001")
    template_df = get_excel_template(overlay)
    print(f"Blank template columns: {list(template_df.columns)}")
    print("User fills this in and uploads for bulk generation")

except FileNotFoundError as e:
    print(f"SKIP: {e}")


# ── Test 6: Real Excel file from disk ─────────────────────────────────────

print("\n=== TEST 6: Real Excel file ===")
try:
    with open("test_holi.xlsx", "rb") as f:
        file_bytes = f.read()

    overlay = load_overlay("holi001")
    df, errors = validate_excel(file_bytes, overlay)

    if errors:
        print(f"VALIDATION ERRORS: {errors}")
    else:
        print(f"Validation passed — {len(df)} rows")
        col_map = build_column_map(overlay, list(df.columns))
        print(f"Column map: {col_map}")

        for _, row in df.iterrows():
            values = split_row(overlay, row.to_dict(), col_map)
            emp_id_val = get_emp_id(row, df)
            print(f"  emp_id={emp_id_val}  values={values}")

except FileNotFoundError:
    print("SKIP: test_holi.xlsx not found in project root")
    print("Create it by running:")
    print("  python -c \"import pandas as pd; pd.DataFrame([{'emp_id':'E001','name':'Rahul Kumar'},{'emp_id':'E002','name':'Priya Sharma'}]).to_excel('test_holi.xlsx', index=False)\"")


# ── Test 7: emp_id with wrong case (eMP_id) ───────────────────────────────

print("\n=== TEST 7: emp_id column with wrong case (eMP_id) ===")
try:
    overlay = load_overlay("holi001")

    bad_case_data = [
        {"eMP_id": "E001", "name": "Rahul Kumar"},
        {"eMP_id": "E002", "name": "Priya Sharma"},
    ]
    excel_bytes = make_excel(bad_case_data)
    df, errors = validate_excel(excel_bytes, overlay)

    if errors:
        print(f"VALIDATION ERRORS: {errors}")
    else:
        print(f"Validation passed — {len(df)} rows")
        col_map = build_column_map(overlay, list(df.columns))
        for _, row in df.iterrows():
            values = split_row(overlay, row.to_dict(), col_map)
            emp_id_val = get_emp_id(row, df)
            print(f"  emp_id={emp_id_val}  values={values}")

except FileNotFoundError as e:
    print(f"SKIP: {e}")


print("\n=== All tests complete ===")