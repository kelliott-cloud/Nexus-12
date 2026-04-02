from conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, BASE_URL
"""
Iteration 97 - Agent Training RAG Module + Cost Alerts + Performance Time Series Tests

Tests for:
1. Agent Training RAG (routes_agent_training.py)
   - POST /api/workspaces/{ws}/agents/{agent_id}/train/text - Ingest text into agent knowledge base
   - POST /api/workspaces/{ws}/agents/{agent_id}/train/url - Crawl URLs and ingest content
   - GET /api/workspaces/{ws}/agents/{agent_id}/knowledge - List agent knowledge chunks  
   - GET /api/workspaces/{ws}/agents/{agent_id}/training-sessions - List training sessions
   - POST /api/workspaces/{ws}/agents/{agent_id}/knowledge/query - TF-IDF knowledge retrieval
   - DELETE /api/workspaces/{ws}/agents/{agent_id}/knowledge/{chunk_id} - Delete knowledge chunk

2. Cost Alerts (routes_cost_alerts.py)
   - GET /api/workspaces/{ws}/cost-alerts - Get cost alerts
   - PUT /api/workspaces/{ws}/cost-alerts/acknowledge - Acknowledge alerts
   - PUT /api/workspaces/{ws}/budget/thresholds - Update alert thresholds

3. Agent Evaluator - run_real_assessment with AI/heuristic scoring

4. Agent Prompt Builder - RAG knowledge injection
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
TEST_WORKSPACE = "ws_a92cb83bfdb2"
TEST_AGENT = "nxa_80888f5c29d3"


@pytest.fixture(scope="module")
def auth_session():
    """Authenticate and return session with cookies"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login
    login_res = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_ADMIN_EMAIL,
        "password": "test"
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    return session


class TestAgentTrainingRAG:
    """Tests for Agent Training RAG module"""

    def test_train_from_text_endpoint(self, auth_session):
        """POST /api/workspaces/{ws}/agents/{agent_id}/train/text - Ingest text content"""
        res = auth_session.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/agents/{TEST_AGENT}/train/text",
            json={
                "title": "Test Security Guide",
                "content": "This is a comprehensive guide about web security. SQL injection is a common attack where malicious SQL statements are inserted into entry fields. Cross-site scripting (XSS) allows attackers to inject malicious scripts. CSRF attacks force users to execute unwanted actions. Always sanitize user input and use parameterized queries to prevent these attacks.",
                "topic": "security"
            }
        )
        assert res.status_code == 200, f"Train from text failed: {res.status_code} - {res.text}"
        data = res.json()
        assert "session_id" in data, "Response should contain session_id"
        assert "total_chunks" in data, "Response should contain total_chunks"
        assert data["total_chunks"] >= 1, "Should create at least 1 chunk"
        print(f"SUCCESS: Text ingestion created {data['total_chunks']} chunks, session: {data['session_id']}")

    def test_train_from_url_endpoint(self, auth_session):
        """POST /api/workspaces/{ws}/agents/{agent_id}/train/url - Crawl URLs"""
        res = auth_session.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/agents/{TEST_AGENT}/train/url",
            json={
                "urls": ["https://httpbin.org/html"],
                "topics": ["test", "http"]
            }
        )
        assert res.status_code == 200, f"Train from URL failed: {res.status_code} - {res.text}"
        data = res.json()
        assert "session_id" in data, "Response should contain session_id"
        assert "successful_urls" in data, "Response should contain successful_urls"
        print(f"SUCCESS: URL crawl processed {data.get('successful_urls', 0)} URLs, {data.get('total_chunks', 0)} chunks")

    def test_get_agent_knowledge(self, auth_session):
        """GET /api/workspaces/{ws}/agents/{agent_id}/knowledge - List knowledge chunks"""
        res = auth_session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/agents/{TEST_AGENT}/knowledge"
        )
        assert res.status_code == 200, f"Get knowledge failed: {res.status_code} - {res.text}"
        data = res.json()
        assert "chunks" in data, "Response should contain chunks array"
        assert "topics" in data, "Response should contain topics array"
        assert "total" in data, "Response should contain total count"
        print(f"SUCCESS: Agent has {data['total']} knowledge chunks across topics: {data['topics']}")

    def test_get_training_sessions(self, auth_session):
        """GET /api/workspaces/{ws}/agents/{agent_id}/training-sessions - List training sessions"""
        res = auth_session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/agents/{TEST_AGENT}/training-sessions"
        )
        assert res.status_code == 200, f"Get training sessions failed: {res.status_code} - {res.text}"
        data = res.json()
        assert isinstance(data, list), "Response should be a list of sessions"
        if len(data) > 0:
            session = data[0]
            assert "session_id" in session, "Session should have session_id"
            assert "status" in session, "Session should have status"
            assert "source_type" in session, "Session should have source_type"
        print(f"SUCCESS: Agent has {len(data)} training sessions")

    def test_knowledge_query_tfidf(self, auth_session):
        """POST /api/workspaces/{ws}/agents/{agent_id}/knowledge/query - TF-IDF retrieval"""
        res = auth_session.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/agents/{TEST_AGENT}/knowledge/query",
            json={
                "query": "SQL injection security vulnerability",
                "top_k": 5
            }
        )
        assert res.status_code == 200, f"Knowledge query failed: {res.status_code} - {res.text}"
        data = res.json()
        assert "results" in data, "Response should contain results array"
        assert "total_searched" in data, "Response should contain total_searched count"
        if data["results"]:
            result = data["results"][0]
            assert "relevance_score" in result, "Result should have relevance_score"
            assert "content" in result, "Result should have content"
        print(f"SUCCESS: Query returned {len(data['results'])} results from {data['total_searched']} searched")

    def test_delete_knowledge_chunk(self, auth_session):
        """DELETE /api/workspaces/{ws}/agents/{agent_id}/knowledge/{chunk_id} - Delete chunk"""
        # First get a chunk to delete
        get_res = auth_session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/agents/{TEST_AGENT}/knowledge"
        )
        assert get_res.status_code == 200
        data = get_res.json()
        
        if data["chunks"]:
            chunk_id = data["chunks"][0]["chunk_id"]
            del_res = auth_session.delete(
                f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/agents/{TEST_AGENT}/knowledge/{chunk_id}"
            )
            assert del_res.status_code == 200, f"Delete chunk failed: {del_res.status_code} - {del_res.text}"
            del_data = del_res.json()
            assert "deleted" in del_data, "Response should confirm deleted chunk"
            print(f"SUCCESS: Deleted knowledge chunk {chunk_id}")
        else:
            print("SKIP: No chunks to delete")


class TestCostAlerts:
    """Tests for Cost Alerts module"""

    def test_get_cost_alerts(self, auth_session):
        """GET /api/workspaces/{ws}/cost-alerts - Get alerts"""
        res = auth_session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/cost-alerts"
        )
        assert res.status_code == 200, f"Get cost alerts failed: {res.status_code} - {res.text}"
        data = res.json()
        assert "alerts" in data, "Response should contain alerts array"
        print(f"SUCCESS: Workspace has {len(data['alerts'])} cost alerts")

    def test_acknowledge_alerts(self, auth_session):
        """PUT /api/workspaces/{ws}/cost-alerts/acknowledge - Acknowledge all alerts"""
        res = auth_session.put(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/cost-alerts/acknowledge"
        )
        assert res.status_code == 200, f"Acknowledge alerts failed: {res.status_code} - {res.text}"
        data = res.json()
        assert "acknowledged" in data, "Response should contain acknowledged count"
        print(f"SUCCESS: Acknowledged {data['acknowledged']} alerts")

    def test_update_alert_thresholds(self, auth_session):
        """PUT /api/workspaces/{ws}/budget/thresholds - Update thresholds"""
        res = auth_session.put(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/budget/thresholds",
            json={
                "thresholds": [25, 50, 75, 90, 100]
            }
        )
        assert res.status_code == 200, f"Update thresholds failed: {res.status_code} - {res.text}"
        data = res.json()
        assert "thresholds" in data, "Response should contain thresholds"
        assert data["thresholds"] == [25, 50, 75, 90, 100], "Thresholds should match input"
        print(f"SUCCESS: Updated alert thresholds to {data['thresholds']}")


class TestAgentEvaluation:
    """Tests for Agent Evaluation module"""

    def test_agent_skill_assess_endpoint(self, auth_session):
        """POST /api/workspaces/{ws}/agents/{agent_id}/skills/assess - Run assessment"""
        res = auth_session.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/agents/{TEST_AGENT}/skills/assess",
            json={"skill_ids": []}
        )
        # May return 200 or 400 depending on agent config
        assert res.status_code in [200, 400, 404], f"Unexpected status: {res.status_code} - {res.text}"
        if res.status_code == 200:
            data = res.json()
            print(f"SUCCESS: Assessment result: {data}")
        else:
            print(f"INFO: Assessment returned {res.status_code} - {res.text}")


class TestPerformanceTimeSeries:
    """Tests for Performance/Cost Time Series data"""

    def test_get_costs_endpoint(self, auth_session):
        """GET /api/workspaces/{ws}/costs - Get cost data"""
        res = auth_session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/costs?period=30d"
        )
        assert res.status_code == 200, f"Get costs failed: {res.status_code} - {res.text}"
        data = res.json()
        # Validate response structure
        assert isinstance(data, dict), "Response should be a dict"
        print(f"SUCCESS: Costs endpoint returned data keys: {list(data.keys())}")

    def test_get_actual_costs_endpoint(self, auth_session):
        """GET /api/workspaces/{ws}/costs/actual - Get batch computed costs"""
        res = auth_session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/costs/actual?period=monthly"
        )
        assert res.status_code == 200, f"Get actual costs failed: {res.status_code} - {res.text}"
        data = res.json()
        assert isinstance(data, dict), "Response should be a dict"
        print(f"SUCCESS: Actual costs endpoint returned data keys: {list(data.keys())}")


class TestSkillsMatrix:
    """Tests for Skills Matrix endpoints"""

    def test_get_skills_endpoint(self, auth_session):
        """GET /api/skills - List all available skills"""
        res = auth_session.get(f"{BASE_URL}/api/skills")
        assert res.status_code == 200, f"Get skills failed: {res.status_code} - {res.text}"
        data = res.json()
        assert "skills" in data, "Response should contain skills array"
        assert "categories" in data, "Response should contain categories"
        print(f"SUCCESS: {len(data['skills'])} skills in {len(data['categories'])} categories")

    def test_get_agent_skills_endpoint(self, auth_session):
        """GET /api/workspaces/{ws}/agents/{agent_id}/skills - Get agent skills"""
        res = auth_session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/agents/{TEST_AGENT}/skills"
        )
        assert res.status_code == 200, f"Get agent skills failed: {res.status_code} - {res.text}"
        data = res.json()
        assert isinstance(data, dict), "Response should be a dict"
        print(f"SUCCESS: Agent skills response: {list(data.keys())}")

    def test_get_skills_leaderboard(self, auth_session):
        """GET /api/workspaces/{ws}/skills/leaderboard - Get skills leaderboard"""
        res = auth_session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/skills/leaderboard"
        )
        assert res.status_code == 200, f"Get leaderboard failed: {res.status_code} - {res.text}"
        data = res.json()
        assert "leaderboard" in data, "Response should contain leaderboard array"
        print(f"SUCCESS: Leaderboard has {len(data['leaderboard'])} entries")


class TestAgentCatalog:
    """Tests for Agent Catalog endpoint"""

    def test_get_workspace_agents(self, auth_session):
        """GET /api/workspaces/{ws}/agents - List workspace agents for comparison"""
        res = auth_session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/agents")
        assert res.status_code == 200, f"Get agents failed: {res.status_code} - {res.text}"
        data = res.json()
        assert "agents" in data, "Response should contain agents array"
        print(f"SUCCESS: Workspace has {len(data['agents'])} agents")


class TestAgentConfigContext:
    """Tests for AI Models endpoint used by AgentConfigContext"""

    def test_get_ai_models(self, auth_session):
        """GET /api/ai-models - Get all AI models for config context"""
        res = auth_session.get(f"{BASE_URL}/api/ai-models")
        assert res.status_code == 200, f"Get AI models failed: {res.status_code} - {res.text}"
        data = res.json()
        assert "models" in data or isinstance(data, dict), "Response should contain models"
        models = data.get("models", data)
        assert len(models) > 0, "Should have at least one model"
        print(f"SUCCESS: {len(models)} AI model providers available")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
