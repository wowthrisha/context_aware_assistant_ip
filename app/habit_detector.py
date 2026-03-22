"""
habit_detector.py — Detects habits from repeated reminder patterns.

If a user sets 3+ reminders at the same hour for similar tasks,
we surface a suggestion to make it recurring.
"""

import re
import logging
from collections import defaultdict
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def _extract_hour(trigger_at: str) -> Optional[int]:
    """Extract the hour from an ISO datetime string."""
    try:
        return datetime.fromisoformat(trigger_at).hour
    except Exception:
        return None


def _normalize_task(task: str) -> str:
    """Simplify task name for comparison."""
    return re.sub(r'\s+', ' ', task.lower().strip())


def detect_habit_pattern(reminders: list[dict]) -> Optional[dict]:
    """
    Analyse a user's reminder history.
    Returns a suggestion dict if a habit pattern is detected, else None.

    A pattern = same hour + similar task appearing 3+ times.

    Returns:
        {
            "task":        str,
            "hour":        int,
            "count":       int,
            "friendly_time": str,   e.g. "7:00 AM"
            "message":     str,     the suggestion text
        }
    """
    # Group by hour
    hour_task_map: dict[int, list[str]] = defaultdict(list)

    for r in reminders:
        hour = _extract_hour(r.get("trigger_at", ""))
        task = _normalize_task(r.get("message", ""))
        if hour is not None and task:
            hour_task_map[hour].append(task)

    for hour, tasks in hour_task_map.items():
        if len(tasks) < 3:
            continue

        # Find the most common task at this hour
        task_counts: dict[str, int] = defaultdict(int)
        for t in tasks:
            task_counts[t] += 1

        top_task, count = max(task_counts.items(), key=lambda x: x[1])

        if count >= 3:
            # Format friendly time
            dt = datetime.now().replace(hour=hour, minute=0)
            try:
                friendly = dt.strftime("%-I:%M %p")
            except ValueError:
                friendly = dt.strftime("%I:%M %p").lstrip("0")

            return {
                "task":          top_task,
                "hour":          hour,
                "count":         count,
                "friendly_time": friendly,
                "message": (
                    f"You've set a {friendly} reminder for \"{top_task}\" "
                    f"{count} times. Want to make it recurring every day?"
                ),
            }

    return None