from __future__ import annotations

import copy
import json
import os
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Request, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.database.models import User
from backend.services import history_service
from backend.services.storage_service import storage_service

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

    # Check if this is per-layer override (at least one value is a dict)
    is_per_layer = any(isinstance(v, dict) for v in overrides.values())

    for layer in patched.get("overlay_layers") or []:
        if str(layer.get("type", "")).lower() != "text":
            continue
        
        lid = layer.get("id")
        style = layer.setdefault("style", {})

        if is_per_layer:
            if lid and lid in overrides:
                layer_overrides = overrides[lid]
                for key in allowed_keys:
                    val = layer_overrides.get(key)
                    if val is not None and val != "":
                        style[key] = val
        else:
            for key in allowed_keys:
                val = overrides.get(key)
                if val is not None and val != "":
                    style[key] = val

    return patched


def _apply_layout_overrides(template: dict, overrides: dict) -> dict:
    """
    Return a deep-copied template with customized layer coordinates.
    """
    if not overrides:
        return template

    patched = copy.deepcopy(template)

    for layer in patched.get("overlay_layers") or []:
        layer_id = layer.get("id")
        if layer_id in overrides:
            layer_override = overrides[layer_id]
            box = layer.setdefault("box", {})
            for key in ("x", "y", "width", "height"):
                if key in layer_override:
                    try:
                        box[key] = int(layer_override[key])
                    except (ValueError, TypeError):
                        pass

    return patched


@router.post("/generate")
async def generate(
    request: Request,
    prompt: str = Form(...),
    template_id: str = Form(None),
    folder: str = Form(None),
    image: UploadFile = File(None),
    style_overrides: str = Form(None),   # JSON string: {"font_family":..., "color":..., etc.}
    layout_overrides: str = Form(None),  # JSON string: {"layer_id": {"x":..., "y":...}}
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prompt = prompt.strip()
    if not prompt:
        raise HTTPException(400, "Prompt cannot be empty.")
    prompt = prompt[:settings.max_prompt_length]

    # ── Parse extra dynamic inputs from form data ──────────────────────────
    form_data = await request.form()
    extra_inputs = {}
    for key, value in form_data.items():
        if key not in {"prompt", "template_id", "folder", "image", "style_overrides", "layout_overrides", "caption_prompt"}:
            if isinstance(value, str):
                extra_inputs[key] = value.strip()

    # ── Parse style overrides ──────────────────────────────────────────────
    parsed_overrides: dict = {}
    if style_overrides:
        try:
            parsed_overrides = json.loads(style_overrides)
        except (json.JSONDecodeError, TypeError):
            pass  # ignore malformed overrides silently
    print(f"[style_overrides] received={style_overrides!r}  parsed={parsed_overrides}")
    print(f"[extra_inputs] received={extra_inputs}")

    # ── Parse layout overrides ─────────────────────────────────────────────
    parsed_layout_overrides: dict = {}
    if layout_overrides:
        try:
            parsed_layout_overrides = json.loads(layout_overrides)
        except (json.JSONDecodeError, TypeError):
            pass
    print(f"[layout_overrides] received={layout_overrides!r}  parsed={parsed_layout_overrides}")


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
        if folder:
            if template_id:
                template = load_template(folder, template_id)
                if not template:
                    raise HTTPException(404, "Template not found.")
            else:
                # User selected a folder from ambiguity choice but hasn't picked a template yet
                all_templates = load_all_templates_in_folder(folder)
                if not all_templates:
                    raise HTTPException(404, "Folder not found or empty.")
                if len(all_templates) == 1:
                    template = all_templates[0]
                    template_id = template["template_id"]
                else:
                    main_path = os.path.join(settings.templates_dir, folder, "main.json")
                    display_name = folder.replace("_", " ").title()
                    if os.path.exists(main_path):
                        try:
                            with open(main_path, encoding="utf-8") as f:
                                main_data = json.load(f)
                                display_name = main_data.get("display_name", display_name)
                        except Exception:
                            pass
                    return {
                        "status": "gallery",
                        "folder": folder,
                        "display_name": display_name,
                        "templates": [
                            {
                                "template_id": t["template_id"],
                                "description": t["description"],
                                "base_image": t.get("base_image"),
                            }
                            for t in all_templates
                        ],
                    }
        else:
            matches = search_folder(prompt)

            if not matches:
                return {
                    "status": "no_match",
                    "message": "No template found for your request.",
                    "trigger_phase2": True,
                }

            # Score ALL candidate matches by token/keyword overlap with prompt + vector score
            def _score_folder_match(m: dict) -> float:
                fname = m["folder"].lower()
                fname_space = fname.replace("_", " ")
                p_lower = prompt.lower()

                import re
                p_words = set(re.findall(r"\w+", p_lower))
                f_words = set(re.findall(r"\w+", fname.replace("_", " ")))
                tags = m.get("tags") or []
                if isinstance(tags, list):
                    for t in tags:
                        if isinstance(t, str):
                            f_words.update(re.findall(r"\w+", t.lower()))

                matching = p_words.intersection(f_words)
                stop = {"a", "an", "the", "for", "of", "in", "on", "at", "to", "is", "with", "and", "or", "me", "my", "poster", "posters", "generate", "create"}
                meaningful = matching - stop

                # Exact folder name or space-separated folder match gets huge boost
                if fname in p_lower or fname_space in p_lower:
                    return 200.0 + len(fname) + len(meaningful) * 10.0

                if meaningful:
                    return float(len(meaningful)) * 20.0 + (m.get("score", 0) * 10.0) + len(fname)
                return m.get("score", 0) * 10.0

            matches.sort(key=lambda m: _score_folder_match(m), reverse=True)
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
                            "base_image": t.get("base_image"),
                        }
                        for t in all_templates
                    ],
                }

        # ── Apply user style overrides ─────────────────────────────────────
        template = _apply_style_overrides(template, parsed_overrides)

        # ── Apply user layout overrides ────────────────────────────────────
        template = _apply_layout_overrides(template, parsed_layout_overrides)

        # Extract caption_prompt override and field_prompts/field_values
        caption_prompt_override = form_data.get("caption_prompt")
        if caption_prompt_override:
            caption_prompt_override = str(caption_prompt_override).strip()

        field_values_override = form_data.get("field_values")
        parsed_field_values = {}
        if field_values_override:
            try:
                parsed_field_values = json.loads(field_values_override)
            except Exception:
                pass

        field_prompts_override = form_data.get("field_prompts")
        parsed_field_prompts = {}
        if field_prompts_override:
            try:
                parsed_field_prompts = json.loads(field_prompts_override)
            except Exception:
                pass

        # Merge parsed_field_values into extra_inputs
        for k, v in parsed_field_values.items():
            if v is not None and str(v).strip() != "":
                extra_inputs[k] = str(v).strip()

        overlay_values, null_fields = build_field_values_single(
            template, prompt,
            existing_values=extra_inputs,
            caption_instruction=caption_prompt_override,
            field_prompts=parsed_field_prompts,
        )


        # Merge user inputs from request form parameters
        for key, val in extra_inputs.items():
            if val is not None and val != "":
                overlay_values[key] = val

        # Recalculate missing required fields
        from processing.field_split import has_missing_required
        null_fields = has_missing_required(template, overlay_values)

        if null_fields:
            return {
                "status": "needs_input",
                "missing_fields": null_fields,
                "template_id": template["template_id"],
                "folder": folder,
                "overlay_values": overlay_values,
            }

        # ── Render ──────────────────────────────────────────────────
        out_path = os.path.join(settings.output_dir, f"output_{uuid.uuid4().hex}.png")
        render_poster(template, overlay_values, out_path, uploaded_image_path)

        # Create conversation and add messages history
        conv = await history_service.create_conversation(
            db,
            user_id=current_user.id,
            title=prompt[:60] if prompt else f"Single: {template.get('template_id') or 'poster'}",
            conversation_type="single",
            template_folder=folder,
            template_id=template.get("template_id")
        )
        await history_service.add_message(
            db,
            conversation_id=conv.id,
            role="user",
            content=prompt
        )
        saved_output_url = await storage_service.save_output_image(out_path, subfolder="outputs")

        await history_service.add_message(
            db,
            conversation_id=conv.id,
            role="assistant",
            content="Generated poster successfully.",
            output_file_path=saved_output_url,
            template_used=template.get("template_id")
        )

        # Check if client prefers JSON response (for drag and drop editor metadata)
        accept_header = request.headers.get("accept", "")
        if "application/json" in accept_header or request.query_params.get("json") == "true":
            import base64
            with open(out_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")
            return {
                "status": "success",
                "image": img_b64,
                "canvas": template.get("canvas"),
                "overlay_layers": template.get("overlay_layers"),
                "template_id": template.get("template_id"),
                "folder": folder,
                "overlay_values": overlay_values,
            }

        return FileResponse(out_path, media_type="image/png", filename="poster.png")

    except ConnectionError as e:
        raise HTTPException(503, f"AI service unavailable: {e}")
    except FileNotFoundError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Error: {e}")
    finally:
        if uploaded_image_path and os.path.exists(uploaded_image_path):
            os.remove(uploaded_image_path)