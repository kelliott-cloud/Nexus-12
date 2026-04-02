"""
Task Sessions API Tests
Tests for the Task Panel feature - isolated AI task sessions within a workspace
"""
import pytest
import requests
import os
import time

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials - will be created in fixture
TEST_SESSION_TOKEN = None
TEST_USER_ID = None
TEST_WORKSPACE_ID = None
TEST_CREATED_SESSION_ID = None


class TestTaskSessionSetup:
    """Setup test data"""
    
    @classmethod
    def setup_class(cls):
        """Create test user, session, and workspace via MongoDB"""
        import subprocess
        timestamp = int(time.time() * 1000)
        
        result = subprocess.run([
            'mongosh', '--quiet', '--eval', f'''
use('test_database');
var userId = 'test-task-user-{timestamp}';
var sessionToken = 'test_task_session_{timestamp}';
var workspaceId = 'ws_tasktest_{timestamp}';
db.users.insertOne({{
  user_id: userId,
  email: 'tasktest.{timestamp}@example.com',
  name: 'Task Test User',
  picture: 'https://via.placeholder.com/150',
  plan: 'pro',
  usage: {{ai_collaborations: 0, period_start: new Date().toISOString()}},
  created_at: new Date().toISOString()
}});
db.user_sessions.insertOne({{
  user_id: userId,
  session_token: sessionToken,
  expires_at: new Date(Date.now() + 7*24*60*60*1000).toISOString(),
  created_at: new Date().toISOString()
}});
db.workspaces.insertOne({{
  workspace_id: workspaceId,
  name: 'Task Session Test Workspace',
  description: 'Testing task sessions',
  owner_id: userId,
  members: [userId],
  created_at: new Date().toISOString()
}});
db.channels.insertOne({{
  channel_id: 'ch_tasktest_{timestamp}',
  workspace_id: workspaceId,
  name: 'general',
  description: 'General channel',
  ai_agents: ['claude', 'chatgpt'],
  created_by: userId,
  created_at: new Date().toISOString()
}});
print('SESSION_TOKEN=' + sessionToken);
print('USER_ID=' + userId);
print('WORKSPACE_ID=' + workspaceId);
'''
        ], capture_output=True, text=True)
        
        for line in result.stdout.strip().split('\n'):
            if 'SESSION_TOKEN=' in line:
                cls.session_token = line.split('=')[1]
            elif 'USER_ID=' in line:
                cls.user_id = line.split('=')[1]
            elif 'WORKSPACE_ID=' in line:
                cls.workspace_id = line.split('=')[1]
        
        global TEST_SESSION_TOKEN, TEST_USER_ID, TEST_WORKSPACE_ID
        TEST_SESSION_TOKEN = cls.session_token
        TEST_USER_ID = cls.user_id
        TEST_WORKSPACE_ID = cls.workspace_id
    
    def test_setup_complete(self):
        """Verify setup completed successfully"""
        assert TEST_SESSION_TOKEN is not None
        assert TEST_USER_ID is not None
        assert TEST_WORKSPACE_ID is not None
        print(f"Test setup complete: session={TEST_SESSION_TOKEN[:20]}..., workspace={TEST_WORKSPACE_ID}")


class TestTaskSessionAuth:
    """Test authentication requirements for task session endpoints"""
    
    def test_get_task_sessions_requires_auth(self):
        """GET /workspaces/{id}/task-sessions should return 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/workspaces/ws_test/task-sessions")
        assert response.status_code == 401
        print("PASS: GET task-sessions requires authentication")
    
    def test_create_task_session_requires_auth(self):
        """POST /workspaces/{id}/task-sessions should return 401 without auth"""
        response = requests.post(
            f"{BASE_URL}/api/workspaces/ws_test/task-sessions",
            json={"title": "Test", "assigned_agent": "claude", "initial_prompt": "Hello"}
        )
        assert response.status_code == 401
        print("PASS: POST task-sessions requires authentication")
    
    def test_get_task_session_messages_requires_auth(self):
        """GET /task-sessions/{id}/messages should return 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/task-sessions/ts_test/messages")
        assert response.status_code == 401
        print("PASS: GET task-session messages requires authentication")


class TestTaskSessionCRUD:
    """Test CRUD operations for task sessions"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up headers with auth"""
        self.headers = {
            "Authorization": f"Bearer {TEST_SESSION_TOKEN}",
            "Content-Type": "application/json"
        }
    
    def test_get_empty_task_sessions(self):
        """GET /workspaces/{id}/task-sessions should return empty list initially"""
        # Use different workspace to ensure empty
        import subprocess
        timestamp = int(time.time() * 1000)
        result = subprocess.run([
            'mongosh', '--quiet', '--eval', f'''
use('test_database');
var workspaceId = 'ws_empty_{timestamp}';
db.workspaces.insertOne({{
  workspace_id: workspaceId,
  name: 'Empty Test Workspace',
  description: 'Testing empty task sessions',
  owner_id: '{TEST_USER_ID}',
  members: ['{TEST_USER_ID}'],
  created_at: new Date().toISOString()
}});
print('WORKSPACE_ID=' + workspaceId);
'''
        ], capture_output=True, text=True)
        
        empty_workspace_id = None
        for line in result.stdout.strip().split('\n'):
            if 'WORKSPACE_ID=' in line:
                empty_workspace_id = line.split('=')[1]
        
        response = requests.get(
            f"{BASE_URL}/api/workspaces/{empty_workspace_id}/task-sessions",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0
        print("PASS: GET empty task sessions returns empty list")
    
    def test_create_task_session_with_claude(self):
        """POST /workspaces/{id}/task-sessions creates task with Claude agent"""
        payload = {
            "title": "TEST_Code Review Task",
            "description": "Review authentication code",
            "assigned_agent": "claude",
            "initial_prompt": "Please review my authentication implementation"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/task-sessions",
            headers=self.headers,
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "session_id" in data
        assert data["session_id"].startswith("ts_")
        assert data["title"] == payload["title"]
        assert data["description"] == payload["description"]
        assert data["status"] == "active"
        assert data["workspace_id"] == TEST_WORKSPACE_ID
        # message_count may be 0 or 1 depending on async update timing
        assert data["message_count"] in [0, 1]
        
        # Verify agent info
        assert "agent" in data
        assert data["agent"]["name"] == "Claude"
        assert data["agent"]["base_model"] == "claude"
        assert data["agent"]["is_nexus_agent"] == False
        
        print(f"PASS: Create task session - {data['session_id']}")
        
        # Store for later tests
        global TEST_CREATED_SESSION_ID
        TEST_CREATED_SESSION_ID = data["session_id"]
    
    def test_create_task_session_with_chatgpt(self):
        """POST /workspaces/{id}/task-sessions creates task with ChatGPT agent"""
        payload = {
            "title": "TEST_Feature Design",
            "description": "Design a new feature",
            "assigned_agent": "chatgpt",
            "initial_prompt": "Help me design a user notification system"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/task-sessions",
            headers=self.headers,
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["agent"]["name"] == "ChatGPT"
        assert data["agent"]["base_model"] == "chatgpt"
        print(f"PASS: Create task session with ChatGPT - {data['session_id']}")
    
    def test_create_task_session_missing_fields(self):
        """POST /workspaces/{id}/task-sessions fails with missing required fields"""
        # Missing title
        response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/task-sessions",
            headers=self.headers,
            json={"assigned_agent": "claude", "initial_prompt": "Hello"}
        )
        assert response.status_code == 422
        
        # Missing agent
        response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/task-sessions",
            headers=self.headers,
            json={"title": "Test", "initial_prompt": "Hello"}
        )
        assert response.status_code == 422
        
        # Missing initial prompt
        response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/task-sessions",
            headers=self.headers,
            json={"title": "Test", "assigned_agent": "claude"}
        )
        assert response.status_code == 422
        
        print("PASS: Create task session validates required fields")
    
    def test_create_task_session_invalid_agent(self):
        """POST /workspaces/{id}/task-sessions fails with invalid agent"""
        payload = {
            "title": "Test Invalid Agent",
            "assigned_agent": "invalid_agent_xyz",
            "initial_prompt": "Hello"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/task-sessions",
            headers=self.headers,
            json=payload
        )
        
        assert response.status_code == 400
        print("PASS: Create task session rejects invalid agent")
    
    def test_get_task_sessions_list(self):
        """GET /workspaces/{id}/task-sessions returns created sessions"""
        response = requests.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/task-sessions",
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) >= 2  # At least 2 sessions created above
        
        # Verify structure of first session
        session = data[0]
        assert "session_id" in session
        assert "title" in session
        assert "agent" in session
        assert "status" in session
        
        print(f"PASS: GET task sessions returns {len(data)} sessions")
    
    def test_get_task_session_by_id(self):
        """GET /task-sessions/{id} returns specific session"""
        if not TEST_CREATED_SESSION_ID:
            pytest.skip("No session created in previous test")
        
        response = requests.get(
            f"{BASE_URL}/api/task-sessions/{TEST_CREATED_SESSION_ID}",
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["session_id"] == TEST_CREATED_SESSION_ID
        assert "title" in data
        assert "agent" in data
        
        print(f"PASS: GET task session by ID - {TEST_CREATED_SESSION_ID}")
    
    def test_get_task_session_not_found(self):
        """GET /task-sessions/{id} returns 404 for non-existent session"""
        response = requests.get(
            f"{BASE_URL}/api/task-sessions/ts_nonexistent_12345",
            headers=self.headers
        )
        
        assert response.status_code == 404
        print("PASS: GET non-existent session returns 404")


class TestTaskSessionMessages:
    """Test message operations in task sessions"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.headers = {
            "Authorization": f"Bearer {TEST_SESSION_TOKEN}",
            "Content-Type": "application/json"
        }
    
    def test_get_task_session_messages(self):
        """GET /task-sessions/{id}/messages returns messages"""
        session_id = TEST_CREATED_SESSION_ID
        if not session_id:
            pytest.skip("No session created in previous test")
        
        response = requests.get(
            f"{BASE_URL}/api/task-sessions/{session_id}/messages",
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) >= 1  # At least the initial prompt
        
        # Verify first message is the initial prompt
        msg = data[0]
        assert "message_id" in msg
        assert msg["sender_type"] == "human"
        assert "content" in msg
        
        print(f"PASS: GET messages returns {len(data)} messages")
    
    def test_send_message_to_task_session(self):
        """POST /task-sessions/{id}/messages sends a follow-up message"""
        session_id = TEST_CREATED_SESSION_ID
        if not session_id:
            pytest.skip("No session created in previous test")
        
        payload = {"content": "Can you also check the error handling?"}
        
        response = requests.post(
            f"{BASE_URL}/api/task-sessions/{session_id}/messages",
            headers=self.headers,
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "message_id" in data
        assert data["message_id"].startswith("tsm_")
        assert data["sender_type"] == "human"
        assert data["content"] == payload["content"]
        
        print(f"PASS: Send message - {data['message_id']}")
    
    def test_send_empty_message_fails(self):
        """POST /task-sessions/{id}/messages fails with empty content"""
        session_id = TEST_CREATED_SESSION_ID
        if not session_id:
            pytest.skip("No session created in previous test")
        
        response = requests.post(
            f"{BASE_URL}/api/task-sessions/{session_id}/messages",
            headers=self.headers,
            json={"content": ""}
        )
        
        assert response.status_code == 422
        print("PASS: Empty message rejected")


class TestTaskSessionStatus:
    """Test status operations for task sessions"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.headers = {
            "Authorization": f"Bearer {TEST_SESSION_TOKEN}",
            "Content-Type": "application/json"
        }
    
    def test_get_task_session_status(self):
        """GET /task-sessions/{id}/status returns thinking status"""
        session_id = TEST_CREATED_SESSION_ID
        if not session_id:
            pytest.skip("No session created in previous test")
        
        response = requests.get(
            f"{BASE_URL}/api/task-sessions/{session_id}/status",
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "is_thinking" in data
        assert isinstance(data["is_thinking"], bool)
        
        print(f"PASS: GET status - is_thinking={data['is_thinking']}")
    
    def test_complete_task_session(self):
        """PUT /task-sessions/{id}/complete marks session as completed"""
        # Create a new session to complete
        payload = {
            "title": "TEST_Task To Complete",
            "assigned_agent": "claude",
            "initial_prompt": "Quick task"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/task-sessions",
            headers=self.headers,
            json=payload
        )
        
        session_id = create_response.json()["session_id"]
        
        # Complete the session
        response = requests.put(
            f"{BASE_URL}/api/task-sessions/{session_id}/complete",
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "completed"
        assert "completed_at" in data
        
        print(f"PASS: Complete task session - {session_id}")
    
    def test_toggle_task_session_status(self):
        """PUT /task-sessions/{id}/status toggles between active/paused"""
        # Create a new session
        payload = {
            "title": "TEST_Task To Toggle",
            "assigned_agent": "chatgpt",
            "initial_prompt": "Toggle test"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/task-sessions",
            headers=self.headers,
            json=payload
        )
        
        session_id = create_response.json()["session_id"]
        
        # Toggle to paused
        response = requests.put(
            f"{BASE_URL}/api/task-sessions/{session_id}/status",
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "paused"
        
        # Toggle back to active
        response = requests.put(
            f"{BASE_URL}/api/task-sessions/{session_id}/status",
            headers=self.headers
        )
        
        data = response.json()
        assert data["status"] == "active"
        
        print(f"PASS: Toggle task session status - {session_id}")


class TestTaskSessionDelete:
    """Test delete operations for task sessions"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.headers = {
            "Authorization": f"Bearer {TEST_SESSION_TOKEN}",
            "Content-Type": "application/json"
        }
    
    def test_delete_task_session(self):
        """DELETE /task-sessions/{id} removes session and messages"""
        # Create a session to delete
        payload = {
            "title": "TEST_Task To Delete",
            "assigned_agent": "claude",
            "initial_prompt": "This will be deleted"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/task-sessions",
            headers=self.headers,
            json=payload
        )
        
        session_id = create_response.json()["session_id"]
        
        # Delete the session
        response = requests.delete(
            f"{BASE_URL}/api/task-sessions/{session_id}",
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Task session deleted"
        
        # Verify session no longer exists
        get_response = requests.get(
            f"{BASE_URL}/api/task-sessions/{session_id}",
            headers=self.headers
        )
        assert get_response.status_code == 404
        
        print(f"PASS: Delete task session - {session_id}")
    
    def test_delete_nonexistent_session(self):
        """DELETE /task-sessions/{id} returns 404 for non-existent session"""
        response = requests.delete(
            f"{BASE_URL}/api/task-sessions/ts_nonexistent_xyz",
            headers=self.headers
        )
        
        assert response.status_code == 404
        print("PASS: Delete non-existent session returns 404")


class TestTaskSessionRun:
    """Test running AI agent on task sessions"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.headers = {
            "Authorization": f"Bearer {TEST_SESSION_TOKEN}",
            "Content-Type": "application/json"
        }
    
    def test_run_task_agent(self):
        """POST /task-sessions/{id}/run triggers AI agent"""
        session_id = TEST_CREATED_SESSION_ID
        if not session_id:
            pytest.skip("No session created in previous test")
        
        response = requests.post(
            f"{BASE_URL}/api/task-sessions/{session_id}/run",
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "started"
        
        print(f"PASS: Run task agent - {session_id}")
    
    def test_run_task_agent_on_completed_session(self):
        """POST /task-sessions/{id}/run fails on completed session"""
        # Create and complete a session
        payload = {
            "title": "TEST_Completed Task Run Test",
            "assigned_agent": "claude",
            "initial_prompt": "Test"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/task-sessions",
            headers=self.headers,
            json=payload
        )
        
        session_id = create_response.json()["session_id"]
        
        # Complete it
        requests.put(
            f"{BASE_URL}/api/task-sessions/{session_id}/complete",
            headers=self.headers
        )
        
        # Try to run
        response = requests.post(
            f"{BASE_URL}/api/task-sessions/{session_id}/run",
            headers=self.headers
        )
        
        assert response.status_code == 400
        print("PASS: Run on completed session returns 400")


class TestTaskSessionFiltering:
    """Test filtering task sessions by status"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.headers = {
            "Authorization": f"Bearer {TEST_SESSION_TOKEN}",
            "Content-Type": "application/json"
        }
    
    def test_filter_by_active_status(self):
        """GET /workspaces/{id}/task-sessions?status=active filters correctly"""
        response = requests.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/task-sessions?status=active",
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # All returned should be active
        for session in data:
            assert session["status"] == "active"
        
        print(f"PASS: Filter by active status - {len(data)} sessions")
    
    def test_filter_by_completed_status(self):
        """GET /workspaces/{id}/task-sessions?status=completed filters correctly"""
        response = requests.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/task-sessions?status=completed",
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # All returned should be completed
        for session in data:
            assert session["status"] == "completed"
        
        print(f"PASS: Filter by completed status - {len(data)} sessions")


class TestCleanup:
    """Clean up test data"""
    
    @classmethod
    def teardown_class(cls):
        """Remove test data"""
        import subprocess
        subprocess.run([
            'mongosh', '--quiet', '--eval', f'''
use('test_database');
db.task_sessions.deleteMany({{title: /^TEST_/}});
db.task_session_messages.deleteMany({{session_id: /^ts_/}});
print('Cleanup complete');
'''
        ], capture_output=True)
    
    def test_cleanup_marker(self):
        """Marker test for cleanup"""
        print("PASS: Test suite cleanup complete")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
