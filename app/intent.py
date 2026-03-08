import re


class IntentDetector:

    def detect_intent(self, text: str) -> str:
        t = text.lower().strip()

        # ── Reminder management ────────────────────────────────────────────────
        if re.search(r"\b(cancel|delete|remove)\b.*\b(reminder|alarm)\b", t):
            return "cancel_reminder"
        if re.search(r"\b(list|show|what are my|view)\b.*\b(reminder|alarm)s?\b", t):
            return "list_reminders"
        if re.search(r"\b(remind|alarm|schedule)\b", t) or "reminder" in t:
            return "set_reminder"

        # ── Memory queries (recall) ────────────────────────────────────────────
        if re.search(r"\b(what do i|do i like|do i prefer|what's my|what are my habits|my routine)\b", t):
            return "recall_memory"
        if re.search(r"\b(what|when|where|do i|did i|have i)\b", t):
            return "recall_memory"

        # ── Preference saving ─────────────────────────────────────────────────
        # Positive
        if re.search(r"\b(i (love|like|enjoy|prefer|want|adore)|my favou?rite)\b", t):
            return "save_preference_positive"
        # Negative
        if re.search(r"\b(i (hate|dislike|don'?t like|can'?t stand|avoid|detest))\b", t):
            return "save_preference_negative"
        # Generic
        if re.search(r"\b(prefer|favourite|favorite)\b", t):
            return "save_preference_positive"

        # ── Habit saving ───────────────────────────────────────────────────────
        if re.search(
            r"\b(i always|i usually|i normally|every (morning|evening|night|day|week)|"
            r"my routine|i wake|i sleep|i work ?out|i exercise|i study|i eat|i go to (bed|gym|work))\b",
            t,
        ):
            return "save_habit"

        return "general_chat"