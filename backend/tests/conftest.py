"""conftest.py — Shared fixtures for Nexus backend tests."""
import os
import sys
import pytest
import asyncio

# Ensure backend is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_database")
os.environ.setdefault("ENCRYPTION_KEY", "glU4FEqhtSIFpB0ivioa8_V6GApBm1e-KNCSj_GUJDI=")
os.environ.setdefault("SUPER_ADMIN_EMAIL", "kelliott@urtech.org")

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def api_url():
    return os.environ.get("API_URL", "https://ai-chat-recovery.preview.emergentagent.com")

@pytest.fixture(scope="session")
def admin_credentials():
    return {
        "email": os.environ.get("ADMIN_EMAIL", "kelliott@urtech.org"),
        "password": os.environ.get("ADMIN_PASSWORD", "test"),
    }

@pytest.fixture(scope="session")
def admin_token(api_url, admin_credentials):
    import requests
    resp = requests.post(f"{api_url}/api/auth/login", json=admin_credentials)
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json().get("session_token")

@pytest.fixture(scope="session")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}
