"""
Test suite for Projects Module - Workspace-level project management with tasks
Tests: Projects CRUD, Tasks CRUD, Channel-Project linking
"""
import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "deploy_test@test.com"
TEST_PASSWORD = "testpass123"

# Test data prefix for cleanup
TEST_PREFIX = "TEST_PROJ_"


@pytest.fixture(scope="module")
def session():
    """Create a requests session"""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth_token(session):
    """Login and get authentication token"""
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    
    if response.status_code == 200:
        data = response.json()
        token = data.get("session_token") or data.get("token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        return token
    
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def workspace_id(session, auth_token):
    """Get or create a workspace for testing"""
    # First try to get existing workspaces
    response = session.get(f"{BASE_URL}/api/workspaces")
    if response.status_code == 200:
        workspaces = response.json()
        if workspaces:
            return workspaces[0]["workspace_id"]
    
    # Create a new workspace if none exists
    response = session.post(f"{BASE_URL}/api/workspaces", json={
        "name": f"{TEST_PREFIX}Workspace",
        "description": "Test workspace for projects module"
    })
    if response.status_code == 200:
        return response.json()["workspace_id"]
    
    pytest.skip("Could not get or create workspace")


@pytest.fixture(scope="module")
def channel_id(session, auth_token, workspace_id):
    """Get or create a channel for testing channel-project linking"""
    response = session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/channels")
    if response.status_code == 200:
        channels = response.json()
        if channels:
            return channels[0]["channel_id"]
    
    # Create a channel
    response = session.post(f"{BASE_URL}/api/workspaces/{workspace_id}/channels", json={
        "name": f"{TEST_PREFIX}Channel",
        "description": "Test channel for linking",
        "ai_agents": ["claude"]
    })
    if response.status_code == 200:
        return response.json()["channel_id"]
    
    pytest.skip("Could not get or create channel")


class TestProjectsCRUD:
    """Test Projects Create, Read, Update, Delete operations"""
    
    def test_list_projects_empty_or_existing(self, session, auth_token, workspace_id):
        """GET /api/workspaces/{workspace_id}/projects - should return list"""
        response = session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/projects")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"[PASS] List projects returned {len(data)} project(s)")
    
    def test_create_project(self, session, auth_token, workspace_id):
        """POST /api/workspaces/{workspace_id}/projects - create a new project"""
        project_name = f"{TEST_PREFIX}{uuid.uuid4().hex[:8]}"
        
        response = session.post(f"{BASE_URL}/api/workspaces/{workspace_id}/projects", json={
            "name": project_name,
            "description": "Test project for automation testing",
            "linked_channels": []
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "project_id" in data, "Response should have project_id"
        assert data["name"] == project_name, f"Project name mismatch"
        assert data["status"] == "active", "New project should have 'active' status"
        assert data["workspace_id"] == workspace_id, "Workspace ID mismatch"
        assert "task_count" in data, "Response should include task_count"
        assert "tasks_done" in data, "Response should include tasks_done"
        
        print(f"[PASS] Project created: {data['project_id']}")
        return data["project_id"]
    
    def test_create_project_with_channel_linking(self, session, auth_token, workspace_id, channel_id):
        """POST /api/workspaces/{workspace_id}/projects - create project linked to channel"""
        project_name = f"{TEST_PREFIX}Linked_{uuid.uuid4().hex[:6]}"
        
        response = session.post(f"{BASE_URL}/api/workspaces/{workspace_id}/projects", json={
            "name": project_name,
            "description": "Project linked to a channel",
            "linked_channels": [channel_id]
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data["linked_channels"] == [channel_id], "Channel should be linked"
        print(f"[PASS] Project created with channel link: {data['project_id']}")
        return data["project_id"]
    
    def test_get_single_project(self, session, auth_token, workspace_id):
        """GET /api/projects/{project_id} - get single project details"""
        # First create a project
        project_name = f"{TEST_PREFIX}GetTest_{uuid.uuid4().hex[:6]}"
        create_res = session.post(f"{BASE_URL}/api/workspaces/{workspace_id}/projects", json={
            "name": project_name,
            "description": "Project for GET test"
        })
        assert create_res.status_code == 200
        project_id = create_res.json()["project_id"]
        
        # Now get it
        response = session.get(f"{BASE_URL}/api/projects/{project_id}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert data["project_id"] == project_id
        assert data["name"] == project_name
        assert "task_count" in data
        assert "tasks_done" in data
        
        print(f"[PASS] Get single project: {project_id}")
    
    def test_update_project_name_description(self, session, auth_token, workspace_id):
        """PUT /api/projects/{project_id} - update name and description"""
        # Create project
        create_res = session.post(f"{BASE_URL}/api/workspaces/{workspace_id}/projects", json={
            "name": f"{TEST_PREFIX}Update_{uuid.uuid4().hex[:6]}",
            "description": "Original description"
        })
        assert create_res.status_code == 200
        project_id = create_res.json()["project_id"]
        
        # Update
        new_name = f"{TEST_PREFIX}Updated_{uuid.uuid4().hex[:6]}"
        response = session.put(f"{BASE_URL}/api/projects/{project_id}", json={
            "name": new_name,
            "description": "Updated description"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert data["name"] == new_name
        assert data["description"] == "Updated description"
        
        # Verify persistence via GET
        get_res = session.get(f"{BASE_URL}/api/projects/{project_id}")
        assert get_res.status_code == 200
        assert get_res.json()["name"] == new_name
        
        print(f"[PASS] Project name/description updated: {project_id}")
    
    def test_update_project_status(self, session, auth_token, workspace_id):
        """PUT /api/projects/{project_id} - change status (active, on_hold, completed, archived)"""
        # Create project
        create_res = session.post(f"{BASE_URL}/api/workspaces/{workspace_id}/projects", json={
            "name": f"{TEST_PREFIX}StatusTest_{uuid.uuid4().hex[:6]}"
        })
        assert create_res.status_code == 200
        project_id = create_res.json()["project_id"]
        
        # Test all valid statuses
        for status in ["on_hold", "completed", "archived", "active"]:
            response = session.put(f"{BASE_URL}/api/projects/{project_id}", json={"status": status})
            assert response.status_code == 200, f"Failed to set status to {status}"
            assert response.json()["status"] == status
        
        print(f"[PASS] Project status changes verified: {project_id}")
    
    def test_update_project_invalid_status(self, session, auth_token, workspace_id):
        """PUT /api/projects/{project_id} - reject invalid status"""
        # Create project
        create_res = session.post(f"{BASE_URL}/api/workspaces/{workspace_id}/projects", json={
            "name": f"{TEST_PREFIX}InvalidStatus_{uuid.uuid4().hex[:6]}"
        })
        assert create_res.status_code == 200
        project_id = create_res.json()["project_id"]
        
        response = session.put(f"{BASE_URL}/api/projects/{project_id}", json={"status": "invalid_status"})
        assert response.status_code == 400, f"Expected 400 for invalid status, got {response.status_code}"
        
        print(f"[PASS] Invalid status rejected correctly")
    
    def test_update_project_linked_channels(self, session, auth_token, workspace_id, channel_id):
        """PUT /api/projects/{project_id} - update linked channels"""
        # Create project without links
        create_res = session.post(f"{BASE_URL}/api/workspaces/{workspace_id}/projects", json={
            "name": f"{TEST_PREFIX}LinkTest_{uuid.uuid4().hex[:6]}",
            "linked_channels": []
        })
        assert create_res.status_code == 200
        project_id = create_res.json()["project_id"]
        
        # Add channel link
        response = session.put(f"{BASE_URL}/api/projects/{project_id}", json={
            "linked_channels": [channel_id]
        })
        assert response.status_code == 200
        assert channel_id in response.json()["linked_channels"]
        
        # Remove channel link
        response = session.put(f"{BASE_URL}/api/projects/{project_id}", json={
            "linked_channels": []
        })
        assert response.status_code == 200
        assert response.json()["linked_channels"] == []
        
        print(f"[PASS] Project channel linking updated: {project_id}")
    
    def test_delete_project(self, session, auth_token, workspace_id):
        """DELETE /api/projects/{project_id} - delete a project"""
        # Create project
        create_res = session.post(f"{BASE_URL}/api/workspaces/{workspace_id}/projects", json={
            "name": f"{TEST_PREFIX}ToDelete_{uuid.uuid4().hex[:6]}"
        })
        assert create_res.status_code == 200
        project_id = create_res.json()["project_id"]
        
        # Delete
        response = session.delete(f"{BASE_URL}/api/projects/{project_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "deleted" in response.json()["message"].lower()
        
        # Verify deletion
        get_res = session.get(f"{BASE_URL}/api/projects/{project_id}")
        assert get_res.status_code == 404, "Deleted project should return 404"
        
        print(f"[PASS] Project deleted and verified: {project_id}")
    
    def test_project_not_found(self, session, auth_token):
        """GET/PUT/DELETE non-existent project returns 404"""
        fake_id = "proj_nonexistent123"
        
        get_res = session.get(f"{BASE_URL}/api/projects/{fake_id}")
        assert get_res.status_code == 404
        
        put_res = session.put(f"{BASE_URL}/api/projects/{fake_id}", json={"name": "Test"})
        assert put_res.status_code == 404
        
        del_res = session.delete(f"{BASE_URL}/api/projects/{fake_id}")
        assert del_res.status_code == 404
        
        print(f"[PASS] Non-existent project returns 404 correctly")


class TestTasksCRUD:
    """Test Tasks Create, Read, Update, Delete operations within projects"""
    
    @pytest.fixture
    def test_project(self, session, auth_token, workspace_id):
        """Create a project for task tests"""
        response = session.post(f"{BASE_URL}/api/workspaces/{workspace_id}/projects", json={
            "name": f"{TEST_PREFIX}TaskTests_{uuid.uuid4().hex[:6]}"
        })
        assert response.status_code == 200
        return response.json()["project_id"]
    
    def test_list_tasks_empty(self, session, auth_token, test_project):
        """GET /api/projects/{project_id}/tasks - list tasks (empty initially)"""
        response = session.get(f"{BASE_URL}/api/projects/{test_project}/tasks")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        print(f"[PASS] List tasks returned {len(data)} task(s)")
    
    def test_create_task_basic(self, session, auth_token, test_project):
        """POST /api/projects/{project_id}/tasks - create basic task"""
        task_title = f"{TEST_PREFIX}Task_{uuid.uuid4().hex[:6]}"
        
        response = session.post(f"{BASE_URL}/api/projects/{test_project}/tasks", json={
            "title": task_title,
            "description": "Test task description",
            "status": "todo",
            "priority": "medium"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "task_id" in data
        assert data["title"] == task_title
        assert data["status"] == "todo"
        assert data["priority"] == "medium"
        assert data["project_id"] == test_project
        
        print(f"[PASS] Task created: {data['task_id']}")
        return data["task_id"]
    
    def test_create_task_with_human_assignee(self, session, auth_token, test_project):
        """POST /api/projects/{project_id}/tasks - create task assigned to human"""
        response = session.post(f"{BASE_URL}/api/projects/{test_project}/tasks", json={
            "title": f"{TEST_PREFIX}HumanTask_{uuid.uuid4().hex[:6]}",
            "status": "todo",
            "priority": "high",
            "assignee_type": "human",
            "assignee_id": "user_12345",
            "assignee_name": "Test User"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["assignee_type"] == "human"
        assert data["assignee_id"] == "user_12345"
        assert data["assignee_name"] == "Test User"
        
        print(f"[PASS] Task with human assignee created: {data['task_id']}")
    
    def test_create_task_with_ai_assignee(self, session, auth_token, test_project):
        """POST /api/projects/{project_id}/tasks - create task assigned to AI agent"""
        response = session.post(f"{BASE_URL}/api/projects/{test_project}/tasks", json={
            "title": f"{TEST_PREFIX}AITask_{uuid.uuid4().hex[:6]}",
            "status": "in_progress",
            "priority": "critical",
            "assignee_type": "ai",
            "assignee_id": "claude",
            "assignee_name": "Claude"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["assignee_type"] == "ai"
        assert data["assignee_id"] == "claude"
        assert data["assignee_name"] == "Claude"
        
        print(f"[PASS] Task with AI assignee created: {data['task_id']}")
    
    def test_create_task_all_statuses(self, session, auth_token, test_project):
        """POST /api/projects/{project_id}/tasks - verify all valid task statuses"""
        for status in ["todo", "in_progress", "review", "done"]:
            response = session.post(f"{BASE_URL}/api/projects/{test_project}/tasks", json={
                "title": f"{TEST_PREFIX}Status_{status}_{uuid.uuid4().hex[:4]}",
                "status": status,
                "priority": "low"
            })
            assert response.status_code == 200, f"Failed to create task with status {status}"
            assert response.json()["status"] == status
        
        print(f"[PASS] All task statuses validated")
    
    def test_create_task_all_priorities(self, session, auth_token, test_project):
        """POST /api/projects/{project_id}/tasks - verify all valid priorities"""
        for priority in ["low", "medium", "high", "critical"]:
            response = session.post(f"{BASE_URL}/api/projects/{test_project}/tasks", json={
                "title": f"{TEST_PREFIX}Priority_{priority}_{uuid.uuid4().hex[:4]}",
                "status": "todo",
                "priority": priority
            })
            assert response.status_code == 200, f"Failed to create task with priority {priority}"
            assert response.json()["priority"] == priority
        
        print(f"[PASS] All task priorities validated")
    
    def test_create_task_invalid_status(self, session, auth_token, test_project):
        """POST /api/projects/{project_id}/tasks - reject invalid status"""
        response = session.post(f"{BASE_URL}/api/projects/{test_project}/tasks", json={
            "title": f"{TEST_PREFIX}InvalidStatus",
            "status": "invalid_status",
            "priority": "medium"
        })
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print(f"[PASS] Invalid task status rejected")
    
    def test_create_task_invalid_priority(self, session, auth_token, test_project):
        """POST /api/projects/{project_id}/tasks - reject invalid priority"""
        response = session.post(f"{BASE_URL}/api/projects/{test_project}/tasks", json={
            "title": f"{TEST_PREFIX}InvalidPriority",
            "status": "todo",
            "priority": "urgent"  # Invalid
        })
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print(f"[PASS] Invalid task priority rejected")
    
    def test_update_task(self, session, auth_token, test_project):
        """PUT /api/projects/{project_id}/tasks/{task_id} - update task"""
        # Create task
        create_res = session.post(f"{BASE_URL}/api/projects/{test_project}/tasks", json={
            "title": f"{TEST_PREFIX}ToUpdate_{uuid.uuid4().hex[:6]}",
            "status": "todo",
            "priority": "low"
        })
        assert create_res.status_code == 200
        task_id = create_res.json()["task_id"]
        
        # Update task
        response = session.put(f"{BASE_URL}/api/projects/{test_project}/tasks/{task_id}", json={
            "title": f"{TEST_PREFIX}Updated_{uuid.uuid4().hex[:6]}",
            "status": "in_progress",
            "priority": "high",
            "assignee_type": "ai",
            "assignee_id": "chatgpt",
            "assignee_name": "ChatGPT"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "in_progress"
        assert data["priority"] == "high"
        assert data["assignee_name"] == "ChatGPT"
        
        print(f"[PASS] Task updated: {task_id}")
    
    def test_delete_task(self, session, auth_token, test_project):
        """DELETE /api/projects/{project_id}/tasks/{task_id} - delete task"""
        # Create task
        create_res = session.post(f"{BASE_URL}/api/projects/{test_project}/tasks", json={
            "title": f"{TEST_PREFIX}ToDelete_{uuid.uuid4().hex[:6]}",
            "status": "todo",
            "priority": "medium"
        })
        assert create_res.status_code == 200
        task_id = create_res.json()["task_id"]
        
        # Delete task
        response = session.delete(f"{BASE_URL}/api/projects/{test_project}/tasks/{task_id}")
        assert response.status_code == 200
        
        # Verify task count decreased (or task list doesn't include it)
        list_res = session.get(f"{BASE_URL}/api/projects/{test_project}/tasks")
        assert list_res.status_code == 200
        task_ids = [t["task_id"] for t in list_res.json()]
        assert task_id not in task_ids, "Deleted task should not appear in list"
        
        print(f"[PASS] Task deleted: {task_id}")
    
    def test_task_not_found(self, session, auth_token, test_project):
        """PUT/DELETE non-existent task returns 404"""
        fake_task_id = "ptask_nonexistent"
        
        put_res = session.put(f"{BASE_URL}/api/projects/{test_project}/tasks/{fake_task_id}", json={
            "title": "Test"
        })
        assert put_res.status_code == 404
        
        del_res = session.delete(f"{BASE_URL}/api/projects/{test_project}/tasks/{fake_task_id}")
        assert del_res.status_code == 404
        
        print(f"[PASS] Non-existent task returns 404")


class TestChannelProjectLinking:
    """Test channel-project linking functionality"""
    
    def test_get_channel_projects(self, session, auth_token, workspace_id, channel_id):
        """GET /api/channels/{channel_id}/projects - get linked projects"""
        # Create a project linked to the channel
        project_name = f"{TEST_PREFIX}ChannelLinked_{uuid.uuid4().hex[:6]}"
        create_res = session.post(f"{BASE_URL}/api/workspaces/{workspace_id}/projects", json={
            "name": project_name,
            "linked_channels": [channel_id]
        })
        assert create_res.status_code == 200
        project_id = create_res.json()["project_id"]
        
        # Get linked projects for channel
        response = session.get(f"{BASE_URL}/api/channels/{channel_id}/projects")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # Verify our project is in the list
        project_ids = [p["project_id"] for p in data]
        assert project_id in project_ids, "Linked project should appear in channel projects"
        
        print(f"[PASS] Channel projects endpoint working: {len(data)} project(s) linked")
    
    def test_channel_projects_includes_task_counts(self, session, auth_token, workspace_id, channel_id):
        """GET /api/channels/{channel_id}/projects - verify task counts included"""
        # Create project with tasks
        project_name = f"{TEST_PREFIX}WithTasks_{uuid.uuid4().hex[:6]}"
        create_res = session.post(f"{BASE_URL}/api/workspaces/{workspace_id}/projects", json={
            "name": project_name,
            "linked_channels": [channel_id]
        })
        assert create_res.status_code == 200
        project_id = create_res.json()["project_id"]
        
        # Add some tasks
        for i in range(3):
            session.post(f"{BASE_URL}/api/projects/{project_id}/tasks", json={
                "title": f"Task {i}",
                "status": "done" if i == 0 else "todo",
                "priority": "medium"
            })
        
        # Get channel projects
        response = session.get(f"{BASE_URL}/api/channels/{channel_id}/projects")
        assert response.status_code == 200
        
        # Find our project
        project = next((p for p in response.json() if p["project_id"] == project_id), None)
        assert project is not None
        assert "task_count" in project
        assert "tasks_done" in project
        assert project["task_count"] >= 3  # May have more from other tests
        
        print(f"[PASS] Channel projects include task counts")


class TestProjectTaskCounts:
    """Test that project task counts are properly calculated"""
    
    def test_project_task_count_after_create(self, session, auth_token, workspace_id):
        """Verify task_count increases after creating tasks"""
        # Create project
        create_res = session.post(f"{BASE_URL}/api/workspaces/{workspace_id}/projects", json={
            "name": f"{TEST_PREFIX}CountTest_{uuid.uuid4().hex[:6]}"
        })
        assert create_res.status_code == 200
        project_id = create_res.json()["project_id"]
        
        # Initial count should be 0
        get_res = session.get(f"{BASE_URL}/api/projects/{project_id}")
        assert get_res.json()["task_count"] == 0
        
        # Add 2 tasks (1 done, 1 todo)
        session.post(f"{BASE_URL}/api/projects/{project_id}/tasks", json={
            "title": "Done Task", "status": "done", "priority": "low"
        })
        session.post(f"{BASE_URL}/api/projects/{project_id}/tasks", json={
            "title": "Todo Task", "status": "todo", "priority": "low"
        })
        
        # Verify counts
        get_res = session.get(f"{BASE_URL}/api/projects/{project_id}")
        data = get_res.json()
        
        assert data["task_count"] == 2
        assert data["tasks_done"] == 1
        
        print(f"[PASS] Task counts calculated correctly")
    
    def test_task_count_in_project_list(self, session, auth_token, workspace_id):
        """Verify task counts are included in project list"""
        response = session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/projects")
        assert response.status_code == 200
        
        projects = response.json()
        for proj in projects:
            assert "task_count" in proj, "Project list should include task_count"
            assert "tasks_done" in proj, "Project list should include tasks_done"
        
        print(f"[PASS] Project list includes task counts")


class TestUnauthorizedAccess:
    """Test that endpoints require authentication"""
    
    def test_projects_require_auth(self):
        """Verify projects endpoints require authentication"""
        no_auth_session = requests.Session()
        no_auth_session.headers.update({"Content-Type": "application/json"})
        
        # Try to list projects
        response = no_auth_session.get(f"{BASE_URL}/api/workspaces/ws_test/projects")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        
        # Try to create project
        response = no_auth_session.post(f"{BASE_URL}/api/workspaces/ws_test/projects", json={
            "name": "Unauthorized Project"
        })
        assert response.status_code == 401
        
        print(f"[PASS] Projects endpoints require authentication")
    
    def test_tasks_require_auth(self):
        """Verify tasks endpoints require authentication"""
        no_auth_session = requests.Session()
        no_auth_session.headers.update({"Content-Type": "application/json"})
        
        response = no_auth_session.get(f"{BASE_URL}/api/projects/proj_test/tasks")
        assert response.status_code == 401
        
        response = no_auth_session.post(f"{BASE_URL}/api/projects/proj_test/tasks", json={
            "title": "Unauthorized Task", "status": "todo", "priority": "low"
        })
        assert response.status_code == 401
        
        print(f"[PASS] Tasks endpoints require authentication")


# Cleanup fixture to remove test data
@pytest.fixture(scope="module", autouse=True)
def cleanup_test_data(session, auth_token, workspace_id):
    """Clean up test projects after all tests complete"""
    yield
    
    # Get all projects and delete test ones
    try:
        response = session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/projects")
        if response.status_code == 200:
            for proj in response.json():
                if proj["name"].startswith(TEST_PREFIX):
                    session.delete(f"{BASE_URL}/api/projects/{proj['project_id']}")
    except:
        pass
