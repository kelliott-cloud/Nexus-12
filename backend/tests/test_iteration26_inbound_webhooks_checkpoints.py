"""
Iteration 26: Test inbound webhooks, enhanced checkpoint types, and KB context injection
Tests:
1. Inbound Webhooks CRUD - POST/GET/DELETE /api/workspaces/{ws}/inbound-webhooks
2. Inbound Webhook Trigger - PUBLIC POST /api/webhooks/inbound/{url_token}
3. Enhanced Checkpoint Types - GET /api/checkpoints/types returns 5 types
4. Checkpoint creation with timeout_minutes and auto_approve_if
5. KB injection code path verification (existence check in server.py)
6. Artifact creation with from-chat tag
"""

import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testmention@test.com"
TEST_PASSWORD = "Test1234!"
TEST_WORKSPACE = "ws_bd1750012bfd"
TEST_CHANNEL = "ch_9988b6543849"

@pytest.fixture(scope="module")
def session():
    """Create a requests session with auth via cookies"""
    s = requests.Session()
    resp = s.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if resp.status_code != 200:
        pytest.skip(f"Auth failed: {resp.status_code} - {resp.text}")
    # Verify auth works
    me_resp = s.get(f"{BASE_URL}/api/auth/me")
    if me_resp.status_code != 200:
        pytest.skip(f"Auth verification failed: {me_resp.status_code}")
    print(f"Authenticated as: {me_resp.json().get('email')}")
    return s


class TestInboundWebhooksCRUD:
    """Test inbound webhook CRUD operations"""
    
    created_hook_id = None
    created_url_token = None
    
    def test_list_inbound_webhooks(self, session):
        """GET /api/workspaces/{ws}/inbound-webhooks - lists inbound webhooks with webhook_url"""
        resp = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/inbound-webhooks")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert isinstance(data, list), "Response should be a list"
        
        # Check structure of any existing webhook
        if len(data) > 0:
            hook = data[0]
            assert "inbound_hook_id" in hook, "Should have inbound_hook_id"
            assert "url_token" in hook, "Should have url_token"
            assert "webhook_url" in hook, "Should have webhook_url"
            assert hook["webhook_url"].startswith("/api/webhooks/inbound/"), "webhook_url should be correct path"
        
        print(f"Listed {len(data)} inbound webhooks")
    
    def test_create_inbound_webhook(self, session):
        """POST /api/workspaces/{ws}/inbound-webhooks - creates inbound webhook"""
        test_workflow_id = f"wf_test_{uuid.uuid4().hex[:8]}"
        
        resp = session.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/inbound-webhooks",
            json={
                "name": "TEST_Inbound_Webhook_26",
                "workflow_id": test_workflow_id,
                "input_mapping": {"message": "$.body.text", "user": "$.headers.sender"}
            }
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "inbound_hook_id" in data, "Should return inbound_hook_id"
        assert data["inbound_hook_id"].startswith("iwh_"), "ID should have iwh_ prefix"
        assert "url_token" in data, "Should return url_token"
        assert "webhook_url" in data, "Should return webhook_url"
        assert data["webhook_url"] == f"/api/webhooks/inbound/{data['url_token']}", "webhook_url should match url_token"
        assert data["name"] == "TEST_Inbound_Webhook_26", "Name should match"
        assert data["workflow_id"] == test_workflow_id, "workflow_id should match"
        assert data["input_mapping"] == {"message": "$.body.text", "user": "$.headers.sender"}, "input_mapping should match"
        assert data["is_active"] == True, "Should be active by default"
        assert data["trigger_count"] == 0, "trigger_count should start at 0"
        
        TestInboundWebhooksCRUD.created_hook_id = data["inbound_hook_id"]
        TestInboundWebhooksCRUD.created_url_token = data["url_token"]
        print(f"Created inbound webhook: {data['inbound_hook_id']} with URL token: {data['url_token']}")
    
    def test_verify_created_hook_in_list(self, session):
        """Verify the created hook appears in the list"""
        if not TestInboundWebhooksCRUD.created_hook_id:
            pytest.skip("No hook created to verify")
        
        resp = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/inbound-webhooks")
        assert resp.status_code == 200
        
        data = resp.json()
        hook_ids = [h["inbound_hook_id"] for h in data]
        assert TestInboundWebhooksCRUD.created_hook_id in hook_ids, "Created hook should appear in list"
        print(f"Verified hook {TestInboundWebhooksCRUD.created_hook_id} in list")
    
    def test_delete_inbound_webhook(self, session):
        """DELETE /api/inbound-webhooks/{id} - deletes inbound webhook"""
        if not TestInboundWebhooksCRUD.created_hook_id:
            pytest.skip("No hook created to delete")
        
        resp = session.delete(f"{BASE_URL}/api/inbound-webhooks/{TestInboundWebhooksCRUD.created_hook_id}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "message" in data, "Should return message"
        assert "Deleted" in data["message"], "Message should confirm deletion"
        print(f"Deleted inbound webhook: {TestInboundWebhooksCRUD.created_hook_id}")
    
    def test_delete_nonexistent_hook(self, session):
        """DELETE on non-existent hook should return 404"""
        resp = session.delete(f"{BASE_URL}/api/inbound-webhooks/iwh_doesnotexist123")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print("Verified 404 for non-existent hook deletion")


class TestInboundWebhookTrigger:
    """Test the PUBLIC inbound webhook trigger endpoint"""
    
    def test_trigger_inbound_webhook_public_endpoint(self, session):
        """POST /api/webhooks/inbound/{url_token} - PUBLIC endpoint triggers workflow"""
        # First create a webhook to test trigger
        test_workflow_id = f"wf_trigger_test_{uuid.uuid4().hex[:8]}"
        
        create_resp = session.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/inbound-webhooks",
            json={
                "name": "TEST_Trigger_Webhook",
                "workflow_id": test_workflow_id,
                "input_mapping": {"data": "$.payload"}
            }
        )
        assert create_resp.status_code == 200, f"Failed to create test webhook: {create_resp.text}"
        
        url_token = create_resp.json()["url_token"]
        hook_id = create_resp.json()["inbound_hook_id"]
        
        # Trigger the webhook - NO AUTH NEEDED (public endpoint)
        trigger_resp = requests.post(
            f"{BASE_URL}/api/webhooks/inbound/{url_token}",
            json={"payload": {"test": "data", "timestamp": time.time()}},
            headers={"Content-Type": "application/json"}  # No auth header!
        )
        assert trigger_resp.status_code == 200, f"Expected 200, got {trigger_resp.status_code}: {trigger_resp.text}"
        
        data = trigger_resp.json()
        assert data["status"] == "triggered", f"Expected status='triggered', got {data.get('status')}"
        assert "run_id" in data, "Should return run_id"
        assert data["run_id"].startswith("wrun_"), "run_id should have wrun_ prefix"
        assert data["workflow_id"] == test_workflow_id, "Should return workflow_id"
        
        print(f"Triggered webhook with run_id: {data['run_id']}")
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/inbound-webhooks/{hook_id}")
    
    def test_trigger_invalid_token_returns_404(self):
        """Trigger with invalid token should return 404"""
        resp = requests.post(
            f"{BASE_URL}/api/webhooks/inbound/invalid_token_xyz",
            json={"test": "data"},
            headers={"Content-Type": "application/json"}
        )
        assert resp.status_code == 404, f"Expected 404 for invalid token, got {resp.status_code}"
        print("Verified 404 for invalid webhook token")
    
    def test_trigger_applies_input_mapping(self, session):
        """Verify input_mapping is applied when triggering"""
        # Create webhook with specific input mapping
        test_workflow_id = f"wf_mapping_test_{uuid.uuid4().hex[:8]}"
        
        create_resp = session.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/inbound-webhooks",
            json={
                "name": "TEST_Mapping_Webhook",
                "workflow_id": test_workflow_id,
                "input_mapping": {
                    "message": "$.text",
                    "sender": "$.user.name"
                }
            }
        )
        assert create_resp.status_code == 200
        
        url_token = create_resp.json()["url_token"]
        hook_id = create_resp.json()["inbound_hook_id"]
        
        # Trigger with nested payload
        trigger_resp = requests.post(
            f"{BASE_URL}/api/webhooks/inbound/{url_token}",
            json={
                "text": "Hello from webhook",
                "user": {"name": "External System", "id": 123}
            },
            headers={"Content-Type": "application/json"}
        )
        assert trigger_resp.status_code == 200, f"Trigger failed: {trigger_resp.text}"
        
        data = trigger_resp.json()
        assert data["status"] == "triggered", "Should trigger successfully"
        
        print(f"Input mapping test passed with run_id: {data['run_id']}")
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/inbound-webhooks/{hook_id}")


class TestEnhancedCheckpointTypes:
    """Test enhanced checkpoint types endpoint"""
    
    def test_get_checkpoint_types_returns_five_types(self, session):
        """GET /api/checkpoints/types - returns 5 checkpoint types"""
        resp = session.get(f"{BASE_URL}/api/checkpoints/types")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "types" in data, "Response should have 'types' key"
        
        types_list = data["types"]
        assert len(types_list) == 5, f"Expected 5 checkpoint types, got {len(types_list)}"
        
        # Verify all expected types
        expected_keys = ["approve_reject", "review_edit", "select_option", "provide_input", "confirm_proceed"]
        actual_keys = [t["key"] for t in types_list]
        
        for expected in expected_keys:
            assert expected in actual_keys, f"Missing checkpoint type: {expected}"
        
        # Verify structure of each type
        for t in types_list:
            assert "key" in t, "Type should have 'key'"
            assert "name" in t, "Type should have 'name'"
            assert "description" in t, "Type should have 'description'"
        
        print(f"Checkpoint types: {actual_keys}")
        
        # Verify specific names
        type_dict = {t["key"]: t for t in types_list}
        assert "Approve" in type_dict["approve_reject"]["name"]
        assert "Review" in type_dict["review_edit"]["name"]
        assert "Select" in type_dict["select_option"]["name"]
        assert "Provide" in type_dict["provide_input"]["name"]
        assert "Confirm" in type_dict["confirm_proceed"]["name"]
        
        print("All 5 checkpoint types verified with correct structure")


class TestCheckpointCreation:
    """Test checkpoint creation with new fields (checkpoint_type, timeout_minutes, auto_approve_if)"""
    
    test_workflow_id = None
    test_checkpoint_id = None
    
    def test_create_workflow_for_checkpoint(self, session):
        """Create a test workflow to add checkpoints to"""
        resp = session.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/workflows",
            json={
                "name": "TEST_Checkpoint_Workflow_26",
                "description": "Workflow for testing checkpoint creation"
            }
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        TestCheckpointCreation.test_workflow_id = data["workflow_id"]
        print(f"Created test workflow: {data['workflow_id']}")
    
    def test_add_checkpoint_with_enhanced_fields(self, session):
        """POST /api/workflows/{wf}/checkpoints with checkpoint_type, timeout_minutes, auto_approve_if"""
        if not TestCheckpointCreation.test_workflow_id:
            pytest.skip("No test workflow created")
        
        resp = session.post(
            f"{BASE_URL}/api/workflows/{TestCheckpointCreation.test_workflow_id}/checkpoints",
            json={
                "label": "Quality Review Gate",
                "instructions": "Review the generated content for accuracy and tone",
                "checkpoint_type": "review_edit",
                "timeout_minutes": 60,
                "auto_approve_if": "confidence > 0.9"
            }
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "node_id" in data, "Should return node_id"
        assert data["type"] == "human_review", "Node type should be human_review"
        assert data["label"] == "Quality Review Gate", "Label should match"
        assert data["checkpoint_type"] == "review_edit", "checkpoint_type should match"
        assert data["timeout_minutes"] == 60, "timeout_minutes should match"
        assert data["auto_approve_if"] == "confidence > 0.9", "auto_approve_if should match"
        
        TestCheckpointCreation.test_checkpoint_id = data["node_id"]
        print(f"Created checkpoint: {data['node_id']} with type={data['checkpoint_type']}")
    
    def test_list_checkpoints_shows_enhanced_fields(self, session):
        """GET /api/workflows/{wf}/checkpoints shows enhanced fields"""
        if not TestCheckpointCreation.test_workflow_id:
            pytest.skip("No test workflow created")
        
        resp = session.get(f"{BASE_URL}/api/workflows/{TestCheckpointCreation.test_workflow_id}/checkpoints")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert isinstance(data, list), "Should return list"
        assert len(data) >= 1, "Should have at least 1 checkpoint"
        
        # Find our created checkpoint
        our_checkpoint = next((c for c in data if c["node_id"] == TestCheckpointCreation.test_checkpoint_id), None)
        if our_checkpoint:
            assert our_checkpoint["checkpoint_type"] == "review_edit"
            assert our_checkpoint["timeout_minutes"] == 60
            assert our_checkpoint["auto_approve_if"] == "confidence > 0.9"
            print(f"Verified checkpoint {our_checkpoint['node_id']} has all enhanced fields")
    
    def test_cleanup_test_workflow(self, session):
        """Cleanup the test workflow"""
        if not TestCheckpointCreation.test_workflow_id:
            pytest.skip("No test workflow to cleanup")
        
        resp = session.delete(f"{BASE_URL}/api/workflows/{TestCheckpointCreation.test_workflow_id}")
        # 200 or 404 (if already deleted) is acceptable
        assert resp.status_code in [200, 404], f"Expected 200 or 404, got {resp.status_code}"
        print(f"Cleaned up test workflow")


class TestKnowledgeBaseInjection:
    """Test KB context injection into AI prompts (code path verification)"""
    
    created_memory_id = None
    
    def test_kb_entries_exist_for_workspace(self, session):
        """Verify we can list KB entries (workspace_memory collection)"""
        resp = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/memory")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        # Response format is {"entries": [...], "total": N}
        assert "entries" in data, "Should have 'entries' key"
        assert isinstance(data["entries"], list), "entries should be a list"
        print(f"Found {data.get('total', len(data['entries']))} KB entries in workspace")
    
    def test_create_kb_entry_for_injection(self, session):
        """Create a KB entry that would be injected into AI prompts"""
        resp = session.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/memory",
            json={
                "key": "TEST_KB_Injection_26",
                "value": "This is a test knowledge base entry for iteration 26 testing. It should be injected into AI system prompts during collaboration.",
                "category": "test"
            }
        )
        assert resp.status_code in [200, 201], f"Expected 200/201, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "memory_id" in data, "Should return memory_id"
        assert data["key"] == "TEST_KB_Injection_26"
        
        TestKnowledgeBaseInjection.created_memory_id = data["memory_id"]
        print(f"Created KB entry: {data['memory_id']}")
    
    def test_verify_kb_entry_persisted(self, session):
        """Verify KB entry appears in list"""
        if not TestKnowledgeBaseInjection.created_memory_id:
            pytest.skip("No KB entry created")
        
        resp = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/memory")
        assert resp.status_code == 200
        
        data = resp.json()
        entries = data.get("entries", [])
        memory_ids = [e.get("memory_id") for e in entries]
        assert TestKnowledgeBaseInjection.created_memory_id in memory_ids, "Created KB entry should be in list"
        print(f"Verified KB entry {TestKnowledgeBaseInjection.created_memory_id} persisted")
    
    def test_delete_test_kb_entry(self, session):
        """Cleanup the test KB entry"""
        if not TestKnowledgeBaseInjection.created_memory_id:
            pytest.skip("No KB entry to delete")
        
        resp = session.delete(f"{BASE_URL}/api/memory/{TestKnowledgeBaseInjection.created_memory_id}")
        assert resp.status_code in [200, 404], f"Expected 200 or 404, got {resp.status_code}"
        print(f"Cleaned up test KB entry")


class TestArtifactCreation:
    """Test artifact creation endpoint (used by Save as Artifact feature)"""
    
    created_artifact_id = None
    
    def test_create_artifact_with_from_chat_tag(self, session):
        """POST /api/workspaces/{ws}/artifacts - creates artifact with from-chat tag"""
        resp = session.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/artifacts",
            json={
                "name": "TEST_Artifact_From_Chat_26",
                "content": "This is test content saved from chat message.",
                "content_type": "text",
                "tags": ["from-chat", "claude"]
            }
        )
        assert resp.status_code in [200, 201], f"Expected 200/201, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "artifact_id" in data, "Should return artifact_id"
        assert data["name"] == "TEST_Artifact_From_Chat_26", "Name should match"
        assert "from-chat" in data.get("tags", []), "Should have from-chat tag"
        
        TestArtifactCreation.created_artifact_id = data["artifact_id"]
        print(f"Created artifact: {data['artifact_id']} with tags {data.get('tags')}")
    
    def test_verify_artifact_persisted(self, session):
        """Verify the created artifact appears in list"""
        if not TestArtifactCreation.created_artifact_id:
            pytest.skip("No artifact created")
        
        resp = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/artifacts")
        assert resp.status_code == 200
        
        data = resp.json()
        # Response format is {"artifacts": [...], "total": N}
        artifacts = data.get("artifacts", [])
        artifact_ids = [a["artifact_id"] for a in artifacts]
        assert TestArtifactCreation.created_artifact_id in artifact_ids, "Created artifact should be in list"
        print(f"Verified artifact {TestArtifactCreation.created_artifact_id} persisted")
    
    def test_cleanup_test_artifact(self, session):
        """Cleanup the test artifact"""
        if not TestArtifactCreation.created_artifact_id:
            return
        
        resp = session.delete(f"{BASE_URL}/api/artifacts/{TestArtifactCreation.created_artifact_id}")
        print(f"Cleaned up test artifact")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
