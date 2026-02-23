from .memory import MemoryManager

class ContextBuilder:
    def __init__(self):
        self.memory = MemoryManager()

    def get_context(self, user_input, intent):
        results = self.memory.retrieve_memory(user_input)

        if not results or len(results) == 0:
            return None

        # flatten chroma result safely
        docs = results[0]
        return "\n".join(docs) if docs else None