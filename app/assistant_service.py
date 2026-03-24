"""
Central orchestrator.

Flow
────
1. Detect intent
2. If reminder → ActionRouter
3. If preference → extract + save to memory + acknowledge
4. If habit → extract + save to memory
5. If recall → pull memory → LLM answers using it
6. General chat → pull relevant memory → LLM
"""

from .intent import IntentDetector
from .llm_engine import LLMEngine
from .context_builder import ContextBuilder
from .action_router import ActionRouter
from .memory import MemoryManager
from .memory_extractor import extract_preference, extract_habit
from .habit_suggester import suggest_from_habits
from .database import upsert_notification_prefs, get_notification_prefs
from .conversation_store import load_history, clear_history

# convo APIs re-exported for api layer

def get_conversation_history(user_id: str):
    return load_history(user_id)


def clear_conversation_history(user_id: str):
    clear_history(user_id)


# ── Core singletons ─────────────────────────────────────────
detector = IntentDetector()
llm = LLMEngine()
memory = MemoryManager()
router = ActionRouter()

chat_history: list[str] = []
MAX_HISTORY = 8

_surfaced_suggestions: set[str] = set()


# ── Main entry point ─────────────────────────────────────────

def run_assistant(msg: str, user_id: str = "default") -> dict:

    intent = detector.detect_intent(msg)
    print(f"[Assistant] Intent: {intent}")

    action = None
    reply = ""
    memory_saved = None
    proactive_suggestion = None

    # Build user-specific context
    context = ContextBuilder(memory)

    # ── Reminder intents ─────────────────────────
    if intent in ("set_reminder", "cancel_reminder", "list_reminders"):

        action = router.handle_action(intent, msg, user_id)

        reply = action.get(
            "reply", "Sorry, something went wrong."
        )

    # ── Save positive preference ─────────────────
    elif intent == "save_preference_positive":

        clean = extract_preference(msg, sentiment="positive")

        saved = memory.save_preference(clean, sentiment="positive")
        memory_saved = {
            "type": "preference",
            "text": clean,
            "sentiment": "positive",
            "stored": saved,
        }

        reply = f"Got it! I'll remember that. ✓\n\"{clean}\""

    # ── Save negative preference ─────────────────
    elif intent == "save_preference_negative":

        clean = extract_preference(msg, sentiment="negative")

        saved = memory.save_preference(clean, sentiment="negative")

        memory_saved = {
            "type": "preference",
            "text": clean,
            "sentiment": "negative",
            "stored": saved,
        }

        reply = f"Noted — I'll keep that in mind. ✓\n\"{clean}\""

    # ── Save habit ─────────────────────────
    elif intent == "save_habit":

        clean, time_hint = extract_habit(msg)

        saved = memory.save_habit(clean, time_hint=time_hint)

        memory_saved = {
            "type": "habit",
            "text": clean,
            "time_hint": time_hint,
            "stored": saved,
        }

        reply = f"Got it, I've noted your routine. ✓\n\"{clean}\""

        if time_hint:
            proactive_suggestion = {
                "activity": clean,
                "time_hint": time_hint,
                "message": f"Want me to set a daily reminder at {time_hint}?",
            }

    # ── Set WhatsApp notification ─────────────
    elif intent == "set_whatsapp_notification":
        import re as _re
        phone_match = _re.search(r'(\+?\d[\d\s\-]{8,14}\d)', msg)
        if phone_match:
            raw = phone_match.group(1).replace(" ", "").replace("-", "")
            if not raw.startswith("+"):
                raw = "+" + raw
            upsert_notification_prefs(user_id, whatsapp=raw, channels=["sse", "whatsapp"])
            reply = (
                f"Done. I will send WhatsApp alerts to {raw} when your reminders fire. "
                f"Make sure you have joined the Twilio Sandbox first by texting "
                f"'join <your-keyword>' to +1 415 523 8886 once."
            )
        else:
            reply = "Please include your WhatsApp number. Example: 'Notify me on WhatsApp at +919876543210'"
        return {"reply": reply, "intent": intent, "system": None, "memory_saved": None, "proactive_suggestion": None}

    # ── Set email notification ─────────────────
    elif intent == "set_email_notification":
        import re as _re
        email_match = _re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', msg)
        if email_match:
            addr = email_match.group(0)
            upsert_notification_prefs(user_id, email=addr, channels=["sse", "email"])
            reply = f"Got it. I will send email alerts to {addr} when your reminders fire."
        else:
            reply = "Please include your email address. Example: 'Notify me by email at you@example.com'"
        return {"reply": reply, "intent": intent, "system": None, "memory_saved": None, "proactive_suggestion": None}

    # ── Disable notification ───────────────────
    elif intent == "disable_notification":
        upsert_notification_prefs(user_id, channels=["sse"])
        reply = "Notifications reset to in-app only. WhatsApp and email alerts are now off."
        return {"reply": reply, "intent": intent, "system": None, "memory_saved": None, "proactive_suggestion": None}

    # ── Get notification prefs ─────────────────
    elif intent == "get_notification_prefs":
        prefs = get_notification_prefs(user_id)
        if not prefs:
            reply = "No notification preferences set. You are receiving in-app (SSE) alerts only."
        else:
            ch = prefs.get("channels", "sse")
            wa = prefs.get("whatsapp") or "not set"
            em = prefs.get("email") or "not set"
            reply = f"Your notification settings:\nChannels: {ch}\nWhatsApp: {wa}\nEmail: {em}"
        return {"reply": reply, "intent": intent, "system": None, "memory_saved": None, "proactive_suggestion": None}

    # ── Recall memory ─────────────────────────
    elif intent == "recall_memory":

        ctx = context.get_context(msg, intent)

        h_txt = "\n".join(chat_history[-MAX_HISTORY:])

        full = "\n\n".join(filter(None, [h_txt, ctx]))

        reply = llm.generate_response(msg, intent, full or None)

    # ── General chat ─────────────────────────
    else:

        ctx = context.get_context(msg, intent)

        h_txt = "\n".join(chat_history[-MAX_HISTORY:])

        full = "\n\n".join(filter(None, [h_txt, ctx]))

        reply = llm.generate_response(msg, intent, full or None)

    # ── Habit suggestions ─────────────────────────
    if not proactive_suggestion:

        habits = memory.retrieve_habits()
        
        suggestions = suggest_from_habits(habits)

        for s in suggestions:

            key = s["time_hint"]

            if key not in _surfaced_suggestions:

                _surfaced_suggestions.add(key)

                proactive_suggestion = {
                    "activity": s["activity"],
                    "time_hint": s["time_hint"],
                    "message": s["suggestion"],
                }

                break

    # ── Save conversation history ─────────────────────────

    chat_history.append(f"User: {msg}")
    chat_history.append(f"Assistant: {reply}")

    if len(chat_history) > MAX_HISTORY * 2:

        chat_history[:] = chat_history[-(MAX_HISTORY * 2):]

    return {
        "reply": reply,
        "intent": intent,
        "system": action,
        "memory_saved": memory_saved,
        "proactive_suggestion": proactive_suggestion,
    }