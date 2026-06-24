import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "audit.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id          TEXT PRIMARY KEY,
            creator_id  TEXT NOT NULL,
            text        TEXT NOT NULL,
            signal1_score   REAL,
            signal2_score   REAL,
            combined_score  REAL,
            attribution     TEXT,
            label           TEXT,
            status          TEXT DEFAULT 'reviewed',
            appeal_reasoning    TEXT,
            appeal_type         TEXT,
            contact_email       TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Migration: add signal2_score if upgrading from Phase 2 database
    try:
        conn.execute("ALTER TABLE submissions ADD COLUMN signal2_score REAL")
    except Exception:
        pass
    conn.commit()
    conn.close()


def insert_submission(record: dict):
    conn = get_db()
    conn.execute("""
        INSERT INTO submissions
            (id, creator_id, text, signal1_score, signal2_score, combined_score,
             attribution, label, status)
        VALUES
            (:id, :creator_id, :text, :signal1_score, :signal2_score, :combined_score,
             :attribution, :label, :status)
    """, record)
    conn.commit()
    conn.close()


def update_appeal(content_id: str, reasoning: str, appeal_type: str, contact_email: str):
    conn = get_db()
    conn.execute("""
        UPDATE submissions
        SET status = 'under_review',
            appeal_reasoning = ?,
            appeal_type = ?,
            contact_email = ?
        WHERE id = ?
    """, (reasoning, appeal_type, contact_email, content_id))
    conn.commit()
    conn.close()


def fetch_log(limit: int = 50):
    conn = get_db()
    rows = conn.execute("""
        SELECT id, creator_id, signal1_score, signal2_score, combined_score,
               attribution, label, status,
               appeal_reasoning, appeal_type, contact_email, created_at
        FROM submissions
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_submission(content_id: str):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM submissions WHERE id = ?", (content_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None
