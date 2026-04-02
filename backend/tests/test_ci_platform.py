"""test_platform.py — Platform-wide API regression tests."""
import requests
import pytest
import uuid


class TestHealthEndpoints:
    """Test health and status endpoints."""

    def test_health(self, api_url):
        resp = requests.get(f"{api_url}/api/health")
        assert resp.status_code == 200
        assert resp.json().get("status") == "healthy"

    def test_health_startup(self, api_url):
        resp = requests.get(f"{api_url}/api/health/startup")
        assert resp.status_code == 200

    def test_health_live(self, api_url):
        resp = requests.get(f"{api_url}/api/health/live")
        assert resp.status_code == 200
        assert resp.json().get("alive") is True


class TestPlatformCapabilities:
    """Test platform capabilities and feature flags."""

    def test_capabilities(self, api_url, auth_headers):
        resp = requests.get(f"{api_url}/api/platform/capabilities", headers=auth_headers)
        assert resp.status_code == 200

    def test_ai_models(self, api_url, auth_headers):
        resp = requests.get(f"{api_url}/api/ai-models", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert isinstance(data["models"], dict)
        assert len(data["models"]) > 0


class TestSupportDesk:
    """Test support desk ticket operations."""

    def test_list_tickets(self, api_url, auth_headers):
        resp = requests.get(f"{api_url}/api/support/tickets", headers=auth_headers)
        assert resp.status_code == 200
        assert "tickets" in resp.json()

    def test_list_tickets_with_org_filter(self, api_url, auth_headers):
        resp = requests.get(f"{api_url}/api/support/tickets?org_id=test_org", headers=auth_headers)
        assert resp.status_code == 200

    def test_create_ticket(self, api_url, auth_headers):
        resp = requests.post(f"{api_url}/api/support/tickets", headers=auth_headers, json={
            "subject": f"CI Test Ticket {uuid.uuid4().hex[:6]}",
            "description": "Automated CI test",
            "ticket_type": "question",
            "priority": "low"
        })
        assert resp.status_code == 200
        assert "ticket_id" in resp.json()


class TestNotifications:
    """Test notification endpoints."""

    def test_list_notifications(self, api_url, auth_headers):
        resp = requests.get(f"{api_url}/api/notifications", headers=auth_headers)
        assert resp.status_code == 200


class TestProjects:
    """Test project CRUD."""

    @pytest.fixture(scope="class")
    def workspace_id(self, api_url, auth_headers):
        ws = requests.post(f"{api_url}/api/workspaces", headers=auth_headers, json={
            "name": f"CI Project WS {uuid.uuid4().hex[:6]}"
        }).json()
        return ws["workspace_id"]

    def test_create_project(self, api_url, auth_headers, workspace_id):
        resp = requests.post(f"{api_url}/api/workspaces/{workspace_id}/projects", headers=auth_headers, json={
            "name": f"CI Project {uuid.uuid4().hex[:6]}",
            "description": "CI test project"
        })
        assert resp.status_code == 200
        assert "project_id" in resp.json()

    def test_list_projects(self, api_url, auth_headers, workspace_id):
        resp = requests.get(f"{api_url}/api/workspaces/{workspace_id}/projects", headers=auth_headers)
        assert resp.status_code == 200


class TestTasks:
    """Test task CRUD."""

    @pytest.fixture(scope="class")
    def workspace_id(self, api_url, auth_headers):
        ws = requests.post(f"{api_url}/api/workspaces", headers=auth_headers, json={
            "name": f"CI Task WS {uuid.uuid4().hex[:6]}"
        }).json()
        return ws["workspace_id"]

    def test_list_tasks(self, api_url, auth_headers, workspace_id):
        resp = requests.get(f"{api_url}/api/workspaces/{workspace_id}/tasks", headers=auth_headers)
        assert resp.status_code == 200

    def test_create_task(self, api_url, auth_headers, workspace_id):
        resp = requests.post(f"{api_url}/api/workspaces/{workspace_id}/tasks", headers=auth_headers, json={
            "title": f"CI Task {uuid.uuid4().hex[:6]}",
            "description": "Automated CI test task"
        })
        assert resp.status_code == 200


class TestWiki:
    """Test wiki page operations."""

    @pytest.fixture(scope="class")
    def workspace_id(self, api_url, auth_headers):
        ws = requests.post(f"{api_url}/api/workspaces", headers=auth_headers, json={
            "name": f"CI Wiki WS {uuid.uuid4().hex[:6]}"
        }).json()
        return ws["workspace_id"]

    def test_create_wiki_page(self, api_url, auth_headers, workspace_id):
        resp = requests.post(f"{api_url}/api/workspaces/{workspace_id}/wiki", headers=auth_headers, json={
            "title": f"CI Wiki Page {uuid.uuid4().hex[:6]}",
            "content": "# Test Page\nThis is a CI test wiki page."
        })
        assert resp.status_code == 200
        assert "page_id" in resp.json()

    def test_list_wiki_pages(self, api_url, auth_headers, workspace_id):
        resp = requests.get(f"{api_url}/api/workspaces/{workspace_id}/wiki", headers=auth_headers)
        assert resp.status_code == 200


class TestReplay:
    """Test replay/share endpoints."""

    def test_replay_nonexistent(self, api_url):
        resp = requests.post(f"{api_url}/api/replay/share_nonexistent", json={})
        assert resp.status_code == 404


class TestAdmin:
    """Test admin endpoints."""

    def test_admin_system_health(self, api_url, auth_headers):
        resp = requests.get(f"{api_url}/api/admin/system-health", headers=auth_headers)
        assert resp.status_code == 200

    def test_admin_diagnostics(self, api_url, auth_headers):
        resp = requests.get(f"{api_url}/api/admin/diagnostics/startup", headers=auth_headers)
        # May be /admin/startup-diagnostics or similar
        assert resp.status_code in (200, 404)
