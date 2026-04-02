"""
Test suite for AI Keys Management API endpoints
Tests: GET/POST/DELETE /api/settings/ai-keys and workspace AI config endpoints
"""
import pytest
import requests
import os
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test API keys — use env vars if available, otherwise use obviously-fake test values
TEST_KEYS = {
    "claude": os.environ.get("TEST_CLAUDE_KEY", TEST_KEYS["claude"]),
    "chatgpt": os.environ.get("TEST_OPENAI_KEY", TEST_KEYS["chatgpt"]),
    "deepseek": os.environ.get("TEST_DEEPSEEK_KEY", TEST_KEYS["deepseek"]),
    "groq": os.environ.get("TEST_GROQ_KEY", "gsk_test_groq_key_12345678"),
}

class TestAIKeysEndpoints:
    """Test AI Keys management endpoints"""
    
    @pytest.fixture(scope="class")
    def test_session(self):
        """Create a test user and session via MongoDB"""
        import subprocess
        result = subprocess.run([
            'mongosh', '--quiet', '--eval', '''
use('test_database');
var userId = 'test-user-aikeys-' + Date.now();
var sessionToken = 'test_session_aikeys_' + Date.now();
db.users.insertOne({
  user_id: userId,
  email: 'test.aikeys.' + Date.now() + '@example.com',
  name: 'Test User AI Keys',
  picture: '',
  plan: 'free',
  ai_keys: {},
  usage: {ai_collaborations: 0},
  created_at: new Date().toISOString()
});
db.user_sessions.insertOne({
  user_id: userId,
  session_token: sessionToken,
  expires_at: new Date(Date.now() + 7*24*60*60*1000).toISOString(),
  created_at: new Date().toISOString()
});
print('SESSION_TOKEN=' + sessionToken);
print('USER_ID=' + userId);
'''
        ], capture_output=True, text=True)
        
        lines = result.stdout.strip().split('\n')
        session_data = {}
        for line in lines:
            if line.startswith('SESSION_TOKEN='):
                session_data['session_token'] = line.split('=')[1]
            elif line.startswith('USER_ID='):
                session_data['user_id'] = line.split('=')[1]
        return session_data
    
    @pytest.fixture
    def auth_headers(self, test_session):
        """Return authorization headers"""
        return {
            "Authorization": f"Bearer {test_session['session_token']}",
            "Content-Type": "application/json"
        }

    # ============ Test AI Keys Routes ============
    
    def test_get_ai_keys_without_auth(self):
        """GET /api/settings/ai-keys should return 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/settings/ai-keys")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: GET /api/settings/ai-keys returns 401 without auth")
    
    def test_get_ai_keys_with_auth(self, auth_headers):
        """GET /api/settings/ai-keys should return key status"""
        response = requests.get(f"{BASE_URL}/api/settings/ai-keys", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Should return status for all 4 agents
        for agent in ["claude", "chatgpt", "deepseek", "grok"]:
            assert agent in data, f"Missing agent: {agent}"
            assert "configured" in data[agent], f"Missing 'configured' field for {agent}"
            assert "masked_key" in data[agent], f"Missing 'masked_key' field for {agent}"
        print(f"PASS: GET /api/settings/ai-keys returns proper structure: {data}")
    
    def test_post_ai_keys_save_key(self, auth_headers):
        """POST /api/settings/ai-keys should save encrypted key"""
        payload = {"claude": TEST_KEYS["claude"]}
        response = requests.post(f"{BASE_URL}/api/settings/ai-keys", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("claude", {}).get("configured") == True, "Claude key should be configured"
        assert data.get("claude", {}).get("masked_key") is not None, "Masked key should be returned"
        # Verify masking format (first 4 + ... + last 4)
        masked = data["claude"]["masked_key"]
        assert "..." in masked, f"Masked key should contain '...': {masked}"
        print(f"PASS: POST /api/settings/ai-keys saved key, masked: {masked}")
    
    def test_post_ai_keys_multiple_keys(self, auth_headers):
        """POST /api/settings/ai-keys should save multiple keys"""
        payload = {
            "chatgpt": TEST_KEYS["chatgpt"],
            "deepseek": TEST_KEYS["deepseek"]
        }
        response = requests.post(f"{BASE_URL}/api/settings/ai-keys", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("chatgpt", {}).get("configured") == True, "ChatGPT key should be configured"
        assert data.get("deepseek", {}).get("configured") == True, "DeepSeek key should be configured"
        print(f"PASS: Multiple keys saved successfully")
    
    def test_delete_ai_key(self, auth_headers):
        """DELETE /api/settings/ai-keys/{agent} should remove key"""
        # First save a key
        requests.post(f"{BASE_URL}/api/settings/ai-keys", json={"grok": "xai-test-key-xyz"}, headers=auth_headers)
        
        # Then delete it
        response = requests.delete(f"{BASE_URL}/api/settings/ai-keys/grok", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "message" in data, "Should return message"
        print(f"PASS: DELETE /api/settings/ai-keys/grok: {data}")
        
        # Verify key is removed
        get_response = requests.get(f"{BASE_URL}/api/settings/ai-keys", headers=auth_headers)
        get_data = get_response.json()
        assert get_data.get("grok", {}).get("configured") == False, "Grok key should be unconfigured after delete"
        print("PASS: Verified grok key removed after delete")
    
    def test_delete_ai_key_invalid_agent(self, auth_headers):
        """DELETE /api/settings/ai-keys/{agent} should return 400 for invalid agent"""
        response = requests.delete(f"{BASE_URL}/api/settings/ai-keys/invalid_agent", headers=auth_headers)
        assert response.status_code == 400, f"Expected 400 for invalid agent, got {response.status_code}"
        print("PASS: DELETE with invalid agent returns 400")
    
    def test_post_ai_keys_remove_key_with_empty_string(self, auth_headers):
        """POST /api/settings/ai-keys with empty string should remove key"""
        # First save a key
        requests.post(f"{BASE_URL}/api/settings/ai-keys", json={"chatgpt": TEST_KEYS["chatgpt"]}, headers=auth_headers)
        
        # Remove by posting empty string
        response = requests.post(f"{BASE_URL}/api/settings/ai-keys", json={"chatgpt": ""}, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("chatgpt", {}).get("configured") == False, "ChatGPT key should be unconfigured"
        print("PASS: Empty string removes key via POST")


class TestWorkspaceAIConfig:
    """Test workspace-level AI configuration endpoints"""
    
    @pytest.fixture(scope="class")
    def test_session(self):
        """Create a test user and session"""
        import subprocess
        result = subprocess.run([
            'mongosh', '--quiet', '--eval', '''
use('test_database');
var userId = 'test-user-wsconfig-' + Date.now();
var sessionToken = 'test_session_wsconfig_' + Date.now();
var workspaceId = 'ws_test_' + Date.now().toString(36);
db.users.insertOne({
  user_id: userId,
  email: 'test.wsconfig.' + Date.now() + '@example.com',
  name: 'Test User WS Config',
  plan: 'free',
  ai_keys: {},
  created_at: new Date().toISOString()
});
db.user_sessions.insertOne({
  user_id: userId,
  session_token: sessionToken,
  expires_at: new Date(Date.now() + 7*24*60*60*1000).toISOString(),
  created_at: new Date().toISOString()
});
db.workspaces.insertOne({
  workspace_id: workspaceId,
  name: 'Test Workspace AI Config',
  owner_id: userId,
  members: [userId],
  created_at: new Date().toISOString()
});
print('SESSION_TOKEN=' + sessionToken);
print('USER_ID=' + userId);
print('WORKSPACE_ID=' + workspaceId);
'''
        ], capture_output=True, text=True)
        
        lines = result.stdout.strip().split('\n')
        session_data = {}
        for line in lines:
            if line.startswith('SESSION_TOKEN='):
                session_data['session_token'] = line.split('=')[1]
            elif line.startswith('USER_ID='):
                session_data['user_id'] = line.split('=')[1]
            elif line.startswith('WORKSPACE_ID='):
                session_data['workspace_id'] = line.split('=')[1]
        return session_data
    
    @pytest.fixture
    def auth_headers(self, test_session):
        return {
            "Authorization": f"Bearer {test_session['session_token']}",
            "Content-Type": "application/json"
        }
    
    def test_get_workspace_ai_config(self, test_session, auth_headers):
        """GET /api/workspaces/{workspace_id}/ai-config should return config"""
        workspace_id = test_session['workspace_id']
        response = requests.get(f"{BASE_URL}/api/workspaces/{workspace_id}/ai-config", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        for agent in ["claude", "chatgpt", "deepseek", "grok"]:
            assert agent in data, f"Missing agent config: {agent}"
            assert "enabled" in data[agent], f"Missing 'enabled' for {agent}"
            assert "key_source" in data[agent], f"Missing 'key_source' for {agent}"
            assert "has_account_key" in data[agent], f"Missing 'has_account_key' for {agent}"
            assert "has_project_key" in data[agent], f"Missing 'has_project_key' for {agent}"
        print(f"PASS: GET workspace ai-config returns proper structure")
    
    def test_get_workspace_ai_config_not_found(self, auth_headers):
        """GET /api/workspaces/{workspace_id}/ai-config should return 404 for invalid workspace"""
        response = requests.get(f"{BASE_URL}/api/workspaces/ws_invalid_12345/ai-config", headers=auth_headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: GET workspace ai-config returns 404 for invalid workspace")
    
    def test_post_workspace_ai_config(self, test_session, auth_headers):
        """POST /api/workspaces/{workspace_id}/ai-config should save config"""
        workspace_id = test_session['workspace_id']
        payload = {
            "claude": {"enabled": True, "key_source": "nexus"},
            "chatgpt": {"enabled": True, "key_source": "account"},
            "deepseek": {"enabled": False, "key_source": "nexus"},
            "grok": {"enabled": True, "key_source": "project", "api_key": "xai-project-test-key"}
        }
        response = requests.post(f"{BASE_URL}/api/workspaces/{workspace_id}/ai-config", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "ai_config" in data, "Response should contain ai_config"
        assert data.get("workspace_id") == workspace_id, "Workspace ID should match"
        print(f"PASS: POST workspace ai-config saved successfully")
        
        # Verify the saved config
        get_response = requests.get(f"{BASE_URL}/api/workspaces/{workspace_id}/ai-config", headers=auth_headers)
        get_data = get_response.json()
        assert get_data["grok"]["has_project_key"] == True, "Grok should have project key"
        print("PASS: Verified workspace ai-config persisted correctly")
    
    def test_post_workspace_ai_config_without_auth(self, test_session):
        """POST /api/workspaces/{workspace_id}/ai-config should return 401 without auth"""
        workspace_id = test_session['workspace_id']
        response = requests.post(f"{BASE_URL}/api/workspaces/{workspace_id}/ai-config", json={})
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: POST workspace ai-config returns 401 without auth")


class TestHealthAndBasicEndpoints:
    """Basic endpoint tests"""
    
    def test_health_endpoint(self):
        """GET /api/health should return ok"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("status") == "ok", f"Expected status=ok, got {data}"
        print("PASS: Health endpoint working")
    
    def test_ai_models_endpoint(self):
        """GET /api/ai-models should return model info"""
        response = requests.get(f"{BASE_URL}/api/ai-models")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        for agent in ["claude", "chatgpt", "deepseek", "grok"]:
            assert agent in data, f"Missing agent: {agent}"
            assert "name" in data[agent], f"Missing name for {agent}"
            assert "mocked" in data[agent], f"Missing mocked flag for {agent}"
        
        # Verify DeepSeek and Grok are mocked
        assert data["deepseek"]["mocked"] == True, "DeepSeek should be mocked"
        assert data["grok"]["mocked"] == True, "Grok should be mocked"
        print(f"PASS: AI models endpoint returns proper data, DeepSeek/Grok are MOCKED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
