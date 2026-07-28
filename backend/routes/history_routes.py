from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import os
import uuid

from backend.database.session import get_db
from backend.database.models import User
from backend.auth.dependencies import get_current_user
from backend.services import history_service

router = APIRouter(prefix="/history", tags=["history"])


class CreateConversationRequest(BaseModel):
    title: str
    conversation_type: str = "single"  # "single" | "bulk" | "creation_agent"
    template_folder: Optional[str] = None
    template_id: Optional[str] = None


class MessageSchema(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    output_file_path: Optional[str] = None
    template_used: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class ConversationSchema(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    conversation_type: str
    template_folder: Optional[str] = None
    template_id: Optional[str] = None
    job_status: Optional[str] = None
    job_total: Optional[int] = None
    job_completed: int = 0
    job_skipped: int = 0
    job_failed: int = 0
    job_zip_path: Optional[str] = None
    job_download_url: Optional[str] = None
    assumptions: Optional[dict] = None
    generated_prompt: Optional[str] = None
    has_image: bool = False
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ConversationWithMessagesResponse(BaseModel):
    conversation: dict
    messages: list


@router.post("/conversations", response_model=ConversationSchema)
async def create_convo(
    body: CreateConversationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = await history_service.create_conversation(
        db,
        user_id=current_user.id,
        title=body.title,
        conversation_type=body.conversation_type,
        template_folder=body.template_folder,
        template_id=body.template_id
    )
    return _serialize_convo(conv)


@router.get("/conversations", response_model=List[ConversationSchema])
async def list_convos(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    convs = await history_service.list_conversations(db, user_id=current_user.id, limit=limit)
    return [_serialize_convo(c) for c in convs]


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    data = await history_service.get_conversation_messages(db, conversation_id=conversation_id, user_id=current_user.id)
    return {
        "conversation": _serialize_convo(data["conversation"]),
        "messages": [_serialize_msg(m) for m in data["messages"]]
    }


@router.get("/conversations/{conversation_id}/image")
async def get_conversation_image(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
   
    data = await history_service.get_conversation_messages(
        db, conversation_id=conversation_id, user_id=current_user.id
    )
    if not data:
        raise HTTPException(status_code=404, detail="Conversation not found")

    output_file_path = None
    for m in reversed(data["messages"]):
        if m.role == "assistant" and m.output_file_path:
            output_file_path = m.output_file_path
            break

    if not output_file_path:
        raise HTTPException(status_code=404, detail="Image file not found")

    # If output_file_path stored in DB is a Cloud URL (GCS/S3), redirect directly
    if output_file_path.startswith(("http://", "https://")):
        return RedirectResponse(url=output_file_path, status_code=307)

    # Local file path check
    if not os.path.exists(output_file_path):
        raise HTTPException(status_code=404, detail="Image file not found")

    return FileResponse(output_file_path, media_type="image/png")

@router.get("/messages/{message_id}/image")
async def get_message_image(
    message_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msg = await history_service.get_message_by_id(db, message_id=message_id, user_id=current_user.id)
    if not msg.output_file_path:
        raise HTTPException(status_code=404, detail="Message has no image")
        
    output_file_path = msg.output_file_path
    if output_file_path.startswith(("http://", "https://")):
        return RedirectResponse(url=output_file_path, status_code=307)
        
    if not os.path.exists(output_file_path):
        raise HTTPException(status_code=404, detail="Image file not found on disk")
        
    return FileResponse(output_file_path, media_type="image/png")


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_convo(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await history_service.delete_conversation(db, conversation_id=conversation_id, user_id=current_user.id)


class RenameConversationRequest(BaseModel):
    title: str

@router.patch("/conversations/{conversation_id}", response_model=ConversationSchema)
async def rename_convo(
    conversation_id: uuid.UUID,
    body: RenameConversationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await history_service.update_conversation_title(db, conversation_id, body.title)
    
    # Return updated conversation by fetching it
    convs = await history_service.list_conversations(db, user_id=current_user.id, limit=50)
    for c in convs:
        if c.id == conversation_id:
            return _serialize_convo(c)
    raise HTTPException(status_code=404, detail="Conversation not found after rename")


def _serialize_convo(c) -> dict:
    return {
        "id": c.id,
        "user_id": c.user_id,
        "title": c.title,
        "conversation_type": c.conversation_type,
        "template_folder": c.template_folder,
        "template_id": c.template_id,
        "job_status": c.job_status,
        "job_total": c.job_total,
        "job_completed": c.job_completed,
        "job_skipped": c.job_skipped,
        "job_failed": c.job_failed,
        "job_zip_path": c.job_zip_path,
        "job_download_url": c.job_download_url,
        "job_error": c.job_error,
        "assumptions": c.assumptions,
        "generated_prompt": c.generated_prompt,
        "has_image": getattr(c, "has_image", False),
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _serialize_msg(m) -> dict:
    return {
        "id": m.id,
        "conversation_id": m.conversation_id,
        "role": m.role,
        "content": m.content,
        "output_file_path": m.output_file_path,
        "template_used": m.template_used,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }