from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, Depends
from contextlib import asynccontextmanager

from pydantic import BaseModel

from .assistant_service import run_assistant, chat_history, router, memory
from .auth import get_current_user, create_token
from .action_router import start_scheduler, stop_scheduler
from .sse import sse_manager
import asyncio
import json
from fastapi import Request
from fastapi.responses import StreamingResponse

@asynccontextmanager
async def lifespan(app: FastAPI):
    sse_manager.set_loop(asyncio.get_running_loop())
    start_scheduler()
    yield
    stop_scheduler()

app = FastAPI(title="Context-Aware Assistant API", version="4.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


class LoginRequest(BaseModel):
    user_id: str


# ── Login ─────────────────────────────

@app.post("/login")
def login(req: LoginRequest):

    token = create_token(req.user_id)

    return {
        "token": token,
        "user_id": req.user_id
    }


@app.get("/")
def health_check():
    return {"status": "ok"}


# ── Chat ─────────────────────────────

@app.post("/chat")
def chat(
    req: ChatRequest,
    user_id: str = Depends(get_current_user)
):

    if not req.message.strip():
        raise HTTPException(status_code=400)

    user_id = user_id.lower()
    result = run_assistant(req.message, user_id)

    return result



# ── History ─────────────────────────────

@app.get("/history")
def get_history():
    return {"history": chat_history}


@app.delete("/history")
def clear_history():
    chat_history.clear()
    return {"message": "History cleared."}


# ── Reminders ─────────────────────────

@app.get("/reminders")
def get_reminders(
    status: str = None,
    user_id: str = Depends(get_current_user)
):

    user_id = user_id.lower()
    reminders = router.get_all_reminders(user_id=user_id, status=status)

    return {"reminders": reminders}


@app.delete("/reminders/{reminder_id}")
def cancel_reminder(
    reminder_id: str,
    user_id: str = Depends(get_current_user)
):

    result = router.cancel_by_id(reminder_id)

    if "error" in result:
        raise HTTPException(status_code=400)

    return result

@app.get("/reminders/stream")
async def stream_reminders(request: Request, user_id: str):
    """
    SSE stream endpoint for real-time notifications.
    Takes user_id via query parameter since standard EventSource doesn't support custom headers easily.
    """
    q = await sse_manager.connect(user_id)

    async def event_generator():
        try:
            while True:
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {json.dumps(payload)}\n\n"
                except asyncio.TimeoutError:
                    # Keep-alive comment
                    yield ": ping\n\n"
        finally:
            sse_manager.disconnect(user_id, q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── Memory ─────────────────────────

@app.get("/memory/{memory_type}")
def get_memory(memory_type: str):

    valid = ("general", "preference", "habit")

    if memory_type not in valid:
        raise HTTPException(status_code=400)

    return {"entries": memory.get_all(memory_type)}