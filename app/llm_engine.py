import os
import anthropic
from dotenv import load_dotenv

load_dotenv()


class LLMEngine:

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            api_key = api_key.strip()  
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
        self.client = anthropic.Anthropic(api_key=api_key)

    def generate_response(self, user_input: str, intent: str = None, context: str = None) -> str:
        system_prompt = (
            "You are a smart, concise personal assistant with memory. "
            "You remember the user's preferences and habits across conversations. "
            "Do not repeat the user's message. "
            "Give clear, short, helpful responses. "
            "If you have context about the user's preferences or habits, use it naturally. "
            "Never say 'based on context' — just respond as if you genuinely know them."
        )

        if context:
            system_prompt += f"\n\n--- What you know about this user ---\n{context}\n---"

        response = self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=system_prompt,
            messages=[{"role": "user", "content": user_input}],
        )

        return response.content[0].text.strip()