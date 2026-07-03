RESERVED_FIELDS = {"emp_id"}

def get_editable_text_fields(template: dict) -> list[dict]:
    return [
        f for f in template.get("overlay_layers", [])
        if f.get("editable") and f["type"] == "text"
    ]

def validate_excel_structure(template: dict, excel_headers: list[str]) -> dict | None:
    editable = get_editable_text_fields(template)
    required = {f["id"] for f in editable} | RESERVED_FIELDS
    header_lower = {h.lower(): h for h in excel_headers}
    header_lower_set = set(header_lower.keys())
    required_lower = {r.lower() for r in required}

    missing = [r for r in required if r.lower() not in header_lower_set]
    unrecognized = [header_lower[h] for h in header_lower_set if h not in required_lower]

    if missing or unrecognized:
        return {
            "status": "column_mismatch",
            "missing_required_columns": sorted(missing),
            "unrecognized_columns_in_your_file": unrecognized,
            "all_required_columns": sorted(required)
        }
    return None

def build_field_values_single(template: dict, prompt: str) -> tuple[dict, list[str]]:
    from processing.llm import fill_overlay_fields
    editable = get_editable_text_fields(template)
    fields_for_llm = [
        {"id": f["id"], "instruction": f["instruction"], "llm_can_invent": f["llm_can_invent"]}
        for f in editable
    ]
    llm_result = fill_overlay_fields(prompt, fields_for_llm)
    valid_ids = {f["id"] for f in editable}
    overlay_values = {}
    null_fields = []
    for fid, val in llm_result.items():
        if fid not in valid_ids:
            continue
        if val is None:
            null_fields.append(fid)
        else:
            overlay_values[fid] = str(val)
    return overlay_values, null_fields

def build_field_values_bulk_row(
    template: dict,
    prompt: str,
    row_data: dict
) -> tuple[dict | None, list[dict]]:
    from processing.llm import fill_overlay_fields
    editable = get_editable_text_fields(template)
    row_lower = {k.lower(): k for k in row_data.keys()}
    overlay_values = {}
    skip_reasons = []
    fields_for_llm = []

    for field in editable:
        fid = field["id"]
        actual_col = row_lower.get(fid.lower())
        value = row_data.get(actual_col) if actual_col else None
        is_blank = value is None or str(value).strip() in ("", "nan", "None")

        if not is_blank:
            overlay_values[fid] = str(value).strip()
        elif field.get("llm_can_invent"):
            fields_for_llm.append({
                "id": fid,
                "instruction": field["instruction"],
                "llm_can_invent": True
            })
        else:
            skip_reasons.append({
                "field_id": fid,
                "reason": f"Value is blank and llm_can_invent is false for '{fid}'"
            })

    if skip_reasons:
        return None, skip_reasons

    if fields_for_llm:
        llm_result = fill_overlay_fields(prompt, fields_for_llm)
        valid_ids = {f["id"] for f in editable}
        for field in fields_for_llm:
            fid = field["id"]
            val = llm_result.get(fid)
            if val and fid in valid_ids:
                overlay_values[fid] = str(val)

    return overlay_values, []