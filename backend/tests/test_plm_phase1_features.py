"""
Nexus PLM Phase 1 Features Tests - Iteration 33
Tests: Enhanced tasks with due dates, work item types, subtasks, comments, attachments, activity logs, My Tasks view

Features tested:
- Task creation with item_type (task/story/bug/epic/subtask), due_date, labels, story_points
- Subtask creation (parent_task_id) and subtask_count increment
- Task comments (add, list, delete) with comment_count tracking
- Task attachments (upload, list, get with data, delete) with attachment_count tracking
- Activity log (created, updated events) tracking changes
- My Tasks endpoint with filters (status, priority)
- Project config endpoint (item_types, statuses, priorities)
"""

import pytest
import requests
import os
import base64

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestPLMPhase1Setup:
    """Setup: Authentication and baseline verification"""
    
    @pytest.fixture(scope="class")
    def session(self):
        """Create authenticated session"""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        
        # Login with test credentials
        resp = s.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testmention@test.com",
            "password": "Test1234!"
        })
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        return s
    
    def test_login_success(self, session):
        """Verify authentication works"""
        resp = session.get(f"{BASE_URL}/api/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert "user_id" in data
        print(f"✓ Authenticated as user_id: {data['user_id']}")


class TestProjectConfig:
    """Test /api/project-config endpoint - returns item_types, statuses, priorities"""
    
    @pytest.fixture(scope="class")
    def session(self):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        resp = s.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testmention@test.com",
            "password": "Test1234!"
        })
        assert resp.status_code == 200
        return s
    
    def test_project_config_returns_item_types(self, session):
        """GET /api/project-config returns 5 item_types"""
        resp = session.get(f"{BASE_URL}/api/project-config")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "item_types" in data
        assert len(data["item_types"]) == 5
        
        # Verify all expected types
        type_keys = [t["key"] for t in data["item_types"]]
        assert "task" in type_keys
        assert "story" in type_keys
        assert "bug" in type_keys
        assert "epic" in type_keys
        assert "subtask" in type_keys
        
        # Verify structure
        for item_type in data["item_types"]:
            assert "key" in item_type
            assert "name" in item_type
            assert "color" in item_type
            assert "description" in item_type
        
        print(f"✓ item_types: {type_keys}")
    
    def test_project_config_returns_statuses(self, session):
        """GET /api/project-config returns 4 statuses"""
        resp = session.get(f"{BASE_URL}/api/project-config")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "statuses" in data
        assert len(data["statuses"]) == 4
        
        expected = ["todo", "in_progress", "review", "done"]
        assert data["statuses"] == expected
        print(f"✓ statuses: {data['statuses']}")
    
    def test_project_config_returns_priorities(self, session):
        """GET /api/project-config returns 4 priorities"""
        resp = session.get(f"{BASE_URL}/api/project-config")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "priorities" in data
        assert len(data["priorities"]) == 4
        
        expected = ["low", "medium", "high", "critical"]
        assert data["priorities"] == expected
        print(f"✓ priorities: {data['priorities']}")


class TestTaskCreationWithNewFields:
    """Test task creation with item_type, due_date, labels, story_points"""
    
    @pytest.fixture(scope="class")
    def session(self):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        resp = s.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testmention@test.com",
            "password": "Test1234!"
        })
        assert resp.status_code == 200
        return s
    
    def test_create_task_with_bug_type(self, session):
        """POST /api/projects/{id}/tasks with item_type=bug stores correctly"""
        project_id = "proj_4e216147ec29"
        
        resp = session.post(f"{BASE_URL}/api/projects/{project_id}/tasks", json={
            "title": "TEST_Bug with due date",
            "description": "Testing bug type creation",
            "item_type": "bug",
            "priority": "high",
            "due_date": "2026-02-15",
            "labels": ["critical", "frontend"],
            "story_points": 3
        })
        
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        # Verify all new fields stored correctly
        assert data["item_type"] == "bug"
        assert data["due_date"] == "2026-02-15"
        assert data["labels"] == ["critical", "frontend"]
        assert data["story_points"] == 3
        assert data["priority"] == "high"
        assert "task_id" in data
        
        # Verify counts initialized to 0
        assert data["subtask_count"] == 0
        assert data["comment_count"] == 0
        assert data["attachment_count"] == 0
        
        print(f"✓ Created bug task: {data['task_id']}")
        
        # Store for later tests
        session.test_bug_task_id = data["task_id"]
    
    def test_create_task_with_epic_type(self, session):
        """POST /api/projects/{id}/tasks with item_type=epic stores correctly"""
        project_id = "proj_4e216147ec29"
        
        resp = session.post(f"{BASE_URL}/api/projects/{project_id}/tasks", json={
            "title": "TEST_Epic for feature",
            "description": "Testing epic type creation",
            "item_type": "epic",
            "priority": "medium",
            "due_date": "2026-03-01",
            "labels": ["q1-release"],
            "story_points": 13
        })
        
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert data["item_type"] == "epic"
        assert data["due_date"] == "2026-03-01"
        assert data["story_points"] == 13
        
        print(f"✓ Created epic task: {data['task_id']}")
        session.test_epic_task_id = data["task_id"]
    
    def test_create_story_task(self, session):
        """POST /api/projects/{id}/tasks with item_type=story"""
        project_id = "proj_4e216147ec29"
        
        resp = session.post(f"{BASE_URL}/api/projects/{project_id}/tasks", json={
            "title": "TEST_User Story",
            "description": "As a user I want...",
            "item_type": "story",
            "priority": "medium",
            "story_points": 5
        })
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["item_type"] == "story"
        print(f"✓ Created story task: {data['task_id']}")
        session.test_story_task_id = data["task_id"]


class TestSubtasks:
    """Test subtask creation and retrieval"""
    
    @pytest.fixture(scope="class")
    def session(self):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        resp = s.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testmention@test.com",
            "password": "Test1234!"
        })
        assert resp.status_code == 200
        return s
    
    @pytest.fixture(scope="class")
    def parent_task(self, session):
        """Create a parent task for subtask tests"""
        project_id = "proj_4e216147ec29"
        resp = session.post(f"{BASE_URL}/api/projects/{project_id}/tasks", json={
            "title": "TEST_Parent Task for Subtasks",
            "description": "Parent task",
            "item_type": "task",
            "priority": "medium"
        })
        assert resp.status_code == 200
        return resp.json()
    
    def test_create_subtask_increments_parent_count(self, session, parent_task):
        """POST /api/projects/{id}/tasks with parent_task_id creates subtask and increments parent subtask_count"""
        project_id = "proj_4e216147ec29"
        parent_id = parent_task["task_id"]
        
        # Create first subtask
        resp = session.post(f"{BASE_URL}/api/projects/{project_id}/tasks", json={
            "title": "TEST_Subtask 1",
            "description": "First subtask",
            "item_type": "subtask",
            "parent_task_id": parent_id,
            "priority": "low"
        })
        
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert data["parent_task_id"] == parent_id
        assert data["item_type"] == "subtask"
        
        subtask1_id = data["task_id"]
        print(f"✓ Created subtask: {subtask1_id}")
        
        # Create second subtask
        resp2 = session.post(f"{BASE_URL}/api/projects/{project_id}/tasks", json={
            "title": "TEST_Subtask 2",
            "description": "Second subtask",
            "item_type": "subtask",
            "parent_task_id": parent_id,
            "priority": "medium"
        })
        
        assert resp2.status_code == 200
        subtask2_id = resp2.json()["task_id"]
        
        # Verify parent's subtask_count incremented
        parent_resp = session.get(f"{BASE_URL}/api/projects/{project_id}/tasks")
        assert parent_resp.status_code == 200
        
        tasks = parent_resp.json()
        parent = next((t for t in tasks if t["task_id"] == parent_id), None)
        assert parent is not None
        assert parent["subtask_count"] >= 2, f"Expected subtask_count >= 2, got {parent['subtask_count']}"
        
        print(f"✓ Parent subtask_count: {parent['subtask_count']}")
        
        # Store for next test
        session.parent_task_id = parent_id
    
    def test_get_subtasks(self, session, parent_task):
        """GET /api/tasks/{id}/subtasks returns child tasks"""
        parent_id = parent_task["task_id"]
        
        resp = session.get(f"{BASE_URL}/api/tasks/{parent_id}/subtasks")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        subtasks = resp.json()
        assert isinstance(subtasks, list)
        assert len(subtasks) >= 2
        
        # Verify all returned are subtasks of parent
        for st in subtasks:
            assert st["parent_task_id"] == parent_id
            assert "task_id" in st
            assert "title" in st
        
        print(f"✓ GET /tasks/{parent_id}/subtasks returned {len(subtasks)} subtasks")


class TestTaskComments:
    """Test task comments: add, list, delete"""
    
    @pytest.fixture(scope="class")
    def session(self):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        resp = s.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testmention@test.com",
            "password": "Test1234!"
        })
        assert resp.status_code == 200
        return s
    
    @pytest.fixture(scope="class")
    def test_task(self, session):
        """Create a task for comment tests"""
        project_id = "proj_4e216147ec29"
        resp = session.post(f"{BASE_URL}/api/projects/{project_id}/tasks", json={
            "title": "TEST_Task for Comments",
            "item_type": "task",
            "priority": "medium"
        })
        assert resp.status_code == 200
        return resp.json()
    
    def test_add_comment(self, session, test_task):
        """POST /api/tasks/{id}/comments adds threaded comment with author_name, increments comment_count"""
        task_id = test_task["task_id"]
        
        resp = session.post(f"{BASE_URL}/api/tasks/{task_id}/comments", json={
            "content": "This is a test comment"
        })
        
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert "comment_id" in data
        assert data["content"] == "This is a test comment"
        assert "author_id" in data
        assert "author_name" in data
        assert "created_at" in data
        assert data["task_id"] == task_id
        
        print(f"✓ Created comment: {data['comment_id']} by {data['author_name']}")
        
        # Store for later tests
        session.test_comment_id = data["comment_id"]
    
    def test_add_second_comment(self, session, test_task):
        """Add second comment to verify list ordering"""
        task_id = test_task["task_id"]
        
        resp = session.post(f"{BASE_URL}/api/tasks/{task_id}/comments", json={
            "content": "Second comment for ordering test"
        })
        
        assert resp.status_code == 200
        print(f"✓ Created second comment")
    
    def test_list_comments_sorted_by_date(self, session, test_task):
        """GET /api/tasks/{id}/comments returns comments sorted by date"""
        task_id = test_task["task_id"]
        
        resp = session.get(f"{BASE_URL}/api/tasks/{task_id}/comments")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        comments = resp.json()
        assert isinstance(comments, list)
        assert len(comments) >= 2
        
        # Verify sorted by date (ascending - oldest first)
        for i in range(1, len(comments)):
            assert comments[i]["created_at"] >= comments[i-1]["created_at"], "Comments not sorted by date"
        
        # Verify structure
        for c in comments:
            assert "comment_id" in c
            assert "content" in c
            assert "author_id" in c
            assert "author_name" in c
            assert "created_at" in c
        
        print(f"✓ GET /tasks/{task_id}/comments returned {len(comments)} comments (sorted)")
    
    def test_delete_comment_decrements_count(self, session, test_task):
        """DELETE /api/task-comments/{id} removes comment and decrements count"""
        task_id = test_task["task_id"]
        
        # Get current comment_count
        project_id = "proj_4e216147ec29"
        tasks_resp = session.get(f"{BASE_URL}/api/projects/{project_id}/tasks")
        tasks = tasks_resp.json()
        task = next((t for t in tasks if t["task_id"] == task_id), None)
        initial_count = task["comment_count"] if task else 0
        
        # Delete the first comment
        comment_id = session.test_comment_id
        resp = session.delete(f"{BASE_URL}/api/task-comments/{comment_id}")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        # Verify count decremented
        tasks_resp2 = session.get(f"{BASE_URL}/api/projects/{project_id}/tasks")
        tasks2 = tasks_resp2.json()
        task2 = next((t for t in tasks2 if t["task_id"] == task_id), None)
        new_count = task2["comment_count"] if task2 else 0
        
        assert new_count == initial_count - 1, f"Expected {initial_count - 1}, got {new_count}"
        print(f"✓ Deleted comment, count: {initial_count} → {new_count}")
    
    def test_add_comment_validation(self, session, test_task):
        """POST /api/tasks/{id}/comments returns 400 without content"""
        task_id = test_task["task_id"]
        
        resp = session.post(f"{BASE_URL}/api/tasks/{task_id}/comments", json={
            "content": ""
        })
        assert resp.status_code == 400
        print("✓ Comment validation works - empty content rejected")


class TestTaskAttachments:
    """Test task attachments: upload, list, get with data, delete"""
    
    @pytest.fixture(scope="class")
    def session(self):
        s = requests.Session()
        # Don't set Content-Type for multipart uploads
        resp = s.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testmention@test.com",
            "password": "Test1234!"
        }, headers={"Content-Type": "application/json"})
        assert resp.status_code == 200
        return s
    
    @pytest.fixture(scope="class")
    def test_task(self, session):
        """Create a task for attachment tests"""
        project_id = "proj_4e216147ec29"
        resp = session.post(f"{BASE_URL}/api/projects/{project_id}/tasks", json={
            "title": "TEST_Task for Attachments",
            "item_type": "task",
            "priority": "medium"
        }, headers={"Content-Type": "application/json"})
        assert resp.status_code == 200
        return resp.json()
    
    def test_upload_attachment(self, session, test_task):
        """POST /api/tasks/{id}/attachments uploads file, increments attachment_count"""
        task_id = test_task["task_id"]
        
        # Create test file content
        file_content = b"This is test file content for attachment testing"
        files = {
            "file": ("test_document.txt", file_content, "text/plain")
        }
        
        resp = session.post(f"{BASE_URL}/api/tasks/{task_id}/attachments", files=files)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "attachment_id" in data
        assert data["filename"] == "test_document.txt"
        assert data["mime_type"] == "text/plain"
        assert data["size"] == len(file_content)
        assert "uploaded_by" in data
        assert "uploaded_at" in data
        assert "data" not in data  # Should not include base64 data in response
        
        print(f"✓ Uploaded attachment: {data['attachment_id']} ({data['size']} bytes)")
        
        session.test_attachment_id = data["attachment_id"]
    
    def test_list_attachments_without_data(self, session, test_task):
        """GET /api/tasks/{id}/attachments lists attachments without data field"""
        task_id = test_task["task_id"]
        
        resp = session.get(f"{BASE_URL}/api/tasks/{task_id}/attachments")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        attachments = resp.json()
        assert isinstance(attachments, list)
        assert len(attachments) >= 1
        
        for att in attachments:
            assert "attachment_id" in att
            assert "filename" in att
            assert "mime_type" in att
            assert "size" in att
            assert "data" not in att  # Should NOT include base64 data
        
        print(f"✓ GET /tasks/{task_id}/attachments returned {len(attachments)} (no data field)")
    
    def test_get_attachment_with_data(self, session):
        """GET /api/task-attachments/{id} returns full attachment with base64 data"""
        attachment_id = session.test_attachment_id
        
        resp = session.get(f"{BASE_URL}/api/task-attachments/{attachment_id}")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "attachment_id" in data
        assert "filename" in data
        assert "data" in data  # Should include base64 data
        
        # Verify base64 content decodes correctly
        decoded = base64.b64decode(data["data"])
        assert decoded == b"This is test file content for attachment testing"
        
        print(f"✓ GET /task-attachments/{attachment_id} returned with base64 data")
    
    def test_attachment_count_incremented(self, session, test_task):
        """Verify attachment_count was incremented on task"""
        task_id = test_task["task_id"]
        project_id = "proj_4e216147ec29"
        
        resp = session.get(f"{BASE_URL}/api/projects/{project_id}/tasks")
        assert resp.status_code == 200
        
        tasks = resp.json()
        task = next((t for t in tasks if t["task_id"] == task_id), None)
        assert task is not None
        assert task["attachment_count"] >= 1
        
        print(f"✓ attachment_count: {task['attachment_count']}")


class TestActivityLog:
    """Test task activity logging"""
    
    @pytest.fixture(scope="class")
    def session(self):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        resp = s.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testmention@test.com",
            "password": "Test1234!"
        })
        assert resp.status_code == 200
        return s
    
    @pytest.fixture(scope="class")
    def test_task(self, session):
        """Create a task for activity tests"""
        project_id = "proj_4e216147ec29"
        resp = session.post(f"{BASE_URL}/api/projects/{project_id}/tasks", json={
            "title": "TEST_Task for Activity Log",
            "item_type": "task",
            "priority": "low",
            "status": "todo"
        })
        assert resp.status_code == 200
        return resp.json()
    
    def test_created_activity_logged(self, session, test_task):
        """GET /api/tasks/{id}/activity returns created event"""
        task_id = test_task["task_id"]
        
        resp = session.get(f"{BASE_URL}/api/tasks/{task_id}/activity")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        activity = resp.json()
        assert isinstance(activity, list)
        assert len(activity) >= 1
        
        # Find created event
        created = next((a for a in activity if a["action"] == "created"), None)
        assert created is not None, "Created event not found in activity log"
        
        assert "activity_id" in created
        assert "actor_id" in created
        assert "actor_name" in created
        assert "timestamp" in created
        assert "details" in created
        
        print(f"✓ Activity log contains 'created' event for task {task_id}")
    
    def test_update_logs_status_change(self, session, test_task):
        """PUT /api/projects/{id}/tasks/{id} logs status change to activity"""
        task_id = test_task["task_id"]
        project_id = "proj_4e216147ec29"
        
        # Update status
        resp = session.put(f"{BASE_URL}/api/projects/{project_id}/tasks/{task_id}", json={
            "status": "in_progress"
        })
        assert resp.status_code == 200
        
        # Check activity log
        activity_resp = session.get(f"{BASE_URL}/api/tasks/{task_id}/activity")
        assert activity_resp.status_code == 200
        
        activity = activity_resp.json()
        updated = next((a for a in activity if a["action"] == "updated"), None)
        assert updated is not None, "Updated event not found"
        
        # Verify status change logged in details
        changes = updated.get("details", {}).get("changes", [])
        status_change = next((c for c in changes if "status" in c.lower()), None)
        assert status_change is not None, f"Status change not in activity. Changes: {changes}"
        
        print(f"✓ Status change logged: {status_change}")
    
    def test_update_logs_priority_change(self, session, test_task):
        """PUT /api/projects/{id}/tasks/{id} logs priority change"""
        task_id = test_task["task_id"]
        project_id = "proj_4e216147ec29"
        
        resp = session.put(f"{BASE_URL}/api/projects/{project_id}/tasks/{task_id}", json={
            "priority": "high"
        })
        assert resp.status_code == 200
        
        activity_resp = session.get(f"{BASE_URL}/api/tasks/{task_id}/activity")
        activity = activity_resp.json()
        
        # Find latest update event
        updates = [a for a in activity if a["action"] == "updated"]
        assert len(updates) >= 2, f"Expected at least 2 update events, got {len(updates)}"
        
        latest = updates[0]  # Sorted by timestamp desc
        changes = latest.get("details", {}).get("changes", [])
        priority_change = next((c for c in changes if "priority" in c.lower()), None)
        assert priority_change is not None, f"Priority change not logged. Changes: {changes}"
        
        print(f"✓ Priority change logged: {priority_change}")
    
    def test_update_logs_due_date_change(self, session, test_task):
        """PUT /api/projects/{id}/tasks/{id} with due_date creates activity log entry"""
        task_id = test_task["task_id"]
        project_id = "proj_4e216147ec29"
        
        resp = session.put(f"{BASE_URL}/api/projects/{project_id}/tasks/{task_id}", json={
            "due_date": "2026-02-20"
        })
        assert resp.status_code == 200
        
        activity_resp = session.get(f"{BASE_URL}/api/tasks/{task_id}/activity")
        activity = activity_resp.json()
        
        updates = [a for a in activity if a["action"] == "updated"]
        latest = updates[0]
        changes = latest.get("details", {}).get("changes", [])
        due_date_change = next((c for c in changes if "due date" in c.lower()), None)
        assert due_date_change is not None, f"Due date change not logged. Changes: {changes}"
        
        print(f"✓ Due date change logged: {due_date_change}")


class TestMyTasks:
    """Test /api/my-tasks endpoint"""
    
    @pytest.fixture(scope="class")
    def session(self):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        resp = s.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testmention@test.com",
            "password": "Test1234!"
        })
        assert resp.status_code == 200
        user = s.get(f"{BASE_URL}/api/auth/me").json()
        s.user_id = user["user_id"]
        return s
    
    @pytest.fixture(scope="class")
    def assigned_task(self, session):
        """Create a task assigned to current user"""
        project_id = "proj_4e216147ec29"
        resp = session.post(f"{BASE_URL}/api/projects/{project_id}/tasks", json={
            "title": "TEST_My Assigned Task",
            "item_type": "task",
            "priority": "high",
            "status": "todo",
            "assignee_id": session.user_id,
            "assignee_name": "Test User"
        })
        assert resp.status_code == 200
        return resp.json()
    
    def test_my_tasks_returns_assigned_tasks(self, session, assigned_task):
        """GET /api/my-tasks returns tasks assigned to current user"""
        resp = session.get(f"{BASE_URL}/api/my-tasks")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "tasks" in data
        assert "total" in data
        
        tasks = data["tasks"]
        assert len(tasks) >= 1
        
        # Find our assigned task
        my_task = next((t for t in tasks if t["task_id"] == assigned_task["task_id"]), None)
        assert my_task is not None, "Assigned task not found in my-tasks"
        
        # Verify enrichment with project_name
        assert "project_name" in my_task
        
        print(f"✓ GET /my-tasks returned {len(tasks)} tasks with project_name enrichment")
    
    def test_my_tasks_filter_by_status(self, session, assigned_task):
        """GET /api/my-tasks?status=todo filters correctly"""
        resp = session.get(f"{BASE_URL}/api/my-tasks?status=todo")
        assert resp.status_code == 200
        
        data = resp.json()
        tasks = data["tasks"]
        
        # All returned tasks should have status=todo
        for t in tasks:
            assert t["status"] == "todo", f"Expected status=todo, got {t['status']}"
        
        print(f"✓ Status filter: {len(tasks)} tasks with status=todo")
    
    def test_my_tasks_filter_by_priority(self, session, assigned_task):
        """GET /api/my-tasks?priority=high filters correctly"""
        resp = session.get(f"{BASE_URL}/api/my-tasks?priority=high")
        assert resp.status_code == 200
        
        data = resp.json()
        tasks = data["tasks"]
        
        for t in tasks:
            assert t["priority"] == "high", f"Expected priority=high, got {t['priority']}"
        
        print(f"✓ Priority filter: {len(tasks)} tasks with priority=high")
    
    def test_my_tasks_combined_filters(self, session, assigned_task):
        """GET /api/my-tasks?status=todo&priority=high filters correctly"""
        resp = session.get(f"{BASE_URL}/api/my-tasks?status=todo&priority=high")
        assert resp.status_code == 200
        
        data = resp.json()
        tasks = data["tasks"]
        
        for t in tasks:
            assert t["status"] == "todo"
            assert t["priority"] == "high"
        
        print(f"✓ Combined filters: {len(tasks)} tasks (todo+high)")


class TestExistingTestTask:
    """Verify existing test task ptask_d0ae46fddc58 (bug type with due date)"""
    
    @pytest.fixture(scope="class")
    def session(self):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        resp = s.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testmention@test.com",
            "password": "Test1234!"
        })
        assert resp.status_code == 200
        return s
    
    def test_existing_task_has_new_fields(self, session):
        """Verify test task ptask_d0ae46fddc58 has new fields"""
        project_id = "proj_4e216147ec29"
        task_id = "ptask_d0ae46fddc58"
        
        resp = session.get(f"{BASE_URL}/api/projects/{project_id}/tasks")
        assert resp.status_code == 200
        
        tasks = resp.json()
        task = next((t for t in tasks if t["task_id"] == task_id), None)
        
        if task:
            print(f"✓ Found existing task: {task_id}")
            print(f"  - item_type: {task.get('item_type')}")
            print(f"  - due_date: {task.get('due_date')}")
            print(f"  - labels: {task.get('labels')}")
            print(f"  - story_points: {task.get('story_points')}")
            print(f"  - subtask_count: {task.get('subtask_count')}")
            print(f"  - comment_count: {task.get('comment_count')}")
            print(f"  - attachment_count: {task.get('attachment_count')}")
        else:
            print(f"⚠ Test task {task_id} not found - may have been deleted")


class TestCleanup:
    """Cleanup test data"""
    
    @pytest.fixture(scope="class")
    def session(self):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        resp = s.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testmention@test.com",
            "password": "Test1234!"
        })
        assert resp.status_code == 200
        return s
    
    def test_cleanup_test_tasks(self, session):
        """Delete TEST_ prefixed tasks"""
        project_id = "proj_4e216147ec29"
        
        resp = session.get(f"{BASE_URL}/api/projects/{project_id}/tasks")
        assert resp.status_code == 200
        
        tasks = resp.json()
        test_tasks = [t for t in tasks if t.get("title", "").startswith("TEST_")]
        
        deleted = 0
        for task in test_tasks:
            del_resp = session.delete(f"{BASE_URL}/api/projects/{project_id}/tasks/{task['task_id']}")
            if del_resp.status_code == 200:
                deleted += 1
        
        print(f"✓ Cleaned up {deleted} TEST_ prefixed tasks")
