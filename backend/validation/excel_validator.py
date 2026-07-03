import pandas as pd
from fastapi import HTTPException

def validate_excel_file(df: pd.DataFrame) -> None:
    col_lower = [c.lower() for c in df.columns]

    if "emp_id" not in col_lower:
        raise HTTPException(422,
            f"Column 'emp_id' is required. Found: {list(df.columns)}")

    if len(df) == 0:
        raise HTTPException(422, "The uploaded file has no data rows.")

    emp_col = next(c for c in df.columns if c.lower() == "emp_id")

    blank = df[
        df[emp_col].isna() | (df[emp_col].astype(str).str.strip() == "")
    ].index.tolist()
    if blank:
        raise HTTPException(422,
            f"Blank emp_id at rows: {[r + 2 for r in blank]}")

    dupes = df[df[emp_col].duplicated(keep=False)][emp_col].unique().tolist()
    if dupes:
        raise HTTPException(422,
            f"Duplicate emp_id values: {dupes}")