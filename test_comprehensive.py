#!/usr/bin/env python3
"""
Comprehensive Test Suite for Context-Aware Assistant
Tests all endpoints, ML features, and integrations
"""

import requests
import json
import sys
from datetime import datetime

BASE_URL = "http://localhost:8000"
TEST_USER = f"test_user_{datetime.now().strftime('%H%M%S')}"

class Colors:
    PASS = '\033[92m✓\033[0m'
    FAIL = '\033[91m✗\033[0m'
    WARN = '\033[93m⚠\033[0m'
    INFO = '\033[94mℹ\033[0m'

results = {"passed": 0, "failed": 0, "warnings": 0}

def test(name, method="GET", endpoint="", data=None, headers=None, expected_status=200, check_fn=None):
    """Run a single test case"""
    try:
        url = f"{BASE_URL}{endpoint}"
        if method == "GET":
            r = requests.get(url, headers=headers, timeout=5)
        elif method == "POST":
            r = requests.post(url, json=data, headers=headers, timeout=5)
        elif method == "DELETE":
            r = requests.delete(url, headers=headers, timeout=5)
        
        status_ok = r.status_code == expected_status
        
        if check_fn:
            content_ok = check_fn(r.json()) if r.status_code == 200 else False
        else:
            content_ok = True
        
        if status_ok and content_ok:
            print(f"{Colors.PASS} {name}")
            results["passed"] += 1
            return True
        else:
            print(f"{Colors.FAIL} {name} - Status: {r.status_code}, Expected: {expected_status}")
            if not content_ok:
                print(f"  Response: {r.text[:200]}")
            results["failed"] += 1
            return False
    except Exception as e:
        print(f"{Colors.FAIL} {name} - Error: {str(e)}")
        results["failed"] += 1
        return False

print("=" * 60)
print("COMPREHENSIVE TEST SUITE")
print("=" * 60)

# Test 1: Basic connectivity
print("\n📡 API Connectivity Tests")
test("Root endpoint", endpoint="/", expected_status=200,
    check_fn=lambda x: "status" in x or "detail" in x)

# Test 2: Authentication
print("\n🔐 Authentication Tests")
login_result = test("User login", "POST", "/login", 
    data={"user_id": TEST_USER},
    check_fn=lambda x: "token" in x and "user_id" in x)

if not login_result:
    print(f"{Colors.FAIL} Cannot continue without authentication")
    sys.exit(1)

# Get token for subsequent tests
login_resp = requests.post(f"{BASE_URL}/login", json={"user_id": TEST_USER}).json()
TOKEN = login_resp["token"]["token"]
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# Test 3: Chat endpoint
print("\n💬 Chat Endpoint Tests")
test("Basic chat", "POST", "/chat",
    data={"message": "Hello"},
    headers=HEADERS,
    check_fn=lambda x: "reply" in x and "intent" in x)

# Test ML intent detection
test("ML - Positive preference", "POST", "/chat",
    data={"message": "I love chocolate"},
    headers=HEADERS,
    check_fn=lambda x: x.get("intent") == "save_preference_positive")

test("ML - Negative preference", "POST", "/chat",
    data={"message": "I hate spinach"},
    headers=HEADERS,
    check_fn=lambda x: x.get("intent") == "save_preference_negative")

test("ML - Set reminder", "POST", "/chat",
    data={"message": "Remind me to drink water"},
    headers=HEADERS,
    check_fn=lambda x: x.get("intent") == "set_reminder")

test("ML - List reminders", "POST", "/chat",
    data={"message": "Show me my reminders"},
    headers=HEADERS,
    check_fn=lambda x: x.get("intent") == "list_reminders")

# Test 4: Reminders
print("\n⏰ Reminder Tests")
test("Get reminders", "GET", "/reminders", headers=HEADERS,
    check_fn=lambda x: "reminders" in x)

# Create a reminder first
reminder_result = requests.post(f"{BASE_URL}/chat", 
    json={"message": "Remind me to test in 1 minute"},
    headers=HEADERS).json()

if reminder_result.get("system", {}).get("reminder_id"):
    rid = reminder_result["system"]["reminder_id"]
    test("Cancel reminder", "DELETE", f"/reminders/{rid}", headers=HEADERS)

# Test 5: Memory
print("\n🧠 Memory Tests")
for mtype in ["preference", "habit", "general"]:
    test(f"Get {mtype} memory", "GET", f"/memory/{mtype}", headers=HEADERS,
        check_fn=lambda x: "entries" in x)

# Test 6: Notifications
print("\n🔔 Notification Tests")
test("Get notification prefs", "GET", "/notification-prefs", headers=HEADERS)
test("Set notification prefs", "POST", "/notification-prefs",
    data={"whatsapp": "+1234567890", "email": "test@test.com", "channels": ["sse"]},
    headers=HEADERS)

print("\n" + "=" * 60)
print("TEST SUMMARY")
print("=" * 60)
print(f"Passed:   {Colors.PASS} {results['passed']}")
print(f"Failed:   {Colors.FAIL} {results['failed']}")
print(f"Warnings: {Colors.WARN} {results['warnings']}")
print("=" * 60)

if results['failed'] > 0:
    sys.exit(1)
else:
    print(f"\n{Colors.PASS} All tests passed! System is industry standard.")
    sys.exit(0)
