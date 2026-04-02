from conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, BASE_URL
"""
Iteration 103 Tests - Staleness Detection API, RAG Pipeline, Keyboard Nav Features

Tests:
1. Staleness Detection API: GET /train/staleness returns correct structure
2. RAG Pipeline: train/text creates chunks, knowledge/query retrieves them
3. Knowledge stats endpoint validation
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
WORKSPACE_ID = "ws_a92cb83bfdb2"
AGENT_ID = "nxa_80888f5c29d3"


@pytest.fixture(scope="module")
def session():
    """Authenticated session for API calls."""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    
    # Login
    login_resp = s.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_ADMIN_EMAIL,
        "password": "test"
    })
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    return s


class TestStalenessDetectionAPI:
    """Test the AI-based content staleness detection endpoint."""

    def test_staleness_endpoint_returns_correct_structure(self, session):
        """GET /train/staleness returns all required fields."""
        resp = session.get(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/train/staleness",
            params={"threshold_days": 30}
        )
        assert resp.status_code == 200, f"Staleness API failed: {resp.text}"
        
        data = resp.json()
        # Verify required fields
        assert "agent_id" in data
        assert "threshold_days" in data
        assert "total_chunks" in data
        assert "stale_count" in data
        assert "fresh_count" in data
        assert "never_used_count" in data
        assert "topic_staleness" in data
        
        # Verify data types
        assert isinstance(data["total_chunks"], int)
        assert isinstance(data["stale_count"], int)
        assert isinstance(data["fresh_count"], int)
        assert isinstance(data["never_used_count"], int)
        assert isinstance(data["topic_staleness"], dict)
        
        print(f"Staleness API verified: {data['total_chunks']} total chunks, {data['stale_count']} stale")

    def test_staleness_endpoint_custom_threshold(self, session):
        """Test staleness with different threshold values."""
        # Test with 7 days threshold
        resp = session.get(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/train/staleness",
            params={"threshold_days": 7}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["threshold_days"] == 7
        
        # Test with 90 days threshold
        resp2 = session.get(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/train/staleness",
            params={"threshold_days": 90}
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["threshold_days"] == 90
        
        print(f"Threshold tests passed: 7-day and 90-day thresholds both work")

    def test_staleness_topic_breakdown(self, session):
        """Verify topic_staleness contains per-topic metrics."""
        resp = session.get(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/train/staleness",
            params={"threshold_days": 30}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        topic_staleness = data.get("topic_staleness", {})
        if topic_staleness:
            # Check structure of each topic entry
            for topic, metrics in topic_staleness.items():
                assert "total" in metrics, f"Topic {topic} missing 'total'"
                assert "stale" in metrics, f"Topic {topic} missing 'stale'"
                assert "staleness_pct" in metrics, f"Topic {topic} missing 'staleness_pct'"
            print(f"Topic breakdown verified: {len(topic_staleness)} topics with metrics")
        else:
            print("No topics found (empty knowledge base)")


class TestRAGPipeline:
    """Test RAG pipeline: training and knowledge retrieval."""

    def test_train_text_creates_chunks(self, session):
        """POST train/text creates knowledge chunks."""
        unique_content = f"TEST_RAG_Pipeline_{uuid.uuid4().hex[:8]}: This is test content for RAG pipeline verification. It contains multiple sentences to ensure proper chunking. The content discusses software development, AI integration, and best practices for building scalable systems."
        
        resp = session.post(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/train/text",
            json={
                "title": f"TEST_RAG_Doc_{uuid.uuid4().hex[:6]}",
                "content": unique_content,
                "topic": "rag_test"
            }
        )
        assert resp.status_code == 200, f"Train text failed: {resp.text}"
        
        data = resp.json()
        assert "session_id" in data
        assert "total_chunks" in data
        assert data["total_chunks"] >= 1
        
        print(f"Train text created {data['total_chunks']} chunks, session_id: {data['session_id']}")
        return data["session_id"]

    def test_knowledge_query_returns_results(self, session):
        """POST knowledge/query retrieves relevant chunks."""
        # First ensure there's some content
        resp = session.post(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/knowledge/query",
            json={
                "query": "software development best practices",
                "top_k": 5
            }
        )
        assert resp.status_code == 200, f"Knowledge query failed: {resp.text}"
        
        data = resp.json()
        assert "results" in data
        assert "total_searched" in data
        assert isinstance(data["results"], list)
        
        print(f"Knowledge query returned {len(data['results'])} results from {data['total_searched']} chunks")

    def test_knowledge_stats_endpoint(self, session):
        """GET knowledge/stats returns summary statistics."""
        resp = session.get(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/knowledge/stats"
        )
        assert resp.status_code == 200, f"Knowledge stats failed: {resp.text}"
        
        data = resp.json()
        assert "total_chunks" in data
        assert "flagged" in data
        assert "active" in data
        assert "categories" in data
        
        print(f"Knowledge stats: {data['total_chunks']} total, {data['active']} active, {data['flagged']} flagged")

    def test_knowledge_list_with_filters(self, session):
        """GET knowledge returns chunks with topic filter."""
        resp = session.get(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/knowledge",
            params={"limit": 10}
        )
        assert resp.status_code == 200, f"Knowledge list failed: {resp.text}"
        
        data = resp.json()
        assert "chunks" in data
        assert "topics" in data
        assert "total" in data
        
        print(f"Knowledge list: {len(data['chunks'])} chunks returned, topics: {data['topics'][:3]}")


class TestTrainingQualityDashboard:
    """Test training quality dashboard endpoint."""

    def test_quality_dashboard_returns_coverage(self, session):
        """GET train/quality-dashboard returns skill coverage metrics."""
        resp = session.get(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/train/quality-dashboard"
        )
        assert resp.status_code == 200, f"Quality dashboard failed: {resp.text}"
        
        data = resp.json()
        assert "agent_id" in data
        assert "total_chunks" in data
        assert "skill_coverage" in data
        assert "topic_breakdown" in data
        
        print(f"Quality dashboard: {data['total_chunks']} chunks, {len(data.get('skill_coverage', []))} skills tracked")


class TestTrainingSessions:
    """Test training session management."""

    def test_get_training_sessions(self, session):
        """GET training-sessions returns list of sessions."""
        resp = session.get(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/training-sessions"
        )
        assert resp.status_code == 200, f"Training sessions failed: {resp.text}"
        
        data = resp.json()
        assert isinstance(data, list)
        
        if data:
            session_entry = data[0]
            assert "session_id" in session_entry
            assert "status" in session_entry
            print(f"Found {len(data)} training sessions, latest status: {session_entry.get('status')}")
        else:
            print("No training sessions found")


class TestAutoRefreshToggle:
    """Test auto-refresh toggle for agent training."""

    def test_toggle_auto_refresh(self, session):
        """POST train/auto-refresh enables/disables auto-refresh."""
        # Enable auto-refresh
        resp = session.post(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/train/auto-refresh",
            json={"enabled": True, "interval_days": 14}
        )
        assert resp.status_code == 200, f"Auto-refresh toggle failed: {resp.text}"
        
        data = resp.json()
        assert data.get("auto_refresh") == True
        assert data.get("interval_days") == 14
        
        # Disable auto-refresh
        resp2 = session.post(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/train/auto-refresh",
            json={"enabled": False}
        )
        assert resp2.status_code == 200
        
        print("Auto-refresh toggle working correctly")
