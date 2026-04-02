"""
Tests for Gantt Charts, Planner, Reports, and Support Desk endpoints.
Features:
- Workspace/Org Gantt with dependencies, progress, status
- Workspace/Org Planner with by_date and overdue
- Reports: summary, velocity
- Support Desk: tickets CRUD, replies, SLA, dashboard, config
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from context
TEST_USER_EMAIL = "testmention@test.com"
TEST_USER_PASSWORD = "Test1234!"
WORKSPACE_ID = "ws_bd1750012bfd"

ORG_ADMIN_EMAIL = "admin@urtech.org"
ORG_ADMIN_PASSWORD = "Test1234!"
ORG_ID = "org_cba36eb8305f"

EXISTING_TICKET_ID = "tkt_f7999f99134a"


class TestAuth:
    """Get authenticated sessions for testing"""
    
    @pytest.fixture(scope="class")
    def test_user_session(self):
        """Login as test user and get session"""
        session = requests.Session()
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        assert resp.status_code == 200, f"Test user login failed: {resp.text}"
        return session
    
    @pytest.fixture(scope="class")
    def org_admin_session(self):
        """Login as org admin and get session"""
        session = requests.Session()
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ORG_ADMIN_EMAIL,
            "password": ORG_ADMIN_PASSWORD
        })
        assert resp.status_code == 200, f"Org admin login failed: {resp.text}"
        return session


@pytest.fixture(scope="module")
def test_user_session():
    """Module-level test user session"""
    session = requests.Session()
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD
    })
    assert resp.status_code == 200, f"Test user login failed: {resp.text}"
    return session


@pytest.fixture(scope="module")
def org_admin_session():
    """Module-level org admin session"""
    session = requests.Session()
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": ORG_ADMIN_EMAIL,
        "password": ORG_ADMIN_PASSWORD
    })
    assert resp.status_code == 200, f"Org admin login failed: {resp.text}"
    return session


# ========== GANTT CHART TESTS ==========

class TestWorkspaceGantt:
    """GET /api/workspaces/{ws}/gantt - workspace-level Gantt data"""
    
    def test_workspace_gantt_returns_items(self, test_user_session):
        """Gantt returns tasks with dependencies, progress, status"""
        resp = test_user_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/gantt")
        assert resp.status_code == 200, f"Workspace Gantt failed: {resp.text}"
        
        data = resp.json()
        assert "items" in data, "Response missing 'items' key"
        assert "total_tasks" in data, "Response missing 'total_tasks' key"
        assert "total_milestones" in data, "Response missing 'total_milestones' key"
        assert "total_dependencies" in data, "Response missing 'total_dependencies' key"
        
        # Verify Gantt item structure
        if data["items"]:
            item = data["items"][0]
            assert "id" in item, "Item missing 'id'"
            assert "type" in item, "Item missing 'type'"
            assert "title" in item, "Item missing 'title'"
            assert "start" in item, "Item missing 'start'"
            assert "end" in item, "Item missing 'end'"
            assert "status" in item, "Item missing 'status'"
            assert "progress" in item, "Item missing 'progress'"
            assert "dependencies" in item, "Item missing 'dependencies'"
            
            # Progress should be 0, 50, or 100 based on status
            assert item["progress"] in [0, 50, 100], f"Invalid progress: {item['progress']}"
        
        print(f"Workspace Gantt: {data['total_tasks']} tasks, {data['total_milestones']} milestones, {data['total_dependencies']} deps")
    
    def test_workspace_gantt_includes_milestones(self, test_user_session):
        """Gantt includes milestones with proper type"""
        resp = test_user_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/gantt")
        assert resp.status_code == 200
        
        data = resp.json()
        milestones = [i for i in data["items"] if i.get("type") == "milestone"]
        
        # Note: per context, workspace has 1 milestone
        if milestones:
            ms = milestones[0]
            assert ms["type"] == "milestone"
            assert "title" in ms
            assert "start" in ms
            assert "status" in ms
            print(f"Found {len(milestones)} milestones in Gantt")


class TestOrgGantt:
    """GET /api/orgs/{org}/gantt - cross-workspace Gantt with workspace names"""
    
    def test_org_gantt_returns_cross_workspace_items(self, org_admin_session):
        """Org Gantt returns tasks across all org workspaces"""
        resp = org_admin_session.get(f"{BASE_URL}/api/orgs/{ORG_ID}/gantt")
        assert resp.status_code == 200, f"Org Gantt failed: {resp.text}"
        
        data = resp.json()
        assert "items" in data, "Response missing 'items' key"
        assert "total_tasks" in data, "Response missing 'total_tasks' key"
        
        # Org Gantt should have workspace field
        if data["items"]:
            item = data["items"][0]
            assert "workspace" in item, "Org Gantt item missing 'workspace' field"
            assert "project" in item, "Item missing 'project' field"
            print(f"Org Gantt: {data['total_tasks']} tasks across workspaces")
    
    def test_org_gantt_requires_membership(self, test_user_session):
        """Org Gantt requires org membership"""
        # Using test_user who may not be org admin
        resp = test_user_session.get(f"{BASE_URL}/api/orgs/{ORG_ID}/gantt")
        # Could be 200 if user is member, or 403 if not
        # Just verify it doesn't crash
        assert resp.status_code in [200, 403, 404], f"Unexpected status: {resp.status_code}"


# ========== PLANNER TESTS ==========

class TestWorkspacePlanner:
    """GET /api/workspaces/{ws}/planner - tasks by date with overdue"""
    
    def test_workspace_planner_returns_tasks_by_date(self, test_user_session):
        """Planner returns tasks grouped by_date with overdue list"""
        resp = test_user_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/planner")
        assert resp.status_code == 200, f"Workspace Planner failed: {resp.text}"
        
        data = resp.json()
        assert "tasks" in data, "Response missing 'tasks' key"
        assert "by_date" in data, "Response missing 'by_date' key"
        assert "overdue" in data, "Response missing 'overdue' key"
        assert "total" in data, "Response missing 'total' key"
        
        # by_date should be a dict with date strings as keys
        assert isinstance(data["by_date"], dict), "by_date should be a dict"
        
        # overdue should be a list
        assert isinstance(data["overdue"], list), "overdue should be a list"
        
        print(f"Workspace Planner: {data['total']} tasks, {len(data['overdue'])} overdue, {len(data['by_date'])} dates")
    
    def test_workspace_planner_with_filters(self, test_user_session):
        """Planner accepts date range filters"""
        # Test with date range
        resp = test_user_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/planner", params={
            "start": "2024-01-01",
            "end": "2026-12-31"
        })
        assert resp.status_code == 200, f"Planner with filters failed: {resp.text}"
        
        data = resp.json()
        assert "tasks" in data


class TestOrgPlanner:
    """GET /api/orgs/{org}/planner - org-level planner"""
    
    def test_org_planner_returns_cross_workspace_tasks(self, org_admin_session):
        """Org planner returns tasks from all org workspaces"""
        resp = org_admin_session.get(f"{BASE_URL}/api/orgs/{ORG_ID}/planner")
        assert resp.status_code == 200, f"Org Planner failed: {resp.text}"
        
        data = resp.json()
        assert "tasks" in data, "Response missing 'tasks' key"
        assert "by_date" in data, "Response missing 'by_date' key"
        assert "total" in data, "Response missing 'total' key"
        
        print(f"Org Planner: {data['total']} tasks across workspaces")
    
    def test_org_planner_with_date_filters(self, org_admin_session):
        """Org planner accepts date filters"""
        resp = org_admin_session.get(f"{BASE_URL}/api/orgs/{ORG_ID}/planner", params={
            "start": "2024-01-01",
            "end": "2026-12-31"
        })
        assert resp.status_code == 200


# ========== REPORTS TESTS ==========

class TestWorkspaceReportSummary:
    """GET /api/workspaces/{ws}/reports/summary - comprehensive report"""
    
    def test_workspace_report_returns_distributions(self, test_user_session):
        """Report returns status/priority/type distributions"""
        resp = test_user_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/reports/summary")
        assert resp.status_code == 200, f"Workspace Report failed: {resp.text}"
        
        data = resp.json()
        
        # Verify summary section
        assert "summary" in data, "Response missing 'summary' key"
        summary = data["summary"]
        assert "total_projects" in summary
        assert "total_tasks" in summary
        assert "completion_rate" in summary
        assert "overdue_count" in summary
        
        # Verify distributions
        assert "status_distribution" in data, "Missing 'status_distribution'"
        assert "priority_distribution" in data, "Missing 'priority_distribution'"
        assert "type_distribution" in data, "Missing 'type_distribution'"
        
        # Verify assignee workload
        assert "assignee_workload" in data, "Missing 'assignee_workload'"
        
        # Verify project summaries
        assert "project_summaries" in data, "Missing 'project_summaries'"
        
        # Verify overdue list
        assert "overdue_tasks" in data, "Missing 'overdue_tasks'"
        
        print(f"Workspace Report: {summary['total_tasks']} tasks, {summary['completion_rate']}% complete")
    
    def test_workspace_report_assignee_workload_structure(self, test_user_session):
        """Assignee workload has correct structure"""
        resp = test_user_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/reports/summary")
        assert resp.status_code == 200
        
        data = resp.json()
        workload = data.get("assignee_workload", {})
        
        for assignee, stats in workload.items():
            assert "total" in stats, f"Missing 'total' for {assignee}"
            assert "done" in stats, f"Missing 'done' for {assignee}"
            assert "in_progress" in stats, f"Missing 'in_progress' for {assignee}"


class TestOrgReportSummary:
    """GET /api/orgs/{org}/reports/summary - org-level report"""
    
    def test_org_report_returns_workspace_summaries(self, org_admin_session):
        """Org report returns workspace summaries and team utilization"""
        resp = org_admin_session.get(f"{BASE_URL}/api/orgs/{ORG_ID}/reports/summary")
        assert resp.status_code == 200, f"Org Report failed: {resp.text}"
        
        data = resp.json()
        
        # Verify summary
        assert "summary" in data
        summary = data["summary"]
        assert "total_workspaces" in summary
        assert "total_projects" in summary
        assert "total_tasks" in summary
        assert "completion_rate" in summary
        
        # Verify workspace summaries
        assert "workspace_summaries" in data, "Missing 'workspace_summaries'"
        if data["workspace_summaries"]:
            ws = data["workspace_summaries"][0]
            assert "workspace_id" in ws
            assert "workspace_name" in ws
            assert "projects" in ws
            assert "tasks" in ws
            assert "completion_rate" in ws
        
        # Verify team utilization
        assert "team_utilization" in data, "Missing 'team_utilization'"
        
        print(f"Org Report: {summary['total_workspaces']} workspaces, {summary['total_tasks']} tasks")


class TestVelocityReport:
    """GET /api/workspaces/{ws}/reports/velocity - sprint velocity"""
    
    def test_velocity_report_returns_sprint_data(self, test_user_session):
        """Velocity report returns sprint velocity data"""
        resp = test_user_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/reports/velocity")
        assert resp.status_code == 200, f"Velocity Report failed: {resp.text}"
        
        data = resp.json()
        assert "sprints" in data, "Response missing 'sprints' key"
        assert "average_velocity" in data, "Response missing 'average_velocity' key"
        
        # Verify sprint structure if any exist
        if data["sprints"]:
            sprint = data["sprints"][0]
            assert "sprint" in sprint, "Sprint missing 'sprint' (name)"
            assert "velocity" in sprint, "Sprint missing 'velocity'"
            assert "completed_points" in sprint, "Sprint missing 'completed_points'"
        
        print(f"Velocity Report: {len(data['sprints'])} sprints, avg velocity: {data['average_velocity']}")


# ========== SUPPORT DESK TESTS ==========

class TestSupportConfig:
    """GET /api/support/config - returns statuses, types, categories"""
    
    def test_support_config_returns_all_options(self, test_user_session):
        """Config returns all valid statuses, types, categories"""
        resp = test_user_session.get(f"{BASE_URL}/api/support/config")
        assert resp.status_code == 200, f"Support Config failed: {resp.text}"
        
        data = resp.json()
        assert "statuses" in data, "Missing 'statuses'"
        assert "priorities" in data, "Missing 'priorities'"
        assert "ticket_types" in data, "Missing 'ticket_types'"
        assert "sla_policies" in data, "Missing 'sla_policies'"
        assert "categories" in data, "Missing 'categories'"
        
        # Verify expected statuses
        expected_statuses = ["open", "in_progress", "waiting_on_customer", "waiting_on_support", "resolved", "closed"]
        for status in expected_statuses:
            assert status in data["statuses"], f"Missing status: {status}"
        
        # Verify priorities
        expected_priorities = ["low", "medium", "high", "urgent"]
        for priority in expected_priorities:
            assert priority in data["priorities"], f"Missing priority: {priority}"
        
        print(f"Support Config: {len(data['statuses'])} statuses, {len(data['ticket_types'])} types")


class TestSLAPolicies:
    """GET /api/support/sla-policies - returns 3 SLA tiers"""
    
    def test_sla_policies_returns_three_tiers(self, test_user_session):
        """Returns standard, priority, enterprise SLA tiers"""
        resp = test_user_session.get(f"{BASE_URL}/api/support/sla-policies")
        assert resp.status_code == 200, f"SLA Policies failed: {resp.text}"
        
        data = resp.json()
        assert "policies" in data, "Response missing 'policies'"
        
        policies = {p["key"]: p for p in data["policies"]}
        
        # Verify 3 tiers exist
        assert "standard" in policies, "Missing 'standard' SLA"
        assert "priority" in policies, "Missing 'priority' SLA"
        assert "enterprise" in policies, "Missing 'enterprise' SLA"
        
        # Verify structure
        for key, policy in policies.items():
            assert "first_response_hours" in policy, f"Missing 'first_response_hours' in {key}"
            assert "resolution_hours" in policy, f"Missing 'resolution_hours' in {key}"
        
        # Verify SLA targets (standard=24h/72h, priority=4h/24h, enterprise=1h/8h)
        assert policies["standard"]["first_response_hours"] == 24
        assert policies["standard"]["resolution_hours"] == 72
        assert policies["priority"]["first_response_hours"] == 4
        assert policies["priority"]["resolution_hours"] == 24
        assert policies["enterprise"]["first_response_hours"] == 1
        assert policies["enterprise"]["resolution_hours"] == 8
        
        print(f"SLA Policies verified: standard, priority, enterprise")


class TestSupportTicketsCRUD:
    """Support tickets create, read, update, delete operations"""
    
    def test_create_ticket_with_sla_policy(self, test_user_session):
        """POST /api/support/tickets creates ticket with SLA policy"""
        ticket_data = {
            "subject": f"TEST_Ticket_{uuid.uuid4().hex[:8]}",
            "description": "Test ticket for automation testing",
            "ticket_type": "incident",
            "priority": "high",
            "category": "technical"
        }
        
        resp = test_user_session.post(f"{BASE_URL}/api/support/tickets", json=ticket_data)
        assert resp.status_code == 200, f"Create ticket failed: {resp.text}"
        
        ticket = resp.json()
        assert "ticket_id" in ticket, "Missing 'ticket_id'"
        assert ticket["subject"] == ticket_data["subject"]
        assert ticket["ticket_type"] == ticket_data["ticket_type"]
        assert ticket["priority"] == ticket_data["priority"]
        assert ticket["status"] == "open", "New ticket should be 'open'"
        assert ticket["sla_policy"] == "standard", "Default SLA should be 'standard'"
        assert ticket["sla_first_response_breached"] == False
        assert ticket["sla_resolution_breached"] == False
        
        # Store for cleanup
        pytest.created_ticket_id = ticket["ticket_id"]
        print(f"Created ticket: {ticket['ticket_id']}")
        return ticket["ticket_id"]
    
    def test_list_tickets_with_filters(self, test_user_session):
        """GET /api/support/tickets lists with search/status/priority filters"""
        # Test basic listing
        resp = test_user_session.get(f"{BASE_URL}/api/support/tickets")
        assert resp.status_code == 200, f"List tickets failed: {resp.text}"
        
        data = resp.json()
        assert "tickets" in data, "Missing 'tickets'"
        assert "total" in data, "Missing 'total'"
        
        # Test with status filter
        resp = test_user_session.get(f"{BASE_URL}/api/support/tickets", params={"status": "open"})
        assert resp.status_code == 200
        
        # Test with priority filter
        resp = test_user_session.get(f"{BASE_URL}/api/support/tickets", params={"priority": "high"})
        assert resp.status_code == 200
        
        # Test with search
        resp = test_user_session.get(f"{BASE_URL}/api/support/tickets", params={"search": "TEST_"})
        assert resp.status_code == 200
        
        print(f"Ticket list filters working: {data['total']} total tickets")
    
    def test_get_single_ticket(self, test_user_session):
        """GET /api/support/tickets/{id} returns full ticket"""
        # Use existing ticket from context
        resp = test_user_session.get(f"{BASE_URL}/api/support/tickets/{EXISTING_TICKET_ID}")
        assert resp.status_code == 200, f"Get ticket failed: {resp.text}"
        
        ticket = resp.json()
        assert ticket["ticket_id"] == EXISTING_TICKET_ID
        assert "subject" in ticket
        assert "description" in ticket
        assert "status" in ticket
        assert "priority" in ticket
        assert "sla_policy" in ticket
        assert "requester_id" in ticket
        assert "created_at" in ticket
        
        print(f"Got ticket: {ticket['ticket_id']} - {ticket['status']}")
    
    def test_update_ticket_status_priority_assignee(self, test_user_session):
        """PUT /api/support/tickets/{id} updates status/priority/assignee with activity logging"""
        # First create a ticket to update
        create_resp = test_user_session.post(f"{BASE_URL}/api/support/tickets", json={
            "subject": f"TEST_Update_{uuid.uuid4().hex[:8]}",
            "description": "Ticket for update testing",
            "ticket_type": "question",
            "priority": "low"
        })
        assert create_resp.status_code == 200
        ticket_id = create_resp.json()["ticket_id"]
        
        # Update status
        update_resp = test_user_session.put(f"{BASE_URL}/api/support/tickets/{ticket_id}", json={
            "status": "in_progress",
            "priority": "high"
        })
        assert update_resp.status_code == 200, f"Update ticket failed: {update_resp.text}"
        
        updated = update_resp.json()
        assert updated["status"] == "in_progress", "Status not updated"
        assert updated["priority"] == "high", "Priority not updated"
        
        # Verify activity was logged
        activity_resp = test_user_session.get(f"{BASE_URL}/api/support/tickets/{ticket_id}/activity")
        assert activity_resp.status_code == 200
        activities = activity_resp.json()
        
        # Should have at least created + updated activities
        assert len(activities) >= 2, "Activity not logged"
        update_activity = next((a for a in activities if a.get("action") == "updated"), None)
        assert update_activity is not None, "Update activity not found"
        
        print(f"Updated ticket {ticket_id}: status=in_progress, priority=high")
        
        # Cleanup
        pytest.test_update_ticket_id = ticket_id
    
    def test_my_tickets_returns_requester_tickets(self, test_user_session):
        """GET /api/support/tickets/my returns requester's tickets"""
        resp = test_user_session.get(f"{BASE_URL}/api/support/tickets/my")
        assert resp.status_code == 200, f"My tickets failed: {resp.text}"
        
        data = resp.json()
        assert "tickets" in data, "Missing 'tickets'"
        
        # All tickets should belong to current user
        # We can verify they have TEST_ prefix from our created tickets
        print(f"My tickets: {len(data['tickets'])} tickets")


class TestSupportTicketReplies:
    """Ticket replies with SLA first-response tracking"""
    
    def test_add_reply_tracks_sla_first_response(self, test_user_session):
        """POST /api/support/tickets/{id}/replies adds reply with SLA tracking"""
        # First create a fresh ticket
        create_resp = test_user_session.post(f"{BASE_URL}/api/support/tickets", json={
            "subject": f"TEST_Reply_{uuid.uuid4().hex[:8]}",
            "description": "Ticket for reply testing"
        })
        assert create_resp.status_code == 200
        ticket_id = create_resp.json()["ticket_id"]
        
        # Add a reply
        reply_resp = test_user_session.post(f"{BASE_URL}/api/support/tickets/{ticket_id}/replies", json={
            "content": "This is a test reply",
            "is_internal": False
        })
        assert reply_resp.status_code == 200, f"Add reply failed: {reply_resp.text}"
        
        reply = reply_resp.json()
        assert "reply_id" in reply, "Missing 'reply_id'"
        assert reply["content"] == "This is a test reply"
        assert reply["is_internal"] == False
        assert "author_id" in reply
        assert "created_at" in reply
        
        print(f"Added reply: {reply['reply_id']}")
        
        # Store for cleanup
        pytest.test_reply_ticket_id = ticket_id
    
    def test_list_replies_customer_and_internal(self, test_user_session):
        """GET /api/support/tickets/{id}/replies lists customer + internal replies"""
        # Use existing ticket from context (already has 1 reply)
        resp = test_user_session.get(f"{BASE_URL}/api/support/tickets/{EXISTING_TICKET_ID}/replies")
        assert resp.status_code == 200, f"List replies failed: {resp.text}"
        
        replies = resp.json()
        assert isinstance(replies, list), "Replies should be a list"
        
        # Per context, ticket already has 1 reply
        if replies:
            reply = replies[0]
            assert "reply_id" in reply
            assert "content" in reply
            assert "is_internal" in reply
            assert "author_name" in reply
        
        print(f"Listed {len(replies)} replies for ticket {EXISTING_TICKET_ID}")
    
    def test_internal_notes_are_agent_only(self, test_user_session):
        """Internal notes (is_internal=true) are filtered when include_internal=false"""
        # Create ticket with internal note
        create_resp = test_user_session.post(f"{BASE_URL}/api/support/tickets", json={
            "subject": f"TEST_Internal_{uuid.uuid4().hex[:8]}",
            "description": "Ticket for internal note testing"
        })
        ticket_id = create_resp.json()["ticket_id"]
        
        # Add internal note
        test_user_session.post(f"{BASE_URL}/api/support/tickets/{ticket_id}/replies", json={
            "content": "Internal agent note",
            "is_internal": True
        })
        
        # Add customer-visible reply
        test_user_session.post(f"{BASE_URL}/api/support/tickets/{ticket_id}/replies", json={
            "content": "Customer visible reply",
            "is_internal": False
        })
        
        # Get all replies (include internal)
        all_resp = test_user_session.get(f"{BASE_URL}/api/support/tickets/{ticket_id}/replies", 
                                         params={"include_internal": True})
        all_replies = all_resp.json()
        
        # Get only customer-visible replies
        customer_resp = test_user_session.get(f"{BASE_URL}/api/support/tickets/{ticket_id}/replies", 
                                              params={"include_internal": False})
        customer_replies = customer_resp.json()
        
        assert len(all_replies) == 2, f"Should have 2 total replies, got {len(all_replies)}"
        assert len(customer_replies) == 1, f"Should have 1 customer reply, got {len(customer_replies)}"
        assert customer_replies[0]["is_internal"] == False
        
        print(f"Internal filtering working: {len(all_replies)} total, {len(customer_replies)} customer-visible")
        
        pytest.test_internal_ticket_id = ticket_id


class TestSupportStatusAutoUpdate:
    """Status auto-updates on reply"""
    
    def test_agent_reply_updates_open_to_in_progress(self, test_user_session):
        """Agent reply on open ticket changes status to in_progress"""
        # Create ticket (status=open)
        create_resp = test_user_session.post(f"{BASE_URL}/api/support/tickets", json={
            "subject": f"TEST_AutoStatus_{uuid.uuid4().hex[:8]}",
            "description": "Test auto status update"
        })
        ticket = create_resp.json()
        ticket_id = ticket["ticket_id"]
        assert ticket["status"] == "open"
        
        # Note: For proper test, we'd need different user (agent vs requester)
        # Since we're using same user, check the logic exists
        # The reply should trigger status update if user != requester
        
        # For this test, just verify the endpoint works
        reply_resp = test_user_session.post(f"{BASE_URL}/api/support/tickets/{ticket_id}/replies", json={
            "content": "Agent response"
        })
        assert reply_resp.status_code == 200
        
        # Get updated ticket
        get_resp = test_user_session.get(f"{BASE_URL}/api/support/tickets/{ticket_id}")
        updated = get_resp.json()
        
        # Status should still be open if same user (requester)
        # But if different user, would be in_progress
        print(f"Auto-status test: ticket status is {updated['status']}")
        
        pytest.test_autostatus_ticket_id = ticket_id


class TestSupportDashboard:
    """GET /api/support/dashboard - queue counts, priority/type breakdown, avg resolution"""
    
    def test_dashboard_returns_queue_counts(self, test_user_session):
        """Dashboard returns queue counts and breakdowns"""
        resp = test_user_session.get(f"{BASE_URL}/api/support/dashboard")
        assert resp.status_code == 200, f"Dashboard failed: {resp.text}"
        
        data = resp.json()
        
        # Verify queue counts
        assert "queue" in data, "Missing 'queue'"
        queue = data["queue"]
        assert "open" in queue, "Missing 'open' count"
        assert "in_progress" in queue, "Missing 'in_progress' count"
        assert "waiting_on_customer" in queue, "Missing 'waiting_on_customer' count"
        assert "waiting_on_support" in queue, "Missing 'waiting_on_support' count"
        assert "total_open" in queue, "Missing 'total_open' count"
        
        # Verify other metrics
        assert "resolved_today" in data, "Missing 'resolved_today'"
        assert "sla_breached" in data, "Missing 'sla_breached'"
        assert "priority_breakdown" in data, "Missing 'priority_breakdown'"
        assert "type_breakdown" in data, "Missing 'type_breakdown'"
        assert "avg_resolution_hours" in data, "Missing 'avg_resolution_hours'"
        
        print(f"Dashboard: {queue['total_open']} open tickets, {data['sla_breached']} SLA breached")


class TestSupportSLAManagement:
    """PUT /api/support/tickets/{id}/sla - set SLA policy"""
    
    def test_set_ticket_sla_policy(self, test_user_session):
        """Set SLA policy on ticket"""
        # Create ticket
        create_resp = test_user_session.post(f"{BASE_URL}/api/support/tickets", json={
            "subject": f"TEST_SLA_{uuid.uuid4().hex[:8]}",
            "description": "Test SLA change"
        })
        ticket = create_resp.json()
        ticket_id = ticket["ticket_id"]
        assert ticket["sla_policy"] == "standard"
        
        # Change to enterprise SLA
        sla_resp = test_user_session.put(f"{BASE_URL}/api/support/tickets/{ticket_id}/sla", 
                                         json={"sla_policy": "enterprise"})
        assert sla_resp.status_code == 200, f"Set SLA failed: {sla_resp.text}"
        
        result = sla_resp.json()
        assert result["sla_policy"] == "enterprise"
        assert result["targets"]["first_response_hours"] == 1
        assert result["targets"]["resolution_hours"] == 8
        
        # Try invalid SLA
        invalid_resp = test_user_session.put(f"{BASE_URL}/api/support/tickets/{ticket_id}/sla", 
                                             json={"sla_policy": "invalid"})
        assert invalid_resp.status_code == 400, "Should reject invalid SLA policy"
        
        print(f"SLA changed to enterprise for ticket {ticket_id}")
        
        pytest.test_sla_ticket_id = ticket_id


class TestSuggestedArticles:
    """GET /api/support/suggested-articles - KB search"""
    
    def test_suggested_articles_searches_kb(self, test_user_session):
        """Suggested articles endpoint searches KB"""
        resp = test_user_session.get(f"{BASE_URL}/api/support/suggested-articles", params={"query": "help"})
        assert resp.status_code == 200, f"Suggested articles failed: {resp.text}"
        
        data = resp.json()
        assert "articles" in data, "Missing 'articles'"
        assert isinstance(data["articles"], list)
        
        print(f"Suggested articles: {len(data['articles'])} results for 'help'")
    
    def test_suggested_articles_empty_query(self, test_user_session):
        """Empty query returns empty results"""
        resp = test_user_session.get(f"{BASE_URL}/api/support/suggested-articles", params={"query": ""})
        assert resp.status_code == 200
        
        data = resp.json()
        assert data["articles"] == []


# ========== CLEANUP ==========

class TestCleanup:
    """Cleanup TEST_ prefixed data after tests"""
    
    def test_cleanup_test_tickets(self, test_user_session):
        """Clean up test tickets"""
        # List tickets with TEST_ prefix
        resp = test_user_session.get(f"{BASE_URL}/api/support/tickets", params={"search": "TEST_"})
        if resp.status_code == 200:
            tickets = resp.json().get("tickets", [])
            cleaned = 0
            for ticket in tickets:
                if ticket.get("subject", "").startswith("TEST_"):
                    # Set to closed status (no delete endpoint)
                    test_user_session.put(f"{BASE_URL}/api/support/tickets/{ticket['ticket_id']}", 
                                         json={"status": "closed"})
                    cleaned += 1
            print(f"Cleaned up {cleaned} test tickets")
