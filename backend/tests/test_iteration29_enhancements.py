"""
Iteration 29: Testing 12 Enhancement Features
- Usage Analytics, Workspace Templates, Team Activity Feed
- Conversation Branching, Agent Personas Library, Smart Summarization
- Comments on Artifacts, @channel Notifications, Workspace Activity Timeline
- Dark/Light Theme, Keyboard Shortcuts, Onboarding Tour (frontend tests)
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials from review request
TEST_EMAIL = "testmention@test.com"
TEST_PASSWORD = "Test1234!"
TEST_WORKSPACE = "ws_bd1750012bfd"
TEST_CHANNEL = "ch_9988b6543849"
TEST_ARTIFACT = "art_3e289bcd225b"


@pytest.fixture(scope="module")
def auth_session():
    """Authenticate and get session with cookies"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return session


class TestUsageAnalytics:
    """1. GET /api/workspaces/{ws}/usage-analytics"""
    
    def test_usage_analytics_returns_expected_fields(self, auth_session):
        """Returns messages, model_usage, daily_activity, artifacts_count"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/usage-analytics")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        # Check required fields
        assert "messages" in data, "Missing 'messages' field"
        assert "model_usage" in data, "Missing 'model_usage' field"
        assert "daily_activity" in data, "Missing 'daily_activity' field"
        assert "artifacts_count" in data, "Missing 'artifacts_count' field"
        
        # Validate messages structure
        messages = data["messages"]
        assert "human" in messages
        assert "ai" in messages
        assert "total" in messages
        
        # model_usage and daily_activity are lists
        assert isinstance(data["model_usage"], list)
        assert isinstance(data["daily_activity"], list)
        
        print(f"Usage analytics: {data['messages']['total']} total messages, {data['artifacts_count']} artifacts")

    def test_usage_analytics_with_days_param(self, auth_session):
        """Can filter by days parameter"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/usage-analytics?days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert data["period_days"] == 7


class TestSmartSummarization:
    """6. POST /api/channels/{ch}/summarize"""
    
    def test_summarize_channel_returns_expected_fields(self, auth_session):
        """Returns summary, total_messages, key_decisions, action_items, open_questions"""
        resp = auth_session.post(f"{BASE_URL}/api/channels/{TEST_CHANNEL}/summarize")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        # Check all required fields
        assert "summary" in data, "Missing 'summary' field"
        assert "total_messages" in data, "Missing 'total_messages' field"
        assert "key_decisions" in data, "Missing 'key_decisions' field"
        assert "action_items" in data, "Missing 'action_items' field"
        assert "open_questions" in data, "Missing 'open_questions' field"
        
        # Validate types
        assert isinstance(data["summary"], str)
        assert isinstance(data["total_messages"], int)
        assert isinstance(data["key_decisions"], list)
        assert isinstance(data["action_items"], list)
        assert isinstance(data["open_questions"], list)
        
        print(f"Summarization: {data['total_messages']} messages, {len(data['key_decisions'])} decisions")


class TestArtifactComments:
    """7. POST/GET /api/artifacts/{id}/comments"""
    
    def test_create_comment_on_artifact(self, auth_session):
        """POST comment with content, returns author_name"""
        unique_content = f"TEST_COMMENT_{uuid.uuid4().hex[:8]}"
        resp = auth_session.post(
            f"{BASE_URL}/api/artifacts/{TEST_ARTIFACT}/comments",
            json={"content": unique_content}
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "comment_id" in data
        assert "author_name" in data
        assert data["content"] == unique_content
        assert "created_at" in data
        
        print(f"Created comment: {data['comment_id']} by {data['author_name']}")
        return data["comment_id"]
    
    def test_list_comments_on_artifact(self, auth_session):
        """GET returns comments sorted by date"""
        resp = auth_session.get(f"{BASE_URL}/api/artifacts/{TEST_ARTIFACT}/comments")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert isinstance(data, list)
        
        if len(data) > 0:
            # Validate comment structure
            comment = data[0]
            assert "comment_id" in comment
            assert "content" in comment
            assert "author_name" in comment
            assert "created_at" in comment
        
        print(f"Listed {len(data)} comments on artifact")
    
    def test_delete_comment(self, auth_session):
        """DELETE /api/comments/{id} removes comment"""
        # First create a comment
        content = f"TEST_DELETE_{uuid.uuid4().hex[:8]}"
        create_resp = auth_session.post(
            f"{BASE_URL}/api/artifacts/{TEST_ARTIFACT}/comments",
            json={"content": content}
        )
        assert create_resp.status_code == 200
        comment_id = create_resp.json()["comment_id"]
        
        # Delete it
        del_resp = auth_session.delete(f"{BASE_URL}/api/comments/{comment_id}")
        assert del_resp.status_code == 200, f"Failed: {del_resp.text}"
        print(f"Deleted comment: {comment_id}")


class TestAgentPersonas:
    """5. GET/POST /api/personas"""
    
    def test_list_personas_returns_builtin(self, auth_session):
        """Returns 4 built-in personas + categories"""
        resp = auth_session.get(f"{BASE_URL}/api/personas")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "personas" in data
        assert "categories" in data
        
        personas = data["personas"]
        assert len(personas) >= 4, f"Expected at least 4 built-in personas, got {len(personas)}"
        
        # Check built-in persona IDs
        persona_ids = [p.get("persona_id") for p in personas]
        expected_ids = ["per_sr_code_reviewer", "per_tech_writer", "per_data_analyst", "per_strategist"]
        for pid in expected_ids:
            assert pid in persona_ids, f"Missing built-in persona: {pid}"
        
        categories = data["categories"]
        assert "code_review" in categories
        assert "writing" in categories
        assert "data" in categories
        assert "strategy" in categories
        
        print(f"Listed {len(personas)} personas in {len(categories)} categories")
    
    def test_create_custom_persona(self, auth_session):
        """POST creates custom persona with system_prompt"""
        persona_name = f"TEST_Persona_{uuid.uuid4().hex[:8]}"
        resp = auth_session.post(f"{BASE_URL}/api/personas", json={
            "name": persona_name,
            "description": "Test persona for automated testing",
            "base_model": "claude",
            "system_prompt": "You are a helpful test assistant for automated testing purposes.",
            "category": "general",
            "is_public": False
        })
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "persona_id" in data
        assert data["name"] == persona_name
        assert data["system_prompt"].startswith("You are a helpful")
        
        print(f"Created persona: {data['persona_id']}")
        
        # Cleanup
        auth_session.delete(f"{BASE_URL}/api/personas/{data['persona_id']}")


class TestWorkspaceTemplates:
    """2. GET/POST /api/workspace-templates"""
    
    def test_list_workspace_templates_returns_builtin(self, auth_session):
        """Returns 4 built-in templates"""
        resp = auth_session.get(f"{BASE_URL}/api/workspace-templates")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "templates" in data
        
        templates = data["templates"]
        assert len(templates) >= 4, f"Expected at least 4 templates, got {len(templates)}"
        
        # Check built-in template IDs
        template_ids = [t.get("template_id") for t in templates]
        expected_ids = ["wst_product_launch", "wst_code_review", "wst_research_lab", "wst_content_studio"]
        for tid in expected_ids:
            assert tid in template_ids, f"Missing built-in template: {tid}"
        
        print(f"Listed {len(templates)} workspace templates")
    
    def test_deploy_workspace_template(self, auth_session):
        """POST /api/workspace-templates/{id}/deploy creates workspace + channels"""
        ws_name = f"TEST_Template_Deploy_{uuid.uuid4().hex[:6]}"
        resp = auth_session.post(
            f"{BASE_URL}/api/workspace-templates/wst_code_review/deploy",
            json={"name": ws_name}
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "workspace_id" in data
        assert "channels_created" in data
        assert data["channels_created"] >= 1, "Should create at least 1 channel from template"
        
        print(f"Deployed template: workspace {data['workspace_id']} with {data['channels_created']} channels")
        
        # Cleanup - delete the workspace
        auth_session.delete(f"{BASE_URL}/api/workspaces/{data['workspace_id']}")


class TestConversationBranching:
    """4. POST /api/channels/{ch}/branch"""
    
    def test_branch_conversation(self, auth_session):
        """Forks conversation to new channel with copied messages"""
        branch_name = f"TEST_Branch_{uuid.uuid4().hex[:6]}"
        resp = auth_session.post(
            f"{BASE_URL}/api/channels/{TEST_CHANNEL}/branch",
            json={"name": branch_name}
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "branch_channel_id" in data
        assert "name" in data
        assert "messages_copied" in data
        assert isinstance(data["messages_copied"], int)
        
        print(f"Created branch: {data['branch_channel_id']} with {data['messages_copied']} copied messages")
        
        # Cleanup - delete the branch channel
        auth_session.delete(f"{BASE_URL}/api/channels/{data['branch_channel_id']}")


class TestTeamActivityFeed:
    """3. GET /api/workspaces/{ws}/activity-feed"""
    
    def test_activity_feed_returns_events(self, auth_session):
        """Returns mixed events (messages, artifacts, tasks)"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/activity-feed")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "events" in data
        
        events = data["events"]
        assert isinstance(events, list)
        
        if len(events) > 0:
            # Check event structure
            event = events[0]
            assert "type" in event
            assert "actor" in event
            assert "description" in event
            assert "timestamp" in event
            
            # Validate event types
            valid_types = ["message", "artifact_created", "task_updated"]
            assert event["type"] in valid_types, f"Invalid event type: {event['type']}"
        
        print(f"Activity feed has {len(events)} events")
    
    def test_activity_feed_limit_param(self, auth_session):
        """Can limit number of events"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/activity-feed?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["events"]) <= 5


class TestWorkspaceTimeline:
    """9. GET /api/workspaces/{ws}/timeline"""
    
    def test_workspace_timeline_returns_audit_and_workflow(self, auth_session):
        """Returns audit + workflow run timeline"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/timeline")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "timeline" in data
        assert "period_days" in data
        
        timeline = data["timeline"]
        assert isinstance(timeline, list)
        
        if len(timeline) > 0:
            entry = timeline[0]
            assert "type" in entry
            assert "action" in entry
            assert "timestamp" in entry
            
            # Valid types
            valid_types = ["audit", "workflow_run"]
            assert entry["type"] in valid_types
        
        print(f"Timeline has {len(timeline)} entries for last {data['period_days']} days")


class TestChannelNotifications:
    """8. POST /api/workspaces/{ws}/notify"""
    
    def test_send_workspace_notification(self, auth_session):
        """Sends notifications to workspace members"""
        resp = auth_session.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/notify",
            json={
                "message": f"TEST notification {uuid.uuid4().hex[:6]}",
                "type": "info"
            }
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "sent_to" in data
        assert "message" in data
        assert isinstance(data["sent_to"], int)
        
        print(f"Notification sent to {data['sent_to']} members")
    
    def test_notification_requires_message(self, auth_session):
        """Returns 400 if message is missing"""
        resp = auth_session.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/notify",
            json={"type": "info"}
        )
        assert resp.status_code == 400, "Should reject empty message"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
