# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A context-aware personal assistant with semantic memory, reminder scheduling, voice I/O, and real-time notifications. Two-part system: a Python FastAPI backend and a React frontend.

## Development Commands

### Backend
```bash
# Install Python dependencies
pip install -r requirements.txt

# Start the FastAPI server (required for frontend)
uvicorn app.api:app --reload --host 0.0.0.0 --port 8000

# Run CLI mode (no frontend needed)
python main.py
```

### Frontend
```bash
cd reminder-dashboard

# Install dependencies
npm install

# Start dev server (runs on port 5174)
npm run dev

# Build for production
npm run build

# Lint
npm run lint
```

### Environment Setup
Copy `.env` and set `ANTHROPIC_API_KEY=your_key_here`. The backend will not start without this key.

## Architecture

### Backend (`app/`)

**Request flow**: `app/api.py` → `app/assistant_service.py` → intent routing → response

- **`assistant_service.py`**: Central orchestrator. Detects intent, routes to memory/reminder/LLM, manages chat history (max 8 turns), surfaces habit-based proactive suggestions.
- **`intent.py`**: Regex-based intent classifier. Returns one of: `set_reminder`, `cancel_reminder`, `list_reminders`, `save_preference_positive`, `save_preference_negative`, `save_habit`, `recall_memory`, `general_chat`.
- **`action_router.py`**: Handles reminder CRUD. Uses APScheduler with SQLite jobstore (`data/apscheduler_jobs.db`) for persistence across restarts. On trigger, updates DB and emits SSE event.
- **`memory.py`**: ChromaDB-backed semantic memory in `memory_db/`. Three collections: `general_memory`, `user_preferences`, `user_habits`. Uses `sentence-transformers/all-MiniLM-L6-v2` for embeddings with deduplication.
- **`llm_engine.py`**: Wraps Claude Haiku (`claude-haiku-4-5-20251001`) with context injection from memory. Max 400 tokens.
- **`sse.py`**: Per-user async queues for real-time reminder notifications. Thread-safe dispatch from APScheduler (sync) to async SSE streams.
- **`database.py`**: SQLite (`data/reminders.db`) for reminder records with user_id, status (`pending`/`fired`/`cancelled`), timestamps.

**Auth**: Stateless `X-User-ID` header on every request. No session storage.

### Frontend (`reminder-dashboard/src/`)

Single-file app in `App.jsx`. Key sections:
- **Chat UI**: Message bubbles with user/assistant avatars
- **Voice I/O**: Web Speech API for input, SpeechSynthesis for output, voice selector
- **Reminders panel**: Live list with status filters, cancel button, pulls from `GET /reminders`
- **Memory panel**: Expandable grid showing ChromaDB entries by type, pulls from `GET /memory/{type}`
- **SSE client**: EventSource on `GET /reminders/stream` for real-time toast notifications + OS desktop notifications

### Data Storage

| Path | Type | Contents |
|------|------|----------|
| `data/reminders.db` | SQLite | Reminder records (all users) |
| `data/apscheduler_jobs.db` | SQLite | Scheduled job metadata |
| `memory_db/` | ChromaDB | Semantic embeddings (preferences, habits, general facts) |

### API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/chat` | Send message, get assistant reply |
| `GET` | `/reminders` | List reminders for user |
| `DELETE` | `/reminders/{id}` | Cancel a reminder |
| `GET` | `/reminders/stream` | SSE stream for real-time events |
| `GET` | `/memory/{type}` | Fetch memory entries by type |
| `POST` | `/login` | Generate user token |

## Key Design Decisions

- **Intent routing is regex-first**: `intent.py` uses regex patterns before invoking LLM, keeping latency low for common operations.
- **APScheduler persistence**: Jobs survive server restarts via SQLite jobstore; `action_router.py` reloads pending reminders on startup.
- **SSEManager thread-safety**: APScheduler runs in a background thread; `sse.py` bridges sync→async via `asyncio.run_coroutine_threadsafe`.
- **Memory deduplication**: Before saving, ChromaDB is queried for similarity; exact duplicates and high-similarity entries are skipped.
- **Chat history cap**: `assistant_service.py` keeps only the last 8 turns (16 messages) to control context window usage.
