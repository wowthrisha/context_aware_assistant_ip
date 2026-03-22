"""
conversation_store.py — SQLite-backed conversation history.

Persists chat turns across restarts so the assistant remembers
what was said in previous sessions.
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_HERE         = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent
_DB_PATH      = _PROJECT_ROOT / "data" / "conversations.db"


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_conversation_db() -> None:
    conn = _conn()
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    TEXT    NOT NULL,
            role       TEXT    NOT NULL,
            content    TEXT    NOT NULL,
            created_at TEXT    NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id);
        CREATE INDEX IF NOT EXISTS idx_conv_time ON conversations(created_at);
        """)
        conn.commit()
        logger.info("Conversation DB ready at %s", _DB_PATH)
    finally:
        conn.close()


def save_turn(user_id: str, role: str, content: str) -> None:
    """Save a single conversation turn (role = 'user' or 'assistant')."""
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO conversations (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (user_id, role, content, datetime.utcnow().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def load_history(user_id: str, limit: int = 20) -> list[dict]:
    """
    Load the last N turns for a user.
    Returns list of {"role": str, "content": str}
    """
    conn = _conn()
    try:
        rows = conn.execute(
            """
            SELECT role, content FROM conversations
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        # Reverse so oldest first
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    finally:
        conn.close()


def load_history_text(user_id: str, limit: int = 8) -> str:
    """Return history as a plain text string for LLM context."""
    turns = load_history(user_id, limit=limit)
    lines = []
    for t in turns:
        prefix = "User" if t["role"] == "user" else "Assistant"
        lines.append(f"{prefix}: {t['content']}")
    return "\n".join(lines)


def clear_history(user_id: str) -> None:
    conn = _conn()
    try:
        conn.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


def get_all_users() -> list[str]:
    """Return all user_ids that have conversation history."""
    conn = _conn()
    try:
        rows = conn.execute("SELECT DISTINCT user_id FROM conversations").fetchall()
        return [r["user_id"] for r in rows]
    finally:
        conn.close()