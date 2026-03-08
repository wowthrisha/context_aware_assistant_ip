"""
Looks at stored habits and suggests reminders when the user might benefit.

Called after every message so the assistant can proactively say things like:
  "You usually work out at 7am — want me to set a reminder for tomorrow?"
"""

import re
from datetime import datetime, timedelta


# Time keywords → approximate hour ranges
_TIME_RANGES = {
    "morning":   (5,  10),
    "noon":      (11, 13),
    "afternoon": (12, 17),
    "evening":   (17, 21),
    "night":     (20, 24),
}

_HOUR_PATTERN = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", re.IGNORECASE)


def _parse_time_hint(hint: str) -> datetime | None:
    """Convert a time hint string into a future datetime (today or tomorrow)."""
    if not hint:
        return None

    hint = hint.strip().lower()
    now  = datetime.now()

    # "7am", "6:30pm", etc.
    m = _HOUR_PATTERN.match(hint)
    if m:
        h   = int(m.group(1))
        min_ = int(m.group(2) or 0)
        mer  = (m.group(3) or "").lower()
        if mer == "pm" and h != 12:
            h += 12
        if mer == "am" and h == 12:
            h = 0
        if 1 <= h <= 7 and not mer:   # assume pm for ambiguous small hours
            h += 12

        t = now.replace(hour=h, minute=min_, second=0, microsecond=0)
        if t <= now:
            t += timedelta(days=1)
        return t

    # Named period
    for period, (start, _) in _TIME_RANGES.items():
        if period in hint:
            t = now.replace(hour=start, minute=0, second=0, microsecond=0)
            if t <= now:
                t += timedelta(days=1)
            return t

    return None


def suggest_from_habits(habits: list[str]) -> list[dict]:
    """
    Given a list of stored habit strings, return a list of suggestions:
      [{"habit": "...", "suggestion": "...", "time": datetime_or_None}]
    """
    suggestions = []
    seen = set()

    for habit in habits:
        # Extract time hint from the stored habit string
        time_hint_match = re.search(
            r"\(at (.+?)\)|at (\d{1,2}(?::\d{2})?\s*(?:am|pm)?)|"
            r"(morning|evening|night|afternoon)",
            habit,
            re.IGNORECASE,
        )
        if not time_hint_match:
            continue

        raw_hint = next((g for g in time_hint_match.groups() if g), None)
        if not raw_hint or raw_hint in seen:
            continue
        seen.add(raw_hint)

        parsed_time = _parse_time_hint(raw_hint)

        # Build a friendly suggestion
        clean_habit = re.sub(r"User habit:\s*", "", habit).strip()
        clean_habit = re.sub(r"\(at .+?\)", "", clean_habit).strip()

        suggestions.append({
            "habit":      habit,
            "activity":   clean_habit,
            "time_hint":  raw_hint,
            "time":       parsed_time,
            "suggestion": (
                f"You usually {clean_habit}. "
                f"Want me to set a reminder for {raw_hint}?"
            ),
        })

    return suggestions