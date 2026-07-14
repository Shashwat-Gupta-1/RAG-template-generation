from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from processing.renderer import render_poster
from processing.rag import load_template
from config import settings
import os
import uuid
import copy

router = APIRouter()


class StyleOverride(BaseModel):
    field_id: str
    font_family: str | None = None
    font_size: int | None = None
    font_weight: str | None = None
    color: str | None = None
    align: str | None = None


class RerenderRequest(BaseModel):
    folder: str
    template_id: str
    overlay_values: dict
    style_overrides: list[StyleOverride] = []
    uploaded_image_path: str | None = None


@router.post("/rerender")
def rerender(req: RerenderRequest):
    template = load_template(req.folder, req.template_id)
    if not template:
        raise HTTPException(404, "Template not found.")

    modified = copy.deepcopy(template)
    override_map = {o.field_id: o for o in req.style_overrides}

    for layer in modified.get("overlay_layers", []):
        fid = layer.get("id")
        if fid in override_map:
            ov = override_map[fid]
            style = layer.setdefault("style", {})
            if ov.font_family is not None:
                style["font_family"] = ov.font_family
            if ov.font_size is not None:
                style["font_size"] = ov.font_size
            if ov.font_weight is not None:
                style["font_weight"] = ov.font_weight
            if ov.color is not None:
                style["color"] = ov.color
            if ov.align is not None:
                style["align"] = ov.align

    out_path = os.path.join(
        settings.output_dir,
        f"preview_{uuid.uuid4().hex}.png"
    )

    try:
        render_poster(
            modified,
            req.overlay_values,
            out_path,
            req.uploaded_image_path
        )
    except Exception as e:
        raise HTTPException(500, f"Render failed: {e}")

    return FileResponse(
        out_path, media_type="image/png", filename="preview.png"
    )