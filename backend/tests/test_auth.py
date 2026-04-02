"""Core API regression tests — covers critical paths across all features."""
import pytest
import httpx
import os

BASE = os.environ.get("TEST_API_URL", "http://localhost:8001/api")

@pytest.fixture(scope="module")
def client():
    return httpx.Client(base_url=BASE, timeout=15)

@pytest.fixture(scope="module")
def auth_client():
    """Client with auth session — cookies auto-managed."""
    import uuid
    c = httpx.Client(base_url=BASE, timeout=15, cookies=httpx.Cookies())
    email = f"coretest_{uuid.uuid4().hex[:6]}@test.com"
    c.post("/auth/register", json={"email": email, "password": "TestPass123!", "name": "Core Tester"})
    r = c.post("/auth/login", json={"email": email, "password": "TestPass123!"})
    # Manually extract and set cookie from response
    for cookie_name, cookie_value in r.cookies.items():
        c.cookies.set(cookie_name, cookie_value)
    return c

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "healthy"
    assert "instance_id" in d

def test_register_weak_password(client):
    r = client.post("/auth/register", json={"email": "weak@x.com", "password": "123", "name": "X"})
    assert r.status_code == 400
    assert "8 characters" in r.json()["detail"]

def test_register_common_password(client):
    r = client.post("/auth/register", json={"email": "common@x.com", "password": "password", "name": "X"})
    assert r.status_code == 400

def test_register_email_verified_false(client, auth_client):
    r = auth_client.get("/auth/me")
    assert r.status_code == 200
    assert r.json().get("email_verified") == False

def test_workspace_crud(client, auth_client):
    r = auth_client.post("/workspaces", json={"name": "Test WS"})
    assert r.status_code == 200
    ws_id = r.json()["workspace_id"]
    r = auth_client.get(f"/workspaces/{ws_id}")
    assert r.status_code == 200

def test_channel_crud(client, auth_client):
    ws = auth_client.post("/workspaces", json={"name": "CH Test"}).json()
    r = auth_client.post(f"/workspaces/{ws['workspace_id']}/channels", json={"name": "test-ch"})
    assert r.status_code == 200
    ch_id = r.json()["channel_id"]
    # Send message
    r = auth_client.post(f"/channels/{ch_id}/messages", json={"content": "Hello"})
    assert r.status_code == 200
    # Get messages
    r = auth_client.get(f"/channels/{ch_id}/messages")
    assert r.status_code == 200
    assert len(r.json()) >= 1

def test_xss_sanitization(client, auth_client):
    ws = auth_client.post("/workspaces", json={"name": "XSS Test"}).json()
    ch = auth_client.post(f"/workspaces/{ws['workspace_id']}/channels", json={"name": "xss"}).json()
    r = auth_client.post(f"/channels/{ch['channel_id']}/messages", json={"content": "<script>alert(1)</script>safe"})
    assert r.status_code == 200
    msgs = auth_client.get(f"/channels/{ch['channel_id']}/messages").json()
    last = msgs[-1]["content"]
    assert "<script>" not in last
    assert "safe" in last

def test_channel_roles(client, auth_client):
    ws = auth_client.post("/workspaces", json={"name": "Roles"}).json()
    ch = auth_client.post(f"/workspaces/{ws['workspace_id']}/channels", json={"name": "r", "ai_agents": ["claude"]}).json()
    r = auth_client.put(f"/channels/{ch['channel_id']}/roles", json={"tpm": "claude"})
    assert r.json()["tpm"] == "claude"

def test_file_upload(client, auth_client):
    ws = auth_client.post("/workspaces", json={"name": "File"}).json()
    ch = auth_client.post(f"/workspaces/{ws['workspace_id']}/channels", json={"name": "f"}).json()
    r = auth_client.post(f"/channels/{ch['channel_id']}/files", files={"file": ("test.txt", b"hello world", "text/plain")})
    assert r.status_code == 200
    assert r.json()["file"]["has_extracted_text"] == True

def test_context_ledger(client, auth_client):
    ws = auth_client.post("/workspaces", json={"name": "CTX"}).json()
    ch = auth_client.post(f"/workspaces/{ws['workspace_id']}/channels", json={"name": "ctx"}).json()
    r = auth_client.get(f"/channels/{ch['channel_id']}/context-ledger")
    assert r.status_code == 200

def test_activities(client, auth_client):
    ws = auth_client.post("/workspaces", json={"name": "Act"}).json()
    r = auth_client.get(f"/workspaces/{ws['workspace_id']}/activities")
    assert r.status_code == 200
    assert "total" in r.json()

def test_activities_export_csv(client, auth_client):
    ws = auth_client.post("/workspaces", json={"name": "Export"}).json()
    r = auth_client.get(f"/workspaces/{ws['workspace_id']}/activities/export?format=csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")

def test_preferences(client, auth_client):
    r = auth_client.put("/user/preferences", json={"pinned_panels": {"ch_test": {"agents": True}}})
    assert r.status_code == 200
    r = auth_client.get("/user/preferences")
    assert "pinned_panels" in r.json()

def test_admin_403(client, auth_client):
    r = auth_client.get("/admin/recycle-bin")
    assert r.status_code == 403
    r = auth_client.get("/admin/duplicate-overrides")
    assert r.status_code == 403

def test_directive_with_rules(client, auth_client):
    ws = auth_client.post("/workspaces", json={"name": "Dir"}).json()
    ch = auth_client.post(f"/workspaces/{ws['workspace_id']}/channels", json={"name": "d"}).json()
    r = client.post(f"/channels/{ch['channel_id']}/directive", json={
        "project_name": "Test", "universal_rules": {"prohibited_patterns": ["eval()"]}
    }, cookies=auth_client.cookies)
    assert r.status_code == 200
    assert "eval()" in r.json().get("universal_rules", {}).get("prohibited_patterns", [])

def test_persist_hard_stop(client, auth_client):
    ws = auth_client.post("/workspaces", json={"name": "Persist"}).json()
    ch = auth_client.post(f"/workspaces/{ws['workspace_id']}/channels", json={"name": "p"}).json()
    r = auth_client.put(f"/channels/{ch['channel_id']}/auto-collab-persist", json={"enabled": True})
    assert r.json()["persist"] == True
    r = auth_client.put(f"/channels/{ch['channel_id']}/auto-collab-persist", json={"enabled": False})
    assert r.json()["status"] == "hard_stopped"
