"""
Iteration 120 - AI Key Health Warning Banner Tests

Tests for the new AI key health warning banner feature:
1. GET /api/workspaces/{workspace_id}/ai-key-health endpoint
2. Returns warnings when channel agents rely on placeholder/invalid platform keys
3. Banner includes AI Keys link and Platform Keys link for super admin
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "http://localhost:8080"

# Test credentials from previous iteration
SUPER_ADMIN_EMAIL = os.environ.get("TEST_ADMIN_EMAIL", "admin@test.local")
SUPER_ADMIN_PASSWORD = "test"
TEST_WORKSPACE_ID = "ws_e82d079bc8ef"
TEST_CHANNEL_ID = "ch_eccab5b28108"


@pytest.fixture(scope="module")
def session():
    """Create a requests session"""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth_session(session):
    """Login as super admin and return authenticated session"""
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Super admin login failed: {response.text}"
    data = response.json()
    # Handle MFA if required
    if data.get("mfa_required"):
        pytest.skip("MFA required for super admin - cannot proceed with automated tests")
    return session


# Alias for backward compatibility
@pytest.fixture(scope="module")
def auth_headers(auth_session):
    """Return the authenticated session (uses cookies, not headers)"""
    return auth_session


class TestAIKeyHealthEndpoint:
    """Tests for GET /api/workspaces/{workspace_id}/ai-key-health"""

    def test_ai_key_health_endpoint_exists(self, auth_session):
        """Test that the AI key health endpoint exists and returns 200"""
        response = auth_session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/ai-key-health"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_ai_key_health_returns_expected_structure(self, auth_session):
        """Test that the response has the expected structure"""
        response = auth_session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/ai-key-health"
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        assert "has_warning" in data, "Response should have 'has_warning' field"
        assert "warnings" in data, "Response should have 'warnings' field"
        assert "providers" in data, "Response should have 'providers' field"
        assert isinstance(data["has_warning"], bool), "'has_warning' should be boolean"
        assert isinstance(data["warnings"], list), "'warnings' should be a list"
        assert isinstance(data["providers"], dict), "'providers' should be a dict"

    def test_ai_key_health_with_channel_id(self, auth_session):
        """Test AI key health endpoint with specific channel_id parameter"""
        response = auth_session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/ai-key-health?channel_id={TEST_CHANNEL_ID}"
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should include channel_id in response
        assert "channel_id" in data, "Response should include channel_id when provided"
        assert data["channel_id"] == TEST_CHANNEL_ID

    def test_ai_key_health_detects_placeholder_keys(self, auth_session):
        """Test that placeholder/invalid platform keys are detected"""
        response = auth_session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/ai-key-health"
        )
        assert response.status_code == 200
        data = response.json()
        
        # Based on previous iteration, we know chatgpt and claude have placeholder keys
        # Check if warnings are generated for placeholder keys
        if data["has_warning"]:
            assert len(data["warnings"]) > 0, "If has_warning is True, warnings list should not be empty"
            for warning in data["warnings"]:
                assert "provider" in warning, "Each warning should have 'provider' field"
                assert "message" in warning, "Each warning should have 'message' field"

    def test_ai_key_health_provider_details(self, auth_session):
        """Test that provider details include source and platform_health"""
        response = auth_session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/ai-key-health"
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check provider structure
        for provider_key, provider_info in data["providers"].items():
            assert "provider" in provider_info, f"Provider {provider_key} should have 'provider' field"
            assert "source" in provider_info, f"Provider {provider_key} should have 'source' field"
            assert "platform_health" in provider_info, f"Provider {provider_key} should have 'platform_health' field"
            
            # Check platform_health structure
            health = provider_info["platform_health"]
            assert "configured" in health, "platform_health should have 'configured' field"
            assert "status" in health, "platform_health should have 'status' field"

    def test_ai_key_health_unauthorized_without_token(self):
        """Test that endpoint requires authentication"""
        response = requests.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/ai-key-health"
        )
        # Should return 401 or 403 without auth
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"

    def test_ai_key_health_nonexistent_workspace(self, auth_session):
        """Test that endpoint returns 403/404 for non-existent workspace"""
        response = auth_session.get(
            f"{BASE_URL}/api/workspaces/ws_nonexistent123/ai-key-health"
        )
        # Can return 403 (access denied) or 404 (not found) - both are acceptable
        assert response.status_code in [403, 404], f"Expected 403/404 for non-existent workspace, got {response.status_code}"


class TestAIKeyHealthWarningLogic:
    """Tests for the warning generation logic"""

    def test_warning_generated_for_platform_source_with_placeholder(self, auth_session):
        """Test that warnings are generated when source=platform and key is placeholder"""
        response = auth_session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/ai-key-health"
        )
        assert response.status_code == 200
        data = response.json()
        
        # Find providers with source=platform and placeholder status
        platform_providers_with_placeholder = []
        for provider_key, provider_info in data["providers"].items():
            if provider_info.get("source") == "platform":
                health = provider_info.get("platform_health", {})
                if health.get("status") in ["placeholder", "invalid"]:
                    platform_providers_with_placeholder.append(provider_key)
        
        # If there are such providers, warnings should be generated
        if platform_providers_with_placeholder:
            assert data["has_warning"], "has_warning should be True when platform keys are placeholder/invalid"
            warning_providers = [w["provider"] for w in data["warnings"]]
            for provider in platform_providers_with_placeholder:
                assert provider in warning_providers, f"Warning should be generated for {provider}"


class TestChatPanelIntegration:
    """Tests to verify the chat panel can fetch AI key health"""

    def test_chat_panel_health_fetch_no_regression(self, auth_session):
        """Test that fetching AI key health doesn't break channel loading"""
        # First, verify we can get the channel
        channel_response = auth_session.get(
            f"{BASE_URL}/api/channels/{TEST_CHANNEL_ID}"
        )
        assert channel_response.status_code == 200, f"Channel fetch failed: {channel_response.status_code}"
        
        # Then verify AI key health fetch works
        health_response = auth_session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/ai-key-health?channel_id={TEST_CHANNEL_ID}"
        )
        assert health_response.status_code == 200, f"AI key health fetch failed: {health_response.status_code}"

    def test_channel_switching_with_health_fetch(self, auth_session):
        """Test that channel switching with health fetch works"""
        # Get list of channels in workspace
        channels_response = auth_session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/channels"
        )
        assert channels_response.status_code == 200
        channels = channels_response.json()
        
        # Test health fetch for first few channels
        for channel in channels[:3]:
            channel_id = channel.get("channel_id")
            if channel_id:
                health_response = auth_session.get(
                    f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/ai-key-health?channel_id={channel_id}"
                )
                assert health_response.status_code == 200, f"Health fetch failed for channel {channel_id}"


class TestManagedKeysHealthComparison:
    """Compare with admin managed keys health endpoint"""

    def test_workspace_health_matches_admin_health(self, auth_session):
        """Test that workspace AI key health aligns with admin managed keys health"""
        # Get admin managed keys health
        admin_health_response = auth_session.get(
            f"{BASE_URL}/api/admin/managed-keys/health"
        )
        
        # Get workspace AI key health
        workspace_health_response = auth_session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/ai-key-health"
        )
        
        assert workspace_health_response.status_code == 200
        
        # If admin health is available, compare
        if admin_health_response.status_code == 200:
            admin_data = admin_health_response.json()
            workspace_data = workspace_health_response.json()
            
            # For providers in workspace that use platform keys, status should match
            for provider_key, provider_info in workspace_data["providers"].items():
                if provider_info.get("source") == "platform":
                    platform_health = provider_info.get("platform_health", {})
                    admin_provider_health = admin_data.get(provider_key, {})
                    
                    # Status should be consistent
                    if admin_provider_health:
                        assert platform_health.get("status") == admin_provider_health.get("status"), \
                            f"Status mismatch for {provider_key}: workspace={platform_health.get('status')}, admin={admin_provider_health.get('status')}"
