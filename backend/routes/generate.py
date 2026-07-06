from __future__ import annotations

import copy
import json
import os
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from processing.rag import search_folder, load_template, load_all_templates_in_folder
from processing.field_split import build_field_values_single
from processing.renderer import render_poster
from config import settings

router = APIRouter()


def _apply_style_overrides(template: dict, overrides: dict) -> dict:
    """
    Return a deep-copied template with user style overrides patched into
    every text layer's style block.

    Only non-None override values are applied, so partial overrides work fine.
    Supported keys: font_family, font_size, font_weight, color
    """
    if not overrides:
        return template

    patched = copy.deepcopy(template)
    allowed_keys = {"font_family", "font_size", "font_weight", "color"}

    for layer in patched.get("overlay_layers") or []:
        if str(layer.get("type", "")).lower() != "text":
            continue
        style = layer.setdefault("style", {})
        for key in allowed_keys:
            val = overrides.get(key)
            if val is not None and val != "":
                style[key] = val

    return patched


@router.post("/generate")
async def generate(
    prompt: str = Form(...),
    template_id: str = Form(None),
    folder: str = Form(None),
    image: UploadFile = File(None),
    style_overrides: str = Form(None),   # JSON string: {"font_family":..., "color":..., etc.}
):
    prompt = prompt.strip()
    if not prompt:
        raise HTTPException(400, "Prompt cannot be empty.")
    prompt = prompt[:settings.max_prompt_length]

    # ── Parse style overrides ──────────────────────────────────────────────
    parsed_overrides: dict = {}
    if style_overrides:
        try:
            parsed_overrides = json.loads(style_overrides)
        except (json.JSONDecodeError, TypeError):
            pass  # ignore malformed overrides silently
    print(f"[style_overrides] received={style_overrides!r}  parsed={parsed_overrides}")


    # ── Save uploaded photo ────────────────────────────────────────────────
    uploaded_image_path = None
    if image and image.filename:
        content = await image.read()
        uploaded_image_path = os.path.join(
            settings.output_dir, f"upload_{uuid.uuid4().hex}"
        )
        os.makedirs(settings.output_dir, exist_ok=True)
        with open(uploaded_image_path, "wb") as f:
            f.write(content)

    try:
        # ── Resolve template ───────────────────────────────────────────────
        if folder and template_id:
            template = load_template(folder, template_id)
            if not template:
                raise HTTPException(404, "Template not found.")
        else:
            matches = search_folder(prompt)

            if not matches:
                return {
                    "status": "no_match",
                    "message": "No template found for your request.",
                    "trigger_phase2": True,
                }

            if (len(matches) > 1 and
                    matches[0]["score"] - matches[1]["score"] < settings.ambiguity_gap):
                return {
                    "status": "ambiguous",
                    "matches": [
                        {
                            "folder": m["folder"],
                            "display_name": m["display_name"],
                            "score": m["score"],
                        }
                        for m in matches
                    ],
                }

            best = matches[0]
            folder = best["folder"]

            if len(best["templates"]) == 1:
                template = load_template(folder, best["templates"][0])
            else:
                all_templates = load_all_templates_in_folder(folder)
                return {
                    "status": "gallery",
                    "folder": folder,
                    "display_name": best["display_name"],
                    "templates": [
                        {
                            "template_id": t["template_id"],
                            "description": t["description"],
                        }
                        for t in all_templates
                    ],
                }

        # ── Apply user style overrides ─────────────────────────────────────
        template = _apply_style_overrides(template, parsed_overrides)

        # ── Build field values ─────────────────────────────────────────────
        overlay_values, null_fields = build_field_values_single(template, prompt)

        if null_fields:
            return {
                "status": "needs_input",
                "missing_fields": null_fields,
                "template_id": template["template_id"],
                "folder": folder,
            }

        # ── Render ─────────────────────────────────────────────────────────
        out_path = os.path.join(settings.output_dir, f"output_{uuid.uuid4().hex}.png")
        render_poster(template, overlay_values, out_path, uploaded_image_path)
        return FileResponse(out_path, media_type="image/png", filename="poster.png")

    except ConnectionError as e:
        raise HTTPException(503, f"AI service unavailable: {e}")
    except FileNotFoundError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(500, f"Error: {e}")
    finally:
        if uploaded_image_path and os.path.exists(uploaded_image_path):
            os.remove(uploaded_image_path)