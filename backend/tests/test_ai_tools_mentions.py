"""
Test suite for AI Agent Tools and @Mentions features
- GET /api/ai-tools - tool definitions
- GET /api/channels/{channel_id}/mentionable - mentionable agents
- POST /api/channels/{channel_id}/messages with @mentions parsing
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials provided
TEST_EMAIL = "testmention@test.com"
TEST_PASSWORD = "Test1234!"
TEST_WORKSPACE = "ws_bd1750012bfd"
TEST_CHANNEL = "ch_9988b6543849"  # Channel with agents: claude, chatgpt, gemini


@pytest.fixture(scope="module")
def api_session():
    """Create session and authenticate"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Try to register user first (may already exist)
    try:
        session.post(f"{BASE_URL}/api/auth/register", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "name": "Test Mention User"
        })
    except Exception:
        pass
    
    # Login
    login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    
    if login_resp.status_code != 200:
        pytest.skip(f"Could not authenticate: {login_resp.text}")
    
    return session


class TestAIToolsEndpoint:
    """Tests for GET /api/ai-tools endpoint - returns available tool definitions"""
    
    def test_ai_tools_returns_6_tools(self, api_session):
        """GET /api/ai-tools should return exactly 6 tool definitions"""
        response = api_session.get(f"{BASE_URL}/api/ai-tools")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "tools" in data, "Response should have 'tools' key"
        
        tools = data["tools"]
        assert len(tools) == 6, f"Expected 6 tools, got {len(tools)}"
        
        # Verify expected tool names
        tool_names = [t["name"] for t in tools]
        expected_tools = ["create_project", "create_task", "update_task_status", "list_projects", "list_tasks", "create_artifact"]
        
        for expected in expected_tools:
            assert expected in tool_names, f"Tool '{expected}' not found in tools list"
    
    def test_ai_tools_have_proper_structure(self, api_session):
        """Each tool should have name, description, and params"""
        response = api_session.get(f"{BASE_URL}/api/ai-tools")
        assert response.status_code == 200
        
        tools = response.json()["tools"]
        for tool in tools:
            assert "name" in tool, f"Tool missing 'name': {tool}"
            assert "description" in tool, f"Tool missing 'description': {tool}"
            assert "params" in tool, f"Tool missing 'params': {tool}"
            assert isinstance(tool["params"], dict), f"Tool params should be dict: {tool}"
    
    def test_create_project_tool_params(self, api_session):
        """create_project tool should have name (required) and description (optional) params"""
        response = api_session.get(f"{BASE_URL}/api/ai-tools")
        tools = response.json()["tools"]
        
        create_project = next((t for t in tools if t["name"] == "create_project"), None)
        assert create_project is not None, "create_project tool not found"
        
        params = create_project["params"]
        assert "name" in params, "create_project should have 'name' param"
        assert params["name"]["required"] == True, "name should be required"
        
        assert "description" in params, "create_project should have 'description' param"
        assert params["description"]["required"] == False, "description should be optional"


class TestMentionableEndpoint:
    """Tests for GET /api/channels/{channel_id}/mentionable endpoint"""
    
    def test_mentionable_returns_channel_agents(self, api_session):
        """GET /api/channels/{channel_id}/mentionable returns agents in channel"""
        response = api_session.get(f"{BASE_URL}/api/channels/{TEST_CHANNEL}/mentionable")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "agents" in data, "Response should have 'agents' key"
        
        agents = data["agents"]
        assert isinstance(agents, list), "agents should be a list"
    
    def test_mentionable_includes_everyone(self, api_session):
        """Mentionable list should always include @everyone"""
        response = api_session.get(f"{BASE_URL}/api/channels/{TEST_CHANNEL}/mentionable")
        assert response.status_code == 200
        
        agents = response.json()["agents"]
        agent_keys = [a["key"] for a in agents]
        
        assert "everyone" in agent_keys, "@everyone should be in mentionable list"
        
        everyone = next((a for a in agents if a["key"] == "everyone"), None)
        assert everyone["type"] == "special", "@everyone should have type 'special'"
    
    def test_mentionable_includes_channel_builtin_agents(self, api_session):
        """Channel ch_9988b6543849 should have claude, chatgpt, gemini as mentionable"""
        response = api_session.get(f"{BASE_URL}/api/channels/{TEST_CHANNEL}/mentionable")
        assert response.status_code == 200
        
        agents = response.json()["agents"]
        agent_keys = [a["key"] for a in agents]
        
        # This channel should have these agents
        expected_agents = ["claude", "chatgpt", "gemini"]
        for agent_key in expected_agents:
            assert agent_key in agent_keys, f"Agent '{agent_key}' should be in mentionable list"
    
    def test_mentionable_agents_have_proper_structure(self, api_session):
        """Each mentionable agent should have key, name, type"""
        response = api_session.get(f"{BASE_URL}/api/channels/{TEST_CHANNEL}/mentionable")
        assert response.status_code == 200
        
        agents = response.json()["agents"]
        for agent in agents:
            assert "key" in agent, f"Agent missing 'key': {agent}"
            assert "name" in agent, f"Agent missing 'name': {agent}"
            assert "type" in agent, f"Agent missing 'type': {agent}"
    
    def test_mentionable_builtin_agents_have_correct_names(self, api_session):
        """Builtin agents should have proper capitalized names"""
        response = api_session.get(f"{BASE_URL}/api/channels/{TEST_CHANNEL}/mentionable")
        agents = response.json()["agents"]
        
        for agent in agents:
            if agent["key"] == "claude":
                assert agent["name"] == "Claude", f"Claude should be capitalized, got {agent['name']}"
                assert agent["type"] == "builtin", f"Claude should be builtin type"
            elif agent["key"] == "chatgpt":
                assert agent["name"] == "ChatGPT", f"ChatGPT should be proper case, got {agent['name']}"
            elif agent["key"] == "gemini":
                assert agent["name"] == "Gemini", f"Gemini should be capitalized, got {agent['name']}"
    
    def test_mentionable_nonexistent_channel_returns_empty(self, api_session):
        """Nonexistent channel should return empty agents list"""
        fake_channel = "ch_nonexistent123"
        response = api_session.get(f"{BASE_URL}/api/channels/{fake_channel}/mentionable")
        # Should return 200 with empty list, not 404
        assert response.status_code == 200
        assert response.json()["agents"] == []


class TestMessageMentionParsing:
    """Tests for POST /api/channels/{channel_id}/messages with @mention parsing"""
    
    def test_message_with_claude_mention(self, api_session):
        """Message with @claude should have mentioned_agents containing 'claude'"""
        unique_content = f"TEST_{uuid.uuid4().hex[:8]} Hey @claude, can you help me?"
        
        response = api_session.post(
            f"{BASE_URL}/api/channels/{TEST_CHANNEL}/messages",
            json={"content": unique_content}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        message = response.json()
        assert "mentions" in message, "Message should have 'mentions' field"
        
        mentions = message["mentions"]
        assert mentions["has_mentions"] == True, "has_mentions should be True"
        assert "claude" in mentions["mentioned_agents"], "claude should be in mentioned_agents"
        assert mentions["mention_everyone"] == False, "mention_everyone should be False"
    
    def test_message_with_everyone_mention(self, api_session):
        """Message with @everyone should have mention_everyone=True"""
        unique_content = f"TEST_{uuid.uuid4().hex[:8]} Hey @everyone, look at this!"
        
        response = api_session.post(
            f"{BASE_URL}/api/channels/{TEST_CHANNEL}/messages",
            json={"content": unique_content}
        )
        assert response.status_code == 200
        
        message = response.json()
        mentions = message["mentions"]
        
        assert mentions["mention_everyone"] == True, "mention_everyone should be True for @everyone"
        assert mentions["has_mentions"] == True, "has_mentions should be True"
    
    def test_message_without_mentions(self, api_session):
        """Message without @mentions should have has_mentions=False"""
        unique_content = f"TEST_{uuid.uuid4().hex[:8]} Just a regular message, no mentions here."
        
        response = api_session.post(
            f"{BASE_URL}/api/channels/{TEST_CHANNEL}/messages",
            json={"content": unique_content}
        )
        assert response.status_code == 200
        
        message = response.json()
        mentions = message["mentions"]
        
        assert mentions["has_mentions"] == False, "has_mentions should be False"
        assert mentions["mentioned_agents"] == [], "mentioned_agents should be empty"
        assert mentions["mention_everyone"] == False, "mention_everyone should be False"
    
    def test_message_with_multiple_mentions(self, api_session):
        """Message with @claude @chatgpt should have both in mentioned_agents"""
        unique_content = f"TEST_{uuid.uuid4().hex[:8]} Hey @claude and @chatgpt, collaborate on this!"
        
        response = api_session.post(
            f"{BASE_URL}/api/channels/{TEST_CHANNEL}/messages",
            json={"content": unique_content}
        )
        assert response.status_code == 200
        
        message = response.json()
        mentions = message["mentions"]
        
        assert mentions["has_mentions"] == True
        assert "claude" in mentions["mentioned_agents"], "claude should be mentioned"
        assert "chatgpt" in mentions["mentioned_agents"], "chatgpt should be mentioned"
    
    def test_message_with_invalid_mention(self, api_session):
        """Message with @invalidagent (not in channel) should not be in mentioned_agents"""
        unique_content = f"TEST_{uuid.uuid4().hex[:8]} Hey @perplexity, are you there?"  # perplexity not in this channel
        
        response = api_session.post(
            f"{BASE_URL}/api/channels/{TEST_CHANNEL}/messages",
            json={"content": unique_content}
        )
        assert response.status_code == 200
        
        message = response.json()
        mentions = message["mentions"]
        
        # perplexity is not in the test channel agents, so shouldn't be in mentioned_agents
        assert "perplexity" not in mentions["mentioned_agents"], "Invalid agent should not be in mentioned_agents"
    
    def test_message_mentions_case_insensitive(self, api_session):
        """@CLAUDE and @Claude should both resolve to claude"""
        unique_content = f"TEST_{uuid.uuid4().hex[:8]} Hey @CLAUDE, this is uppercase!"
        
        response = api_session.post(
            f"{BASE_URL}/api/channels/{TEST_CHANNEL}/messages",
            json={"content": unique_content}
        )
        assert response.status_code == 200
        
        message = response.json()
        mentions = message["mentions"]
        
        # Mention parsing is case-insensitive
        assert "claude" in mentions["mentioned_agents"], "claude should be mentioned (case insensitive)"


class TestMessageRetrieval:
    """Tests for GET /api/channels/{channel_id}/messages - verify mentions persisted"""
    
    def test_get_messages_includes_mentions(self, api_session):
        """Retrieved messages should include mentions field"""
        response = api_session.get(f"{BASE_URL}/api/channels/{TEST_CHANNEL}/messages")
        assert response.status_code == 200
        
        messages = response.json()
        assert isinstance(messages, list)
        
        # Find a message with mentions (from our tests)
        for msg in messages:
            if msg.get("mentions"):
                # Verify mentions structure
                mentions = msg["mentions"]
                assert "mentioned_agents" in mentions
                assert "mention_everyone" in mentions
                assert "has_mentions" in mentions
                break


# Cleanup fixture for test messages
@pytest.fixture(scope="module", autouse=True)
def cleanup_test_messages(api_session):
    """Cleanup test messages after test suite completes"""
    yield
    # Note: We're using TEST_ prefix for test data identification
    # In production, you'd want a proper cleanup endpoint
    # For now, test messages remain but are identifiable by TEST_ prefix
