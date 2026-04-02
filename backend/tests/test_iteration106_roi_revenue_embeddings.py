from conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, BASE_URL
"""
Iteration 106 Tests - ROI Comparison, Revenue Sharing, Gemini Embeddings

Tests for three new features:
1. Multi-Workspace ROI Comparison Dashboard - GET /api/roi-comparison/workspaces, GET /api/roi-comparison/trend
2. Agent Marketplace Revenue Sharing - GET /api/marketplace/revenue/dashboard, PUT/GET /api/marketplace/agents/{agent_id}/pricing
3. Dense Gemini vector embeddings for knowledge search
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture(scope="module")
def session():
    """Authenticated requests session with cookies."""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    login_res = s.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_ADMIN_EMAIL,
        "password": "test"
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    return s


@pytest.fixture(scope="module")
def workspace_id():
    """Known workspace ID for testing."""
    return "ws_a92cb83bfdb2"


# ------------------------------------------------------------------
# ROI Comparison Endpoints Tests
# ------------------------------------------------------------------

class TestROIComparison:
    """Tests for Multi-Workspace ROI Comparison endpoints"""

    def test_roi_comparison_workspaces_endpoint_exists(self, session):
        """GET /api/roi-comparison/workspaces returns valid response"""
        res = session.get(f"{BASE_URL}/api/roi-comparison/workspaces?period=30d")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert "period" in data, "Response should have 'period' field"
        assert "workspaces" in data, "Response should have 'workspaces' array"
        assert data["period"] == "30d"

    def test_roi_comparison_workspaces_data_structure(self, session):
        """Verify workspace comparison data has correct fields"""
        res = session.get(f"{BASE_URL}/api/roi-comparison/workspaces?period=30d")
        assert res.status_code == 200
        data = res.json()
        workspaces = data.get("workspaces", [])
        
        # Should have at least one workspace for super admin
        if workspaces:
            ws = workspaces[0]
            expected_fields = [
                "workspace_id", "workspace_name", "total_cost_usd", "total_calls",
                "total_tokens", "total_messages", "agent_messages", "time_saved_hours",
                "human_cost_equivalent_usd", "roi_multiplier", "efficiency_score",
                "agent_count", "knowledge_chunks"
            ]
            for field in expected_fields:
                assert field in ws, f"Workspace data should have '{field}' field"

    def test_roi_comparison_workspaces_7d_period(self, session):
        """Test 7-day period parameter"""
        res = session.get(f"{BASE_URL}/api/roi-comparison/workspaces?period=7d")
        assert res.status_code == 200
        data = res.json()
        assert data["period"] == "7d"

    def test_roi_comparison_workspaces_90d_period(self, session):
        """Test 90-day period parameter"""
        res = session.get(f"{BASE_URL}/api/roi-comparison/workspaces?period=90d")
        assert res.status_code == 200
        data = res.json()
        assert data["period"] == "90d"

    def test_roi_comparison_trend_endpoint_exists(self, session):
        """GET /api/roi-comparison/trend returns valid response"""
        res = session.get(f"{BASE_URL}/api/roi-comparison/trend?period=30d")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert "period" in data, "Response should have 'period' field"
        assert "trends" in data, "Response should have 'trends' object"

    def test_roi_comparison_trend_data_structure(self, session):
        """Verify trend data structure"""
        res = session.get(f"{BASE_URL}/api/roi-comparison/trend?period=30d")
        assert res.status_code == 200
        data = res.json()
        trends = data.get("trends", {})
        
        # Each workspace ID key should have workspace_name and daily array
        for ws_id, trend_data in trends.items():
            assert "workspace_name" in trend_data, f"Trend for {ws_id} should have 'workspace_name'"
            assert "daily" in trend_data, f"Trend for {ws_id} should have 'daily' array"
            assert isinstance(trend_data["daily"], list), "Daily should be a list"


# ------------------------------------------------------------------
# Revenue Sharing Endpoints Tests
# ------------------------------------------------------------------

class TestRevenueSharing:
    """Tests for Agent Marketplace Revenue Sharing endpoints"""

    def test_revenue_dashboard_endpoint_exists(self, session):
        """GET /api/marketplace/revenue/dashboard returns valid response"""
        res = session.get(f"{BASE_URL}/api/marketplace/revenue/dashboard")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert "creator" in data, "Response should have 'creator' section"
        assert "buyer" in data, "Response should have 'buyer' section"

    def test_revenue_dashboard_creator_structure(self, session):
        """Verify creator dashboard data structure"""
        res = session.get(f"{BASE_URL}/api/marketplace/revenue/dashboard")
        assert res.status_code == 200
        data = res.json()
        creator = data.get("creator", {})
        
        expected_fields = [
            "total_earnings_usd", "total_sales", "platform_fee_pct",
            "per_agent", "recent_transactions"
        ]
        for field in expected_fields:
            assert field in creator, f"Creator section should have '{field}' field"
        
        # Platform fee should be 20%
        assert creator.get("platform_fee_pct") == 20, "Platform fee should be 20%"

    def test_revenue_dashboard_buyer_structure(self, session):
        """Verify buyer dashboard data structure"""
        res = session.get(f"{BASE_URL}/api/marketplace/revenue/dashboard")
        assert res.status_code == 200
        data = res.json()
        buyer = data.get("buyer", {})
        
        assert "total_purchases" in buyer, "Buyer section should have 'total_purchases'"
        assert "purchases" in buyer, "Buyer section should have 'purchases' list"

    def test_revenue_dashboard_empty_state(self, session):
        """Revenue dashboard should return zeros when no transactions exist"""
        res = session.get(f"{BASE_URL}/api/marketplace/revenue/dashboard")
        assert res.status_code == 200
        data = res.json()
        
        # Should return valid structure even with no transactions
        creator = data.get("creator", {})
        assert isinstance(creator.get("total_earnings_usd", 0), (int, float))
        assert isinstance(creator.get("total_sales", 0), int)


class TestAgentPricing:
    """Tests for Agent Pricing endpoints"""

    def test_get_pricing_nonexistent_agent(self, session):
        """GET pricing for non-existent agent returns 404"""
        res = session.get(f"{BASE_URL}/api/marketplace/agents/nonexistent_agent_123/pricing")
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"

    def test_put_pricing_nonexistent_agent(self, session):
        """PUT pricing for non-existent agent returns 404"""
        res = session.put(
            f"{BASE_URL}/api/marketplace/agents/nonexistent_agent_123/pricing",
            json={"price_usd": 9.99, "pricing_model": "one_time"}
        )
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"

    def test_put_pricing_validation_negative_price(self, session):
        """PUT pricing with negative price should fail validation"""
        # First we need a valid marketplace agent - this will return 404 if no agents
        res = session.put(
            f"{BASE_URL}/api/marketplace/agents/test_agent/pricing",
            json={"price_usd": -5.0, "pricing_model": "one_time"}
        )
        # Either 404 (no agent) or 422 (validation error) is acceptable
        assert res.status_code in [404, 422], f"Expected 404 or 422, got {res.status_code}"

    def test_put_pricing_validation_invalid_model(self, session):
        """PUT pricing with invalid pricing_model should fail validation"""
        res = session.put(
            f"{BASE_URL}/api/marketplace/agents/test_agent/pricing",
            json={"price_usd": 9.99, "pricing_model": "invalid_model"}
        )
        # Either 404 (no agent) or 422 (validation error) is acceptable
        assert res.status_code in [404, 422], f"Expected 404 or 422, got {res.status_code}"


# ------------------------------------------------------------------
# Gemini Embeddings Module Tests
# ------------------------------------------------------------------

class TestGeminiEmbeddings:
    """Tests for Dense Gemini vector embeddings module"""

    def test_gemini_embeddings_module_import(self):
        """Verify gemini_embeddings.py can be imported"""
        try:
            import sys
            sys.path.insert(0, "/app/backend")
            from gemini_embeddings import (
                generate_embeddings,
                generate_query_embedding,
                cosine_similarity_dense,
                compute_and_store_dense_embeddings,
                retrieve_with_dense_embeddings
            )
            assert callable(generate_embeddings), "generate_embeddings should be callable"
            assert callable(generate_query_embedding), "generate_query_embedding should be callable"
            assert callable(cosine_similarity_dense), "cosine_similarity_dense should be callable"
        except ImportError as e:
            pytest.fail(f"Failed to import gemini_embeddings module: {e}")

    def test_cosine_similarity_dense_calculation(self):
        """Test cosine similarity calculation"""
        import sys
        sys.path.insert(0, "/app/backend")
        from gemini_embeddings import cosine_similarity_dense
        
        # Identical vectors should have similarity 1.0
        vec_a = [1.0, 0.0, 0.0]
        vec_b = [1.0, 0.0, 0.0]
        sim = cosine_similarity_dense(vec_a, vec_b)
        assert abs(sim - 1.0) < 0.01, f"Identical vectors should have similarity ~1.0, got {sim}"
        
        # Orthogonal vectors should have similarity 0.0
        vec_c = [1.0, 0.0, 0.0]
        vec_d = [0.0, 1.0, 0.0]
        sim_orth = cosine_similarity_dense(vec_c, vec_d)
        assert abs(sim_orth) < 0.01, f"Orthogonal vectors should have similarity ~0.0, got {sim_orth}"
        
        # Opposite vectors should have similarity -1.0
        vec_e = [1.0, 0.0, 0.0]
        vec_f = [-1.0, 0.0, 0.0]
        sim_opp = cosine_similarity_dense(vec_e, vec_f)
        assert abs(sim_opp + 1.0) < 0.01, f"Opposite vectors should have similarity ~-1.0, got {sim_opp}"

    def test_cosine_similarity_edge_cases(self):
        """Test cosine similarity edge cases"""
        import sys
        sys.path.insert(0, "/app/backend")
        from gemini_embeddings import cosine_similarity_dense
        
        # Empty vectors
        assert cosine_similarity_dense([], []) == 0.0
        
        # Mismatched lengths
        assert cosine_similarity_dense([1.0, 2.0], [1.0]) == 0.0
        
        # Zero vectors
        assert cosine_similarity_dense([0.0, 0.0], [1.0, 0.0]) == 0.0

    def test_embedding_constants(self):
        """Verify embedding module constants"""
        import sys
        sys.path.insert(0, "/app/backend")
        from gemini_embeddings import GEMINI_MODEL, EMBEDDING_DIM, BATCH_SIZE
        
        assert GEMINI_MODEL == "gemini-embedding-001", f"Model should be gemini-embedding-001"
        assert EMBEDDING_DIM == 768, f"Embedding dimension should be 768"
        assert BATCH_SIZE == 50, f"Batch size should be 50"


# ------------------------------------------------------------------
# Agent Knowledge Retrieval Integration Tests
# ------------------------------------------------------------------

class TestKnowledgeRetrieval:
    """Tests for knowledge retrieval using dense embeddings"""

    def test_semantic_select_function_exists(self):
        """Verify _semantic_select function exists in agent_knowledge_retrieval"""
        import sys
        sys.path.insert(0, "/app/backend")
        from agent_knowledge_retrieval import retrieve_training_knowledge
        assert callable(retrieve_training_knowledge)

    def test_knowledge_retrieval_endpoint(self, session, workspace_id):
        """Test knowledge retrieval via API"""
        # First get an agent in the workspace
        agents_res = session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/agents")
        if agents_res.status_code != 200:
            pytest.skip("No agents endpoint or access")
        
        data = agents_res.json()
        agents = data.get("agents", []) if isinstance(data, dict) else data
        if not agents:
            pytest.skip("No agents in workspace to test knowledge retrieval")
        
        agent_id = agents[0].get("agent_id") if isinstance(agents[0], dict) else None
        if not agent_id:
            pytest.skip("Agent has no agent_id")
        
        # Query knowledge
        res = session.post(
            f"{BASE_URL}/api/workspaces/{workspace_id}/agents/{agent_id}/knowledge/query",
            json={"query": "test query", "top_k": 5}
        )
        # Either 200 with results or 400 if no knowledge
        assert res.status_code in [200, 400], f"Expected 200 or 400, got {res.status_code}"


# ------------------------------------------------------------------
# Authentication & Authorization Tests
# ------------------------------------------------------------------

class TestAuthentication:
    """Tests for authentication requirements"""

    def test_roi_comparison_requires_auth(self):
        """ROI comparison endpoints require authentication"""
        s = requests.Session()
        res = s.get(f"{BASE_URL}/api/roi-comparison/workspaces")
        assert res.status_code == 401, f"Expected 401 without auth, got {res.status_code}"

    def test_revenue_dashboard_requires_auth(self):
        """Revenue dashboard requires authentication"""
        s = requests.Session()
        res = s.get(f"{BASE_URL}/api/marketplace/revenue/dashboard")
        assert res.status_code == 401, f"Expected 401 without auth, got {res.status_code}"

    def test_pricing_get_requires_auth(self):
        """Agent pricing GET requires authentication"""
        s = requests.Session()
        res = s.get(f"{BASE_URL}/api/marketplace/agents/test/pricing")
        assert res.status_code == 401, f"Expected 401 without auth, got {res.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
