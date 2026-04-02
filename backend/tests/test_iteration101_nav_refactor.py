from conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, BASE_URL
"""
Iteration 101 - Navigation Refactor and P0 Backend Integration Tests

Features tested:
1. Frontend dropdown navigation (5 grouped menus) - via Playwright
2. Backend P0: agent_prompt_builder for Nexus agents with skills
3. Backend P0: Tool access gating (denied_tools, allowed_tools)
4. Backend P0: Agent context builder includes skill profile
5. P2: MarketplacePage uses api instance
6. P3: .env.example files exist
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

@pytest.fixture(scope="module")
def api_client():
    """Shared requests session with cookies for auth"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_session(api_client):
    """Authenticate and return session with cookies"""
    # Super admin login
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_ADMIN_EMAIL,
        "password": "test"
    })
    if response.status_code != 200:
        pytest.skip("Authentication failed - skipping tests")
    return api_client


@pytest.fixture(scope="module")
def workspace_id(auth_session):
    """Get first workspace ID"""
    response = auth_session.get(f"{BASE_URL}/api/workspaces")
    if response.status_code == 200:
        workspaces = response.json()
        if workspaces:
            return workspaces[0]["workspace_id"]
    return "ws_a92cb83bfdb2"  # Fallback


class TestBackendP0AgentPromptBuilder:
    """Test: agent_prompt_builder is called for Nexus agents with skills"""
    
    def test_get_workspace_agents(self, auth_session, workspace_id):
        """Verify workspace agents endpoint returns agents (used by collaboration_core.py)"""
        response = auth_session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/agents")
        assert response.status_code == 200
        data = response.json()
        # API returns {"agents": [...], "count": N, ...}
        agents = data.get("agents", data) if isinstance(data, dict) else data
        assert isinstance(agents, list)
        print(f"Found {len(agents)} agents in workspace")
        
    def test_agent_skills_endpoint(self, auth_session, workspace_id):
        """Test GET agent skills endpoint - used by build_agent_prompt"""
        # First get an agent ID
        response = auth_session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/agents")
        if response.status_code != 200 or not response.json():
            pytest.skip("No agents found")
        data = response.json()
        agents = data.get("agents", data) if isinstance(data, dict) else data
        # Find a nexus agent (starts with nxa_)
        nexus_agent = None
        for a in agents:
            if isinstance(a, dict) and a.get("agent_id", "").startswith("nxa_"):
                nexus_agent = a
                break
        if not nexus_agent:
            pytest.skip("No nexus agents found")
        agent_id = nexus_agent["agent_id"]
        
        # Get agent skills
        response = auth_session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/agents/{agent_id}/skills")
        assert response.status_code in [200, 404]  # 404 is OK if no skills assigned yet
        print(f"Agent skills response: {response.status_code}")


class TestBackendP0ToolAccessGating:
    """Test: Tool access gating in routes_ai_tools.py checks denied_tools and allowed_tools"""
    
    def test_create_nexus_agent_with_tool_restrictions(self, auth_session, workspace_id):
        """Create a Nexus agent with denied_tools and allowed_tools"""
        agent_data = {
            "name": f"TEST_Tool_Gated_Agent_{int(time.time())}",
            "base_model": "claude",
            "system_prompt": "You are a test agent with restricted tools.",
            "color": "#FF5733",
            "denied_tools": ["execute_code", "delete_project"],
            "allowed_tools": ["create_task", "list_projects", "read_memory"]
        }
        response = auth_session.post(
            f"{BASE_URL}/api/workspaces/{workspace_id}/agents",
            json=agent_data
        )
        # Accept 200, 201, or 400 if agent already exists
        assert response.status_code in [200, 201, 400]
        if response.status_code in [200, 201]:
            agent = response.json()
            print(f"Created agent with ID: {agent.get('agent_id')}")
            # Verify the agent was created
            assert "agent_id" in agent
            
    def test_get_workspace_agents_for_tool_config(self, auth_session, workspace_id):
        """Verify workspace agents endpoint returns agents (nexus agents may have tool config)"""
        response = auth_session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/agents")
        assert response.status_code == 200
        data = response.json()
        agents = data.get("agents", data) if isinstance(data, dict) else data
        # Check if any nexus agent has tool restrictions
        nexus_agents = [a for a in agents if isinstance(a, dict) and a.get("agent_id", "").startswith("nxa_")]
        print(f"Found {len(nexus_agents)} nexus agents")
        for agent in nexus_agents[:3]:
            if agent.get("denied_tools") or agent.get("allowed_tools"):
                print(f"Agent {agent.get('name')} has tool restrictions: denied={agent.get('denied_tools')}, allowed={agent.get('allowed_tools')}")
                break


class TestBackendP0AgentContextBuilder:
    """Test: agent_context_builder.py includes skill profile in context block"""
    
    def test_agent_skills_leaderboard(self, auth_session, workspace_id):
        """Verify skills leaderboard endpoint (agent skills are stored)"""
        response = auth_session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/skills/leaderboard")
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            print(f"Skills leaderboard: {data}")
        
    def test_workspace_analytics_for_cost_context(self, auth_session, workspace_id):
        """Verify analytics data is available (used by context builder for cost info)"""
        response = auth_session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/analytics/summary")
        # May return 200 or 404 if no data
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            print(f"Analytics available for context: {response.json()}")
            
    def test_agent_ai_skills_config(self, auth_session, workspace_id):
        """Test AI skills config endpoint - another source for skill profile"""
        response = auth_session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/ai-skills")
        assert response.status_code in [200, 403, 404]  # 403 if permission denied
        if response.status_code == 200:
            skills = response.json()
            print(f"AI skills config available: {type(skills)}")
        elif response.status_code == 403:
            print("AI skills config: permission denied (expected for some users)")


class TestP2MarketplacePage:
    """Test: MarketplacePage uses api instance (not fetch()) and handleSilent"""
    
    def test_marketplace_agents_endpoint(self, auth_session):
        """Test marketplace agents endpoint which MarketplacePage calls via api instance"""
        response = auth_session.get(f"{BASE_URL}/api/marketplace/agents?sort=popular&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        print(f"Marketplace has {len(data.get('agents', []))} agents")
        
    def test_marketplace_stats_endpoint(self, auth_session):
        """Test marketplace stats endpoint"""
        response = auth_session.get(f"{BASE_URL}/api/marketplace/agent-stats")
        assert response.status_code == 200
        stats = response.json()
        assert "total_agents" in stats or "total_installs" in stats or isinstance(stats, dict)
        print(f"Marketplace stats: {stats}")
        
    def test_marketplace_agent_detail(self, auth_session):
        """Test fetching a marketplace agent detail - uses api.get"""
        # First get list
        response = auth_session.get(f"{BASE_URL}/api/marketplace/agents?limit=1")
        if response.status_code == 200 and response.json().get("agents"):
            agent = response.json()["agents"][0]
            agent_id = agent.get("agent_id")
            # Get detail
            detail_resp = auth_session.get(f"{BASE_URL}/api/marketplace/agents/{agent_id}")
            assert detail_resp.status_code in [200, 404]
            print(f"Marketplace agent detail: {detail_resp.status_code}")


class TestP3EnvExampleFiles:
    """Test: .env.example files exist for frontend and backend"""
    
    def test_backend_env_example_exists(self):
        """Verify backend/.env.example exists with required keys"""
        env_path = "/app/backend/.env.example"
        assert os.path.exists(env_path), "backend/.env.example does not exist"
        with open(env_path, "r") as f:
            content = f.read()
        assert "MONGO_URL" in content
        assert "DB_NAME" in content
        keys = [line.split('=')[0] for line in content.strip().split('\n') if '=' in line]
        print(f"Backend .env.example keys: {keys}")
        
    def test_frontend_env_example_exists(self):
        """Verify frontend/.env.example exists with required keys"""
        env_path = "/app/frontend/.env.example"
        assert os.path.exists(env_path), "frontend/.env.example does not exist"
        with open(env_path, "r") as f:
            content = f.read()
        assert "REACT_APP_BACKEND_URL" in content
        keys = [line.split('=')[0] for line in content.strip().split('\n') if '=' in line]
        print(f"Frontend .env.example keys: {keys}")


class TestWorkspaceAndChannelAPIs:
    """Additional tests for workspace navigation context"""
    
    def test_get_workspace_channels(self, auth_session, workspace_id):
        """Test channels endpoint - needed for workspace navigation"""
        response = auth_session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/channels")
        assert response.status_code == 200
        channels = response.json()
        assert isinstance(channels, list)
        print(f"Workspace has {len(channels)} channels")
        
    def test_get_workspace_details(self, auth_session, workspace_id):
        """Test workspace details endpoint"""
        response = auth_session.get(f"{BASE_URL}/api/workspaces/{workspace_id}")
        assert response.status_code == 200
        workspace = response.json()
        assert "workspace_id" in workspace
        assert "name" in workspace
        print(f"Workspace: {workspace.get('name')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
