"""
context_builder.py — ML-enhanced context builder.

ML additions:
  - Cross-encoder re-ranking of retrieved memories for relevance
  - Scores each memory against the current query before injecting
  - Falls back to standard retrieval if cross-encoder not available

Standard retrieval: top-k by cosine similarity (ChromaDB)
ML enhancement:     re-rank retrieved memories by query relevance score
"""

import logging
from .memory import MemoryManager

logger = logging.getLogger(__name__)

# ── Lazy cross-encoder ────────────────────────────────────────────────────────

_cross_encoder = None

def _get_cross_encoder():
    global _cross_encoder
    if _cross_encoder is None:
        try:
            from sentence_transformers import CrossEncoder
            _cross_encoder = CrossEncoder(
                "cross-encoder/ms-marco-MiniLM-L-6-v2",
                device=-1,
            )
            print("[ContextBuilder] Cross-encoder loaded")
        except Exception as e:
            print(f"[ContextBuilder] Cross-encoder not available: {e}")
            _cross_encoder = False
    return _cross_encoder if _cross_encoder is not False else None


def _rerank(query: str, docs: list[str], top_k: int = 4) -> list[str]:
    """
    Re-rank retrieved documents using a cross-encoder.
    Returns top_k most relevant docs.
    """
    if not docs:
        return docs

    cross_encoder = _get_cross_encoder()
    if cross_encoder is None or len(docs) <= 1:
        return docs[:top_k]

    try:
        pairs  = [(query, doc) for doc in docs]
        scores = cross_encoder.predict(pairs)
        ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
        result = [doc for doc, _ in ranked[:top_k]]
        logger.info("[ContextBuilder] Re-ranked %d docs → top %d", len(docs), top_k)
        return result
    except Exception as e:
        logger.error("[ContextBuilder] Re-rank error: %s", e)
        return docs[:top_k]


class ContextBuilder:

    def __init__(self, memory: MemoryManager):
        self.memory = memory

    def get_context(self, user_input: str, intent: str) -> str | None:
        sections = []

        # Retrieve preferences and re-rank
        prefs = self.memory.retrieve_preferences(user_input)
        prefs = _rerank(user_input, prefs, top_k=3)
        if prefs:
            sections.append(
                "User preferences:\n" + "\n".join(f"  - {p}" for p in prefs)
            )

        # Retrieve habits and re-rank
        habits = self.memory.retrieve_habits(user_input)
        habits = _rerank(user_input, habits, top_k=3)
        if habits:
            sections.append(
                "User habits:\n" + "\n".join(f"  - {h}" for h in habits)
            )

        # General memory for recall/chat
        if intent in ("recall_memory", "general_chat"):
            general = self.memory.retrieve(user_input, memory_type="general")
            general = _rerank(user_input, general, top_k=3)
            if general:
                sections.append(
                    "Other known facts:\n" + "\n".join(f"  - {g}" for g in general)
                )

        if not sections:
            return None

        return "\n\n".join(sections)