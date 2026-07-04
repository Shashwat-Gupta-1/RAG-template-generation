from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from processing.rag import search_folder, load_template, load_all_templates_in_folder
from processing.field_split import build_field_values_single
from processing.renderer import render_poster
from config import settings
import os, uuid

router = APIRouter()

@router.post("/generate")
async def generate(
    prompt: str = Form(...),
    template_id: str = Form(None),
    folder: str = Form(None),
    image: UploadFile = File(None)
):
    prompt = prompt.strip()
    if not prompt:
        raise HTTPException(400, "Prompt cannot be empty.")
    prompt = prompt[:settings.max_prompt_length]

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
        if folder and template_id:
            template = load_template(folder, template_id)
            if not template:
                raise HTTPException(404, "Template not found.")
        else:
            matches = search_folder(prompt)

            if not matches:
                return {
                    "status": "no_match",
                    "message": f"No template found for your request.",
                    "trigger_phase2": True
                }

            if (len(matches) > 1 and
                    matches[0]["score"] - matches[1]["score"] < settings.ambiguity_gap):
                return {
                    "status": "ambiguous",
                    "matches": [
                        {
                            "folder": m["folder"],
                            "display_name": m["display_name"],
                            "score": m["score"]
                        }
                        for m in matches
                    ]
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
                            "description": t["description"]
                        }
                        for t in all_templates
                    ]
                }

        overlay_values, null_fields = build_field_values_single(template, prompt)

        if null_fields:
            return {
                "status": "needs_input",
                "missing_fields": null_fields,
                "template_id": template["template_id"],
                "folder": folder
            }

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