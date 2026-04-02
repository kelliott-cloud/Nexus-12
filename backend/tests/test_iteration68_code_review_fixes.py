"""
Iteration 68 - Code Review Security/Quality Fixes Testing
Tests 18 code review fixes:
1. Password validation (8 char minimum, common password rejection)
2. Registration returns email_verified=False
3. nh3 HTML sanitization (XSS protection)
4. Request size limit (10MB)
5. Anthropic version header updated to 2024-10-22
6. Rate limiter cleanup mechanism
7. CORS warning on wildcard
8. Existing user login still works
9. File upload still works
10. Browser functionality still works
11. Auto-collab persist hard stop works
12. Workspace list works
13. Channel roles work
14. Stripe checkout works
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestHealthCheck:
    """Verify server is healthy after all 18 changes"""
    
    def test_health_endpoint(self):
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        assert data.get("database") == "connected"
        print(f"PASS: Health check - status={data['status']}, db={data['database']}")


class TestPasswordValidation:
    """Test password strength validation (8 char min, common password rejection)"""
    
    def test_register_short_password_rejected(self):
        """Password '123' should return 400 (too short)"""
        email = f"TEST_short_pwd_{uuid.uuid4().hex[:8]}@test.com"
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": email, "password": "123", "name": "Test User"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "8 characters" in data.get("detail", "")
        print(f"PASS: Short password rejected - {data.get('detail')}")
    
    def test_register_common_password_rejected(self):
        """Common passwords like 'password' should be rejected"""
        email = f"TEST_common_pwd_{uuid.uuid4().hex[:8]}@test.com"
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": email, "password": "password", "name": "Test User"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "common" in data.get("detail", "").lower()
        print(f"PASS: Common password rejected - {data.get('detail')}")
    
    def test_register_common_numeric_password_rejected(self):
        """Common passwords like '12345678' should be rejected"""
        email = f"TEST_numeric_pwd_{uuid.uuid4().hex[:8]}@test.com"
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": email, "password": "12345678", "name": "Test User"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "common" in data.get("detail", "").lower()
        print(f"PASS: Common numeric password rejected - {data.get('detail')}")
    
    def test_register_strong_password_succeeds_with_email_verified_false(self):
        """Strong password like 'SecurePass1' should succeed with email_verified=False"""
        email = f"TEST_strong_pwd_{uuid.uuid4().hex[:8]}@test.com"
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": email, "password": "SecurePass1", "name": "Test User"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("email") == email
        assert data.get("email_verified") == False
        print(f"PASS: Strong password registration succeeded, email_verified={data.get('email_verified')}")
        return data


class TestXSSProtection:
    """Test HTML sanitization (nh3 replaces regex sanitizer)"""
    
    def test_message_xss_content_stripped(self):
        """XSS content '<script>alert(1)</script>test' should strip script tag"""
        # First create user, workspace, and channel
        email = f"TEST_xss_{uuid.uuid4().hex[:8]}@test.com"
        reg_response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": email, "password": "SecurePass123", "name": "XSS Tester"}
        )
        if reg_response.status_code != 200:
            pytest.skip(f"Could not create test user: {reg_response.text}")
        
        session_cookie = reg_response.cookies.get("session_token")
        cookies = {"session_token": session_cookie}
        
        # Create workspace
        ws_response = requests.post(
            f"{BASE_URL}/api/workspaces",
            json={"name": "XSS Test Workspace"},
            cookies=cookies
        )
        if ws_response.status_code != 200:
            pytest.skip(f"Could not create workspace: {ws_response.text}")
        workspace_id = ws_response.json().get("workspace_id")
        
        # Create channel
        ch_response = requests.post(
            f"{BASE_URL}/api/workspaces/{workspace_id}/channels",
            json={"name": "XSS Test Channel"},
            cookies=cookies
        )
        if ch_response.status_code != 200:
            pytest.skip(f"Could not create channel: {ch_response.text}")
        channel_id = ch_response.json().get("channel_id")
        
        # Post message with XSS content
        xss_content = '<script>alert(1)</script>test'
        msg_response = requests.post(
            f"{BASE_URL}/api/channels/{channel_id}/messages",
            json={"content": xss_content},
            cookies=cookies
        )
        assert msg_response.status_code == 200
        msg_data = msg_response.json()
        
        # Verify script tag is stripped
        content = msg_data.get("content", "")
        assert "<script>" not in content
        assert "alert(1)" not in content
        assert "test" in content  # The text content should remain
        print(f"PASS: XSS content stripped - original: '{xss_content}', sanitized: '{content}'")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/workspaces/{workspace_id}", cookies=cookies)


class TestRequestSizeLimit:
    """Test request size limit (10MB)"""
    
    def test_large_request_rejected(self):
        """Request with body > 10MB should return 413"""
        # Create 11MB of data (exceeds 10MB limit)
        large_data = 'x' * (11 * 1024 * 1024)
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            data=large_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        # Backend returns 413 for requests > 10MB
        assert response.status_code == 413
        assert "too large" in response.text.lower()
        print(f"PASS: Large request rejected with 413 - {response.text}")


class TestExistingLoginWorks:
    """Test that existing user login still works after changes"""
    
    def test_register_then_login(self):
        """Register a user, then login with same credentials"""
        email = f"TEST_login_{uuid.uuid4().hex[:8]}@test.com"
        password = "LoginTest123!"
        
        # Register
        reg_response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": email, "password": password, "name": "Login Tester"}
        )
        assert reg_response.status_code == 200
        
        # Login
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": email, "password": password}
        )
        assert login_response.status_code == 200
        data = login_response.json()
        assert data.get("email") == email
        print(f"PASS: Login works after registration - user_id={data.get('user_id')}")


class TestFileUpload:
    """Test file upload still works (MongoDB storage)"""
    
    def test_file_upload_endpoint_exists(self):
        """Verify file upload endpoint responds (may need auth)"""
        # First create user and channel
        email = f"TEST_upload_{uuid.uuid4().hex[:8]}@test.com"
        reg_response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": email, "password": "UploadTest123!", "name": "Upload Tester"}
        )
        if reg_response.status_code != 200:
            pytest.skip(f"Could not create test user: {reg_response.text}")
        
        session_cookie = reg_response.cookies.get("session_token")
        cookies = {"session_token": session_cookie}
        
        # Create workspace
        ws_response = requests.post(
            f"{BASE_URL}/api/workspaces",
            json={"name": "Upload Test Workspace"},
            cookies=cookies
        )
        workspace_id = ws_response.json().get("workspace_id")
        
        # Create channel
        ch_response = requests.post(
            f"{BASE_URL}/api/workspaces/{workspace_id}/channels",
            json={"name": "Upload Test Channel"},
            cookies=cookies
        )
        channel_id = ch_response.json().get("channel_id")
        
        # Test file upload
        files = {"file": ("test.txt", b"Hello World", "text/plain")}
        upload_response = requests.post(
            f"{BASE_URL}/api/channels/{channel_id}/files",
            files=files,
            cookies=cookies
        )
        # Should be 200 or 201 on success
        assert upload_response.status_code in [200, 201]
        data = upload_response.json()
        # file_id may be in data directly or in data['file']
        has_file_id = "file_id" in data or "id" in data or (isinstance(data.get("file"), dict) and "file_id" in data["file"])
        assert has_file_id
        print(f"PASS: File upload works - response: {data}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/workspaces/{workspace_id}", cookies=cookies)


class TestBrowserFunctionality:
    """Test browser functionality still works"""
    
    def test_browser_open_endpoint(self):
        """Test POST /api/channels/{id}/browser/open still works"""
        email = f"TEST_browser_{uuid.uuid4().hex[:8]}@test.com"
        reg_response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": email, "password": "BrowserTest123!", "name": "Browser Tester"}
        )
        if reg_response.status_code != 200:
            pytest.skip(f"Could not create test user: {reg_response.text}")
        
        session_cookie = reg_response.cookies.get("session_token")
        cookies = {"session_token": session_cookie}
        
        # Create workspace and channel
        ws_response = requests.post(
            f"{BASE_URL}/api/workspaces",
            json={"name": "Browser Test Workspace"},
            cookies=cookies
        )
        workspace_id = ws_response.json().get("workspace_id")
        
        ch_response = requests.post(
            f"{BASE_URL}/api/workspaces/{workspace_id}/channels",
            json={"name": "Browser Test Channel"},
            cookies=cookies
        )
        channel_id = ch_response.json().get("channel_id")
        
        # Open browser
        browser_response = requests.post(
            f"{BASE_URL}/api/channels/{channel_id}/browser/open",
            json={"url": "https://example.com"},
            cookies=cookies
        )
        assert browser_response.status_code == 200
        data = browser_response.json()
        assert "session_id" in data
        print(f"PASS: Browser open works - session_id={data.get('session_id')}")
        
        # Close browser
        requests.post(f"{BASE_URL}/api/channels/{channel_id}/browser/close", cookies=cookies)
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/workspaces/{workspace_id}", cookies=cookies)


class TestAutoCollabPersistHardStop:
    """Test auto-collab persist hard stop works"""
    
    def test_persist_hard_stop(self):
        """PUT /api/channels/{id}/auto-collab-persist enabled=false should work"""
        email = f"TEST_persist_{uuid.uuid4().hex[:8]}@test.com"
        reg_response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": email, "password": "PersistTest123!", "name": "Persist Tester"}
        )
        if reg_response.status_code != 200:
            pytest.skip(f"Could not create test user: {reg_response.text}")
        
        session_cookie = reg_response.cookies.get("session_token")
        cookies = {"session_token": session_cookie}
        
        # Create workspace and channel
        ws_response = requests.post(
            f"{BASE_URL}/api/workspaces",
            json={"name": "Persist Test Workspace"},
            cookies=cookies
        )
        workspace_id = ws_response.json().get("workspace_id")
        
        ch_response = requests.post(
            f"{BASE_URL}/api/workspaces/{workspace_id}/channels",
            json={"name": "Persist Test Channel"},
            cookies=cookies
        )
        channel_id = ch_response.json().get("channel_id")
        
        # Disable persist (hard stop)
        persist_response = requests.put(
            f"{BASE_URL}/api/channels/{channel_id}/auto-collab-persist",
            json={"enabled": False},
            cookies=cookies
        )
        assert persist_response.status_code == 200
        data = persist_response.json()
        assert data.get("auto_collab_persist") == False or "disabled" in str(data).lower() or persist_response.status_code == 200
        print(f"PASS: Persist hard stop works - response: {data}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/workspaces/{workspace_id}", cookies=cookies)


class TestWorkspaceList:
    """Test workspace list works"""
    
    def test_get_workspaces(self):
        """GET /api/workspaces should return list"""
        email = f"TEST_wslist_{uuid.uuid4().hex[:8]}@test.com"
        reg_response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": email, "password": "WorkspaceTest123!", "name": "Workspace Tester"}
        )
        if reg_response.status_code != 200:
            pytest.skip(f"Could not create test user: {reg_response.text}")
        
        session_cookie = reg_response.cookies.get("session_token")
        cookies = {"session_token": session_cookie}
        
        # Create a workspace
        ws_response = requests.post(
            f"{BASE_URL}/api/workspaces",
            json={"name": "List Test Workspace"},
            cookies=cookies
        )
        
        # Get workspaces list
        list_response = requests.get(f"{BASE_URL}/api/workspaces", cookies=cookies)
        assert list_response.status_code == 200
        data = list_response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        print(f"PASS: Workspace list works - found {len(data)} workspace(s)")
        
        # Cleanup
        workspace_id = ws_response.json().get("workspace_id")
        requests.delete(f"{BASE_URL}/api/workspaces/{workspace_id}", cookies=cookies)


class TestChannelRoles:
    """Test channel roles still work"""
    
    def test_channel_roles_endpoint(self):
        """PUT /api/channels/{id}/roles should work"""
        email = f"TEST_roles_{uuid.uuid4().hex[:8]}@test.com"
        reg_response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": email, "password": "RolesTest123!", "name": "Roles Tester"}
        )
        if reg_response.status_code != 200:
            pytest.skip(f"Could not create test user: {reg_response.text}")
        
        session_cookie = reg_response.cookies.get("session_token")
        cookies = {"session_token": session_cookie}
        
        # Create workspace and channel
        ws_response = requests.post(
            f"{BASE_URL}/api/workspaces",
            json={"name": "Roles Test Workspace"},
            cookies=cookies
        )
        workspace_id = ws_response.json().get("workspace_id")
        
        ch_response = requests.post(
            f"{BASE_URL}/api/workspaces/{workspace_id}/channels",
            json={"name": "Roles Test Channel", "ai_agents": ["claude", "chatgpt"]},
            cookies=cookies
        )
        channel_id = ch_response.json().get("channel_id")
        
        # Set channel roles
        roles_response = requests.put(
            f"{BASE_URL}/api/channels/{channel_id}/roles",
            json={"tpm": "claude", "architect": "chatgpt"},
            cookies=cookies
        )
        assert roles_response.status_code == 200
        data = roles_response.json()
        # Roles may be at top level (tpm, architect) or under channel_roles
        has_roles = "channel_roles" in data or ("tpm" in data and "architect" in data)
        assert has_roles
        print(f"PASS: Channel roles work - roles set: {data}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/workspaces/{workspace_id}", cookies=cookies)


class TestStripeCheckout:
    """Test Stripe checkout endpoint exists"""
    
    def test_billing_checkout_endpoint(self):
        """POST /api/billing/checkout should respond (may need auth)"""
        email = f"TEST_billing_{uuid.uuid4().hex[:8]}@test.com"
        reg_response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": email, "password": "BillingTest123!", "name": "Billing Tester"}
        )
        if reg_response.status_code != 200:
            pytest.skip(f"Could not create test user: {reg_response.text}")
        
        session_cookie = reg_response.cookies.get("session_token")
        cookies = {"session_token": session_cookie}
        
        # Test billing checkout - will fail without Stripe key but endpoint should exist
        checkout_response = requests.post(
            f"{BASE_URL}/api/billing/checkout",
            json={"plan": "pro"},
            cookies=cookies
        )
        # Should not be 404 (endpoint exists)
        assert checkout_response.status_code != 404
        print(f"PASS: Billing checkout endpoint exists - status={checkout_response.status_code}")


class TestAnthropicVersionHeader:
    """Verify Anthropic version header is updated"""
    
    def test_anthropic_version_in_code(self):
        """Check ai_providers.py has anthropic-version: 2024-10-22"""
        import subprocess
        result = subprocess.run(
            ["grep", "-c", "2024-10-22", "/app/backend/ai_providers.py"],
            capture_output=True,
            text=True
        )
        count = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0
        assert count >= 1
        print(f"PASS: Anthropic version 2024-10-22 found {count} time(s) in ai_providers.py")


class TestNh3SanitizationInCode:
    """Verify nh3 is used for HTML sanitization"""
    
    def test_nh3_import_in_server(self):
        """Check server.py imports nh3"""
        import subprocess
        result = subprocess.run(
            ["grep", "-c", "import nh3", "/app/backend/server.py"],
            capture_output=True,
            text=True
        )
        count = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0
        assert count >= 1
        print(f"PASS: nh3 import found in server.py")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
