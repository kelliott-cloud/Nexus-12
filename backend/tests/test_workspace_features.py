"""
Comprehensive tests for Workspace features - CRUD operations, channels, and auth
Testing: User auth (register/login), Workspace CRUD, Channel CRUD
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "test@nexus.com"
TEST_PASSWORD = "Test1234!"
UNIQUE_ID = uuid.uuid4().hex[:8]


class TestHealthCheck:
    """Basic health check to ensure API is running"""
    
    def test_health_endpoint(self):
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        print("✓ Health check passed")


class TestAuthEndpoints:
    """Authentication endpoint tests - register and login"""
    
    def test_register_new_user(self):
        """Test user registration creates new account"""
        unique_email = f"TEST_user_{UNIQUE_ID}@nexus.com"
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "TestPass123!",
            "name": "Test User"
        })
        # May be 400 if user exists, 200 if successful
        assert response.status_code in [200, 400]
        if response.status_code == 200:
            data = response.json()
            assert "user_id" in data
            assert data["email"] == unique_email
            print(f"✓ User registration successful: {unique_email}")
        else:
            print(f"✓ User registration returned 400 (email may exist)")
    
    def test_login_with_valid_credentials(self):
        """Test login with known test user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "user_id" in data
        assert data["email"] == TEST_EMAIL
        print(f"✓ Login successful for {TEST_EMAIL}")
    
    def test_login_with_invalid_credentials(self):
        """Test login with wrong password"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": "WrongPassword123!"
        })
        assert response.status_code == 401
        print("✓ Invalid credentials correctly rejected")
    
    def test_auth_me_without_session(self):
        """Test /auth/me without authentication"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401
        print("✓ /auth/me correctly requires authentication")


class TestWorkspaceEndpoints:
    """Workspace CRUD endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup_session(self):
        """Login and get session for authenticated requests"""
        self.session = requests.Session()
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Setup failed - login error: {response.text}"
        self.user = response.json()
        yield
        # Cleanup: Delete any test workspaces created
        try:
            workspaces = self.session.get(f"{BASE_URL}/api/workspaces?include_disabled=true").json()
            for ws in workspaces:
                if ws["name"].startswith("TEST_"):
                    self.session.delete(f"{BASE_URL}/api/workspaces/{ws['workspace_id']}")
        except:
            pass
    
    def test_get_workspaces_list(self):
        """Test GET /api/workspaces returns workspace list"""
        response = self.session.get(f"{BASE_URL}/api/workspaces")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/workspaces returned {len(data)} workspaces")
        # Check workspace structure if any exist
        if len(data) > 0:
            ws = data[0]
            assert "workspace_id" in ws
            assert "name" in ws
            assert "owner_id" in ws
            print(f"  First workspace: {ws['name']} ({ws['workspace_id']})")
    
    def test_get_workspaces_with_disabled(self):
        """Test include_disabled parameter"""
        response = self.session.get(f"{BASE_URL}/api/workspaces?include_disabled=true")
        assert response.status_code == 200
        print("✓ GET /api/workspaces?include_disabled=true works")
    
    def test_create_workspace(self):
        """Test POST /api/workspaces creates new workspace"""
        ws_name = f"TEST_Workspace_{UNIQUE_ID}"
        response = self.session.post(f"{BASE_URL}/api/workspaces", json={
            "name": ws_name,
            "description": "Test workspace created by pytest"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == ws_name
        assert "workspace_id" in data
        assert data["owner_id"] == self.user["user_id"]
        print(f"✓ POST /api/workspaces created: {data['workspace_id']}")
        
        # Verify it appears in list
        list_response = self.session.get(f"{BASE_URL}/api/workspaces")
        workspaces = list_response.json()
        ws_ids = [w["workspace_id"] for w in workspaces]
        assert data["workspace_id"] in ws_ids
        print("  Workspace appears in list after creation")
    
    def test_get_single_workspace(self):
        """Test GET /api/workspaces/{id} returns workspace details"""
        # First create a workspace
        ws_name = f"TEST_Single_{UNIQUE_ID}"
        create_res = self.session.post(f"{BASE_URL}/api/workspaces", json={
            "name": ws_name,
            "description": "Test single get"
        })
        assert create_res.status_code == 200
        ws_id = create_res.json()["workspace_id"]
        
        # Then get it
        response = self.session.get(f"{BASE_URL}/api/workspaces/{ws_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["workspace_id"] == ws_id
        assert data["name"] == ws_name
        print(f"✓ GET /api/workspaces/{ws_id} returned correct data")
    
    def test_get_nonexistent_workspace(self):
        """Test GET nonexistent workspace returns 404"""
        response = self.session.get(f"{BASE_URL}/api/workspaces/ws_nonexistent123")
        assert response.status_code == 404
        print("✓ GET nonexistent workspace returns 404")
    
    def test_update_workspace(self):
        """Test PUT /api/workspaces/{id} updates workspace"""
        # Create workspace
        create_res = self.session.post(f"{BASE_URL}/api/workspaces", json={
            "name": f"TEST_Update_{UNIQUE_ID}",
            "description": "Original description"
        })
        ws_id = create_res.json()["workspace_id"]
        
        # Update it
        new_name = f"TEST_Updated_{UNIQUE_ID}"
        response = self.session.put(f"{BASE_URL}/api/workspaces/{ws_id}", json={
            "name": new_name,
            "description": "Updated description"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == new_name
        assert data["description"] == "Updated description"
        print(f"✓ PUT /api/workspaces/{ws_id} updated successfully")
        
        # Verify with GET
        get_res = self.session.get(f"{BASE_URL}/api/workspaces/{ws_id}")
        assert get_res.json()["name"] == new_name
        print("  Update persisted correctly")
    
    def test_disable_enable_workspace(self):
        """Test PUT /api/workspaces/{id}/disable toggles workspace"""
        # Create workspace
        create_res = self.session.post(f"{BASE_URL}/api/workspaces", json={
            "name": f"TEST_Disable_{UNIQUE_ID}",
            "description": "To be disabled"
        })
        ws_id = create_res.json()["workspace_id"]
        
        # Disable it
        response = self.session.put(f"{BASE_URL}/api/workspaces/{ws_id}/disable")
        assert response.status_code == 200
        data = response.json()
        assert data["disabled"] == True
        print(f"✓ PUT /api/workspaces/{ws_id}/disable - workspace disabled")
        
        # Enable it again
        response = self.session.put(f"{BASE_URL}/api/workspaces/{ws_id}/disable")
        assert response.status_code == 200
        data = response.json()
        assert data["disabled"] == False
        print("  Workspace re-enabled successfully")
    
    def test_delete_workspace(self):
        """Test DELETE /api/workspaces/{id} removes workspace"""
        # Create workspace
        create_res = self.session.post(f"{BASE_URL}/api/workspaces", json={
            "name": f"TEST_Delete_{UNIQUE_ID}",
            "description": "To be deleted"
        })
        ws_id = create_res.json()["workspace_id"]
        
        # Delete it
        response = self.session.delete(f"{BASE_URL}/api/workspaces/{ws_id}")
        assert response.status_code == 200
        print(f"✓ DELETE /api/workspaces/{ws_id} successful")
        
        # Verify it's gone
        get_res = self.session.get(f"{BASE_URL}/api/workspaces/{ws_id}")
        assert get_res.status_code == 404
        print("  Workspace no longer exists")
    
    def test_workspaces_require_auth(self):
        """Test workspace endpoints require authentication"""
        unauth_session = requests.Session()
        
        response = unauth_session.get(f"{BASE_URL}/api/workspaces")
        assert response.status_code == 401
        
        response = unauth_session.post(f"{BASE_URL}/api/workspaces", json={"name": "Test"})
        assert response.status_code == 401
        
        print("✓ Workspace endpoints correctly require authentication")


class TestChannelEndpoints:
    """Channel CRUD endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup_workspace(self):
        """Login and create test workspace for channel tests"""
        self.session = requests.Session()
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        
        # Create test workspace
        ws_res = self.session.post(f"{BASE_URL}/api/workspaces", json={
            "name": f"TEST_Channels_WS_{UNIQUE_ID}",
            "description": "Workspace for channel tests"
        })
        assert ws_res.status_code == 200
        self.workspace_id = ws_res.json()["workspace_id"]
        yield
        # Cleanup
        try:
            self.session.delete(f"{BASE_URL}/api/workspaces/{self.workspace_id}")
        except:
            pass
    
    def test_get_channels_empty(self):
        """Test GET /api/workspaces/{id}/channels on new workspace"""
        response = self.session.get(f"{BASE_URL}/api/workspaces/{self.workspace_id}/channels")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET channels returned {len(data)} channels")
    
    def test_create_channel(self):
        """Test POST /api/workspaces/{id}/channels creates channel"""
        ch_name = f"test-channel-{UNIQUE_ID}"
        response = self.session.post(f"{BASE_URL}/api/workspaces/{self.workspace_id}/channels", json={
            "name": ch_name,
            "description": "Test channel",
            "ai_agents": ["claude", "chatgpt"]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == ch_name
        assert "channel_id" in data
        assert data["workspace_id"] == self.workspace_id
        assert "claude" in data["ai_agents"]
        print(f"✓ POST channel created: {data['channel_id']}")
        
        # Verify in list
        list_res = self.session.get(f"{BASE_URL}/api/workspaces/{self.workspace_id}/channels")
        channels = list_res.json()
        assert len(channels) >= 1
        print("  Channel appears in workspace channel list")
    
    def test_get_single_channel(self):
        """Test GET /api/channels/{id} returns channel details"""
        # Create channel first
        create_res = self.session.post(f"{BASE_URL}/api/workspaces/{self.workspace_id}/channels", json={
            "name": "test-single-channel",
            "description": "Single channel test",
            "ai_agents": ["claude"]
        })
        ch_id = create_res.json()["channel_id"]
        
        # Get it
        response = self.session.get(f"{BASE_URL}/api/channels/{ch_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["channel_id"] == ch_id
        assert data["name"] == "test-single-channel"
        print(f"✓ GET /api/channels/{ch_id} returned correct data")
    
    def test_update_channel(self):
        """Test PUT /api/channels/{id} updates channel"""
        # Create channel
        create_res = self.session.post(f"{BASE_URL}/api/workspaces/{self.workspace_id}/channels", json={
            "name": "original-name",
            "description": "Original description"
        })
        ch_id = create_res.json()["channel_id"]
        
        # Update it
        response = self.session.put(f"{BASE_URL}/api/channels/{ch_id}", json={
            "name": "updated-name",
            "description": "Updated description"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "updated-name"
        print(f"✓ PUT /api/channels/{ch_id} updated successfully")
    
    def test_delete_channel(self):
        """Test DELETE /api/channels/{id} removes channel"""
        # Create channel
        create_res = self.session.post(f"{BASE_URL}/api/workspaces/{self.workspace_id}/channels", json={
            "name": "to-delete",
            "description": "Will be deleted"
        })
        ch_id = create_res.json()["channel_id"]
        
        # Delete it
        response = self.session.delete(f"{BASE_URL}/api/channels/{ch_id}")
        assert response.status_code == 200
        print(f"✓ DELETE /api/channels/{ch_id} successful")
        
        # Verify gone
        get_res = self.session.get(f"{BASE_URL}/api/channels/{ch_id}")
        assert get_res.status_code == 404
        print("  Channel no longer exists")
    
    def test_channel_with_custom_agents(self):
        """Test creating channel with various AI agents"""
        response = self.session.post(f"{BASE_URL}/api/workspaces/{self.workspace_id}/channels", json={
            "name": "multi-agent-channel",
            "description": "Channel with multiple agents",
            "ai_agents": ["claude", "chatgpt", "gemini", "deepseek"]
        })
        assert response.status_code == 200
        data = response.json()
        assert len(data["ai_agents"]) == 4
        print("✓ Channel created with multiple AI agents")


class TestExistingWorkspaces:
    """Test operations on existing workspaces mentioned in the request"""
    
    @pytest.fixture(autouse=True)
    def setup_session(self):
        self.session = requests.Session()
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        yield
    
    def test_list_includes_existing_workspaces(self):
        """Verify existing workspaces are returned in list"""
        response = self.session.get(f"{BASE_URL}/api/workspaces")
        assert response.status_code == 200
        workspaces = response.json()
        print(f"✓ Found {len(workspaces)} workspaces for test user")
        for ws in workspaces:
            print(f"  - {ws['name']} ({ws['workspace_id']})")
    
    def test_access_test_workspace(self):
        """Test accessing 'Test Workspace' workspace"""
        # Get all workspaces and find Test Workspace
        response = self.session.get(f"{BASE_URL}/api/workspaces")
        workspaces = response.json()
        
        test_ws = next((ws for ws in workspaces if "Test" in ws["name"]), None)
        if test_ws:
            ws_response = self.session.get(f"{BASE_URL}/api/workspaces/{test_ws['workspace_id']}")
            assert ws_response.status_code == 200
            print(f"✓ Successfully accessed Test Workspace: {test_ws['workspace_id']}")
            
            # Check channels
            ch_response = self.session.get(f"{BASE_URL}/api/workspaces/{test_ws['workspace_id']}/channels")
            assert ch_response.status_code == 200
            channels = ch_response.json()
            print(f"  Found {len(channels)} channels in workspace")
        else:
            print("✓ No 'Test Workspace' found - creating one for test")
            create_res = self.session.post(f"{BASE_URL}/api/workspaces", json={
                "name": "Test Workspace",
                "description": "Created by pytest"
            })
            assert create_res.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
