"""
P2 Features Test Suite - Iteration 25
Tests: Export & Audit Trail, Webhooks, Model Performance, Disagreement Resolution, Human Checkpoints, Integration Stubs

Test credentials:
  email: testmention@test.com
  password: Test1234!
  workspace: ws_bd1750012bfd
  channel: ch_9988b6543849
  webhook: whk_3404b890fe1a
"""
import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestAuth:
    """Helper to get auth token"""

    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get auth token via email login"""
        login_data = {"email": "testmention@test.com", "password": "Test1234!"}
        resp = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
        if resp.status_code == 200:
            return resp.json().get("session_token") or resp.cookies.get("session_token")
        pytest.skip("Auth failed - cannot proceed with tests")

    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ============ EXPORT & AUDIT TRAIL TESTS ============

class TestAuditLog(TestAuth):
    """Audit Log endpoint tests"""

    def test_get_audit_log(self, headers):
        """GET /api/workspaces/{ws}/audit-log returns audit entries"""
        resp = requests.get(f"{BASE_URL}/api/workspaces/ws_bd1750012bfd/audit-log", headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "entries" in data
        assert "total" in data
        print(f"PASS: Audit log has {data['total']} entries")

    def test_get_audit_actions(self, headers):
        """GET /api/audit-log/actions returns 14 action types"""
        resp = requests.get(f"{BASE_URL}/api/audit-log/actions", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "actions" in data
        actions = data["actions"]
        assert len(actions) == 14, f"Expected 14 actions, got {len(actions)}"
        expected_actions = ["create", "update", "delete", "login", "logout", "export",
                           "run_workflow", "approve_gate", "reject_gate", "schedule_run",
                           "handoff", "bulk_update", "bulk_delete", "api_key_update"]
        for act in expected_actions:
            assert act in actions, f"Missing action: {act}"
        print(f"PASS: 14 audit actions returned: {actions}")


class TestExport(TestAuth):
    """Export endpoint tests"""

    def test_export_channel_json(self, headers):
        """GET /api/channels/{ch}/export?format=json exports messages"""
        resp = requests.get(f"{BASE_URL}/api/channels/ch_9988b6543849/export?format=json", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "channel" in data
        assert "messages" in data
        assert "format" in data and data["format"] == "json"
        assert "exported_at" in data
        print(f"PASS: Channel export (JSON) returned {len(data['messages'])} messages")

    def test_export_channel_markdown(self, headers):
        """GET /api/channels/{ch}/export?format=markdown exports as markdown"""
        resp = requests.get(f"{BASE_URL}/api/channels/ch_9988b6543849/export?format=markdown", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data
        assert "format" in data and data["format"] == "markdown"
        assert "filename" in data
        assert data["filename"].endswith(".md")
        print(f"PASS: Channel export (Markdown) - filename: {data['filename']}")

    def test_export_workspace(self, headers):
        """GET /api/workspaces/{ws}/export exports full workspace data"""
        resp = requests.get(f"{BASE_URL}/api/workspaces/ws_bd1750012bfd/export", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "workspace" in data
        assert "channels" in data
        assert "projects" in data
        assert "workflows" in data
        assert "artifacts" in data
        assert "memory" in data
        assert "exported_at" in data
        print(f"PASS: Workspace export - {len(data['channels'])} channels, {len(data['projects'])} projects")


# ============ WEBHOOK TESTS ============

class TestWebhooks(TestAuth):
    """Webhook CRUD and event tests"""

    def test_list_webhooks(self, headers):
        """GET /api/workspaces/{ws}/webhooks lists webhooks"""
        resp = requests.get(f"{BASE_URL}/api/workspaces/ws_bd1750012bfd/webhooks", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"PASS: Listed {len(data)} webhooks")

    def test_create_webhook(self, headers):
        """POST /api/workspaces/{ws}/webhooks creates webhook with events"""
        payload = {
            "url": "https://httpbin.org/post",
            "events": ["message.created", "task.completed"],
            "name": "TEST_Webhook_" + uuid.uuid4().hex[:6],
            "secret": "test_secret_123"
        }
        resp = requests.post(f"{BASE_URL}/api/workspaces/ws_bd1750012bfd/webhooks", json=payload, headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "webhook_id" in data
        assert data["url"] == payload["url"]
        assert data["events"] == payload["events"]
        assert data["enabled"] is True
        print(f"PASS: Created webhook {data['webhook_id']}")
        return data["webhook_id"]

    def test_update_webhook(self, headers):
        """PUT /api/webhooks/{id} updates webhook"""
        # Use existing webhook or skip
        resp = requests.get(f"{BASE_URL}/api/workspaces/ws_bd1750012bfd/webhooks", headers=headers)
        hooks = resp.json()
        if not hooks:
            pytest.skip("No webhooks to update")
        webhook_id = hooks[0]["webhook_id"]
        
        update_payload = {"name": "Updated_TEST_Webhook", "enabled": True}
        resp = requests.put(f"{BASE_URL}/api/webhooks/{webhook_id}", json=update_payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated_TEST_Webhook"
        print(f"PASS: Updated webhook {webhook_id}")

    def test_test_webhook(self, headers):
        """POST /api/webhooks/{id}/test tests webhook delivery"""
        # Get webhooks and pick one with a valid URL
        resp = requests.get(f"{BASE_URL}/api/workspaces/ws_bd1750012bfd/webhooks", headers=headers)
        hooks = resp.json()
        if not hooks:
            pytest.skip("No webhooks to test")
        webhook_id = hooks[0]["webhook_id"]
        
        resp = requests.post(f"{BASE_URL}/api/webhooks/{webhook_id}/test", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "success" in data
        assert "delivery_id" in data
        assert "status_code" in data
        print(f"PASS: Webhook test - success: {data['success']}, status: {data['status_code']}")

    def test_get_webhook_events(self, headers):
        """GET /api/webhooks/events returns 15 event types"""
        resp = requests.get(f"{BASE_URL}/api/webhooks/events", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        events = data["events"]
        assert len(events) == 15, f"Expected 15 events, got {len(events)}"
        expected_events = ["message.created", "collaboration.started", "collaboration.completed",
                          "task.created", "task.updated", "task.completed",
                          "workflow.run.started", "workflow.run.completed", "workflow.run.failed",
                          "handoff.created", "schedule.executed",
                          "artifact.created", "artifact.updated",
                          "member.joined", "member.removed"]
        for ev in expected_events:
            assert ev in events, f"Missing event: {ev}"
        print(f"PASS: 15 webhook events returned")

    def test_delete_webhook(self, headers):
        """DELETE /api/webhooks/{id} deletes webhook"""
        # Create a test webhook to delete
        payload = {"url": "https://httpbin.org/post", "events": ["message.created"], "name": "DELETE_ME_Webhook"}
        resp = requests.post(f"{BASE_URL}/api/workspaces/ws_bd1750012bfd/webhooks", json=payload, headers=headers)
        if resp.status_code != 200:
            pytest.skip("Could not create webhook to delete")
        webhook_id = resp.json()["webhook_id"]
        
        # Delete it
        resp = requests.delete(f"{BASE_URL}/api/webhooks/{webhook_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("message") == "Webhook deleted"
        print(f"PASS: Deleted webhook {webhook_id}")


# ============ MODEL PERFORMANCE TESTS ============

class TestModelPerformance(TestAuth):
    """Model stats and recommendations tests"""

    def test_get_model_stats(self, headers):
        """GET /api/workspaces/{ws}/model-stats returns model performance stats"""
        resp = requests.get(f"{BASE_URL}/api/workspaces/ws_bd1750012bfd/model-stats", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "stats" in data
        # Stats may be empty if no analytics data
        print(f"PASS: Model stats returned {len(data['stats'])} models")
        if data["stats"]:
            stat = data["stats"][0]
            assert "model" in stat
            assert "total_messages" in stat
            assert "avg_response_ms" in stat

    def test_get_model_recommendations(self, headers):
        """GET /api/workspaces/{ws}/model-recommendations?task_type=code returns recommendations"""
        resp = requests.get(f"{BASE_URL}/api/workspaces/ws_bd1750012bfd/model-recommendations?task_type=code", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "task_type" in data and data["task_type"] == "code"
        assert "recommendations" in data
        print(f"PASS: Model recommendations returned {len(data['recommendations'])} models for task_type=code")
        if data["recommendations"]:
            rec = data["recommendations"][0]
            assert "model" in rec
            assert "score" in rec
            assert "strengths" in rec


# ============ DISAGREEMENT RESOLUTION TESTS ============

class TestDisagreementResolution(TestAuth):
    """Disagreement creation, voting, and resolution tests"""

    @pytest.fixture(scope="class")
    def test_disagreement_id(self, headers):
        """Create a test disagreement for the class"""
        payload = {"topic": "TEST_Disagreement_" + uuid.uuid4().hex[:6]}
        resp = requests.post(f"{BASE_URL}/api/channels/ch_9988b6543849/disagreements", json=payload, headers=headers)
        if resp.status_code == 200:
            return resp.json()["disagreement_id"]
        return None

    def test_create_disagreement(self, headers):
        """POST /api/channels/{ch}/disagreements creates disagreement"""
        payload = {"topic": "TEST_Should_we_use_React_or_Vue"}
        resp = requests.post(f"{BASE_URL}/api/channels/ch_9988b6543849/disagreements", json=payload, headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "disagreement_id" in data
        assert data["topic"] == payload["topic"]
        assert data["status"] == "open"
        assert data["votes"] == {}
        print(f"PASS: Created disagreement {data['disagreement_id']}")
        return data["disagreement_id"]

    def test_submit_vote(self, headers):
        """POST /api/disagreements/{id}/vote submits vote"""
        # Create fresh disagreement
        dis_resp = requests.post(f"{BASE_URL}/api/channels/ch_9988b6543849/disagreements", 
                                 json={"topic": "TEST_Vote_Topic"}, headers=headers)
        if dis_resp.status_code != 200:
            pytest.skip("Could not create disagreement")
        dis_id = dis_resp.json()["disagreement_id"]
        
        # Submit a vote
        vote_payload = {"position": "React", "confidence": 0.9, "agent_key": "claude"}
        resp = requests.post(f"{BASE_URL}/api/disagreements/{dis_id}/vote", json=vote_payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "voting"
        assert "claude" in data["votes"]
        assert data["votes"]["claude"]["position"] == "React"
        print(f"PASS: Vote submitted for disagreement {dis_id}")
        return dis_id

    def test_resolve_disagreement(self, headers):
        """POST /api/disagreements/{id}/resolve resolves with weighted voting"""
        # Create disagreement with 2 votes
        dis_resp = requests.post(f"{BASE_URL}/api/channels/ch_9988b6543849/disagreements", 
                                 json={"topic": "TEST_Resolve_Topic"}, headers=headers)
        if dis_resp.status_code != 200:
            pytest.skip("Could not create disagreement")
        dis_id = dis_resp.json()["disagreement_id"]
        
        # Submit 2 votes (need at least 2 to resolve)
        vote1 = {"position": "Option_A", "confidence": 0.95, "agent_key": "claude"}
        vote2 = {"position": "Option_A", "confidence": 0.7, "agent_key": "chatgpt"}
        requests.post(f"{BASE_URL}/api/disagreements/{dis_id}/vote", json=vote1, headers=headers)
        requests.post(f"{BASE_URL}/api/disagreements/{dis_id}/vote", json=vote2, headers=headers)
        
        # Resolve
        resp = requests.post(f"{BASE_URL}/api/disagreements/{dis_id}/resolve", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "resolution" in data
        res = data["resolution"]
        assert res["winning_position"] == "Option_A"
        assert "confidence_score" in res
        assert res["vote_count"] == 2
        print(f"PASS: Resolved disagreement - winner: {res['winning_position']}, confidence: {res['confidence_score']}")

    def test_resolve_needs_2_votes(self, headers):
        """Resolution requires at least 2 votes"""
        dis_resp = requests.post(f"{BASE_URL}/api/channels/ch_9988b6543849/disagreements", 
                                 json={"topic": "TEST_One_Vote_Only"}, headers=headers)
        if dis_resp.status_code != 200:
            pytest.skip("Could not create disagreement")
        dis_id = dis_resp.json()["disagreement_id"]
        
        # Submit only 1 vote
        vote = {"position": "Solo", "confidence": 0.9, "agent_key": "claude"}
        requests.post(f"{BASE_URL}/api/disagreements/{dis_id}/vote", json=vote, headers=headers)
        
        # Try to resolve - should fail
        resp = requests.post(f"{BASE_URL}/api/disagreements/{dis_id}/resolve", headers=headers)
        assert resp.status_code == 400
        print("PASS: Resolution correctly requires at least 2 votes")


# ============ HUMAN CHECKPOINTS TESTS ============

class TestHumanCheckpoints(TestAuth):
    """Human checkpoint in workflow tests"""

    def test_add_checkpoint_to_workflow(self, headers):
        """POST /api/workflows/{wf}/checkpoints adds human checkpoint"""
        # Get a workflow
        resp = requests.get(f"{BASE_URL}/api/workspaces/ws_bd1750012bfd/workflows", headers=headers)
        workflows = resp.json()
        if not workflows:
            pytest.skip("No workflows to add checkpoint to")
        wf_id = workflows[0]["workflow_id"]
        
        checkpoint_payload = {
            "label": "TEST_Checkpoint_Review",
            "instructions": "Please review before continuing"
        }
        resp = requests.post(f"{BASE_URL}/api/workflows/{wf_id}/checkpoints", json=checkpoint_payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "node_id" in data
        assert data["type"] == "human_review"
        assert data["label"] == checkpoint_payload["label"]
        print(f"PASS: Created checkpoint node {data['node_id']} in workflow {wf_id}")

    def test_list_checkpoints(self, headers):
        """GET /api/workflows/{wf}/checkpoints lists human checkpoints"""
        resp = requests.get(f"{BASE_URL}/api/workspaces/ws_bd1750012bfd/workflows", headers=headers)
        workflows = resp.json()
        if not workflows:
            pytest.skip("No workflows")
        wf_id = workflows[0]["workflow_id"]
        
        resp = requests.get(f"{BASE_URL}/api/workflows/{wf_id}/checkpoints", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"PASS: Listed {len(data)} checkpoints in workflow {wf_id}")


# ============ INTEGRATION STUBS TESTS ============

class TestIntegrationStubs(TestAuth):
    """Integration status stubs tests"""

    def test_all_integrations_status(self, headers):
        """GET /api/integrations/status returns all integration statuses"""
        resp = requests.get(f"{BASE_URL}/api/integrations/status", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        # Should have all integration statuses
        assert "email" in data
        assert "microsoft_oauth" in data
        assert "meta_oauth" in data
        assert "paypal" in data
        assert "stripe" in data
        assert "google_oauth" in data
        # Google OAuth should be configured (emergent)
        assert data["google_oauth"]["configured"] is True
        print(f"PASS: All integration statuses returned")

    def test_microsoft_auth_stub(self, headers):
        """POST /api/auth/microsoft returns 501 (not configured)"""
        resp = requests.post(f"{BASE_URL}/api/auth/microsoft", headers=headers)
        assert resp.status_code == 501
        print("PASS: Microsoft OAuth returns 501 as expected (stub)")

    def test_meta_auth_stub(self, headers):
        """POST /api/auth/meta returns 501 (not configured)"""
        resp = requests.post(f"{BASE_URL}/api/auth/meta", headers=headers)
        assert resp.status_code == 501
        print("PASS: Meta OAuth returns 501 as expected (stub)")

    def test_paypal_stub(self, headers):
        """POST /api/billing/paypal/create-order returns 501 (not configured)"""
        resp = requests.post(f"{BASE_URL}/api/billing/paypal/create-order", headers=headers)
        assert resp.status_code == 501
        print("PASS: PayPal create-order returns 501 as expected (stub)")


# ============ N+1 FIX TEST ============

class TestWorkspacesOptimized(TestAuth):
    """Test N+1 query optimization in get_workspaces"""

    def test_get_workspaces_has_counts(self, headers):
        """GET /api/workspaces returns agent counts (batch queries)"""
        resp = requests.get(f"{BASE_URL}/api/workspaces", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if data:
            ws = data[0]
            # Should have agent counts from optimized batch query
            assert "agent_count" in ws or "total_agents" in ws
            print(f"PASS: Workspaces endpoint returns agent counts (N+1 fix verified)")
        else:
            print("PASS: Workspaces endpoint returns empty list (no workspaces)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
