from conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, BASE_URL
"""
Iteration 93 — AI Agent Marketplace, Status Page Metrics, Redis Health, API Docs Testing

Tests cover:
1. Status page system metrics (CPU, RAM, disk)
2. Redis health probe endpoint
3. API documentation page
4. Marketplace CRUD operations (browse, publish, rate, install)
5. Marketplace statistics
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "http://localhost:8080"

TEST_EMAIL = TEST_ADMIN_EMAIL
TEST_PASSWORD = "test"


@pytest.fixture(scope="module")
def session():
    """Create authenticated session"""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    # Login
    login_resp = s.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if login_resp.status_code != 200:
        pytest.skip(f"Login failed: {login_resp.status_code} - {login_resp.text[:200]}")
    return s


class TestStatusEndpoints:
    """Status page system metrics and health"""
    
    def test_status_returns_system_metrics(self, session):
        """GET /api/status returns system metrics (cpu_percent, memory_used_pct, disk_used_pct)"""
        resp = session.get(f"{BASE_URL}/api/status")
        assert resp.status_code == 200
        data = resp.json()
        
        # Check overall status fields
        assert "status" in data
        assert "uptime_seconds" in data
        assert "services" in data
        
        # Check system metrics
        services = data["services"]
        assert "system" in services, "System metrics missing"
        system = services["system"]
        assert "cpu_percent" in system, "cpu_percent missing in system metrics"
        assert "memory_used_pct" in system, "memory_used_pct missing in system metrics"
        assert "disk_used_pct" in system, "disk_used_pct missing in system metrics"
        
        # Validate values are reasonable
        assert isinstance(system["cpu_percent"], (int, float))
        assert isinstance(system["memory_used_pct"], (int, float))
        assert isinstance(system["disk_used_pct"], (int, float))
        print(f"System metrics: CPU={system['cpu_percent']}%, RAM={system['memory_used_pct']}%, Disk={system['disk_used_pct']}%")
    
    def test_status_has_ai_models_check(self, session):
        """GET /api/status includes ai_models check"""
        resp = session.get(f"{BASE_URL}/api/status")
        assert resp.status_code == 200
        data = resp.json()
        
        services = data["services"]
        assert "ai_models" in services
        ai = services["ai_models"]
        assert "status" in ai
        assert "configured_count" in ai
        print(f"AI Models: {ai['configured_count']} configured, status={ai['status']}")


class TestRedisHealthEndpoint:
    """Redis health probe endpoint"""
    
    def test_redis_health_endpoint_exists(self, session):
        """GET /api/health/redis returns health status"""
        resp = session.get(f"{BASE_URL}/api/health/redis")
        assert resp.status_code == 200
        data = resp.json()
        
        # Check required fields
        assert "status" in data
        assert "redis_required" in data
        assert "redis_configured" in data
        
        print(f"Redis health: status={data['status']}, required={data['redis_required']}, configured={data['redis_configured']}")
        
        # If operational, check additional fields
        if data["status"] == "operational":
            assert "latency_ms" in data
            assert "version" in data
            print(f"Redis operational: v{data.get('version')}, latency={data.get('latency_ms')}ms")


class TestAPIDocsEndpoint:
    """API documentation page"""
    
    def test_api_docs_html_page(self, session):
        """GET /api/docs/api returns comprehensive HTML API documentation"""
        resp = session.get(f"{BASE_URL}/api/docs/api")
        assert resp.status_code == 200
        
        # Check content type is HTML
        content_type = resp.headers.get("content-type", "")
        assert "text/html" in content_type, f"Expected HTML, got {content_type}"
        
        content = resp.text
        
        # Check title is present
        assert "Nexus" in content or "API" in content
        
        # Check request/response examples are included (key sections)
        assert "/api/auth" in content, "Auth endpoints missing"
        assert "/api/workspaces" in content, "Workspaces endpoints missing"
        assert "/api/marketplace" in content, "Marketplace endpoints missing"
        assert "/api/health" in content, "Health endpoints missing"
        
        print(f"API docs page loaded: {len(content)} bytes, contains marketplace and health sections")


class TestMarketplaceBrowse:
    """Marketplace browse and search"""
    
    def test_browse_agents_returns_list(self, session):
        """GET /api/marketplace/agents returns published agents list with total count"""
        resp = session.get(f"{BASE_URL}/api/marketplace/agents")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "agents" in data
        assert "total" in data
        assert isinstance(data["agents"], list)
        assert isinstance(data["total"], int)
        
        print(f"Marketplace: {data['total']} total agents, returned {len(data['agents'])} in this page")
        
        # Check categories returned
        assert "categories" in data
        assert isinstance(data["categories"], list)
    
    def test_browse_agents_with_category_filter(self, session):
        """GET /api/marketplace/agents?category=coding filters by category"""
        resp = session.get(f"{BASE_URL}/api/marketplace/agents?category=coding")
        assert resp.status_code == 200
        data = resp.json()
        
        # All returned agents should be in coding category
        for agent in data["agents"]:
            assert agent.get("category") == "coding", f"Agent {agent.get('name')} has category {agent.get('category')}"
    
    def test_browse_agents_with_search(self, session):
        """GET /api/marketplace/agents?search=code searches by name/description"""
        resp = session.get(f"{BASE_URL}/api/marketplace/agents?search=code")
        assert resp.status_code == 200
        data = resp.json()
        
        # Should return list (may be empty if no matches)
        assert "agents" in data


class TestMarketplacePublish:
    """Marketplace publish agent"""
    
    def test_publish_agent_with_required_fields(self, session):
        """POST /api/marketplace/agents publishes a new agent with required fields"""
        unique_id = uuid.uuid4().hex[:8]
        agent_data = {
            "name": f"TEST_Agent_{unique_id}",
            "description": "A test agent for automated testing",
            "category": "coding",
            "base_model": "claude",
            "system_prompt": "You are a test agent for automated testing. This is a placeholder prompt that should be at least 10 characters.",
            "tags": ["test", "automation"],
            "color": "#6366f1"
        }
        
        resp = session.post(f"{BASE_URL}/api/marketplace/agents", json=agent_data)
        assert resp.status_code == 200
        data = resp.json()
        
        # Check agent was created
        assert "agent_id" in data
        assert data["name"] == agent_data["name"]
        assert data["category"] == "coding"
        assert data["status"] == "published"
        
        print(f"Published agent: {data['agent_id']} - {data['name']}")
        
        # Store for later tests
        session.test_agent_id = data["agent_id"]
        return data["agent_id"]
    
    def test_publish_agent_validates_category(self, session):
        """POST /api/marketplace/agents rejects invalid category"""
        agent_data = {
            "name": "Invalid Category Test",
            "category": "invalid_category",
            "system_prompt": "This is a test system prompt with at least 10 chars.",
        }
        
        resp = session.post(f"{BASE_URL}/api/marketplace/agents", json=agent_data)
        assert resp.status_code == 400


class TestMarketplaceAgentDetail:
    """Marketplace agent detail view"""
    
    def test_get_agent_detail_includes_system_prompt(self, session):
        """GET /api/marketplace/agents/:agent_id returns full agent detail including system_prompt"""
        # First get list to find an agent
        list_resp = session.get(f"{BASE_URL}/api/marketplace/agents?limit=1")
        assert list_resp.status_code == 200
        agents = list_resp.json().get("agents", [])
        
        if not agents:
            pytest.skip("No marketplace agents available")
        
        agent_id = agents[0]["agent_id"]
        
        # Get detail
        resp = session.get(f"{BASE_URL}/api/marketplace/agents/{agent_id}")
        assert resp.status_code == 200
        data = resp.json()
        
        # Check full detail fields
        assert "agent_id" in data
        assert "system_prompt" in data, "system_prompt missing in detail view"
        assert "name" in data
        assert "description" in data
        assert "base_model" in data
        
        print(f"Agent detail: {data['name']}, prompt={len(data.get('system_prompt', ''))} chars")
    
    def test_get_nonexistent_agent_returns_404(self, session):
        """GET /api/marketplace/agents/:agent_id returns 404 for missing agent"""
        resp = session.get(f"{BASE_URL}/api/marketplace/agents/mkt_nonexistent_12345")
        assert resp.status_code == 404


class TestMarketplaceRate:
    """Marketplace rating functionality"""
    
    def test_rate_agent_updates_average(self, session):
        """POST /api/marketplace/agents/:agent_id/rate submits rating and returns updated avg"""
        # Get an existing agent (Code Reviewer Pro mentioned in context)
        list_resp = session.get(f"{BASE_URL}/api/marketplace/agents?limit=1")
        assert list_resp.status_code == 200
        agents = list_resp.json().get("agents", [])
        
        if not agents:
            pytest.skip("No marketplace agents available")
        
        agent_id = agents[0]["agent_id"]
        
        # Submit rating
        resp = session.post(f"{BASE_URL}/api/marketplace/agents/{agent_id}/rate", json={
            "rating": 4,
            "review": "Good test review"
        })
        assert resp.status_code == 200
        data = resp.json()
        
        # Check response
        assert "status" in data
        assert data["status"] == "rated"
        assert "avg_rating" in data
        assert "rating_count" in data
        
        print(f"Rated agent: avg={data['avg_rating']}, count={data['rating_count']}")
    
    def test_rate_agent_validates_rating_range(self, session):
        """POST /api/marketplace/agents/:agent_id/rate validates rating is 1-5"""
        list_resp = session.get(f"{BASE_URL}/api/marketplace/agents?limit=1")
        agents = list_resp.json().get("agents", [])
        
        if not agents:
            pytest.skip("No marketplace agents available")
        
        agent_id = agents[0]["agent_id"]
        
        # Try invalid rating (6 is out of range)
        resp = session.post(f"{BASE_URL}/api/marketplace/agents/{agent_id}/rate", json={
            "rating": 6
        })
        # Should fail validation
        assert resp.status_code == 422


class TestMarketplaceInstall:
    """Marketplace install functionality"""
    
    def test_install_agent_to_workspace(self, session):
        """POST /api/marketplace/agents/:agent_id/install installs agent to workspace"""
        # Get an existing agent
        list_resp = session.get(f"{BASE_URL}/api/marketplace/agents?limit=1")
        assert list_resp.status_code == 200
        agents = list_resp.json().get("agents", [])
        
        if not agents:
            pytest.skip("No marketplace agents available")
        
        agent_id = agents[0]["agent_id"]
        
        # Install with workspace_id
        resp = session.post(f"{BASE_URL}/api/marketplace/agents/{agent_id}/install?workspace_id=ws_test_install")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "status" in data
        assert data["status"] == "installed"
        assert "install_id" in data
        
        print(f"Installed agent: {agent_id} -> {data['install_id']}")
    
    def test_install_requires_workspace_id(self, session):
        """POST /api/marketplace/agents/:agent_id/install requires workspace_id"""
        list_resp = session.get(f"{BASE_URL}/api/marketplace/agents?limit=1")
        agents = list_resp.json().get("agents", [])
        
        if not agents:
            pytest.skip("No marketplace agents available")
        
        agent_id = agents[0]["agent_id"]
        
        # Install without workspace_id
        resp = session.post(f"{BASE_URL}/api/marketplace/agents/{agent_id}/install")
        assert resp.status_code == 400


class TestMarketplaceStats:
    """Marketplace statistics"""
    
    def test_agent_stats_returns_totals(self, session):
        """GET /api/marketplace/agent-stats returns marketplace statistics"""
        resp = session.get(f"{BASE_URL}/api/marketplace/agent-stats")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "total_agents" in data
        assert "total_installs" in data
        assert "categories" in data
        
        assert isinstance(data["total_agents"], int)
        assert isinstance(data["total_installs"], int)
        assert isinstance(data["categories"], dict)
        
        print(f"Marketplace stats: {data['total_agents']} agents, {data['total_installs']} installs")
        print(f"Category breakdown: {data['categories']}")


class TestMarketplaceMyAgents:
    """Current user's published agents"""
    
    def test_my_agents_returns_user_published(self, session):
        """GET /api/marketplace/my-agents returns current user published agents"""
        resp = session.get(f"{BASE_URL}/api/marketplace/my-agents")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "agents" in data
        assert isinstance(data["agents"], list)
        
        print(f"My published agents: {len(data['agents'])}")


class TestHealthEndpoints:
    """Additional health endpoints"""
    
    def test_basic_health_check(self, session):
        """GET /api/health returns healthy status"""
        resp = session.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "status" in data
        print(f"Health check: status={data['status']}")
    
    def test_startup_probe(self, session):
        """GET /api/health/startup returns full readiness"""
        resp = session.get(f"{BASE_URL}/api/health/startup")
        # May be 200 or 503 depending on Redis availability
        assert resp.status_code in [200, 503]
        data = resp.json()
        
        assert "ready" in data
        assert "checks" in data
        print(f"Startup probe: ready={data['ready']}, checks={data['checks']}")
    
    def test_liveness_probe(self, session):
        """GET /api/health/live returns alive"""
        resp = session.get(f"{BASE_URL}/api/health/live")
        assert resp.status_code == 200
        data = resp.json()
        
        assert data.get("alive") == True
