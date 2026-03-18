import asyncio
import json
import logging
import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)

class SSEManager:
    def __init__(self):
        # Maps user_id to a list of asyncio Queues.
        self.active_connections: Dict[str, List[asyncio.Queue]] = {}
        self.loop = None
        self.log_file = "data/sse_debug.log"

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop

    async def connect(self, user_id: str) -> asyncio.Queue:
        user_id = user_id.lower()
        q = asyncio.Queue()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(q)
        logger.info(f"➕ User '{user_id}' connected to SSE. Active connections: {len(self.active_connections[user_id])}")
        return q

    def disconnect(self, user_id: str, q: asyncio.Queue):
        user_id = user_id.lower()
        if user_id in self.active_connections:
            if q in self.active_connections[user_id]:
                self.active_connections[user_id].remove(q)
            logger.info(f"➖ User '{user_id}' disconnected from SSE. Remaining: {len(self.active_connections.get(user_id, []))}")
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    def emit(self, user_id: str, payload: dict):
        """Called from sync thread (APScheduler) or anywhere to dispatch event to user"""
        user_id = user_id.lower()
        if user_id in self.active_connections:
            if self.loop is None:
                logger.error(f"❌ SSEManager loop is not set! Cannot emit to {user_id}")
                return
            
            logger.info(f"📡 Emitting {payload.get('type')} to '{user_id}' ({len(self.active_connections[user_id])} connections)")
            with open(self.log_file, "a") as f:
                f.write(f"[{datetime.datetime.now()}] EMIT to {user_id}: {payload}\n")
            for q in self.active_connections[user_id]:
                # Thread-safe dispatch
                self.loop.call_soon_threadsafe(q.put_nowait, payload)
        else:
            logger.warning(f"⚠️ No active SSE connections for user '{user_id}'. Event dropped.")
            with open(self.log_file, "a") as f:
                f.write(f"[{datetime.datetime.now()}] DROP for {user_id}: No connection\n")

sse_manager = SSEManager()
