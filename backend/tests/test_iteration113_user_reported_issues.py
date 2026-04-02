"""
Iteration 113 - User Reported Issues Testing
Tests for: 1) Workspaces loading, 2) Admin panel visibility, 3) Billing endpoint fields

User reports:
- Workspaces don't load
- Admin panel is gone from the UI

Root cause identified: OnboardingTour component overlay (z-[250]) blocks all clicks
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8080')

# Test credentials
TEST_EMAIL = os.environ.get("TEST_ADMIN_EMAIL", "admin@test.local")
TEST_PASSWORD = "test"


class TestAuthentication:
    """Test login flow and session management"""
    
    @pytest.fixture(scope="class")
    def session_token(self):
        """Login and get session token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "session_token" in data, "No session_token in response"
        assert "user_id" in data, "No user_id in response"
        return data["session_token"]
    
    def test_login_returns_user_data(self):
        """Test login returns complete user data"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert data.get("user_id"), "Missing user_id"
        assert data.get("email") == TEST_EMAIL, "Email mismatch"
        assert data.get("name"), "Missing name"
        assert data.get("platform_role"), "Missing platform_role"
        assert data.get("session_token"), "Missing session_token"
        
        # Verify super_admin role for test user
        assert data.get("platform_role") == "super_admin", f"Expected super_admin, got {data.get('platform_role')}"
    
    def test_auth_me_returns_user(self, session_token):
        """Test /auth/me returns authenticated user"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {session_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("user_id"), "Missing user_id"
        assert data.get("email") == TEST_EMAIL, "Email mismatch"
        assert data.get("platform_role") == "super_admin", "Role mismatch"


class TestWorkspaces:
    """Test workspace loading - addresses user report 'workspaces don't load'"""
    
    @pytest.fixture(scope="class")
    def session_token(self):
        """Login and get session token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        return response.json()["session_token"]
    
    def test_workspaces_list_loads(self, session_token):
        """Test GET /workspaces returns workspace list"""
        response = requests.get(
            f"{BASE_URL}/api/workspaces",
            headers={"Authorization": f"Bearer {session_token}"}
        )
        assert response.status_code == 200, f"Workspaces failed: {response.text}"
        data = response.json()
        
        # Should return a list
        assert isinstance(data, list), "Expected list of workspaces"
        
        # Verify workspace structure if any exist
        if len(data) > 0:
            ws = data[0]
            assert "workspace_id" in ws, "Missing workspace_id"
            assert "name" in ws, "Missing name"
    
    def test_workspaces_count(self, session_token):
        """Test workspaces return expected count"""
        response = requests.get(
            f"{BASE_URL}/api/workspaces",
            headers={"Authorization": f"Bearer {session_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should have workspaces for super_admin
        assert len(data) > 0, "No workspaces returned for super_admin user"
        print(f"✓ Found {len(data)} workspaces")
    
    def test_workspace_detail_loads(self, session_token):
        """Test individual workspace loads correctly"""
        # First get list
        list_response = requests.get(
            f"{BASE_URL}/api/workspaces",
            headers={"Authorization": f"Bearer {session_token}"}
        )
        assert list_response.status_code == 200
        workspaces = list_response.json()
        
        if len(workspaces) > 0:
            ws_id = workspaces[0]["workspace_id"]
            
            # Get workspace detail
            detail_response = requests.get(
                f"{BASE_URL}/api/workspaces/{ws_id}",
                headers={"Authorization": f"Bearer {session_token}"}
            )
            assert detail_response.status_code == 200, f"Workspace detail failed: {detail_response.text}"
            
            ws = detail_response.json()
            assert ws.get("workspace_id") == ws_id, "Workspace ID mismatch"
            assert ws.get("name"), "Missing workspace name"
    
    def test_workspace_channels_load(self, session_token):
        """Test workspace channels load correctly"""
        # First get list
        list_response = requests.get(
            f"{BASE_URL}/api/workspaces",
            headers={"Authorization": f"Bearer {session_token}"}
        )
        assert list_response.status_code == 200
        workspaces = list_response.json()
        
        if len(workspaces) > 0:
            ws_id = workspaces[0]["workspace_id"]
            
            # Get channels
            channels_response = requests.get(
                f"{BASE_URL}/api/workspaces/{ws_id}/channels",
                headers={"Authorization": f"Bearer {session_token}"}
            )
            assert channels_response.status_code == 200, f"Channels failed: {channels_response.text}"
            
            channels = channels_response.json()
            assert isinstance(channels, list), "Expected list of channels"


class TestAdminPanel:
    """Test admin panel access - addresses user report 'admin panel is gone'"""
    
    @pytest.fixture(scope="class")
    def session_token(self):
        """Login and get session token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        return response.json()["session_token"]
    
    def test_admin_check_for_super_admin(self, session_token):
        """Test /admin/check returns correct permissions for super_admin"""
        response = requests.get(
            f"{BASE_URL}/api/admin/check",
            headers={"Authorization": f"Bearer {session_token}"}
        )
        assert response.status_code == 200, f"Admin check failed: {response.text}"
        data = response.json()
        
        # Verify super_admin has admin access
        assert data.get("is_super_admin") == True, "Expected is_super_admin=True"
        assert data.get("is_staff") == True, "Expected is_staff=True"
        assert data.get("platform_role") == "super_admin", "Expected platform_role=super_admin"
    
    def test_admin_stats_accessible(self, session_token):
        """Test /admin/stats returns platform statistics"""
        response = requests.get(
            f"{BASE_URL}/api/admin/stats",
            headers={"Authorization": f"Bearer {session_token}"}
        )
        assert response.status_code == 200, f"Admin stats failed: {response.text}"
        data = response.json()
        
        # Verify stats structure
        assert "users" in data, "Missing users stats"
        assert "workspaces" in data, "Missing workspaces stats"
        assert "messages" in data, "Missing messages stats"
        
        # Verify counts
        assert data["users"].get("total", 0) > 0, "No users in stats"
        assert data["workspaces"].get("total", 0) > 0, "No workspaces in stats"
        
        print(f"✓ Admin stats: {data['users']['total']} users, {data['workspaces']['total']} workspaces")
    
    def test_admin_users_list(self, session_token):
        """Test /admin/users returns user list"""
        response = requests.get(
            f"{BASE_URL}/api/admin/users?limit=10",
            headers={"Authorization": f"Bearer {session_token}"}
        )
        assert response.status_code == 200, f"Admin users failed: {response.text}"
        data = response.json()
        
        assert "users" in data, "Missing users in response"
        assert isinstance(data["users"], list), "Expected list of users"
    
    def test_admin_bugs_list(self, session_token):
        """Test /admin/bugs returns bug reports"""
        response = requests.get(
            f"{BASE_URL}/api/admin/bugs",
            headers={"Authorization": f"Bearer {session_token}"}
        )
        assert response.status_code == 200, f"Admin bugs failed: {response.text}"
        data = response.json()
        
        assert "bugs" in data, "Missing bugs in response"
        assert "stats" in data, "Missing stats in response"


class TestBillingEndpoint:
    """Test billing endpoint field names"""
    
    @pytest.fixture(scope="class")
    def session_token(self):
        """Login and get session token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        return response.json()["session_token"]
    
    def test_billing_subscription_fields(self, session_token):
        """Test /billing/subscription returns correct field names"""
        response = requests.get(
            f"{BASE_URL}/api/billing/subscription",
            headers={"Authorization": f"Bearer {session_token}"}
        )
        assert response.status_code == 200, f"Billing subscription failed: {response.text}"
        data = response.json()
        
        # Verify required fields
        assert "plan_id" in data, "Missing plan_id"
        assert "ai_collaboration_used" in data, "Missing ai_collaboration_used"
        assert "ai_collaboration_limit" in data, "Missing ai_collaboration_limit"
        
        print(f"✓ Billing: plan={data['plan_id']}, used={data['ai_collaboration_used']}, limit={data['ai_collaboration_limit']}")
    
    def test_billing_plans_list(self, session_token):
        """Test /billing/plans returns available plans"""
        response = requests.get(
            f"{BASE_URL}/api/billing/plans",
            headers={"Authorization": f"Bearer {session_token}"}
        )
        assert response.status_code == 200, f"Billing plans failed: {response.text}"
        data = response.json()
        
        assert "plans" in data, "Missing plans in response"
        plans = data["plans"]
        
        # Verify expected plans exist
        assert "free" in plans, "Missing free plan"
        assert "pro" in plans, "Missing pro plan"
        assert "enterprise" in plans, "Missing enterprise plan"


class TestGoogleOAuth:
    """Test Google OAuth configuration"""
    
    def test_google_login_endpoint(self):
        """Test /auth/google/login returns OAuth config"""
        response = requests.get(f"{BASE_URL}/api/auth/google/login")
        assert response.status_code == 200, f"Google login failed: {response.text}"
        data = response.json()
        
        # Should return either a URL, use_emergent_bridge flag, or configured==False
        has_url = "url" in data and data["url"]
        has_bridge = data.get("use_emergent_bridge") == True
        not_configured = data.get("configured") == False
        
        assert has_url or has_bridge or not_configured, "Expected url, use_emergent_bridge, or configured==False"
        
        if has_url:
            print(f"✓ Google OAuth URL: {data['url'][:50]}...")
        elif has_bridge:
            print("✓ Google OAuth uses Emergent bridge")
        else:
            print("✓ Google OAuth not configured (no client ID set)")


class TestUnauthorizedAccess:
    """Test 401 handling for unauthenticated requests"""
    
    def test_workspaces_requires_auth(self):
        """Test /workspaces returns 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/workspaces")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_admin_requires_auth(self):
        """Test /admin/check returns 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/admin/check")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_billing_requires_auth(self):
        """Test /billing/subscription returns 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/billing/subscription")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
