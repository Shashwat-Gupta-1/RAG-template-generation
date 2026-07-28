import uuid
from datetime import datetime, timezone
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.models import Conversation, Message

async def create_conversation(
    db: AsyncSession,
    user_id: uuid.UUID,
    title: str,
    conversation_type: str = "single",
    template_folder: str = None,
    template_id: str = None
) -> Conversation:
    conv = Conversation(
        id=uuid.uuid4(),
        user_id=user_id,
        title=title,
        conversation_type=conversation_type,
        template_folder=template_folder,
        template_id=template_id,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv

async def list_conversations(db: AsyncSession, user_id: uuid.UUID, limit: int = 50):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
    )
    convs = list(result.scalars().all())

    if convs:
        conv_ids = [c.id for c in convs]
        msg_result = await db.execute(
            select(Message.conversation_id)
            .where(
                Message.conversation_id.in_(conv_ids),
                Message.output_file_path.isnot(None),
                Message.output_file_path != ""
            )
        )
        has_msg_image_set = set(msg_result.scalars().all())

        for c in convs:
            c.has_image = bool(
                (c.template_folder and c.template_id) or
                (c.id in has_msg_image_set) or
                (c.job_status == "completed" or (c.job_completed or 0) > 0 or c.job_download_url)
            )
    return convs

async def add_message(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    output_file_path: str = None,
    template_used: str = None
) -> Message:
    # Update Conversation.updated_at
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalars().first()
    if conv:
        conv.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    
    msg = Message(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role=role,
        content=content,
        output_file_path=output_file_path,
        template_used=template_used,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg

async def get_conversation_messages(db: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID) -> dict:
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalars().first()
    if not conv or conv.user_id != user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    result_msgs = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    messages = result_msgs.scalars().all()
    return {
        "conversation": conv,
        "messages": list(messages)
    }

async def delete_conversation(db: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID) -> None:
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalars().first()
    if not conv or conv.user_id != user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Conversation not found")
    await db.delete(conv)
    await db.commit()

async def update_conversation_title(db: AsyncSession, conversation_id: uuid.UUID, new_title: str) -> None:
    conv = await db.get(Conversation, conversation_id)
    if conv:
        conv.title = new_title
        await db.commit()

async def get_message_by_id(db: AsyncSession, message_id: uuid.UUID, user_id: uuid.UUID) -> Message:
    result = await db.execute(select(Message).where(Message.id == message_id))
    msg = result.scalars().first()
    if not msg:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Message not found")
    # Verify the message belongs to a conversation owned by this user
    conv_result = await db.execute(select(Conversation).where(Conversation.id == msg.conversation_id))
    conv = conv_result.scalars().first()
    if not conv or conv.user_id != user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Access denied")
    return msg

async def update_conversation_state(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    assumptions: dict = None,
    generated_prompt: str = None,
    prompt_versions: list = None
):
    res = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = res.scalars().first()
    if conv:
        if assumptions is not None:
            conv.assumptions = assumptions
        if generated_prompt is not None:
            conv.generated_prompt = generated_prompt
        if prompt_versions is not None:
            conv.prompt_versions = prompt_versions
        await db.commit()
        await db.refresh(conv)
    return conv