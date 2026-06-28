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
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_verified BOOLEAN DEFAULT 0,
            content_type TEXT DEFAULT 'text'
        )
    """)
    try:
        conn.execute("ALTER TABLE submissions ADD COLUMN signal2_score REAL")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE submissions ADD COLUMN signal3_score REAL")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE submissions ADD COLUMN is_verified BOOLEAN DEFAULT 0")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE submissions ADD COLUMN content_type TEXT DEFAULT 'text'")
    except Exception:
        pass
    conn.commit()
    conn.close()


def insert_submission(record: dict):
    conn = get_db()
    conn.execute("""
        INSERT INTO submissions
            (id, creator_id, text, signal1_score, signal2_score, signal3_score,
             combined_score, attribution, label, status, is_verified, content_type)
        VALUES
            (:id, :creator_id, :text, :signal1_score, :signal2_score, :signal3_score,
             :combined_score, :attribution, :label, :status, :is_verified, :content_type)
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


def update_verification(content_id: str):
    conn = get_db()
    conn.execute("""
        UPDATE submissions
        SET is_verified = 1
        WHERE id = ?
    """, (content_id,))
    conn.commit()
    conn.close()


def fetch_log(limit: int = 50):
    conn = get_db()
    rows = conn.execute("""
        SELECT id, creator_id, signal1_score, signal2_score, signal3_score,
               combined_score, attribution, label, status,
               appeal_reasoning, appeal_type, contact_email, created_at,
               is_verified, content_type
        FROM submissions
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_analytics() -> dict:
    conn = get_db()
    row = conn.execute("""
        SELECT
            COUNT(*) AS total,
            AVG(combined_score) AS avg_combined,
            AVG(signal1_score)  AS avg_signal1,
            AVG(signal2_score)  AS avg_signal2,
            AVG(signal3_score)  AS avg_signal3,
            COUNT(CASE WHEN attribution = 'AI-generated'  THEN 1 END) AS ai_count,
            COUNT(CASE WHEN attribution = 'Uncertain'     THEN 1 END) AS uncertain_count,
            COUNT(CASE WHEN attribution = 'Human-written' THEN 1 END) AS human_count,
            COUNT(CASE WHEN status = 'under_review'       THEN 1 END) AS appeal_count
        FROM submissions
    """).fetchone()
    conn.close()

    total = row["total"] or 0
    pct = lambda n: round(n / total * 100, 1) if total else 0.0
    rnd = lambda v: round(v, 4) if v is not None else None

    return {
        "total_submissions": total,
        "average_confidence_score": rnd(row["avg_combined"]),
        "signal_averages": {
            "groq_llm":     rnd(row["avg_signal1"]),
            "stylometrics": rnd(row["avg_signal2"]),
            "punctuation":  rnd(row["avg_signal3"]),
        },
        "label_distribution": {
            "AI-generated":  {"count": row["ai_count"],       "pct": pct(row["ai_count"])},
            "Uncertain":     {"count": row["uncertain_count"], "pct": pct(row["uncertain_count"])},
            "Human-written": {"count": row["human_count"],    "pct": pct(row["human_count"])},
        },
        "appeal_count": row["appeal_count"],
        "appeal_rate_pct": pct(row["appeal_count"]),
    }


def fetch_submission(content_id: str):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM submissions WHERE id = ?", (content_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None
