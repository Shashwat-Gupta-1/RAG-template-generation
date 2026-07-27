import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from backend.database.session import Base

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)  # Thread ID
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    conversation_type = Column(String, default="single", nullable=False)  # "single" | "bulk" | "creation_agent"
    template_folder = Column(String, nullable=True)
    template_id = Column(String, nullable=True)
    
    # Creation Agent columns
    assumptions = Column(JSON, nullable=True)
    generated_prompt = Column(String, nullable=True)

    # Bulk job columns
    job_status = Column(String, nullable=True)  # "processing" | "done" | "failed" | None
    job_total = Column(Integer, nullable=True)
    job_completed = Column(Integer, default=0, nullable=False)
    job_skipped = Column(Integer, default=0, nullable=False)
    job_failed = Column(Integer, default=0, nullable=False)
    job_zip_path = Column(String, nullable=True)
    job_download_url = Column(String, nullable=True)
    job_error = Column(String, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)  # "user" | "assistant"
    content = Column(String, nullable=False)
    output_file_path = Column(String, nullable=True)
    template_used = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
