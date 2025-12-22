#!/usr/bin/env python3
"""
Test script to verify frontend-backend connectivity
"""
import requests
import time
import json

BASE_URL = "http://localhost:8000"

print("=" * 60)
print("🔍 ExamEase Frontend-Backend Connectivity Test")
print("=" * 60)

tests = [
    ("Health Check", "GET", "/health", None),
    ("Home", "GET", "/", None),
]

print("\n⏳ Waiting for backend to be ready...")
time.sleep(1)

passed = 0
failed = 0

for test_name, method, endpoint, data in tests:
    try:
        url = f"{BASE_URL}{endpoint}"
        print(f"\n📍 Testing: {test_name}")
        print(f"   URL: {url}")
        
        if method == "GET":
            response = requests.get(url, timeout=5)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=5)
        
        if response.status_code == 200:
            print(f"   ✅ SUCCESS ({response.status_code})")
            print(f"   Response: {json.dumps(response.json(), indent=2)[:200]}")
            passed += 1
        else:
            print(f"   ❌ FAILED ({response.status_code})")
            print(f"   Response: {response.text[:200]}")
            failed += 1
    except Exception as e:
        print(f"   ❌ ERROR: {str(e)}")
        failed += 1

print("\n" + "=" * 60)
print(f"✅ Passed: {passed} | ❌ Failed: {failed}")
print("=" * 60)

if failed == 0:
    print("\n🎉 All tests passed! Frontend can connect to backend.")
    print(f"   Backend URL: {BASE_URL}")
    print(f"   Frontend should be pointing to: {BASE_URL}")
else:
    print("\n⚠️ Some tests failed. Check if backend is running on port 8000")
