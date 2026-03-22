"""
database.py — SQLite-backed persistent reminder storage with multi-user support.
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent
DB_PATH = _PROJECT_ROOT / "data" / "reminders.db"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    conn = _conn()
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS reminders (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            message TEXT NOT NULL,
            trigger_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            fired_at TEXT,
            cancelled_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_user ON reminders(user_id);
        CREATE INDEX IF NOT EXISTS idx_status ON reminders(status);
        CREATE INDEX IF NOT EXISTS idx_trigger_at ON reminders(trigger_at);

        CREATE TABLE IF NOT EXISTS notification_prefs (
            user_id    TEXT PRIMARY KEY,
            whatsapp   TEXT,
            email      TEXT,
            channels   TEXT DEFAULT 'sse',
            updated_at TEXT NOT NULL
        );
        """)
        conn.commit()
        logger.info("SQLite DB ready at %s", DB_PATH)
    finally:
        conn.close()


# ── NOTIFICATION PREFS ──────────────────────────────────────────

def upsert_notification_prefs(
    user_id: str,
    whatsapp: Optional[str] = None,
    email: Optional[str] = None,
    channels: Optional[list] = None,
) -> None:
    existing = get_notification_prefs(user_id)
    wa = whatsapp if whatsapp is not None else (existing.get("whatsapp") if existing else None)
    em = email if email is not None else (existing.get("email") if existing else None)
    ch = ",".join(channels) if channels is not None else (existing.get("channels", "sse") if existing else "sse")
    conn = _conn()
    try:
        conn.execute(
            """INSERT INTO notification_prefs (user_id, whatsapp, email, channels, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   whatsapp   = excluded.whatsapp,
                   email      = excluded.email,
                   channels   = excluded.channels,
                   updated_at = excluded.updated_at""",
            (user_id, wa, em, ch, datetime.utcnow().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def get_notification_prefs(user_id: str) -> dict:
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT * FROM notification_prefs WHERE user_id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


# ── CREATE ─────────────────────────────────────

def save_reminder(reminder_id: str, user_id: str, message: str, trigger_at: datetime):
    conn = _conn()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO reminders
            (id, user_id, message, trigger_at, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?)""",
            (
                reminder_id,
                user_id,
                message,
                trigger_at.isoformat(),
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


# ── UPDATE ─────────────────────────────────────

def mark_fired(reminder_id: str):
    conn = _conn()
    try:
        conn.execute(
            "UPDATE reminders SET status='fired', fired_at=? WHERE id=?",
            (datetime.utcnow().isoformat(), reminder_id),
        )
        conn.commit()
    finally:
        conn.close()


def mark_cancelled(reminder_id: str) -> bool:
    conn = _conn()
    try:
        cur = conn.execute(
            "UPDATE reminders SET status='cancelled', cancelled_at=? WHERE id=?",
            (datetime.utcnow().isoformat(), reminder_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ── READ ─────────────────────────────────────

def get_reminder_by_id(reminder_id: str):
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM reminders WHERE id=?", (reminder_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_all_reminders_db(user_id: Optional[str] = None, status: Optional[str] = None):
    conn = _conn()
    try:
        query = "SELECT * FROM reminders"
        params = []
        conditions = []
        
        if user_id:
            conditions.append("user_id=?")
            params.append(user_id)
        if status:
            conditions.append("status=?")
            params.append(status)
            
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY trigger_at"
        
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_pending_reminders_db():
    conn = _conn()
    try:
        now = datetime.utcnow().isoformat()

        rows = conn.execute(
            """SELECT * FROM reminders WHERE status='pending'"""
        ).fetchall()

        return [dict(r) for r in rows]
    finally:
        conn.close()