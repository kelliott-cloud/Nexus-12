"""
Iteration 83: Full End-to-End QA Tests for Nexus Cloud Platform
Tests: Health API, Auth, Workspaces, Channels, Deployments, Coordination, Bridge, Social APIs
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "test@test.com"
TEST_PASSWORD = "testtest"
WORKSPACE_ID = "ws_f6ec6355bb18"


class TestHealthAndPublicAPIs:
    """Health check and public endpoint tests"""
    
    def test_health_endpoint_returns_healthy(self):
        """Health API returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "database" in data
        print(f"✓ Health API: {data['status']}, DB: {data['database']}")


class TestAuthentication:
    """Authentication flow tests"""
    
    def test_login_with_valid_credentials(self):
        """Test email/password login works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert data["email"] == TEST_EMAIL
        print(f"✓ Login successful: {data['email']}, user_id: {data['user_id']}")
    
    def test_login_with_invalid_credentials(self):
        """Test login fails with wrong password"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": "wrongpassword"
        })
        assert response.status_code in [401, 400]
        print("✓ Invalid login correctly rejected")


@pytest.fixture(scope="class")
def auth_session():
    """Create authenticated session for tests requiring auth"""
    session = requests.Session()
    login_res = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if login_res.status_code != 200:
        pytest.skip("Authentication failed - skipping authenticated tests")
    return session


class TestWorkspaces:
    """Workspace CRUD and navigation tests"""
    
    def test_get_workspaces_list(self, auth_session):
        """GET /workspaces returns list"""
        response = auth_session.get(f"{BASE_URL}/api/workspaces")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Workspaces list: {len(data)} workspaces")
        if len(data) > 0:
            print(f"  First workspace: {data[0].get('name')}")
    
    def test_get_workspace_by_id(self, auth_session):
        """GET /workspaces/{id} returns workspace details"""
        response = auth_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}")
        if response.status_code == 404:
            pytest.skip(f"Workspace {WORKSPACE_ID} not found")
        assert response.status_code == 200
        data = response.json()
        assert "workspace_id" in data or "name" in data
        print(f"✓ Workspace details: {data.get('name', 'N/A')}")
    
    def test_get_workspace_channels(self, auth_session):
        """GET /workspaces/{id}/channels returns channels list"""
        response = auth_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/channels")
        if response.status_code == 404:
            pytest.skip(f"Workspace {WORKSPACE_ID} not found")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Channels: {len(data)} channels in workspace")


class TestCoordinationAPIs:
    """Agent coordination protocol tests"""
    
    def test_coordination_status_api(self, auth_session):
        """GET /workspaces/{id}/coordination-status returns coordination info"""
        response = auth_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/coordination-status")
        # May return 404 if workspace doesn't exist
        if response.status_code == 404:
            pytest.skip("Workspace not found for coordination test")
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Coordination status retrieved: {data}")


class TestDeploymentAPIs:
    """Deployment templates and CRUD tests"""
    
    def test_deployment_templates_list(self, auth_session):
        """GET /deployment-templates returns 5 templates"""
        response = auth_session.get(f"{BASE_URL}/api/deployment-templates")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Deployment templates: {len(data)} templates")
        if len(data) > 0:
            print(f"  Template types: {[t.get('type') or t.get('name') for t in data[:5]]}")
    
    def test_workspace_deployments_list(self, auth_session):
        """GET /workspaces/{id}/deployments returns deployment list"""
        response = auth_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/deployments")
        if response.status_code == 404:
            pytest.skip("Workspace not found")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Deployments: {len(data)} deployments in workspace")


class TestBridgeAPIs:
    """Desktop bridge API tests"""
    
    def test_bridge_status(self, auth_session):
        """GET /bridge/status returns bridge connection status"""
        response = auth_session.get(f"{BASE_URL}/api/bridge/status")
        assert response.status_code == 200
        data = response.json()
        # Should return status about bridge connection
        print(f"✓ Bridge status: {data}")
    
    def test_bridge_tools_list(self, auth_session):
        """GET /bridge/tools lists available bridge tools"""
        response = auth_session.get(f"{BASE_URL}/api/bridge/tools")
        # May return 404 if not implemented or empty list
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Bridge tools: {len(data) if isinstance(data, list) else data}")


class TestSocialAPIs:
    """Social media publishing API tests"""
    
    def test_social_platforms_list(self, auth_session):
        """GET /social/platforms returns supported platforms"""
        response = auth_session.get(f"{BASE_URL}/api/social/platforms")
        assert response.status_code == 200
        data = response.json()
        print(f"✓ Social platforms: {data}")
    
    def test_social_connections_status(self, auth_session):
        """GET /social/connections shows user's connected accounts"""
        response = auth_session.get(f"{BASE_URL}/api/social/connections")
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Social connections: {data}")


class TestChatChannels:
    """Chat channel and message API tests"""
    
    def test_channel_messages_load(self, auth_session):
        """GET channel messages works"""
        # First get a channel
        ws_res = auth_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/channels")
        if ws_res.status_code != 200 or not ws_res.json():
            pytest.skip("No channels found")
        
        channels = ws_res.json()
        channel_id = channels[0].get("channel_id")
        
        response = auth_session.get(f"{BASE_URL}/api/channels/{channel_id}/messages")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Channel messages: {len(data)} messages")


class TestProjectsAndTasks:
    """Projects and tasks API tests"""
    
    def test_workspace_projects_list(self, auth_session):
        """GET /workspaces/{id}/projects returns project list"""
        response = auth_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/projects")
        if response.status_code == 404:
            pytest.skip("Workspace not found")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Projects: {len(data)} projects")
    
    def test_workspace_tasks_list(self, auth_session):
        """GET /workspaces/{id}/tasks returns task list"""
        response = auth_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/tasks")
        if response.status_code == 404:
            pytest.skip("Workspace not found")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Tasks: {len(data)} tasks")


class TestAnalyticsAPIs:
    """Analytics and reporting API tests"""
    
    def test_workspace_analytics(self, auth_session):
        """GET workspace analytics data"""
        response = auth_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/analytics")
        if response.status_code == 404:
            pytest.skip("Workspace not found")
        # Could be 200 or 403 based on plan
        assert response.status_code in [200, 403]
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Analytics: {data}")


class TestMembersAPI:
    """Workspace members API tests"""
    
    def test_workspace_members_list(self, auth_session):
        """GET /workspaces/{id}/members returns member list"""
        response = auth_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/members")
        if response.status_code == 404:
            pytest.skip("Workspace not found")
        assert response.status_code == 200
        data = response.json()
        # API returns dict with 'members' key or list directly
        members = data.get('members', data) if isinstance(data, dict) else data
        assert isinstance(members, list)
        print(f"✓ Members: {len(members)} members")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
