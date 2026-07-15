import sqlite3
import uuid

from backend.config import settings

DB_PATH = "jobs.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id      TEXT PRIMARY KEY,
            status      TEXT NOT NULL,
            total       INTEGER NOT NULL,
            completed   INTEGER DEFAULT 0,
            skipped     INTEGER DEFAULT 0,
            failed      INTEGER DEFAULT 0,
            zip_path    TEXT DEFAULT '',
            download_url TEXT DEFAULT '',
            error       TEXT DEFAULT '',
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def create_job(total_rows: int) -> str:
    job_id = uuid.uuid4().hex
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO jobs (job_id, status, total) VALUES (?, ?, ?)",
        (job_id, "processing", total_rows)
    )
    conn.commit()
    conn.close()
    return job_id

def update_job(job_id: str, completed: int, skipped: int,
               failed: int, done: bool = False, zip_path: str = ""):
    status = "done" if done else "processing"
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        UPDATE jobs SET status=?, completed=?, skipped=?, failed=?,
        zip_path=?, updated_at=CURRENT_TIMESTAMP WHERE job_id=?
    """, (status, completed, skipped, failed, zip_path, job_id))
    conn.commit()
    conn.close()

def update_progress(job_id: str, completed: int, skipped: int = 0, failed: int = 0) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        UPDATE jobs
        SET completed=?, skipped=?, failed=?, updated_at=CURRENT_TIMESTAMP
        WHERE job_id=?
    """, (completed, skipped, failed, job_id))
    conn.commit()
    conn.close()

def mark_done(job_id: str, download_url: str = "") -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        UPDATE jobs
        SET status='done', download_url=?, updated_at=CURRENT_TIMESTAMP
        WHERE job_id=?
    """, (download_url, job_id))
    conn.commit()
    conn.close()

def mark_failed(job_id: str, error: str = "") -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        UPDATE jobs
        SET status='failed', error=?, updated_at=CURRENT_TIMESTAMP
        WHERE job_id=?
    """, (error, job_id))
    conn.commit()
    conn.close()

def get_job(job_id: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM jobs WHERE job_id=?", (job_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


init_db()