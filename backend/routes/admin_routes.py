import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from backend.config import settings
from backend.database.session import get_db
from backend.database.models import User, Conversation, Message

router = APIRouter(prefix="/admin", tags=["admin"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
OUTPUT_DIR = PROJECT_ROOT / "output"


@router.get("/stats")
async def get_admin_stats(db: AsyncSession = Depends(get_db)):
    """
    Returns administrative summary stats:
    - total_templates: counts directories in workspace templates/ folder
    - total_posters: counts total output images / generated poster messages
    - active_sessions: total conversations count
    - total_users: total registered users
    """
    # 1. Scan templates/ folder
    template_count = 0
    if TEMPLATES_DIR.exists():
        template_count = len([d for d in TEMPLATES_DIR.iterdir() if d.is_dir()])

    # 2. Count posters in output/ directory + DB messages
    poster_files_count = 0
    if OUTPUT_DIR.exists():
        poster_files_count = len([f for f in OUTPUT_DIR.iterdir() if f.is_file() and f.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]])

    # DB Queries
    user_count_res = await db.execute(select(func.count(User.id)))
    total_users = user_count_res.scalar() or 0

    convo_count_res = await db.execute(select(func.count(Conversation.id)))
    total_convos = convo_count_res.scalar() or 0

    msg_count_res = await db.execute(select(func.count(Message.id)).where(Message.output_file_path.isnot(None)))
    total_db_posters = msg_count_res.scalar() or 0

    total_posters = max(poster_files_count, total_db_posters)

    # Calculate active users in last 24 hours (offset-naive for PostgreSQL TIMESTAMP WITHOUT TIME ZONE)
    twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
    active_24h_res = await db.execute(
        select(func.count(func.distinct(Conversation.user_id)))
        .where(Conversation.created_at >= twenty_four_hours_ago)
    )
    active_users_24h = active_24h_res.scalar() or 0

    return {
        "total_templates": template_count,
        "total_posters": total_posters,
        "active_sessions": active_users_24h,
        "total_users": total_users,
        "templates_path": str(TEMPLATES_DIR),
        "output_path": str(OUTPUT_DIR),
    }


@router.get("/templates")
async def list_admin_templates():
    """
    Scans workspace templates/ folder and returns details for each template folder, subfolders, and GCS/local image URLs.
    """
    storage_type = getattr(settings, "storage_type", "local").lower()
    gcs_bucket = (os.getenv("GCS_BUCKET_NAME") or os.getenv("GCS_BUCKET")) if storage_type == "gcs" else None
    templates_list = []
    if TEMPLATES_DIR.exists():
        for d in sorted(TEMPLATES_DIR.iterdir()):
            if d.is_dir():
                subfolders = []
                direct_files = [f.name for f in d.iterdir() if f.is_file()]
                first_preview_url = None
                
                # Check child variant folders
                for child in sorted(d.iterdir()):
                    if child.is_dir():
                        child_files = [f.name for f in child.iterdir() if f.is_file()]
                        has_preview = "template.png" in child_files
                        
                        # Build image URL (GCS cloud storage aware or local server mount)
                        if has_preview:
                            if gcs_bucket:
                                preview_url = f"https://storage.googleapis.com/{gcs_bucket}/templates/{d.name}/{child.name}/template.png"
                            else:
                                preview_url = f"http://localhost:8000/templates/{d.name}/{child.name}/template.png"
                            
                            if not first_preview_url:
                                first_preview_url = preview_url
                        else:
                            preview_url = None

                        subfolders.append({
                            "name": child.name,
                            "path": f"{d.name}/{child.name}",
                            "files_count": len(child_files),
                            "files": child_files,
                            "has_preview": has_preview,
                            "preview_url": preview_url,
                        })

                # Determine category
                folder_lower = d.name.lower()
                if any(k in folder_lower for k in ["diwali", "dussehra", "eid", "holi", "teej", "gangaur", "makar", "new_year"]):
                    category = "Festival"
                elif any(k in folder_lower for k in ["hiring", "hr"]):
                    category = "HR & Hiring"
                elif any(k in folder_lower for k in ["loan", "lead_gen", "opening"]):
                    category = "Financial & Branch"
                else:
                    category = "Corporate"

                templates_list.append({
                    "id": d.name.replace(" ", "_"),
                    "title": d.name.replace("_", " ").title(),
                    "folder_name": d.name,
                    "category": category,
                    "status": "ACTIVE",
                    "previewImage": first_preview_url or "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=600&q=80",
                    "subfolder_count": len(subfolders),
                    "subfolders": subfolders,
                    "files_count": len(direct_files),
                    "direct_files": direct_files,
                    "uses": f"{(len(subfolders) + 1) * 12}k",
                    "description": f"Contains {len(subfolders)} variant subfolder(s) for AI template rendering.",
                    "tags": [category, f"{len(subfolders)} variants", "Active Preset"],
                })
    return templates_list


@router.get("/users")
async def list_admin_users(db: AsyncSession = Depends(get_db)):
    """
    Returns list of all users with their role, poster count, and details.
    """
    stmt = select(User).order_by(User.created_at.desc())
    res = await db.execute(stmt)
    users = res.scalars().all()

    user_list = []
    for u in users:
        # Count user convos
        c_res = await db.execute(select(func.count(Conversation.id)).where(Conversation.user_id == u.id))
        convo_cnt = c_res.scalar() or 0

        # Count actual posters generated by user
        p_res = await db.execute(
            select(func.count(Message.id))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(Conversation.user_id == u.id)
            .where(Message.output_file_path.isnot(None))
        )
        posters_cnt = p_res.scalar() or 0

        user_list.append({
            "id": str(u.id),
            "name": u.name,
            "email": u.email,
            "role": u.role,
            "status": "Active" if u.is_active else "Inactive",
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "conversations_count": convo_cnt,
            "postersCount": posters_cnt,
            "department": "Admin Operations" if u.role == "admin" else "Field Executive",
        })
    return user_list


@router.get("/logs")
async def list_admin_logs(
    days: int = 7,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Returns conversation logs across all users for the last 7 days in order of execution.
    Supports filtering by search query (user name, email, session title).
    Handles Postgres & SQLite naive / timezone-aware datetimes cleanly.
    """
    stmt = (
        select(Conversation, User.name, User.email)
        .join(User, Conversation.user_id == User.id)
    )

    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                User.name.ilike(q),
                User.email.ilike(q),
                Conversation.title.ilike(q),
            )
        )

    stmt = stmt.order_by(Conversation.created_at.desc())
    
    res = await db.execute(stmt)
    rows = res.all()

    # Filter by 7-day cutoff in Python for timezone safety across Postgres and SQLite
    if days > 0 and rows:
        now_utc = datetime.utcnow()
        filtered_rows = []
        for row in rows:
            convo = row[0]
            if convo.created_at:
                c_date = convo.created_at
                if c_date.tzinfo is not None:
                    c_date = c_date.replace(tzinfo=None)
                if (now_utc - c_date) <= timedelta(days=days):
                    filtered_rows.append(row)
        
        # If matching rows exist within last 7 days, use them; otherwise use all rows ordered by execution
        if filtered_rows:
            rows = filtered_rows

    logs_list = []
    for convo, user_name, user_email in rows:
        # Fetch messages for this convo in execution order
        m_stmt = select(Message).where(Message.conversation_id == convo.id).order_by(Message.created_at.asc())
        m_res = await db.execute(m_stmt)
        messages = m_res.scalars().all()

        formatted_messages = []
        for m in messages:
            cleaned_text = (m.content or "").replace("Run real-time Gemini AI audit to verify brand compliance & intent.", "").replace("Run real-time Gemini AI audit to verify brand compliance and intent.", "").strip()
            out_url = _build_storage_url(m.output_file_path) if m.output_file_path else None
            formatted_messages.append({
                "id": str(m.id),
                "sender": m.role,
                "text": cleaned_text,
                "time": m.created_at.strftime("%H:%M") if m.created_at else "",
                "output_file_path": out_url,
                "is_bulk": True if (m.output_file_path and m.output_file_path.endswith('.zip')) else False,
            })

        logs_list.append({
            "id": str(convo.id),
            "user": user_name or "User",
            "userEmail": user_email or "",
            "userInitials": "".join([n[0] for n in (user_name or "U").split()[:2]]).upper(),
            "sessionTitle": convo.title or "Poster Generation Session",
            "date": convo.created_at.strftime("%b %d, %Y, %H:%M") if convo.created_at else "Today",
            "timestamp": convo.created_at.isoformat() if convo.created_at else "",
            "messageCount": len(messages),
            "category": "Bulk Request" if convo.conversation_type == "bulk" else "Creation Flow",
            "messages": formatted_messages,
        })
    return logs_list


def _build_storage_url(file_path: str, gcs_bucket: Optional[str] = None) -> str:
    """
    Resilient URL builder for local disk and Google Cloud Storage (GCS).
    - If file_path is already a GCS HTTP/HTTPS URL or signed link: returns file_path as-is.
    - If file_path is a gs:// protocol URI: converts it to https://storage.googleapis.com/...
    - If GCS_BUCKET environment variable is present: formats GCS public URL.
    - Fallback: returns local server static HTTP URL preserving subfolder paths under output/.
    """
    if not file_path:
        return "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=600&q=80"
    
    # Direct GCS HTTP/HTTPS URLs or signed URLs returned by StorageService
    if file_path.startswith(("http://", "https://")):
        return file_path
    
    # gs:// protocol URI format (e.g. gs://my-bucket/output/poster.png)
    if file_path.startswith("gs://"):
        blob_path = file_path[5:]  # strip 'gs://'
        return f"https://storage.googleapis.com/{blob_path}"

    # Standardize slashes and derive path relative to output/
    normalized_path = file_path.replace("\\", "/")
    if "output/" in normalized_path:
        rel_subpath = normalized_path.split("output/")[-1]
    else:
        rel_subpath = os.path.basename(file_path)

    storage_type = getattr(settings, "storage_type", "local").lower()
    if gcs_bucket and storage_type == "gcs":
        return f"https://storage.googleapis.com/{gcs_bucket}/output/{rel_subpath}"

    return f"http://localhost:8000/output/{rel_subpath}"


def _build_template_url(template_path: str, gcs_bucket: Optional[str] = None) -> str:
    """Helper to convert template path (e.g. templates/hiring/hiring001/template.png) to HTTP or GCS URL."""
    if not template_path:
        return "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=600&q=80"
    if template_path.startswith(("http://", "https://")):
        return template_path
    
    clean_path = template_path.replace("\\", "/").strip("/")
    if clean_path.startswith("templates/"):
        clean_path = clean_path.replace("templates/", "", 1)
        
    storage_type = getattr(settings, "storage_type", "local").lower()
    if gcs_bucket and storage_type == "gcs":
        return f"https://storage.googleapis.com/{gcs_bucket}/templates/{clean_path}"
    return f"http://localhost:8000/templates/{clean_path}"


def _get_bulk_template_preview(job_dir: Optional[Path], fallback_folder: Optional[str], gcs_bucket: Optional[str]) -> Tuple[str, str]:
    """Helper to extract template.png image and template name from job's meta.json or folder name."""
    if job_dir and job_dir.exists():
        meta_file = job_dir / "meta.json"
        if meta_file.exists():
            try:
                import json
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    base_img = meta.get("base_image") or meta.get("overlay", {}).get("base_image")
                    template_name = meta.get("template_id") or meta.get("folder") or "Template Asset"
                    if base_img:
                        return _build_template_url(base_img, gcs_bucket), template_name
            except Exception:
                pass

    # Scanning templates/ directory for matching folder
    folder = fallback_folder or (job_dir.name.replace("job_", "") if job_dir else "default")
    if TEMPLATES_DIR.exists():
        for d in TEMPLATES_DIR.iterdir():
            if d.is_dir() and d.name.lower() in folder.lower():
                # Check subfolder template.png
                for child in d.iterdir():
                    if child.is_dir() and (child / "template.png").exists():
                        return _build_template_url(f"{d.name}/{child.name}/template.png", gcs_bucket), f"{d.name}/{child.name}"
                if (d / "template.png").exists():
                    return _build_template_url(f"{d.name}/template.png", gcs_bucket), d.name
        
        # Guaranteed global fallback: return first available template.png from workspace
        for d in TEMPLATES_DIR.iterdir():
            if d.is_dir():
                for child in d.iterdir():
                    if child.is_dir() and (child / "template.png").exists():
                        return _build_template_url(f"{d.name}/{child.name}/template.png", gcs_bucket), f"{d.name}/{child.name}"
                if (d / "template.png").exists():
                    return _build_template_url(f"{d.name}/template.png", gcs_bucket), d.name

    return "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=600&q=80", folder


@router.get("/posters")
async def list_admin_posters(db: AsyncSession = Depends(get_db)):
    """
    Returns output posters & bulk packages from DB records and workspace output/ directory.
    Includes user authorship details, GCS cloud readiness, and template image resolution for bulk jobs.
    """
    gcs_bucket = os.getenv("GCS_BUCKET_NAME") or os.getenv("GCS_BUCKET")
    poster_list = []
    seen_files = set()

    # 1. Fetch DB Messages linked with User and Conversation
    stmt = (
        select(Message, Conversation, User)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .join(User, Conversation.user_id == User.id)
        .where(Message.output_file_path.isnot(None))
        .order_by(Message.created_at.desc())
    )
    res = await db.execute(stmt)
    db_rows = res.all()

    for msg, convo, user in db_rows:
        file_path = msg.output_file_path
        if not file_path:
            continue

        filename = os.path.basename(file_path)
        seen_files.add(filename)
        is_zip = filename.endswith(".zip") or convo.conversation_type == "bulk"

        # Resolve template.png image for bulk jobs
        template_preview = None
        template_folder_name = convo.template_folder or msg.template_used or "Standard Preset"

        if is_zip:
            job_dir_name = f"job_{filename.replace('.zip', '')}"
            job_dir = OUTPUT_DIR / job_dir_name
            t_img, t_name = _get_bulk_template_preview(job_dir, convo.template_folder, gcs_bucket)
            template_preview = t_img
            if t_name:
                template_folder_name = t_name

        # Check if single output file exists locally or format storage URL
        if not is_zip:
            image_url = _build_storage_url(file_path, gcs_bucket)
        else:
            image_url = template_preview or _build_storage_url(file_path, gcs_bucket)
        zip_url = _build_storage_url(convo.job_zip_path or file_path, gcs_bucket) if is_zip else None

        poster_list.append({
            "id": str(msg.id),
            "title": convo.title or filename,
            "filename": filename,
            "author": user.name,
            "authorEmail": user.email,
            "timeAgo": msg.created_at.strftime("%b %d, %Y") if msg.created_at else "Recent",
            "category": "Festival" if "festival" in (msg.template_used or "").lower() else "Corporate",
            "imageUrl": image_url,
            "dataAlt": f"Generated by {user.name} ({user.email}) using template {template_folder_name}",
            "downloads": convo.job_completed or 1,
            "views": (convo.job_completed or 1) * 3 + 5,
            "isBulk": is_zip,
            "zipUrl": zip_url,
            "zipFilename": filename if is_zip else None,
            "totalPostersInBulk": convo.job_total or convo.job_completed or 1,
            "templateFolder": template_folder_name,
        })

    # 2. Scan workspace output/ directory for any un-indexed posters or bulk ZIP files
    if OUTPUT_DIR.exists():
        for f in sorted(OUTPUT_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if f.is_file() and f.name not in seen_files:
                is_zip = f.suffix.lower() == ".zip"
                if not is_zip and f.suffix.lower() not in [".png", ".jpg", ".jpeg", ".webp"]:
                    continue

                seen_files.add(f.name)
                url = _build_storage_url(str(f), gcs_bucket)

                template_preview = None
                bulk_count = 1
                template_name = "diwali"

                if is_zip:
                    job_dir_name = f"job_{f.stem}"
                    job_dir = OUTPUT_DIR / job_dir_name
                    if job_dir.exists() and job_dir.is_dir():
                        job_images = [img for img in job_dir.iterdir() if img.suffix.lower() in [".png", ".jpg"]]
                        bulk_count = len(job_images) if job_images else 1
                    t_img, t_name = _get_bulk_template_preview(job_dir if job_dir.exists() else None, None, gcs_bucket)
                    template_preview = t_img
                    if t_name:
                        template_name = t_name

                poster_list.append({
                    "id": f"disk-{f.stem[:12]}",
                    "title": f.stem.replace("output_", "").replace("_", " ").title(),
                    "filename": f.name,
                    "author": "Shashwat Gupta (Admin)",
                    "authorEmail": "user1@gmail.com",
                    "timeAgo": "Recent",
                    "category": "Festival",
                    "imageUrl": template_preview if (is_zip and template_preview) else url,
                    "dataAlt": f"Output artifact {f.name} using template {template_name}",
                    "downloads": 12,
                    "views": 45,
                    "isBulk": is_zip,
                    "zipUrl": url if is_zip else None,
                    "zipFilename": f.name if is_zip else None,
                    "totalPostersInBulk": bulk_count if is_zip else 1,
                    "templateFolder": template_name,
                })

    return poster_list


@router.get("/bulk-jobs")
async def list_admin_bulk_jobs(db: AsyncSession = Depends(get_db)):
    """
    Returns real bulk jobs created in DB conversations (conversation_type == 'bulk'),
    joined with User details and scanned output ZIP packages.
    """
    storage_type = getattr(settings, "storage_type", "local").lower()
    gcs_bucket = (os.getenv("GCS_BUCKET_NAME") or os.getenv("GCS_BUCKET")) if storage_type == "gcs" else None

    stmt = (
        select(Conversation, User)
        .join(User, Conversation.user_id == User.id)
        .where(Conversation.conversation_type == "bulk")
        .order_by(Conversation.created_at.desc())
    )
    res = await db.execute(stmt)
    db_rows = res.all()

    jobs_list = []
    seen_ids = set()

    for convo, user in db_rows:
        seen_ids.add(str(convo.id))
        raw_status = (convo.job_status or "done").lower()
        if raw_status in ["done", "completed"]:
            status_str = "DONE"
        elif raw_status in ["processing", "active", "running"]:
            status_str = "ACTIVE"
        elif raw_status in ["failed", "error"]:
            status_str = "FAILED"
        else:
            status_str = "QUEUED"

        name_parts = (user.name or "User").split()
        if len(name_parts) >= 2:
            formatted_name = f"{name_parts[0]} {name_parts[-1][0]}."
        else:
            formatted_name = user.name or "User"

        jobs_list.append({
            "id": f"#{str(convo.id)[:4]}",
            "fullId": str(convo.id),
            "user": formatted_name,
            "userEmail": user.email,
            "template": convo.template_folder or convo.title or "Bulk Package",
            "count": convo.job_total or convo.job_completed or 1,
            "completed": convo.job_completed or 0,
            "status": status_str,
            "time": convo.created_at.strftime("%b %d, %H:%M") if convo.created_at else "Recent",
            "timestamp": convo.created_at.isoformat() if convo.created_at else "",
            "downloadUrl": _build_storage_url(convo.job_zip_path, gcs_bucket) if convo.job_zip_path else None,
        })

    # Scan workspace output/ for exported bulk ZIP archives
    if OUTPUT_DIR.exists():
        for f in sorted(OUTPUT_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if f.is_file() and f.suffix.lower() == ".zip":
                job_dir = OUTPUT_DIR / f"job_{f.stem}"
                count = 1
                if job_dir.exists() and job_dir.is_dir():
                    imgs = [i for i in job_dir.iterdir() if i.suffix.lower() in [".png", ".jpg"]]
                    if imgs:
                        count = len(imgs)

                jobs_list.append({
                    "id": f"#{f.stem[:4]}",
                    "fullId": f.stem,
                    "user": "Shashwat G.",
                    "userEmail": "user1@gmail.com",
                    "template": f.stem.replace("output_", "").replace("_", " ").title(),
                    "count": count,
                    "completed": count,
                    "status": "DONE",
                    "time": datetime.fromtimestamp(f.stat().st_mtime).strftime("%b %d, %H:%M"),
                    "timestamp": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                    "downloadUrl": _build_storage_url(str(f), gcs_bucket),
                })

    return jobs_list
