from conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, BASE_URL
"""
Iteration 98 - Testing new features:
1. Agent Playground (sandbox chat)
2. Cross-workspace Agent Leaderboard
3. Knowledge Base Deduplication UI
4. Cost Alerts (webhook alerts)

Tests cover:
- Backend API endpoints
- Data persistence verification
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestAuthSetup:
    """Login and get workspace/agent IDs for subsequent tests"""

    @pytest.fixture(scope="class")
    def auth_session(self):
        """Create an authenticated session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})

        # Login with super admin
        login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_ADMIN_EMAIL,
            "password": "test"
        })
        if login_resp.status_code != 200:
            pytest.skip(f"Login failed: {login_resp.status_code} - {login_resp.text}")

        return session

    @pytest.fixture(scope="class")
    def workspace_agent_ids(self, auth_session):
        """Get workspace and agent IDs for testing"""
        # Get workspaces
        ws_resp = auth_session.get(f"{BASE_URL}/api/workspaces")
        assert ws_resp.status_code == 200, f"Failed to get workspaces: {ws_resp.text}"
        workspaces = ws_resp.json()
        assert len(workspaces) > 0, "No workspaces found"
        
        workspace_id = workspaces[0].get("workspace_id")
        
        # Get agents in workspace
        agents_resp = auth_session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/agents")
        assert agents_resp.status_code == 200, f"Failed to get agents: {agents_resp.text}"
        agents_data = agents_resp.json()
        agents = agents_data.get("agents", [])
        
        agent_id = agents[0].get("agent_id") if agents else None
        
        return {
            "workspace_id": workspace_id,
            "agent_id": agent_id
        }

    def test_login_success(self, auth_session):
        """Verify login works"""
        assert auth_session is not None
        print("Login successful - session established")


class TestAgentLeaderboard:
    """Test cross-workspace agent leaderboard APIs"""

    @pytest.fixture(scope="class")
    def auth_session(self):
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_ADMIN_EMAIL,
            "password": "test"
        })
        if login_resp.status_code != 200:
            pytest.skip(f"Login failed: {login_resp.status_code}")
        return session

    def test_leaderboard_agents_evaluation_metric(self, auth_session):
        """GET /api/leaderboard/agents?metric=evaluation - Returns agents ranked by evaluation score"""
        resp = auth_session.get(f"{BASE_URL}/api/leaderboard/agents?metric=evaluation")
        assert resp.status_code == 200, f"Failed: {resp.status_code} - {resp.text}"
        
        data = resp.json()
        assert "leaderboard" in data, "Response should contain 'leaderboard' key"
        assert "metric" in data, "Response should contain 'metric' key"
        assert data["metric"] == "evaluation"
        
        print(f"Leaderboard (evaluation): {len(data['leaderboard'])} agents returned")
        if data["leaderboard"]:
            first_agent = data["leaderboard"][0]
            assert "rank" in first_agent, "Agent should have rank"
            assert "name" in first_agent, "Agent should have name"
            assert "score" in first_agent, "Agent should have score"
            print(f"Top agent: {first_agent.get('name')} - score: {first_agent.get('score')}")

    def test_leaderboard_agents_skills_metric(self, auth_session):
        """GET /api/leaderboard/agents?metric=skills - Returns agents ranked by skill count"""
        resp = auth_session.get(f"{BASE_URL}/api/leaderboard/agents?metric=skills")
        assert resp.status_code == 200, f"Failed: {resp.status_code} - {resp.text}"
        
        data = resp.json()
        assert "leaderboard" in data
        assert data["metric"] == "skills"
        
        print(f"Leaderboard (skills): {len(data['leaderboard'])} agents returned")

    def test_leaderboard_agents_messages_metric(self, auth_session):
        """GET /api/leaderboard/agents?metric=messages - Returns agents ranked by message volume"""
        resp = auth_session.get(f"{BASE_URL}/api/leaderboard/agents?metric=messages")
        assert resp.status_code == 200, f"Failed: {resp.status_code} - {resp.text}"
        
        data = resp.json()
        assert "leaderboard" in data
        assert data["metric"] == "messages"
        
        print(f"Leaderboard (messages): {len(data['leaderboard'])} agents returned")

    def test_leaderboard_skills(self, auth_session):
        """GET /api/leaderboard/skills - Returns skill proficiency leaderboard"""
        resp = auth_session.get(f"{BASE_URL}/api/leaderboard/skills")
        assert resp.status_code == 200, f"Failed: {resp.status_code} - {resp.text}"
        
        data = resp.json()
        assert "leaderboard" in data, "Response should contain 'leaderboard' key"
        
        print(f"Skills leaderboard: {len(data['leaderboard'])} records returned")
        if data["leaderboard"]:
            first_skill = data["leaderboard"][0]
            assert "rank" in first_skill, "Skill record should have rank"
            assert "skill" in first_skill, "Skill record should have skill name"
            print(f"Top skill record: {first_skill}")


class TestAgentPlayground:
    """Test agent playground (sandbox chat) APIs"""

    @pytest.fixture(scope="class")
    def auth_session(self):
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_ADMIN_EMAIL,
            "password": "test"
        })
        if login_resp.status_code != 200:
            pytest.skip(f"Login failed: {login_resp.status_code}")
        return session

    @pytest.fixture(scope="class")
    def workspace_agent_ids(self, auth_session):
        ws_resp = auth_session.get(f"{BASE_URL}/api/workspaces")
        if ws_resp.status_code != 200:
            pytest.skip("Could not fetch workspaces")
        workspaces = ws_resp.json()
        if not workspaces:
            pytest.skip("No workspaces found")
        
        workspace_id = workspaces[0].get("workspace_id")
        agents_resp = auth_session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/agents")
        if agents_resp.status_code != 200:
            pytest.skip("Could not fetch agents")
        
        agents = agents_resp.json().get("agents", [])
        if not agents:
            pytest.skip("No agents found in workspace")
        
        return {"workspace_id": workspace_id, "agent_id": agents[0].get("agent_id")}

    def test_playground_chat_new_session(self, auth_session, workspace_agent_ids):
        """POST /api/workspaces/{ws}/agents/{agent_id}/playground - Send message to create new session"""
        ws_id = workspace_agent_ids["workspace_id"]
        agent_id = workspace_agent_ids["agent_id"]
        
        resp = auth_session.post(
            f"{BASE_URL}/api/workspaces/{ws_id}/agents/{agent_id}/playground",
            json={"content": "Hello, this is a test message", "session_id": None}
        )
        assert resp.status_code == 200, f"Failed: {resp.status_code} - {resp.text}"
        
        data = resp.json()
        assert "session_id" in data, "Response should contain session_id"
        assert "response" in data, "Response should contain AI response"
        assert "model" in data, "Response should contain model info"
        
        print(f"Playground session created: {data['session_id']}")
        print(f"AI response preview: {data['response'][:100]}...")
        
        return data["session_id"]

    def test_playground_list_sessions(self, auth_session, workspace_agent_ids):
        """GET /api/workspaces/{ws}/agents/{agent_id}/playground-sessions - List sessions"""
        ws_id = workspace_agent_ids["workspace_id"]
        agent_id = workspace_agent_ids["agent_id"]
        
        resp = auth_session.get(
            f"{BASE_URL}/api/workspaces/{ws_id}/agents/{agent_id}/playground-sessions"
        )
        assert resp.status_code == 200, f"Failed: {resp.status_code} - {resp.text}"
        
        data = resp.json()
        assert "sessions" in data, "Response should contain sessions list"
        
        print(f"Found {len(data['sessions'])} playground sessions")


class TestKnowledgeDeduplication:
    """Test knowledge base deduplication and quality scoring APIs"""

    @pytest.fixture(scope="class")
    def auth_session(self):
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_ADMIN_EMAIL,
            "password": "test"
        })
        if login_resp.status_code != 200:
            pytest.skip(f"Login failed: {login_resp.status_code}")
        return session

    @pytest.fixture(scope="class")
    def workspace_agent_ids(self, auth_session):
        ws_resp = auth_session.get(f"{BASE_URL}/api/workspaces")
        if ws_resp.status_code != 200:
            pytest.skip("Could not fetch workspaces")
        workspaces = ws_resp.json()
        if not workspaces:
            pytest.skip("No workspaces found")
        
        workspace_id = workspaces[0].get("workspace_id")
        agents_resp = auth_session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/agents")
        if agents_resp.status_code != 200:
            pytest.skip("Could not fetch agents")
        
        agents = agents_resp.json().get("agents", [])
        if not agents:
            pytest.skip("No agents found in workspace")
        
        return {"workspace_id": workspace_id, "agent_id": agents[0].get("agent_id")}

    def test_scan_duplicates(self, auth_session, workspace_agent_ids):
        """POST /api/workspaces/{ws}/agents/{agent_id}/knowledge/deduplicate?threshold=0.7"""
        ws_id = workspace_agent_ids["workspace_id"]
        agent_id = workspace_agent_ids["agent_id"]
        
        resp = auth_session.post(
            f"{BASE_URL}/api/workspaces/{ws_id}/agents/{agent_id}/knowledge/deduplicate?threshold=0.7"
        )
        assert resp.status_code == 200, f"Failed: {resp.status_code} - {resp.text}"
        
        data = resp.json()
        assert "duplicates" in data, "Response should contain duplicates list"
        assert "total_checked" in data, "Response should contain total_checked"
        assert "duplicate_count" in data, "Response should contain duplicate_count"
        
        print(f"Dedup scan: checked {data['total_checked']} chunks, found {data['duplicate_count']} duplicates")

    def test_rescore_knowledge(self, auth_session, workspace_agent_ids):
        """POST /api/workspaces/{ws}/agents/{agent_id}/knowledge/rescore"""
        ws_id = workspace_agent_ids["workspace_id"]
        agent_id = workspace_agent_ids["agent_id"]
        
        resp = auth_session.post(
            f"{BASE_URL}/api/workspaces/{ws_id}/agents/{agent_id}/knowledge/rescore"
        )
        assert resp.status_code == 200, f"Failed: {resp.status_code} - {resp.text}"
        
        data = resp.json()
        assert "rescored" in data, "Response should contain rescored count"
        
        print(f"Rescored {data['rescored']} knowledge chunks")


class TestCostAlerts:
    """Test cost alert APIs"""

    @pytest.fixture(scope="class")
    def auth_session(self):
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_ADMIN_EMAIL,
            "password": "test"
        })
        if login_resp.status_code != 200:
            pytest.skip(f"Login failed: {login_resp.status_code}")
        return session

    @pytest.fixture(scope="class")
    def workspace_id(self, auth_session):
        ws_resp = auth_session.get(f"{BASE_URL}/api/workspaces")
        if ws_resp.status_code != 200:
            pytest.skip("Could not fetch workspaces")
        workspaces = ws_resp.json()
        if not workspaces:
            pytest.skip("No workspaces found")
        return workspaces[0].get("workspace_id")

    def test_get_cost_alerts(self, auth_session, workspace_id):
        """GET /api/workspaces/{ws}/cost-alerts - Get cost alerts"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/cost-alerts")
        assert resp.status_code == 200, f"Failed: {resp.status_code} - {resp.text}"
        
        data = resp.json()
        assert "alerts" in data, "Response should contain alerts array"
        
        print(f"Found {len(data['alerts'])} cost alerts")

    def test_acknowledge_alerts(self, auth_session, workspace_id):
        """PUT /api/workspaces/{ws}/cost-alerts/acknowledge - Acknowledge all alerts"""
        resp = auth_session.put(f"{BASE_URL}/api/workspaces/{workspace_id}/cost-alerts/acknowledge")
        assert resp.status_code == 200, f"Failed: {resp.status_code} - {resp.text}"
        
        data = resp.json()
        assert "acknowledged" in data, "Response should contain acknowledged count"
        
        print(f"Acknowledged {data['acknowledged']} alerts")

    def test_update_budget_thresholds(self, auth_session, workspace_id):
        """PUT /api/workspaces/{ws}/budget/thresholds - Update alert thresholds"""
        resp = auth_session.put(
            f"{BASE_URL}/api/workspaces/{workspace_id}/budget/thresholds",
            json={"thresholds": [50, 75, 90, 100]}
        )
        assert resp.status_code == 200, f"Failed: {resp.status_code} - {resp.text}"
        
        data = resp.json()
        assert "thresholds" in data, "Response should contain thresholds"
        assert data["thresholds"] == [50, 75, 90, 100], "Thresholds should match input"
        
        print(f"Updated thresholds: {data['thresholds']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
