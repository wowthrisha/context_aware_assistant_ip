"""
action_router.py — ActionRouter with APScheduler + SQLite + recurring reminders.

Multi-user version (user_id support)
"""

import uuid
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from .database import (
    init_db,
    save_reminder,
    mark_fired,
    mark_cancelled,
    get_all_reminders_db,
    get_pending_reminders_db,
    get_reminder_by_id,
)
from .time_parser import parse_time, extract_task, detect_recurrence

logger = logging.getLogger(__name__)

# ── APScheduler setup ─────────────────────────────────────────────────────────

_HERE         = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent
_DATA_DIR     = _PROJECT_ROOT / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

_APSCHED_URL = f"sqlite:///{_DATA_DIR / 'apscheduler_jobs.db'}"

_scheduler = BackgroundScheduler(
    jobstores   ={"default": SQLAlchemyJobStore(url=_APSCHED_URL)},
    executors   ={"default": ThreadPoolExecutor(max_workers=10)},
    job_defaults={
        "coalesce":           True,
        "max_instances":      1,
        "misfire_grace_time": None,   # fire even if late
    },
)

# ── Recurring reschedule ──────────────────────────────────────────────────────

def _reschedule_recurring(rem: dict, user_id: str):
    rec_type = rem.get("recurrence")
    interval = rem.get("interval")
    now      = datetime.now()
    next_time = None

    if rec_type == "hourly":
        next_time = now + timedelta(hours=1)
    elif rec_type == "interval_minutes" and interval:
        next_time = now + timedelta(minutes=interval)
    elif rec_type == "interval_hours" and interval:
        next_time = now + timedelta(hours=interval)
    elif rec_type in ("daily", "daily_morning"):
        base = datetime.fromisoformat(rem["trigger_at"])
        next_time = now.replace(hour=base.hour, minute=base.minute, second=0, microsecond=0) + timedelta(days=1)
    elif rec_type == "daily_evening":
        next_time = now.replace(hour=18, minute=0, second=0, microsecond=0) + timedelta(days=1)
    elif rec_type == "daily_night":
        next_time = now.replace(hour=21, minute=0, second=0, microsecond=0) + timedelta(days=1)
    elif rec_type and rec_type.startswith("weekly_"):
        day_map = {
            "weekly_monday": 0, "weekly_tuesday": 1, "weekly_wednesday": 2,
            "weekly_thursday": 3, "weekly_friday": 4,
            "weekly_saturday": 5, "weekly_sunday": 6,
        }
        target_day = day_map.get(rec_type, 0)
        days_ahead = (target_day - now.weekday() + 7) % 7 or 7
        base = datetime.fromisoformat(rem["trigger_at"])
        next_time = (now + timedelta(days=days_ahead)).replace(
            hour=base.hour, minute=base.minute, second=0, microsecond=0
        )

    if not next_time:
        logger.warning("Could not calculate next time for recurrence: %s", rec_type)
        return

    new_id = str(uuid.uuid4())
    save_reminder(new_id, user_id, rem["message"], next_time,
                  recurrence=rec_type, interval=interval)

    _scheduler.add_job(
        _reminder_callback,
        trigger="date",
        run_date=next_time,
        args=[new_id, rem["message"], user_id],
        id=new_id,
        replace_existing=True,
    )
    logger.info("🔁 Rescheduled recurring reminder → %s at %s", new_id, next_time)


# ── Reminder callback ─────────────────────────────────────────────────────────

def _reminder_callback(reminder_id: str, message: str, user_id: str):
    logger.info("🔔 REMINDER FIRED [%s] user=%s msg=%s", reminder_id, user_id, message)
    mark_fired(reminder_id)

    from .sse import sse_manager
    sse_manager.emit(user_id, {
        "type":        "reminder",
        "reminder_id": reminder_id,
        "message":     message,
        "trigger_at":  datetime.utcnow().isoformat(),
    })

    rem = get_reminder_by_id(reminder_id)
    if rem and rem.get("recurrence"):
        _reschedule_recurring(rem, user_id)


# ── Scheduler events ──────────────────────────────────────────────────────────

def _on_job_event(event):
    if event.exception:
        logger.error("❌ Job %s failed: %s", event.job_id, event.exception)
    else:
        logger.info("✅ Job %s completed", event.job_id)

_scheduler.add_listener(_on_job_event, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)


# ── Lifecycle ─────────────────────────────────────────────────────────────────

def start_scheduler():
    init_db()
    if not _scheduler.running:
        _scheduler.start()
        logger.info("🚀 APScheduler started — %s", _APSCHED_URL)
    _reload_pending_reminders()


def stop_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("🛑 APScheduler stopped")


def _reload_pending_reminders():
    pending  = get_pending_reminders_db()
    reloaded = 0
    for rem in pending:
        jid = rem["id"]
        if _scheduler.get_job(jid):
            continue
        trigger_at = datetime.fromisoformat(rem["trigger_at"])
        _scheduler.add_job(
            _reminder_callback,
            trigger="date",
            run_date=trigger_at,
            args=[jid, rem["message"], rem["user_id"]],
            id=jid,
            replace_existing=True,
        )
        reloaded += 1
        logger.info("♻️ Reloaded %s → %s", jid, trigger_at)
    logger.info("ℹ️ %d pending reminder(s) reloaded", reloaded)


# ── Action Router ─────────────────────────────────────────────────────────────

class ActionRouter:

    def handle_action(self, intent: str, message: str, user_id: str) -> dict:
        if intent == "set_reminder":
            return self._set_reminder(message, user_id)
        elif intent == "cancel_reminder":
            return self._cancel_latest(user_id)
        elif intent == "list_reminders":
            return self._list_reminders(user_id)
        return {"reply": "I didn't understand that action."}

    # ── Set reminder ──────────────────────────────────────────────────────────

    def _set_reminder(self, message: str, user_id: str) -> dict:
        trigger_at = parse_time(message)
        recurrence = detect_recurrence(message)

        if not trigger_at and not recurrence:
            clean_msg = extract_task(message)
            if clean_msg and len(clean_msg) > 2:
             return {
                "reply": f"When should I remind you to {clean_msg}? "
                         f"Try: 'remind me to {clean_msg} in 30 minutes' "
                         f"or 'remind me to {clean_msg} at 8pm'"
            }
            return {
                "reply": (
                    "I couldn't figure out when to remind you. "
                    "Try: 'remind me in 30 minutes to call John' "
                    "or 'remind me every day at 7am to work out'."
                )
            }

        if not trigger_at:
            trigger_at = datetime.now() + timedelta(minutes=1)

        # Extract task — use "reminder" as fallback if nothing found
        clean_msg = extract_task(message)
        if not clean_msg:
            clean_msg = "reminder"

        reminder_id = str(uuid.uuid4())
        rec_type    = recurrence["type"]     if recurrence else None
        interval    = recurrence["interval"] if recurrence else None

        save_reminder(
            reminder_id, user_id, clean_msg, trigger_at,
            recurrence=rec_type, interval=interval,
        )

        _scheduler.add_job(
            _reminder_callback,
            trigger="date",
            run_date=trigger_at,
            args=[reminder_id, clean_msg, user_id],
            id=reminder_id,
            replace_existing=True,
        )

        if recurrence:
            label = (
                rec_type
                .replace("_", " ")
                .replace("daily", "day")
                .replace("weekly ", "")
            )
            return {
                "reply":       f"🔁 Recurring reminder set (every {label}) — \"{clean_msg}\"",
                "reminder_id": reminder_id,
                "trigger_at":  trigger_at.isoformat(),
                "recurrence":  rec_type,
            }

        try:
            friendly = trigger_at.strftime("%-I:%M %p on %a, %b %d")
        except ValueError:
            friendly = trigger_at.strftime("%I:%M %p on %a, %b %d").lstrip("0")

        return {
            "reply":       f"✅ Reminder set for {friendly} — \"{clean_msg}\"",
            "reminder_id": reminder_id,
            "trigger_at":  trigger_at.isoformat(),
        }

    # ── Cancel latest ─────────────────────────────────────────────────────────

    def _cancel_latest(self, user_id: str) -> dict:
        pending = get_all_reminders_db(user_id=user_id, status="pending")
        if not pending:
            return {"reply": "You have no pending reminders to cancel."}
        return self.cancel_by_id(pending[0]["id"])

    # ── List reminders ────────────────────────────────────────────────────────

    def _list_reminders(self, user_id: str) -> dict:
        pending = get_all_reminders_db(user_id=user_id, status="pending")
        if not pending:
            return {"reply": "You have no pending reminders."}

        lines = []
        for r in pending:
            dt = datetime.fromisoformat(r["trigger_at"])
            try:
                t_str = dt.strftime("%-I:%M %p")
            except ValueError:
                t_str = dt.strftime("%I:%M %p").lstrip("0")
            rec_label = f" 🔁 {r['recurrence'].replace('_',' ')}" if r.get("recurrence") else ""
            lines.append(f"• {t_str} — {r['message']}{rec_label}")

        return {"reply": "📋 Your pending reminders:\n" + "\n".join(lines)}

    # ── Cancel by ID ──────────────────────────────────────────────────────────

    def cancel_by_id(self, reminder_id: str) -> dict:
        job = _scheduler.get_job(reminder_id)
        if job:
            job.remove()
        updated = mark_cancelled(reminder_id)
        if updated:
            return {"reply": "🗑️ Reminder cancelled.", "cancelled_id": reminder_id}
        return {"error": f"Reminder '{reminder_id}' not found or already completed."}

    # ── Get all ───────────────────────────────────────────────────────────────

    def get_all_reminders(self, user_id: str, status: Optional[str] = None) -> list:
        return get_all_reminders_db(user_id=user_id, status=status)