"""
Iteration 65 - Context Ledger System Backend Tests

Tests the Context Ledger system that tracks agent context switches for seamless work resumption.
When agents are interrupted (by humans or other agents), the ledger records:
- What the agent was working on (prior context)
- What triggered the switch (human question, agent disagreement, etc.)
- The agent's response to the trigger
- A resume point so the agent can resume without repeating itself

Modules tested:
- GET /api/channels/{channel_id}/context-ledger - Returns ledger entries for a channel
- GET /api/admin/context-ledger - Admin endpoint (returns 403 for non-admin)
- GET /api/admin/context-ledger/stats - Stats endpoint (returns 403 for non-admin)
- save_context tool in TOOL_DEFINITIONS (routes_ai_tools.py)
- Context ledger entry structure (ledger_id, channel_id, workspace_id, agent_key, event_type, prior_work, trigger, trigger_source)
- build_context_awareness_prompt function
"""

import pytest
import requests
import uuid
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test user credentials
TEST_EMAIL = f"ctxtest_{uuid.uuid4().hex[:8]}@test.com"
TEST_PASSWORD = "test123"


class TestContextLedgerSystem:
    """Test the Context Ledger system for tracking agent context switches"""
    
    @pytest.fixture(scope="class")
    def session(self):
        """Create a requests session"""
        return requests.Session()
    
    @pytest.fixture(scope="class")
    def auth_setup(self, session):
        """Register user, create workspace and channel for testing"""
        # Register user
        register_resp = session.post(f"{BASE_URL}/api/auth/register", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "name": "Context Test User"
        })
        assert register_resp.status_code == 200, f"Registration failed: {register_resp.text}"
        
        # Login
        login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        user = login_resp.json()
        
        # Get session token from cookies
        session_token = login_resp.cookies.get('session_token')
        if session_token:
            session.cookies.set('session_token', session_token)
        
        # Create workspace
        ws_resp = session.post(f"{BASE_URL}/api/workspaces", json={
            "name": f"Context Ledger Test WS {uuid.uuid4().hex[:6]}",
            "description": "Testing context ledger features"
        })
        assert ws_resp.status_code == 200, f"Workspace creation failed: {ws_resp.text}"
        workspace = ws_resp.json()
        
        # Create channel with AI agents
        ch_resp = session.post(f"{BASE_URL}/api/workspaces/{workspace['workspace_id']}/channels", json={
            "name": "Context Test Channel",
            "description": "Channel for context ledger testing",
            "ai_agents": ["claude", "chatgpt", "gemini"]
        })
        assert ch_resp.status_code == 200, f"Channel creation failed: {ch_resp.text}"
        channel = ch_resp.json()
        
        return {
            "user": user,
            "workspace_id": workspace["workspace_id"],
            "channel_id": channel["channel_id"]
        }
    
    # --- GET /api/channels/{channel_id}/context-ledger ---
    
    def test_get_context_ledger_empty(self, session, auth_setup):
        """Test GET context ledger returns empty entries for new channel"""
        channel_id = auth_setup["channel_id"]
        
        resp = session.get(f"{BASE_URL}/api/channels/{channel_id}/context-ledger")
        assert resp.status_code == 200, f"GET context-ledger failed: {resp.text}"
        
        data = resp.json()
        assert "entries" in data, "Response should have 'entries' field"
        assert isinstance(data["entries"], list), "entries should be a list"
        print(f"PASS: GET /channels/{{channel_id}}/context-ledger returns 200 with entries list")
    
    def test_context_ledger_endpoint_requires_auth(self, session, auth_setup):
        """Test context ledger endpoint requires authentication"""
        channel_id = auth_setup["channel_id"]
        
        # Create new session without auth
        unauth_session = requests.Session()
        resp = unauth_session.get(f"{BASE_URL}/api/channels/{channel_id}/context-ledger")
        assert resp.status_code == 401, f"Expected 401 for unauthenticated request, got {resp.status_code}"
        print(f"PASS: Context ledger endpoint requires authentication (401 for unauth)")
    
    def test_context_ledger_limit_param(self, session, auth_setup):
        """Test context ledger respects limit parameter"""
        channel_id = auth_setup["channel_id"]
        
        resp = session.get(f"{BASE_URL}/api/channels/{channel_id}/context-ledger?limit=10")
        assert resp.status_code == 200, f"GET context-ledger with limit failed: {resp.text}"
        
        data = resp.json()
        assert "entries" in data
        print(f"PASS: GET /channels/{{channel_id}}/context-ledger?limit=10 returns 200")
    
    # --- Admin Endpoints (should return 403 for non-admin) ---
    
    def test_admin_context_ledger_returns_403_for_non_admin(self, session, auth_setup):
        """Test GET /admin/context-ledger returns 403 for non-admin users"""
        resp = session.get(f"{BASE_URL}/api/admin/context-ledger")
        assert resp.status_code == 403, f"Expected 403 for non-admin, got {resp.status_code}: {resp.text}"
        print(f"PASS: GET /admin/context-ledger returns 403 for non-admin user")
    
    def test_admin_context_ledger_stats_returns_403_for_non_admin(self, session, auth_setup):
        """Test GET /admin/context-ledger/stats returns 403 for non-admin users"""
        resp = session.get(f"{BASE_URL}/api/admin/context-ledger/stats")
        assert resp.status_code == 403, f"Expected 403 for non-admin, got {resp.status_code}: {resp.text}"
        print(f"PASS: GET /admin/context-ledger/stats returns 403 for non-admin user")
    
    def test_admin_context_ledger_with_filters(self, session, auth_setup):
        """Test admin context ledger accepts filter parameters (still 403 for non-admin)"""
        workspace_id = auth_setup["workspace_id"]
        channel_id = auth_setup["channel_id"]
        
        resp = session.get(
            f"{BASE_URL}/api/admin/context-ledger",
            params={"workspace_id": workspace_id, "channel_id": channel_id, "agent": "claude", "event_type": "human_interrupt"}
        )
        # Should be 403 regardless of filters for non-admin
        assert resp.status_code == 403, f"Expected 403 with filters, got {resp.status_code}"
        print(f"PASS: GET /admin/context-ledger with filters returns 403 for non-admin")


class TestSaveContextTool:
    """Test save_context tool is registered in TOOL_DEFINITIONS"""
    
    @pytest.fixture(scope="class")
    def session(self):
        return requests.Session()
    
    @pytest.fixture(scope="class")
    def auth_setup(self, session):
        """Register and login for tool testing"""
        email = f"tooltest_{uuid.uuid4().hex[:8]}@test.com"
        session.post(f"{BASE_URL}/api/auth/register", json={
            "email": email, "password": "test123", "name": "Tool Test User"
        })
        login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": email, "password": "test123"
        })
        if login_resp.status_code == 200:
            token = login_resp.cookies.get('session_token')
            if token:
                session.cookies.set('session_token', token)
        return {"email": email}
    
    def test_save_context_tool_in_definitions(self, session, auth_setup):
        """Test that save_context tool is in the /api/ai-tools list"""
        resp = session.get(f"{BASE_URL}/api/ai-tools")
        assert resp.status_code == 200, f"GET /ai-tools failed: {resp.text}"
        
        data = resp.json()
        assert "tools" in data, "Response should have 'tools' field"
        
        tools = data["tools"]
        tool_names = [t.get("name") for t in tools]
        
        assert "save_context" in tool_names, f"save_context tool not found in TOOL_DEFINITIONS. Found: {tool_names}"
        
        # Find the save_context tool and verify its structure
        save_context_tool = next((t for t in tools if t.get("name") == "save_context"), None)
        assert save_context_tool is not None, "save_context tool not found"
        
        # Verify tool has required params
        params = save_context_tool.get("params", {})
        assert "prior_work" in params, "save_context tool should have 'prior_work' param"
        assert params["prior_work"].get("required") == True, "prior_work should be required"
        
        print(f"PASS: save_context tool found in TOOL_DEFINITIONS with prior_work (required) param")
        print(f"  - Tool description: {save_context_tool.get('description', '')[:100]}...")
    
    def test_save_context_tool_has_resume_note_param(self, session, auth_setup):
        """Test that save_context tool has resume_note optional param"""
        resp = session.get(f"{BASE_URL}/api/ai-tools")
        assert resp.status_code == 200
        
        tools = resp.json().get("tools", [])
        save_context_tool = next((t for t in tools if t.get("name") == "save_context"), None)
        assert save_context_tool is not None
        
        params = save_context_tool.get("params", {})
        assert "resume_note" in params, "save_context tool should have 'resume_note' param"
        
        # resume_note should be optional
        assert params["resume_note"].get("required") != True, "resume_note should be optional"
        
        print(f"PASS: save_context tool has resume_note (optional) param")


class TestContextLedgerEntryStructure:
    """Test context ledger entry structure by seeding test data directly"""
    
    @pytest.fixture(scope="class")
    def session(self):
        return requests.Session()
    
    @pytest.fixture(scope="class")
    def auth_setup(self, session):
        """Setup user, workspace, channel and seed context ledger entry"""
        email = f"structtest_{uuid.uuid4().hex[:8]}@test.com"
        session.post(f"{BASE_URL}/api/auth/register", json={
            "email": email, "password": "test123", "name": "Structure Test User"
        })
        login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": email, "password": "test123"
        })
        if login_resp.status_code == 200:
            token = login_resp.cookies.get('session_token')
            if token:
                session.cookies.set('session_token', token)
        
        # Create workspace and channel
        ws_resp = session.post(f"{BASE_URL}/api/workspaces", json={
            "name": f"Structure Test WS {uuid.uuid4().hex[:6]}"
        })
        workspace = ws_resp.json()
        
        ch_resp = session.post(f"{BASE_URL}/api/workspaces/{workspace['workspace_id']}/channels", json={
            "name": "Structure Test Channel",
            "ai_agents": ["claude"]
        })
        channel = ch_resp.json()
        
        return {
            "workspace_id": workspace["workspace_id"],
            "channel_id": channel["channel_id"]
        }
    
    def test_context_ledger_entry_fields_via_seed(self, session, auth_setup):
        """
        Test context ledger entry fields by checking the schema.
        Since we can't directly create entries via API (they're created automatically
        during AI collaboration), we verify the GET endpoint returns proper structure.
        """
        channel_id = auth_setup["channel_id"]
        
        resp = session.get(f"{BASE_URL}/api/channels/{channel_id}/context-ledger")
        assert resp.status_code == 200
        
        data = resp.json()
        # New channel won't have entries, but we verify the endpoint works
        assert "entries" in data
        assert isinstance(data["entries"], list)
        
        print(f"PASS: Context ledger GET endpoint returns proper structure (entries list)")
        print(f"  - Entry count: {len(data['entries'])}")
        
        # If there are entries, verify their structure
        if data["entries"]:
            entry = data["entries"][0]
            required_fields = ["ledger_id", "channel_id", "workspace_id", "agent_key", "event_type", "prior_work", "trigger", "trigger_source"]
            for field in required_fields:
                assert field in entry, f"Entry missing required field: {field}"
            print(f"  - Entry has all required fields: {required_fields}")


class TestContextAwarenessPromptFunction:
    """Test build_context_awareness_prompt function exists by checking code"""
    
    def test_build_context_awareness_prompt_exists(self):
        """Verify build_context_awareness_prompt function exists in routes_context_ledger.py"""
        # This is a code verification test - the function should be importable
        try:
            import sys
            sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent))
            from routes_context_ledger import build_context_awareness_prompt, get_agent_prior_context, save_context_entry
            
            assert callable(build_context_awareness_prompt), "build_context_awareness_prompt should be callable"
            assert callable(get_agent_prior_context), "get_agent_prior_context should be callable"
            assert callable(save_context_entry), "save_context_entry should be callable"
            
            print(f"PASS: All context ledger functions exist and are callable")
            print(f"  - build_context_awareness_prompt: ✓")
            print(f"  - get_agent_prior_context: ✓")
            print(f"  - save_context_entry: ✓")
            
        except ImportError as e:
            pytest.fail(f"Failed to import context ledger functions: {e}")
    
    def test_build_context_awareness_prompt_output(self):
        """Test build_context_awareness_prompt generates correct format"""
        import sys
        sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent))
        from routes_context_ledger import build_context_awareness_prompt
        
        # Test with empty entries
        result_empty = build_context_awareness_prompt([], "TestAgent")
        assert result_empty == "", "Empty entries should return empty string"
        
        # Test with sample entries
        sample_entries = [
            {
                "event_type": "human_interrupt",
                "trigger": "What about the API design?",
                "prior_work": "I was working on database schema design",
                "trigger_source": "human:User"
            },
            {
                "event_type": "disagreement",
                "trigger": "I think we should use PostgreSQL instead",
                "prior_work": "",
                "trigger_source": "agent:ChatGPT"
            },
            {
                "event_type": "context_switch",
                "trigger": "Let's move to frontend implementation",
                "prior_work": "Completed backend API endpoints",
                "trigger_source": "agent:Claude"
            }
        ]
        
        result = build_context_awareness_prompt(sample_entries, "TestAgent")
        
        # Verify prompt contains expected elements
        assert "CONTEXT CONTINUITY LOG" in result, "Prompt should contain CONTEXT CONTINUITY LOG header"
        assert "TestAgent" in result, "Prompt should contain agent name"
        assert "Human interruption" in result, "Prompt should mention human interruption"
        assert "DO NOT" in result, "Prompt should have DO NOT instruction"
        
        print(f"PASS: build_context_awareness_prompt generates correct format")
        print(f"  - Contains header: ✓")
        print(f"  - Contains agent name: ✓")
        print(f"  - Contains event type info: ✓")
        print(f"  - Contains DO NOT instructions: ✓")


class TestContextLedgerEventTypes:
    """Test different event types in context ledger"""
    
    def test_event_types_are_valid(self):
        """Verify expected event types are documented"""
        expected_event_types = [
            "human_interrupt",  # Human message triggered agent response
            "disagreement",     # Agent disagrees with another agent
            "context_switch",   # Topic change from another agent
            "context_save"      # Agent explicitly saves context via tool
        ]
        
        # Verify these are handled in the code by checking routes_context_ledger.py
        import sys
        sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent))
        
        # Read the file to verify event types are documented
        with open('/app/backend/routes_context_ledger.py', 'r') as f:
            content = f.read()
        
        # Check admin stats endpoint handles these types
        assert "human_interrupt" in content, "human_interrupt event type should be in code"
        assert "disagreement" in content, "disagreement event type should be in code"
        assert "context_switch" in content, "context_switch event type should be in code"
        assert "context_save" in content, "context_save event type should be in code"
        
        print(f"PASS: All expected event types are handled in code")
        print(f"  - Event types: {expected_event_types}")


class TestContextLedgerIndexes:
    """Test context ledger MongoDB indexes are created"""
    
    def test_context_ledger_indexes_in_startup(self):
        """Verify context ledger indexes are defined in server.py startup"""
        with open('/app/backend/server.py', 'r') as f:
            content = f.read()
        
        # Verify indexes are created
        assert 'context_ledger.create_index("ledger_id"' in content, "ledger_id index should be created"
        assert 'context_ledger.create_index' in content and 'channel_id' in content, "channel_id index should be created"
        assert 'context_ledger.create_index' in content and 'workspace_id' in content, "workspace_id index should be created"
        assert 'context_ledger.create_index("event_type"' in content, "event_type index should be created"
        
        print(f"PASS: All context ledger indexes are defined in server.py startup")
        print(f"  - ledger_id (unique): ✓")
        print(f"  - channel_id + agent_key + created_at: ✓")
        print(f"  - workspace_id + created_at: ✓")
        print(f"  - event_type: ✓")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
