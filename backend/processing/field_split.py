RESERVED_FIELDS = {"emp_id"}


def get_editable_text_fields(template: dict) -> list[dict]:
    return [
        f for f in template.get("overlay_layers", [])
        if f.get("editable") and f["type"] == "text"
    ]


def validate_excel_structure(
    template: dict,
    excel_headers: list[str]
) -> dict | None:
    """
    Hard validation — no fuzzy matching, no LLM rescue for mismatches.
    Returns error dict if any required column is missing or misnamed.
    Returns None if all good.
    """
    editable = get_editable_text_fields(template)
    required_ids = {f["id"] for f in editable if not f.get("llm_can_invent")}
    required_ids.add("emp_id")

    header_set = {h.lower().strip() for h in excel_headers}
    required_lower = {r.lower() for r in required_ids}

    missing = [
        r for r in required_ids
        if r.lower() not in header_set
    ]

    if not missing:
        return None

    return {
        "status": "column_mismatch",
        "missing_required_columns": sorted(missing),
        "required_columns": sorted(required_ids),
        "your_columns": sorted(excel_headers),
        "message": (
            f"Your Excel is missing these required columns: "
            f"{', '.join(sorted(missing))}. "
            f"Rename your columns to match exactly."
        )
    }


def build_field_values_single(
    template: dict,
    prompt: str,
    prefilled_values: dict = None
) -> tuple[dict, list[str]]:
    """
    For single poster generation — LLM fills everything from prompt.
    prefilled_values: from fallback form — used directly, skip LLM for these.
    Returns (overlay_values, null_fields).
    null_fields: field IDs where LLM returned null (llm_can_invent=False + no value in prompt).
    """
    from processing.llm import fill_overlay_fields
    prefilled_values = prefilled_values or {}
    editable = get_editable_text_fields(template)

    fields_for_llm = [
        {
            "id": f["id"],
            "instruction": f["instruction"],
            "llm_can_invent": f["llm_can_invent"]
        }
        for f in editable
        if f["id"] not in prefilled_values
    ]

    llm_result = fill_overlay_fields(
        prompt, fields_for_llm, prefilled_values
    )

    valid_ids = {f["id"] for f in editable}
    overlay_values = dict(prefilled_values)
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
    """
    For bulk generation — strict Excel-based filling.
    Identity fields (llm_can_invent=False): must come from Excel — error if blank.
    Creative fields (llm_can_invent=True): generate with LLM if Excel column absent.
    Returns (overlay_values, skip_reasons).
    If skip_reasons is non-empty, overlay_values is None — this row is skipped.
    """
    from processing.llm import fill_overlay_fields
    editable = get_editable_text_fields(template)
    row_lower = {k.lower().strip(): v for k, v in row_data.items()}

    overlay_values = {}
    skip_reasons = []
    fields_for_llm = []

    for field in editable:
        fid = field["id"]
        value = row_lower.get(fid.lower())
        is_blank = (
            value is None
            or str(value).strip() in ("", "nan", "None", "NaN")
        )

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
                "reason": (
                    f"Column '{fid}' is blank for this row. "
                    f"llm_can_invent is false — cannot auto-fill."
                )
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