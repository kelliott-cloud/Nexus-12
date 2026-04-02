"""
Test suite for AI Keys Management API endpoints v2
Tests: GET/POST/DELETE /api/settings/ai-keys, test connection, workspace AI config
"""
import pytest
import requests
import os
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test API keys — env var backed with obviously-fake defaults
TEST_KEYS = {
    "claude": os.environ.get("TEST_CLAUDE_KEY", "sk-ant-test-key-v2-12345"),
    "chatgpt": os.environ.get("TEST_OPENAI_KEY", "sk-openai-test-key-v2-abcd"),
    "groq": os.environ.get("TEST_GROQ_KEY", TEST_KEYS["groq"]),
}

# All 9 supported AI agents
ALL_AGENTS = ["claude", "chatgpt", "deepseek", "grok", "gemini", "perplexity", "mistral", "cohere", "groq"]


class TestAIKeysEndpoints:
    """Test AI Keys management endpoints"""
    
    @pytest.fixture(scope="class")
    def test_session(self):
        """Create a test user and session via MongoDB"""
        import subprocess
        result = subprocess.run([
            'mongosh', '--quiet', '--eval', '''
use('test_database');
var userId = 'test-user-aikeys-v2-' + Date.now();
var sessionToken = 'test_session_aikeys_v2_' + Date.now();
db.users.insertOne({
  user_id: userId,
  email: 'test.aikeys.v2.' + Date.now() + '@example.com',
  name: 'Test User AI Keys V2',
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

    # ============ Test All 9 AI Agents in GET endpoint ============
    
    def test_get_ai_keys_without_auth(self):
        """GET /api/settings/ai-keys should return 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/settings/ai-keys")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: GET /api/settings/ai-keys returns 401 without auth")
    
    def test_get_ai_keys_returns_all_9_agents(self, auth_headers):
        """GET /api/settings/ai-keys should return status for all 9 AI agents"""
        response = requests.get(f"{BASE_URL}/api/settings/ai-keys", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Should return status for all 9 agents including new ones
        for agent in ALL_AGENTS:
            assert agent in data, f"Missing agent: {agent}"
            assert "configured" in data[agent], f"Missing 'configured' field for {agent}"
            assert "masked_key" in data[agent], f"Missing 'masked_key' field for {agent}"
        
        print(f"PASS: GET /api/settings/ai-keys returns all 9 agents: {list(data.keys())}")
    
    # ============ Test Save Keys for New Agents ============
    
    def test_save_gemini_key(self, auth_headers):
        """POST /api/settings/ai-keys should save Gemini API key"""
        payload = {"gemini": "AIzaSyTest-gemini-key-12345678"}
        response = requests.post(f"{BASE_URL}/api/settings/ai-keys", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("gemini", {}).get("configured") == True, "Gemini key should be configured"
        assert "..." in data["gemini"]["masked_key"], "Key should be masked"
        print(f"PASS: Gemini key saved, masked: {data['gemini']['masked_key']}")
    
    def test_save_perplexity_key(self, auth_headers):
        """POST /api/settings/ai-keys should save Perplexity API key"""
        payload = {"perplexity": "pplx-test-perplexity-key-12345"}
        response = requests.post(f"{BASE_URL}/api/settings/ai-keys", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("perplexity", {}).get("configured") == True, "Perplexity key should be configured"
        print(f"PASS: Perplexity key saved, masked: {data['perplexity']['masked_key']}")
    
    def test_save_mistral_key(self, auth_headers):
        """POST /api/settings/ai-keys should save Mistral API key"""
        payload = {"mistral": "test-mistral-key-abc123xyz"}
        response = requests.post(f"{BASE_URL}/api/settings/ai-keys", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("mistral", {}).get("configured") == True, "Mistral key should be configured"
        print(f"PASS: Mistral key saved, masked: {data['mistral']['masked_key']}")
    
    def test_save_cohere_key(self, auth_headers):
        """POST /api/settings/ai-keys should save Cohere API key"""
        payload = {"cohere": "test-cohere-key-xyz789abc"}
        response = requests.post(f"{BASE_URL}/api/settings/ai-keys", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("cohere", {}).get("configured") == True, "Cohere key should be configured"
        print(f"PASS: Cohere key saved, masked: {data['cohere']['masked_key']}")
    
    def test_save_groq_key(self, auth_headers):
        """POST /api/settings/ai-keys should save Groq API key"""
        payload = {"groq": TEST_KEYS["groq"]}
        response = requests.post(f"{BASE_URL}/api/settings/ai-keys", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("groq", {}).get("configured") == True, "Groq key should be configured"
        print(f"PASS: Groq key saved, masked: {data['groq']['masked_key']}")
    
    def test_save_multiple_new_keys(self, auth_headers):
        """POST /api/settings/ai-keys should save multiple new agent keys at once"""
        payload = {
            "gemini": "AIzaMulti-gemini-key",
            "perplexity": "pplx-multi-key",
            "mistral": "mistral-multi-key"
        }
        response = requests.post(f"{BASE_URL}/api/settings/ai-keys", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("gemini", {}).get("configured") == True, "Gemini should be configured"
        assert data.get("perplexity", {}).get("configured") == True, "Perplexity should be configured"
        assert data.get("mistral", {}).get("configured") == True, "Mistral should be configured"
        print("PASS: Multiple new agent keys saved successfully")
    
    # ============ Test Delete New Agent Keys ============
    
    def test_delete_new_agent_key(self, auth_headers):
        """DELETE /api/settings/ai-keys/{agent} should work for new agents"""
        # First save a key
        requests.post(f"{BASE_URL}/api/settings/ai-keys", json={"cohere": "test-delete-cohere"}, headers=auth_headers)
        
        # Then delete it
        response = requests.delete(f"{BASE_URL}/api/settings/ai-keys/cohere", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: DELETE cohere key successful")
        
        # Verify key is removed
        get_response = requests.get(f"{BASE_URL}/api/settings/ai-keys", headers=auth_headers)
        get_data = get_response.json()
        assert get_data.get("cohere", {}).get("configured") == False, "Cohere key should be unconfigured"
        print("PASS: Verified cohere key removed after delete")


class TestAIKeyValidation:
    """Test API key validation/test connection endpoint"""
    
    @pytest.fixture(scope="class")
    def test_session(self):
        """Create a test user and session"""
        import subprocess
        result = subprocess.run([
            'mongosh', '--quiet', '--eval', '''
use('test_database');
var userId = 'test-user-keytest-' + Date.now();
var sessionToken = 'test_session_keytest_' + Date.now();
db.users.insertOne({
  user_id: userId,
  email: 'test.keytest.' + Date.now() + '@example.com',
  name: 'Test User Key Validation',
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
        return {
            "Authorization": f"Bearer {test_session['session_token']}",
            "Content-Type": "application/json"
        }
    
    def test_test_endpoint_without_auth(self):
        """POST /api/settings/ai-keys/test should return 401 without auth"""
        response = requests.post(f"{BASE_URL}/api/settings/ai-keys/test", json={"agent": "claude", "api_key": "test"})
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Test endpoint requires authentication")
    
    def test_test_endpoint_invalid_agent(self, auth_headers):
        """POST /api/settings/ai-keys/test should return 400 for invalid agent"""
        payload = {"agent": "invalid_agent", "api_key": "test-key"}
        response = requests.post(f"{BASE_URL}/api/settings/ai-keys/test", json=payload, headers=auth_headers)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("PASS: Test endpoint returns 400 for invalid agent")
    
    def test_test_endpoint_returns_proper_structure(self, auth_headers):
        """POST /api/settings/ai-keys/test should return proper response structure"""
        # Test with an invalid key to verify structure
        payload = {"agent": "claude", "api_key": TEST_KEYS.get("claude", "sk-ant-invalid-test-key")}
        response = requests.post(f"{BASE_URL}/api/settings/ai-keys/test", json=payload, headers=auth_headers)
        
        # Should return 200 but with success=false
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "success" in data, "Response should contain 'success' field"
        # Invalid key should fail
        assert data["success"] == False, "Invalid key should return success=false"
        assert "error" in data, "Failed test should include error message"
        print(f"PASS: Test endpoint returns proper structure: {data}")
    
    def test_test_endpoint_for_all_agents(self, auth_headers):
        """POST /api/settings/ai-keys/test should accept all 9 agents"""
        for agent in ALL_AGENTS:
            payload = {"agent": agent, "api_key": "test-key-12345"}
            response = requests.post(f"{BASE_URL}/api/settings/ai-keys/test", json=payload, headers=auth_headers)
            assert response.status_code == 200, f"Test endpoint failed for {agent}: {response.status_code}"
            
            data = response.json()
            # All should fail with invalid keys but return proper response
            assert "success" in data, f"Missing success field for {agent}"
            print(f"  - {agent}: success={data['success']}")
        
        print("PASS: Test endpoint accepts all 9 agents")


class TestWorkspaceAIConfigFor9Agents:
    """Test workspace-level AI configuration endpoints with all 9 agents"""
    
    @pytest.fixture(scope="class")
    def test_session(self):
        """Create a test user and session"""
        import subprocess
        result = subprocess.run([
            'mongosh', '--quiet', '--eval', '''
use('test_database');
var userId = 'test-user-ws9-' + Date.now();
var sessionToken = 'test_session_ws9_' + Date.now();
var workspaceId = 'ws_9agents_' + Date.now().toString(36);
db.users.insertOne({
  user_id: userId,
  email: 'test.ws9.' + Date.now() + '@example.com',
  name: 'Test User WS 9 Agents',
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
  name: 'Test Workspace 9 Agents',
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
    
    def test_workspace_ai_config_returns_all_9_agents(self, test_session, auth_headers):
        """GET /api/workspaces/{workspace_id}/ai-config should return config for all 9 agents"""
        workspace_id = test_session['workspace_id']
        response = requests.get(f"{BASE_URL}/api/workspaces/{workspace_id}/ai-config", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        for agent in ALL_AGENTS:
            assert agent in data, f"Missing agent config: {agent}"
            assert "enabled" in data[agent], f"Missing 'enabled' for {agent}"
            assert "key_source" in data[agent], f"Missing 'key_source' for {agent}"
        print(f"PASS: Workspace ai-config returns all 9 agents: {list(data.keys())}")
    
    def test_workspace_ai_config_save_new_agents(self, test_session, auth_headers):
        """POST /api/workspaces/{workspace_id}/ai-config should save config for new agents"""
        workspace_id = test_session['workspace_id']
        payload = {
            "gemini": {"enabled": True, "key_source": "nexus"},
            "perplexity": {"enabled": True, "key_source": "account"},
            "mistral": {"enabled": False, "key_source": "nexus"},
            "cohere": {"enabled": True, "key_source": "project", "api_key": "cohere-project-test-key"},
            "groq": {"enabled": True, "key_source": "nexus"}
        }
        response = requests.post(f"{BASE_URL}/api/workspaces/{workspace_id}/ai-config", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "ai_config" in data, "Response should contain ai_config"
        print("PASS: Workspace ai-config saved for new agents")
        
        # Verify the saved config
        get_response = requests.get(f"{BASE_URL}/api/workspaces/{workspace_id}/ai-config", headers=auth_headers)
        get_data = get_response.json()
        assert get_data["cohere"]["has_project_key"] == True, "Cohere should have project key"
        print("PASS: Verified workspace ai-config persisted correctly for new agents")


class TestAIModelsEndpoint:
    """Test that AI models endpoint returns all 9 models"""
    
    def test_ai_models_returns_all_9_models(self):
        """GET /api/ai-models should return info for all 9 models"""
        response = requests.get(f"{BASE_URL}/api/ai-models")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        for agent in ALL_AGENTS:
            assert agent in data, f"Missing model: {agent}"
            assert "name" in data[agent], f"Missing name for {agent}"
            assert "color" in data[agent], f"Missing color for {agent}"
            assert "mocked" in data[agent], f"Missing mocked flag for {agent}"
        
        # Verify DeepSeek and Grok are mocked (per user request)
        assert data["deepseek"]["mocked"] == True, "DeepSeek should be mocked"
        assert data["grok"]["mocked"] == True, "Grok should be mocked"
        
        # Verify new agents are NOT mocked
        assert data["gemini"]["mocked"] == False, "Gemini should NOT be mocked"
        assert data["perplexity"]["mocked"] == False, "Perplexity should NOT be mocked"
        assert data["mistral"]["mocked"] == False, "Mistral should NOT be mocked"
        assert data["cohere"]["mocked"] == False, "Cohere should NOT be mocked"
        assert data["groq"]["mocked"] == False, "Groq should NOT be mocked"
        
        print(f"PASS: AI models endpoint returns all 9 models with correct mocked status")
        print(f"  Mocked: deepseek={data['deepseek']['mocked']}, grok={data['grok']['mocked']}")
        print(f"  Real: gemini, perplexity, mistral, cohere, groq")


class TestHealthEndpoint:
    """Basic health check"""
    
    def test_health_endpoint(self):
        """GET /api/health should return ok"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("status") == "ok", f"Expected status=ok, got {data}"
        print("PASS: Health endpoint working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
