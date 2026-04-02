#!/usr/bin/env python3
"""Nexus Cloud — Staging Smoke Test Suite

Run after deployment to verify critical paths work:
  python smoke_test.py [BASE_URL]

Environment variables:
  SMOKE_TEST_URL: Base URL (default: http://localhost:8080)
  TEST_ADMIN_EMAIL: Admin email for login test
  TEST_ADMIN_PASSWORD: Admin password for login test

Exit codes: 0 = all passed, 1 = failures detected
"""
import os
import sys
import time
import requests

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SMOKE_TEST_URL", "http://localhost:8080")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = os.environ.get("TEST_ADMIN_EMAIL", "admin@test.local")
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "test")

results = []


def check(name, fn):
    """Run a smoke test and record result."""
    try:
        fn()
        results.append((name, "PASS", ""))
        print(f"  [PASS] {name}")
    except Exception as e:
        results.append((name, "FAIL", str(e)[:200]))
        print(f"  [FAIL] {name}: {e}")


def test_health():
    r = requests.get(f"{API}/health", timeout=10)
    assert r.status_code == 200, f"Health returned {r.status_code}"


def test_health_startup():
    r = requests.get(f"{API}/health/startup", timeout=10)
    assert r.status_code == 200, f"Startup health returned {r.status_code}"


def test_auth_login():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=10)
    assert r.status_code == 200, f"Login returned {r.status_code}: {r.text[:100]}"
    data = r.json()
    assert "session_token" in data or "user_id" in data, "No session_token or user_id in response"


def test_auth_me():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=10)
    if r.status_code != 200:
        raise Exception("Login failed — cannot test /auth/me")
    token = r.json().get("session_token", "")
    r2 = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=10)
    assert r2.status_code == 200, f"/auth/me returned {r2.status_code}"


def test_ai_models():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=10)
    token = r.json().get("session_token", "") if r.status_code == 200 else ""
    r2 = requests.get(f"{API}/ai-models", headers={"Authorization": f"Bearer {token}"}, timeout=10)
    assert r2.status_code == 200, f"/ai-models returned {r2.status_code}"


def test_workspaces():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=10)
    token = r.json().get("session_token", "") if r.status_code == 200 else ""
    r2 = requests.get(f"{API}/workspaces", headers={"Authorization": f"Bearer {token}"}, timeout=10)
    assert r2.status_code == 200, f"/workspaces returned {r2.status_code}"


def test_media_config():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=10)
    token = r.json().get("session_token", "") if r.status_code == 200 else ""
    r2 = requests.get(f"{API}/media/config", headers={"Authorization": f"Bearer {token}"}, timeout=10)
    assert r2.status_code == 200, f"/media/config returned {r2.status_code}"
    data = r2.json()
    features = data.get("features", {})
    assert features.get("video_generation", {}).get("enabled"), "video_generation not enabled"
    assert features.get("music_generation", {}).get("enabled"), "music_generation not enabled"


def test_no_emergent_references():
    """Verify auth/session returns 410 (Emergent bridge removed)."""
    r = requests.post(f"{API}/auth/session", json={"session_id": "test"}, timeout=10)
    assert r.status_code == 410, f"/auth/session should return 410, got {r.status_code}"


def test_platform_capabilities():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=10)
    token = r.json().get("session_token", "") if r.status_code == 200 else ""
    r2 = requests.get(f"{API}/platform/capabilities", headers={"Authorization": f"Bearer {token}"}, timeout=10)
    assert r2.status_code == 200, f"/platform/capabilities returned {r2.status_code}"


if __name__ == "__main__":
    print(f"\nNexus Cloud Smoke Tests — {BASE_URL}")
    print(f"{'=' * 50}\n")

    start = time.time()

    check("Health endpoint", test_health)
    check("Startup health", test_health_startup)
    check("Auth login", test_auth_login)
    check("Auth /me", test_auth_me)
    check("AI models", test_ai_models)
    check("Workspaces", test_workspaces)
    check("Media config (features enabled)", test_media_config)
    check("Emergent bridge removed (410)", test_no_emergent_references)
    check("Platform capabilities", test_platform_capabilities)

    duration = time.time() - start
    passed = sum(1 for _, s, _ in results if s == "PASS")
    failed = sum(1 for _, s, _ in results if s == "FAIL")

    print(f"\n{'=' * 50}")
    print(f"Results: {passed} passed, {failed} failed ({duration:.1f}s)")

    if failed > 0:
        print("\nFailed tests:")
        for name, status, err in results:
            if status == "FAIL":
                print(f"  - {name}: {err}")
        sys.exit(1)
    else:
        print("\nAll smoke tests passed!")
        sys.exit(0)
