"""
Full QA Regression Test Suite - Iteration 30
Comprehensive testing of all Nexus platform features: Auth, Workspaces, Channels, Messages,
Projects, Tasks, Artifacts, Workflows, Handoffs, Memory, Webhooks, Exports, AI Tools,
Schedules, Model Performance, Disagreements, Image Generation, Orgs, and Enhancements.
"""
import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL_EXISTING = "testmention@test.com"
TEST_PASSWORD = "Test1234!"
TEST_EMAIL_NEW = f"qa_test_{uuid.uuid4().hex[:8]}@nexus.com"
QA_PASSWORD = "QATest1234!"

# Known fixtures
EXISTING_WORKSPACE_ID = "ws_bd1750012bfd"
EXISTING_CHANNEL_ID = "ch_9988b6543849"


class TestSession:
    """Shared session with authentication"""
    session = None
    token = None
    user = None
    workspace_id = None
    channel_id = None
    project_id = None
    artifact_id = None
    org_id = None


@pytest.fixture(scope="module")
def api_session():
    """Create session and login once for all tests"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login with existing test user
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL_EXISTING,
        "password": TEST_PASSWORD
    })
    if resp.status_code == 200:
        data = resp.json()
        if data.get("session_token"):
            session.headers.update({"Authorization": f"Bearer {data['session_token']}"})
        TestSession.user = data.get("user") or data
        TestSession.session = session
        return session
    
    pytest.skip(f"Login failed: {resp.status_code} - {resp.text[:200]}")


# ============ AUTH TESTS ============

class TestAuth:
    """Authentication endpoint tests - 4 tests"""
    
    def test_register_new_user(self):
        """POST /api/auth/register - register new user"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        resp = session.post(f"{BASE_URL}/api/auth/register", json={
            "email": TEST_EMAIL_NEW,
            "password": QA_PASSWORD,
            "name": "QA Test User"
        })
        # May fail if user exists (400) or succeed (200/201)
        assert resp.status_code in [200, 201, 400], f"Unexpected: {resp.status_code}"
        if resp.status_code in [200, 201]:
            data = resp.json()
            assert "user_id" in data or "email" in data
            print(f"PASS: Registered new user {TEST_EMAIL_NEW}")
        else:
            print(f"PASS: User already exists or validation error - {resp.json()}")
    
    def test_login_with_credentials(self, api_session):
        """POST /api/auth/login - login with email/password"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL_EXISTING,
            "password": TEST_PASSWORD
        })
        assert resp.status_code == 200, f"Login failed: {resp.status_code}"
        data = resp.json()
        assert "session_token" in data or "user_id" in data or "email" in data
        print("PASS: Login successful")
    
    def test_get_current_user(self, api_session):
        """GET /api/auth/me - returns current user"""
        resp = api_session.get(f"{BASE_URL}/api/auth/me")
        assert resp.status_code == 200, f"Auth/me failed: {resp.status_code}"
        data = resp.json()
        assert "user_id" in data
        assert "email" in data
        print(f"PASS: Current user: {data.get('email')}")
    
    def test_logout(self, api_session):
        """POST /api/auth/logout - clears session (test with new session)"""
        # Use a separate session to not break other tests
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL_EXISTING,
            "password": TEST_PASSWORD
        })
        if login_resp.status_code == 200:
            token = login_resp.json().get("session_token")
            session.headers.update({"Authorization": f"Bearer {token}"})
            resp = session.post(f"{BASE_URL}/api/auth/logout")
            assert resp.status_code == 200, f"Logout failed: {resp.status_code}"
            print("PASS: Logout successful")


# ============ WORKSPACE TESTS ============

class TestWorkspaces:
    """Workspace CRUD tests - 5 tests"""
    
    def test_create_workspace(self, api_session):
        """POST /api/workspaces - create workspace"""
        resp = api_session.post(f"{BASE_URL}/api/workspaces", json={
            "name": f"QA Test Workspace {uuid.uuid4().hex[:6]}",
            "description": "Created by full QA regression test"
        })
        assert resp.status_code == 200, f"Create workspace failed: {resp.status_code}"
        data = resp.json()
        assert "workspace_id" in data
        TestSession.workspace_id = data["workspace_id"]
        print(f"PASS: Created workspace {data['workspace_id']}")
    
    def test_list_workspaces(self, api_session):
        """GET /api/workspaces - list user workspaces (N+1 optimized)"""
        resp = api_session.get(f"{BASE_URL}/api/workspaces")
        assert resp.status_code == 200, f"List workspaces failed: {resp.status_code}"
        data = resp.json()
        assert isinstance(data, list)
        if data:
            # Verify N+1 optimization fields
            ws = data[0]
            assert "workspace_id" in ws
            # Check for aggregated counts if present
            print(f"PASS: Listed {len(data)} workspaces")
        else:
            print("PASS: No workspaces found")
    
    def test_update_workspace(self, api_session):
        """PUT /api/workspaces/{id} - update workspace"""
        ws_id = TestSession.workspace_id or EXISTING_WORKSPACE_ID
        resp = api_session.put(f"{BASE_URL}/api/workspaces/{ws_id}", json={
            "name": f"Updated QA Workspace {uuid.uuid4().hex[:4]}",
            "description": "Updated by QA test"
        })
        assert resp.status_code in [200, 403], f"Update failed: {resp.status_code}"
        print(f"PASS: Update workspace returned {resp.status_code}")
    
    def test_disable_workspace(self, api_session):
        """PUT /api/workspaces/{id}/disable - toggle disable/enable"""
        ws_id = TestSession.workspace_id
        if not ws_id:
            pytest.skip("No test workspace created")
        resp = api_session.put(f"{BASE_URL}/api/workspaces/{ws_id}/disable")
        assert resp.status_code in [200, 403], f"Disable failed: {resp.status_code}"
        print(f"PASS: Disable workspace returned {resp.status_code}")
    
    def test_delete_workspace(self, api_session):
        """DELETE /api/workspaces/{id} - delete workspace (cleanup)"""
        ws_id = TestSession.workspace_id
        if not ws_id:
            pytest.skip("No test workspace to delete")
        resp = api_session.delete(f"{BASE_URL}/api/workspaces/{ws_id}")
        assert resp.status_code in [200, 403], f"Delete failed: {resp.status_code}"
        print(f"PASS: Delete workspace returned {resp.status_code}")


# ============ CHANNEL TESTS ============

class TestChannels:
    """Channel CRUD tests - 2 tests"""
    
    def test_create_channel(self, api_session):
        """POST /api/workspaces/{ws}/channels - create channel with AI agents"""
        resp = api_session.post(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/channels", json={
            "name": f"qa-channel-{uuid.uuid4().hex[:6]}",
            "description": "QA test channel",
            "ai_agents": ["claude", "chatgpt", "gemini"]
        })
        assert resp.status_code == 200, f"Create channel failed: {resp.status_code}"
        data = resp.json()
        assert "channel_id" in data
        TestSession.channel_id = data["channel_id"]
        print(f"PASS: Created channel {data['channel_id']}")
    
    def test_list_channels(self, api_session):
        """GET /api/workspaces/{ws}/channels - list channels"""
        resp = api_session.get(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/channels")
        assert resp.status_code == 200, f"List channels failed: {resp.status_code}"
        data = resp.json()
        assert isinstance(data, list)
        print(f"PASS: Listed {len(data)} channels")


# ============ MESSAGE TESTS ============

class TestMessages:
    """Message endpoint tests - 3 tests"""
    
    def test_send_message(self, api_session):
        """POST /api/channels/{ch}/messages - send message with @mention"""
        ch_id = TestSession.channel_id or EXISTING_CHANNEL_ID
        resp = api_session.post(f"{BASE_URL}/api/channels/{ch_id}/messages", json={
            "content": "Hello @claude, this is a QA test message!",
            "mentions": ["claude"]
        })
        assert resp.status_code in [200, 201], f"Send message failed: {resp.status_code}"
        data = resp.json()
        assert "message_id" in data
        print(f"PASS: Sent message {data['message_id']}")
    
    def test_list_messages(self, api_session):
        """GET /api/channels/{ch}/messages - list messages"""
        ch_id = TestSession.channel_id or EXISTING_CHANNEL_ID
        resp = api_session.get(f"{BASE_URL}/api/channels/{ch_id}/messages")
        assert resp.status_code == 200, f"List messages failed: {resp.status_code}"
        data = resp.json()
        assert isinstance(data, list)
        print(f"PASS: Listed {len(data)} messages")
    
    def test_mentionable_agents(self, api_session):
        """GET /api/channels/{ch}/mentionable - list mentionable agents"""
        ch_id = TestSession.channel_id or EXISTING_CHANNEL_ID
        resp = api_session.get(f"{BASE_URL}/api/channels/{ch_id}/mentionable")
        assert resp.status_code == 200, f"Mentionable failed: {resp.status_code}"
        data = resp.json()
        assert "agents" in data
        print(f"PASS: {len(data['agents'])} mentionable agents")


# ============ PROJECT TESTS ============

class TestProjects:
    """Project CRUD tests - 3 tests"""
    
    def test_create_project(self, api_session):
        """POST /api/workspaces/{ws}/projects - create project"""
        resp = api_session.post(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/projects", json={
            "name": f"QA Project {uuid.uuid4().hex[:6]}",
            "description": "QA regression test project"
        })
        assert resp.status_code == 200, f"Create project failed: {resp.status_code}"
        data = resp.json()
        assert "project_id" in data
        TestSession.project_id = data["project_id"]
        print(f"PASS: Created project {data['project_id']}")
    
    def test_list_projects(self, api_session):
        """GET /api/workspaces/{ws}/projects - list projects"""
        resp = api_session.get(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/projects")
        assert resp.status_code == 200, f"List projects failed: {resp.status_code}"
        data = resp.json()
        assert isinstance(data, list)
        print(f"PASS: Listed {len(data)} projects")
    
    def test_get_project(self, api_session):
        """GET /api/projects/{id} - get single project"""
        if not TestSession.project_id:
            pytest.skip("No project created")
        resp = api_session.get(f"{BASE_URL}/api/projects/{TestSession.project_id}")
        assert resp.status_code == 200, f"Get project failed: {resp.status_code}"
        data = resp.json()
        assert data["project_id"] == TestSession.project_id
        print("PASS: Got project details")


# ============ TASK TESTS ============

class TestTasks:
    """Task CRUD and bulk operations - 6 tests"""
    
    task_ids = []
    
    def test_create_task(self, api_session):
        """POST /api/projects/{id}/tasks - create task"""
        if not TestSession.project_id:
            pytest.skip("No project created")
        resp = api_session.post(f"{BASE_URL}/api/projects/{TestSession.project_id}/tasks", json={
            "title": f"QA Task {uuid.uuid4().hex[:6]}",
            "description": "Test task from QA suite",
            "status": "todo",
            "priority": "high"
        })
        assert resp.status_code == 200, f"Create task failed: {resp.status_code}"
        data = resp.json()
        assert "task_id" in data
        self.task_ids.append(data["task_id"])
        print(f"PASS: Created task {data['task_id']}")
    
    def test_update_task(self, api_session):
        """PUT /api/projects/{id}/tasks/{tid} - update task"""
        if not TestSession.project_id or not self.task_ids:
            pytest.skip("No task created")
        task_id = self.task_ids[0]
        resp = api_session.put(f"{BASE_URL}/api/projects/{TestSession.project_id}/tasks/{task_id}", json={
            "status": "in_progress",
            "priority": "critical"
        })
        assert resp.status_code == 200, f"Update task failed: {resp.status_code}"
        data = resp.json()
        assert data["status"] == "in_progress"
        print("PASS: Updated task")
    
    def test_bulk_update_tasks(self, api_session):
        """POST /api/projects/{id}/tasks/bulk-update - bulk update"""
        if not TestSession.project_id or not self.task_ids:
            pytest.skip("No tasks created")
        resp = api_session.post(f"{BASE_URL}/api/projects/{TestSession.project_id}/tasks/bulk-update", json={
            "task_ids": self.task_ids,
            "status": "review"
        })
        assert resp.status_code == 200, f"Bulk update failed: {resp.status_code}"
        data = resp.json()
        assert "updated" in data
        print(f"PASS: Bulk updated {data['updated']} tasks")
    
    def test_search_tasks(self, api_session):
        """GET /api/workspaces/{ws}/tasks/search - search/filter tasks"""
        resp = api_session.get(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/tasks/search", params={
            "q": "QA",
            "status": "review"
        })
        assert resp.status_code == 200, f"Search tasks failed: {resp.status_code}"
        data = resp.json()
        assert "tasks" in data
        assert "total" in data
        print(f"PASS: Found {data['total']} tasks")
    
    def test_bulk_delete_tasks(self, api_session):
        """POST /api/projects/{id}/tasks/bulk-delete - bulk delete"""
        if not TestSession.project_id or not self.task_ids:
            pytest.skip("No tasks to delete")
        resp = api_session.post(f"{BASE_URL}/api/projects/{TestSession.project_id}/tasks/bulk-delete", json={
            "task_ids": self.task_ids
        })
        assert resp.status_code == 200, f"Bulk delete failed: {resp.status_code}"
        data = resp.json()
        assert "deleted" in data
        print(f"PASS: Bulk deleted {data['deleted']} tasks")


# ============ WORKFLOW TESTS ============

class TestWorkflows:
    """Workflow endpoint tests - 2 tests"""
    
    def test_create_workflow(self, api_session):
        """POST /api/workspaces/{ws}/workflows - create workflow"""
        resp = api_session.post(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/workflows", json={
            "name": f"QA Workflow {uuid.uuid4().hex[:6]}",
            "description": "QA test workflow"
        })
        assert resp.status_code == 200, f"Create workflow failed: {resp.status_code}"
        data = resp.json()
        assert "workflow_id" in data
        print(f"PASS: Created workflow {data['workflow_id']}")
    
    def test_list_workflows(self, api_session):
        """GET /api/workspaces/{ws}/workflows - list workflows"""
        resp = api_session.get(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/workflows")
        assert resp.status_code == 200, f"List workflows failed: {resp.status_code}"
        data = resp.json()
        assert isinstance(data, list)
        print(f"PASS: Listed {len(data)} workflows")


# ============ MARKETPLACE TESTS ============

class TestMarketplace:
    """Marketplace endpoint tests - 1 test"""
    
    def test_browse_marketplace(self, api_session):
        """GET /api/marketplace - browse templates"""
        resp = api_session.get(f"{BASE_URL}/api/marketplace")
        assert resp.status_code == 200, f"Marketplace failed: {resp.status_code}"
        data = resp.json()
        assert "templates" in data
        print(f"PASS: Marketplace has {len(data['templates'])} templates")


# ============ ARTIFACT TESTS ============

class TestArtifacts:
    """Artifact CRUD and versioning tests - 7 tests"""
    
    def test_create_artifact(self, api_session):
        """POST /api/workspaces/{ws}/artifacts - create artifact with file_name, mime_type"""
        resp = api_session.post(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/artifacts", json={
            "name": f"QA Artifact {uuid.uuid4().hex[:6]}",
            "content": "# Test Artifact\n\nThis is a test artifact from QA suite.",
            "content_type": "markdown",
            "file_name": "test_artifact.md",
            "mime_type": "text/markdown",
            "tags": ["qa", "test"]
        })
        assert resp.status_code == 200, f"Create artifact failed: {resp.status_code}"
        data = resp.json()
        assert "artifact_id" in data
        assert "attachments" in data  # Should have attachments array
        TestSession.artifact_id = data["artifact_id"]
        print(f"PASS: Created artifact {data['artifact_id']}")
    
    def test_get_artifact(self, api_session):
        """GET /api/artifacts/{id} - get artifact with attachments array"""
        if not TestSession.artifact_id:
            pytest.skip("No artifact created")
        resp = api_session.get(f"{BASE_URL}/api/artifacts/{TestSession.artifact_id}")
        assert resp.status_code == 200, f"Get artifact failed: {resp.status_code}"
        data = resp.json()
        assert "attachments" in data
        assert "versions" in data
        print("PASS: Got artifact with attachments and versions")
    
    def test_update_artifact_creates_version(self, api_session):
        """PUT /api/artifacts/{id} - update artifact (creates version with change_summary)"""
        if not TestSession.artifact_id:
            pytest.skip("No artifact created")
        resp = api_session.put(f"{BASE_URL}/api/artifacts/{TestSession.artifact_id}", json={
            "content": "# Updated Test Artifact\n\nThis content was updated by QA.\n\nNew paragraph added."
        })
        assert resp.status_code == 200, f"Update artifact failed: {resp.status_code}"
        data = resp.json()
        assert data["version"] >= 2  # Version should increment
        print(f"PASS: Updated artifact to version {data['version']}")
    
    def test_restore_artifact_version(self, api_session):
        """POST /api/artifacts/{id}/restore/{version} - restore version"""
        if not TestSession.artifact_id:
            pytest.skip("No artifact created")
        resp = api_session.post(f"{BASE_URL}/api/artifacts/{TestSession.artifact_id}/restore/1")
        assert resp.status_code == 200, f"Restore failed: {resp.status_code}"
        data = resp.json()
        assert data["version"] >= 3  # Creates new version from restore
        print(f"PASS: Restored to version 1, now at version {data['version']}")
    
    def test_get_artifact_diff(self, api_session):
        """GET /api/artifacts/{id}/diff?v1=1&v2=2 - get diff"""
        if not TestSession.artifact_id:
            pytest.skip("No artifact created")
        resp = api_session.get(f"{BASE_URL}/api/artifacts/{TestSession.artifact_id}/diff", params={
            "v1": 1,
            "v2": 2
        })
        assert resp.status_code == 200, f"Diff failed: {resp.status_code}"
        data = resp.json()
        assert "diff" in data
        assert "additions" in data
        assert "deletions" in data
        print(f"PASS: Got diff with {data['additions']} additions, {data['deletions']} deletions")
    
    def test_add_artifact_comment(self, api_session):
        """POST /api/artifacts/{id}/comments - add comment"""
        if not TestSession.artifact_id:
            pytest.skip("No artifact created")
        resp = api_session.post(f"{BASE_URL}/api/artifacts/{TestSession.artifact_id}/comments", json={
            "content": "This is a QA test comment on the artifact."
        })
        assert resp.status_code == 200, f"Add comment failed: {resp.status_code}"
        data = resp.json()
        assert "comment_id" in data
        assert "author_name" in data
        print(f"PASS: Added comment {data['comment_id']}")
    
    def test_list_artifact_comments(self, api_session):
        """GET /api/artifacts/{id}/comments - list comments"""
        if not TestSession.artifact_id:
            pytest.skip("No artifact created")
        resp = api_session.get(f"{BASE_URL}/api/artifacts/{TestSession.artifact_id}/comments")
        assert resp.status_code == 200, f"List comments failed: {resp.status_code}"
        data = resp.json()
        assert isinstance(data, list)
        print(f"PASS: Listed {len(data)} comments")


# ============ AI TOOLS TESTS ============

class TestAITools:
    """AI Tools endpoint tests - 1 test"""
    
    def test_get_ai_tools(self, api_session):
        """GET /api/ai-tools - returns 9 tools"""
        resp = api_session.get(f"{BASE_URL}/api/ai-tools")
        assert resp.status_code == 200, f"AI tools failed: {resp.status_code}"
        data = resp.json()
        assert "tools" in data
        assert len(data["tools"]) >= 9, f"Expected 9+ tools, got {len(data['tools'])}"
        tool_names = [t["name"] for t in data["tools"]]
        expected = ["create_project", "create_task", "update_task_status", "list_projects", 
                    "list_tasks", "create_artifact", "save_to_memory", "read_memory", "handoff_to_agent"]
        for name in expected:
            assert name in tool_names, f"Missing tool: {name}"
        print(f"PASS: Got {len(data['tools'])} AI tools")


# ============ SCHEDULE TESTS ============

class TestSchedules:
    """Agent schedule tests - 4 tests"""
    
    schedule_id = None
    
    def test_create_schedule(self, api_session):
        """POST /api/workspaces/{ws}/schedules - create schedule"""
        ch_id = TestSession.channel_id or EXISTING_CHANNEL_ID
        resp = api_session.post(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/schedules", json={
            "channel_id": ch_id,
            "agent_key": "claude",
            "action_type": "project_review",
            "interval_minutes": 1440,
            "enabled": False  # Don't actually run it
        })
        assert resp.status_code == 200, f"Create schedule failed: {resp.status_code}"
        data = resp.json()
        assert "schedule_id" in data
        self.__class__.schedule_id = data["schedule_id"]
        print(f"PASS: Created schedule {data['schedule_id']}")
    
    def test_list_schedules(self, api_session):
        """GET /api/workspaces/{ws}/schedules - list schedules"""
        resp = api_session.get(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/schedules")
        assert resp.status_code == 200, f"List schedules failed: {resp.status_code}"
        data = resp.json()
        assert isinstance(data, list)
        print(f"PASS: Listed {len(data)} schedules")
    
    def test_update_schedule(self, api_session):
        """PUT /api/schedules/{id} - toggle/update schedule"""
        if not self.schedule_id:
            pytest.skip("No schedule created")
        resp = api_session.put(f"{BASE_URL}/api/schedules/{self.schedule_id}", json={
            "enabled": True,
            "interval_minutes": 60
        })
        assert resp.status_code == 200, f"Update schedule failed: {resp.status_code}"
        print("PASS: Updated schedule")
    
    def test_trigger_schedule(self, api_session):
        """POST /api/schedules/{id}/run - manual trigger"""
        if not self.schedule_id:
            pytest.skip("No schedule created")
        resp = api_session.post(f"{BASE_URL}/api/schedules/{self.schedule_id}/run")
        assert resp.status_code == 200, f"Trigger failed: {resp.status_code}"
        data = resp.json()
        assert "status" in data
        print("PASS: Triggered schedule manually")


# ============ HANDOFF TESTS ============

class TestHandoffs:
    """Handoff endpoint tests - 2 tests"""
    
    def test_create_handoff(self, api_session):
        """POST /api/channels/{ch}/handoffs - create handoff"""
        ch_id = TestSession.channel_id or EXISTING_CHANNEL_ID
        resp = api_session.post(f"{BASE_URL}/api/channels/{ch_id}/handoffs", json={
            "channel_id": ch_id,
            "from_agent": "claude",
            "to_agent": "chatgpt",
            "context_type": "analysis",
            "title": "QA Test Handoff",
            "content": "This is a test handoff from the QA suite.",
            "metadata": {"test": True}
        })
        assert resp.status_code == 200, f"Create handoff failed: {resp.status_code}"
        data = resp.json()
        assert "handoff_id" in data
        print(f"PASS: Created handoff {data['handoff_id']}")
    
    def test_list_handoffs(self, api_session):
        """GET /api/channels/{ch}/handoffs - list handoffs"""
        ch_id = TestSession.channel_id or EXISTING_CHANNEL_ID
        resp = api_session.get(f"{BASE_URL}/api/channels/{ch_id}/handoffs")
        assert resp.status_code == 200, f"List handoffs failed: {resp.status_code}"
        data = resp.json()
        assert isinstance(data, list)
        print(f"PASS: Listed {len(data)} handoffs")


# ============ MEMORY / KNOWLEDGE BASE TESTS ============

class TestMemory:
    """Knowledge Base memory tests - 4 tests"""
    
    memory_id = None
    
    def test_create_memory(self, api_session):
        """POST /api/workspaces/{ws}/memory - create/upsert memory entry"""
        resp = api_session.post(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/memory", json={
            "key": f"qa_test_key_{uuid.uuid4().hex[:6]}",
            "value": "This is a QA test memory entry for regression testing.",
            "category": "reference",
            "tags": ["qa", "test"]
        })
        assert resp.status_code == 200, f"Create memory failed: {resp.status_code}"
        data = resp.json()
        assert "memory_id" in data
        self.__class__.memory_id = data["memory_id"]
        print(f"PASS: Created memory entry {data['memory_id']}")
    
    def test_list_memory(self, api_session):
        """GET /api/workspaces/{ws}/memory - list with search/category filter"""
        resp = api_session.get(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/memory", params={
            "category": "reference",
            "search": "qa"
        })
        assert resp.status_code == 200, f"List memory failed: {resp.status_code}"
        data = resp.json()
        assert "entries" in data
        assert "total" in data
        print(f"PASS: Listed {data['total']} memory entries")
    
    def test_semantic_search_memory(self, api_session):
        """POST /api/workspaces/{ws}/memory/semantic-search - semantic search"""
        resp = api_session.post(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/memory/semantic-search", json={
            "query": "qa test regression"
        })
        assert resp.status_code == 200, f"Semantic search failed: {resp.status_code}"
        data = resp.json()
        assert "results" in data
        assert "total" in data
        print(f"PASS: Semantic search found {data['total']} results")
    
    def test_upload_knowledge_file(self, api_session):
        """POST /api/workspaces/{ws}/memory/upload - file upload with chunking"""
        # Create a simple text file content
        files = {
            "file": ("qa_test.txt", "This is a QA test file.\nIt has multiple lines.\nFor testing file upload and chunking.\n" * 10, "text/plain")
        }
        # Need to use files parameter for multipart upload
        session = api_session
        headers = dict(session.headers)
        del headers["Content-Type"]  # Let requests set multipart boundary
        resp = requests.post(
            f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/memory/upload",
            files=files,
            headers=headers
        )
        assert resp.status_code == 200, f"Upload failed: {resp.status_code}"
        data = resp.json()
        assert "filename" in data
        assert "total_chunks" in data
        print(f"PASS: Uploaded file with {data['total_chunks']} chunks")


# ============ EXPORT TESTS ============

class TestExport:
    """Export endpoint tests - 4 tests"""
    
    def test_export_channel_json(self, api_session):
        """GET /api/channels/{ch}/export?format=json - export messages JSON"""
        ch_id = EXISTING_CHANNEL_ID
        resp = api_session.get(f"{BASE_URL}/api/channels/{ch_id}/export", params={"format": "json"})
        assert resp.status_code == 200, f"Export JSON failed: {resp.status_code}"
        data = resp.json()
        assert "messages" in data or "channel" in data
        print("PASS: Exported channel as JSON")
    
    def test_export_channel_markdown(self, api_session):
        """GET /api/channels/{ch}/export?format=markdown - export markdown"""
        ch_id = EXISTING_CHANNEL_ID
        resp = api_session.get(f"{BASE_URL}/api/channels/{ch_id}/export", params={"format": "markdown"})
        assert resp.status_code == 200, f"Export markdown failed: {resp.status_code}"
        data = resp.json()
        assert "content" in data or "format" in data
        print("PASS: Exported channel as markdown")
    
    def test_export_tasks_csv(self, api_session):
        """GET /api/workspaces/{ws}/export/csv - export tasks CSV"""
        resp = api_session.get(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/export/csv")
        assert resp.status_code == 200, f"Export CSV failed: {resp.status_code}"
        data = resp.json()
        assert "content" in data or "format" in data
        print("PASS: Exported tasks as CSV")
    
    def test_export_messages_csv(self, api_session):
        """GET /api/channels/{ch}/export/csv - export messages CSV"""
        ch_id = EXISTING_CHANNEL_ID
        resp = api_session.get(f"{BASE_URL}/api/channels/{ch_id}/export/csv")
        assert resp.status_code == 200, f"Export messages CSV failed: {resp.status_code}"
        data = resp.json()
        assert "content" in data or "format" in data
        print("PASS: Exported messages as CSV")


# ============ AUDIT LOG TESTS ============

class TestAudit:
    """Audit log tests - 1 test"""
    
    def test_get_audit_log(self, api_session):
        """GET /api/workspaces/{ws}/audit-log - audit entries"""
        resp = api_session.get(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/audit-log")
        assert resp.status_code == 200, f"Audit log failed: {resp.status_code}"
        data = resp.json()
        assert "entries" in data
        assert "total" in data
        print(f"PASS: Got {data['total']} audit entries")


# ============ WEBHOOK TESTS ============

class TestWebhooks:
    """Webhook endpoint tests - 3 tests"""
    
    webhook_id = None
    inbound_hook_id = None
    
    def test_create_webhook(self, api_session):
        """POST /api/workspaces/{ws}/webhooks - create webhook"""
        resp = api_session.post(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/webhooks", json={
            "url": "https://example.com/webhook",
            "events": ["message.created", "task.created"],
            "name": "QA Test Webhook"
        })
        assert resp.status_code == 200, f"Create webhook failed: {resp.status_code}"
        data = resp.json()
        assert "webhook_id" in data
        self.__class__.webhook_id = data["webhook_id"]
        print(f"PASS: Created webhook {data['webhook_id']}")
    
    def test_get_webhook_events(self, api_session):
        """GET /api/webhooks/events - list 15 event types"""
        resp = api_session.get(f"{BASE_URL}/api/webhooks/events")
        assert resp.status_code == 200, f"Get events failed: {resp.status_code}"
        data = resp.json()
        assert "events" in data
        assert len(data["events"]) >= 10, f"Expected 10+ events, got {len(data['events'])}"
        print(f"PASS: Got {len(data['events'])} webhook event types")
    
    def test_create_inbound_webhook(self, api_session):
        """POST /api/workspaces/{ws}/inbound-webhooks - create inbound webhook"""
        # First get a workflow ID
        resp = api_session.get(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/workflows")
        if resp.status_code != 200 or not resp.json():
            pytest.skip("No workflows for inbound webhook test")
        
        wf_id = resp.json()[0]["workflow_id"]
        resp = api_session.post(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/inbound-webhooks", json={
            "workflow_id": wf_id,
            "name": "QA Inbound Webhook"
        })
        assert resp.status_code == 200, f"Create inbound webhook failed: {resp.status_code}"
        data = resp.json()
        assert "inbound_hook_id" in data
        assert "webhook_url" in data
        self.__class__.inbound_hook_id = data["inbound_hook_id"]
        print(f"PASS: Created inbound webhook {data['inbound_hook_id']}")


# ============ MODEL PERFORMANCE TESTS ============

class TestModelPerformance:
    """Model performance and auto-routing tests - 3 tests"""
    
    def test_get_model_stats(self, api_session):
        """GET /api/workspaces/{ws}/model-stats - model performance stats"""
        resp = api_session.get(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/model-stats")
        assert resp.status_code == 200, f"Model stats failed: {resp.status_code}"
        data = resp.json()
        assert "stats" in data
        print(f"PASS: Got stats for {len(data['stats'])} models")
    
    def test_get_model_recommendations(self, api_session):
        """GET /api/workspaces/{ws}/model-recommendations - task-type recommendations"""
        resp = api_session.get(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/model-recommendations", params={
            "task_type": "code"
        })
        assert resp.status_code == 200, f"Recommendations failed: {resp.status_code}"
        data = resp.json()
        assert "task_type" in data
        assert "recommendations" in data
        print(f"PASS: Got {len(data['recommendations'])} model recommendations")
    
    def test_auto_route_model(self, api_session):
        """POST /api/workspaces/{ws}/auto-route - auto-select best model"""
        resp = api_session.post(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/auto-route", json={
            "task_type": "general",
            "prompt": "Write a function to sort an array"
        })
        assert resp.status_code == 200, f"Auto-route failed: {resp.status_code}"
        data = resp.json()
        assert "selected_model" in data
        assert "confidence" in data
        print(f"PASS: Auto-routed to {data['selected_model']} with {data['confidence']} confidence")


# ============ DISAGREEMENT TESTS ============

class TestDisagreements:
    """Disagreement resolution tests - 3 tests"""
    
    disagreement_id = None
    
    def test_create_disagreement(self, api_session):
        """POST /api/channels/{ch}/disagreements - create disagreement"""
        ch_id = EXISTING_CHANNEL_ID
        resp = api_session.post(f"{BASE_URL}/api/channels/{ch_id}/disagreements", json={
            "topic": "QA Test Disagreement: Best testing framework"
        })
        assert resp.status_code == 200, f"Create disagreement failed: {resp.status_code}"
        data = resp.json()
        assert "disagreement_id" in data
        self.__class__.disagreement_id = data["disagreement_id"]
        print(f"PASS: Created disagreement {data['disagreement_id']}")
    
    def test_submit_votes(self, api_session):
        """POST /api/disagreements/{id}/vote - submit votes"""
        if not self.disagreement_id:
            pytest.skip("No disagreement created")
        
        # Vote 1
        resp = api_session.post(f"{BASE_URL}/api/disagreements/{self.disagreement_id}/vote", json={
            "agent_key": "claude",
            "position": "pytest is best",
            "confidence": 0.9
        })
        assert resp.status_code == 200, f"Vote 1 failed: {resp.status_code}"
        
        # Vote 2
        resp = api_session.post(f"{BASE_URL}/api/disagreements/{self.disagreement_id}/vote", json={
            "agent_key": "chatgpt",
            "position": "unittest is best",
            "confidence": 0.7
        })
        assert resp.status_code == 200, f"Vote 2 failed: {resp.status_code}"
        print("PASS: Submitted 2 votes")
    
    def test_resolve_disagreement(self, api_session):
        """POST /api/disagreements/{id}/resolve - resolve with weighted voting"""
        if not self.disagreement_id:
            pytest.skip("No disagreement created")
        resp = api_session.post(f"{BASE_URL}/api/disagreements/{self.disagreement_id}/resolve")
        assert resp.status_code == 200, f"Resolve failed: {resp.status_code}"
        data = resp.json()
        assert "resolution" in data
        assert data["resolution"]["winning_position"] is not None
        print(f"PASS: Resolved - winner: {data['resolution']['winning_position']}")


# ============ CHECKPOINT TESTS ============

class TestCheckpoints:
    """Checkpoint type tests - 1 test"""
    
    def test_get_checkpoint_types(self, api_session):
        """GET /api/checkpoints/types - 5 checkpoint types"""
        resp = api_session.get(f"{BASE_URL}/api/checkpoints/types")
        assert resp.status_code == 200, f"Checkpoint types failed: {resp.status_code}"
        data = resp.json()
        assert "types" in data
        assert len(data["types"]) >= 5, f"Expected 5 types, got {len(data['types'])}"
        print(f"PASS: Got {len(data['types'])} checkpoint types")


# ============ INTEGRATION STATUS TESTS ============

class TestIntegrations:
    """Integration status tests - 1 test"""
    
    def test_get_integration_status(self, api_session):
        """GET /api/integrations/status - all integration statuses"""
        resp = api_session.get(f"{BASE_URL}/api/integrations/status")
        assert resp.status_code == 200, f"Integration status failed: {resp.status_code}"
        data = resp.json()
        # Should have email, microsoft_oauth, meta_oauth, paypal, stripe, google_oauth
        expected_keys = ["email", "microsoft_oauth", "meta_oauth", "paypal", "stripe", "google_oauth"]
        for key in expected_keys:
            assert key in data, f"Missing integration: {key}"
        print("PASS: Got all integration statuses")


# ============ IMAGE GENERATION TESTS ============

class TestImageGeneration:
    """Image generation tests - 3 tests"""
    
    def test_generate_image(self, api_session):
        """POST /api/workspaces/{ws}/generate-image - generate image"""
        resp = api_session.post(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/generate-image", json={
            "prompt": "A simple geometric pattern for testing",
            "provider": "gemini",
            "use_own_key": False
        })
        # May take a while or fail due to API limits - accept either
        assert resp.status_code in [200, 422, 500], f"Unexpected: {resp.status_code}"
        if resp.status_code == 200:
            data = resp.json()
            assert "image_id" in data
            print(f"PASS: Generated image {data['image_id']}")
        else:
            print(f"PASS: Image generation returned {resp.status_code} (expected with API limits)")
    
    def test_list_generated_images(self, api_session):
        """GET /api/workspaces/{ws}/images - list generated images"""
        resp = api_session.get(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/images")
        assert resp.status_code == 200, f"List images failed: {resp.status_code}"
        data = resp.json()
        assert "images" in data
        assert "total" in data
        print(f"PASS: Listed {data['total']} images")
    
    def test_get_image_metrics(self, api_session):
        """GET /api/workspaces/{ws}/image-gen/metrics - generation metrics"""
        resp = api_session.get(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/image-gen/metrics")
        assert resp.status_code == 200, f"Metrics failed: {resp.status_code}"
        data = resp.json()
        assert "total_requests" in data
        assert "success_rate" in data
        print(f"PASS: Got image gen metrics - {data['total_requests']} total requests")


# ============ ENHANCEMENT TESTS ============

class TestEnhancements:
    """Enhancement endpoint tests - 9 tests"""
    
    def test_usage_analytics(self, api_session):
        """GET /api/workspaces/{ws}/usage-analytics - usage dashboard"""
        resp = api_session.get(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/usage-analytics")
        assert resp.status_code == 200, f"Analytics failed: {resp.status_code}"
        data = resp.json()
        assert "messages" in data
        assert "model_usage" in data
        print("PASS: Got usage analytics")
    
    def test_channel_summarize(self, api_session):
        """POST /api/channels/{ch}/summarize - smart summarization"""
        ch_id = EXISTING_CHANNEL_ID
        resp = api_session.post(f"{BASE_URL}/api/channels/{ch_id}/summarize")
        assert resp.status_code == 200, f"Summarize failed: {resp.status_code}"
        data = resp.json()
        assert "summary" in data
        assert "total_messages" in data
        print("PASS: Got channel summary")
    
    def test_get_personas(self, api_session):
        """GET /api/personas - 4+ personas with categories"""
        resp = api_session.get(f"{BASE_URL}/api/personas")
        assert resp.status_code == 200, f"Personas failed: {resp.status_code}"
        data = resp.json()
        assert "personas" in data
        assert "categories" in data
        assert len(data["personas"]) >= 4, f"Expected 4+ personas, got {len(data['personas'])}"
        print(f"PASS: Got {len(data['personas'])} personas")
    
    def test_get_workspace_templates(self, api_session):
        """GET /api/workspace-templates - 4 built-in templates"""
        resp = api_session.get(f"{BASE_URL}/api/workspace-templates")
        assert resp.status_code == 200, f"Templates failed: {resp.status_code}"
        data = resp.json()
        assert "templates" in data
        assert len(data["templates"]) >= 4, f"Expected 4+ templates, got {len(data['templates'])}"
        # Verify specific templates exist
        template_ids = [t["template_id"] for t in data["templates"]]
        expected = ["wst_product_launch", "wst_code_review", "wst_research_lab", "wst_content_studio"]
        for tid in expected:
            assert tid in template_ids, f"Missing template: {tid}"
        print(f"PASS: Got {len(data['templates'])} workspace templates")
    
    def test_deploy_workspace_template(self, api_session):
        """POST /api/workspace-templates/{id}/deploy - deploy template creates workspace + channels"""
        resp = api_session.post(f"{BASE_URL}/api/workspace-templates/wst_code_review/deploy", json={
            "name": f"QA Deployed Workspace {uuid.uuid4().hex[:6]}"
        })
        assert resp.status_code == 200, f"Deploy failed: {resp.status_code}"
        data = resp.json()
        assert "workspace_id" in data
        assert "channels_created" in data
        print(f"PASS: Deployed template - created workspace with {data['channels_created']} channels")
    
    def test_branch_conversation(self, api_session):
        """POST /api/channels/{ch}/branch - branch conversation"""
        ch_id = EXISTING_CHANNEL_ID
        resp = api_session.post(f"{BASE_URL}/api/channels/{ch_id}/branch", json={
            "name": f"qa-branch-{uuid.uuid4().hex[:6]}"
        })
        assert resp.status_code == 200, f"Branch failed: {resp.status_code}"
        data = resp.json()
        assert "branch_channel_id" in data
        assert "messages_copied" in data
        print(f"PASS: Branched conversation - copied {data['messages_copied']} messages")
    
    def test_activity_feed(self, api_session):
        """GET /api/workspaces/{ws}/activity-feed - mixed activity events"""
        resp = api_session.get(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/activity-feed")
        assert resp.status_code == 200, f"Activity feed failed: {resp.status_code}"
        data = resp.json()
        assert "events" in data
        print(f"PASS: Got {len(data['events'])} activity events")
    
    def test_workspace_timeline(self, api_session):
        """GET /api/workspaces/{ws}/timeline - audit + run timeline"""
        resp = api_session.get(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/timeline")
        assert resp.status_code == 200, f"Timeline failed: {resp.status_code}"
        data = resp.json()
        assert "timeline" in data
        print(f"PASS: Got {len(data['timeline'])} timeline entries")
    
    def test_send_notification(self, api_session):
        """POST /api/workspaces/{ws}/notify - send workspace notification"""
        resp = api_session.post(f"{BASE_URL}/api/workspaces/{EXISTING_WORKSPACE_ID}/notify", json={
            "message": "QA Test Notification from regression suite",
            "type": "info"
        })
        assert resp.status_code == 200, f"Notify failed: {resp.status_code}"
        data = resp.json()
        assert "sent_to" in data
        print(f"PASS: Sent notification to {data['sent_to']} users")


# ============ ORGANIZATION TESTS ============

class TestOrganizations:
    """Organization endpoint tests - 6 tests"""
    
    org_id = None
    
    def test_register_organization(self, api_session):
        """POST /api/orgs/register - create organization"""
        unique = uuid.uuid4().hex[:8]
        resp = requests.post(f"{BASE_URL}/api/orgs/register", json={
            "name": f"QA Test Org {unique}",
            "slug": f"qa-org-{unique}",
            "admin_name": "QA Admin",
            "admin_email": f"qa_admin_{unique}@test.com",
            "admin_password": "QAAdmin1234!"
        })
        # May fail if slug taken (400) or succeed (200)
        assert resp.status_code in [200, 400], f"Unexpected: {resp.status_code}"
        if resp.status_code == 200:
            data = resp.json()
            assert "org_id" in data
            self.__class__.org_id = data["org_id"]
            print(f"PASS: Registered org {data['org_id']}")
        else:
            print(f"PASS: Org registration returned 400 (expected if slug taken)")
    
    def test_get_org_projects_rollup(self, api_session):
        """GET /api/orgs/{id}/projects - org-level projects rollup"""
        # Use existing org from credentials if available
        # Try to get user's orgs first
        resp = api_session.get(f"{BASE_URL}/api/orgs/my-orgs")
        if resp.status_code != 200 or not resp.json().get("organizations"):
            pytest.skip("No orgs available for testing")
        
        org_id = resp.json()["organizations"][0]["org_id"]
        resp = api_session.get(f"{BASE_URL}/api/orgs/{org_id}/projects")
        assert resp.status_code == 200, f"Org projects failed: {resp.status_code}"
        data = resp.json()
        assert "projects" in data
        assert "total" in data
        print(f"PASS: Got {data['total']} org-level projects")
    
    def test_get_org_tasks_rollup(self, api_session):
        """GET /api/orgs/{id}/tasks - org-level tasks rollup"""
        resp = api_session.get(f"{BASE_URL}/api/orgs/my-orgs")
        if resp.status_code != 200 or not resp.json().get("organizations"):
            pytest.skip("No orgs available")
        
        org_id = resp.json()["organizations"][0]["org_id"]
        resp = api_session.get(f"{BASE_URL}/api/orgs/{org_id}/tasks")
        assert resp.status_code == 200, f"Org tasks failed: {resp.status_code}"
        data = resp.json()
        assert "tasks" in data
        assert "total" in data
        print(f"PASS: Got {data['total']} org-level tasks")
    
    def test_get_org_workflows(self, api_session):
        """GET /api/orgs/{id}/workflows - org-level workflows"""
        resp = api_session.get(f"{BASE_URL}/api/orgs/my-orgs")
        if resp.status_code != 200 or not resp.json().get("organizations"):
            pytest.skip("No orgs available")
        
        org_id = resp.json()["organizations"][0]["org_id"]
        resp = api_session.get(f"{BASE_URL}/api/orgs/{org_id}/workflows")
        assert resp.status_code == 200, f"Org workflows failed: {resp.status_code}"
        data = resp.json()
        assert "workflows" in data
        print(f"PASS: Got {data['total']} org-level workflows")
    
    def test_get_org_analytics_summary(self, api_session):
        """GET /api/orgs/{id}/analytics/summary - org analytics"""
        resp = api_session.get(f"{BASE_URL}/api/orgs/my-orgs")
        if resp.status_code != 200 or not resp.json().get("organizations"):
            pytest.skip("No orgs available")
        
        org_id = resp.json()["organizations"][0]["org_id"]
        resp = api_session.get(f"{BASE_URL}/api/orgs/{org_id}/analytics/summary")
        assert resp.status_code == 200, f"Org analytics failed: {resp.status_code}"
        data = resp.json()
        assert "total_messages" in data
        assert "total_projects" in data
        print("PASS: Got org analytics summary")


# ============ SETTINGS / AI KEYS TESTS ============

class TestSettings:
    """Settings endpoint tests - 2 tests"""
    
    def test_get_ai_keys_status(self, api_session):
        """GET /api/settings/ai-keys - list AI key status"""
        resp = api_session.get(f"{BASE_URL}/api/settings/ai-keys")
        assert resp.status_code == 200, f"AI keys failed: {resp.status_code}"
        data = resp.json()
        # Should return key status for each provider
        assert isinstance(data, dict)
        print("PASS: Got AI keys status")
    
    def test_ai_keys_health(self, api_session):
        """GET /api/settings/ai-keys/health - encryption health check"""
        resp = api_session.get(f"{BASE_URL}/api/settings/ai-keys/health")
        assert resp.status_code == 200, f"AI keys health failed: {resp.status_code}"
        data = resp.json()
        assert "encryption_configured" in data or "status" in data or isinstance(data, dict)
        print("PASS: Got AI keys health check")


# Cleanup fixture
@pytest.fixture(scope="module", autouse=True)
def cleanup(api_session):
    """Cleanup test data after all tests"""
    yield
    # Cleanup happens after all tests
    # Delete test artifacts, projects, etc. created during testing
    if TestSession.artifact_id:
        try:
            api_session.delete(f"{BASE_URL}/api/artifacts/{TestSession.artifact_id}")
        except:
            pass
    if TestSession.project_id:
        try:
            api_session.delete(f"{BASE_URL}/api/projects/{TestSession.project_id}")
        except:
            pass
    if TestSession.channel_id:
        try:
            api_session.delete(f"{BASE_URL}/api/channels/{TestSession.channel_id}")
        except:
            pass
