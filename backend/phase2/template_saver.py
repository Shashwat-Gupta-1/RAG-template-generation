import os
import json
import re
from config import settings


def resolve_save_path(
    category: str,
    template_base_id: str
) -> tuple[str, str]:
    """
    Returns (folder_path, resolved_template_id).
    If templates/{category}/{template_base_id}/ exists,
    finds next available sequence number.
    """
    base_dir = settings.templates_dir
    category_path = os.path.join(base_dir, category)
    os.makedirs(category_path, exist_ok=True)

    target_path = os.path.join(category_path, template_base_id)
    # If the user passed the exact same name for category and base_id, 
    # we force auto-numbering (e.g. diwali -> diwali01, diwali02)
    if template_base_id != category and not os.path.exists(target_path):
        return target_path, template_base_id

    base_name = re.sub(r"\d+$", "", template_base_id)

    existing_nums = []
    for name in os.listdir(category_path):
        full = os.path.join(category_path, name)
        if not os.path.isdir(full):
            continue
        stripped = re.sub(r"^" + re.escape(base_name), "", name)
        if stripped.isdigit():
            existing_nums.append(int(stripped))

    next_num = max(existing_nums, default=0) + 1
    new_id = f"{base_name}{next_num:02d}"
    new_path = os.path.join(category_path, new_id)
    return new_path, new_id


def save_template_files(
    png_bytes: bytes,
    overlay: dict,
    category: str,
    template_base_id: str
) -> tuple[str, str]:
    """
    Saves template.png and overlay.json to disk.
    Auto-runs indexer so template is immediately searchable.
    Returns (resolved_folder_path, resolved_template_id).
    """
    folder_path, resolved_id = resolve_save_path(
        category, template_base_id
    )
    os.makedirs(folder_path, exist_ok=True)

    overlay["template_id"] = resolved_id
    overlay["base_image"] = (
        f"{settings.templates_dir}/{category}/{resolved_id}/template.png"
    )

    png_path = os.path.join(folder_path, "template.png")
    with open(png_path, "wb") as f:
        f.write(png_bytes)

    json_path = os.path.join(folder_path, "overlay.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(overlay, f, indent=2, ensure_ascii=False)

    # Auto-run indexer
    import sys
    sys.path.insert(0, os.path.join(
        os.path.dirname(__file__), "..", ".."
    ))
    from backend.indexer.indexer_templates import build_main_json, index_folder
    category_path = os.path.join(settings.templates_dir, category)
    main = build_main_json(category_path, category)
    if main:
        index_folder(category, main)

    return folder_path, resolved_id