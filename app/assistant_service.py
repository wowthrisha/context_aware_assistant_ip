"""
Central orchestrator.

Flow
────
1. Detect intent
2. If reminder → ActionRouter
3. If preference → extract + save to ChromaDB + acknowledge
4. If habit      → extract + save to ChromaDB + optionally suggest reminder
5. If recall     → pull memory → LLM answers using it
6. General chat  → pull all relevant memory → LLM
7. After EVERY turn → check habits → surface proactive suggestion if relevant
"""

from .intent           import IntentDetector
from .llm_engine       import LLMEngine
from .context_builder  import ContextBuilder
from .action_router    import ActionRouter
from .memory           import MemoryManager
from .memory_extractor import extract_preference, extract_habit
from .habit_suggester  import suggest_from_habits

# ── Singletons (loaded once, persist across requests) ─────────────────────────
detector = IntentDetector()
llm      = LLMEngine()
memory   = MemoryManager()          # shared — loads embedding model once
context  = ContextBuilder(memory)
router   = ActionRouter()

chat_history: list[str] = []
MAX_HISTORY = 8

# Track which habit suggestions we've already surfaced so we don't repeat
_surfaced_suggestions: set[str] = set()


# ── Main entry point ──────────────────────────────────────────────────────────

def run_assistant(msg: str) -> dict:
    intent = detector.detect_intent(msg)
    print(f"[Assistant] Intent: {intent}")

    action     = None
    reply      = ""
    memory_saved = None
    proactive_suggestion = None

    # ── 1. Reminder intents ───────────────────────────────────────────────────
    if intent in ("set_reminder", "cancel_reminder", "list_reminders"):
        action = router.handle_action(intent, msg)
        reply  = action.get("reply", "Sorry, something went wrong.") if action else "Could not process that."

    # ── 2. Save positive preference ───────────────────────────────────────────
    elif intent == "save_preference_positive":
        clean = extract_preference(msg, sentiment="positive")
        saved = memory.save_preference(clean, sentiment="positive")
        memory_saved = {"type": "preference", "text": clean, "sentiment": "positive", "stored": saved}
        reply = _acknowledge_preference(clean, "positive")

    # ── 3. Save negative preference ───────────────────────────────────────────
    elif intent == "save_preference_negative":
        clean = extract_preference(msg, sentiment="negative")
        saved = memory.save_preference(clean, sentiment="negative")
        memory_saved = {"type": "preference", "text": clean, "sentiment": "negative", "stored": saved}
        reply = _acknowledge_preference(clean, "negative")

    # ── 4. Save habit ─────────────────────────────────────────────────────────
    elif intent == "save_habit":
        clean, time_hint = extract_habit(msg)
        saved = memory.save_habit(clean, time_hint=time_hint)
        memory_saved = {"type": "habit", "text": clean, "time_hint": time_hint, "stored": saved}
        reply = _acknowledge_habit(clean, time_hint)

        # Immediately suggest a reminder for this habit
        if time_hint:
            proactive_suggestion = {
                "activity":  clean,
                "time_hint": time_hint,
                "message":   f"Want me to set a daily reminder for {time_hint}?",
            }

    # ── 5. Recall memory ──────────────────────────────────────────────────────
    elif intent == "recall_memory":
        ctx   = context.get_context(msg, intent)
        h_txt = "\n".join(chat_history[-MAX_HISTORY:])
        full  = "\n\n".join(filter(None, [h_txt, ctx]))
        reply = llm.generate_response(msg, intent, full or None)

    # ── 6. General chat ───────────────────────────────────────────────────────
    else:
        ctx   = context.get_context(msg, intent)
        h_txt = "\n".join(chat_history[-MAX_HISTORY:])
        full  = "\n\n".join(filter(None, [h_txt, ctx]))
        reply = llm.generate_response(msg, intent, full or None)

    # ── 7. Proactive habit suggestions (every turn) ───────────────────────────
    if not proactive_suggestion and intent not in ("set_reminder", "cancel_reminder", "list_reminders"):
        habits = memory.retrieve_habits()
        suggestions = suggest_from_habits(habits)
        for s in suggestions:
            key = s["time_hint"]
            if key not in _surfaced_suggestions:
                _surfaced_suggestions.add(key)
                proactive_suggestion = {
                    "activity":  s["activity"],
                    "time_hint": s["time_hint"],
                    "message":   s["suggestion"],
                }
                break   # surface one at a time

    # ── Store conversation turn ───────────────────────────────────────────────
    chat_history.append(f"User: {msg}")
    chat_history.append(f"Assistant: {reply}")
    if len(chat_history) > MAX_HISTORY * 2:
        chat_history[:] = chat_history[-(MAX_HISTORY * 2):]

    return {
        "reply":               reply,
        "intent":              intent,
        "system":              action,
        "memory_saved":        memory_saved,
        "proactive_suggestion": proactive_suggestion,
    }


# ── Acknowledgement helpers ───────────────────────────────────────────────────

def _acknowledge_preference(clean: str, sentiment: str) -> str:
    if sentiment == "positive":
        return f"Got it! I'll remember that. ✓\n\"{clean}\""
    else:
        return f"Noted — I'll keep that in mind. ✓\n\"{clean}\""


def _acknowledge_habit(clean: str, time_hint: str | None) -> str:
    base = f"Got it, I've noted your routine. ✓\n\"{clean}\""
    if time_hint:
        base += f"\n\nWant me to set a recurring reminder at {time_hint}?"
    return base