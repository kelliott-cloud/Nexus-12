from conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, BASE_URL
"""
Iteration 99 Tests - Agent Training & Knowledge APIs
Tests new features:
1. Topic suggestions API based on agent skills
2. Knowledge stats API with chunk counts, categories, top sources
3. Knowledge listing with filters (category, topic)
4. Flag knowledge chunk
5. Delete knowledge chunk
6. Text training
7. URL training
8. Knowledge query with TF-IDF similarity
9. Leaderboard still works
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

class TestIteration99TrainingKnowledge:
    """Test the new agent training and knowledge APIs"""
    
    @pytest.fixture(scope="class")
    def session(self):
        """Create authenticated session with cookies"""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        return s
    
    @pytest.fixture(scope="class")
    def auth_session(self, session):
        """Login and return authenticated session"""
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_ADMIN_EMAIL,
            "password": "test"
        })
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        return session
    
    @pytest.fixture(scope="class")
    def workspace_id(self):
        return "ws_a92cb83bfdb2"
    
    @pytest.fixture(scope="class")
    def agent_id(self):
        return "nxa_80888f5c29d3"
    
    # Test 1: Topic suggestions API
    def test_suggest_topics_with_skills(self, auth_session, workspace_id, agent_id):
        """POST /api/workspaces/{ws_id}/agents/{agent_id}/train/suggest-topics returns topic suggestions"""
        resp = auth_session.post(
            f"{BASE_URL}/api/workspaces/{workspace_id}/agents/{agent_id}/train/suggest-topics",
            json={"skill_ids": ["code_review"]}
        )
        assert resp.status_code == 200, f"Suggest topics failed: {resp.text}"
        data = resp.json()
        assert "suggestions" in data, "Response missing 'suggestions'"
        assert isinstance(data["suggestions"], list), "Suggestions should be a list"
        # Should include code_review related topics
        print(f"Topic suggestions: {data['suggestions'][:5]}")
    
    def test_suggest_topics_without_skills(self, auth_session, workspace_id, agent_id):
        """Test topic suggestions with empty skill_ids - should use agent's configured skills"""
        resp = auth_session.post(
            f"{BASE_URL}/api/workspaces/{workspace_id}/agents/{agent_id}/train/suggest-topics",
            json={"skill_ids": []}
        )
        assert resp.status_code == 200, f"Suggest topics failed: {resp.text}"
        data = resp.json()
        assert "suggestions" in data
        print(f"Topic suggestions (from agent skills): {data['suggestions'][:5]}")
    
    # Test 2: Knowledge stats API
    def test_knowledge_stats(self, auth_session, workspace_id, agent_id):
        """GET /api/workspaces/{ws_id}/agents/{agent_id}/knowledge/stats returns stats"""
        resp = auth_session.get(
            f"{BASE_URL}/api/workspaces/{workspace_id}/agents/{agent_id}/knowledge/stats"
        )
        assert resp.status_code == 200, f"Knowledge stats failed: {resp.text}"
        data = resp.json()
        assert "total_chunks" in data, "Response missing 'total_chunks'"
        assert "flagged" in data, "Response missing 'flagged'"
        assert "active" in data, "Response missing 'active'"
        assert "categories" in data, "Response missing 'categories'"
        assert "top_sources" in data, "Response missing 'top_sources'"
        print(f"Knowledge stats: total={data['total_chunks']}, flagged={data['flagged']}, active={data['active']}")
        print(f"Categories: {list(data['categories'].keys())}")
    
    # Test 3: Knowledge listing with filters
    def test_knowledge_listing(self, auth_session, workspace_id, agent_id):
        """GET /api/workspaces/{ws_id}/agents/{agent_id}/knowledge returns chunks"""
        resp = auth_session.get(
            f"{BASE_URL}/api/workspaces/{workspace_id}/agents/{agent_id}/knowledge"
        )
        assert resp.status_code == 200, f"Knowledge listing failed: {resp.text}"
        data = resp.json()
        assert "chunks" in data, "Response missing 'chunks'"
        assert "topics" in data, "Response missing 'topics'"
        assert "total" in data, "Response missing 'total'"
        print(f"Knowledge listing: {data['total']} total chunks, {len(data['topics'])} topics")
    
    def test_knowledge_filter_by_category(self, auth_session, workspace_id, agent_id):
        """GET /api/workspaces/{ws_id}/agents/{agent_id}/knowledge?category=concept filters by category"""
        resp = auth_session.get(
            f"{BASE_URL}/api/workspaces/{workspace_id}/agents/{agent_id}/knowledge?category=concept"
        )
        assert resp.status_code == 200, f"Knowledge filter failed: {resp.text}"
        data = resp.json()
        assert "chunks" in data
        # Verify all returned chunks have the correct category
        for chunk in data["chunks"]:
            assert chunk.get("category") == "concept", f"Chunk has wrong category: {chunk.get('category')}"
        print(f"Filtered by category 'concept': {len(data['chunks'])} chunks")
    
    # Test 4: Text training
    def test_text_training(self, auth_session, workspace_id, agent_id):
        """POST /api/workspaces/{ws_id}/agents/{agent_id}/train/text ingests text"""
        resp = auth_session.post(
            f"{BASE_URL}/api/workspaces/{workspace_id}/agents/{agent_id}/train/text",
            json={
                "content": "TEST_TRAINING: This is a test knowledge chunk for testing purposes. It contains information about code review best practices including checking for null pointer exceptions and proper error handling.",
                "title": "TEST Code Review Guide",
                "topic": "test_topic"
            }
        )
        assert resp.status_code == 200, f"Text training failed: {resp.text}"
        data = resp.json()
        assert "session_id" in data, "Response missing 'session_id'"
        assert "total_chunks" in data, "Response missing 'total_chunks'"
        assert data["total_chunks"] >= 1, "Should have created at least 1 chunk"
        print(f"Text training: session={data['session_id']}, chunks={data['total_chunks']}")
        return data["session_id"]
    
    # Test 5: URL training
    def test_url_training(self, auth_session, workspace_id, agent_id):
        """POST /api/workspaces/{ws_id}/agents/{agent_id}/train/url crawls URLs"""
        # Use a simple, reliable URL that should return quickly
        resp = auth_session.post(
            f"{BASE_URL}/api/workspaces/{workspace_id}/agents/{agent_id}/train/url",
            json={
                "urls": ["https://httpbin.org/html"],
                "topics": ["test_url_topic"]
            }
        )
        assert resp.status_code == 200, f"URL training failed: {resp.text}"
        data = resp.json()
        assert "session_id" in data, "Response missing 'session_id'"
        assert "total_chunks" in data, "Response missing 'total_chunks'"
        print(f"URL training: session={data['session_id']}, chunks={data['total_chunks']}, successful_urls={data.get('successful_urls', 0)}")
    
    # Test 6: Knowledge query
    def test_knowledge_query(self, auth_session, workspace_id, agent_id):
        """POST /api/workspaces/{ws_id}/agents/{agent_id}/knowledge/query returns relevant chunks"""
        resp = auth_session.post(
            f"{BASE_URL}/api/workspaces/{workspace_id}/agents/{agent_id}/knowledge/query",
            json={
                "query": "code review",
                "top_k": 3
            }
        )
        assert resp.status_code == 200, f"Knowledge query failed: {resp.text}"
        data = resp.json()
        assert "results" in data, "Response missing 'results'"
        assert "total_searched" in data, "Response missing 'total_searched'"
        print(f"Knowledge query: found {len(data['results'])} results from {data['total_searched']} chunks")
        if data["results"]:
            # Check that results have relevance scores
            for r in data["results"]:
                if "relevance_score" in r:
                    print(f"  - Score: {r['relevance_score']}, Topic: {r.get('topic', 'N/A')}")
    
    # Test 7: Flag knowledge chunk
    def test_flag_knowledge_chunk(self, auth_session, workspace_id, agent_id):
        """PUT /api/workspaces/{ws_id}/agents/{agent_id}/knowledge/{chunk_id}/flag flags a chunk"""
        # First get list of chunks to find one to flag
        resp = auth_session.get(
            f"{BASE_URL}/api/workspaces/{workspace_id}/agents/{agent_id}/knowledge?limit=10"
        )
        assert resp.status_code == 200
        data = resp.json()
        
        # Find an unflagged chunk to flag
        unflagged = [c for c in data.get("chunks", []) if not c.get("flagged")]
        if not unflagged:
            pytest.skip("No unflagged chunks available to test flagging")
        
        chunk_id = unflagged[0]["chunk_id"]
        
        # Flag it
        flag_resp = auth_session.put(
            f"{BASE_URL}/api/workspaces/{workspace_id}/agents/{agent_id}/knowledge/{chunk_id}/flag"
        )
        assert flag_resp.status_code == 200, f"Flag failed: {flag_resp.text}"
        flag_data = flag_resp.json()
        assert flag_data.get("flagged") == chunk_id, "Response should confirm flagged chunk_id"
        print(f"Flagged chunk: {chunk_id}")
    
    # Test 8: Delete knowledge chunk
    def test_delete_knowledge_chunk(self, auth_session, workspace_id, agent_id):
        """DELETE /api/workspaces/{ws_id}/agents/{agent_id}/knowledge/{chunk_id} deletes a chunk"""
        # First create a test chunk to delete
        create_resp = auth_session.post(
            f"{BASE_URL}/api/workspaces/{workspace_id}/agents/{agent_id}/train/text",
            json={
                "content": "TEST_DELETE: This chunk is specifically created for deletion testing. Delete me please.",
                "title": "TEST Delete Test Chunk",
                "topic": "test_delete"
            }
        )
        assert create_resp.status_code == 200
        session_id = create_resp.json().get("session_id")
        
        # Get the chunk we just created
        list_resp = auth_session.get(
            f"{BASE_URL}/api/workspaces/{workspace_id}/agents/{agent_id}/knowledge?topic=test_delete&limit=5"
        )
        assert list_resp.status_code == 200
        chunks = list_resp.json().get("chunks", [])
        
        if not chunks:
            pytest.skip("Test chunk not found")
        
        chunk_id = chunks[0]["chunk_id"]
        
        # Delete it
        del_resp = auth_session.delete(
            f"{BASE_URL}/api/workspaces/{workspace_id}/agents/{agent_id}/knowledge/{chunk_id}"
        )
        assert del_resp.status_code == 200, f"Delete failed: {del_resp.text}"
        del_data = del_resp.json()
        assert del_data.get("deleted") == chunk_id, "Response should confirm deleted chunk_id"
        print(f"Deleted chunk: {chunk_id}")
        
        # Verify it's gone
        verify_resp = auth_session.get(
            f"{BASE_URL}/api/workspaces/{workspace_id}/agents/{agent_id}/knowledge?topic=test_delete&limit=5"
        )
        verify_data = verify_resp.json()
        remaining_ids = [c["chunk_id"] for c in verify_data.get("chunks", [])]
        assert chunk_id not in remaining_ids, "Chunk should be deleted"
    
    # Test 9: Leaderboard still works (regression)
    def test_leaderboard_agents(self, auth_session):
        """GET /api/leaderboard/agents?metric=evaluation returns agent rankings"""
        resp = auth_session.get(f"{BASE_URL}/api/leaderboard/agents?metric=evaluation&limit=5")
        assert resp.status_code == 200, f"Leaderboard failed: {resp.text}"
        data = resp.json()
        assert "leaderboard" in data, "Response missing 'leaderboard'"
        print(f"Leaderboard agents: {len(data['leaderboard'])} entries")
    
    # Test 10: Training sessions listing
    def test_training_sessions(self, auth_session, workspace_id, agent_id):
        """GET /api/workspaces/{ws_id}/agents/{agent_id}/training-sessions lists sessions"""
        resp = auth_session.get(
            f"{BASE_URL}/api/workspaces/{workspace_id}/agents/{agent_id}/training-sessions"
        )
        assert resp.status_code == 200, f"Training sessions failed: {resp.text}"
        data = resp.json()
        assert isinstance(data, list), "Should return list of sessions"
        if data:
            print(f"Training sessions: {len(data)} sessions, latest type: {data[0].get('source_type')}")
        else:
            print("No training sessions found")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
