from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Depends
import json
import os

from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.database.models import User
from sqlalchemy.ext.asyncio import AsyncSession

from backend.processing.llm import generate_tags_and_description
from backend.phase2.template_saver import save_template_files

router = APIRouter()

@router.get("/templates/categories")
async def get_categories():
    try:
        base_dir = "templates"
        if not os.path.exists(base_dir):
            return {"categories": []}
        
        categories = []
        for d in os.listdir(base_dir):
            if os.path.isdir(os.path.join(base_dir, d)) and d != "__pycache__":
                categories.append(d)
        return {"categories": categories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/templates/add")
async def add_template(
    image: UploadFile = File(...),
    overlay_data: str = Form(...),
    category: str = Form(...),
    base_id: str = Form(...),
    hint: str = Form(""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        overlay = json.loads(overlay_data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in overlay_data")

    if not category or not base_id:
        raise HTTPException(status_code=400, detail="Category and base_id are required")

    category = category.strip().lower()
    base_id = base_id.strip().lower()

    # Extract fields for LLM tag generation
    field_ids = [
        l["id"] for l in overlay.get("overlay_layers", [])
        if l.get("type") == "text"
    ]
    instructions = [
        l.get("instruction", "") for l in overlay.get("overlay_layers", [])
        if l.get("type") == "text"
    ]

    try:
        meta = generate_tags_and_description(
            category, field_ids, instructions, hint.strip()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate tags: {str(e)}")

    full_overlay = {
        "template_id": base_id,
        "description": meta["description"],
        "type": "poster",
        "tags": meta["tags"],
        "base_image": "",
        "canvas": overlay.get("canvas", {"width": 0, "height": 0}),
        "overlay_layers": overlay.get("overlay_layers", [])
    }

    try:
        png_bytes = await image.read()
        folder_path, resolved_id = save_template_files(
            png_bytes,
            full_overlay,
            category,
            base_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save template: {str(e)}")

    return {
        "status": "success",
        "template_id": resolved_id,
        "folder_path": folder_path
    }
