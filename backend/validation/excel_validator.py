import pandas as pd
from fastapi import HTTPException


def validate_excel_file(df: pd.DataFrame) -> None:
    """
    Validates emp_id column existence, no blanks, no duplicates.
    Raises HTTPException with clear message on any failure.
    """
    col_lower = [c.lower().strip() for c in df.columns]

    if "emp_id" not in col_lower:
        raise HTTPException(
            422,
            f"Column 'emp_id' is required but not found. "
            f"Your columns: {list(df.columns)}"
        )

    if len(df) == 0:
        raise HTTPException(422, "File has no data rows.")

    emp_col = next(
        c for c in df.columns if c.lower().strip() == "emp_id"
    )

    blank_rows = df[
        df[emp_col].isna()
        | (df[emp_col].astype(str).str.strip() == "")
    ].index.tolist()
    if blank_rows:
        raise HTTPException(
            422,
            f"Blank emp_id at rows: {[r + 2 for r in blank_rows]} "
            f"(row 1 = header, row 2 = first data row)"
        )

    dupes = (
        df[df[emp_col].duplicated(keep=False)][emp_col]
        .unique()
        .tolist()
    )
    if dupes:
        raise HTTPException(
            422,
            f"Duplicate emp_id values found: {dupes}. "
            f"Every emp_id must be unique."
        )