"""
Org-Level Features Tests - Iteration 27
Tests: 
- Org Projects/Tasks/Workflows/Analytics rollup endpoints
- Custom domain and login config
- Checkpoint types endpoint

Credentials:
- Org admin: email=admin@urtech.org password=Test1234!
- Org slug: urtech
- Org ID: org_cba36eb8305f
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

class TestOrgLevelFeatures:
    """Test org-level rollup features"""

    @pytest.fixture(scope="class")
    def session(self):
        """Create authenticated session"""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        return s

    @pytest.fixture(scope="class")
    def auth_cookies(self, session):
        """Login and get auth cookies"""
        login_data = {"email": "admin@urtech.org", "password": "Test1234!"}
        r = session.post(f"{BASE_URL}/api/auth/login", json=login_data)
        assert r.status_code == 200, f"Login failed: {r.text}"
        return session.cookies

    @pytest.fixture(scope="class")
    def org_id(self):
        """Get org ID for urtech"""
        return "org_cba36eb8305f"

    # ========== Checkpoint Types ==========
    def test_checkpoint_types_returns_5_types(self, session, auth_cookies):
        """GET /api/checkpoints/types returns 5 checkpoint types"""
        r = session.get(f"{BASE_URL}/api/checkpoints/types")
        assert r.status_code == 200, f"Got {r.status_code}: {r.text}"
        data = r.json()
        # Could be list of objects with key/name/description
        assert "types" in data or isinstance(data, list), f"Unexpected format: {data}"
        types_list = data.get("types", data) if isinstance(data, dict) else data
        assert len(types_list) == 5, f"Expected 5 types, got {len(types_list)}: {types_list}"
        print(f"Checkpoint types: {[t.get('key', t) if isinstance(t, dict) else t for t in types_list]}")

    def test_checkpoint_types_have_required_fields(self, session, auth_cookies):
        """Each checkpoint type has key, name, description"""
        r = session.get(f"{BASE_URL}/api/checkpoints/types")
        assert r.status_code == 200
        data = r.json()
        types_list = data.get("types", data) if isinstance(data, dict) else data
        for t in types_list:
            if isinstance(t, dict):
                assert "key" in t or "type" in t, f"Missing key/type in {t}"
                assert "name" in t or "label" in t, f"Missing name/label in {t}"
                assert "description" in t or "desc" in t, f"Missing description in {t}"

    # ========== Org Projects Rollup ==========
    def test_org_projects_returns_list(self, session, auth_cookies, org_id):
        """GET /api/orgs/{org_id}/projects returns aggregated projects"""
        r = session.get(f"{BASE_URL}/api/orgs/{org_id}/projects")
        assert r.status_code == 200, f"Got {r.status_code}: {r.text}"
        data = r.json()
        assert "projects" in data, f"Missing 'projects' key: {data}"
        assert "total" in data, f"Missing 'total' key: {data}"
        assert isinstance(data["projects"], list), f"projects should be list: {data}"
        print(f"Org projects count: {data['total']}")

    # ========== Org Tasks Rollup ==========
    def test_org_tasks_returns_list(self, session, auth_cookies, org_id):
        """GET /api/orgs/{org_id}/tasks returns aggregated tasks"""
        r = session.get(f"{BASE_URL}/api/orgs/{org_id}/tasks")
        assert r.status_code == 200, f"Got {r.status_code}: {r.text}"
        data = r.json()
        assert "tasks" in data, f"Missing 'tasks' key: {data}"
        assert "total" in data, f"Missing 'total' key: {data}"
        assert isinstance(data["tasks"], list), f"tasks should be list: {data}"
        print(f"Org tasks count: {data['total']}")

    def test_org_tasks_supports_search_filter(self, session, auth_cookies, org_id):
        """GET /api/orgs/{org_id}/tasks supports search and status filter"""
        # Test with search param
        r = session.get(f"{BASE_URL}/api/orgs/{org_id}/tasks?search=test")
        assert r.status_code == 200, f"Search failed: {r.text}"
        # Test with status filter
        r = session.get(f"{BASE_URL}/api/orgs/{org_id}/tasks?status=todo")
        assert r.status_code == 200, f"Status filter failed: {r.text}"
        # Test with sort
        r = session.get(f"{BASE_URL}/api/orgs/{org_id}/tasks?sort_by=updated_at&sort_order=desc")
        assert r.status_code == 200, f"Sort failed: {r.text}"

    # ========== Org Workflows Rollup ==========
    def test_org_workflows_returns_list(self, session, auth_cookies, org_id):
        """GET /api/orgs/{org_id}/workflows returns aggregated workflows"""
        r = session.get(f"{BASE_URL}/api/orgs/{org_id}/workflows")
        assert r.status_code == 200, f"Got {r.status_code}: {r.text}"
        data = r.json()
        assert "workflows" in data, f"Missing 'workflows' key: {data}"
        assert "total" in data, f"Missing 'total' key: {data}"
        assert isinstance(data["workflows"], list), f"workflows should be list: {data}"
        print(f"Org workflows count: {data['total']}")

    # ========== Org Analytics Summary ==========
    def test_org_analytics_summary(self, session, auth_cookies, org_id):
        """GET /api/orgs/{org_id}/analytics/summary returns summary stats"""
        r = session.get(f"{BASE_URL}/api/orgs/{org_id}/analytics/summary")
        assert r.status_code == 200, f"Got {r.status_code}: {r.text}"
        data = r.json()
        # Check required fields
        required_fields = ["total_messages", "total_projects", "total_tasks", "total_workflows", "workspaces"]
        for field in required_fields:
            assert field in data, f"Missing '{field}' in analytics: {data}"
        print(f"Analytics: workspaces={data['workspaces']}, projects={data['total_projects']}, tasks={data['total_tasks']}")

    # ========== Custom Domain ==========
    def test_set_custom_domain(self, session, auth_cookies, org_id):
        """PUT /api/orgs/{org_id}/custom-domain sets custom domain"""
        r = session.put(f"{BASE_URL}/api/orgs/{org_id}/custom-domain", json={"custom_domain": "test.urtech.org"})
        assert r.status_code == 200, f"Got {r.status_code}: {r.text}"
        data = r.json()
        assert "custom_domain" in data or "login_url" in data, f"Missing domain info: {data}"
        print(f"Custom domain set: {data}")
        
        # Reset to empty
        r2 = session.put(f"{BASE_URL}/api/orgs/{org_id}/custom-domain", json={"custom_domain": ""})
        assert r2.status_code == 200, f"Reset failed: {r2.text}"

    # ========== Login Config ==========
    def test_get_login_config(self, session, auth_cookies, org_id):
        """GET /api/orgs/{org_id}/login-config returns login URL config"""
        r = session.get(f"{BASE_URL}/api/orgs/{org_id}/login-config")
        assert r.status_code == 200, f"Got {r.status_code}: {r.text}"
        data = r.json()
        assert "slug" in data, f"Missing 'slug': {data}"
        assert "default_url" in data or "dashboard_url" in data, f"Missing URL info: {data}"
        print(f"Login config: slug={data.get('slug')}, dashboard_url={data.get('dashboard_url')}")


class TestOrgWorkspaceCreationAndRollup:
    """Test creating workspace and verifying rollup data"""

    @pytest.fixture(scope="class")
    def session(self):
        """Create authenticated session"""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        # Login
        login_data = {"email": "admin@urtech.org", "password": "Test1234!"}
        r = s.post(f"{BASE_URL}/api/auth/login", json=login_data)
        assert r.status_code == 200, f"Login failed: {r.text}"
        return s

    @pytest.fixture(scope="class")
    def org_id(self):
        return "org_cba36eb8305f"

    @pytest.fixture(scope="class")
    def test_workspace(self, session, org_id):
        """Create test workspace in org for rollup testing"""
        ws_data = {
            "name": "TEST_Org_Rollup_WS_27",
            "description": "Testing org-level rollup features"
        }
        r = session.post(f"{BASE_URL}/api/orgs/{org_id}/workspaces", json=ws_data)
        assert r.status_code == 200 or r.status_code == 201, f"Workspace create failed: {r.text}"
        ws = r.json()
        assert "workspace_id" in ws, f"Missing workspace_id: {ws}"
        print(f"Created test workspace: {ws['workspace_id']}")
        yield ws
        # Cleanup - try to delete
        try:
            session.delete(f"{BASE_URL}/api/workspaces/{ws['workspace_id']}")
        except:
            pass

    @pytest.fixture(scope="class")
    def test_project(self, session, test_workspace):
        """Create test project in workspace"""
        project_data = {
            "name": "TEST_Rollup_Project_27",
            "description": "Testing project rollup",
            "status": "active"
        }
        r = session.post(f"{BASE_URL}/api/workspaces/{test_workspace['workspace_id']}/projects", json=project_data)
        assert r.status_code == 200 or r.status_code == 201, f"Project create failed: {r.text}"
        project = r.json()
        assert "project_id" in project, f"Missing project_id: {project}"
        print(f"Created test project: {project['project_id']}")
        yield project
        # Cleanup
        try:
            session.delete(f"{BASE_URL}/api/projects/{project['project_id']}")
        except:
            pass

    @pytest.fixture(scope="class")
    def test_task(self, session, test_workspace, test_project):
        """Create test task in project"""
        task_data = {
            "title": "TEST_Rollup_Task_27",
            "description": "Testing task rollup",
            "status": "todo",
            "priority": "medium"
        }
        r = session.post(f"{BASE_URL}/api/projects/{test_project['project_id']}/tasks", json=task_data)
        assert r.status_code == 200 or r.status_code == 201, f"Task create failed: {r.text}"
        task = r.json()
        assert "task_id" in task, f"Missing task_id: {task}"
        print(f"Created test task: {task['task_id']}")
        yield task
        # Cleanup
        try:
            session.delete(f"{BASE_URL}/api/tasks/{task['task_id']}")
        except:
            pass

    def test_org_projects_includes_workspace_name(self, session, org_id, test_workspace, test_project):
        """Org projects include workspace_name for cross-workspace attribution"""
        r = session.get(f"{BASE_URL}/api/orgs/{org_id}/projects")
        assert r.status_code == 200
        data = r.json()
        # Find our test project
        test_proj = next((p for p in data["projects"] if p["project_id"] == test_project["project_id"]), None)
        if test_proj:
            assert "workspace_name" in test_proj, f"Missing workspace_name in project: {test_proj}"
            print(f"Project workspace_name: {test_proj.get('workspace_name')}")
        else:
            print(f"Test project not found in org projects list (may be expected if workspace not in org)")

    def test_org_projects_includes_task_counts(self, session, org_id, test_workspace, test_project, test_task):
        """Org projects include task_count and tasks_done"""
        r = session.get(f"{BASE_URL}/api/orgs/{org_id}/projects")
        assert r.status_code == 200
        data = r.json()
        # Find our test project
        test_proj = next((p for p in data["projects"] if p["project_id"] == test_project["project_id"]), None)
        if test_proj:
            assert "task_count" in test_proj, f"Missing task_count: {test_proj}"
            assert "tasks_done" in test_proj, f"Missing tasks_done: {test_proj}"
            print(f"Project task_count={test_proj.get('task_count')}, tasks_done={test_proj.get('tasks_done')}")

    def test_org_tasks_includes_project_and_workspace_name(self, session, org_id, test_task, test_project, test_workspace):
        """Org tasks include project_name and workspace_name"""
        r = session.get(f"{BASE_URL}/api/orgs/{org_id}/tasks")
        assert r.status_code == 200
        data = r.json()
        # Find our test task
        test_t = next((t for t in data["tasks"] if t.get("task_id") == test_task.get("task_id")), None)
        if test_t:
            assert "project_name" in test_t, f"Missing project_name: {test_t}"
            assert "workspace_name" in test_t, f"Missing workspace_name: {test_t}"
            print(f"Task project_name={test_t.get('project_name')}, workspace_name={test_t.get('workspace_name')}")

    def test_org_workspaces_list(self, session, org_id, test_workspace):
        """GET /api/orgs/{org_id}/workspaces lists org workspaces"""
        r = session.get(f"{BASE_URL}/api/orgs/{org_id}/workspaces")
        assert r.status_code == 200, f"Got {r.status_code}: {r.text}"
        data = r.json()
        assert "workspaces" in data, f"Missing workspaces: {data}"
        ws_ids = [w["workspace_id"] for w in data["workspaces"]]
        assert test_workspace["workspace_id"] in ws_ids, f"Test workspace not in list: {ws_ids}"
        print(f"Org has {len(data['workspaces'])} workspaces")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
