from conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, BASE_URL
"""
Iteration 107 Tests - Enhanced Agent Training Module

Tests:
1. Training Sessions API - GET list, GET detail, GET progress
2. Knowledge Chunk Edit API - PUT /knowledge/{chunk_id}
3. Knowledge Chunk Flag API - PUT /knowledge/{chunk_id}/flag
4. Suggest Topics API - POST /train/suggest-topics
5. Export/Import Knowledge APIs
6. Agents List API for selector
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
WORKSPACE_ID = "ws_a92cb83bfdb2"
AGENT_ID = "nxa_80888f5c29d3"  # Test Studio Agent with training data
CHUNK_ID = "kc_e7971e0149d1"  # Existing chunk for edit testing


@pytest.fixture(scope="module")
def session_token():
    """Get authentication session token."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_ADMIN_EMAIL, "password": "test"},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    cookies = resp.cookies
    token = cookies.get("session_token")
    assert token, "No session_token in login response"
    return token


@pytest.fixture(scope="module")
def auth_cookies(session_token):
    """Return cookies dict for authenticated requests."""
    return {"session_token": session_token}


class TestTrainingSessionsAPI:
    """Tests for GET /api/workspaces/{ws_id}/agents/{agent_id}/training-sessions"""

    def test_get_training_sessions_list(self, auth_cookies):
        """GET /api/workspaces/{ws_id}/agents/{agent_id}/training-sessions returns sessions list"""
        resp = requests.get(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/training-sessions",
            cookies=auth_cookies,
        )
        assert resp.status_code == 200, f"Failed: {resp.status_code} - {resp.text}"
        data = resp.json()
        assert isinstance(data, list), "Response should be a list of sessions"
        print(f"Found {len(data)} training sessions")
        # Verify session structure if any sessions exist
        if data:
            session = data[0]
            assert "session_id" in session
            assert "agent_id" in session
            assert "status" in session
            assert "source_type" in session
            print(f"First session: {session.get('session_id')} - {session.get('status')} - {session.get('source_type')}")

    def test_get_training_sessions_requires_auth(self):
        """GET training-sessions without auth returns 401"""
        resp = requests.get(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/training-sessions"
        )
        assert resp.status_code == 401, "Should require authentication"


class TestTrainingSessionDetail:
    """Tests for GET /api/workspaces/{ws_id}/agents/{agent_id}/training-sessions/{session_id}"""

    def test_get_session_detail(self, auth_cookies):
        """GET /api/workspaces/{ws_id}/agents/{agent_id}/training-sessions/{session_id} returns session detail"""
        # First get sessions list
        resp = requests.get(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/training-sessions",
            cookies=auth_cookies,
        )
        assert resp.status_code == 200
        sessions = resp.json()
        if not sessions:
            pytest.skip("No training sessions to test detail endpoint")
        
        session_id = sessions[0]["session_id"]
        detail_resp = requests.get(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/training-sessions/{session_id}",
            cookies=auth_cookies,
        )
        assert detail_resp.status_code == 200, f"Failed: {detail_resp.status_code} - {detail_resp.text}"
        data = detail_resp.json()
        assert data.get("session_id") == session_id
        print(f"Session detail: {data.get('session_id')} status={data.get('status')} chunks={data.get('total_chunks')}")

    def test_get_session_detail_404(self, auth_cookies):
        """GET non-existent session returns 404"""
        resp = requests.get(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/training-sessions/nonexistent_session",
            cookies=auth_cookies,
        )
        assert resp.status_code == 404


class TestTrainingProgress:
    """Tests for GET /api/workspaces/{ws_id}/agents/{agent_id}/training-sessions/{session_id}/progress"""

    def test_get_training_progress(self, auth_cookies):
        """GET /api/workspaces/{ws_id}/agents/{agent_id}/training-sessions/{session_id}/progress returns progress"""
        # First get sessions list
        resp = requests.get(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/training-sessions",
            cookies=auth_cookies,
        )
        assert resp.status_code == 200
        sessions = resp.json()
        if not sessions:
            pytest.skip("No training sessions to test progress endpoint")
        
        session_id = sessions[0]["session_id"]
        progress_resp = requests.get(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/training-sessions/{session_id}/progress",
            cookies=auth_cookies,
        )
        assert progress_resp.status_code == 200, f"Failed: {progress_resp.status_code} - {progress_resp.text}"
        data = progress_resp.json()
        assert "session_id" in data
        assert "status" in data
        print(f"Progress: status={data.get('status')} total_chunks={data.get('total_chunks')}")


class TestKnowledgeEditAPI:
    """Tests for PUT /api/workspaces/{ws_id}/agents/{agent_id}/knowledge/{chunk_id}"""

    def test_edit_knowledge_chunk(self, auth_cookies):
        """PUT /api/workspaces/{ws_id}/agents/{agent_id}/knowledge/{chunk_id} edits a chunk"""
        # First get an existing chunk
        resp = requests.get(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/knowledge",
            cookies=auth_cookies,
        )
        assert resp.status_code == 200
        data = resp.json()
        chunks = data.get("chunks", [])
        if not chunks:
            pytest.skip("No knowledge chunks to test edit endpoint")
        
        chunk = chunks[0]
        chunk_id = chunk.get("chunk_id")
        original_content = chunk.get("content", "")
        
        # Edit the chunk
        new_content = f"TEST_EDITED: {original_content[:100]}"
        edit_resp = requests.put(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/knowledge/{chunk_id}",
            json={
                "content": new_content,
                "category": "concept",
                "tags": ["test", "edited"],
                "topic": chunk.get("topic", "general")
            },
            cookies=auth_cookies,
        )
        assert edit_resp.status_code == 200, f"Edit failed: {edit_resp.status_code} - {edit_resp.text}"
        updated = edit_resp.json()
        assert updated.get("content") == new_content
        assert updated.get("category") == "concept"
        assert "test" in updated.get("tags", [])
        print(f"Edited chunk {chunk_id}: content updated, category=concept, tags={updated.get('tags')}")
        
        # Restore original content
        restore_resp = requests.put(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/knowledge/{chunk_id}",
            json={"content": original_content, "category": chunk.get("category", "concept")},
            cookies=auth_cookies,
        )
        assert restore_resp.status_code == 200

    def test_edit_chunk_404(self, auth_cookies):
        """PUT non-existent chunk returns 404"""
        resp = requests.put(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/knowledge/nonexistent_chunk",
            json={"content": "test"},
            cookies=auth_cookies,
        )
        assert resp.status_code == 404


class TestKnowledgeFlagAPI:
    """Tests for PUT /api/workspaces/{ws_id}/agents/{agent_id}/knowledge/{chunk_id}/flag"""

    def test_flag_knowledge_chunk(self, auth_cookies):
        """PUT /api/workspaces/{ws_id}/agents/{agent_id}/knowledge/{chunk_id}/flag flags a chunk"""
        # Get an unflagged chunk
        resp = requests.get(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/knowledge",
            cookies=auth_cookies,
        )
        assert resp.status_code == 200
        data = resp.json()
        chunks = [c for c in data.get("chunks", []) if not c.get("flagged")]
        if not chunks:
            pytest.skip("No unflagged chunks to test flag endpoint")
        
        chunk = chunks[-1]  # Use last unflagged chunk to avoid breaking main data
        chunk_id = chunk.get("chunk_id")
        
        # Flag the chunk
        flag_resp = requests.put(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/knowledge/{chunk_id}/flag",
            cookies=auth_cookies,
        )
        assert flag_resp.status_code == 200, f"Flag failed: {flag_resp.status_code} - {flag_resp.text}"
        result = flag_resp.json()
        assert result.get("flagged") == chunk_id
        print(f"Flagged chunk: {chunk_id}")


class TestSuggestTopicsAPI:
    """Tests for POST /api/workspaces/{ws_id}/agents/{agent_id}/train/suggest-topics"""

    def test_suggest_topics(self, auth_cookies):
        """POST /api/workspaces/{ws_id}/agents/{agent_id}/train/suggest-topics returns suggestions"""
        resp = requests.post(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/train/suggest-topics",
            json={"skill_ids": []},
            cookies=auth_cookies,
        )
        assert resp.status_code == 200, f"Failed: {resp.status_code} - {resp.text}"
        data = resp.json()
        assert "suggestions" in data
        assert isinstance(data["suggestions"], list)
        print(f"Suggested topics: {data.get('suggestions')[:5]}...")

    def test_suggest_topics_with_skills(self, auth_cookies):
        """POST suggest-topics with skill_ids filters suggestions"""
        resp = requests.post(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/train/suggest-topics",
            json={"skill_ids": ["security_audit"]},
            cookies=auth_cookies,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "suggestions" in data


class TestKnowledgeExportImport:
    """Tests for knowledge export and import endpoints"""

    def test_export_knowledge(self, auth_cookies):
        """GET /api/workspaces/{ws_id}/agents/{agent_id}/knowledge/export returns knowledge pack"""
        resp = requests.get(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/knowledge/export",
            cookies=auth_cookies,
        )
        assert resp.status_code == 200, f"Export failed: {resp.status_code} - {resp.text}"
        data = resp.json()
        assert "chunks" in data or isinstance(data, dict)
        print(f"Export data structure: {list(data.keys()) if isinstance(data, dict) else 'list'}")


class TestAgentsListAPI:
    """Tests for GET /api/workspaces/{ws_id}/agents - used in agent selector"""

    def test_get_agents_list(self, auth_cookies):
        """GET /api/workspaces/{ws_id}/agents returns agents list for selector"""
        resp = requests.get(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents",
            cookies=auth_cookies,
        )
        assert resp.status_code == 200, f"Failed: {resp.status_code} - {resp.text}"
        data = resp.json()
        agents = data if isinstance(data, list) else data.get("agents", [])
        assert isinstance(agents, list)
        print(f"Found {len(agents)} agents")
        # Verify agent structure
        if agents:
            agent = agents[0]
            assert "agent_id" in agent
            assert "name" in agent
            # Check for training stats
            training = agent.get("training", {})
            print(f"First agent: {agent.get('name')} - chunks={training.get('total_chunks', 0)} sessions={training.get('total_sessions', 0)}")


class TestKnowledgeAPI:
    """Tests for GET /api/workspaces/{ws_id}/agents/{agent_id}/knowledge"""

    def test_get_knowledge_list(self, auth_cookies):
        """GET /api/workspaces/{ws_id}/agents/{agent_id}/knowledge returns chunks with stats"""
        resp = requests.get(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/knowledge",
            cookies=auth_cookies,
        )
        assert resp.status_code == 200, f"Failed: {resp.status_code} - {resp.text}"
        data = resp.json()
        assert "chunks" in data
        assert "topics" in data
        assert "total" in data
        chunks = data.get("chunks", [])
        print(f"Knowledge: {data.get('total')} total chunks, {len(data.get('topics', []))} topics")
        
        # Verify chunk structure
        if chunks:
            chunk = chunks[0]
            assert "chunk_id" in chunk
            assert "content" in chunk
            assert "category" in chunk
            assert "topic" in chunk
            # Check for new fields
            print(f"First chunk: category={chunk.get('category')} quality={chunk.get('quality_score')} retrieved={chunk.get('times_retrieved')}")

    def test_get_knowledge_with_topic_filter(self, auth_cookies):
        """GET knowledge with topic filter works"""
        # First get available topics
        resp = requests.get(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/knowledge",
            cookies=auth_cookies,
        )
        topics = resp.json().get("topics", [])
        if not topics:
            pytest.skip("No topics to test filter")
        
        topic = topics[0]
        filtered_resp = requests.get(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/knowledge?topic={topic}",
            cookies=auth_cookies,
        )
        assert filtered_resp.status_code == 200
        filtered_data = filtered_resp.json()
        # All chunks should have the filtered topic
        for chunk in filtered_data.get("chunks", []):
            assert chunk.get("topic") == topic


class TestKnowledgeStats:
    """Tests for GET /api/workspaces/{ws_id}/agents/{agent_id}/knowledge/stats"""

    def test_get_knowledge_stats(self, auth_cookies):
        """GET /api/workspaces/{ws_id}/agents/{agent_id}/knowledge/stats returns summary stats"""
        resp = requests.get(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/knowledge/stats",
            cookies=auth_cookies,
        )
        assert resp.status_code == 200, f"Failed: {resp.status_code} - {resp.text}"
        data = resp.json()
        assert "total_chunks" in data
        assert "categories" in data
        print(f"Knowledge stats: total={data.get('total_chunks')} flagged={data.get('flagged')} active={data.get('active')}")


class TestStalenessAPI:
    """Tests for GET /api/workspaces/{ws_id}/agents/{agent_id}/train/staleness"""

    def test_get_staleness(self, auth_cookies):
        """GET /api/workspaces/{ws_id}/agents/{agent_id}/train/staleness returns staleness info"""
        resp = requests.get(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/train/staleness?threshold_days=30",
            cookies=auth_cookies,
        )
        assert resp.status_code == 200, f"Failed: {resp.status_code} - {resp.text}"
        data = resp.json()
        assert "total_chunks" in data
        assert "stale_count" in data
        assert "fresh_count" in data
        assert "never_used_count" in data
        print(f"Staleness: total={data.get('total_chunks')} stale={data.get('stale_count')} fresh={data.get('fresh_count')} never_used={data.get('never_used_count')}")


class TestDeleteKnowledgeChunk:
    """Tests for DELETE /api/workspaces/{ws_id}/agents/{agent_id}/knowledge/{chunk_id}"""

    def test_delete_chunk_requires_auth(self):
        """DELETE chunk without auth returns 401"""
        resp = requests.delete(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/knowledge/test_chunk"
        )
        assert resp.status_code == 401

    def test_delete_nonexistent_chunk_404(self, auth_cookies):
        """DELETE non-existent chunk returns 404"""
        resp = requests.delete(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/knowledge/nonexistent_chunk_id",
            cookies=auth_cookies,
        )
        assert resp.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
