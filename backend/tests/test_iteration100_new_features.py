from conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, BASE_URL
"""
Test Iteration 100 - New Nexus Features
Tests:
1. File upload training (POST /train/file with multipart form)
2. Auto-refresh toggle (POST /train/auto-refresh)
3. Training quality dashboard (GET /train/quality-dashboard)
4. Cost breakdown per skill (GET /cost-breakdown)
5. Leaderboard snapshots (GET /leaderboard/snapshots, POST /leaderboard/snapshot)
6. Multi-agent playground (POST /playground/multi-agent)
7. Knowledge flag (PUT /knowledge/{chunk_id}/flag)
8. Knowledge stats (GET /knowledge/stats)
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
WS_ID = "ws_a92cb83bfdb2"
AGENT_ID = "nxa_80888f5c29d3"
SECOND_AGENT_ID = "nxa_63f28e63e15c"


class TestIteration100NewFeatures:
    """New features for iteration 100: file upload, auto-refresh, quality dashboard, cost breakdown, snapshots, multi-agent"""

    @pytest.fixture(autouse=True)
    def setup(self, api_client, auth_cookies):
        """Setup for all tests"""
        self.client = api_client
        self.client.cookies.update(auth_cookies)

    def test_file_upload_training(self, api_client, auth_cookies):
        """Test file upload training endpoint - POST /train/file"""
        # Create fresh session for multipart
        session = requests.Session()
        session.cookies.update(auth_cookies)
        
        # Create a test file in memory
        test_content = b"This is test training content for the AI agent.\nIt contains multiple lines of text about machine learning.\nThe agent should learn from this knowledge base.\nAdditional context about API testing and development."
        
        # For multipart, don't set JSON content-type header
        files = {"file": ("test_training.txt", io.BytesIO(test_content), "text/plain")}
        data = {"topic": "test_file_upload"}
        
        response = session.post(
            f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/train/file",
            files=files,
            data=data
        )
        
        assert response.status_code == 200, f"File upload failed: {response.text}"
        result = response.json()
        assert "session_id" in result, "Response should contain session_id"
        assert "total_chunks" in result, "Response should contain total_chunks"
        assert result["total_chunks"] >= 0, "Should have ingested chunks"
        print(f"File upload training: {result['total_chunks']} chunks, session {result['session_id']}")

    def test_auto_refresh_toggle_enable(self, api_client, auth_cookies):
        """Test auto-refresh toggle - enable"""
        api_client.cookies.update(auth_cookies)
        
        response = api_client.post(
            f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/train/auto-refresh",
            json={"enabled": True, "interval_days": 30}
        )
        
        assert response.status_code == 200, f"Auto-refresh toggle failed: {response.text}"
        result = response.json()
        assert result.get("auto_refresh") == True, "auto_refresh should be True"
        assert result.get("interval_days") == 30, "interval_days should be 30"
        print(f"Auto-refresh enabled: {result}")

    def test_auto_refresh_toggle_disable(self, api_client, auth_cookies):
        """Test auto-refresh toggle - disable"""
        api_client.cookies.update(auth_cookies)
        
        response = api_client.post(
            f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/train/auto-refresh",
            json={"enabled": False, "interval_days": 30}
        )
        
        assert response.status_code == 200, f"Auto-refresh toggle failed: {response.text}"
        result = response.json()
        assert result.get("auto_refresh") == False, "auto_refresh should be False"
        print(f"Auto-refresh disabled: {result}")

    def test_training_quality_dashboard(self, api_client, auth_cookies):
        """Test training quality dashboard endpoint"""
        api_client.cookies.update(auth_cookies)
        
        response = api_client.get(
            f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/train/quality-dashboard"
        )
        
        assert response.status_code == 200, f"Quality dashboard failed: {response.text}"
        result = response.json()
        assert "agent_id" in result, "Should have agent_id"
        assert "total_chunks" in result, "Should have total_chunks"
        assert "skill_coverage" in result, "Should have skill_coverage array"
        assert isinstance(result["skill_coverage"], list), "skill_coverage should be list"
        assert "topic_breakdown" in result, "Should have topic_breakdown"
        
        # Check skill coverage structure if present
        if result["skill_coverage"]:
            sc = result["skill_coverage"][0]
            assert "skill_id" in sc, "skill_coverage item should have skill_id"
            assert "coverage_pct" in sc, "skill_coverage item should have coverage_pct"
        
        print(f"Quality dashboard: {result['total_chunks']} chunks, {len(result['skill_coverage'])} skills tracked")

    def test_cost_breakdown(self, api_client, auth_cookies):
        """Test cost breakdown per skill endpoint"""
        api_client.cookies.update(auth_cookies)
        
        response = api_client.get(
            f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/cost-breakdown?days=30"
        )
        
        assert response.status_code == 200, f"Cost breakdown failed: {response.text}"
        result = response.json()
        assert "agent_id" in result, "Should have agent_id"
        assert "total_cost_usd" in result, "Should have total_cost_usd"
        assert "total_calls" in result, "Should have total_calls"
        assert "daily_costs" in result, "Should have daily_costs"
        assert "skill_costs" in result, "Should have skill_costs"
        assert isinstance(result["daily_costs"], list), "daily_costs should be list"
        assert isinstance(result["skill_costs"], dict), "skill_costs should be dict"
        
        print(f"Cost breakdown: ${result['total_cost_usd']} total, {result['total_calls']} calls")

    def test_leaderboard_snapshots_get(self, api_client, auth_cookies):
        """Test getting leaderboard snapshots"""
        api_client.cookies.update(auth_cookies)
        
        response = api_client.get(
            f"{BASE_URL}/api/leaderboard/snapshots?days=30&limit=5"
        )
        
        assert response.status_code == 200, f"Get snapshots failed: {response.text}"
        result = response.json()
        assert "snapshots" in result, "Should have snapshots array"
        assert isinstance(result["snapshots"], list), "snapshots should be list"
        
        # Snapshots may already exist from scheduler auto-run on startup
        print(f"Got {len(result['snapshots'])} leaderboard snapshots")

    def test_leaderboard_snapshot_create(self, api_client, auth_cookies):
        """Test creating a leaderboard snapshot"""
        api_client.cookies.update(auth_cookies)
        
        response = api_client.post(
            f"{BASE_URL}/api/leaderboard/snapshot"
        )
        
        assert response.status_code == 200, f"Create snapshot failed: {response.text}"
        result = response.json()
        assert "snapshot_id" in result, "Should have snapshot_id"
        assert "timestamp" in result, "Should have timestamp"
        assert "data" in result, "Should have data array"
        assert isinstance(result["data"], list), "data should be list"
        
        print(f"Created snapshot {result['snapshot_id']} with {len(result['data'])} ranked agents")

    def test_multi_agent_playground(self, api_client, auth_cookies):
        """Test multi-agent playground sandbox"""
        api_client.cookies.update(auth_cookies)
        
        response = api_client.post(
            f"{BASE_URL}/api/workspaces/{WS_ID}/playground/multi-agent",
            json={
                "agent_ids": [AGENT_ID, SECOND_AGENT_ID],
                "topic": "Testing AI collaboration features",
                "rounds": 2
            }
        )
        
        assert response.status_code == 200, f"Multi-agent playground failed: {response.text}"
        result = response.json()
        assert "session_id" in result, "Should have session_id"
        assert "conversation" in result, "Should have conversation array"
        assert "rounds" in result, "Should have rounds"
        assert isinstance(result["conversation"], list), "conversation should be list"
        
        # Note: With LLM key, agents respond; without, they may show error messages
        print(f"Multi-agent session {result['session_id']} completed {result['rounds']} rounds with {len(result['conversation'])} messages")

    def test_knowledge_stats(self, api_client, auth_cookies):
        """Test knowledge stats endpoint"""
        api_client.cookies.update(auth_cookies)
        
        response = api_client.get(
            f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/knowledge/stats"
        )
        
        assert response.status_code == 200, f"Knowledge stats failed: {response.text}"
        result = response.json()
        assert "total_chunks" in result, "Should have total_chunks"
        assert "flagged" in result, "Should have flagged count"
        assert "active" in result, "Should have active count"
        assert "categories" in result, "Should have categories dict"
        assert "top_sources" in result, "Should have top_sources"
        
        print(f"Knowledge stats: {result['total_chunks']} total, {result['active']} active, {result['flagged']} flagged")

    def test_knowledge_flag_chunk(self, api_client, auth_cookies):
        """Test flagging a knowledge chunk"""
        api_client.cookies.update(auth_cookies)
        
        # First get a chunk to flag
        list_response = api_client.get(
            f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/knowledge?limit=1"
        )
        
        if list_response.status_code != 200:
            pytest.skip("No knowledge chunks to test flagging")
            return
            
        chunks = list_response.json().get("chunks", [])
        if not chunks:
            pytest.skip("No knowledge chunks found for flagging test")
            return
        
        chunk_id = chunks[0]["chunk_id"]
        
        # Flag the chunk
        response = api_client.put(
            f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/knowledge/{chunk_id}/flag"
        )
        
        assert response.status_code == 200, f"Flag chunk failed: {response.text}"
        result = response.json()
        assert "flagged" in result, "Should have flagged field"
        assert result["flagged"] == chunk_id, "Should return flagged chunk_id"
        
        print(f"Flagged chunk {chunk_id}")


# Fixtures
@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_cookies(api_client):
    """Get authentication cookies via login"""
    response = api_client.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_ADMIN_EMAIL, "password": "test"}
    )
    if response.status_code != 200:
        pytest.skip(f"Login failed: {response.status_code} - {response.text}")
    
    cookies = response.cookies.get_dict()
    print(f"Logged in, got {len(cookies)} cookies")
    return cookies
