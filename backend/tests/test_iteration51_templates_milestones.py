"""
Iteration 51 Tests - Project Templates, Milestone Management, Repo Analytics, Milestone Alerts
Tests the new features added in this iteration:
1. GET /api/project-templates - Returns 3 templates (web_app, ai_agent, sprint)
2. POST /api/workspaces/{ws}/projects/from-template - Creates project with milestones and tasks
3. GET /api/projects/{pid}/milestones - Returns milestones with progress
4. POST /api/projects/{pid}/milestones - Creates milestone
5. PUT /api/projects/{pid}/milestones/{mid} - Updates milestone status
6. DELETE /api/projects/{pid}/milestones/{mid} - Deletes milestone
7. GET /api/workspaces/{ws}/code-repo/analytics - Returns repo stats
8. GET /api/workspaces/{ws}/milestone-alerts - Returns upcoming deadlines
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials from the request
TEST_EMAIL = "test@test.com"
TEST_PASSWORD = "test123"
TEST_WORKSPACE_ID = "ws_f6ec6355bb18"
TEST_PROJECT_ID = "proj_84d004633464"  # Project created from tpl_ai_agent template


@pytest.fixture(scope="module")
def session():
    """Create authenticated session with cookies"""
    s = requests.Session()
    resp = s.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL, "password": TEST_PASSWORD
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return s


@pytest.fixture(scope="module")
def auth_headers(session):
    """Auth headers with session cookies"""
    return {
        "Cookie": "; ".join([f"{k}={v}" for k, v in session.cookies.items()]),
        "Content-Type": "application/json"
    }


class TestProjectTemplates:
    """Tests for GET /api/project-templates endpoint"""
    
    def test_get_templates_returns_200(self, auth_headers):
        """GET /api/project-templates returns 200"""
        response = requests.get(f"{BASE_URL}/api/project-templates", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    def test_get_templates_returns_3_templates(self, auth_headers):
        """GET /api/project-templates returns exactly 3 templates"""
        response = requests.get(f"{BASE_URL}/api/project-templates", headers=auth_headers)
        data = response.json()
        assert "templates" in data, "Response should have 'templates' key"
        assert len(data["templates"]) == 3, f"Expected 3 templates, got {len(data['templates'])}"
    
    def test_templates_have_correct_ids(self, auth_headers):
        """Templates include tpl_web_app, tpl_ai_agent, tpl_sprint"""
        response = requests.get(f"{BASE_URL}/api/project-templates", headers=auth_headers)
        data = response.json()
        template_ids = [t["template_id"] for t in data["templates"]]
        assert "tpl_web_app" in template_ids, "Missing tpl_web_app template"
        assert "tpl_ai_agent" in template_ids, "Missing tpl_ai_agent template"
        assert "tpl_sprint" in template_ids, "Missing tpl_sprint template"
    
    def test_templates_have_expected_fields(self, auth_headers):
        """Each template has name, description, milestone_count, task_count"""
        response = requests.get(f"{BASE_URL}/api/project-templates", headers=auth_headers)
        data = response.json()
        for t in data["templates"]:
            assert "template_id" in t
            assert "name" in t
            assert "description" in t
            assert "milestone_count" in t
            assert "task_count" in t
    
    def test_tpl_ai_agent_has_4_milestones_11_tasks(self, auth_headers):
        """tpl_ai_agent template has 4 milestones and 11 tasks"""
        response = requests.get(f"{BASE_URL}/api/project-templates", headers=auth_headers)
        data = response.json()
        ai_agent = next((t for t in data["templates"] if t["template_id"] == "tpl_ai_agent"), None)
        assert ai_agent is not None, "tpl_ai_agent template not found"
        assert ai_agent["milestone_count"] == 4, f"Expected 4 milestones, got {ai_agent['milestone_count']}"
        assert ai_agent["task_count"] == 11, f"Expected 11 tasks, got {ai_agent['task_count']}"


class TestCreateProjectFromTemplate:
    """Tests for POST /api/workspaces/{ws}/projects/from-template endpoint"""
    
    created_project_id = None
    
    def test_create_from_template_returns_200(self, auth_headers):
        """POST /api/workspaces/{ws}/projects/from-template returns success"""
        response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/projects/from-template",
            headers=auth_headers,
            json={"template_id": "tpl_sprint", "name": "TEST_Sprint_Project_51"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        TestCreateProjectFromTemplate.created_project_id = data.get("project_id")
        assert data.get("project_id"), "Response should have project_id"
        assert data.get("template_applied") == "tpl_sprint"
        assert data.get("milestones_created") == 3, f"Expected 3 milestones, got {data.get('milestones_created')}"
        assert data.get("tasks_created") == 6, f"Expected 6 tasks, got {data.get('tasks_created')}"
    
    def test_created_project_has_milestones(self, auth_headers):
        """Project created from template has milestones"""
        if not TestCreateProjectFromTemplate.created_project_id:
            pytest.skip("No project created to test")
        response = requests.get(
            f"{BASE_URL}/api/projects/{TestCreateProjectFromTemplate.created_project_id}/milestones",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "milestones" in data
        assert len(data["milestones"]) == 3, f"Expected 3 milestones, got {len(data['milestones'])}"
    
    def test_created_project_has_tasks(self, auth_headers):
        """Project created from template has tasks"""
        if not TestCreateProjectFromTemplate.created_project_id:
            pytest.skip("No project created to test")
        response = requests.get(
            f"{BASE_URL}/api/projects/{TestCreateProjectFromTemplate.created_project_id}/tasks",
            headers=auth_headers
        )
        assert response.status_code == 200
        tasks = response.json()
        assert len(tasks) == 6, f"Expected 6 tasks, got {len(tasks)}"
    
    def test_invalid_template_returns_404(self, auth_headers):
        """Invalid template_id returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/projects/from-template",
            headers=auth_headers,
            json={"template_id": "invalid_template", "name": "Test"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    
    @pytest.fixture(scope="class", autouse=True)
    def cleanup_created_project(self, auth_headers, request):
        """Cleanup test project after tests"""
        yield
        if TestCreateProjectFromTemplate.created_project_id:
            requests.delete(
                f"{BASE_URL}/api/projects/{TestCreateProjectFromTemplate.created_project_id}",
                headers=auth_headers
            )


class TestMilestonesForExistingProject:
    """Tests for milestones CRUD on existing project (proj_84d004633464)"""
    
    def test_get_milestones_returns_200(self, auth_headers):
        """GET /api/projects/{pid}/milestones returns 200"""
        response = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/milestones", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    def test_get_milestones_has_progress_fields(self, auth_headers):
        """Milestones have linked_tasks, done_tasks, progress fields"""
        response = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/milestones", headers=auth_headers)
        data = response.json()
        assert "milestones" in data
        for m in data["milestones"]:
            assert "milestone_id" in m
            assert "name" in m
            assert "linked_tasks" in m, "Missing linked_tasks field"
            assert "done_tasks" in m, "Missing done_tasks field"
            assert "progress" in m, "Missing progress field"
    
    def test_project_has_4_milestones_from_template(self, auth_headers):
        """proj_84d004633464 (created from tpl_ai_agent) has 4 milestones"""
        response = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/milestones", headers=auth_headers)
        data = response.json()
        # Project was created from tpl_ai_agent which has 4 milestones
        assert len(data["milestones"]) >= 4, f"Expected at least 4 milestones, got {len(data['milestones'])}"


class TestMilestonesCRUD:
    """Tests for create/update/delete milestone operations"""
    
    created_milestone_id = None
    
    def test_create_milestone_returns_milestone(self, auth_headers):
        """POST /api/projects/{pid}/milestones creates milestone"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/milestones",
            headers=auth_headers,
            json={"name": "TEST_Milestone_51", "description": "Test milestone", "due_date": "2026-03-20"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("milestone_id"), "Missing milestone_id"
        assert data.get("name") == "TEST_Milestone_51"
        TestMilestonesCRUD.created_milestone_id = data["milestone_id"]
    
    def test_update_milestone_status(self, auth_headers):
        """PUT /api/projects/{pid}/milestones/{mid} updates status"""
        if not TestMilestonesCRUD.created_milestone_id:
            pytest.skip("No milestone created to update")
        response = requests.put(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/milestones/{TestMilestonesCRUD.created_milestone_id}",
            headers=auth_headers,
            json={"status": "in_progress"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("status") == "in_progress"
    
    def test_delete_milestone(self, auth_headers):
        """DELETE /api/projects/{pid}/milestones/{mid} deletes milestone"""
        if not TestMilestonesCRUD.created_milestone_id:
            pytest.skip("No milestone created to delete")
        response = requests.delete(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/milestones/{TestMilestonesCRUD.created_milestone_id}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        # Verify deleted
        response = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/milestones", headers=auth_headers)
        data = response.json()
        ids = [m["milestone_id"] for m in data["milestones"]]
        assert TestMilestonesCRUD.created_milestone_id not in ids, "Milestone should be deleted"


class TestRepoAnalytics:
    """Tests for GET /api/workspaces/{ws}/code-repo/analytics endpoint"""
    
    def test_repo_analytics_returns_200(self, auth_headers):
        """GET /api/workspaces/{ws}/code-repo/analytics returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/analytics",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    def test_repo_analytics_has_expected_fields(self, auth_headers):
        """Repo analytics response has file_count, folder_count, commit_count, etc."""
        response = requests.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/analytics",
            headers=auth_headers
        )
        data = response.json()
        assert "file_count" in data, "Missing file_count"
        assert "folder_count" in data, "Missing folder_count"
        assert "commit_count" in data, "Missing commit_count"
        assert "branch_count" in data, "Missing branch_count"
        assert "review_count" in data, "Missing review_count"
        assert "language_stats" in data, "Missing language_stats"
        assert "recent_commits" in data, "Missing recent_commits"
        assert "contributors" in data, "Missing contributors"


class TestMilestoneAlerts:
    """Tests for GET /api/workspaces/{ws}/milestone-alerts endpoint"""
    
    def test_milestone_alerts_returns_200(self, auth_headers):
        """GET /api/workspaces/{ws}/milestone-alerts returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/milestone-alerts",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    def test_milestone_alerts_has_alerts_field(self, auth_headers):
        """Response has 'alerts' array"""
        response = requests.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/milestone-alerts",
            headers=auth_headers
        )
        data = response.json()
        assert "alerts" in data, "Response should have 'alerts' key"
        assert isinstance(data["alerts"], list)
    
    def test_alerts_have_expected_fields(self, auth_headers):
        """Alert items have project_name, overdue, days_until fields"""
        response = requests.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/milestone-alerts",
            headers=auth_headers
        )
        data = response.json()
        if data["alerts"]:
            alert = data["alerts"][0]
            assert "milestone_id" in alert
            assert "name" in alert
            assert "project_name" in alert, "Missing project_name"
            assert "overdue" in alert, "Missing overdue field"
            assert "days_until" in alert, "Missing days_until field"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
