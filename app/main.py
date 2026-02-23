from assistant_service import run_assistant

while True:
    text=input("You: ")
    print(run_assistant(text))