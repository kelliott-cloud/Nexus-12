from conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, BASE_URL
"""
Iteration 108 - Agent Versioning, Training Analytics, Auto-Refresh, Conversation Learning Tests

Features tested:
1. Agent Versioning (CRUD + rollback)
2. Training Analytics (effectiveness, gaps, timeseries)
3. Auto-Refresh Training settings
4. Conversation Learning (thumbs_up triggers knowledge extraction)
"""
import os
import pytest
import requests
import uuid
from datetime import datetime

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
WS_ID = "ws_a92cb83bfdb2"
AGENT_ID = "nxa_80888f5c29d3"
EXISTING_VERSION_ID = "ver_b9b3bed2b16e"


class TestAuthentication:
    """Get auth token for subsequent tests"""

    @pytest.fixture(scope="class")
    def session_token(self):
        """Login and get session token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_ADMIN_EMAIL, "password": "test"},
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        cookies = response.cookies
        token = cookies.get("session_token")
        assert token, "No session_token in response cookies"
        return token


class TestAgentVersioning:
    """Test Agent Versioning CRUD + Rollback endpoints"""

    @pytest.fixture(scope="class")
    def auth_cookies(self):
        """Get auth cookies"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_ADMIN_EMAIL, "password": "test"},
        )
        return {"session_token": response.cookies.get("session_token")}

    def test_list_versions(self, auth_cookies):
        """GET /workspaces/{ws_id}/agents/{agent_id}/versions - list all versions"""
        response = requests.get(
            f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/versions",
            cookies=auth_cookies,
        )
        assert response.status_code == 200, f"List versions failed: {response.text}"
        data = response.json()
        assert "versions" in data, "Response missing 'versions' key"
        assert "total" in data, "Response missing 'total' key"
        assert isinstance(data["versions"], list), "versions should be a list"
        print(f"Found {data['total']} versions")

    def test_create_version(self, auth_cookies):
        """POST /workspaces/{ws_id}/agents/{agent_id}/versions - create version snapshot"""
        unique_label = f"Test Version {uuid.uuid4().hex[:6]}"
        response = requests.post(
            f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/versions",
            json={
                "label": unique_label,
                "description": "Automated test version",
                "include_knowledge": True,
            },
            cookies=auth_cookies,
        )
        assert response.status_code == 200, f"Create version failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "version_id" in data, "Response missing version_id"
        assert data["version_id"].startswith("ver_"), "version_id should start with 'ver_'"
        assert data["label"] == unique_label, "Label mismatch"
        assert "snapshot" in data, "Response missing snapshot"
        assert "knowledge_chunk_ids" in data, "Response missing knowledge_chunk_ids"
        assert "knowledge_count" in data, "Response missing knowledge_count"
        assert data["agent_id"] == AGENT_ID, "Agent ID mismatch"
        
        # Store for cleanup
        return data["version_id"]

    def test_get_version_detail(self, auth_cookies):
        """GET /workspaces/{ws_id}/agents/{agent_id}/versions/{version_id} - get version detail"""
        # First list versions to get a valid version_id
        list_response = requests.get(
            f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/versions",
            cookies=auth_cookies,
        )
        versions = list_response.json().get("versions", [])
        if not versions:
            pytest.skip("No versions available to test get detail")
        
        version_id = versions[0]["version_id"]
        response = requests.get(
            f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/versions/{version_id}",
            cookies=auth_cookies,
        )
        assert response.status_code == 200, f"Get version detail failed: {response.text}"
        data = response.json()
        
        # Validate full snapshot structure
        assert data["version_id"] == version_id
        assert "snapshot" in data, "Detail missing snapshot"
        snapshot = data["snapshot"]
        assert "name" in snapshot, "Snapshot missing name"
        assert "model" in snapshot, "Snapshot missing model"
        print(f"Version {version_id} snapshot: name={snapshot.get('name')}, model={snapshot.get('model')}")

    def test_rollback_to_version(self, auth_cookies):
        """POST /workspaces/{ws_id}/agents/{agent_id}/versions/{version_id}/rollback - rollback"""
        # First create a test version to rollback to
        create_response = requests.post(
            f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/versions",
            json={"label": "Rollback Test", "description": "For rollback test", "include_knowledge": True},
            cookies=auth_cookies,
        )
        assert create_response.status_code == 200
        version_id = create_response.json()["version_id"]
        
        # Perform rollback
        response = requests.post(
            f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/versions/{version_id}/rollback",
            cookies=auth_cookies,
        )
        assert response.status_code == 200, f"Rollback failed: {response.text}"
        data = response.json()
        
        # Validate rollback response
        assert "rolled_back_to" in data, "Response missing rolled_back_to"
        assert data["rolled_back_to"] == version_id
        assert "config_restored" in data, "Response missing config_restored"
        assert isinstance(data["config_restored"], list), "config_restored should be a list"
        assert "knowledge_restored" in data, "Response missing knowledge_restored"
        print(f"Rollback successful: restored {len(data['config_restored'])} config fields, {data['knowledge_restored']} knowledge chunks")

    def test_delete_version(self, auth_cookies):
        """DELETE /workspaces/{ws_id}/agents/{agent_id}/versions/{version_id} - delete version"""
        # Create a version specifically for deletion
        create_response = requests.post(
            f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/versions",
            json={"label": "Delete Test", "description": "Will be deleted", "include_knowledge": False},
            cookies=auth_cookies,
        )
        assert create_response.status_code == 200
        version_id = create_response.json()["version_id"]
        
        # Delete the version
        response = requests.delete(
            f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/versions/{version_id}",
            cookies=auth_cookies,
        )
        assert response.status_code == 200, f"Delete version failed: {response.text}"
        data = response.json()
        assert "deleted" in data, "Response missing 'deleted' key"
        assert data["deleted"] == version_id
        
        # Verify deletion
        get_response = requests.get(
            f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/versions/{version_id}",
            cookies=auth_cookies,
        )
        assert get_response.status_code == 404, "Version should be deleted (404)"
        print(f"Version {version_id} successfully deleted")


class TestTrainingAnalytics:
    """Test Training Analytics endpoints"""

    @pytest.fixture(scope="class")
    def auth_cookies(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_ADMIN_EMAIL, "password": "test"},
        )
        return {"session_token": response.cookies.get("session_token")}

    def test_effectiveness_analytics(self, auth_cookies):
        """GET /workspaces/{ws_id}/agents/{agent_id}/analytics/effectiveness"""
        response = requests.get(
            f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/analytics/effectiveness",
            cookies=auth_cookies,
        )
        assert response.status_code == 200, f"Effectiveness analytics failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "top_performers" in data, "Missing top_performers"
        assert "low_performers" in data, "Missing low_performers"
        assert "total_chunks" in data, "Missing total_chunks"
        assert "chunks_used" in data, "Missing chunks_used"
        
        assert isinstance(data["top_performers"], list)
        assert isinstance(data["low_performers"], list)
        
        # If there are top performers, validate structure
        if data["top_performers"]:
            top = data["top_performers"][0]
            assert "chunk_id" in top, "Top performer missing chunk_id"
            assert "topic" in top, "Top performer missing topic"
            assert "effectiveness_score" in top, "Top performer missing effectiveness_score"
        
        print(f"Effectiveness: {data['total_chunks']} total chunks, {data['chunks_used']} used, {len(data['top_performers'])} top performers")

    def test_gaps_analytics(self, auth_cookies):
        """GET /workspaces/{ws_id}/agents/{agent_id}/analytics/gaps"""
        response = requests.get(
            f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/analytics/gaps",
            cookies=auth_cookies,
        )
        assert response.status_code == 200, f"Gaps analytics failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "gaps" in data, "Missing gaps"
        assert "topic_coverage" in data, "Missing topic_coverage"
        assert "category_distribution" in data, "Missing category_distribution"
        assert "agent_skills" in data, "Missing agent_skills"
        
        assert isinstance(data["gaps"], list)
        assert isinstance(data["topic_coverage"], list)
        assert isinstance(data["category_distribution"], dict)
        
        # Validate gap structure if present
        if data["gaps"]:
            gap = data["gaps"][0]
            assert "skill" in gap, "Gap missing skill"
            assert "type" in gap, "Gap missing type"
            assert "severity" in gap, "Gap missing severity"
            assert "suggestion" in gap, "Gap missing suggestion"
        
        # Validate topic coverage structure
        if data["topic_coverage"]:
            topic = data["topic_coverage"][0]
            assert "topic" in topic, "Topic coverage missing topic"
            assert "chunk_count" in topic, "Topic coverage missing chunk_count"
        
        print(f"Gaps: {len(data['gaps'])} gaps, {len(data['topic_coverage'])} topics covered")

    def test_timeseries_analytics(self, auth_cookies):
        """GET /workspaces/{ws_id}/agents/{agent_id}/analytics/timeseries"""
        response = requests.get(
            f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/analytics/timeseries?days=30",
            cookies=auth_cookies,
        )
        assert response.status_code == 200, f"Timeseries analytics failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "timeline" in data, "Missing timeline"
        assert "period_days" in data, "Missing period_days"
        assert "summary" in data, "Missing summary"
        
        assert isinstance(data["timeline"], list)
        assert data["period_days"] == 30
        
        # Validate summary structure
        summary = data["summary"]
        assert "total_chunks" in summary, "Summary missing total_chunks"
        assert "total_sessions" in summary, "Summary missing total_sessions"
        assert "new_chunks_in_period" in summary, "Summary missing new_chunks_in_period"
        
        # Validate timeline entry structure if present
        if data["timeline"]:
            entry = data["timeline"][0]
            assert "date" in entry, "Timeline entry missing date"
            assert "new_chunks" in entry, "Timeline entry missing new_chunks"
        
        print(f"Timeseries: {len(data['timeline'])} data points, {summary['total_chunks']} total chunks, {summary['total_sessions']} sessions")

    def test_timeseries_with_different_periods(self, auth_cookies):
        """Test timeseries with different day periods (7, 30, 90)"""
        for days in [7, 30, 90]:
            response = requests.get(
                f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/analytics/timeseries?days={days}",
                cookies=auth_cookies,
            )
            assert response.status_code == 200, f"Timeseries failed for {days} days"
            data = response.json()
            assert data["period_days"] == days, f"Period days mismatch for {days}"
            print(f"Timeseries {days}d: OK")


class TestAutoRefresh:
    """Test Auto-Refresh Training settings"""

    @pytest.fixture(scope="class")
    def auth_cookies(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_ADMIN_EMAIL, "password": "test"},
        )
        return {"session_token": response.cookies.get("session_token")}

    def test_get_auto_refresh_settings(self, auth_cookies):
        """GET /workspaces/{ws_id}/agents/{agent_id}/training/auto-refresh"""
        response = requests.get(
            f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/training/auto-refresh",
            cookies=auth_cookies,
        )
        assert response.status_code == 200, f"Get auto-refresh failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "auto_refresh" in data, "Missing auto_refresh"
        assert "interval_days" in data, "Missing interval_days"
        assert isinstance(data["auto_refresh"], bool)
        assert isinstance(data["interval_days"], int)
        
        print(f"Auto-refresh: enabled={data['auto_refresh']}, interval={data['interval_days']} days")

    def test_enable_auto_refresh(self, auth_cookies):
        """PUT /workspaces/{ws_id}/agents/{agent_id}/training/auto-refresh - enable"""
        response = requests.put(
            f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/training/auto-refresh",
            json={"enabled": True, "interval_days": 14},
            cookies=auth_cookies,
        )
        assert response.status_code == 200, f"Enable auto-refresh failed: {response.text}"
        data = response.json()
        
        assert data["auto_refresh"] == True, "auto_refresh should be True"
        assert data["interval_days"] == 14, "interval_days should be 14"
        
        # Verify via GET
        get_response = requests.get(
            f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/training/auto-refresh",
            cookies=auth_cookies,
        )
        get_data = get_response.json()
        assert get_data["auto_refresh"] == True
        print("Auto-refresh enabled with 14 day interval")

    def test_disable_auto_refresh(self, auth_cookies):
        """PUT /workspaces/{ws_id}/agents/{agent_id}/training/auto-refresh - disable"""
        response = requests.put(
            f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/training/auto-refresh",
            json={"enabled": False, "interval_days": 30},
            cookies=auth_cookies,
        )
        assert response.status_code == 200, f"Disable auto-refresh failed: {response.text}"
        data = response.json()
        
        assert data["auto_refresh"] == False, "auto_refresh should be False"
        assert data["interval_days"] == 30, "interval_days should be 30"
        print("Auto-refresh disabled")

    def test_auto_refresh_interval_bounds(self, auth_cookies):
        """Test auto-refresh interval boundary validation"""
        # Test minimum interval (should clamp to 1)
        response = requests.put(
            f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/training/auto-refresh",
            json={"enabled": True, "interval_days": 0},
            cookies=auth_cookies,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["interval_days"] >= 1, "interval_days should be at least 1"
        
        # Test maximum interval (should clamp to 365)
        response = requests.put(
            f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/training/auto-refresh",
            json={"enabled": True, "interval_days": 500},
            cookies=auth_cookies,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["interval_days"] <= 365, "interval_days should be at most 365"
        print("Interval bounds validated")


class TestConversationLearning:
    """Test Conversation Learning via message reactions"""

    @pytest.fixture(scope="class")
    def auth_cookies(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_ADMIN_EMAIL, "password": "test"},
        )
        return {"session_token": response.cookies.get("session_token")}

    def test_react_to_message_thumbs_up(self, auth_cookies):
        """POST /messages/{message_id}/react with thumbs_up"""
        # First get a channel to find messages
        ws_response = requests.get(
            f"{BASE_URL}/api/workspaces/{WS_ID}/channels",
            cookies=auth_cookies,
        )
        assert ws_response.status_code == 200
        channels = ws_response.json()
        
        if not channels:
            pytest.skip("No channels available")
        
        channel_id = channels[0]["channel_id"]
        
        # Get messages from channel
        msg_response = requests.get(
            f"{BASE_URL}/api/channels/{channel_id}/messages",
            cookies=auth_cookies,
        )
        assert msg_response.status_code == 200
        messages = msg_response.json()
        
        # Find an agent message (has agent_key or sender_type is not human)
        agent_message = None
        for msg in messages:
            if msg.get("agent_key") or msg.get("sender_agent") or msg.get("sender_type") != "human":
                agent_message = msg
                break
        
        if not agent_message:
            # Create a test message to react to
            create_response = requests.post(
                f"{BASE_URL}/api/channels/{channel_id}/messages",
                json={"content": "Test message for reaction"},
                cookies=auth_cookies,
            )
            assert create_response.status_code == 200
            agent_message = create_response.json()
        
        message_id = agent_message["message_id"]
        
        # React with thumbs_up
        response = requests.post(
            f"{BASE_URL}/api/messages/{message_id}/react",
            json={"reaction": "thumbs_up"},
            cookies=auth_cookies,
        )
        assert response.status_code == 200, f"React failed: {response.text}"
        data = response.json()
        
        assert "reacted" in data, "Response missing 'reacted'"
        assert data["reacted"] == True
        
        # Check if learning was triggered (may or may not depending on message content)
        if data.get("learned"):
            assert "chunk_id" in data, "Learning happened but missing chunk_id"
            print(f"Conversation learning triggered: chunk_id={data['chunk_id']}")
        else:
            print(f"Reaction recorded, no learning triggered (message may not have agent_key)")

    def test_react_to_message_other_reactions(self, auth_cookies):
        """Test reactions other than thumbs_up don't trigger learning"""
        ws_response = requests.get(
            f"{BASE_URL}/api/workspaces/{WS_ID}/channels",
            cookies=auth_cookies,
        )
        channels = ws_response.json()
        if not channels:
            pytest.skip("No channels available")
        
        channel_id = channels[0]["channel_id"]
        msg_response = requests.get(
            f"{BASE_URL}/api/channels/{channel_id}/messages",
            cookies=auth_cookies,
        )
        messages = msg_response.json()
        if not messages:
            pytest.skip("No messages available")
        
        message_id = messages[0]["message_id"]
        
        # Test thumbs_down reaction (should not trigger learning)
        response = requests.post(
            f"{BASE_URL}/api/messages/{message_id}/react",
            json={"reaction": "thumbs_down"},
            cookies=auth_cookies,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["reacted"] == True
        assert not data.get("learned"), "thumbs_down should not trigger learning"
        print("thumbs_down reaction recorded, no learning (expected)")


class TestExistingVersion:
    """Test operations on the existing version mentioned in requirements"""

    @pytest.fixture(scope="class")
    def auth_cookies(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_ADMIN_EMAIL, "password": "test"},
        )
        return {"session_token": response.cookies.get("session_token")}

    def test_get_existing_version(self, auth_cookies):
        """Get the existing version ver_b9b3bed2b16e"""
        response = requests.get(
            f"{BASE_URL}/api/workspaces/{WS_ID}/agents/{AGENT_ID}/versions/{EXISTING_VERSION_ID}",
            cookies=auth_cookies,
        )
        # May or may not exist depending on test state
        if response.status_code == 200:
            data = response.json()
            assert data["version_id"] == EXISTING_VERSION_ID
            print(f"Existing version found: {data.get('label')}")
        elif response.status_code == 404:
            print(f"Version {EXISTING_VERSION_ID} not found (may have been deleted)")
        else:
            pytest.fail(f"Unexpected status code: {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
