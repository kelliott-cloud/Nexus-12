"""
Iteration 118 - P0 Backlog Items Testing
Tests for:
- Workspace tools endpoint GET /api/workspaces/{workspace_id}/tools
- Admin startup diagnostics endpoint GET /api/admin/startup-diagnostics
- Workspace Nexus AI alerts endpoint
- Budget alert notifications via GET /api/notifications
- Cloud storage providers endpoint (after budget tracking changes)
- Social platforms endpoint (after budget tracking changes)
"""
import os
import pytest
import requests
from datetime import datetime

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
TEST_EMAIL = os.environ.get("TEST_ADMIN_EMAIL", "admin@test.local")
TEST_PASSWORD = "test"


class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def session(self):
        return requests.Session()
    
    @pytest.fixture(scope="class")
    def auth_token(self, session):
        """Login and get auth token"""
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        token = data.get("session_token") or data.get("token")
        assert token, "No token in login response"
        return token
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}"}
    
    @pytest.fixture(scope="class")
    def user_data(self, session, auth_headers):
        """Get current user data"""
        response = session.get(f"{BASE_URL}/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        return response.json()
    
    @pytest.fixture(scope="class")
    def workspace_id(self, session, auth_headers):
        """Get first workspace ID"""
        response = session.get(f"{BASE_URL}/api/workspaces", headers=auth_headers)
        assert response.status_code == 200
        workspaces = response.json()
        assert len(workspaces) > 0, "No workspaces found"
        return workspaces[0]["workspace_id"]


class TestWorkspaceToolsEndpoint(TestAuth):
    """Test GET /api/workspaces/{workspace_id}/tools endpoint"""
    
    def test_workspace_tools_returns_200(self, session, auth_headers, workspace_id):
        """Workspace tools endpoint should return 200 with tools list"""
        response = session.get(
            f"{BASE_URL}/api/workspaces/{workspace_id}/tools",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Should have a tools list
        assert "tools" in data, "Response should contain 'tools' key"
        assert isinstance(data["tools"], list), "tools should be a list"
        print(f"Workspace tools endpoint returned {len(data['tools'])} tools")
    
    def test_workspace_tools_without_auth(self, session, workspace_id):
        """Workspace tools endpoint behavior without authentication"""
        response = session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/tools")
        # Note: This endpoint may return 200 with empty tools or 401 depending on implementation
        # The key test is that it doesn't return 404 (endpoint exists)
        assert response.status_code in [200, 401], f"Expected 200 or 401, got {response.status_code}"
        print(f"Workspace tools without auth: {response.status_code}")


class TestAdminStartupDiagnostics(TestAuth):
    """Test GET /api/admin/startup-diagnostics endpoint"""
    
    def test_startup_diagnostics_returns_200(self, session, auth_headers):
        """Admin startup diagnostics should return 200 for staff users"""
        response = session.get(
            f"{BASE_URL}/api/admin/startup-diagnostics",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify expected fields
        assert "timestamp" in data, "Should have timestamp"
        assert "database" in data, "Should have database status"
        assert "routes" in data, "Should have routes info"
        assert "startup_probe" in data, "Should have startup_probe"
        
        # Verify database is ok
        assert data["database"]["status"] == "ok", f"Database status: {data['database']}"
        
        # Verify workspace_tools_endpoint is present
        assert "workspace_tools_endpoint" in data["routes"], "Should report workspace_tools_endpoint"
        assert data["routes"]["workspace_tools_endpoint"] == True, "workspace_tools_endpoint should be True"
        
        # Report duplicate routes (informational - may exist for valid reasons)
        duplicates = data["routes"].get("duplicates", [])
        if duplicates:
            print(f"Note: Found {len(duplicates)} duplicate routes: {duplicates}")
        
        print(f"Startup diagnostics: DB={data['database']['status']}, Ready={data['startup_probe'].get('ready')}")
    
    def test_startup_diagnostics_without_auth(self, session):
        """Admin startup diagnostics behavior without authentication"""
        response = session.get(f"{BASE_URL}/api/admin/startup-diagnostics")
        # Note: May return 200 for public health check or 401/403 for protected
        assert response.status_code in [200, 401, 403], f"Expected 200/401/403, got {response.status_code}"
        print(f"Startup diagnostics without auth: {response.status_code}")


class TestNexusAIBudgetAlerts(TestAuth):
    """Test Nexus AI budget alerts endpoints"""
    
    def test_workspace_nexus_ai_alerts_returns_200(self, session, auth_headers, workspace_id):
        """Workspace Nexus AI alerts endpoint should return 200"""
        response = session.get(
            f"{BASE_URL}/api/workspaces/{workspace_id}/nexus-ai/alerts",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "alerts" in data, "Response should contain 'alerts' key"
        assert isinstance(data["alerts"], list), "alerts should be a list"
        print(f"Workspace Nexus AI alerts: {len(data['alerts'])} alerts found")
    
    def test_workspace_nexus_ai_budgets_returns_200(self, session, auth_headers, workspace_id):
        """Workspace Nexus AI budgets endpoint should return 200"""
        response = session.get(
            f"{BASE_URL}/api/workspaces/{workspace_id}/nexus-ai/budgets",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "scope_type" in data, "Response should contain 'scope_type'"
        assert data["scope_type"] == "workspace", "scope_type should be 'workspace'"
        assert "budgets" in data, "Response should contain 'budgets'"
        print(f"Workspace Nexus AI budgets: {len(data.get('budgets', {}))} providers configured")
    
    def test_workspace_nexus_ai_dashboard_returns_200(self, session, auth_headers, workspace_id):
        """Workspace Nexus AI dashboard endpoint should return 200"""
        response = session.get(
            f"{BASE_URL}/api/workspaces/{workspace_id}/nexus-ai/dashboard",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "scope_type" in data, "Response should contain 'scope_type'"
        assert "month_key" in data, "Response should contain 'month_key'"
        assert "total_cost_usd" in data, "Response should contain 'total_cost_usd'"
        print(f"Workspace Nexus AI dashboard: month={data.get('month_key')}, cost=${data.get('total_cost_usd', 0):.4f}")


class TestNotifications(TestAuth):
    """Test notifications endpoint for budget alerts"""
    
    def test_notifications_returns_200(self, session, auth_headers):
        """Notifications endpoint should return 200"""
        response = session.get(
            f"{BASE_URL}/api/notifications",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Response can be a list or dict with notifications key
        if isinstance(data, dict):
            notifications = data.get("notifications", [])
        else:
            notifications = data
        
        assert isinstance(notifications, list), "notifications should be a list"
        
        # Check for budget_alert notifications if any exist
        budget_alerts = [n for n in notifications if n.get("type") == "budget_alert"]
        print(f"Notifications: {len(notifications)} total, {len(budget_alerts)} budget alerts")


class TestCloudStorageProviders(TestAuth):
    """Test cloud storage providers endpoint after budget tracking changes"""
    
    def test_cloud_storage_providers_returns_200(self, session, auth_headers):
        """Cloud storage providers endpoint should return 200"""
        response = session.get(
            f"{BASE_URL}/api/cloud-storage/providers",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "providers" in data, "Response should contain 'providers'"
        assert isinstance(data["providers"], list), "providers should be a list"
        
        # Verify expected providers are present
        provider_names = [p["provider"] for p in data["providers"]]
        expected_providers = ["google_drive", "onedrive", "dropbox", "box"]
        for expected in expected_providers:
            assert expected in provider_names, f"Expected provider '{expected}' not found"
        
        print(f"Cloud storage providers: {provider_names}")


class TestSocialPlatforms(TestAuth):
    """Test social platforms endpoint after budget tracking changes"""
    
    def test_social_platforms_returns_200(self, session, auth_headers):
        """Social platforms endpoint should return 200"""
        response = session.get(
            f"{BASE_URL}/api/social/platforms",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "platforms" in data, "Response should contain 'platforms'"
        assert isinstance(data["platforms"], list), "platforms should be a list"
        
        # Verify expected platforms are present
        platform_names = [p["platform"] for p in data["platforms"]]
        expected_platforms = ["youtube", "tiktok", "instagram"]
        for expected in expected_platforms:
            assert expected in platform_names, f"Expected platform '{expected}' not found"
        
        print(f"Social platforms: {platform_names}")


class TestAIModelsEndpoint(TestAuth):
    """Test AI models endpoint - should not return 401 when authenticated"""
    
    def test_ai_models_returns_200_when_authenticated(self, session, auth_headers):
        """AI models endpoint should return 200 when authenticated"""
        response = session.get(
            f"{BASE_URL}/api/ai-models",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Should have models data
        assert "models" in data or isinstance(data, dict), "Response should contain models data"
        print(f"AI models endpoint returned successfully")
    
    def test_ai_models_without_auth(self, session):
        """AI models endpoint behavior without authentication"""
        response = session.get(f"{BASE_URL}/api/ai-models")
        # Note: This endpoint may be public (200) or protected (401)
        # The key is that it doesn't error (500) and returns valid data
        assert response.status_code in [200, 401], f"Expected 200 or 401, got {response.status_code}"
        print(f"AI models without auth: {response.status_code}")


class TestAdminDashboardDiagnosticsTab(TestAuth):
    """Test admin dashboard diagnostics tab functionality"""
    
    def test_admin_check_returns_200(self, session, auth_headers):
        """Admin check endpoint should return 200 for super admin"""
        response = session.get(
            f"{BASE_URL}/api/admin/check",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "is_super_admin" in data, "Response should contain 'is_super_admin'"
        assert "is_staff" in data, "Response should contain 'is_staff'"
        print(f"Admin check: is_super_admin={data.get('is_super_admin')}, is_staff={data.get('is_staff')}")
    
    def test_admin_stats_returns_200(self, session, auth_headers):
        """Admin stats endpoint should return 200 for staff"""
        response = session.get(
            f"{BASE_URL}/api/admin/stats",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "users" in data, "Response should contain 'users'"
        assert "workspaces" in data, "Response should contain 'workspaces'"
        print(f"Admin stats: {data.get('users', {}).get('total', 0)} users, {data.get('workspaces', {}).get('total', 0)} workspaces")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
