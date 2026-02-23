from .intent import IntentDetector
from .llm_engine import LLMEngine
from .context_builder import ContextBuilder
from .action_router import ActionRouter

detector = IntentDetector()
llm = LLMEngine()
context = ContextBuilder()
router = ActionRouter()

# ⭐ NEW: simple conversation memory
chat_history = []

def run_assistant(msg:str):
    intent = detector.detect_intent(msg)
    ctx = context.get_context(msg,intent)

    # add history into context
    history_text = "\n".join(chat_history[-4:])  # last 4 turns only
    full_context = f"{history_text}\n{ctx}" if ctx else history_text

    reply = llm.generate_response(msg,intent,full_context)
    action = router.handle_action(intent,msg)

    # store conversation
    chat_history.append(f"User:{msg}")
    chat_history.append(f"Assistant:{reply}")
    print(chat_history)
    return {"reply": reply, "system": action}