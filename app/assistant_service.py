"""
assistant_service.py — Central orchestrator.

Features:
  1. Persistent conversation history (SQLite)
  2. Smart habit detection from repeated reminders
  3. Daily morning summary (via daily_summary.py)
  4. Memory-aware LLM responses
  5. Proactive habit suggestions
"""

from .intent              import IntentDetector
from .llm_engine          import LLMEngine
from .context_builder     import ContextBuilder
from .action_router       import ActionRouter
from .memory              import MemoryManager
from .memory_extractor    import extract_preference, extract_habit
from .habit_suggester     import suggest_from_habits
from .conversation_store  import (
    init_conversation_db,
    save_turn,
    load_history_text,
    clear_history,
)
from .habit_detector      import detect_habit_pattern
from .database            import get_all_reminders_db

# ── Singletons ────────────────────────────────────────────────────────────────

detector = IntentDetector()
llm      = LLMEngine()
memory   = MemoryManager()
router   = ActionRouter()

init_conversation_db()

_surfaced_suggestions: set[str] = set()
_surfaced_habit_hours: set[str] = set()   # track habit suggestions per user+hour


# ── Main entry point ──────────────────────────────────────────────────────────

def run_assistant(msg: str, user_id: str = "default") -> dict:
    intent = detector.detect_intent(msg)
    print(f"[Assistant] Intent: {intent} | User: {user_id}")

    context_builder   = ContextBuilder(memory)
    action            = None
    reply             = ""
    memory_saved      = None
    proactive         = None
    habit_suggestion  = None

    # ── Reminder intents ──────────────────────────────────────────────────────
    if intent in ("set_reminder", "cancel_reminder", "list_reminders"):
        action = router.handle_action(intent, msg, user_id)
        reply  = action.get("reply", "Sorry, something went wrong.")

        # ── Smart habit detection after setting a reminder ────────────────────
        if intent == "set_reminder" and action.get("reminder_id"):
            all_reminders = get_all_reminders_db(user_id=user_id)
            pattern = detect_habit_pattern(all_reminders)

            if pattern:
                key = f"{user_id}_{pattern['hour']}"
                if key not in _surfaced_habit_hours:
                    _surfaced_habit_hours.add(key)
                    habit_suggestion = {
                        "task":          pattern["task"],
                        "hour":          pattern["hour"],
                        "friendly_time": pattern["friendly_time"],
                        "message":       pattern["message"],
                    }

    # ── Save positive preference ───────────────────────────────────────────────
    elif intent == "save_preference_positive":
        clean = extract_preference(msg, sentiment="positive")
        saved = memory.save_preference(clean, sentiment="positive")
        memory_saved = {"type": "preference", "text": clean, "sentiment": "positive", "stored": saved}
        reply = f"Got it! I'll remember that. ✓\n\"{clean}\""

    # ── Save negative preference ───────────────────────────────────────────────
    elif intent == "save_preference_negative":
        clean = extract_preference(msg, sentiment="negative")
        saved = memory.save_preference(clean, sentiment="negative")
        memory_saved = {"type": "preference", "text": clean, "sentiment": "negative", "stored": saved}
        reply = f"Noted — I'll keep that in mind. ✓\n\"{clean}\""

    # ── Save habit ────────────────────────────────────────────────────────────
    elif intent == "save_habit":
        clean, time_hint = extract_habit(msg)
        saved = memory.save_habit(clean, time_hint=time_hint)
        memory_saved = {"type": "habit", "text": clean, "time_hint": time_hint, "stored": saved}
        reply = f"Got it, I've noted your routine. ✓\n\"{clean}\""
        if time_hint:
            proactive = {
                "activity":  clean,
                "time_hint": time_hint,
                "message":   f"Want me to set a daily reminder at {time_hint}?",
            }

    # ── Recall memory ─────────────────────────────────────────────────────────
    elif intent == "recall_memory":
        ctx      = context_builder.get_context(msg, intent)
        history  = load_history_text(user_id, limit=8)
        full_ctx = "\n\n".join(filter(None, [history, ctx]))
        reply    = llm.generate_response(msg, intent, full_ctx or None)

    # ── General chat ──────────────────────────────────────────────────────────
    else:
        ctx      = context_builder.get_context(msg, intent)
        history  = load_history_text(user_id, limit=8)
        full_ctx = "\n\n".join(filter(None, [history, ctx]))
        reply    = llm.generate_response(msg, intent, full_ctx or None)

    # ── Proactive habit suggestions (every non-reminder turn) ─────────────────
    if not proactive and intent not in ("set_reminder", "cancel_reminder", "list_reminders"):
        habits      = memory.retrieve_habits()
        suggestions = suggest_from_habits(habits)
        for s in suggestions:
            key = s["time_hint"]
            if key not in _surfaced_suggestions:
                _surfaced_suggestions.add(key)
                proactive = {
                    "activity":  s["activity"],
                    "time_hint": s["time_hint"],
                    "message":   s["suggestion"],
                }
                break

    # ── Persist conversation turn ─────────────────────────────────────────────
    save_turn(user_id, "user",      msg)
    save_turn(user_id, "assistant", reply)

    return {
        "reply":             reply,
        "intent":            intent,
        "system":            action,
        "memory_saved":      memory_saved,
        "proactive_suggestion": proactive,
        "habit_suggestion":  habit_suggestion,
    }


# ── Exposed helpers ───────────────────────────────────────────────────────────

def get_conversation_history(user_id: str) -> list[dict]:
    from .conversation_store import load_history
    return load_history(user_id, limit=50)


def clear_conversation_history(user_id: str) -> None:
    clear_history(user_id)