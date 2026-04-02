from conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, BASE_URL
"""
Iteration 91 — Planner Module Testing
Tests for:
- POST /api/workspaces/:id/tasks — create task with due_date and priority fields
- GET /api/workspaces/:id/planner?start=YYYY-MM-DD&end=YYYY-MM-DD — returns tasks with due_date grouped by_date
- PUT /api/tasks/:id — update task status and due_date fields
- Planner endpoint sources both project_tasks and tasks collections
- Overdue detection in planner response
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
WORKSPACE_ID = "ws_a92cb83bfdb2"
ADMIN_EMAIL = TEST_ADMIN_EMAIL
ADMIN_PASSWORD = "test"


@pytest.fixture(scope="module")
def admin_session():
    """Create authenticated admin session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login as admin
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed: {resp.status_code} - {resp.text}")
    return session


class TestPlannerEndpoint:
    """Tests for GET /api/workspaces/:id/planner"""
    
    def test_planner_returns_tasks_with_dates(self, admin_session):
        """Verify planner endpoint returns tasks with by_date grouping"""
        # Get March 2026 data
        start = "2026-03-01"
        end = "2026-03-31"
        resp = admin_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/planner?start={start}&end={end}")
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Verify response structure
        assert "tasks" in data, "Response should include 'tasks' array"
        assert "by_date" in data, "Response should include 'by_date' dict for date grouping"
        assert "overdue" in data, "Response should include 'overdue' array"
        assert "total" in data, "Response should include 'total' count"
        
        print(f"Planner returned {data['total']} tasks")
        print(f"Tasks by date: {list(data['by_date'].keys())}")
        print(f"Overdue count: {len(data['overdue'])}")
    
    def test_planner_groups_tasks_by_date(self, admin_session):
        """Verify tasks are properly grouped by due date"""
        start = "2026-03-01"
        end = "2026-03-31"
        resp = admin_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/planner?start={start}&end={end}")
        
        assert resp.status_code == 200
        data = resp.json()
        
        by_date = data.get("by_date", {})
        tasks = data.get("tasks", [])
        
        # Verify each task in tasks array exists in by_date
        for task in tasks:
            due_date = task.get("due_date", "")[:10]
            if due_date in by_date:
                task_ids_for_date = [t.get("task_id") for t in by_date[due_date]]
                assert task.get("task_id") in task_ids_for_date, f"Task {task.get('task_id')} not found in by_date for {due_date}"
    
    def test_planner_detects_overdue_tasks(self, admin_session):
        """Verify overdue detection works correctly"""
        # Use a date range that includes past dates
        today = datetime.now()
        start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
        end = today.strftime("%Y-%m-%d")
        
        resp = admin_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/planner?start={start}&end={end}")
        
        assert resp.status_code == 200
        data = resp.json()
        
        overdue = data.get("overdue", [])
        today_str = today.strftime("%Y-%m-%d")
        
        # If there are overdue tasks, verify they have past due dates and not-done status
        for task in overdue:
            due_date = task.get("due_date", "")[:10]
            status = task.get("status", "")
            assert due_date < today_str, f"Overdue task {task.get('task_id')} should have past due date"
            assert status not in ("done", "completed"), f"Overdue task {task.get('task_id')} should not be done"
        
        print(f"Found {len(overdue)} overdue tasks")
    
    def test_planner_date_filter(self, admin_session):
        """Verify date filtering works correctly"""
        # Query narrow date range
        resp = admin_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/planner?start=2026-03-10&end=2026-03-15")
        
        assert resp.status_code == 200
        data = resp.json()
        
        tasks = data.get("tasks", [])
        
        # All tasks should have due dates within range (or None if api doesn't filter strictly)
        for task in tasks:
            due = task.get("due_date", "")[:10]
            if due:
                assert due >= "2026-03-10" and due <= "2026-03-15", f"Task {task.get('task_id')} due date {due} outside range"


class TestTaskCreation:
    """Tests for POST /api/workspaces/:id/tasks with due_date and priority"""
    
    def test_create_task_with_due_date(self, admin_session):
        """Create task with due_date field"""
        unique_id = uuid.uuid4().hex[:8]
        payload = {
            "title": f"TEST_Planner_Task_{unique_id}",
            "due_date": "2026-03-20",
            "priority": "high",
            "status": "todo"
        }
        
        resp = admin_session.post(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/tasks", json=payload)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        task = resp.json()
        
        # Verify task fields
        assert task.get("title") == payload["title"]
        assert task.get("due_date") == payload["due_date"]
        assert task.get("priority") == payload["priority"]
        assert task.get("status") == payload["status"]
        assert "task_id" in task
        
        print(f"Created task: {task.get('task_id')} with due_date={task.get('due_date')}")
        
        # Store for cleanup
        TestTaskCreation.created_task_id = task.get("task_id")
        return task
    
    def test_task_appears_in_planner(self, admin_session):
        """Verify newly created task appears in planner query"""
        task_id = getattr(TestTaskCreation, 'created_task_id', None)
        if not task_id:
            pytest.skip("No task created in previous test")
        
        # Query planner for March 2026
        resp = admin_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/planner?start=2026-03-01&end=2026-03-31")
        
        assert resp.status_code == 200
        data = resp.json()
        
        tasks = data.get("tasks", [])
        task_ids = [t.get("task_id") for t in tasks]
        
        assert task_id in task_ids, f"Created task {task_id} not found in planner results"
        
        # Verify task is in by_date for 2026-03-20
        by_date = data.get("by_date", {})
        tasks_on_date = by_date.get("2026-03-20", [])
        task_ids_on_date = [t.get("task_id") for t in tasks_on_date]
        
        assert task_id in task_ids_on_date, f"Created task not grouped under correct date"


class TestTaskUpdate:
    """Tests for PUT /api/tasks/:id with status and due_date"""
    
    def test_update_task_status(self, admin_session):
        """Update task status field"""
        task_id = getattr(TestTaskCreation, 'created_task_id', None)
        if not task_id:
            pytest.skip("No task created for update test")
        
        # Update status to done
        payload = {"status": "done"}
        resp = admin_session.put(f"{BASE_URL}/api/tasks/{task_id}", json=payload)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        task = resp.json()
        
        assert task.get("status") == "done", f"Expected status 'done', got '{task.get('status')}'"
        print(f"Updated task {task_id} status to: {task.get('status')}")
    
    def test_update_task_due_date(self, admin_session):
        """Update task due_date field"""
        task_id = getattr(TestTaskCreation, 'created_task_id', None)
        if not task_id:
            pytest.skip("No task created for update test")
        
        # Update due_date
        new_due_date = "2026-03-25"
        payload = {"due_date": new_due_date}
        resp = admin_session.put(f"{BASE_URL}/api/tasks/{task_id}", json=payload)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        task = resp.json()
        
        assert task.get("due_date") == new_due_date, f"Expected due_date '{new_due_date}', got '{task.get('due_date')}'"
        print(f"Updated task {task_id} due_date to: {task.get('due_date')}")
    
    def test_update_task_priority(self, admin_session):
        """Update task priority field"""
        task_id = getattr(TestTaskCreation, 'created_task_id', None)
        if not task_id:
            pytest.skip("No task created for update test")
        
        # Update priority
        payload = {"priority": "low"}
        resp = admin_session.put(f"{BASE_URL}/api/tasks/{task_id}", json=payload)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        task = resp.json()
        
        assert task.get("priority") == "low", f"Expected priority 'low', got '{task.get('priority')}'"
        print(f"Updated task {task_id} priority to: {task.get('priority')}")


class TestTaskCleanup:
    """Cleanup test tasks"""
    
    def test_delete_test_task(self, admin_session):
        """Delete the test task created during testing"""
        task_id = getattr(TestTaskCreation, 'created_task_id', None)
        if not task_id:
            pytest.skip("No task to delete")
        
        resp = admin_session.delete(f"{BASE_URL}/api/tasks/{task_id}")
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print(f"Deleted test task: {task_id}")


class TestPlannerSourceBothCollections:
    """Verify planner sources both project_tasks and tasks collections"""
    
    def test_planner_includes_workspace_tasks(self, admin_session):
        """Verify workspace-level tasks (from tasks collection) appear in planner"""
        # First create a workspace task
        unique_id = uuid.uuid4().hex[:8]
        payload = {
            "title": f"TEST_WS_Task_{unique_id}",
            "due_date": "2026-03-22",
            "priority": "medium",
            "status": "todo"
        }
        
        resp = admin_session.post(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/tasks", json=payload)
        assert resp.status_code == 200
        ws_task = resp.json()
        ws_task_id = ws_task.get("task_id")
        
        # Query planner
        resp = admin_session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/planner?start=2026-03-01&end=2026-03-31")
        assert resp.status_code == 200
        data = resp.json()
        
        # Check task is in planner
        tasks = data.get("tasks", [])
        found_task = next((t for t in tasks if t.get("task_id") == ws_task_id), None)
        
        assert found_task is not None, f"Workspace task {ws_task_id} not found in planner"
        assert found_task.get("source") == "workspace", f"Expected source 'workspace', got '{found_task.get('source')}'"
        
        # Cleanup
        admin_session.delete(f"{BASE_URL}/api/tasks/{ws_task_id}")
        print(f"Verified workspace task {ws_task_id} appears in planner with source='workspace'")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
