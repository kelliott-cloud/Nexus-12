"""
P1 Features Testing - Iteration 24
Tests for 3 new features:
1. Workflow Engine Phase 2 - Merge node execution (cannot fully test without AI), execution logs endpoint
2. Agent-to-Agent Structured Handoffs - Create, List, Acknowledge
3. Project Memory & Knowledge Base - CRUD with AI tool integration
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from review request
TEST_EMAIL = "testmention@test.com"
TEST_PASSWORD = "Test1234!"
WORKSPACE_ID = "ws_bd1750012bfd"
CHANNEL_ID = "ch_9988b6543849"
EXISTING_HANDOFF_ID = "ho_1366eac59e56"


@pytest.fixture(scope="module")
def api_client():
    """Shared session with auth cookies"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    # Login to get cookie
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL, "password": TEST_PASSWORD
    })
    if resp.status_code != 200:
        pytest.skip(f"Login failed: {resp.status_code} - {resp.text}")
    return session


# ============ 1. WORKFLOW EXECUTION LOGS ENDPOINT ============

class TestWorkflowExecutionLogs:
    """Test GET /api/workflow-runs/{run_id}/logs endpoint"""

    def test_get_execution_logs_existing_run(self, api_client):
        """Get execution logs for any existing workflow run"""
        # First get list of workflow runs
        wf_res = api_client.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/workflows")
        if wf_res.status_code != 200:
            pytest.skip("Cannot list workflows")
        workflows = wf_res.json()
        
        # Look for any run in any workflow
        for wf in workflows[:5]:  # Check up to 5 workflows
            runs_res = api_client.get(f"{BASE_URL}/api/workflows/{wf['workflow_id']}/runs")
            if runs_res.status_code == 200 and runs_res.json():
                run_id = runs_res.json()[0]["run_id"]
                logs_res = api_client.get(f"{BASE_URL}/api/workflow-runs/{run_id}/logs")
                assert logs_res.status_code == 200, f"Expected 200, got {logs_res.status_code}"
                data = logs_res.json()
                # Validate response structure
                assert "run_id" in data
                assert "status" in data
                assert "logs" in data
                assert isinstance(data["logs"], list)
                assert "total_tokens" in data
                assert "total_cost_usd" in data
                assert "total_duration_ms" in data
                print(f"✓ Logs endpoint returned {len(data['logs'])} log entries for run {run_id}")
                return
        pytest.skip("No workflow runs found to test logs endpoint")

    def test_get_logs_nonexistent_run(self, api_client):
        """Test 404 for non-existent run"""
        resp = api_client.get(f"{BASE_URL}/api/workflow-runs/wrun_nonexistent123/logs")
        assert resp.status_code == 404
        print("✓ 404 returned for non-existent run")

    def test_logs_response_structure(self, api_client):
        """Validate logs array item structure (node metadata)"""
        # Find any run with executions
        wf_res = api_client.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/workflows")
        if wf_res.status_code != 200:
            pytest.skip("Cannot list workflows")
        workflows = wf_res.json()
        
        for wf in workflows[:5]:
            runs_res = api_client.get(f"{BASE_URL}/api/workflows/{wf['workflow_id']}/runs")
            if runs_res.status_code == 200 and runs_res.json():
                run_id = runs_res.json()[0]["run_id"]
                logs_res = api_client.get(f"{BASE_URL}/api/workflow-runs/{run_id}/logs")
                if logs_res.status_code == 200:
                    data = logs_res.json()
                    if data["logs"]:
                        log_entry = data["logs"][0]
                        # Validate node metadata fields
                        expected_fields = ["exec_id", "node_id", "node_label", "node_type", "status", "attempt", "started_at"]
                        for field in expected_fields:
                            assert field in log_entry, f"Missing field: {field}"
                        print(f"✓ Log entry has required fields: {list(log_entry.keys())}")
                        return
        pytest.skip("No workflow run with log entries found")


# ============ 2. AGENT-TO-AGENT HANDOFFS ============

class TestAgentHandoffs:
    """Test handoff creation, listing, and acknowledgment"""
    
    def test_create_handoff(self, api_client):
        """POST /api/channels/{id}/handoffs - creates handoff + posts message"""
        handoff_data = {
            "channel_id": CHANNEL_ID,
            "from_agent": "claude",
            "to_agent": "chatgpt",
            "context_type": "analysis",
            "title": "TEST_Handoff_Analysis_Results",
            "content": "Here is the analysis from my review. Key findings:\n1. Performance bottleneck identified\n2. Solution proposed",
            "metadata": {"test": True}
        }
        resp = api_client.post(f"{BASE_URL}/api/channels/{CHANNEL_ID}/handoffs", json=handoff_data)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Validate handoff structure
        assert "handoff_id" in data
        assert data["handoff_id"].startswith("ho_")
        assert data["from_agent"] == "claude"
        assert data["to_agent"] == "chatgpt"
        assert data["context_type"] == "analysis"
        assert data["title"] == "TEST_Handoff_Analysis_Results"
        assert data["status"] == "pending"
        print(f"✓ Handoff created: {data['handoff_id']}")
        # Store for cleanup
        TestAgentHandoffs.created_handoff_id = data["handoff_id"]

    def test_list_handoffs(self, api_client):
        """GET /api/channels/{id}/handoffs - lists all handoffs"""
        resp = api_client.get(f"{BASE_URL}/api/channels/{CHANNEL_ID}/handoffs")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} handoffs in channel")
        
        # Check existing handoff mentioned in context is present
        handoff_ids = [h["handoff_id"] for h in data]
        assert EXISTING_HANDOFF_ID in handoff_ids, f"Existing handoff {EXISTING_HANDOFF_ID} not found"
        print(f"✓ Existing handoff {EXISTING_HANDOFF_ID} found in list")

    def test_list_handoffs_returns_all_fields(self, api_client):
        """Verify handoff list returns all expected fields"""
        resp = api_client.get(f"{BASE_URL}/api/channels/{CHANNEL_ID}/handoffs")
        assert resp.status_code == 200
        data = resp.json()
        if data:
            handoff = data[0]
            expected_fields = ["handoff_id", "channel_id", "from_agent", "to_agent", "context_type", "title", "content", "status", "created_at"]
            for field in expected_fields:
                assert field in handoff, f"Missing field: {field}"
            print(f"✓ Handoff list items have all required fields")

    def test_acknowledge_handoff(self, api_client):
        """PUT /api/handoffs/{id}/acknowledge - marks as acknowledged"""
        # Use the existing handoff or the one we just created
        handoff_id = getattr(TestAgentHandoffs, 'created_handoff_id', EXISTING_HANDOFF_ID)
        resp = api_client.put(f"{BASE_URL}/api/handoffs/{handoff_id}/acknowledge")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["status"] == "acknowledged"
        print(f"✓ Handoff {handoff_id} acknowledged")

    def test_acknowledge_nonexistent_handoff(self, api_client):
        """Test 404 for non-existent handoff"""
        resp = api_client.put(f"{BASE_URL}/api/handoffs/ho_nonexistent123/acknowledge")
        assert resp.status_code == 404
        print("✓ 404 returned for non-existent handoff")

    def test_handoff_message_posted(self, api_client):
        """Verify handoff creates a message with sender_type=handoff"""
        resp = api_client.get(f"{BASE_URL}/api/channels/{CHANNEL_ID}/messages")
        assert resp.status_code == 200
        messages = resp.json()
        
        # Find handoff messages
        handoff_msgs = [m for m in messages if m.get("sender_type") == "handoff"]
        assert len(handoff_msgs) > 0, "No handoff messages found"
        print(f"✓ Found {len(handoff_msgs)} handoff messages in channel")
        
        # Verify handoff message structure
        msg = handoff_msgs[0]
        assert "handoff" in msg, "Handoff message missing 'handoff' object"
        assert "from_agent" in msg["handoff"]
        assert "to_agent" in msg["handoff"]
        print(f"✓ Handoff message has embedded handoff object")


# ============ 3. KNOWLEDGE BASE / MEMORY ============

class TestKnowledgeBaseMemory:
    """Test workspace memory CRUD operations"""

    def test_create_memory_entry(self, api_client):
        """POST /api/workspaces/{ws}/memory - creates new entry"""
        memory_data = {
            "key": "TEST_api_documentation",
            "value": "The API uses RESTful patterns with JSON responses. Authentication via JWT tokens.",
            "category": "reference",
            "tags": ["api", "docs", "test"]
        }
        resp = api_client.post(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/memory", json=memory_data)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert "memory_id" in data
        assert data["memory_id"].startswith("mem_")
        assert data["key"] == "TEST_api_documentation"
        assert data["value"] == memory_data["value"]
        assert data["category"] == "reference"
        assert data["version"] == 1
        print(f"✓ Memory entry created: {data['memory_id']}")
        TestKnowledgeBaseMemory.created_memory_id = data["memory_id"]

    def test_create_memory_upsert_existing_key(self, api_client):
        """POST with existing key updates instead of creating duplicate (upsert)"""
        # The context says a memory with key='project_stack' already exists
        upsert_data = {
            "key": "project_stack",
            "value": "React, FastAPI, MongoDB - Updated via test",
            "category": "context"
        }
        resp = api_client.post(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/memory", json=upsert_data)
        assert resp.status_code == 200
        data = resp.json()
        # If it was updated, version should be > 1
        assert data["key"] == "project_stack"
        # Value should be updated
        assert "Updated via test" in data["value"]
        print(f"✓ Memory upsert worked: version={data.get('version', 1)}")

    def test_list_memory_entries(self, api_client):
        """GET /api/workspaces/{ws}/memory - list all entries"""
        resp = api_client.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/memory")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "entries" in data
        assert "total" in data
        assert isinstance(data["entries"], list)
        print(f"✓ Listed {len(data['entries'])} memory entries (total: {data['total']})")

    def test_list_memory_with_search(self, api_client):
        """GET /api/workspaces/{ws}/memory?search=api - search filter"""
        resp = api_client.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/memory?search=api")
        assert resp.status_code == 200
        data = resp.json()
        
        # Should find our test entry or any with 'api' in key/value
        entries = data["entries"]
        if entries:
            # Verify search relevance
            found_match = any("api" in e.get("key", "").lower() or "api" in e.get("value", "").lower() for e in entries)
            assert found_match, "Search results don't contain 'api'"
            print(f"✓ Search filter working: found {len(entries)} entries matching 'api'")
        else:
            print("✓ Search returned empty (no matches)")

    def test_list_memory_with_category_filter(self, api_client):
        """GET /api/workspaces/{ws}/memory?category=reference - category filter"""
        resp = api_client.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/memory?category=reference")
        assert resp.status_code == 200
        data = resp.json()
        
        for entry in data["entries"]:
            assert entry["category"] == "reference"
        print(f"✓ Category filter working: {len(data['entries'])} entries in 'reference'")

    def test_update_memory_entry(self, api_client):
        """PUT /api/memory/{id} - updates entry, increments version"""
        memory_id = getattr(TestKnowledgeBaseMemory, 'created_memory_id', None)
        if not memory_id:
            # Create one first
            create_resp = api_client.post(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/memory", json={
                "key": "TEST_update_target",
                "value": "Original value",
                "category": "general"
            })
            memory_id = create_resp.json()["memory_id"]
            TestKnowledgeBaseMemory.created_memory_id = memory_id
        
        update_data = {
            "value": "Updated value with more details",
            "category": "insight",
            "tags": ["updated", "test"]
        }
        resp = api_client.put(f"{BASE_URL}/api/memory/{memory_id}", json=update_data)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert data["value"] == "Updated value with more details"
        assert data["category"] == "insight"
        assert data["version"] >= 2, f"Expected version >= 2, got {data.get('version')}"
        print(f"✓ Memory updated: version={data['version']}")

    def test_update_nonexistent_memory(self, api_client):
        """Test 404 for updating non-existent memory"""
        resp = api_client.put(f"{BASE_URL}/api/memory/mem_nonexistent123", json={"value": "test"})
        assert resp.status_code == 404
        print("✓ 404 returned for non-existent memory")

    def test_delete_memory_entry(self, api_client):
        """DELETE /api/memory/{id} - deletes entry"""
        # Create a test entry to delete
        create_resp = api_client.post(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/memory", json={
            "key": "TEST_delete_me",
            "value": "This will be deleted",
            "category": "general"
        })
        assert create_resp.status_code == 200
        memory_id = create_resp.json()["memory_id"]
        
        # Delete it
        resp = api_client.delete(f"{BASE_URL}/api/memory/{memory_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data
        print(f"✓ Memory entry deleted: {memory_id}")
        
        # Verify deletion
        get_resp = api_client.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/memory?search=TEST_delete_me")
        entries = get_resp.json().get("entries", [])
        assert not any(e.get("memory_id") == memory_id for e in entries), "Entry still exists after delete"
        print("✓ Verified entry no longer in list")

    def test_delete_nonexistent_memory(self, api_client):
        """Test 404 for deleting non-existent memory"""
        resp = api_client.delete(f"{BASE_URL}/api/memory/mem_nonexistent123")
        assert resp.status_code == 404
        print("✓ 404 returned for non-existent memory")

    def test_get_memory_categories(self, api_client):
        """GET /api/memory/categories - returns 5 categories"""
        resp = api_client.get(f"{BASE_URL}/api/memory/categories")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        
        assert "categories" in data
        categories = data["categories"]
        assert len(categories) == 5, f"Expected 5 categories, got {len(categories)}"
        
        # Verify category structure
        expected_keys = ["general", "insight", "decision", "reference", "context"]
        category_keys = [c["key"] for c in categories]
        for key in expected_keys:
            assert key in category_keys, f"Missing category: {key}"
        
        # Verify each category has required fields
        for cat in categories:
            assert "key" in cat
            assert "name" in cat
            assert "description" in cat
        print(f"✓ Got {len(categories)} categories: {category_keys}")


# ============ 4. AI TOOLS ENDPOINT ============

class TestAIToolsEndpoint:
    """Test /api/ai-tools returns the 9 tools including new ones"""

    def test_ai_tools_returns_9_tools(self, api_client):
        """GET /api/ai-tools - returns 9 tools (including new 3)"""
        resp = api_client.get(f"{BASE_URL}/api/ai-tools")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        
        assert "tools" in data
        tools = data["tools"]
        assert len(tools) == 9, f"Expected 9 tools, got {len(tools)}"
        
        tool_names = [t["name"] for t in tools]
        print(f"✓ Available tools: {tool_names}")
        
        # Verify the 3 new tools are present
        new_tools = ["save_to_memory", "read_memory", "handoff_to_agent"]
        for tool in new_tools:
            assert tool in tool_names, f"Missing new tool: {tool}"
        print(f"✓ All 3 new tools present: {new_tools}")

    def test_ai_tools_structure(self, api_client):
        """Verify tool definitions have required fields"""
        resp = api_client.get(f"{BASE_URL}/api/ai-tools")
        assert resp.status_code == 200
        tools = resp.json()["tools"]
        
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "params" in tool
            assert isinstance(tool["params"], dict)
        print("✓ All tools have required structure")


# ============ 5. MERGE NODE LOGIC (Code Review) ============

class TestMergeNodeLogic:
    """Code-level verification of merge node behavior (cannot fully test without running workflow)"""

    def test_workflow_nodes_support_merge_type(self, api_client):
        """Verify merge is a valid node type"""
        # Create a test workflow to check node types
        wf_res = api_client.post(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/workflows", json={
            "name": "TEST_MergeNodeWorkflow",
            "description": "Testing merge node support"
        })
        if wf_res.status_code != 200:
            pytest.skip("Cannot create workflow")
        
        workflow_id = wf_res.json()["workflow_id"]
        
        # Try to create a merge node
        node_res = api_client.post(f"{BASE_URL}/api/workflows/{workflow_id}/nodes", json={
            "type": "merge",
            "label": "Merge Results"
        })
        assert node_res.status_code == 200, f"Expected 200, got {node_res.status_code}: {node_res.text}"
        data = node_res.json()
        assert data["type"] == "merge"
        print("✓ Merge node type is valid and can be created")
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/workflows/{workflow_id}")


# ============ CLEANUP ============

class TestCleanup:
    """Clean up test data"""

    def test_cleanup_test_memory(self, api_client):
        """Delete test memory entries"""
        resp = api_client.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/memory?search=TEST_")
        if resp.status_code == 200:
            entries = resp.json().get("entries", [])
            for entry in entries:
                if entry.get("key", "").startswith("TEST_"):
                    api_client.delete(f"{BASE_URL}/api/memory/{entry['memory_id']}")
            print(f"✓ Cleaned up {len(entries)} test memory entries")
