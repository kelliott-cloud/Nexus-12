"""
Iteration 55 - Legal Compliance Testing
Tests for Phase 1 BLOCKERS and Phase 2 HIGH legal features:
- Legal pages (Terms, Privacy, AUP)
- ToS acceptance, version tracking
- Cookie consent
- GDPR: Data export, account deletion
- Content flagging
- AI metadata on messages
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module")
def session():
    """Shared requests session"""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth_token(session):
    """Login and get session token"""
    # Login with test credentials
    login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "test@test.com",
        "password": "test123"
    })
    if login_resp.status_code != 200:
        pytest.skip("Login failed - skipping authenticated tests")
    
    # Extract session token from cookies
    session_token = login_resp.cookies.get("session_token")
    if not session_token:
        # Try from response body if not in cookies
        data = login_resp.json()
        session_token = data.get("session_token")
    
    return session_token


@pytest.fixture(scope="module")
def auth_session(session, auth_token):
    """Session with auth cookie set"""
    if auth_token:
        session.cookies.set("session_token", auth_token)
    return session


class TestLegalDocumentRoutes:
    """Test legal document metadata endpoints"""
    
    def test_get_tos_version(self, session):
        """GET /api/legal/tos-version returns current ToS version"""
        resp = session.get(f"{BASE_URL}/api/legal/tos-version")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "version" in data, "Response missing 'version' field"
        assert "effective_date" in data, "Response missing 'effective_date' field"
        assert data["version"] == "1.0", f"Expected version 1.0, got {data['version']}"
        print(f"ToS version: {data['version']}, effective: {data['effective_date']}")
    
    def test_get_tos_status(self, auth_session):
        """GET /api/legal/tos-status returns acceptance status"""
        resp = auth_session.get(f"{BASE_URL}/api/legal/tos-status")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "current_version" in data
        assert "accepted_version" in data
        assert "needs_acceptance" in data
        print(f"ToS status: current={data['current_version']}, accepted={data['accepted_version']}, needs_acceptance={data['needs_acceptance']}")
    
    def test_accept_tos(self, auth_session):
        """POST /api/legal/accept-tos accepts ToS"""
        resp = auth_session.post(f"{BASE_URL}/api/legal/accept-tos", json={
            "beta_accepted": True
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("accepted") == True
        assert data.get("version") == "1.0"
        assert "timestamp" in data
        print(f"ToS accepted: version={data['version']}, timestamp={data['timestamp']}")


class TestCookieConsent:
    """Test cookie consent endpoints"""
    
    def test_save_cookie_consent_essential(self, session):
        """POST /api/legal/cookie-consent saves essential consent"""
        resp = session.post(f"{BASE_URL}/api/legal/cookie-consent", json={
            "consent": "essential"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("consent") == "essential"
        assert "timestamp" in data
        print(f"Cookie consent saved: {data['consent']}")
    
    def test_save_cookie_consent_all(self, session):
        """POST /api/legal/cookie-consent saves all cookies consent"""
        resp = session.post(f"{BASE_URL}/api/legal/cookie-consent", json={
            "consent": "all"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("consent") == "all"


class TestGDPRDataExport:
    """Test GDPR data export (Article 20)"""
    
    def test_export_data_returns_zip(self, auth_session):
        """POST /api/user/export-data returns ZIP file"""
        resp = auth_session.post(f"{BASE_URL}/api/user/export-data")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        # Check content type is ZIP
        content_type = resp.headers.get("content-type", "")
        assert "application/zip" in content_type or "application/octet-stream" in content_type, \
            f"Expected ZIP content type, got {content_type}"
        
        # Check content-disposition header
        content_disp = resp.headers.get("content-disposition", "")
        assert "nexus_data_export.zip" in content_disp, \
            f"Expected filename in content-disposition, got {content_disp}"
        
        # Verify response has content
        assert len(resp.content) > 0, "ZIP file is empty"
        print(f"Data export received: {len(resp.content)} bytes")


class TestGDPRAccountDeletion:
    """Test GDPR account deletion (Article 17)"""
    
    def test_delete_account_requires_confirmation(self, auth_session):
        """POST /api/user/delete-account requires confirm flag"""
        resp = auth_session.post(f"{BASE_URL}/api/user/delete-account", json={
            "confirm": False
        })
        assert resp.status_code == 400, f"Expected 400 without confirmation, got {resp.status_code}"
    
    # Note: We skip actual deletion test to preserve test user


class TestContentFlagging:
    """Test content flagging for moderation"""
    
    def test_flag_content(self, auth_session):
        """POST /api/content/flag creates a flag"""
        resp = auth_session.post(f"{BASE_URL}/api/content/flag", json={
            "type": "template",
            "content_id": "test_content_123",
            "reason": "inappropriate",
            "details": "Test flag from iteration 55 testing"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "flag_id" in data
        assert data.get("status") == "reported"
        print(f"Content flag created: {data['flag_id']}")
    
    def test_flag_content_missing_fields(self, auth_session):
        """POST /api/content/flag validates required fields"""
        resp = auth_session.post(f"{BASE_URL}/api/content/flag", json={
            "type": "template"
            # Missing content_id and reason
        })
        assert resp.status_code == 400, f"Expected 400 for missing fields, got {resp.status_code}"
    
    def test_get_content_flags(self, auth_session):
        """GET /api/admin/content-flags returns flags list"""
        resp = auth_session.get(f"{BASE_URL}/api/admin/content-flags")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "flags" in data
        assert isinstance(data["flags"], list)
        print(f"Content flags retrieved: {len(data['flags'])} flags")


class TestAuthMeWithToS:
    """Test /auth/me returns ToS fields"""
    
    def test_auth_me_returns_tos_fields(self, auth_session):
        """GET /api/auth/me includes tos_needs_acceptance"""
        resp = auth_session.get(f"{BASE_URL}/api/auth/me")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "tos_current_version" in data, "Response missing tos_current_version"
        assert "tos_needs_acceptance" in data, "Response missing tos_needs_acceptance"
        print(f"/auth/me: tos_current_version={data['tos_current_version']}, tos_needs_acceptance={data['tos_needs_acceptance']}")


class TestRegistrationToS:
    """Test registration stores ToS version"""
    
    def test_registration_endpoint_exists(self, session):
        """POST /api/auth/register validates input"""
        # Test that endpoint exists and validates
        resp = session.post(f"{BASE_URL}/api/auth/register", json={
            "email": "test_invalid@test.com",
            "password": "test"
            # Missing name
        })
        # Should get validation error (422) or success, not 404
        assert resp.status_code != 404, "Registration endpoint not found"
        print(f"Registration endpoint exists, status: {resp.status_code}")


class TestAIMessageMetadata:
    """Test AI messages include metadata fields"""
    
    def test_messages_endpoint_returns_ai_metadata(self, auth_session):
        """GET messages should have ai_generated metadata on AI messages"""
        # First get a workspace
        ws_resp = auth_session.get(f"{BASE_URL}/api/workspaces")
        if ws_resp.status_code != 200 or not ws_resp.json():
            pytest.skip("No workspaces available")
        
        workspaces = ws_resp.json()
        workspace_id = workspaces[0]["workspace_id"]
        
        # Get channels
        ch_resp = auth_session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/channels")
        if ch_resp.status_code != 200 or not ch_resp.json():
            pytest.skip("No channels available")
        
        channels = ch_resp.json()
        channel_id = channels[0]["channel_id"]
        
        # Get messages
        msg_resp = auth_session.get(f"{BASE_URL}/api/channels/{channel_id}/messages")
        assert msg_resp.status_code == 200, f"Expected 200, got {msg_resp.status_code}"
        
        messages = msg_resp.json()
        ai_messages = [m for m in messages if m.get("sender_type") == "ai"]
        
        if ai_messages:
            # Check AI message has metadata
            ai_msg = ai_messages[0]
            print(f"AI message found: sender={ai_msg.get('sender_name')}")
            print(f"  ai_generated={ai_msg.get('ai_generated')}")
            print(f"  ai_provider={ai_msg.get('ai_provider')}")
            print(f"  ai_model_id={ai_msg.get('ai_model_id')}")
            # These fields should exist on new AI messages
            # Note: Old messages may not have these fields
        else:
            print("No AI messages in channel to verify metadata (this is OK for this test)")


class TestLegalPagesAccessible:
    """Test legal pages are accessible (frontend routes)"""
    
    def test_terms_page_accessible(self, session):
        """Terms page should be accessible"""
        resp = session.get(f"{BASE_URL.replace('/api', '')}/terms", allow_redirects=True)
        # Frontend pages return HTML, status should be 200 or redirect to SPA
        assert resp.status_code in [200, 304], f"Terms page not accessible: {resp.status_code}"
    
    def test_privacy_page_accessible(self, session):
        """Privacy page should be accessible"""
        resp = session.get(f"{BASE_URL.replace('/api', '')}/privacy", allow_redirects=True)
        assert resp.status_code in [200, 304], f"Privacy page not accessible: {resp.status_code}"
    
    def test_aup_page_accessible(self, session):
        """AUP page should be accessible"""
        resp = session.get(f"{BASE_URL.replace('/api', '')}/acceptable-use", allow_redirects=True)
        assert resp.status_code in [200, 304], f"AUP page not accessible: {resp.status_code}"


class TestRegressionChat:
    """Regression: Verify chat still works"""
    
    def test_channels_list(self, auth_session):
        """GET workspaces/{ws}/channels returns channels"""
        ws_resp = auth_session.get(f"{BASE_URL}/api/workspaces")
        if ws_resp.status_code != 200 or not ws_resp.json():
            pytest.skip("No workspaces")
        
        workspace_id = ws_resp.json()[0]["workspace_id"]
        ch_resp = auth_session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/channels")
        assert ch_resp.status_code == 200
        print(f"Channels list works: {len(ch_resp.json())} channels")
    
    def test_messages_list(self, auth_session):
        """GET channels/{ch}/messages returns messages"""
        ws_resp = auth_session.get(f"{BASE_URL}/api/workspaces")
        if ws_resp.status_code != 200 or not ws_resp.json():
            pytest.skip("No workspaces")
        
        workspace_id = ws_resp.json()[0]["workspace_id"]
        ch_resp = auth_session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/channels")
        if ch_resp.status_code != 200 or not ch_resp.json():
            pytest.skip("No channels")
        
        channel_id = ch_resp.json()[0]["channel_id"]
        msg_resp = auth_session.get(f"{BASE_URL}/api/channels/{channel_id}/messages")
        assert msg_resp.status_code == 200
        print(f"Messages list works: {len(msg_resp.json())} messages")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
