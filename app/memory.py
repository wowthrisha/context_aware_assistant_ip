"""
Persistent memory backed by ChromaDB.

Three separate collections:
  - general_memory    : facts the user mentions ("I have a dog named Max")
  - user_preferences  : likes / dislikes / settings
  - user_habits       : recurring routines with time patterns
"""

import uuid
import json
from datetime import datetime

import chromadb
from sentence_transformers import SentenceTransformer

from .config import (
    DB_PATH, EMBEDDING_MODEL,
    COLLECTION_GENERAL, COLLECTION_PREFERENCES, COLLECTION_HABITS,
    SIMILARITY_RESULTS,
)


class MemoryManager:

    def __init__(self):
        # PersistentClient writes to disk → survives restarts
        self.client = chromadb.PersistentClient(path=DB_PATH)
        self.embedder = SentenceTransformer(EMBEDDING_MODEL)

        self.general     = self.client.get_or_create_collection(COLLECTION_GENERAL)
        self.preferences = self.client.get_or_create_collection(COLLECTION_PREFERENCES)
        self.habits      = self.client.get_or_create_collection(COLLECTION_HABITS)

        self._collections = {
            "general":     self.general,
            "preference":  self.preferences,
            "habit":       self.habits,
        }

    # ── Embedding ──────────────────────────────────────────────────────────────

    def _embed(self, text: str) -> list:
        return self.embedder.encode(text).tolist()

    # ── Generic add ───────────────────────────────────────────────────────────

    def add_memory(self, text: str, memory_type: str, extra_meta: dict = None) -> bool:
        """
        Store a memory entry.  Returns False if near-duplicate detected.

        memory_type: 'general' | 'preference' | 'habit'
        extra_meta : optional dict merged into the stored metadata
        """
        collection = self._collections.get(memory_type, self.general)
        embedding  = self._embed(text)

        # Duplicate check — if very similar entry exists, skip
        try:
            existing = collection.query(query_embeddings=[embedding], n_results=1)
            if existing["documents"] and existing["documents"][0]:
                top_doc = existing["documents"][0][0]
                # simple exact-ish check
                if text.strip().lower() == top_doc.strip().lower():
                    return False
        except Exception:
            pass

        meta = {
            "type":       memory_type,
            "created_at": datetime.now().isoformat(),
        }
        if extra_meta:
            meta.update({k: str(v) for k, v in extra_meta.items()})

        collection.add(
            documents  =[text],
            embeddings =[embedding],
            ids        =[str(uuid.uuid4())],
            metadatas  =[meta],
        )
        return True

    # ── Specialised savers ────────────────────────────────────────────────────

    def save_preference(self, text: str, sentiment: str = "positive") -> bool:
        """
        sentiment: 'positive' (like/prefer) | 'negative' (dislike/hate)
        """
        return self.add_memory(
            text,
            memory_type="preference",
            extra_meta={"sentiment": sentiment},
        )

    def save_habit(self, text: str, time_hint: str = None) -> bool:
        """
        time_hint: e.g. '7am', 'evening' — extracted from the message if known
        """
        return self.add_memory(
            text,
            memory_type="habit",
            extra_meta={"time_hint": time_hint or ""},
        )

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def retrieve(self, query: str, memory_type: str = None, n: int = None) -> list[str]:
        """
        Returns a flat list of relevant memory strings.
        If memory_type is None, searches all three collections.
        """
        n = n or SIMILARITY_RESULTS
        embedding = self._embed(query)
        docs = []

        targets = (
            [self._collections[memory_type]]
            if memory_type and memory_type in self._collections
            else list(self._collections.values())
        )

        for col in targets:
            try:
                res = col.query(query_embeddings=[embedding], n_results=n)
                if res["documents"] and res["documents"][0]:
                    docs.extend(res["documents"][0])
            except Exception:
                pass

        # deduplicate while preserving order
        seen, unique = set(), []
        for d in docs:
            if d not in seen:
                seen.add(d)
                unique.append(d)

        return unique

    def retrieve_preferences(self, query: str) -> list[str]:
        return self.retrieve(query, memory_type="preference")

    def retrieve_habits(self, query: str = "routine workout sleep wake") -> list[str]:
        return self.retrieve(query, memory_type="habit")

    # ── Inspection helpers ────────────────────────────────────────────────────

    def get_all(self, memory_type: str) -> list[dict]:
        """Return all stored entries for a given type (for /memory API endpoint)."""
        col = self._collections.get(memory_type)
        if not col:
            return []
        try:
            result = col.get()
            rows = []
            for i, doc in enumerate(result["documents"]):
                rows.append({
                    "id":   result["ids"][i],
                    "text": doc,
                    "meta": result["metadatas"][i],
                })
            return rows
        except Exception:
            return []

    def delete(self, memory_id: str, memory_type: str) -> bool:
        col = self._collections.get(memory_type)
        if not col:
            return False
        try:
            col.delete(ids=[memory_id])
            return True
        except Exception:
            return False