"""
CLI runner — shows intent, memory saves, and proactive suggestions.
Run with: python main.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app.assistant_service import run_assistant

print("=" * 55)
print("  🤖  Context-Aware Assistant  (memory enabled)")
print("  Type 'quit' to exit | 'memory' to inspect stored data")
print("=" * 55)
print()

while True:
    try:
        user_input = input("You: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye!")
        break

    if not user_input:
        continue

    if user_input.lower() in ("quit", "exit", "bye"):
        print("Assistant: Goodbye!")
        break

    # Quick inspect command
    if user_input.lower() == "memory":
        from app.assistant_service import memory
        for mtype in ("preference", "habit", "general"):
            entries = memory.get_all(mtype)
            print(f"\n── {mtype.upper()} ({len(entries)}) ──")
            for e in entries:
                print(f"  • {e['text']}")
        print()
        continue

    result = run_assistant(user_input)

    print(f"\nAssistant: {result['reply']}")

    # Show what was saved
    if result.get("memory_saved"):
        ms = result["memory_saved"]
        print(f"  [💾 saved {ms['type']}: \"{ms['text'][:60]}...\"]" if len(ms['text'])>60 else f"  [💾 saved {ms['type']}: \"{ms['text']}\"]")

    # Show proactive suggestion
    if result.get("proactive_suggestion"):
        ps = result["proactive_suggestion"]
        print(f"\n  💡 {ps['message']}")
        ans = input("     Set reminder? (y/n): ").strip().lower()
        if ans == 'y':
            reminder_msg = f"Remind me to {ps['activity']} at {ps['time_hint']}"
            r = run_assistant(reminder_msg)
            print(f"  → {r['reply']}")

    print(f"  [intent: {result['intent']}]\n")