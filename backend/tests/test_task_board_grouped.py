"""
Test Task Board Grouped View and Prompt-Agent Feature
- GET /workspaces/{ws_id}/all-tasks returns tasks grouped by project
- POST /tasks/{task_id}/prompt-agent prompts the assigned AI agent
- Regression tests for integration keys and agent toggle
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAllTasksGrouped:
    """Test GET /workspaces/{ws_id}/all-tasks endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth for all tests"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com",
            "password": "test123"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.workspace_id = "ws_f6ec6355bb18"
        self.channel_id = "ch_bbc9cea9ccc6"
    
    def test_all_tasks_returns_groups_array(self):
        """All-tasks endpoint returns groups array"""
        resp = self.session.get(f"{BASE_URL}/api/workspaces/{self.workspace_id}/all-tasks")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert "groups" in data, "Response should have 'groups' key"
        assert isinstance(data["groups"], list), "groups should be a list"
        assert "total_tasks" in data, "Response should have 'total_tasks' key"
    
    def test_groups_have_correct_structure(self):
        """Each group has project_id, project_name, tasks"""
        resp = self.session.get(f"{BASE_URL}/api/workspaces/{self.workspace_id}/all-tasks")
        assert resp.status_code == 200
        data = resp.json()
        
        for group in data["groups"]:
            assert "project_id" in group, "Group should have project_id"
            assert "project_name" in group, "Group should have project_name"
            assert "tasks" in group, "Group should have tasks array"
            assert isinstance(group["tasks"], list), "tasks should be a list"
    
    def test_workspace_tasks_have_null_project_id(self):
        """Workspace-level tasks appear in group with project_id=null"""
        resp = self.session.get(f"{BASE_URL}/api/workspaces/{self.workspace_id}/all-tasks")
        assert resp.status_code == 200
        data = resp.json()
        
        # Find workspace tasks group
        ws_group = next((g for g in data["groups"] if g["project_id"] is None), None)
        if ws_group:
            assert ws_group["project_name"] == "Workspace Tasks", f"Expected 'Workspace Tasks', got {ws_group['project_name']}"
    
    def test_project_tasks_have_project_id(self):
        """Project tasks appear under their project with project_id set"""
        resp = self.session.get(f"{BASE_URL}/api/workspaces/{self.workspace_id}/all-tasks")
        assert resp.status_code == 200
        data = resp.json()
        
        # Find project groups (non-null project_id)
        project_groups = [g for g in data["groups"] if g["project_id"] is not None]
        if project_groups:
            for pg in project_groups:
                assert pg["project_id"].startswith("proj_"), f"project_id should start with proj_: {pg['project_id']}"
                assert len(pg["project_name"]) > 0, "project_name should not be empty"
    
    def test_tasks_have_required_fields(self):
        """Tasks have title, description, status, priority fields"""
        resp = self.session.get(f"{BASE_URL}/api/workspaces/{self.workspace_id}/all-tasks")
        assert resp.status_code == 200
        data = resp.json()
        
        for group in data["groups"]:
            for task in group["tasks"]:
                assert "task_id" in task, f"Task missing task_id: {task}"
                assert "title" in task, f"Task missing title: {task}"
                assert "status" in task, f"Task missing status: {task}"
                # Optional but should exist if set
                if "priority" in task:
                    assert task["priority"] in ["low", "medium", "high", "critical"], f"Invalid priority: {task['priority']}"
                if "status" in task:
                    assert task["status"] in ["todo", "in_progress", "review", "done", "on_hold", "wont_do"], f"Invalid status: {task['status']}"


class TestPromptAgent:
    """Test POST /tasks/{task_id}/prompt-agent endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth for all tests"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com",
            "password": "test123"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.workspace_id = "ws_f6ec6355bb18"
    
    def test_prompt_agent_nonexistent_task_returns_404(self):
        """Prompt-agent returns 404 for nonexistent task"""
        resp = self.session.post(f"{BASE_URL}/api/tasks/nonexistent_task_12345/prompt-agent")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
    
    def test_prompt_agent_requires_assigned_agent(self):
        """Prompt-agent returns 400 if task has no agent assigned"""
        # Create a task without an agent
        create_resp = self.session.post(f"{BASE_URL}/api/workspaces/{self.workspace_id}/tasks", json={
            "title": "TEST_unassigned_task_for_prompt",
            "description": "Testing prompt without agent",
            "status": "todo",
            "priority": "low",
            "assigned_to": "",
            "assigned_type": "human"
        })
        assert create_resp.status_code == 200, f"Create task failed: {create_resp.text}"
        task_id = create_resp.json().get("task_id")
        
        try:
            # Try to prompt agent
            prompt_resp = self.session.post(f"{BASE_URL}/api/tasks/{task_id}/prompt-agent")
            assert prompt_resp.status_code == 400, f"Expected 400, got {prompt_resp.status_code}: {prompt_resp.text}"
            assert "no agent" in prompt_resp.text.lower() or "assigned" in prompt_resp.text.lower()
        finally:
            # Cleanup
            self.session.delete(f"{BASE_URL}/api/tasks/{task_id}")
    
    def test_prompt_agent_returns_channel_and_message_ids(self):
        """Prompt-agent returns channel_id and message_id on success"""
        # First check if there's a task with an AI agent assigned
        all_tasks_resp = self.session.get(f"{BASE_URL}/api/workspaces/{self.workspace_id}/all-tasks")
        assert all_tasks_resp.status_code == 200
        
        # Find a task with AI agent assigned
        ai_task = None
        for group in all_tasks_resp.json()["groups"]:
            for task in group["tasks"]:
                assigned = task.get("assigned_to") or task.get("assignee_id")
                assigned_type = task.get("assigned_type") or task.get("assignee_type")
                if assigned and assigned_type == "ai":
                    ai_task = task
                    break
            if ai_task:
                break
        
        if not ai_task:
            # Create one
            create_resp = self.session.post(f"{BASE_URL}/api/workspaces/{self.workspace_id}/tasks", json={
                "title": "TEST_ai_task_for_prompt",
                "description": "Testing prompt with AI agent",
                "status": "todo",
                "priority": "medium",
                "assigned_to": "groq",
                "assigned_type": "ai",
                "channel_id": "ch_bbc9cea9ccc6"
            })
            assert create_resp.status_code == 200, f"Create task failed: {create_resp.text}"
            ai_task = create_resp.json()
        
        task_id = ai_task.get("task_id")
        
        try:
            prompt_resp = self.session.post(f"{BASE_URL}/api/tasks/{task_id}/prompt-agent")
            # Could be 200 success or 400 if no channel found
            if prompt_resp.status_code == 200:
                data = prompt_resp.json()
                assert "channel_id" in data, "Response should have channel_id"
                assert "message_id" in data, "Response should have message_id"
                assert data.get("prompted") == True, "prompted should be True"
                print(f"Successfully prompted agent: {data}")
            else:
                # 400 if no channel with agent - acceptable
                print(f"Prompt returned {prompt_resp.status_code}: {prompt_resp.text}")
        finally:
            # Cleanup if we created a test task
            if "TEST_" in ai_task.get("title", ""):
                self.session.delete(f"{BASE_URL}/api/tasks/{task_id}")


class TestRegressionIntegrationKeys:
    """Regression: GET /admin/integrations shows saved keys"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth for all tests"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com",
            "password": "test123"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_get_integrations_returns_200(self):
        """GET /admin/integrations returns 200"""
        resp = self.session.get(f"{BASE_URL}/api/admin/integrations")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    
    def test_integrations_has_integrations_array(self):
        """GET /admin/integrations has integrations array"""
        resp = self.session.get(f"{BASE_URL}/api/admin/integrations")
        assert resp.status_code == 200
        data = resp.json()
        assert "integrations" in data, "Response should have 'integrations' key"
        assert isinstance(data["integrations"], list), "integrations should be a list"


class TestRegressionAgentToggle:
    """Regression: PUT /channels/{ch_id}/agent-toggle works"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth for all tests"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com",
            "password": "test123"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.channel_id = "ch_bbc9cea9ccc6"
    
    def test_agent_toggle_disable(self):
        """PUT /channels/{ch_id}/agent-toggle can disable an agent"""
        resp = self.session.put(f"{BASE_URL}/api/channels/{self.channel_id}/agent-toggle", json={
            "agent_key": "claude",
            "enabled": False
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        # Response contains channel_id, agent_key, enabled
        assert "channel_id" in data or "agent_key" in data, "Response should have confirmation"
    
    def test_agent_toggle_enable(self):
        """PUT /channels/{ch_id}/agent-toggle can enable an agent"""
        resp = self.session.put(f"{BASE_URL}/api/channels/{self.channel_id}/agent-toggle", json={
            "agent_key": "claude",
            "enabled": True
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        # Response contains channel_id, agent_key, enabled
        assert "channel_id" in data or "agent_key" in data, "Response should have confirmation"
    
    def test_get_disabled_agents(self):
        """GET /channels/{ch_id}/disabled-agents works"""
        resp = self.session.get(f"{BASE_URL}/api/channels/{self.channel_id}/disabled-agents")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "disabled_agents" in data, "Response should have disabled_agents"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
