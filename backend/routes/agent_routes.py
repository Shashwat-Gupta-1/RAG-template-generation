from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import uuid
import os

from backend.database.session import get_db
from backend.database.models import User, Conversation
from backend.auth.dependencies import get_current_user
from backend.services import history_service, agent_service
from backend.phase2.create_agent import _COMPILED_GRAPH

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

class GenerateImageRequest(BaseModel):
    conversation_id: uuid.UUID

async def verify_ownership(db: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Conversation:
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalars().first()
    if not conv or conv.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conv

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

    config = {"configurable": {"thread_id": str(conversation_id)}}
    snapshot = await _COMPILED_GRAPH.aget_state(config)
    values = snapshot.values if snapshot else {}

    return {
        "assumptions": values.get("assumptions", {}),
        "generated_prompt": values.get("generated_prompt", ""),
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
    return res

@router.post("/refine-prompt")
async def refine_prompt(
    body: RefinePromptRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify ownership
    await verify_ownership(db, body.conversation_id, current_user.id)
    
    res = await agent_service.run_agent_refine(str(body.conversation_id), body.refinement_request)
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
    res = await agent_service.run_agent_generate_image(str(body.conversation_id))
    
    # Save assistant message showing the image path
    await history_service.add_message(
        db,
        conversation_id=body.conversation_id,
        role="assistant",
        content=f"Generated template image.",
        output_file_path=res["image_path"]
    )
    
    return res

@router.get("/image")
async def get_agent_image(
    path: str,
    token: str = None,
    db: AsyncSession = Depends(get_db)
):
    if not token:
        raise HTTPException(status_code=401, detail="Missing token query parameter")
    from backend.auth.security import decode_token
    from sqlalchemy.future import select
    from backend.database.models import User
    try:
        payload = decode_token(token)
        email = payload.get("sub")
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Invalid user")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Image not found")
        
    allowed_dirs = ["output", "templates"]
    is_allowed = False
    for allowed in allowed_dirs:
        if allowed in path.replace("\\", "/").split("/"):
            is_allowed = True
            break
            
    if not is_allowed:
        raise HTTPException(status_code=403, detail="Access denied")
        
    return FileResponse(path)
