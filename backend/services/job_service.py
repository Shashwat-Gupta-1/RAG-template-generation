import uuid
from datetime import datetime, timezone
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.models import Conversation
from backend.services import history_service

async def create_job(
    db: AsyncSession,
    user_id: uuid.UUID,
    total_rows: int,
    template_folder: str = None,
    template_id: str = None,
    title: str = None
) -> Conversation:
    if not title:
        title = f"Bulk: {template_id or 'unknown'} ({total_rows} rows)"
    conv = Conversation(
        id=uuid.uuid4(),
        user_id=user_id,
        title=title,
        conversation_type="bulk",
        template_folder=template_folder,
        template_id=template_id,
        job_status="processing",
        job_total=total_rows,
        job_completed=0,
        job_skipped=0,
        job_failed=0,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv

async def update_progress(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    completed: int,
    skipped: int = 0,
    failed: int = 0
) -> None:
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalars().first()
    if conv:
        conv.job_completed = completed
        conv.job_skipped = skipped
        conv.job_failed = failed
        conv.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()

async def mark_done(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    zip_path: str = "",
    download_url: str = ""
) -> None:
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalars().first()
    if conv:
        conv.job_status = "done"
        conv.job_zip_path = zip_path
        conv.job_download_url = download_url
        conv.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        
        # Add assistant message to messages history
        content = f"Generated {conv.job_completed} posters, {conv.job_skipped} skipped, {conv.job_failed} failed"
        await history_service.add_message(
            db,
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            output_file_path=zip_path
        )
        await db.commit()

async def mark_failed(db: AsyncSession, conversation_id: uuid.UUID, error: str = "") -> None:
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalars().first()
    if conv:
        conv.job_status = "failed"
        conv.job_error = error
        conv.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        
        # Add assistant failure message
        await history_service.add_message(
            db,
            conversation_id=conversation_id,
            role="assistant",
            content=f"Bulk job failed: {error}"
        )
        await db.commit()

async def mark_processing(db: AsyncSession, conversation_id: uuid.UUID) -> None:
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalars().first()
    if conv:
        conv.job_status = "processing"
        conv.job_error = None
        conv.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()


async def get_job(db: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID) -> dict | None:
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalars().first()
    if not conv or conv.user_id != user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Return as dict matching the old SQLite job_tracker output style
    return {
        "job_id": str(conv.id),
        "status": conv.job_status,
        "total": conv.job_total,
        "completed": conv.job_completed,
        "skipped": conv.job_skipped,
        "failed": conv.job_failed,
        "zip_path": conv.job_zip_path,
        "download_url": conv.job_download_url,
        "error": conv.job_error,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None
    }
