"""
Test iteration 37 - Gantt Chart & Planner Calendar API endpoints
Tests for:
- Workspace-level Gantt: GET /api/workspaces/{ws}/gantt
- Workspace-level Planner: GET /api/workspaces/{ws}/planner
- Org-level Gantt: GET /api/orgs/{org}/gantt
- Org-level Planner: GET /api/orgs/{org}/planner
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
WORKSPACE_ID = "ws_bd1750012bfd"
ORG_ID = "org_cba36eb8305f"

@pytest.fixture(scope="module")
def user_session():
    """Login as workspace user (testmention@test.com)"""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    resp = s.post(f"{BASE_URL}/api/auth/login", json={
        "email": "testmention@test.com",
        "password": "Test1234!"
    })
    assert resp.status_code == 200, f"User login failed: {resp.text}"
    return s

@pytest.fixture(scope="module")
def admin_session():
    """Login as org admin (admin@urtech.org)"""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    resp = s.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@urtech.org",
        "password": "Test1234!"
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return s


class TestWorkspaceGantt:
    """Workspace-level Gantt Chart API"""

    def test_get_workspace_gantt(self, user_session):
        """GET /api/workspaces/{ws}/gantt - Returns gantt items with progress and dependencies"""
        resp = user_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/gantt")
        assert resp.status_code == 200, f"Gantt request failed: {resp.text}"
        result = resp.json()
        assert "items" in result
        print(f"Workspace Gantt has {len(result['items'])} items")
        # Check item structure if items exist
        if result["items"]:
            item = result["items"][0]
            expected_fields = ["id", "title", "start", "end", "status"]
            for field in expected_fields:
                assert field in item, f"Missing field: {field}"
            # Progress and dependencies are optional but should be present if defined
            print(f"First item: {item['title']} ({item['status']})")

    def test_get_workspace_gantt_with_project_filter(self, user_session):
        """GET /api/workspaces/{ws}/gantt?project_id= - Filter by project"""
        # First get projects to find a valid project ID
        projects_resp = user_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/projects")
        if projects_resp.status_code == 200 and projects_resp.json():
            project_id = projects_resp.json()[0]["project_id"]
            resp = user_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/gantt", params={"project_id": project_id})
            assert resp.status_code == 200
            result = resp.json()
            assert "items" in result
            print(f"Gantt filtered by project {project_id}: {len(result['items'])} items")
        else:
            print("No projects found to filter - skipping filter test")


class TestWorkspacePlanner:
    """Workspace-level Planner Calendar API"""

    def test_get_workspace_planner(self, user_session):
        """GET /api/workspaces/{ws}/planner - Returns tasks grouped by date"""
        resp = user_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/planner")
        assert resp.status_code == 200, f"Planner request failed: {resp.text}"
        result = resp.json()
        assert "tasks" in result
        print(f"Workspace Planner has {len(result['tasks'])} tasks")
        # Check task structure if tasks exist
        if result["tasks"]:
            task = result["tasks"][0]
            expected_fields = ["task_id", "title", "status"]
            for field in expected_fields:
                assert field in task, f"Missing field: {field}"
            # due_date is the key field for planner
            assert "due_date" in task, "Task missing due_date field"
            print(f"First task: {task['title']} - due: {task.get('due_date', 'N/A')}")

    def test_get_workspace_planner_with_date_range(self, user_session):
        """GET /api/workspaces/{ws}/planner?start=&end= - Filter by date range"""
        params = {"start": "2026-01-01", "end": "2026-12-31"}
        resp = user_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/planner", params=params)
        assert resp.status_code == 200
        result = resp.json()
        assert "tasks" in result
        print(f"Planner with date range: {len(result['tasks'])} tasks")


class TestOrgGantt:
    """Org-level Gantt Chart API - Cross-workspace view"""

    def test_get_org_gantt(self, admin_session):
        """GET /api/orgs/{org}/gantt - Returns cross-workspace gantt data"""
        resp = admin_session.get(f"{BASE_URL}/api/orgs/{ORG_ID}/gantt")
        assert resp.status_code == 200, f"Org Gantt request failed: {resp.text}"
        result = resp.json()
        assert "items" in result
        print(f"Org Gantt has {len(result['items'])} items across workspaces")
        # Check structure includes workspace info
        if result["items"]:
            item = result["items"][0]
            # Org-level items may include workspace_name
            expected_fields = ["id", "title", "start", "end", "status"]
            for field in expected_fields:
                assert field in item, f"Missing field: {field}"
            print(f"First org item: {item['title']}")


class TestOrgPlanner:
    """Org-level Planner Calendar API - Cross-workspace view"""

    def test_get_org_planner(self, admin_session):
        """GET /api/orgs/{org}/planner - Returns org-level planner data"""
        resp = admin_session.get(f"{BASE_URL}/api/orgs/{ORG_ID}/planner")
        assert resp.status_code == 200, f"Org Planner request failed: {resp.text}"
        result = resp.json()
        assert "tasks" in result
        print(f"Org Planner has {len(result['tasks'])} tasks")

    def test_get_org_planner_with_date_range(self, admin_session):
        """GET /api/orgs/{org}/planner?start=&end= - Filter by date range"""
        params = {"start": "2025-01-01", "end": "2027-12-31"}
        resp = admin_session.get(f"{BASE_URL}/api/orgs/{ORG_ID}/planner", params=params)
        assert resp.status_code == 200
        result = resp.json()
        assert "tasks" in result
        print(f"Org Planner with date range: {len(result['tasks'])} tasks")


class TestAdminIntegrations:
    """Admin Integration Keys API"""

    def test_get_admin_integrations(self, admin_session):
        """GET /api/admin/integrations - Returns 13 integration keys"""
        resp = admin_session.get(f"{BASE_URL}/api/admin/integrations")
        assert resp.status_code == 200, f"Admin integrations failed: {resp.text}"
        result = resp.json()
        assert "integrations" in result
        integrations = result["integrations"]
        # Should have 13 keys as per spec
        assert len(integrations) == 13, f"Expected 13 integrations, got {len(integrations)}"
        print(f"Admin has {len(integrations)} integration keys")
        # Check structure
        for integ in integrations:
            assert "key" in integ
            assert "name" in integ
            assert "configured" in integ
        # List the keys
        keys = [i["key"] for i in integrations]
        print(f"Integration keys: {keys}")


class TestOrgIntegrations:
    """Org-level Integration Overrides"""

    def test_get_org_integrations(self, admin_session):
        """GET /api/orgs/{org}/integrations - Returns org-level overrides"""
        resp = admin_session.get(f"{BASE_URL}/api/orgs/{ORG_ID}/integrations")
        assert resp.status_code == 200, f"Org integrations failed: {resp.text}"
        result = resp.json()
        assert "integrations" in result
        print(f"Org has {len(result['integrations'])} integration config entries")
        # Check structure
        if result["integrations"]:
            integ = result["integrations"][0]
            assert "key" in integ
            assert "has_override" in integ
            assert "using" in integ


class TestOrgEncryption:
    """Per-Tenant Encryption Status"""

    def test_get_encryption_status(self, admin_session):
        """GET /api/orgs/{org}/encryption-status - Returns encryption level"""
        resp = admin_session.get(f"{BASE_URL}/api/orgs/{ORG_ID}/encryption-status")
        assert resp.status_code == 200, f"Encryption status failed: {resp.text}"
        result = resp.json()
        assert "org_id" in result
        assert "has_dedicated_key" in result
        assert "encryption_level" in result
        print(f"Encryption level: {result['encryption_level']}")

    def test_generate_encryption_key(self, admin_session):
        """POST /api/orgs/{org}/encryption/generate-key - Generate per-tenant key"""
        resp = admin_session.post(f"{BASE_URL}/api/orgs/{ORG_ID}/encryption/generate-key")
        assert resp.status_code == 200, f"Generate key failed: {resp.text}"
        result = resp.json()
        assert result["encryption_level"] == "tenant-isolated"
        print(f"Encryption key: {result['status']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
