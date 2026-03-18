import requests
import json
import threading
import time

URL = "http://127.0.0.1:8000/reminders/stream?user_id=ridhu"

def listen():
    print(f"👂 Listening to {URL}...")
    try:
        response = requests.get(URL, stream=True, timeout=30)
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                print(f"[{time.strftime('%H:%M:%S')}] RECEIVED: {decoded_line}")
    except Exception as e:
        print(f"❌ Error: {e}")

# Start listener in thread
t = threading.Thread(target=listen)
t.daemon = True
t.start()

# Give it time to connect
time.sleep(2)

# Trigger a reminder via chat
CHAT_URL = "http://127.0.0.1:8000/chat"
print("📨 Sending chat command to trigger reminder...")
try:
    resp = requests.post(CHAT_URL, 
        params={"user_id": "ridhu"}, # Note: depends on how auth works
        json={"message": "remind me in 3 seconds to test sse from python"}
    )
    print(f"📨 Response code: {resp.status_code}")
    print(f"📨 Response: {resp.json()}")
except Exception as e:
    print(f"📨 Send Error: {e}")

# Wait for reminder
print("⏳ Waiting for reminder...")
time.sleep(15)
print("🏁 Test finished.")
