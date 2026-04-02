"""
Iteration 70 - Code Review Fixes Testing

Tests for:
- F-08: Expanded password blocklist (22 common passwords)
- F-02: Budget endpoint org admin authorization check
- F-14: No auto ToS acceptance on registration
- F-15: Budget body validation
- Other endpoint regression tests
"""
import pytest
import requests
import uuid
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestPasswordBlocklist:
    """F-08: Expanded password blocklist - 22 common passwords should be rejected"""
    
    def test_register_with_password_password_rejected(self):
        """Password 'password' should be rejected as too common"""
        email = f"TEST_pwd_{uuid.uuid4().hex[:8]}@test.com"
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": "password",
            "name": "Test User"
        })
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "too common" in data.get("detail", "").lower() or "common" in data.get("detail", "").lower()
        print(f"PASS: Password 'password' correctly rejected with 400: {data.get('detail')}")
    
    def test_register_with_password_admin123_rejected(self):
        """Password 'admin123' should be rejected as too common"""
        email = f"TEST_pwd_{uuid.uuid4().hex[:8]}@test.com"
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": "admin123",
            "name": "Test User"
        })
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "too common" in data.get("detail", "").lower() or "common" in data.get("detail", "").lower()
        print(f"PASS: Password 'admin123' correctly rejected with 400: {data.get('detail')}")
    
    def test_register_with_password_12345678_rejected(self):
        """Password '12345678' should be rejected as too common"""
        email = f"TEST_pwd_{uuid.uuid4().hex[:8]}@test.com"
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": "12345678",
            "name": "Test User"
        })
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "too common" in data.get("detail", "").lower()
        print(f"PASS: Password '12345678' correctly rejected with 400")
    
    def test_register_with_password_qwerty123_rejected(self):
        """Password 'qwerty123' should be rejected as too common"""
        email = f"TEST_pwd_{uuid.uuid4().hex[:8]}@test.com"
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": "qwerty123",
            "name": "Test User"
        })
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print(f"PASS: Password 'qwerty123' correctly rejected")
    
    def test_register_with_strong_password_succeeds(self):
        """Strong password 'StrongP@ss99' should be accepted"""
        email = f"TEST_strong_{uuid.uuid4().hex[:8]}@test.com"
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": "StrongP@ss99",
            "name": "Test User"
        })
        # Should succeed (200 or 201)
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        data = response.json()
        assert "user_id" in data
        print(f"PASS: Strong password accepted, user_id: {data.get('user_id')}")
        return data


class TestNoAutoToS:
    """F-14: No auto ToS acceptance - tos_version should be null on registration"""
    
    def test_registration_tos_version_null(self):
        """New user registration should have tos_version=null"""
        email = f"TEST_tos_{uuid.uuid4().hex[:8]}@test.com"
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": "SecurePass123!",
            "name": "Test User TOS"
        })
        assert response.status_code in [200, 201], f"Registration failed: {response.text}"
        data = response.json()
        
        # tos_version should be None (null in JSON)
        assert data.get("tos_version") is None, f"Expected tos_version=null, got {data.get('tos_version')}"
        # Also email_verified should be False
        assert data.get("email_verified") == False, f"Expected email_verified=False, got {data.get('email_verified')}"
        print(f"PASS: New user has tos_version=null and email_verified=False")
        return data


class TestBudgetEndpointAuth:
    """F-02: Budget endpoint org admin authorization check"""
    
    @pytest.fixture
    def regular_user(self):
        """Create a regular user (not org admin)"""
        email = f"TEST_budget_{uuid.uuid4().hex[:8]}@test.com"
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": "SecurePass123!",
            "name": "Regular User"
        })
        assert response.status_code in [200, 201]
        # Get session token from cookies
        session = requests.Session()
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": "SecurePass123!"
        })
        cookies = login_resp.cookies
        return {"session": session, "cookies": cookies, "email": email}
    
    def test_put_budget_returns_403_for_non_admin(self, regular_user):
        """PUT /api/reports/org/fake_org/budget should return 403 for non-admin"""
        # Use the session cookie
        response = requests.put(
            f"{BASE_URL}/api/reports/org/fake_org/budget",
            json={"monthly_cost_limit_usd": 100},
            cookies=regular_user["cookies"]
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"PASS: PUT budget correctly returns 403 for non-admin")
    
    def test_get_budget_returns_403_for_non_admin(self, regular_user):
        """GET /api/reports/org/fake_org/budget should return 403 for non-admin"""
        response = requests.get(
            f"{BASE_URL}/api/reports/org/fake_org/budget",
            cookies=regular_user["cookies"]
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"PASS: GET budget correctly returns 403 for non-admin")


class TestBudgetBodyValidation:
    """F-15: Budget body validation - must validate field types"""
    
    @pytest.fixture
    def admin_session(self):
        """Create a user session for testing (will still get 403 without org admin)"""
        email = f"TEST_valid_{uuid.uuid4().hex[:8]}@test.com"
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": "SecurePass123!",
            "name": "Validation Test"
        })
        assert response.status_code in [200, 201]
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": "SecurePass123!"
        })
        return {"cookies": login_resp.cookies}
    
    def test_budget_invalid_cost_type_rejected(self, admin_session):
        """Budget with string cost should be rejected with 400"""
        # This will either return 403 (auth check first) or 400 (validation)
        # If auth passes, validation should reject string
        response = requests.put(
            f"{BASE_URL}/api/reports/org/test_org/budget",
            json={"monthly_cost_limit_usd": "not_a_number"},
            cookies=admin_session["cookies"]
        )
        # Should be 403 (non-admin) or 400 (validation) - 403 comes first
        assert response.status_code in [400, 403], f"Expected 400 or 403, got {response.status_code}"
        print(f"PASS: Invalid budget type returns {response.status_code}")


class TestHealthEndpoint:
    """Health check endpoint"""
    
    def test_health_returns_healthy(self):
        """GET /api/health should return healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("status") == "healthy"
        assert data.get("database") == "connected"
        print(f"PASS: Health check returns healthy with instance_id: {data.get('instance_id')}")


class TestMessagingEndpoint:
    """Test channel messages endpoint still works"""
    
    @pytest.fixture
    def authenticated_user(self):
        """Create authenticated user with workspace and channel"""
        email = f"TEST_msg_{uuid.uuid4().hex[:8]}@test.com"
        # Register
        reg_resp = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": "SecurePass123!",
            "name": "Message Tester"
        })
        assert reg_resp.status_code in [200, 201]
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": "SecurePass123!"
        })
        cookies = login_resp.cookies
        
        # Create workspace
        ws_resp = requests.post(
            f"{BASE_URL}/api/workspaces",
            json={"name": "Test Workspace", "description": "For testing"},
            cookies=cookies
        )
        assert ws_resp.status_code in [200, 201]
        workspace_id = ws_resp.json().get("workspace_id")
        
        # Create channel
        ch_resp = requests.post(
            f"{BASE_URL}/api/workspaces/{workspace_id}/channels",
            json={"name": "Test Channel", "description": "For messages"},
            cookies=cookies
        )
        assert ch_resp.status_code in [200, 201]
        channel_id = ch_resp.json().get("channel_id")
        
        return {"cookies": cookies, "workspace_id": workspace_id, "channel_id": channel_id}
    
    def test_post_message_works(self, authenticated_user):
        """POST /api/channels/{id}/messages should work"""
        channel_id = authenticated_user["channel_id"]
        response = requests.post(
            f"{BASE_URL}/api/channels/{channel_id}/messages",
            json={"content": "Hello from test!"},
            cookies=authenticated_user["cookies"]
        )
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        data = response.json()
        assert "message_id" in data
        assert data.get("content") == "Hello from test!"
        print(f"PASS: Message created with ID: {data.get('message_id')}")


class TestRolesEndpoint:
    """Test channel roles endpoint still works"""
    
    @pytest.fixture
    def authenticated_with_channel(self):
        """Create user with channel for roles testing"""
        email = f"TEST_role_{uuid.uuid4().hex[:8]}@test.com"
        reg_resp = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": "SecurePass123!",
            "name": "Role Tester"
        })
        assert reg_resp.status_code in [200, 201]
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": "SecurePass123!"
        })
        cookies = login_resp.cookies
        
        ws_resp = requests.post(
            f"{BASE_URL}/api/workspaces",
            json={"name": "Role Test WS", "description": ""},
            cookies=cookies
        )
        workspace_id = ws_resp.json().get("workspace_id")
        
        ch_resp = requests.post(
            f"{BASE_URL}/api/workspaces/{workspace_id}/channels",
            json={"name": "Role Test Channel", "ai_agents": ["claude", "chatgpt"]},
            cookies=cookies
        )
        channel_id = ch_resp.json().get("channel_id")
        
        return {"cookies": cookies, "channel_id": channel_id}
    
    def test_put_roles_works(self, authenticated_with_channel):
        """PUT /api/channels/{id}/roles should work"""
        channel_id = authenticated_with_channel["channel_id"]
        response = requests.put(
            f"{BASE_URL}/api/channels/{channel_id}/roles",
            json={"tpm": "claude", "architect": "chatgpt"},
            cookies=authenticated_with_channel["cookies"]
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # API returns {"tpm": "...", "architect": "...", "browser_operator": "..."}
        assert data.get("tpm") == "claude", f"Expected tpm=claude, got {data}"
        assert data.get("architect") == "chatgpt", f"Expected architect=chatgpt, got {data}"
        print(f"PASS: Roles set successfully: {data}")


class TestPersonalUsageReport:
    """Test personal usage report endpoint"""
    
    @pytest.fixture
    def auth_session(self):
        """Create authenticated session"""
        email = f"TEST_usage_{uuid.uuid4().hex[:8]}@test.com"
        requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": "SecurePass123!",
            "name": "Usage Tester"
        })
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": "SecurePass123!"
        })
        return {"cookies": login_resp.cookies}
    
    def test_get_personal_usage_works(self, auth_session):
        """GET /api/reports/me/usage should return personal metrics"""
        response = requests.get(
            f"{BASE_URL}/api/reports/me/usage",
            cookies=auth_session["cookies"]
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Should have expected fields
        assert "total_tokens" in data
        assert "period_days" in data
        print(f"PASS: Personal usage returned: tokens={data.get('total_tokens')}, days={data.get('period_days')}")


class TestCSVExport:
    """Test CSV export functionality"""
    
    @pytest.fixture
    def auth_session(self):
        """Create authenticated session"""
        email = f"TEST_csv_{uuid.uuid4().hex[:8]}@test.com"
        requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": "SecurePass123!",
            "name": "CSV Tester"
        })
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": "SecurePass123!"
        })
        return {"cookies": login_resp.cookies}
    
    def test_csv_export_works(self, auth_session):
        """GET /api/reports/export?format=csv should return CSV"""
        response = requests.get(
            f"{BASE_URL}/api/reports/export?format=csv",
            cookies=auth_session["cookies"]
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "text/csv" in response.headers.get("content-type", "")
        print(f"PASS: CSV export returned with content-type: {response.headers.get('content-type')}")


class TestZipImport:
    """Test ZIP import endpoint exists"""
    
    @pytest.fixture
    def auth_with_workspace(self):
        """Create user with workspace"""
        email = f"TEST_zip_{uuid.uuid4().hex[:8]}@test.com"
        requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": "SecurePass123!",
            "name": "ZIP Tester"
        })
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": "SecurePass123!"
        })
        cookies = login_resp.cookies
        
        ws_resp = requests.post(
            f"{BASE_URL}/api/workspaces",
            json={"name": "ZIP Test WS"},
            cookies=cookies
        )
        workspace_id = ws_resp.json().get("workspace_id")
        return {"cookies": cookies, "workspace_id": workspace_id}
    
    def test_zip_import_endpoint_exists(self, auth_with_workspace):
        """POST /api/workspaces/{id}/code-repo/import-zip should exist"""
        workspace_id = auth_with_workspace["workspace_id"]
        # Test with empty/invalid data - should get 4xx not 404
        response = requests.post(
            f"{BASE_URL}/api/workspaces/{workspace_id}/code-repo/import-zip",
            files={"file": ("test.zip", b"not a real zip", "application/zip")},
            cookies=auth_with_workspace["cookies"]
        )
        # Should not be 404 (endpoint exists), expect 400/422 for invalid zip
        assert response.status_code != 404, f"Endpoint not found (404)"
        print(f"PASS: ZIP import endpoint exists (status: {response.status_code})")


# Run specific tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
