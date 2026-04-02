"""
Test Task Panel Bug Fixes:
1. Task Panel position fix (verified by frontend tests)
2. Ctrl+Enter submission (verified by frontend tests)
3. DeepSeek API key retrieval defaults to account-level keys
"""
import pytest
import requests
import os
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_SESSION_TOKEN = "test_session_taskpanel_1772556885329"
TEST_USER_ID = "test-user-taskpanel-1772556885329"
TEST_WORKSPACE_ID = "ws_taskpanel_1772556885329"
TEST_CHANNEL_ID = "ch_taskpanel_1772556885329"


@pytest.fixture
def api_client():
    """Authenticated requests session"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TEST_SESSION_TOKEN}"
    })
    return session


class TestDeepSeekKeyRetrieval:
    """Tests for DeepSeek API key retrieval fix - defaults to account-level keys"""
    
    def test_get_ai_keys_endpoint_works(self, api_client):
        """Verify AI keys settings endpoint is accessible"""
        response = api_client.get(f"{BASE_URL}/api/settings/ai-keys")
        assert response.status_code == 200
        data = response.json()
        # Should return status for all 9 AI models
        assert "deepseek" in data
        assert "configured" in data["deepseek"]
        print(f"DeepSeek key configured: {data['deepseek']['configured']}")
    
    def test_workspace_ai_config_endpoint_works(self, api_client):
        """Verify workspace AI config endpoint returns expected structure"""
        response = api_client.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/ai-config")
        assert response.status_code == 200
        data = response.json()
        # Should have entries for supported models
        assert "deepseek" in data
        assert "key_source" in data["deepseek"]
        assert "has_account_key" in data["deepseek"]
        print(f"DeepSeek config: {data['deepseek']}")
    
    def test_deepseek_model_in_ai_models(self, api_client):
        """Verify DeepSeek is available in AI models list"""
        response = api_client.get(f"{BASE_URL}/api/ai-models")
        assert response.status_code == 200
        data = response.json()
        assert "deepseek" in data
        assert data["deepseek"]["name"] == "DeepSeek"
        assert data["deepseek"]["color"] == "#4D6BFE"
        print(f"DeepSeek model info: {data['deepseek']}")
    
    def test_channel_has_deepseek_agent(self, api_client):
        """Verify test channel has DeepSeek as an agent"""
        response = api_client.get(f"{BASE_URL}/api/channels/{TEST_CHANNEL_ID}")
        assert response.status_code == 200
        data = response.json()
        assert "deepseek" in data.get("ai_agents", [])
        print(f"Channel agents: {data.get('ai_agents')}")


class TestTaskSessionsAPI:
    """Tests for Task Sessions API which uses the key retrieval fix"""
    
    def test_list_task_sessions(self, api_client):
        """Test listing task sessions for workspace"""
        response = api_client.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/task-sessions")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if data:
            print(f"Found {len(data)} task sessions")
            # Check structure of first session
            session = data[0]
            assert "session_id" in session
            assert "agent" in session
            print(f"First session agent: {session['agent']}")
    
    def test_create_task_session_with_deepseek(self, api_client):
        """Test creating a task session with DeepSeek agent"""
        # Create a task with DeepSeek
        payload = {
            "title": "DeepSeek API Test Task",
            "description": "Testing DeepSeek key retrieval",
            "assigned_agent": "deepseek",
            "initial_prompt": "Test prompt - please respond briefly"
        }
        response = api_client.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/task-sessions",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify task was created with DeepSeek
        assert data["agent"]["base_model"] == "deepseek"
        assert data["title"] == "DeepSeek API Test Task"
        print(f"Created task session: {data['session_id']}")
        print(f"Agent info: {data['agent']}")
        
        # Store session_id for cleanup
        session_id = data["session_id"]
        
        # Check initial message was created
        msg_response = api_client.get(f"{BASE_URL}/api/task-sessions/{session_id}/messages")
        assert msg_response.status_code == 200
        messages = msg_response.json()
        assert len(messages) >= 1  # At least the initial prompt
        print(f"Initial messages: {len(messages)}")


class TestAPIKeyValidation:
    """Tests for API key validation endpoint"""
    
    def test_key_validation_endpoint_exists(self, api_client):
        """Test that key validation endpoint exists"""
        # Test with a clearly invalid key
        payload = {
            "agent": "deepseek",
            "api_key": "invalid-test-key"
        }
        response = api_client.post(f"{BASE_URL}/api/settings/ai-keys/test", json=payload)
        # Should return 200 with error in response body (not 400/500)
        assert response.status_code == 200
        data = response.json()
        # Should have debug info
        assert "success" in data
        assert "debug" in data
        print(f"Key validation response: {data['success']}")
        if data.get("debug"):
            print(f"Debug - endpoint: {data['debug'].get('endpoint')}")
            print(f"Debug - model: {data['debug'].get('model')}")


class TestCollaborationAPI:
    """Tests for AI collaboration which uses key retrieval"""
    
    def test_channel_status(self, api_client):
        """Test getting channel collaboration status"""
        response = api_client.get(f"{BASE_URL}/api/channels/{TEST_CHANNEL_ID}/status")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert "is_running" in data
        print(f"Channel status: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
