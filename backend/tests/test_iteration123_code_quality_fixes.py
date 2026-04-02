"""
Iteration 123 - Code Quality Fixes Testing
Tests for:
1. Backend health check
2. Login with test credentials
3. GET /api/user/sessions (previously crashed with undefined get_current_user)
4. DELETE /api/user/sessions/{session_id} (previously undefined get_current_user)
5. GET /api/support/tickets with org_id param
6. GET /api/platform/capabilities returns features
7. POST /api/workspaces/{ws_id}/wiki-pages creates a wiki page (fixed ws_id bug)
8. Backend starts without import errors (no F821 undefined names)
9. No __import__ calls remain in production code
10. routes/__init__.py uses explicit imports not wildcards
"""
import pytest
import requests
import os
import subprocess

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "kelliott@urtech.org"
TEST_PASSWORD = "test"


class TestHealthCheck:
    """Verify backend is running without import errors"""
    
    def test_health_endpoint_returns_200(self):
        """Backend health check - confirms no import errors crashed the server"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data.get("status") == "healthy"
        assert data.get("database") == "connected"
        print("PASSED: Health endpoint returns 200 with healthy status")


class TestAuthentication:
    """Test login and session management"""
    
    def test_login_with_super_admin(self):
        """Login with kelliott@urtech.org / test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        # Could be MFA required or direct login
        if data.get("mfa_required"):
            assert "challenge_token" in data
            print("PASSED: Login returns MFA challenge (MFA enabled)")
        else:
            assert "user_id" in data or "session_token" in data
            print("PASSED: Login successful with session token")


class TestSessionManagement:
    """Test session endpoints - previously crashed with undefined get_current_user"""
    
    @pytest.fixture
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Login failed: {response.text}")
        data = response.json()
        if data.get("mfa_required"):
            pytest.skip("MFA required - skipping session tests")
        if "session_token" in data:
            session.headers.update({"Authorization": f"Bearer {data['session_token']}"})
        return session
    
    def test_list_sessions_returns_list(self, auth_session):
        """GET /api/user/sessions - previously crashed with undefined get_current_user"""
        response = auth_session.get(f"{BASE_URL}/api/user/sessions")
        assert response.status_code == 200, f"List sessions failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"PASSED: GET /api/user/sessions returns list with {len(data)} sessions")
    
    def test_delete_session_endpoint_exists(self, auth_session):
        """DELETE /api/user/sessions/{session_id} - previously undefined get_current_user"""
        # Try to delete a non-existent session - should return 200 (no-op) or 404
        response = auth_session.delete(f"{BASE_URL}/api/user/sessions/nonexistent_session_123")
        # Should not crash with 500 - that would indicate undefined variable
        assert response.status_code in [200, 204, 404], f"Delete session crashed: {response.status_code} - {response.text}"
        print(f"PASSED: DELETE /api/user/sessions/{{session_id}} returns {response.status_code} (no crash)")


class TestSupportDesk:
    """Test support desk with org_id parameter"""
    
    @pytest.fixture
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Login failed: {response.text}")
        data = response.json()
        if data.get("mfa_required"):
            pytest.skip("MFA required - skipping support desk tests")
        if "session_token" in data:
            session.headers.update({"Authorization": f"Bearer {data['session_token']}"})
        return session
    
    def test_list_tickets_with_org_id(self, auth_session):
        """GET /api/support/tickets with org_id param works"""
        response = auth_session.get(f"{BASE_URL}/api/support/tickets", params={"org_id": "test_org"})
        assert response.status_code == 200, f"Support tickets failed: {response.text}"
        data = response.json()
        assert "tickets" in data or isinstance(data, list)
        print("PASSED: GET /api/support/tickets with org_id returns 200")


class TestPlatformCapabilities:
    """Test platform capabilities endpoint"""
    
    @pytest.fixture
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Login failed: {response.text}")
        data = response.json()
        if data.get("mfa_required"):
            pytest.skip("MFA required - skipping platform tests")
        if "session_token" in data:
            session.headers.update({"Authorization": f"Bearer {data['session_token']}"})
        return session
    
    def test_platform_capabilities_returns_features(self, auth_session):
        """GET /api/platform/capabilities returns features"""
        response = auth_session.get(f"{BASE_URL}/api/platform/capabilities")
        assert response.status_code == 200, f"Platform capabilities failed: {response.text}"
        data = response.json()
        # Should return some capabilities/features
        assert isinstance(data, dict) or isinstance(data, list)
        print(f"PASSED: GET /api/platform/capabilities returns {type(data).__name__}")


class TestWikiPageCreation:
    """Test wiki page creation - fixed ws_id -> workspace_id bug"""
    
    @pytest.fixture
    def auth_session(self):
        """Get authenticated session with CSRF handling"""
        session = requests.Session()
        
        # First make a GET request to get CSRF cookie
        session.get(f"{BASE_URL}/api/health")
        
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Login failed: {response.text}")
        data = response.json()
        if data.get("mfa_required"):
            pytest.skip("MFA required - skipping wiki tests")
        if "session_token" in data:
            session.headers.update({
                "Authorization": f"Bearer {data['session_token']}",
            })
            # Get CSRF token from cookies and add to headers
            csrf_token = session.cookies.get("csrf_token", "")
            if csrf_token:
                session.headers.update({"X-CSRF-Token": csrf_token})
        return session, data
    
    def test_create_wiki_page(self, auth_session):
        """POST /api/workspaces/{ws_id}/wiki creates a wiki page (fixed ws_id bug)"""
        session, user_data = auth_session
        
        # Get a workspace to test with
        ws_response = session.get(f"{BASE_URL}/api/workspaces")
        if ws_response.status_code != 200:
            pytest.skip(f"Could not get workspaces: {ws_response.text}")
        
        workspaces = ws_response.json()
        if not workspaces:
            pytest.skip("No workspaces available for testing")
        
        workspace_id = workspaces[0].get("workspace_id") or workspaces[0].get("id")
        
        # Update CSRF token from latest response
        csrf_token = session.cookies.get("csrf_token", "")
        if csrf_token:
            session.headers.update({"X-CSRF-Token": csrf_token})
        
        # Create a wiki page
        response = session.post(f"{BASE_URL}/api/workspaces/{workspace_id}/wiki", json={
            "title": "TEST_Wiki_Page_Iteration123",
            "content": "Test content for code quality fixes verification",
            "icon": ""
        })
        
        # Should not crash with 500 due to undefined ws_id
        assert response.status_code in [200, 201], f"Wiki page creation failed: {response.status_code} - {response.text}"
        data = response.json()
        assert "page_id" in data, f"Response missing page_id: {data}"
        assert data.get("workspace_id") == workspace_id
        print(f"PASSED: Wiki page created with page_id={data['page_id']}")
        
        # Cleanup - delete the test page
        page_id = data["page_id"]
        session.delete(f"{BASE_URL}/api/workspaces/{workspace_id}/wiki/{page_id}")


class TestCodeQualityFixes:
    """Verify code quality fixes are in place"""
    
    def test_no_import_calls_in_routes(self):
        """No __import__ calls remain in production code"""
        result = subprocess.run(
            ["grep", "-r", "__import__", "/app/backend/routes/", "--include=*.py"],
            capture_output=True, text=True
        )
        # Should find nothing (exit code 1 means no matches)
        assert result.returncode == 1 or result.stdout.strip() == "", \
            f"Found __import__ calls: {result.stdout}"
        print("PASSED: No __import__ calls in routes/")
    
    def test_no_wildcard_imports_in_routes_init(self):
        """routes/__init__.py uses explicit imports not wildcards"""
        with open("/app/backend/routes/__init__.py", "r") as f:
            content = f.read()
        
        # Check for wildcard imports (excluding comments)
        lines = [l for l in content.split("\n") if not l.strip().startswith("#")]
        for line in lines:
            assert "import *" not in line, f"Found wildcard import: {line}"
        
        # Verify explicit imports exist
        assert "from routes.routes_auth_email import register_auth_email_routes" in content
        assert "from routes.routes_wiki import register_wiki_routes" in content
        print("PASSED: routes/__init__.py uses explicit imports")
    
    def test_now_iso_imports_in_route_files(self):
        """Verify now_iso is imported in files that use it"""
        files_to_check = [
            "/app/backend/routes/routes_billing_advanced.py",
            "/app/backend/routes/routes_code_dev.py",
            "/app/backend/routes/routes_content_gen.py",
            "/app/backend/routes/routes_deployments.py",
            "/app/backend/routes/routes_directive_engine.py",
            "/app/backend/routes/routes_drive.py",
            "/app/backend/routes/routes_plm_advanced.py",
            "/app/backend/routes/routes_strategic_v2.py",
            "/app/backend/routes/routes_cost_intelligence.py",
            "/app/backend/routes/routes_keystone.py",
            "/app/backend/routes/routes_nx_features.py",
            "/app/backend/routes/routes_workspace_templates.py",
        ]
        
        for filepath in files_to_check:
            try:
                with open(filepath, "r") as f:
                    content = f.read()
                # Check if now_iso is used and imported
                if "now_iso" in content:
                    assert "from nexus_utils import" in content and "now_iso" in content, \
                        f"{filepath} uses now_iso but doesn't import it"
            except FileNotFoundError:
                pass  # File may not exist in this environment
        
        print("PASSED: now_iso imports verified in route files")
    
    def test_session_helper_in_auth_email(self):
        """Verify _get_current_user_for_sessions helper exists in routes_auth_email.py"""
        with open("/app/backend/routes/routes_auth_email.py", "r") as f:
            content = f.read()
        
        assert "_get_current_user_for_sessions" in content, \
            "Missing _get_current_user_for_sessions helper"
        assert "async def _get_current_user_for_sessions" in content, \
            "_get_current_user_for_sessions should be async"
        print("PASSED: _get_current_user_for_sessions helper exists")
    
    def test_wiki_uses_workspace_id_not_ws_id(self):
        """Verify routes_wiki.py uses workspace_id parameter correctly"""
        with open("/app/backend/routes/routes_wiki.py", "r") as f:
            content = f.read()
        
        # Check that workspace_id is used in route definitions
        assert "workspace_id: str" in content, "Missing workspace_id parameter"
        # The bug was using undefined ws_id - check it's not there
        # (ws_id might appear in comments or other contexts, so check function signatures)
        assert 'def create_wiki_page(workspace_id: str' in content or \
               'workspace_id: str, data: WikiPageCreate' in content, \
               "create_wiki_page should use workspace_id parameter"
        print("PASSED: routes_wiki.py uses workspace_id correctly")


class TestStaticImportFixes:
    """Verify __import__ was replaced with static imports"""
    
    def test_routes_scim_uses_static_json_import(self):
        """routes_scim.py uses import json instead of __import__('json')"""
        try:
            with open("/app/backend/routes/routes_scim.py", "r") as f:
                content = f.read()
            assert "__import__('json')" not in content, "Still using __import__('json')"
            assert "import json" in content or "from json import" in content, \
                "Missing static json import"
            print("PASSED: routes_scim.py uses static json import")
        except FileNotFoundError:
            pytest.skip("routes_scim.py not found")
    
    def test_routes_nexus_browser_uses_static_timedelta(self):
        """routes_nexus_browser.py uses static timedelta import"""
        try:
            with open("/app/backend/routes/routes_nexus_browser.py", "r") as f:
                content = f.read()
            assert "__import__('datetime')" not in content, "Still using __import__('datetime')"
            print("PASSED: routes_nexus_browser.py uses static imports")
        except FileNotFoundError:
            pytest.skip("routes_nexus_browser.py not found")
    
    def test_routes_mfa_uses_static_timedelta(self):
        """routes_mfa.py uses static timedelta import"""
        try:
            with open("/app/backend/routes/routes_mfa.py", "r") as f:
                content = f.read()
            assert "__import__('datetime')" not in content, "Still using __import__('datetime')"
            print("PASSED: routes_mfa.py uses static imports")
        except FileNotFoundError:
            pytest.skip("routes_mfa.py not found")
    
    def test_routes_agent_training_uses_static_timedelta(self):
        """routes_agent_training.py uses static timedelta import"""
        try:
            with open("/app/backend/routes/routes_agent_training.py", "r") as f:
                content = f.read()
            assert "__import__('datetime')" not in content, "Still using __import__('datetime')"
            print("PASSED: routes_agent_training.py uses static imports")
        except FileNotFoundError:
            pytest.skip("routes_agent_training.py not found")


class TestIdentityComparisonFixes:
    """Verify is True/is False replaced with == True/== False"""
    
    def test_routes_ai_keys_identity_comparisons(self):
        """routes_ai_keys.py uses == True/== False instead of is True/is False"""
        try:
            with open("/app/backend/routes/routes_ai_keys.py", "r") as f:
                content = f.read()
            # Check that problematic patterns are fixed
            # Note: "is True" might appear in comments, so we check for common patterns
            lines = [l for l in content.split("\n") if not l.strip().startswith("#")]
            code_content = "\n".join(lines)
            
            # These patterns should not exist in code (outside comments)
            problematic_patterns = [
                " is True:",
                " is False:",
                "== is True",
                "== is False",
            ]
            for pattern in problematic_patterns:
                if pattern in code_content:
                    # Double check it's not in a string
                    assert f'"{pattern}"' in code_content or f"'{pattern}'" in code_content, \
                        f"Found problematic pattern: {pattern}"
            
            print("PASSED: routes_ai_keys.py identity comparisons fixed")
        except FileNotFoundError:
            pytest.skip("routes_ai_keys.py not found")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
