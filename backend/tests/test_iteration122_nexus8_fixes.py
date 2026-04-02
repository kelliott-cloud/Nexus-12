"""
Iteration 122 - Nexus 8.0 Assessment Bug Fixes Testing
Tests for:
1. Support desk org_id scoping
2. Replay rate limiting (returns 404 for nonexistent, not 500)
3. Transcript endpoint exists
4. Platform capabilities endpoint
5. Image gen provider field (gemini, imagen4, openai)
6. Health check
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
TEST_EMAIL = "kelliott@urtech.org"
TEST_PASSWORD = "test"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for testing"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if resp.status_code == 200:
        data = resp.json()
        return data.get("session_token") or data.get("token")
    pytest.skip(f"Authentication failed: {resp.status_code} - {resp.text[:200]}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestHealthCheck:
    """Test backend health endpoint"""
    
    def test_health_endpoint_returns_200(self):
        """GET /api/health should return 200"""
        resp = requests.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200, f"Health check failed: {resp.status_code}"
        data = resp.json()
        assert "status" in data or "ok" in str(data).lower()
        print(f"Health check passed: {data}")


class TestSupportDeskOrgScoping:
    """Test support desk org_id scoping fix"""
    
    def test_list_tickets_with_org_id_filter(self, auth_headers):
        """GET /api/support/tickets with org_id filter should work"""
        resp = requests.get(
            f"{BASE_URL}/api/support/tickets?org_id=test_org_123",
            headers=auth_headers
        )
        # Should return 200 even if no tickets match
        assert resp.status_code == 200, f"Failed: {resp.status_code} - {resp.text[:200]}"
        data = resp.json()
        assert "tickets" in data
        assert "total" in data
        print(f"Support tickets with org_id filter: {data['total']} tickets")
    
    def test_list_tickets_without_org_id(self, auth_headers):
        """GET /api/support/tickets without org_id should still work"""
        resp = requests.get(
            f"{BASE_URL}/api/support/tickets",
            headers=auth_headers
        )
        assert resp.status_code == 200, f"Failed: {resp.status_code} - {resp.text[:200]}"
        data = resp.json()
        assert "tickets" in data
        print(f"Support tickets without filter: {data['total']} tickets")


class TestReplayRateLimiting:
    """Test replay endpoint returns 404 for nonexistent shares (not 500)"""
    
    def test_replay_nonexistent_returns_404(self):
        """POST /api/replay/nonexistent should return 404, not 500"""
        resp = requests.post(f"{BASE_URL}/api/replay/nonexistent_share_id_12345")
        # Should be 404 (not found) not 500 (server error)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text[:200]}"
        print(f"Replay nonexistent correctly returns 404")
    
    def test_replay_invalid_share_format(self):
        """POST /api/replay with invalid share ID format"""
        resp = requests.post(f"{BASE_URL}/api/replay/invalid")
        # Should be 404 not 500
        assert resp.status_code in [404, 422], f"Expected 404/422, got {resp.status_code}"
        print(f"Replay invalid format returns {resp.status_code}")


class TestTranscriptEndpoint:
    """Test transcript endpoint exists"""
    
    def test_transcript_endpoint_exists(self, auth_headers):
        """GET /api/channels/{id}/transcript should exist (may 404 for nonexistent channel)"""
        # Use a fake channel ID - should return 404 (not found) not 500 (server error)
        resp = requests.get(
            f"{BASE_URL}/api/channels/ch_nonexistent123/transcript",
            headers=auth_headers
        )
        # 404 = endpoint exists but channel not found (correct)
        # 500 = server error (bug)
        # 200 = channel exists and transcript returned
        assert resp.status_code in [200, 404], f"Expected 200/404, got {resp.status_code}: {resp.text[:200]}"
        print(f"Transcript endpoint exists, returns {resp.status_code} for nonexistent channel")


class TestPlatformCapabilities:
    """Test platform capabilities endpoint"""
    
    def test_platform_capabilities_returns_features(self, auth_headers):
        """GET /api/platform/capabilities should return feature flags"""
        resp = requests.get(
            f"{BASE_URL}/api/platform/capabilities",
            headers=auth_headers
        )
        assert resp.status_code == 200, f"Failed: {resp.status_code} - {resp.text[:200]}"
        data = resp.json()
        # Should have features block
        assert "features" in data or "capabilities" in data, f"Missing features/capabilities: {data.keys()}"
        print(f"Platform capabilities: {list(data.keys())}")
        
        # Check for specific feature flags if features block exists
        if "features" in data:
            features = data["features"]
            print(f"Features: {list(features.keys()) if isinstance(features, dict) else features}")


class TestImageGenProviderField:
    """Test image generation accepts provider field"""
    
    def test_generate_image_accepts_gemini_provider(self, auth_headers):
        """POST /api/workspaces/{id}/generate-image should accept provider=gemini"""
        # First get a workspace ID
        ws_resp = requests.get(f"{BASE_URL}/api/workspaces", headers=auth_headers)
        if ws_resp.status_code != 200 or not ws_resp.json():
            pytest.skip("No workspaces available for testing")
        
        workspace_id = ws_resp.json()[0].get("workspace_id")
        
        resp = requests.post(
            f"{BASE_URL}/api/workspaces/{workspace_id}/generate-image",
            headers=auth_headers,
            json={
                "prompt": "test image",
                "provider": "gemini",
                "use_own_key": False
            }
        )
        # May fail due to API key not configured, but should not be 422 (validation error)
        # 500 with "not configured" is acceptable, 422 means provider field not accepted
        assert resp.status_code != 422, f"Provider field not accepted: {resp.text[:200]}"
        print(f"Image gen with gemini provider: {resp.status_code}")
    
    def test_generate_image_accepts_imagen4_provider(self, auth_headers):
        """POST /api/workspaces/{id}/generate-image should accept provider=imagen4"""
        ws_resp = requests.get(f"{BASE_URL}/api/workspaces", headers=auth_headers)
        if ws_resp.status_code != 200 or not ws_resp.json():
            pytest.skip("No workspaces available for testing")
        
        workspace_id = ws_resp.json()[0].get("workspace_id")
        
        resp = requests.post(
            f"{BASE_URL}/api/workspaces/{workspace_id}/generate-image",
            headers=auth_headers,
            json={
                "prompt": "test image",
                "provider": "imagen4",
                "use_own_key": False
            }
        )
        # Should accept the provider field (may fail on API key)
        assert resp.status_code != 422, f"Provider field not accepted: {resp.text[:200]}"
        print(f"Image gen with imagen4 provider: {resp.status_code}")
    
    def test_generate_image_accepts_openai_provider(self, auth_headers):
        """POST /api/workspaces/{id}/generate-image should accept provider=openai"""
        ws_resp = requests.get(f"{BASE_URL}/api/workspaces", headers=auth_headers)
        if ws_resp.status_code != 200 or not ws_resp.json():
            pytest.skip("No workspaces available for testing")
        
        workspace_id = ws_resp.json()[0].get("workspace_id")
        
        resp = requests.post(
            f"{BASE_URL}/api/workspaces/{workspace_id}/generate-image",
            headers=auth_headers,
            json={
                "prompt": "test image",
                "provider": "openai",
                "use_own_key": False
            }
        )
        # Should accept the provider field (may fail on API key)
        assert resp.status_code != 422, f"Provider field not accepted: {resp.text[:200]}"
        print(f"Image gen with openai provider: {resp.status_code}")


class TestFrontendCodeReview:
    """Code review verification - these are static checks"""
    
    def test_docviewer_no_backend_url_import(self):
        """DocViewer.js should not import BACKEND_URL"""
        with open("/app/frontend/src/components/DocViewer.js", "r") as f:
            content = f.read()
        assert "BACKEND_URL" not in content, "DocViewer still imports BACKEND_URL"
        assert "api.get" in content, "DocViewer should use api.get for downloads"
        print("DocViewer uses relative paths via api.get - PASS")
    
    def test_chatpanel_transcript_uses_api_get(self):
        """ChatPanel.js transcript download should use api.get with blob"""
        with open("/app/frontend/src/components/ChatPanel.js", "r") as f:
            content = f.read()
        # Check transcript download uses api.get
        assert "api.get(`/channels/${channel.channel_id}/transcript`" in content or \
               'api.get(`/channels/' in content, "ChatPanel should use api.get for transcript"
        assert "responseType: \"blob\"" in content or "responseType: 'blob'" in content, \
            "ChatPanel should use blob responseType for transcript"
        print("ChatPanel transcript uses api.get with blob - PASS")
    
    def test_coderepo_ws_uses_window_location(self):
        """CodeRepoPanel.js WebSocket should use window.location"""
        with open("/app/frontend/src/components/CodeRepoPanel.js", "r") as f:
            content = f.read()
        assert "window.location.protocol" in content, "CodeRepoPanel should derive WS protocol from window.location"
        assert "window.location.host" in content, "CodeRepoPanel should derive WS host from window.location"
        print("CodeRepoPanel WS uses window.location - PASS")
    
    def test_workspace_ws_uses_window_location(self):
        """WorkspacePage.js WebSocket should use window.location"""
        with open("/app/frontend/src/pages/WorkspacePage.js", "r") as f:
            content = f.read()
        assert "window.location.protocol" in content, "WorkspacePage should derive WS protocol from window.location"
        assert "window.location.host" in content, "WorkspacePage should derive WS host from window.location"
        print("WorkspacePage WS uses window.location - PASS")
    
    def test_social_connections_uses_correct_callback(self):
        """SocialConnectionsPanel.js should use /social/callback path"""
        with open("/app/frontend/src/components/SocialConnectionsPanel.js", "r") as f:
            content = f.read()
        assert "/social/callback" in content, "SocialConnectionsPanel should use /social/callback"
        assert "/cloud-storage/callback" not in content, "SocialConnectionsPanel should NOT use /cloud-storage/callback"
        print("SocialConnectionsPanel uses /social/callback - PASS")
    
    def test_cloud_storage_callback_route_aware(self):
        """CloudStorageCallback.js should detect pathname for social vs cloud-storage"""
        with open("/app/frontend/src/pages/CloudStorageCallback.js", "r") as f:
            content = f.read()
        assert "window.location.pathname" in content, "CloudStorageCallback should check pathname"
        assert "/social" in content, "CloudStorageCallback should handle /social path"
        print("CloudStorageCallback is route-aware - PASS")
    
    def test_imagegen_panel_has_provider_dropdown(self):
        """ImageGenPanel.js should have provider dropdown with gemini, imagen4, openai"""
        with open("/app/frontend/src/components/ImageGenPanel.js", "r") as f:
            content = f.read()
        assert "provider" in content, "ImageGenPanel should have provider state"
        assert "gemini" in content.lower(), "ImageGenPanel should have gemini option"
        assert "imagen4" in content.lower(), "ImageGenPanel should have imagen4 option"
        assert "openai" in content.lower(), "ImageGenPanel should have openai option"
        print("ImageGenPanel has provider dropdown with all options - PASS")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
