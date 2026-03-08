import uuid
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from .time_parser import parse_time, extract_task


class ActionRouter:

    def __init__(self):
        # Store reminders as dict: id → reminder
        self.reminders: dict = {}

        self.scheduler = BackgroundScheduler()
        self.scheduler.start()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _fire_reminder(self, reminder_id: str):
        """Called by the scheduler when a reminder's time arrives."""
        if reminder_id in self.reminders:
            self.reminders[reminder_id]["status"] = "fired"
            task = self.reminders[reminder_id]["task"]
            print(f"\n🔔 REMINDER [{reminder_id[:8]}]: {task}\n")

    # ------------------------------------------------------------------
    # Public action handler
    # ------------------------------------------------------------------

    def handle_action(self, intent: str, msg: str) -> dict | None:

        if intent == "set_reminder":
            return self._set_reminder(msg)

        if intent == "cancel_reminder":
            return self._cancel_latest_reminder()

        if intent == "list_reminders":
            return self._list_reminders()

        return None

    # ------------------------------------------------------------------
    # Reminder operations
    # ------------------------------------------------------------------

    def _set_reminder(self, msg: str) -> dict:
        time = parse_time(msg)

        if not time:
            return {
                "reply": "Sorry, I couldn't understand the time. Try something like: \"Remind me to call John at 3pm\" or \"Remind me in 30 minutes\"."
            }

        if time <= datetime.now():
            return {
                "reply": "That time has already passed. Please give a future time."
            }

        task = extract_task(msg)
        reminder_id = str(uuid.uuid4())

        reminder = {
            "id": reminder_id,
            "task": task,
            "raw_message": msg,
            "time": time.isoformat(),
            "created_at": datetime.now().isoformat(),
            "status": "pending"  # pending | fired | cancelled
        }

        self.reminders[reminder_id] = reminder

        # Schedule the callback
        self.scheduler.add_job(
            self._fire_reminder,
            trigger="date",
            run_date=time,
            args=[reminder_id],
            id=reminder_id,
            replace_existing=True
        )

        friendly_time = time.strftime("%A, %b %d at %I:%M %p")
        return {
            "reply": f"✅ Reminder set for {friendly_time} — \"{task}\"",
            "reminder": reminder
        }

    def _cancel_latest_reminder(self) -> dict:
        pending = [r for r in self.reminders.values() if r["status"] == "pending"]

        if not pending:
            return {"reply": "You have no pending reminders to cancel."}

        # Cancel the most recently created pending reminder
        latest = sorted(pending, key=lambda r: r["created_at"], reverse=True)[0]
        latest["status"] = "cancelled"

        try:
            self.scheduler.remove_job(latest["id"])
        except Exception:
            pass

        return {
            "reply": f"🚫 Cancelled reminder: \"{latest['task']}\"",
            "reminder": latest
        }

    def cancel_by_id(self, reminder_id: str) -> dict:
        if reminder_id not in self.reminders:
            return {"error": "Reminder not found."}

        reminder = self.reminders[reminder_id]
        if reminder["status"] != "pending":
            return {"error": f"Cannot cancel — reminder is already '{reminder['status']}'."}

        reminder["status"] = "cancelled"
        try:
            self.scheduler.remove_job(reminder_id)
        except Exception:
            pass

        return {"message": f"Cancelled: \"{reminder['task']}\"", "reminder": reminder}

    def _list_reminders(self) -> dict:
        pending = [r for r in self.reminders.values() if r["status"] == "pending"]
        if not pending:
            return {"reply": "You have no upcoming reminders."}

        lines = []
        for r in sorted(pending, key=lambda x: x["time"]):
            t = datetime.fromisoformat(r["time"]).strftime("%b %d at %I:%M %p")
            lines.append(f"• {r['task']} — {t}")

        return {"reply": "Your upcoming reminders:\n" + "\n".join(lines)}

    # ------------------------------------------------------------------
    # Helpers for API
    # ------------------------------------------------------------------

    def get_all_reminders(self, status: str = None) -> list:
        all_r = list(self.reminders.values())
        if status:
            all_r = [r for r in all_r if r["status"] == status]
        return sorted(all_r, key=lambda r: r["created_at"], reverse=True)