import re
from datetime import datetime, timedelta


def _clean_time_text(text: str) -> str:
    text = re.sub(r'(\d)\s+p[,.]?\s*(?=\s|$)', r'\1pm ', text, flags=re.IGNORECASE)
    text = re.sub(r'(\d)\s+a[,.]?\s*(?=\s|$)', r'\1am ', text, flags=re.IGNORECASE)
    text = re.sub(r'\bp\.m\.?\b', 'pm', text, flags=re.IGNORECASE)
    text = re.sub(r'\ba\.m\.?\b', 'am', text, flags=re.IGNORECASE)
    return text


def parse_time(text: str):
    text = _clean_time_text(text)
    print(f"[TimeParser] Cleaned: '{text}'")
    now = datetime.now()

    # "in X minutes/hours/days"
    rel = re.search(r'\bin\s+(\d+)\s*(second|minute|hour|day|min|hr|sec)s?\b', text, re.IGNORECASE)
    if rel:
        val = int(rel.group(1))
        unit = rel.group(2).lower()
        if unit.startswith('s'):
            return now + timedelta(seconds=val)
        elif unit.startswith('m') or unit == 'min':
            return now + timedelta(minutes=val)
        elif unit.startswith('h') or unit == 'hr':
            return now + timedelta(hours=val)
        elif unit.startswith('d'):
            return now + timedelta(days=val)

    # "at 6pm", "at 6:30pm", "at 6:30 pm"
    at = re.search(r'\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b', text, re.IGNORECASE)
    if at:
        hours = int(at.group(1))
        mins  = int(at.group(2) or 0)
        mer   = at.group(3).lower()
        if mer == 'pm' and hours != 12:
            hours += 12
        if mer == 'am' and hours == 12:
            hours = 0

        has_tomorrow = bool(re.search(r'\btomorrow\b', text, re.IGNORECASE))
        has_today    = bool(re.search(r'\btoday\b|\btonight\b', text, re.IGNORECASE))

        t = now.replace(hour=hours, minute=mins, second=0, microsecond=0)
        if has_tomorrow:
            t += timedelta(days=1)
        elif t <= now and not has_today:
            t += timedelta(days=1)
        return t

    # "at 6" with no am/pm — assume future (pm if hour < 7, else nearest)
    at_bare = re.search(r'\bat\s+(\d{1,2})(?::(\d{2}))?\b', text, re.IGNORECASE)
    if at_bare:
        hours = int(at_bare.group(1))
        mins  = int(at_bare.group(2) or 0)

        # assume pm for hours 1-7, else take as-is
        if 1 <= hours <= 7:
            hours += 12

        has_tomorrow = bool(re.search(r'\btomorrow\b', text, re.IGNORECASE))
        has_today    = bool(re.search(r'\btoday\b|\btonight\b', text, re.IGNORECASE))

        t = now.replace(hour=hours, minute=mins, second=0, microsecond=0)
        if has_tomorrow:
            t += timedelta(days=1)
        elif t <= now and not has_today:
            t += timedelta(days=1)
        return t

    # "tomorrow" alone → tomorrow 9am
    if re.search(r'\btomorrow\b', text, re.IGNORECASE):
        t = now.replace(hour=9, minute=0, second=0, microsecond=0)
        return t + timedelta(days=1)

    return None


def extract_task(text: str) -> str:
    t = text
    t = re.sub(r'\b(remind me to|remind me|set a reminder to|set a reminder for|set reminder|please remind me to|can you remind me to)\b', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\bin \d+ (second|minute|hour|day|week)s?\b', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\bat \d{1,2}(:\d{2})?\s*(am|pm)?\b', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\b\d{1,2}\s*p[,.]?\b', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\b(tomorrow|today|tonight|this evening|this morning|next week)\b', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s{2,}', ' ', t).strip(' .,;-')
    return t if t else text
