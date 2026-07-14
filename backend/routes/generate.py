from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from processing.rag import (
    search_folder, load_template, load_all_templates_in_folder
)
from processing.field_split import build_field_values_single
from processing.renderer import render_poster
from config import settings
from logging_config import get_logger
import os
import uuid
import json
import base64

router = APIRouter()
logger = get_logger("ms_fincap.generate")


@router.post("/generate")
async def generate(
    prompt: str = Form(...),
    template_id: str = Form(None),
    folder: str = Form(None),
    extra_fields: str = Form(None),
    image: UploadFile = File(None)
):
    prompt = prompt.strip()
    if not prompt:
        raise HTTPException(400, "Prompt cannot be empty.")
    prompt = prompt[:settings.max_prompt_length]

    logger.info(
        f"/generate: prompt={prompt!r} client_folder={folder!r} "
        f"client_template_id={template_id!r}"
    )

    prefilled_values = {}
    if extra_fields:
        try:
            prefilled_values = json.loads(extra_fields)
        except Exception:
            pass

    uploaded_image_path = None
    if image and image.filename:
        content = await image.read()
        os.makedirs(settings.output_dir, exist_ok=True)
        uploaded_image_path = os.path.join(
            settings.output_dir, f"upload_{uuid.uuid4().hex}"
        )
        with open(uploaded_image_path, "wb") as f:
            f.write(content)

    try:
        if folder and template_id:
            logger.info(
                f"/generate: client explicitly pinned folder={folder!r} "
                f"template_id={template_id!r} — RAG search is being SKIPPED. "
                f"If this doesn't match what the prompt is actually about, "
                f"the frontend is re-sending a stale selection from a "
                f"previous turn."
            )
            template = load_template(folder, template_id)
            if not template:
                logger.warning(
                    f"/generate: pinned folder={folder!r} "
                    f"template_id={template_id!r} not found on disk."
                )
                raise HTTPException(404, "Template not found.")
            resolved_template_id = template_id
        else:
            matches = search_folder(prompt)

            if not matches:
                return {
                    "status": "no_match",
                    "message": "No matching template found.",
                    "trigger_phase2": True
                }

            top = matches[0]
            second_score = matches[1]["score"] if len(matches) > 1 else 0

            if (
                len(matches) > 1
                and top["score"] > 0
                and (top["score"] - second_score) < settings.ambiguity_gap
            ):
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

            folder = top["folder"]

            if len(top["templates"]) == 1:
                resolved_template_id = top["templates"][0]
                logger.info(
                    f"/generate: single-match branch — folder={folder!r} "
                    f"resolved_template_id={resolved_template_id!r} "
                    f"(from top['templates']={top['templates']!r})"
                )
                template = load_template(folder, resolved_template_id)
                if not template:
                    raise HTTPException(
                        500, f"Template file missing for {resolved_template_id}"
                    )
            else:
                all_templates = load_all_templates_in_folder(folder)
                logger.info(
                    f"/generate: gallery — folder={folder!r} "
                    f"template_ids={[t['template_id'] for t in all_templates]!r} "
                    f"(from top['templates']={top['templates']!r})"
                )
                return {
                    "status": "gallery",
                    "folder": folder,
                    "display_name": top["display_name"],
                    "templates": [
                        {
                            "template_id": t["template_id"],
                            "description": t["description"]
                        }
                        for t in all_templates
                    ]
                }

        overlay_values, null_fields = build_field_values_single(
            template, prompt, prefilled_values
        )

        if null_fields:
            logger.info(
                f"/generate: needs_input — folder={folder!r} "
                f"template_id={template['template_id']!r} "
                f"missing_fields={null_fields}"
            )
            return {
                "status": "needs_input",
                "missing_fields": null_fields,
                "template_id": template["template_id"],
                "folder": folder
            }

        if template.get("template_id") != resolved_template_id:
            logger.warning(
                f"overlay.json 'template_id' field "
                f"('{template.get('template_id')}') does not match the "
                f"actual folder name on disk ('{resolved_template_id}') "
                f"under '{folder}/'. This causes /template-info lookups "
                f"to 404. Fix the 'template_id' field inside that "
                f"overlay.json to match its folder name."
            )

        logger.info(
            f"/generate: rendering folder={folder!r} "
            f"template_id={resolved_template_id!r} "
            f"overlay_values={overlay_values}"
        )

        out_path = os.path.join(
            settings.output_dir,
            f"output_{uuid.uuid4().hex}.png"
        )
        render_poster(template, overlay_values, out_path, uploaded_image_path)

        # NOTE: these headers are the fix — the client needs to know which
        # folder/template_id was actually rendered, even when the match was
        # unambiguous and no gallery/ambiguous round-trip happened. Without
        # this, the frontend has no way to call /template-info or /rerender
        # for the live preview / style editor.
        # HTTP headers must be latin-1/ASCII-safe, but overlay_values can
        # contain Hindi/Devanagari text (names, greetings). Base64-encode
        # the JSON so it survives the header transport intact, and give the
        # frontend everything it needs to call /rerender with the *actual*
        # resolved values (including anything the LLM filled in) rather
        # than only the fields the user typed manually into a form.
        overlay_values_b64 = base64.b64encode(
            json.dumps(overlay_values, ensure_ascii=False).encode("utf-8")
        ).decode("ascii")

        return FileResponse(
            out_path,
            media_type="image/png",
            filename="poster.png",
            headers={
                "X-Folder": folder,
                "X-Template-Id": resolved_template_id,
                "X-Overlay-Values-B64": overlay_values_b64,
                "Access-Control-Expose-Headers": (
                    "X-Folder, X-Template-Id, X-Overlay-Values-B64"
                ),
            }
        )

    except ConnectionError as e:
        raise HTTPException(503, f"AI service unavailable: {e}")
    except FileNotFoundError as e:
        raise HTTPException(500, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(500, f"Error: {e}")
    finally:
        if uploaded_image_path and os.path.exists(uploaded_image_path):
            try:
                os.remove(uploaded_image_path)
            except Exception:
                pass


@router.get("/template-info")
def template_info(folder: str, template_id: str):
    template = load_template(folder, template_id)
    if not template:
        raise HTTPException(404, "Template not found")
    return template