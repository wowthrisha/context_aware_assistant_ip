"""
daily_summary.py — Schedules a daily 8am summary notification via SSE.

The summary includes:
  - Pending reminders for the day
  - User preferences (e.g. "you prefer coffee in the morning")
  - Habit nudges
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _build_summary(user_id: str) -> str:
    from .database import get_all_reminders_db
    from .memory import MemoryManager

    lines = ["Good morning! Here's your daily summary:"]

    all_pending = get_all_reminders_db(user_id=user_id, status="pending")
    today = datetime.now().date()

    todays = [
        r for r in all_pending
        if datetime.fromisoformat(r["trigger_at"]).date() == today
    ]

    if todays:
        lines.append(f"\nYou have {len(todays)} reminder(s) today:")
        for r in todays:
            dt = datetime.fromisoformat(r["trigger_at"])
            try:
                t_str = dt.strftime("%-I:%M %p")
            except ValueError:
                t_str = dt.strftime("%I:%M %p").lstrip("0")
            rec = " (recurring)" if r.get("recurrence") else ""
            lines.append(f"  - {t_str}: {r['message']}{rec}")
    else:
        lines.append("\nNo reminders scheduled for today.")

    try:
        mem = MemoryManager()
        prefs = mem.retrieve_preferences("morning routine coffee")
        if prefs:
            lines.append(f"\nRemember: {prefs[0]}")
    except Exception:
        pass

    lines.append("\nHave a great day!")
    return "\n".join(lines)



def _send_daily_summary(user_id: str) -> None:
    """Called by APScheduler at 8am daily."""
    from .sse import sse_manager

    logger.info("📅 Sending daily summary to user: %s", user_id)

    try:
        message = _build_summary(user_id)
        sse_manager.emit(user_id, {
            "type":    "daily_summary",
            "message": message,
        })
        logger.info("✅ Daily summary sent to %s", user_id)
    except Exception as e:
        logger.error("❌ Failed to send daily summary to %s: %s", user_id, e)


def schedule_daily_summary(scheduler, user_id: str) -> None:
    """
    Schedule the daily 8am summary for a user.
    Safe to call multiple times — uses replace_existing=True.
    """
    job_id = f"daily_summary_{user_id}"

    scheduler.add_job(
        _send_daily_summary,
        trigger="cron",
        hour=8,
        minute=0,
        args=[user_id],
        id=job_id,
        replace_existing=True,
    )
    logger.info("📅 Daily summary scheduled at 8am for user: %s", user_id)


def schedule_all_users(scheduler) -> None:
    """Schedule daily summaries for all known users on startup."""
    from .conversation_store import get_all_users

    users = get_all_users()
    for user_id in users:
        schedule_daily_summary(scheduler, user_id)
    logger.info("📅 Daily summaries scheduled for %d user(s)", len(users))