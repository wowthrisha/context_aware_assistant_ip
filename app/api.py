from contextlib import asynccontextmanager
import asyncio
import json

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .assistant_service import (
    run_assistant,
    get_conversation_history,
    clear_conversation_history,
    router,
    memory,
)
from .auth import get_current_user, create_token
from .action_router import start_scheduler, stop_scheduler, _scheduler
from .daily_summary import schedule_all_users, schedule_daily_summary
from .sse import sse_manager
from .database import upsert_notification_prefs, get_notification_prefs
from .notifier import send_whatsapp, send_email


@asynccontextmanager
async def lifespan(app: FastAPI):
    sse_manager.set_loop(asyncio.get_running_loop())
    start_scheduler()
    # Schedule daily summaries for all known users
    schedule_all_users(_scheduler)
    yield
    stop_scheduler()


app = FastAPI(title="Context-Aware Assistant API", version="5.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str

class LoginRequest(BaseModel):
    user_id: str


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.post("/login")
def login(req: LoginRequest):
    token = create_token(req.user_id)
    # Schedule daily summary for new user
    schedule_daily_summary(_scheduler, req.user_id)
    return {"token": token, "user_id": req.user_id}


@app.get("/")
def health_check():
    return {"status": "ok", "version": "5.0"}


# ── Chat ──────────────────────────────────────────────────────────────────────

@app.post("/chat")
def chat(req: ChatRequest, user_id: str = Depends(get_current_user)):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    user_id = user_id.lower()
    return run_assistant(req.message, user_id)


# ── Conversation history ──────────────────────────────────────────────────────

@app.get("/history")
def get_history(user_id: str = Depends(get_current_user)):
    return {"history": get_conversation_history(user_id.lower())}


@app.delete("/history")
def clear_hist(user_id: str = Depends(get_current_user)):
    clear_conversation_history(user_id.lower())
    return {"message": "History cleared."}


# ── Reminders ─────────────────────────────────────────────────────────────────

@app.get("/reminders")
def get_reminders(status: str = None, user_id: str = Depends(get_current_user)):
    reminders = router.get_all_reminders(user_id=user_id.lower(), status=status)
    return {"reminders": reminders}


@app.delete("/reminders/{reminder_id}")
def cancel_reminder(reminder_id: str, user_id: str = Depends(get_current_user)):
    result = router.cancel_by_id(reminder_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/reminders/stream")
async def stream_reminders(request: Request, user_id: str):
    q = await sse_manager.connect(user_id)

    async def event_generator():
        try:
            while True:
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {json.dumps(payload)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            sse_manager.disconnect(user_id, q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


<<<<<<< HEAD
# ── Notification Prefs ─────────────────────────

@app.get("/notification-prefs")
def api_get_notification_prefs(user_id: str = Depends(get_current_user)):
    prefs = get_notification_prefs(user_id.lower())
    return {"prefs": prefs if prefs else {}}


@app.post("/notification-prefs")
def api_set_notification_prefs(
    payload: dict,
    user_id: str = Depends(get_current_user)
):
    """
    Payload (all fields optional):
    {
      "whatsapp": "+91XXXXXXXXXX",
      "email": "you@example.com",
      "channels": ["sse", "whatsapp", "email"]
    }
    """
    upsert_notification_prefs(
        user_id=user_id.lower(),
        whatsapp=payload.get("whatsapp"),
        email=payload.get("email"),
        channels=payload.get("channels"),
    )
    return {"status": "saved", "prefs": get_notification_prefs(user_id.lower())}


@app.post("/test-notification")
async def api_test_notification(
    payload: dict,
    user_id: str = Depends(get_current_user)
):
    """
    Payload: {"channel": "whatsapp"|"email"|"all", "message": "optional text"}
    Fires a test notification to the user's configured channels.
    Runs blocking network calls in a thread pool so the HTTP connection stays alive.
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    msg = payload.get("message", "Test notification from your Context Assistant.")
    channel = payload.get("channel", "all")
    prefs = get_notification_prefs(user_id.lower())
    results = {}

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = []

        if channel in ("whatsapp", "all") and prefs.get("whatsapp"):
            futures.append(("whatsapp", loop.run_in_executor(
                pool, send_whatsapp, prefs["whatsapp"], f"TEST: {msg}"
            )))

        if channel in ("email", "all") and prefs.get("email"):
            futures.append(("email", loop.run_in_executor(
                pool, send_email, prefs["email"],
                "Test Notification — Context Assistant", msg
            )))

        for key, fut in futures:
            results[key] = await fut

    if not results:
        return {
            "status": "no_channels_configured",
            "hint": "Set up WhatsApp or email first via chat or POST /notification-prefs"
        }

    return {"status": "dispatched", "results": results}


# ── Memory ─────────────────────────
=======
# ── Memory ────────────────────────────────────────────────────────────────────
>>>>>>> f7e66f612baa81668c94700f0150ac9d91fc1cc3

@app.get("/memory/{memory_type}")
def get_memory(memory_type: str):
    valid = ("general", "preference", "habit")
    if memory_type not in valid:
        raise HTTPException(status_code=400, detail=f"Must be one of {valid}")
    return {"entries": memory.get_all(memory_type)}


@app.delete("/memory/{memory_type}/{memory_id}")
def delete_memory(memory_type: str, memory_id: str):
    success = memory.delete(memory_id, memory_type)
    if not success:
        raise HTTPException(status_code=404, detail="Memory entry not found.")
    return {"message": "Deleted."}


# ── Daily summary (manual trigger for testing) ────────────────────────────────

@app.post("/summary/trigger")
def trigger_summary(user_id: str = Depends(get_current_user)):
    """Manually trigger daily summary — useful for testing."""
    from .daily_summary import _send_daily_summary
    _send_daily_summary(user_id.lower())
    return {"message": f"Summary sent to {user_id}"}