from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import uuid

from backend.database.session import get_db
from backend.database.models import User, Conversation
from backend.auth.dependencies import get_current_user
from backend.services import history_service, agent_service
from backend.services.storage_service import storage_service
from backend.phase2.create_agent import _COMPILED_GRAPH, load_brand_theme

router = APIRouter(prefix="/agent", tags=["agent"])

class ChatRequest(BaseModel):
    conversation_id: uuid.UUID
    message: Optional[str] = None

class RebuildPromptRequest(BaseModel):
    conversation_id: uuid.UUID
    assumptions: Dict[str, Any]
    user_edits: Optional[str] = ""

class RefinePromptRequest(BaseModel):
    conversation_id: uuid.UUID
    refinement_request: str
    previous_prompt: Optional[str] = None


class GenerateImageRequest(BaseModel):
    conversation_id: uuid.UUID

async def verify_ownership(db: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID):
    conv_data = await history_service.get_conversation_messages(db, conversation_id=conversation_id, user_id=user_id)
    if not conv_data:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv_data["conversation"]

@router.post("/conversations")
async def create_agent_convo(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = await history_service.create_conversation(
        db,
        user_id=current_user.id,
        title="New Template Creation Agent Session",
        conversation_type="creation_agent"
    )
    return {"conversation_id": str(conv.id)}

@router.get("/conversations/{conversation_id}/state")
async def get_agent_state(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        conv_uuid = uuid.UUID(str(conversation_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="Conversation not found")

    data = await history_service.get_conversation_messages(
        db, conversation_id=conv_uuid, user_id=current_user.id
    )
    if not data:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv = data["conversation"]
    assumptions = conv.assumptions or {}
    generated_prompt = conv.generated_prompt or ""

    # If DB doesn't have assumptions, check in-memory LangGraph checkpointer
    if not any(assumptions.values() if isinstance(assumptions, dict) else []):
        config = {"configurable": {"thread_id": str(conversation_id)}}
        snapshot = await _COMPILED_GRAPH.aget_state(config)
        values = snapshot.values if snapshot else {}
        assumptions = values.get("assumptions") or {}
        generated_prompt = values.get("generated_prompt") or generated_prompt

    # Fallback: if state is still empty, reconstruct from conversation messages & save to DB!
    if not any(assumptions.values() if isinstance(assumptions, dict) else []) and data.get("messages"):
        db_messages = data["messages"]
        # Filter messages to only system/chat relevant content
        history = [
            {"role": m.role, "content": m.content}
            for m in db_messages
            if m.role in ("user", "assistant") and m.content and not m.content.startswith("Generated template image") and not m.content.startswith("Template finalized")
        ]
        if history:
            try:
                config = {"configurable": {"thread_id": str(conversation_id)}}
                res_analyze = await _COMPILED_GRAPH.ainvoke(
                    {
                        "action": "analyze",
                        "brand_theme": load_brand_theme(),
                        "conversation_history": history,
                        "assumptions": {},
                    },
                    config=config,
                )
                assumptions = res_analyze.get("assumptions") or {}

                res_build = await _COMPILED_GRAPH.ainvoke(
                    {
                        "action": "build_prompt",
                        "brand_theme": load_brand_theme(),
                        "conversation_history": history,
                        "assumptions": assumptions,
                        "user_edits": "",
                    },
                    config=config,
                )
                generated_prompt = res_build.get("generated_prompt") or ""

                # Save reconstructed state into DB so we never need to reconstruct again
                await history_service.update_conversation_state(
                    db, conv_uuid, assumptions=assumptions, generated_prompt=generated_prompt
                )
            except Exception as e:
                print(f"[get_agent_state] Reconstruction error: {e}")

    return {
        "assumptions": assumptions,
        "generated_prompt": generated_prompt,
    }

@router.post("/chat")
async def agent_chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify ownership
    conv = await verify_ownership(db, body.conversation_id, current_user.id)
    
    # Save user message if provided
    if body.message:
        await history_service.add_message(
            db,
            conversation_id=body.conversation_id,
            role="user",
            content=body.message
        )
        if conv.title == "New Template Creation Agent Session":
            await history_service.update_conversation_title(
                db, body.conversation_id, body.message[:60]
            )
        
    # Run agent chat
    res = await agent_service.run_agent_chat(str(body.conversation_id), body.message)
    
    # Save assistant message
    await history_service.add_message(
        db,
        conversation_id=body.conversation_id,
        role="assistant",
        content=res["reply"]
    )

    # Persist assumptions and prompt to DB
    if res.get("assumptions") or res.get("generated_prompt"):
        await history_service.update_conversation_state(
            db, body.conversation_id,
            assumptions=res.get("assumptions"),
            generated_prompt=res.get("generated_prompt")
        )
    
    return res

@router.post("/rebuild-prompt")
async def rebuild_prompt(
    body: RebuildPromptRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify ownership
    await verify_ownership(db, body.conversation_id, current_user.id)
    
    res = await agent_service.run_agent_rebuild(str(body.conversation_id), body.assumptions, body.user_edits)
    
    await history_service.update_conversation_state(
        db, body.conversation_id,
        assumptions=body.assumptions,
        generated_prompt=res.get("generated_prompt")
    )
    return res

@router.post("/refine-prompt")
async def refine_prompt(
    body: RefinePromptRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify ownership
    await verify_ownership(db, body.conversation_id, current_user.id)
    
    res = await agent_service.run_agent_refine(str(body.conversation_id), body.refinement_request, body.previous_prompt)

    await history_service.update_conversation_state(
        db, body.conversation_id,
        generated_prompt=res.get("generated_prompt")
    )
    return res


@router.post("/generate-image")
async def generate_image(
    body: GenerateImageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify ownership
    await verify_ownership(db, body.conversation_id, current_user.id)
    
    # Call image generation
    try:
        res = await agent_service.run_agent_generate_image(str(body.conversation_id))
    except Exception as e:
        err_msg = str(e)
        if not err_msg.startswith("API error:"):
            err_msg = f"API error: {err_msg}"
        raise HTTPException(status_code=500, detail=err_msg)
    
    # Save assistant message showing the image path
    local_img_path = res.get("image_path")
    saved_image_url = await storage_service.save_output_image(
        local_file_path=local_img_path,
        subfolder="agent_outputs"
    )

    await history_service.add_message(
        db,
        conversation_id=body.conversation_id,
        role="assistant",
        content=f"Generated template image.",
        output_file_path=saved_image_url
    )
    
    res["image_path"] = saved_image_url
    return res

@router.get("/categories")
async def get_categories():
    import os
    from backend.config import settings
    base_dir = settings.templates_dir
    if not os.path.exists(base_dir):
        return {"categories": []}
    try:
        categories = sorted([
            name for name in os.listdir(base_dir)
            if os.path.isdir(os.path.join(base_dir, name))
        ])
        return {"categories": categories}
    except Exception as e:
        return {"categories": [], "error": str(e)}

class PreviewRenderRequest(BaseModel):
    overlay: Dict[str, Any]
    image_b64: Optional[str] = None
    conversation_id: Optional[str] = None

@router.post("/render-preview")
async def render_sample_preview(
    body: PreviewRenderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    import base64
    import os
    import tempfile
    from backend.processing.renderer import render_poster

    png_bytes = None
    if body.image_b64:
        try:
            raw_b64 = body.image_b64
            if "," in raw_b64:
                raw_b64 = raw_b64.split(",", 1)[1]
            png_bytes = base64.b64decode(raw_b64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image_b64 data: {e}")
    elif body.conversation_id:
        try:
            conv_uuid = uuid.UUID(str(body.conversation_id))
            data = await history_service.get_conversation_messages(
                db, conversation_id=conv_uuid, user_id=current_user.id
            )
            image_msg = next((m for m in reversed(data.get("messages", [])) if m.output_file_path and m.output_file_path.endswith(".png")), None)
            if image_msg and image_msg.output_file_path:
                with open(image_msg.output_file_path, "rb") as f:
                    png_bytes = f.read()
        except Exception as e:
            print(f"[render_preview] error reading conversation image: {e}")

    if not png_bytes:
        raise HTTPException(status_code=400, detail="No base image found for preview render.")

    # Create temporary files for render
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_base:
        tmp_base.write(png_bytes)
        tmp_base_path = tmp_base.name

    tmp_out_path = tmp_base_path.replace(".png", "_out.png")

    try:
        sample_values = {
            layer["id"]: f"[{layer['id']}] font:{layer.get('style', {}).get('font_family', 'Poppins')}"
            if layer.get("type") == "text" else ""
            for layer in body.overlay.get("overlay_layers", [])
            if layer.get("id")
        }

        test_overlay = {
            **body.overlay,
            "template_id": "_preview",
            "base_image": tmp_base_path,
            "description": "preview",
            "tags": [],
            "type": "poster",
        }

        render_poster(test_overlay, sample_values, tmp_out_path, tmp_base_path)

        with open(tmp_out_path, "rb") as f:
            out_b64 = base64.b64encode(f.read()).decode("utf-8")

        return {"status": "success", "image_b64": f"data:image/png;base64,{out_b64}"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Preview render failed: {e}")
    finally:
        if os.path.exists(tmp_base_path):
            os.remove(tmp_base_path)
        if os.path.exists(tmp_out_path):
            os.remove(tmp_out_path)

class SaveTemplateRequest(BaseModel):
    category: str
    template_base_id: str
    user_hint: Optional[str] = ""
    overlay: Dict[str, Any]
    image_b64: Optional[str] = None
    conversation_id: Optional[str] = None

def _validate_subfolder_name(subfolder_name: str, category_name: str) -> Optional[str]:
    import os
    from backend.config import settings

    name = subfolder_name.strip().lower()
    cat = category_name.strip().lower()

    if not name:
        return "Subfolder/Template ID cannot be empty."

    if name == cat:
        return f"Subfolder/Template ID '{subfolder_name}' cannot be the same as the category folder name '{category_name}'."

    base_dir = settings.templates_dir
    if os.path.exists(base_dir):
        try:
            existing_folders = [
                f.lower() for f in os.listdir(base_dir)
                if os.path.isdir(os.path.join(base_dir, f))
            ]
            if name in existing_folders:
                return f"Subfolder name '{subfolder_name}' conflicts with an existing templates category folder name '{name}'."
        except Exception:
            pass
    return None

@router.post("/save-template")
async def save_template(
    body: SaveTemplateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    import base64
    from backend.phase2.template_saver import save_template_files
    from backend.processing.llm import generate_tags_and_description

    cat_name = body.category.strip().lower()
    base_id = body.template_base_id.strip()

    val_err = _validate_subfolder_name(base_id, cat_name)
    if val_err:
        raise HTTPException(status_code=400, detail=val_err)

    png_bytes = None
    if body.image_b64:
        try:
            raw_b64 = body.image_b64
            if "," in raw_b64:
                raw_b64 = raw_b64.split(",", 1)[1]
            png_bytes = base64.b64decode(raw_b64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image_b64 data: {e}")
    elif body.conversation_id:
        try:
            conv_uuid = uuid.UUID(str(body.conversation_id))
            data = await history_service.get_conversation_messages(
                db, conversation_id=conv_uuid, user_id=current_user.id
            )
            image_msg = next((m for m in reversed(data.get("messages", [])) if m.output_file_path and m.output_file_path.endswith(".png")), None)
            if image_msg and image_msg.output_file_path:
                with open(image_msg.output_file_path, "rb") as f:
                    png_bytes = f.read()
        except Exception as e:
            print(f"[save_template] error reading conversation image: {e}")

    if not png_bytes:
        raise HTTPException(status_code=400, detail="No PNG image provided for template base.")

    # Gather field IDs and instructions for LLM tag generation
    overlay_layers = body.overlay.get("overlay_layers", [])
    field_ids = [l["id"] for l in overlay_layers if l.get("type") == "text" and l.get("id")]
    instructions = [l.get("instruction", "") for l in overlay_layers if l.get("type") == "text" and l.get("id")]

    # Generate LLM tags & rich description
    try:
        meta = generate_tags_and_description(cat_name, field_ids, instructions, body.user_hint or "")
    except Exception as e:
        fallback_desc = body.user_hint if (body.user_hint and len(body.user_hint.split()) >= 10) else f"Custom promotional {cat_name} visual poster template designed for social media greetings, announcements, and marketing graphics."
        meta = {
            "description": fallback_desc,
            "tags": [cat_name, "poster", "greeting"]
        }

    full_overlay = {
        "template_id": base_id,
        "description": meta.get("description", body.user_hint or ""),
        "type": "poster",
        "tags": meta.get("tags", [cat_name]),
        "base_image": "",
        "canvas": body.overlay.get("canvas", {"width": 1024, "height": 1536}),
        "overlay_layers": overlay_layers
    }

    try:
        folder_path, resolved_id = save_template_files(
            png_bytes=png_bytes,
            overlay=full_overlay,
            category=cat_name,
            template_base_id=base_id
        )

        if body.conversation_id:
            try:
                conv_uuid = uuid.UUID(str(body.conversation_id))
                # Update conversation to set template_id and job_status so it's no longer a draft
                res = await db.execute(select(history_service.Conversation).where(history_service.Conversation.id == conv_uuid))
                conv = res.scalars().first()
                if conv:
                    conv.template_id = resolved_id
                    conv.template_folder = cat_name
                    conv.job_status = "completed"
                    await db.commit()
                
                # Add message with output_file_path so it shows in the versions modal
                import os
                await history_service.add_message(
                    db,
                    conversation_id=conv_uuid,
                    role="assistant",
                    content=f"Template finalized and saved as {resolved_id}.",
                    output_file_path=os.path.join(folder_path, "template.png").replace("\\", "/")
                )
            except Exception as hist_err:
                print(f"[save_template] error updating history: {hist_err}")

        return {
            "status": "success",
            "message": f"Saved as `{resolved_id}` in `{cat_name}/` — searchable immediately!",
            "folder": cat_name,
            "template_id": resolved_id,
            "folder_path": folder_path
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to save template: {e}")

