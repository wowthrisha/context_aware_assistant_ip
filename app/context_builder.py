"""
Builds a rich context string for the LLM by pulling from all three
memory collections and formatting them clearly.
"""

from .memory import MemoryManager


class ContextBuilder:

    def __init__(self, memory: MemoryManager):
        # Accept shared MemoryManager so we don't load the model twice
        self.memory = memory

    def get_context(self, user_input: str, intent: str) -> str | None:
        sections = []

        # ── Always pull preferences ────────────────────────────────────────────
        prefs = self.memory.retrieve_preferences(user_input)
        if prefs:
            sections.append("User preferences:\n" + "\n".join(f"  • {p}" for p in prefs))

        # ── Pull habits (especially useful for recall / general chat) ──────────
        habits = self.memory.retrieve_habits(user_input)
        if habits:
            sections.append("User habits:\n" + "\n".join(f"  • {h}" for h in habits))

        # ── Pull general memories for recall questions ─────────────────────────
        if intent in ("recall_memory", "general_chat"):
            general = self.memory.retrieve(user_input, memory_type="general")
            if general:
                sections.append("Other things I know about the user:\n" + "\n".join(f"  • {g}" for g in general))

        if not sections:
            return None

        return "\n\n".join(sections)