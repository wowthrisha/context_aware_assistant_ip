"""
Extracts clean, storable facts from user messages.

Examples
--------
"I hate mornings"            → ("I hate mornings", "negative")
"I prefer tea over coffee"   → ("prefers tea over coffee", "positive")
"I always work out at 7am"   → ("works out every day at 7am", time_hint="7am")
"""

import re


# ── Preference extraction ──────────────────────────────────────────────────────

_POSITIVE_PATTERNS = [
    r"i (love|like|enjoy|prefer|adore) (.+)",
    r"my favou?rite (.+?) is (.+)",
    r"i'?m a (big )?fan of (.+)",
]

_NEGATIVE_PATTERNS = [
    r"i (hate|dislike|can'?t stand|avoid|detest|don'?t like) (.+)",
]


def extract_preference(text: str, sentiment: str) -> str:
    """
    Returns a clean sentence to store, e.g. 'User prefers tea over coffee'.
    Falls back to the original text if no pattern matches.
    """
    t = text.lower().strip().rstrip(".")

    if sentiment == "positive":
        for pat in _POSITIVE_PATTERNS:
            m = re.search(pat, t)
            if m:
                groups = [g for g in m.groups() if g]
                phrase = " ".join(groups[-2:]) if len(groups) >= 2 else groups[-1]
                return f"User likes/prefers: {phrase.strip()}"

    if sentiment == "negative":
        for pat in _NEGATIVE_PATTERNS:
            m = re.search(pat, t)
            if m:
                groups = [g for g in m.groups() if g]
                phrase = groups[-1] if groups else t
                return f"User dislikes: {phrase.strip()}"

    # fallback — store as-is
    return text.strip()


# ── Habit extraction ───────────────────────────────────────────────────────────

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
]


def extract_habit(text: str) -> tuple[str, str | None]:
    """
    Returns (clean_habit_string, time_hint_or_None).

    Example:
        "I always work out at 7am" → ("User habit: works out at 7am", "7am")
    """
    t = text.lower().strip().rstrip(".")

    # extract time hint
    time_match = _TIME_HINT_PATTERN.search(t)
    time_hint = time_match.group(0).strip() if time_match else None

    for pat in _HABIT_PATTERNS:
        m = re.search(pat, t)
        if m:
            groups = [g for g in m.groups() if g]
            activity = " ".join(groups).strip()
            label = f"User habit: {activity}"
            if time_hint and time_hint not in label:
                label += f" (at {time_hint})"
            return label, time_hint

    return f"User habit: {text.strip()}", time_hint