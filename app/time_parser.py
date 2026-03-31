"""
time_parser.py — Hybrid NLP + Rule-based time parsing.

ML additions:
  - spaCy NER for DATE/TIME entity extraction (handles complex expressions)
  - Falls back to regex for simple patterns (faster)

Handles:
  - "in 30 minutes", "in one hour", "in a minute", "in an hour"
  - "at 3pm", "at 6:30 am", "at 6 p,"
  - "tomorrow at 9am", "tmrw at 6pm"
  - "next friday evening", "after lunch" (via spaCy)
  - "every day at 7am", "every Monday" (recurrence)
  - Word numbers: one, two, three ... sixty
"""

import re
from datetime import datetime, timedelta

# ── spaCy NER (lazy load) ──────────────────────────────────────────────────────
_nlp = None

def _get_nlp():
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load("en_core_web_sm")
            print("[TimeParser] spaCy model loaded")
        except Exception as e:
            print(f"[TimeParser] spaCy not available: {e} — using regex fallback")
            _nlp = False
    return _nlp if _nlp is not False else None


# ── Word number map ───────────────────────────────────────────────────────────

_WORD_NUMBERS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "eleven": "11", "twelve": "12", "thirteen": "13", "fourteen": "14",
    "fifteen": "15", "sixteen": "16", "seventeen": "17", "eighteen": "18",
    "nineteen": "19", "twenty": "20", "thirty": "30", "forty": "40",
    "forty-five": "45", "fifty": "50", "sixty": "60",
}

# Named time periods → hour
_PERIOD_HOURS = {
    "morning": 8, "breakfast": 8,
    "noon": 12, "lunch": 12, "midday": 12,
    "afternoon": 14,
    "evening": 18, "dinner": 18,
    "night": 21, "bedtime": 22,
    "midnight": 0,
}


def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'\bin an?\s+(second|minute|hour|day)s?\b', r'in 1 \1', text)
    for word, digit in _WORD_NUMBERS.items():
        text = re.sub(rf'\b{word}\b', digit, text)
    text = re.sub(r'\b(tmrw|tmr|tom|tomoro|tommorrow)\b', 'tomorrow', text)
    text = re.sub(r'(\d)\s+p[,.]?\s*(?=\s|$)', r'\1pm ', text)
    text = re.sub(r'(\d)\s+a[,.]?\s*(?=\s|$)', r'\1am ', text)
    text = re.sub(r'\bp\.m\.?\b', 'pm', text)
    text = re.sub(r'\ba\.m\.?\b', 'am', text)
    return text


def _apply_day_offset(now: datetime, h: int, m: int, text: str) -> datetime:
    has_tomorrow = bool(re.search(r'\btomorrow\b', text))
    has_today    = bool(re.search(r'\btoday\b|\btonight\b', text))
    t = now.replace(hour=h, minute=m, second=0, microsecond=0)
    grace = timedelta(minutes=15)
    if has_tomorrow:
        t += timedelta(days=1)
    elif t <= now and not has_today:
        if (now - t) <= grace:
            pass
        else:
            t += timedelta(days=1)
    return t


def _regex_parse(text: str, now: datetime) -> datetime | None:
    """Fast regex-based parsing for common patterns."""
    # "in X minutes/hours/days/seconds"
    rel = re.search(r'\bin\s+(\d+)\s*(second|minute|hour|day|min|hr|sec)s?\b', text, re.IGNORECASE)
    if rel:
        val, unit = int(rel.group(1)), rel.group(2).lower()
        if unit.startswith('s'):                    return now + timedelta(seconds=val)
        elif unit.startswith('m') or unit == 'min': return now + timedelta(minutes=val)
        elif unit.startswith('h') or unit == 'hr':  return now + timedelta(hours=val)
        elif unit.startswith('d'):                  return now + timedelta(days=val)

    # "at 6pm" / "at 6:30am"
    at = re.search(r'\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b', text, re.IGNORECASE)
    if at:
        h, m, mer = int(at.group(1)), int(at.group(2) or 0), at.group(3).lower()
        if mer == 'pm' and h != 12: h += 12
        if mer == 'am' and h == 12: h = 0
        return _apply_day_offset(now, h, m, text)

    # "at 6" no am/pm
    at_bare = re.search(r'\bat\s+(\d{1,2})(?::(\d{2}))?\b', text, re.IGNORECASE)
    if at_bare:
        h, m = int(at_bare.group(1)), int(at_bare.group(2) or 0)
        if 1 <= h <= 7: h += 12
        return _apply_day_offset(now, h, m, text)

    # Named periods: "in the morning", "after lunch", "this evening"
    for period, hour in _PERIOD_HOURS.items():
        if re.search(rf'\b{period}\b', text, re.IGNORECASE):
            t = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            has_tomorrow = bool(re.search(r'\btomorrow\b', text))
            if has_tomorrow:
                t += timedelta(days=1)
            elif t <= now:
                t += timedelta(days=1)
            return t

    # "tomorrow" alone → 9am tomorrow
    if re.search(r'\btomorrow\b', text):
        return now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)

    return None


def _spacy_parse(text: str, now: datetime) -> datetime | None:
    """
    Use spaCy NER to extract DATE/TIME entities.
    Handles: "next friday", "next week", "in two days", etc.
    """
    nlp = _get_nlp()
    if nlp is None:
        return None

    try:
        doc = nlp(text)
        for ent in doc.ents:
            if ent.label_ not in ("DATE", "TIME"):
                continue
            ent_text = ent.text.lower().strip()

            # "next monday/tuesday/..."
            days = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
            for i, day in enumerate(days):
                if day in ent_text or day[:3] in ent_text:
                    days_ahead = (i - now.weekday() + 7) % 7 or 7
                    t = now + timedelta(days=days_ahead)
                    return t.replace(hour=9, minute=0, second=0, microsecond=0)

            # "next week"
            if "next week" in ent_text:
                return now + timedelta(weeks=1)

            # "in two days", "in 3 days"
            m = re.search(r'in (\d+) days?', ent_text)
            if m:
                return now + timedelta(days=int(m.group(1)))

            # "this weekend"
            if "weekend" in ent_text:
                days_until_sat = (5 - now.weekday()) % 7 or 7
                t = now + timedelta(days=days_until_sat)
                return t.replace(hour=9, minute=0, second=0, microsecond=0)

    except Exception as e:
        print(f"[TimeParser] spaCy parse error: {e}")

    return None


def parse_time(text: str) -> datetime | None:
    """
    Hybrid parser: regex first (fast), then spaCy NER (complex expressions).
    """
    normalized = _normalize(text)
    print(f"[TimeParser] Normalized: '{normalized}'")
    now = datetime.now()

    # 1. Try fast regex
    result = _regex_parse(normalized, now)
    if result:
        return result

    # 2. Try spaCy NER for complex expressions
    result = _spacy_parse(text, now)
    if result:
        print(f"[TimeParser] spaCy extracted: {result}")
        return result

    return None


# ── Recurrence ────────────────────────────────────────────────────────────────

_RECURRENCE_PATTERNS = {
    r"\bevery day\b|\bdaily\b|\beveryday\b":  "daily",
    r"\bevery morning\b":                     "daily_morning",
    r"\bevery evening\b":                     "daily_evening",
    r"\bevery night\b":                       "daily_night",
    r"\bevery (monday|mon)\b":                "weekly_monday",
    r"\bevery (tuesday|tue)\b":               "weekly_tuesday",
    r"\bevery (wednesday|wed)\b":             "weekly_wednesday",
    r"\bevery (thursday|thu)\b":              "weekly_thursday",
    r"\bevery (friday|fri)\b":                "weekly_friday",
    r"\bevery (saturday|sat)\b":              "weekly_saturday",
    r"\bevery (sunday|sun)\b":                "weekly_sunday",
    r"\bevery week(ly)?\b|\bweekly\b":        "weekly",
    r"\bevery hour(ly)?\b|\bhourly\b":        "hourly",
    r"\bevery (\d+) minutes?\b":              "interval_minutes",
    r"\bevery (\d+) hours?\b":                "interval_hours",
}


def detect_recurrence(text: str) -> dict | None:
    t = _normalize(text)
    for pattern, rec_type in _RECURRENCE_PATTERNS.items():
        match = re.search(pattern, t)
        if match:
            interval = None
            if "interval" in rec_type and match.lastindex:
                try: interval = int(match.group(1))
                except: pass
            return {"type": rec_type, "interval": interval}
    return None


# ── Task extractor ────────────────────────────────────────────────────────────

def extract_task(text: str) -> str:
    t = _normalize(text)
    t = re.sub(
        r'\b(remind me to|remind me|set a reminder to|set a reminder for|'
        r'set reminder|please remind me to|can you remind me to|'
        r'give (a|me a) reminder to|give a reminder to|give a reminder)\b', '', t)
    t = re.sub(
        r'\bevery\s+(day|morning|evening|night|hour|week|'
        r'monday|tuesday|wednesday|thursday|friday|saturday|sunday|'
        r'mon|tue|wed|thu|fri|sat|sun)\b', '', t)
    t = re.sub(r'\bevery\s+\d+\s+(minutes?|hours?)\b', '', t)
    t = re.sub(r'\b(daily|weekly|hourly|everyday)\b', '', t)
    t = re.sub(r'\bin \d+ (second|minute|hour|day|week)s?\b', '', t)
    t = re.sub(r'\bin \d+\b', '', t)
    t = re.sub(r'\bat \d{1,2}(:\d{2})?\s*(am|pm)?\b', '', t)
    t = re.sub(r'\b\d{1,2}\s*(am|pm)\b', '', t)
    t = re.sub(r'\b\d{1,2}\s*p[,.]?\b', '', t)
    t = re.sub(
        r'\b(tomorrow|today|tonight|this evening|this morning|next week|'
        r'morning|evening|night|afternoon|noon|lunch|dinner|breakfast)\b', '', t)
    t = re.sub(r'\s{2,}', ' ', t).strip(' .,;-')
    return t if len(t) > 2 else ""
