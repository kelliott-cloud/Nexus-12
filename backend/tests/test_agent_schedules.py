"""
Test Suite for Agent Schedules Feature (Iteration 22)
Tests the cron-like scheduled actions for AI agents in workspaces.

Endpoints:
- GET /api/schedules/action-types - Get available action types and intervals
- POST /api/workspaces/{ws_id}/schedules - Create a new schedule
- GET /api/workspaces/{ws_id}/schedules - List schedules for workspace
- PUT /api/schedules/{id} - Update a schedule
- DELETE /api/schedules/{id} - Delete a schedule
- POST /api/schedules/{id}/run - Manual trigger
- GET /api/schedules/{id}/history - Get execution history
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testmention@test.com"
TEST_PASSWORD = "Test1234!"
TEST_WORKSPACE_ID = "ws_bd1750012bfd"
TEST_CHANNEL_ID = "ch_9988b6543849"


@pytest.fixture(scope="module")
def session():
    """Create authenticated session"""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    
    # Login
    login_res = s.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    
    # Session cookie is set automatically
    return s


@pytest.fixture(scope="module")
def created_schedule_id(session):
    """Create a test schedule and return its ID, cleaned up after tests"""
    # Create schedule
    payload = {
        "channel_id": TEST_CHANNEL_ID,
        "agent_key": "claude",
        "action_type": "project_review",
        "interval_minutes": 1440,
        "enabled": True
    }
    res = session.post(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/schedules", json=payload)
    assert res.status_code == 200, f"Failed to create schedule: {res.text}"
    schedule_id = res.json()["schedule_id"]
    
    yield schedule_id
    
    # Cleanup
    session.delete(f"{BASE_URL}/api/schedules/{schedule_id}")


class TestScheduleActionTypes:
    """Test GET /api/schedules/action-types endpoint"""
    
    def test_get_action_types_returns_4_types(self, session):
        """GET /api/schedules/action-types returns exactly 4 action types"""
        res = session.get(f"{BASE_URL}/api/schedules/action-types")
        assert res.status_code == 200
        data = res.json()
        
        assert "action_types" in data
        assert len(data["action_types"]) == 4
        
        action_keys = [at["key"] for at in data["action_types"]]
        assert "project_review" in action_keys
        assert "task_triage" in action_keys
        assert "standup_summary" in action_keys
        assert "custom" in action_keys
    
    def test_get_action_types_returns_8_intervals(self, session):
        """GET /api/schedules/action-types returns exactly 8 valid intervals"""
        res = session.get(f"{BASE_URL}/api/schedules/action-types")
        assert res.status_code == 200
        data = res.json()
        
        assert "valid_intervals" in data
        assert len(data["valid_intervals"]) == 8
        
        interval_minutes = [i["minutes"] for i in data["valid_intervals"]]
        expected = [15, 30, 60, 120, 240, 480, 720, 1440]
        assert interval_minutes == expected
    
    def test_action_types_have_proper_structure(self, session):
        """Action types have key, name, description fields"""
        res = session.get(f"{BASE_URL}/api/schedules/action-types")
        assert res.status_code == 200
        data = res.json()
        
        for at in data["action_types"]:
            assert "key" in at
            assert "name" in at
            assert "description" in at


class TestScheduleCreate:
    """Test POST /api/workspaces/{ws_id}/schedules endpoint"""
    
    def test_create_schedule_success(self, session):
        """POST creates a new schedule with proper fields"""
        payload = {
            "channel_id": TEST_CHANNEL_ID,
            "agent_key": "chatgpt",
            "action_type": "standup_summary",
            "interval_minutes": 60,
            "enabled": True
        }
        res = session.post(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/schedules", json=payload)
        assert res.status_code == 200, f"Create failed: {res.text}"
        
        data = res.json()
        assert "schedule_id" in data
        assert data["schedule_id"].startswith("sched_")
        assert data["channel_id"] == TEST_CHANNEL_ID
        assert data["agent_key"] == "chatgpt"
        assert data["action_type"] == "standup_summary"
        assert data["interval_minutes"] == 60
        assert data["enabled"] == True
        assert "next_run_at" in data
        assert "created_at" in data
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/schedules/{data['schedule_id']}")
    
    def test_create_schedule_invalid_action_type_returns_400(self, session):
        """Invalid action_type returns 400"""
        payload = {
            "channel_id": TEST_CHANNEL_ID,
            "agent_key": "claude",
            "action_type": "invalid_action",
            "interval_minutes": 1440,
            "enabled": True
        }
        res = session.post(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/schedules", json=payload)
        assert res.status_code == 400
        assert "Invalid action_type" in res.json().get("detail", "")
    
    def test_create_schedule_invalid_interval_returns_400(self, session):
        """Invalid interval_minutes returns 400"""
        payload = {
            "channel_id": TEST_CHANNEL_ID,
            "agent_key": "claude",
            "action_type": "project_review",
            "interval_minutes": 999,  # Invalid interval
            "enabled": True
        }
        res = session.post(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/schedules", json=payload)
        assert res.status_code == 400
        assert "Invalid interval" in res.json().get("detail", "")
    
    def test_create_custom_without_prompt_returns_400(self, session):
        """Custom action without custom_prompt returns 400"""
        payload = {
            "channel_id": TEST_CHANNEL_ID,
            "agent_key": "claude",
            "action_type": "custom",
            "interval_minutes": 1440,
            "enabled": True
            # Missing custom_prompt
        }
        res = session.post(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/schedules", json=payload)
        assert res.status_code == 400
        assert "custom_prompt is required" in res.json().get("detail", "")
    
    def test_create_custom_with_prompt_success(self, session):
        """Custom action with custom_prompt succeeds"""
        payload = {
            "channel_id": TEST_CHANNEL_ID,
            "agent_key": "claude",
            "action_type": "custom",
            "custom_prompt": "Summarize all tasks due this week",
            "interval_minutes": 720,
            "enabled": True
        }
        res = session.post(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/schedules", json=payload)
        assert res.status_code == 200, f"Create failed: {res.text}"
        
        data = res.json()
        assert data["action_type"] == "custom"
        assert data["custom_prompt"] == "Summarize all tasks due this week"
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/schedules/{data['schedule_id']}")


class TestScheduleList:
    """Test GET /api/workspaces/{ws_id}/schedules endpoint"""
    
    def test_list_schedules_returns_array(self, session, created_schedule_id):
        """GET returns an array of schedules"""
        res = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/schedules")
        assert res.status_code == 200
        
        data = res.json()
        assert isinstance(data, list)
        
        # Should contain at least the fixture-created schedule
        schedule_ids = [s["schedule_id"] for s in data]
        assert created_schedule_id in schedule_ids
    
    def test_list_schedules_have_proper_fields(self, session, created_schedule_id):
        """Listed schedules have all required fields"""
        res = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/schedules")
        assert res.status_code == 200
        
        data = res.json()
        for schedule in data:
            assert "schedule_id" in schedule
            assert "workspace_id" in schedule
            assert "channel_id" in schedule
            assert "agent_key" in schedule
            assert "agent_name" in schedule
            assert "action_type" in schedule
            assert "interval_minutes" in schedule
            assert "enabled" in schedule


class TestScheduleUpdate:
    """Test PUT /api/schedules/{id} endpoint"""
    
    def test_toggle_enabled(self, session, created_schedule_id):
        """PUT toggles enabled status"""
        # Disable
        res = session.put(f"{BASE_URL}/api/schedules/{created_schedule_id}", json={
            "enabled": False
        })
        assert res.status_code == 200
        assert res.json()["enabled"] == False
        
        # Re-enable
        res = session.put(f"{BASE_URL}/api/schedules/{created_schedule_id}", json={
            "enabled": True
        })
        assert res.status_code == 200
        assert res.json()["enabled"] == True
    
    def test_update_interval(self, session, created_schedule_id):
        """PUT updates interval_minutes"""
        res = session.put(f"{BASE_URL}/api/schedules/{created_schedule_id}", json={
            "interval_minutes": 240
        })
        assert res.status_code == 200
        assert res.json()["interval_minutes"] == 240
        
        # Restore
        session.put(f"{BASE_URL}/api/schedules/{created_schedule_id}", json={
            "interval_minutes": 1440
        })
    
    def test_update_action_type(self, session, created_schedule_id):
        """PUT updates action_type"""
        res = session.put(f"{BASE_URL}/api/schedules/{created_schedule_id}", json={
            "action_type": "task_triage"
        })
        assert res.status_code == 200
        assert res.json()["action_type"] == "task_triage"
        
        # Restore
        session.put(f"{BASE_URL}/api/schedules/{created_schedule_id}", json={
            "action_type": "project_review"
        })
    
    def test_update_invalid_interval_returns_400(self, session, created_schedule_id):
        """PUT with invalid interval returns 400"""
        res = session.put(f"{BASE_URL}/api/schedules/{created_schedule_id}", json={
            "interval_minutes": 45  # Invalid
        })
        assert res.status_code == 400
        assert "Invalid interval" in res.json().get("detail", "")
    
    def test_update_nonexistent_returns_404(self, session):
        """PUT on nonexistent schedule returns 404"""
        res = session.put(f"{BASE_URL}/api/schedules/sched_nonexistent", json={
            "enabled": False
        })
        assert res.status_code == 404


class TestScheduleDelete:
    """Test DELETE /api/schedules/{id} endpoint"""
    
    def test_delete_schedule(self, session):
        """DELETE removes schedule"""
        # Create a schedule to delete
        payload = {
            "channel_id": TEST_CHANNEL_ID,
            "agent_key": "gemini",
            "action_type": "task_triage",
            "interval_minutes": 480,
            "enabled": True
        }
        create_res = session.post(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/schedules", json=payload)
        assert create_res.status_code == 200
        schedule_id = create_res.json()["schedule_id"]
        
        # Delete
        del_res = session.delete(f"{BASE_URL}/api/schedules/{schedule_id}")
        assert del_res.status_code == 200
        assert "deleted" in del_res.json().get("message", "").lower()
        
        # Verify deleted - listing should not contain it
        list_res = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/schedules")
        schedule_ids = [s["schedule_id"] for s in list_res.json()]
        assert schedule_id not in schedule_ids
    
    def test_delete_nonexistent_returns_404(self, session):
        """DELETE nonexistent schedule returns 404"""
        res = session.delete(f"{BASE_URL}/api/schedules/sched_nonexistent")
        assert res.status_code == 404


class TestScheduleManualTrigger:
    """Test POST /api/schedules/{id}/run endpoint"""
    
    def test_manual_trigger_returns_triggered_status(self, session, created_schedule_id):
        """POST /schedules/{id}/run returns status=triggered"""
        res = session.post(f"{BASE_URL}/api/schedules/{created_schedule_id}/run")
        assert res.status_code == 200
        
        data = res.json()
        assert data.get("status") == "triggered"
        assert data.get("schedule_id") == created_schedule_id
    
    def test_trigger_nonexistent_returns_404(self, session):
        """POST /run on nonexistent schedule returns 404"""
        res = session.post(f"{BASE_URL}/api/schedules/sched_nonexistent/run")
        assert res.status_code == 404


class TestScheduleHistory:
    """Test GET /api/schedules/{id}/history endpoint"""
    
    def test_get_history_returns_array(self, session, created_schedule_id):
        """GET /schedules/{id}/history returns an array"""
        # Trigger once to create history (may fail due to missing API key but creates record)
        session.post(f"{BASE_URL}/api/schedules/{created_schedule_id}/run")
        time.sleep(1)  # Brief wait for async task to create record
        
        res = session.get(f"{BASE_URL}/api/schedules/{created_schedule_id}/history")
        assert res.status_code == 200
        
        data = res.json()
        assert isinstance(data, list)
    
    def test_history_entries_have_proper_structure(self, session, created_schedule_id):
        """History entries have run_id, schedule_id, status, started_at"""
        res = session.get(f"{BASE_URL}/api/schedules/{created_schedule_id}/history")
        assert res.status_code == 200
        
        data = res.json()
        if len(data) > 0:
            entry = data[0]
            assert "run_id" in entry
            assert "schedule_id" in entry
            assert "status" in entry
            assert "started_at" in entry


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
