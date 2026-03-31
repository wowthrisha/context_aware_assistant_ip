"""
memory_extractor.py — ML-enhanced preference and habit extraction.

ML additions:
  - HuggingFace sentiment pipeline for accurate positive/negative detection
  - Falls back to regex patterns if transformers not available

Examples:
  "I hate mornings"           → ("User dislikes: mornings", "negative")
  "I prefer tea over coffee"  → ("User likes/prefers: tea over coffee", "positive")
  "I always work out at 7am"  → ("User habit: works out at 7am", "7am")
"""

import re
import logging

logger = logging.getLogger(__name__)

# ── Lazy ML sentiment pipeline ────────────────────────────────────────────────

_sentiment_pipeline = None

def _get_sentiment_pipeline():
    global _sentiment_pipeline
    if _sentiment_pipeline is None:
        try:
            from transformers import pipeline
            _sentiment_pipeline = pipeline(
                "sentiment-analysis",
                model="distilbert-base-uncased-finetuned-sst-2-english",
                device=-1,
            )
            print("[MemoryExtractor] Sentiment pipeline loaded")
        except Exception as e:
            print(f"[MemoryExtractor] Sentiment pipeline not available: {e}")
            _sentiment_pipeline = False
    return _sentiment_pipeline if _sentiment_pipeline is not False else None


def detect_sentiment_ml(text: str) -> str:
    """
    Use DistilBERT to detect sentiment.
    Returns 'positive' or 'negative'.
    Falls back to keyword matching.
    """
    pipeline_ = _get_sentiment_pipeline()
    if pipeline_:
        try:
            result = pipeline_(text[:512])[0]
            label = result["label"].lower()
            score = result["score"]
            logger.info("[ML Sentiment] '%s' → %s (%.2f)", text[:40], label, score)
            return "positive" if label == "positive" else "negative"
        except Exception as e:
            logger.error("[ML Sentiment] Error: %s", e)

    # Fallback: keyword-based
    negative_words = ["hate", "dislike", "don't like", "cant stand", "avoid",
                      "detest", "terrible", "awful", "bad", "worse", "worst"]
    t = text.lower()
    for word in negative_words:
        if word in t:
            return "negative"
    return "positive"


# ── Preference patterns ───────────────────────────────────────────────────────

_POSITIVE_PATTERNS = [
    r"i (love|like|enjoy|prefer|adore|want) (.+)",
    r"my favou?rite (.+?) is (.+)",
    r"i'?m a (big )?fan of (.+)",
    r"i'?m into (.+)",
    r"i really like (.+)",
]

_NEGATIVE_PATTERNS = [
    r"i (hate|dislike|can'?t stand|avoid|detest|don'?t like|despise) (.+)",
    r"i'?m not a fan of (.+)",
    r"i really dislike (.+)",
    r"(.+) is terrible",
    r"(.+) is awful",
]


def extract_preference(text: str, sentiment: str = None) -> str:
    """
    Extract a clean preference string.
    If sentiment not provided, uses ML to detect it.
    """
    if sentiment is None:
        sentiment = detect_sentiment_ml(text)

    t = text.lower().strip().rstrip(".")

    patterns = _POSITIVE_PATTERNS if sentiment == "positive" else _NEGATIVE_PATTERNS
    label    = "likes/prefers" if sentiment == "positive" else "dislikes"

    for pat in patterns:
        m = re.search(pat, t)
        if m:
            groups = [g for g in m.groups() if g]
            phrase = " ".join(groups[-2:]) if len(groups) >= 2 else groups[-1] if groups else t
            return f"User {label}: {phrase.strip()}"

    # Fallback
    return text.strip()


# ── Habit patterns ────────────────────────────────────────────────────────────

_TIME_HINT_PATTERN = re.compile(
    r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm)|morning|evening|night|afternoon|noon)\b",
    re.IGNORECASE,
)

_HABIT_PATTERNS = [
    r"i always (.+)",
    r"i usually (.+)",
    r"i normally (.+)",
    r"every (morning|evening|night|day|week)[,]? i (.+)",
    r"my routine (is |includes )?(.+)",
    r"i (wake up|sleep|work ?out|exercise|study|eat|go to \w+) (.+)",
    r"i tend to (.+)",
    r"i make it a habit to (.+)",
]


def extract_habit(text: str) -> tuple[str, str | None]:
    """
    Extract habit string and optional time hint.

    Example:
        "I always work out at 7am" → ("User habit: works out at 7am", "7am")
    """
    t = text.lower().strip().rstrip(".")

    # Extract time hint
    time_match = _TIME_HINT_PATTERN.search(t)
    time_hint  = time_match.group(0).strip() if time_match else None

    for pat in _HABIT_PATTERNS:
        m = re.search(pat, t)
        if m:
            groups   = [g for g in m.groups() if g]
            activity = " ".join(groups).strip()
            label    = f"User habit: {activity}"
            if time_hint and time_hint not in label:
                label += f" (at {time_hint})"
            return label, time_hint

    return f"User habit: {text.strip()}", time_hint