"""
Test Module: Integration Keys Bug Fix + Agent Toggle Feature
Iteration 47

Tests for:
1. BUG FIX: Integration keys now persist to MongoDB (platform_settings collection) and GET reads from both DB and env vars
2. FEATURE: Agent toggle - disable/enable agents per channel via PUT /channels/{ch_id}/agent-toggle
3. FEATURE: GET /channels/{ch_id}/disabled-agents returns list of disabled agents
"""

import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_EMAIL = "test@test.com"
TEST_PASSWORD = "test123"
TEST_WORKSPACE_ID = "ws_f6ec6355bb18"
TEST_CHANNEL_ID = "ch_bbc9cea9ccc6"


class TestSetup:
    """Setup fixtures for authentication"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("session_token")
            if token:
                session.headers.update({"Authorization": f"Bearer {token}"})
        
        return session


class TestIntegrationKeysBugFix:
    """Test that integration keys are properly saved to and read from MongoDB"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        login_response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if login_response.status_code == 200:
            token = login_response.json().get("session_token")
            if token:
                session.headers.update({"Authorization": f"Bearer {token}"})
        return session
    
    def test_01_get_integrations_endpoint_exists(self, auth_session):
        """GET /api/admin/integrations should return list of integrations"""
        response = auth_session.get(f"{BASE_URL}/api/admin/integrations")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "integrations" in data, "Response should have 'integrations' key"
        assert isinstance(data["integrations"], list), "integrations should be a list"
        print(f"✓ GET /admin/integrations returns {len(data['integrations'])} integrations")
    
    def test_02_post_integration_key_saves_to_db(self, auth_session):
        """POST /api/admin/integrations should save key to platform_settings collection"""
        # Use a unique test key value to verify it's saved
        test_key_value = f"TEST_KEY_{uuid.uuid4().hex[:8]}"
        
        response = auth_session.post(f"{BASE_URL}/api/admin/integrations", json={
            "key": "DISCORD_BOT_TOKEN",
            "value": test_key_value
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("key") == "DISCORD_BOT_TOKEN"
        assert data.get("configured") == True
        print(f"✓ POST /admin/integrations saved DISCORD_BOT_TOKEN")
    
    def test_03_get_shows_saved_key_as_configured(self, auth_session):
        """GET /api/admin/integrations should show saved key as configured (reads from DB)"""
        response = auth_session.get(f"{BASE_URL}/api/admin/integrations")
        assert response.status_code == 200
        data = response.json()
        
        # Find DISCORD_BOT_TOKEN
        discord_config = None
        for integ in data["integrations"]:
            if integ["key"] == "DISCORD_BOT_TOKEN":
                discord_config = integ
                break
        
        assert discord_config is not None, "DISCORD_BOT_TOKEN should be in response"
        assert discord_config["configured"] == True, "DISCORD_BOT_TOKEN should show configured=True after saving"
        assert discord_config.get("masked_value") is not None, "Should have masked_value for configured keys"
        print(f"✓ GET /admin/integrations shows DISCORD_BOT_TOKEN as configured with masked value: {discord_config.get('masked_value')}")
    
    def test_04_save_multiple_different_keys(self, auth_session):
        """Save multiple different integration keys and verify they all persist"""
        keys_to_test = [
            ("GITHUB_CLIENT_ID", f"github_{uuid.uuid4().hex[:12]}"),
            ("TELEGRAM_BOT_TOKEN", f"telegram_{uuid.uuid4().hex[:12]}"),
            ("SLACK_CLIENT_ID", f"slack_{uuid.uuid4().hex[:12]}"),
        ]
        
        # Save each key
        for key_name, key_value in keys_to_test:
            response = auth_session.post(f"{BASE_URL}/api/admin/integrations", json={
                "key": key_name,
                "value": key_value
            })
            assert response.status_code == 200, f"Failed to save {key_name}: {response.text}"
            print(f"✓ Saved {key_name}")
        
        # Verify all keys are configured
        response = auth_session.get(f"{BASE_URL}/api/admin/integrations")
        assert response.status_code == 200
        data = response.json()
        
        configured_keys = {i["key"]: i["configured"] for i in data["integrations"]}
        
        for key_name, _ in keys_to_test:
            assert configured_keys.get(key_name) == True, f"{key_name} should be configured after saving"
            print(f"✓ {key_name} verified as configured")
    
    def test_05_integration_response_structure(self, auth_session):
        """Verify each integration has required fields"""
        response = auth_session.get(f"{BASE_URL}/api/admin/integrations")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["key", "name", "provider", "category", "configured"]
        
        for integ in data["integrations"][:5]:  # Check first 5
            for field in required_fields:
                assert field in integ, f"Integration missing required field: {field}"
            
            # If configured, should have masked_value
            if integ["configured"]:
                assert "masked_value" in integ, f"{integ['key']} is configured but missing masked_value"
        
        print(f"✓ Integration response structure verified")


class TestAgentToggleFeature:
    """Test agent enable/disable toggle feature per channel"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        login_response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if login_response.status_code == 200:
            token = login_response.json().get("session_token")
            if token:
                session.headers.update({"Authorization": f"Bearer {token}"})
        return session
    
    def test_01_get_disabled_agents_initially_empty(self, auth_session):
        """GET /api/channels/{ch_id}/disabled-agents should return empty list initially"""
        response = auth_session.get(f"{BASE_URL}/api/channels/{TEST_CHANNEL_ID}/disabled-agents")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "disabled_agents" in data, "Response should have 'disabled_agents' key"
        assert isinstance(data["disabled_agents"], list), "disabled_agents should be a list"
        print(f"✓ GET disabled-agents returns list: {data['disabled_agents']}")
    
    def test_02_disable_agent_with_enabled_false(self, auth_session):
        """PUT /api/channels/{ch_id}/agent-toggle with enabled=false should disable agent"""
        response = auth_session.put(
            f"{BASE_URL}/api/channels/{TEST_CHANNEL_ID}/agent-toggle",
            json={"agent_key": "claude", "enabled": False}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("agent_key") == "claude"
        assert data.get("enabled") == False
        assert data.get("channel_id") == TEST_CHANNEL_ID
        print(f"✓ Disabled claude in channel")
    
    def test_03_verify_agent_in_disabled_list(self, auth_session):
        """Verify disabled agent appears in disabled-agents list"""
        response = auth_session.get(f"{BASE_URL}/api/channels/{TEST_CHANNEL_ID}/disabled-agents")
        assert response.status_code == 200
        data = response.json()
        assert "claude" in data["disabled_agents"], "claude should be in disabled list"
        print(f"✓ claude verified in disabled-agents list: {data['disabled_agents']}")
    
    def test_04_enable_agent_with_enabled_true(self, auth_session):
        """PUT /api/channels/{ch_id}/agent-toggle with enabled=true should re-enable agent"""
        response = auth_session.put(
            f"{BASE_URL}/api/channels/{TEST_CHANNEL_ID}/agent-toggle",
            json={"agent_key": "claude", "enabled": True}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("agent_key") == "claude"
        assert data.get("enabled") == True
        print(f"✓ Re-enabled claude in channel")
    
    def test_05_verify_agent_removed_from_disabled_list(self, auth_session):
        """Verify re-enabled agent is removed from disabled-agents list"""
        response = auth_session.get(f"{BASE_URL}/api/channels/{TEST_CHANNEL_ID}/disabled-agents")
        assert response.status_code == 200
        data = response.json()
        assert "claude" not in data["disabled_agents"], "claude should NOT be in disabled list after re-enabling"
        print(f"✓ claude removed from disabled-agents list: {data['disabled_agents']}")
    
    def test_06_disable_multiple_agents(self, auth_session):
        """Disable multiple agents simultaneously"""
        agents_to_disable = ["claude", "chatgpt"]
        
        for agent in agents_to_disable:
            response = auth_session.put(
                f"{BASE_URL}/api/channels/{TEST_CHANNEL_ID}/agent-toggle",
                json={"agent_key": agent, "enabled": False}
            )
            assert response.status_code == 200, f"Failed to disable {agent}"
        
        # Verify both in disabled list
        response = auth_session.get(f"{BASE_URL}/api/channels/{TEST_CHANNEL_ID}/disabled-agents")
        assert response.status_code == 200
        data = response.json()
        
        for agent in agents_to_disable:
            assert agent in data["disabled_agents"], f"{agent} should be in disabled list"
        
        print(f"✓ Multiple agents disabled: {data['disabled_agents']}")
    
    def test_07_disabled_agents_persist_across_requests(self, auth_session):
        """Verify disabled agents persist (stored in channel doc)"""
        # Make another request to verify persistence
        time.sleep(0.5)
        response = auth_session.get(f"{BASE_URL}/api/channels/{TEST_CHANNEL_ID}/disabled-agents")
        assert response.status_code == 200
        data = response.json()
        
        # Should still have disabled agents from previous test
        assert len(data["disabled_agents"]) >= 1, "Disabled agents should persist"
        print(f"✓ Disabled agents persisted: {data['disabled_agents']}")
    
    def test_08_cleanup_re_enable_all_agents(self, auth_session):
        """Cleanup: Re-enable all agents that were disabled"""
        response = auth_session.get(f"{BASE_URL}/api/channels/{TEST_CHANNEL_ID}/disabled-agents")
        if response.status_code == 200:
            disabled = response.json().get("disabled_agents", [])
            for agent in disabled:
                auth_session.put(
                    f"{BASE_URL}/api/channels/{TEST_CHANNEL_ID}/agent-toggle",
                    json={"agent_key": agent, "enabled": True}
                )
        
        # Verify all re-enabled
        response = auth_session.get(f"{BASE_URL}/api/channels/{TEST_CHANNEL_ID}/disabled-agents")
        data = response.json()
        assert len(data.get("disabled_agents", [])) == 0, "All agents should be re-enabled"
        print(f"✓ Cleanup complete - all agents re-enabled")
    
    def test_09_toggle_without_agent_key_returns_400(self, auth_session):
        """PUT without agent_key should return 400 error"""
        response = auth_session.put(
            f"{BASE_URL}/api/channels/{TEST_CHANNEL_ID}/agent-toggle",
            json={"enabled": False}  # Missing agent_key
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print(f"✓ Missing agent_key correctly returns 400")


class TestRegressionCodeRepo:
    """Regression tests for code repo CRUD"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        login_response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if login_response.status_code == 200:
            token = login_response.json().get("session_token")
            if token:
                session.headers.update({"Authorization": f"Bearer {token}"})
        return session
    
    def test_01_get_code_repo_tree(self, auth_session):
        """GET /api/workspaces/{ws_id}/code-repo/tree should work"""
        response = auth_session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/tree")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "files" in data, "Response should have 'files' key"
        print(f"✓ Code repo tree has {len(data.get('files', []))} files")


class TestRegressionAutoCollab:
    """Regression tests for auto-collab toggle"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        login_response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if login_response.status_code == 200:
            token = login_response.json().get("session_token")
            if token:
                session.headers.update({"Authorization": f"Bearer {token}"})
        return session
    
    def test_01_get_auto_collab_status(self, auth_session):
        """GET /api/channels/{ch_id}/auto-collab should return status"""
        response = auth_session.get(f"{BASE_URL}/api/channels/{TEST_CHANNEL_ID}/auto-collab")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "enabled" in data, "Response should have 'enabled' key"
        print(f"✓ Auto-collab status: enabled={data.get('enabled')}")
    
    def test_02_toggle_auto_collab(self, auth_session):
        """PUT /api/channels/{ch_id}/auto-collab should toggle"""
        # Get current state
        response = auth_session.get(f"{BASE_URL}/api/channels/{TEST_CHANNEL_ID}/auto-collab")
        current_state = response.json().get("enabled", False)
        
        # Toggle
        response = auth_session.put(
            f"{BASE_URL}/api/channels/{TEST_CHANNEL_ID}/auto-collab",
            json={"enabled": not current_state}
        )
        assert response.status_code == 200
        
        # Revert
        response = auth_session.put(
            f"{BASE_URL}/api/channels/{TEST_CHANNEL_ID}/auto-collab",
            json={"enabled": current_state}
        )
        assert response.status_code == 200
        print(f"✓ Auto-collab toggle works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
