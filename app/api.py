from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .assistant_service import run_assistant, chat_history, router, memory

app = FastAPI(title="Context-Aware Assistant API", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


# ── Chat ──────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "running", "version": "3.0"}


@app.post("/chat")
def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    return run_assistant(req.message)


@app.get("/history")
def get_history():
    return {"history": chat_history}


@app.delete("/history")
def clear_history():
    chat_history.clear()
    return {"message": "History cleared."}


# ── Reminders ─────────────────────────────────────────────────────────────────

@app.get("/reminders")
def get_reminders(status: str = None):
    reminders = router.get_all_reminders(status=status)
    return {"reminders": reminders, "count": len(reminders)}


@app.delete("/reminders/{reminder_id}")
def cancel_reminder(reminder_id: str):
    result = router.cancel_by_id(reminder_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Memory ────────────────────────────────────────────────────────────────────

@app.get("/memory/{memory_type}")
def get_memory(memory_type: str):
    """
    memory_type: general | preference | habit
    Returns all stored entries for that collection.
    """
    valid = ("general", "preference", "habit")
    if memory_type not in valid:
        raise HTTPException(status_code=400, detail=f"memory_type must be one of {valid}")
    return {"type": memory_type, "entries": memory.get_all(memory_type)}


@app.delete("/memory/{memory_type}/{memory_id}")
def delete_memory(memory_type: str, memory_id: str):
    success = memory.delete(memory_id, memory_type)
    if not success:
        raise HTTPException(status_code=404, detail="Memory entry not found.")
    return {"message": "Deleted."}