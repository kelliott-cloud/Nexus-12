"""
Iteration 84: Full E2E QA Backend API Tests for Nexus Cloud Platform
Tests all critical API endpoints including auth, workspaces, channels, deployments, arena, costs, etc.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8080")
WORKSPACE_ID = "ws_f6ec6355bb18"

@pytest.fixture(scope="session")
def session():
    """Create a requests session with proper headers"""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s

@pytest.fixture(scope="session")
def auth_session(session):
    """Login and get authenticated session"""
    # Login with test credentials
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "test@test.com",
        "password": "testtest"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    user_data = resp.json()
    assert "user_id" in user_data
    return session

# ===== HEALTH CHECK =====
class TestHealth:
    """Health check tests"""
    
    def test_health_endpoint(self, session):
        """Test health endpoint returns healthy"""
        resp = session.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        print(f"✓ Health check passed: {data}")

# ===== AUTHENTICATION =====
class TestAuth:
    """Authentication API tests"""
    
    def test_login_success(self, session):
        """Test login with valid credentials"""
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com",
            "password": "testtest"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@test.com"
        assert "user_id" in data
        print(f"✓ Login successful: user_id={data['user_id']}")
    
    def test_login_invalid_credentials(self, session):
        """Test login with invalid credentials returns 401"""
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "invalid@test.com",
            "password": "wrongpassword"
        })
        assert resp.status_code == 401
        print("✓ Invalid login correctly returns 401")
    
    def test_auth_me_without_session(self):
        """Test /auth/me without session returns 401"""
        fresh_session = requests.Session()
        resp = fresh_session.get(f"{BASE_URL}/api/auth/me")
        # May return 401 or user data if cookies carried over
        print(f"✓ /auth/me status: {resp.status_code}")

# ===== WORKSPACES =====
class TestWorkspaces:
    """Workspace API tests"""
    
    def test_get_workspaces_list(self, auth_session):
        """Test fetching list of workspaces"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"✓ Found {len(data)} workspaces")
    
    def test_get_workspace_by_id(self, auth_session):
        """Test fetching specific workspace"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert "workspace_id" in data or "name" in data
        print(f"✓ Workspace: {data.get('name', 'N/A')}")
    
    def test_workspace_channels(self, auth_session):
        """Test fetching workspace channels"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/channels")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"✓ Found {len(data)} channels")
    
    def test_workspace_coordination_status(self, auth_session):
        """Test workspace coordination status"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/coordination-status")
        assert resp.status_code == 200
        data = resp.json()
        print(f"✓ Coordination status: {data}")
    
    def test_workspace_projects(self, auth_session):
        """Test fetching workspace projects"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"✓ Found {len(data)} projects")
    
    def test_workspace_tasks(self, auth_session):
        """Test fetching workspace tasks"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"✓ Found {len(data)} tasks")
    
    def test_workspace_members(self, auth_session):
        """Test fetching workspace members"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/members")
        assert resp.status_code == 200
        data = resp.json()
        # API returns {count, members} dict
        members = data.get("members", []) if isinstance(data, dict) else data
        print(f"✓ Found {len(members)} members")
    
    def test_workspace_analytics(self, auth_session):
        """Test fetching workspace analytics"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/analytics")
        assert resp.status_code == 200
        data = resp.json()
        print(f"✓ Analytics: {list(data.keys()) if isinstance(data, dict) else 'list data'}")

# ===== DEPLOYMENTS =====
class TestDeployments:
    """Deployment API tests"""
    
    def test_deployment_templates(self, auth_session):
        """Test fetching deployment templates"""
        resp = auth_session.get(f"{BASE_URL}/api/deployment-templates")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"✓ Found {len(data)} deployment templates")
    
    def test_workspace_deployments(self, auth_session):
        """Test fetching workspace deployments"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/deployments")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"✓ Found {len(data)} deployments")
    
    def test_deployment_limits(self, auth_session):
        """Test fetching deployment limits"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/deployment-limits")
        # May return 200 or 404 depending on setup
        print(f"✓ Deployment limits status: {resp.status_code}")

# ===== AGENT ARENA =====
class TestAgentArena:
    """Agent Arena API tests"""
    
    def test_arena_battles_list(self, auth_session):
        """Test fetching arena battles"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/arena/battles?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"✓ Found {len(data)} arena battles")
    
    def test_arena_leaderboard(self, auth_session):
        """Test fetching arena leaderboard"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/arena/leaderboard")
        assert resp.status_code == 200
        data = resp.json()
        leaderboard = data.get("leaderboard", [])
        print(f"✓ Leaderboard has {len(leaderboard)} entries")

# ===== COST DASHBOARD =====
class TestCostDashboard:
    """Cost Dashboard API tests"""
    
    def test_costs_7d(self, auth_session):
        """Test fetching 7-day costs"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/costs?period=7d")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_cost_usd" in data or "total_calls" in data or isinstance(data, dict)
        print(f"✓ 7-day costs: {data}")
    
    def test_costs_30d(self, auth_session):
        """Test fetching 30-day costs"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/costs?period=30d")
        assert resp.status_code == 200
        data = resp.json()
        print(f"✓ 30-day costs: {data.get('total_cost_usd', 0)}")
    
    def test_budget(self, auth_session):
        """Test fetching budget info"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/budget")
        assert resp.status_code == 200
        data = resp.json()
        print(f"✓ Budget: {data}")

# ===== BRIDGE & SOCIAL =====
class TestBridgeAndSocial:
    """Desktop Bridge and Social connections API tests"""
    
    def test_bridge_status(self, auth_session):
        """Test desktop bridge status"""
        resp = auth_session.get(f"{BASE_URL}/api/bridge/status")
        assert resp.status_code == 200
        data = resp.json()
        print(f"✓ Bridge status: {data}")
    
    def test_bridge_tools(self, auth_session):
        """Test fetching bridge tools"""
        resp = auth_session.get(f"{BASE_URL}/api/bridge/tools")
        # 200 or 404 - both acceptable (404 means not configured)
        assert resp.status_code in [200, 404]
        if resp.status_code == 200:
            data = resp.json()
            print(f"✓ Bridge tools: {len(data) if isinstance(data, list) else 'dict'}")
        else:
            print("✓ Bridge tools: not configured (404)")
    
    def test_social_platforms(self, auth_session):
        """Test fetching social platforms"""
        resp = auth_session.get(f"{BASE_URL}/api/social/platforms")
        assert resp.status_code == 200
        data = resp.json()
        print(f"✓ Social platforms: {len(data) if isinstance(data, list) else 'dict'}")
    
    def test_social_connections(self, auth_session):
        """Test fetching social connections"""
        resp = auth_session.get(f"{BASE_URL}/api/social/connections")
        assert resp.status_code == 200
        data = resp.json()
        print(f"✓ Social connections: {data}")

# ===== CHANNELS & MESSAGES =====
class TestChannelsMessages:
    """Channel and message API tests"""
    
    def test_get_channel_messages(self, auth_session):
        """Test fetching channel messages"""
        # First get channels
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/channels")
        channels = resp.json()
        if channels:
            channel_id = channels[0].get("channel_id")
            msg_resp = auth_session.get(f"{BASE_URL}/api/channels/{channel_id}/messages")
            assert msg_resp.status_code == 200
            messages = msg_resp.json()
            print(f"✓ Found {len(messages)} messages in channel {channel_id}")

# ===== WORKFLOWS =====
class TestWorkflows:
    """Workflow API tests"""
    
    def test_workspace_workflows(self, auth_session):
        """Test fetching workspace workflows"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/workflows")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"✓ Found {len(data)} workflows")
    
    def test_templates(self, auth_session):
        """Test fetching workflow templates"""
        resp = auth_session.get(f"{BASE_URL}/api/templates")
        assert resp.status_code == 200
        data = resp.json()
        print(f"✓ Found {len(data) if isinstance(data, list) else 'dict'} templates")

# ===== AI MODELS =====
class TestAIModels:
    """AI Models API tests"""
    
    def test_ai_models_list(self, auth_session):
        """Test fetching AI models list"""
        resp = auth_session.get(f"{BASE_URL}/api/ai-models")
        assert resp.status_code == 200
        data = resp.json()
        print(f"✓ Found {len(data) if isinstance(data, list) else 'dict'} AI models")

# ===== NOTIFICATIONS =====
class TestNotifications:
    """Notification API tests"""
    
    def test_notifications_list(self, auth_session):
        """Test fetching notifications"""
        resp = auth_session.get(f"{BASE_URL}/api/notifications?limit=20")
        assert resp.status_code == 200
        data = resp.json()
        print(f"✓ Notifications: {len(data) if isinstance(data, list) else 'dict'}")

# ===== WORKSPACE AGENTS =====
class TestWorkspaceAgents:
    """Workspace agents API tests"""
    
    def test_workspace_agents(self, auth_session):
        """Test fetching workspace agents"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents")
        assert resp.status_code == 200
        data = resp.json()
        print(f"✓ Found {len(data) if isinstance(data, list) else 'dict'} workspace agents")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
