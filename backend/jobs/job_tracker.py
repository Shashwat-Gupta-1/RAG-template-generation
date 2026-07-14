import sqlite3
import os

DB_PATH = "jobs.db"


def init_db() -> None:
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
            folder      TEXT DEFAULT '',
            template_id TEXT DEFAULT '',
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Migrate older DBs created before folder/template_id existed.
    existing_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()
    }
    if "folder" not in existing_cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN folder TEXT DEFAULT ''")
    if "template_id" not in existing_cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN template_id TEXT DEFAULT ''")
    conn.commit()
    conn.close()


def create_job(
    job_id: str,
    total: int,
    folder: str = "",
    template_id: str = ""
) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO jobs "
        "(job_id, status, total, completed, skipped, failed, folder, template_id) "
        "VALUES (?, 'processing', ?, 0, 0, 0, ?, ?)",
        (job_id, total, folder, template_id)
    )
    conn.commit()
    conn.close()


def update_job(
    job_id: str,
    completed: int,
    skipped: int,
    failed: int,
    done: bool = False,
    zip_path: str = ""
) -> None:
    status = "done" if done else "processing"
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """UPDATE jobs SET
            status=?, completed=?, skipped=?, failed=?,
            zip_path=?, updated_at=CURRENT_TIMESTAMP
           WHERE job_id=?""",
        (status, completed, skipped, failed, zip_path, job_id)
    )
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