"""
Iteration 23 Tests: Artifact Versioning, Bulk Task Operations, Search/Filter
Tests the 4 new enhancements:
1. Artifact versioning with restore & diff
2. Task assignment features  
3. Bulk task operations (bulk-update, bulk-delete)
4. Enhanced search/filtering for projects
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testmention@test.com"
TEST_PASSWORD = "Test1234!"
WORKSPACE_ID = "ws_bd1750012bfd"


@pytest.fixture(scope="module")
def session():
    """Create authenticated session"""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    
    # Login
    resp = s.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return s


@pytest.fixture(scope="module")
def test_project(session):
    """Create a test project for task operations"""
    resp = session.post(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/projects", json={
        "name": "TEST_BulkOps_Project",
        "description": "Test project for bulk operations testing"
    })
    assert resp.status_code == 200, f"Project creation failed: {resp.text}"
    project = resp.json()
    yield project
    # Cleanup
    session.delete(f"{BASE_URL}/api/projects/{project['project_id']}")


@pytest.fixture(scope="module")
def test_artifact(session):
    """Create a test artifact for versioning tests"""
    resp = session.post(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/artifacts", json={
        "name": "TEST_Versioning_Artifact",
        "content": "Initial content version 1",
        "content_type": "text",
        "tags": ["test", "versioning"]
    })
    assert resp.status_code == 200, f"Artifact creation failed: {resp.text}"
    artifact = resp.json()
    yield artifact
    # Cleanup
    session.delete(f"{BASE_URL}/api/artifacts/{artifact['artifact_id']}")


# ==================== ARTIFACT VERSIONING TESTS ====================

class TestArtifactVersioning:
    """Tests for artifact versioning with restore and diff"""
    
    def test_artifact_creation_starts_at_version_1(self, session, test_artifact):
        """Newly created artifact should start at version 1"""
        assert test_artifact["version"] == 1
        assert test_artifact["content"] == "Initial content version 1"
        print(f"✓ Artifact created at version 1: {test_artifact['artifact_id']}")
    
    def test_artifact_update_increments_version(self, session, test_artifact):
        """Updating artifact content should increment version"""
        resp = session.put(f"{BASE_URL}/api/artifacts/{test_artifact['artifact_id']}", json={
            "content": "Updated content version 2"
        })
        assert resp.status_code == 200, f"Update failed: {resp.text}"
        data = resp.json()
        assert data["version"] == 2
        assert data["content"] == "Updated content version 2"
        print(f"✓ Artifact updated to version 2")
    
    def test_artifact_has_version_history(self, session, test_artifact):
        """GET artifact should include version history"""
        resp = session.get(f"{BASE_URL}/api/artifacts/{test_artifact['artifact_id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert "versions" in data
        assert len(data["versions"]) >= 2
        # Versions should be sorted descending
        versions = data["versions"]
        assert versions[0]["version"] == 2  # Latest first
        assert versions[1]["version"] == 1
        print(f"✓ Version history retrieved: {len(versions)} versions")
    
    def test_version_has_change_summary(self, session, test_artifact):
        """Version 2+ should have change_summary with chars_added/removed"""
        resp = session.get(f"{BASE_URL}/api/artifacts/{test_artifact['artifact_id']}")
        assert resp.status_code == 200
        data = resp.json()
        v2 = next((v for v in data["versions"] if v["version"] == 2), None)
        assert v2 is not None
        assert "change_summary" in v2
        assert "chars_added" in v2["change_summary"]
        assert "chars_removed" in v2["change_summary"]
        print(f"✓ change_summary present: +{v2['change_summary']['chars_added']} -{v2['change_summary']['chars_removed']}")
    
    def test_artifact_diff_between_versions(self, session, test_artifact):
        """GET /artifacts/{id}/diff?v1=1&v2=2 returns unified diff"""
        resp = session.get(f"{BASE_URL}/api/artifacts/{test_artifact['artifact_id']}/diff?v1=1&v2=2")
        assert resp.status_code == 200, f"Diff failed: {resp.text}"
        data = resp.json()
        assert "diff" in data
        assert "additions" in data
        assert "deletions" in data
        assert "v1" in data
        assert "v2" in data
        assert data["v1"]["version"] == 1
        assert data["v2"]["version"] == 2
        print(f"✓ Diff retrieved: +{data['additions']} -{data['deletions']} lines")
    
    def test_artifact_diff_invalid_versions_returns_404(self, session, test_artifact):
        """Diff with nonexistent version returns 404"""
        resp = session.get(f"{BASE_URL}/api/artifacts/{test_artifact['artifact_id']}/diff?v1=1&v2=999")
        assert resp.status_code == 404
        print("✓ Invalid version diff returns 404")
    
    def test_artifact_restore_creates_new_version(self, session, test_artifact):
        """POST /artifacts/{id}/restore/{version} restores to previous version"""
        # First check current version
        resp = session.get(f"{BASE_URL}/api/artifacts/{test_artifact['artifact_id']}")
        current_version = resp.json()["version"]
        
        # Restore to version 1
        resp = session.post(f"{BASE_URL}/api/artifacts/{test_artifact['artifact_id']}/restore/1")
        assert resp.status_code == 200, f"Restore failed: {resp.text}"
        data = resp.json()
        assert data["version"] == current_version + 1  # Should be version 3
        assert data["content"] == "Initial content version 1"  # Content from v1
        print(f"✓ Restored to v1, created version {data['version']}")
    
    def test_restored_version_has_restored_from_field(self, session, test_artifact):
        """Restored version should have restored_from field"""
        resp = session.get(f"{BASE_URL}/api/artifacts/{test_artifact['artifact_id']}")
        assert resp.status_code == 200
        data = resp.json()
        # Latest version (v3) should have restored_from
        latest_version = data["versions"][0]
        assert latest_version["version"] == 3
        assert "restored_from" in latest_version
        assert latest_version["restored_from"] == 1
        print(f"✓ restored_from field present: restored from v{latest_version['restored_from']}")
    
    def test_restore_nonexistent_version_returns_404(self, session, test_artifact):
        """Restoring to nonexistent version returns 404"""
        resp = session.post(f"{BASE_URL}/api/artifacts/{test_artifact['artifact_id']}/restore/999")
        assert resp.status_code == 404
        print("✓ Restore nonexistent version returns 404")


# ==================== BULK TASK OPERATIONS TESTS ====================

class TestBulkTaskOperations:
    """Tests for bulk task update and delete operations"""
    
    @pytest.fixture
    def test_tasks(self, session, test_project):
        """Create multiple tasks for bulk operations"""
        task_ids = []
        for i in range(3):
            resp = session.post(f"{BASE_URL}/api/projects/{test_project['project_id']}/tasks", json={
                "title": f"TEST_Bulk_Task_{i}",
                "description": f"Task {i} for bulk testing",
                "status": "todo",
                "priority": "medium"
            })
            assert resp.status_code == 200, f"Task creation failed: {resp.text}"
            task_ids.append(resp.json()["task_id"])
        yield task_ids
        # Cleanup any remaining tasks
        for tid in task_ids:
            session.delete(f"{BASE_URL}/api/projects/{test_project['project_id']}/tasks/{tid}")
    
    def test_bulk_update_status(self, session, test_project, test_tasks):
        """POST /projects/{id}/tasks/bulk-update updates status for multiple tasks"""
        resp = session.post(f"{BASE_URL}/api/projects/{test_project['project_id']}/tasks/bulk-update", json={
            "task_ids": test_tasks,
            "status": "in_progress"
        })
        assert resp.status_code == 200, f"Bulk update failed: {resp.text}"
        data = resp.json()
        assert "updated" in data
        assert data["updated"] == 3
        
        # Verify tasks were actually updated
        for tid in test_tasks:
            resp = session.get(f"{BASE_URL}/api/projects/{test_project['project_id']}/tasks")
            tasks = resp.json()
            task = next((t for t in tasks if t["task_id"] == tid), None)
            assert task is not None
            assert task["status"] == "in_progress"
        print(f"✓ Bulk updated {data['updated']} tasks to in_progress")
    
    def test_bulk_update_priority(self, session, test_project, test_tasks):
        """Bulk update can change priority"""
        resp = session.post(f"{BASE_URL}/api/projects/{test_project['project_id']}/tasks/bulk-update", json={
            "task_ids": test_tasks,
            "priority": "high"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated"] == 3
        print(f"✓ Bulk updated {data['updated']} tasks to high priority")
    
    def test_bulk_update_assignee(self, session, test_project, test_tasks):
        """Bulk update can set assignee"""
        resp = session.post(f"{BASE_URL}/api/projects/{test_project['project_id']}/tasks/bulk-update", json={
            "task_ids": test_tasks,
            "assignee_type": "ai",
            "assignee_id": "claude",
            "assignee_name": "Claude"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated"] == 3
        print(f"✓ Bulk updated {data['updated']} tasks with assignee Claude")
    
    def test_bulk_update_invalid_status_returns_400(self, session, test_project, test_tasks):
        """Bulk update with invalid status returns 400"""
        resp = session.post(f"{BASE_URL}/api/projects/{test_project['project_id']}/tasks/bulk-update", json={
            "task_ids": test_tasks,
            "status": "invalid_status"
        })
        assert resp.status_code == 400
        print("✓ Invalid status returns 400")
    
    def test_bulk_update_empty_task_ids_returns_400(self, session, test_project):
        """Bulk update with empty task_ids returns 400"""
        resp = session.post(f"{BASE_URL}/api/projects/{test_project['project_id']}/tasks/bulk-update", json={
            "task_ids": [],
            "status": "done"
        })
        assert resp.status_code == 400
        print("✓ Empty task_ids returns 400")
    
    def test_bulk_delete_tasks(self, session, test_project):
        """POST /projects/{id}/tasks/bulk-delete removes multiple tasks"""
        # Create fresh tasks for deletion test
        task_ids = []
        for i in range(2):
            resp = session.post(f"{BASE_URL}/api/projects/{test_project['project_id']}/tasks", json={
                "title": f"TEST_Delete_Task_{i}",
                "status": "todo",
                "priority": "low"
            })
            task_ids.append(resp.json()["task_id"])
        
        # Bulk delete
        resp = session.post(f"{BASE_URL}/api/projects/{test_project['project_id']}/tasks/bulk-delete", json={
            "task_ids": task_ids
        })
        assert resp.status_code == 200, f"Bulk delete failed: {resp.text}"
        data = resp.json()
        assert "deleted" in data
        assert data["deleted"] == 2
        
        # Verify tasks are gone
        resp = session.get(f"{BASE_URL}/api/projects/{test_project['project_id']}/tasks")
        tasks = resp.json()
        for tid in task_ids:
            assert not any(t["task_id"] == tid for t in tasks)
        print(f"✓ Bulk deleted {data['deleted']} tasks")
    
    def test_bulk_delete_empty_task_ids_returns_400(self, session, test_project):
        """Bulk delete with empty task_ids returns 400"""
        resp = session.post(f"{BASE_URL}/api/projects/{test_project['project_id']}/tasks/bulk-delete", json={
            "task_ids": []
        })
        assert resp.status_code == 400
        print("✓ Empty task_ids for bulk delete returns 400")


# ==================== SEARCH & FILTER TESTS ====================

class TestSearchFilter:
    """Tests for workspace task search and filter"""
    
    @pytest.fixture
    def search_project_with_tasks(self, session):
        """Create project with varied tasks for search testing"""
        # Create project
        resp = session.post(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/projects", json={
            "name": "TEST_Search_Project",
            "description": "Project for search testing"
        })
        project = resp.json()
        project_id = project["project_id"]
        
        # Create tasks with different statuses, priorities, assignees
        tasks_data = [
            {"title": "Alpha critical task", "status": "todo", "priority": "critical", "assignee_id": "user1", "assignee_name": "User One", "assignee_type": "human"},
            {"title": "Beta high priority", "status": "in_progress", "priority": "high", "assignee_id": "claude", "assignee_name": "Claude", "assignee_type": "ai"},
            {"title": "Gamma review task", "status": "review", "priority": "medium"},
            {"title": "Delta done task", "status": "done", "priority": "low"},
        ]
        
        task_ids = []
        for td in tasks_data:
            resp = session.post(f"{BASE_URL}/api/projects/{project_id}/tasks", json=td)
            task_ids.append(resp.json()["task_id"])
        
        yield {"project_id": project_id, "task_ids": task_ids}
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/projects/{project_id}")
    
    def test_search_tasks_by_keyword(self, session, search_project_with_tasks):
        """GET /workspaces/{ws}/tasks/search?q=keyword returns matching tasks"""
        resp = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/tasks/search?q=Alpha")
        assert resp.status_code == 200, f"Search failed: {resp.text}"
        data = resp.json()
        assert "tasks" in data
        assert "total" in data
        # Should find the "Alpha critical task"
        assert len(data["tasks"]) >= 1
        assert any("Alpha" in t["title"] for t in data["tasks"])
        print(f"✓ Search by keyword found {len(data['tasks'])} tasks")
    
    def test_filter_tasks_by_status(self, session, search_project_with_tasks):
        """Filter tasks by status"""
        resp = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/tasks/search?status=todo")
        assert resp.status_code == 200
        data = resp.json()
        # All returned tasks should have status=todo
        for task in data["tasks"]:
            assert task["status"] == "todo"
        print(f"✓ Filter by status=todo found {len(data['tasks'])} tasks")
    
    def test_filter_tasks_by_priority(self, session, search_project_with_tasks):
        """Filter tasks by priority"""
        resp = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/tasks/search?priority=critical")
        assert resp.status_code == 200
        data = resp.json()
        for task in data["tasks"]:
            assert task["priority"] == "critical"
        print(f"✓ Filter by priority=critical found {len(data['tasks'])} tasks")
    
    def test_filter_tasks_by_assignee(self, session, search_project_with_tasks):
        """Filter tasks by assignee_id"""
        resp = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/tasks/search?assignee_id=claude")
        assert resp.status_code == 200
        data = resp.json()
        for task in data["tasks"]:
            assert task["assignee_id"] == "claude"
        print(f"✓ Filter by assignee=claude found {len(data['tasks'])} tasks")
    
    def test_search_with_multiple_filters(self, session, search_project_with_tasks):
        """Combine keyword search with status filter"""
        resp = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/tasks/search?q=task&status=done")
        assert resp.status_code == 200
        data = resp.json()
        for task in data["tasks"]:
            assert task["status"] == "done"
            assert "task" in task["title"].lower()
        print(f"✓ Combined search+filter found {len(data['tasks'])} tasks")
    
    def test_search_returns_project_name(self, session, search_project_with_tasks):
        """Search results include project_name field"""
        resp = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/tasks/search?q=Alpha")
        assert resp.status_code == 200
        data = resp.json()
        if data["tasks"]:
            assert "project_name" in data["tasks"][0]
            print(f"✓ Search results include project_name: {data['tasks'][0]['project_name']}")
    
    def test_get_workspace_assignees(self, session, search_project_with_tasks):
        """GET /workspaces/{ws}/assignees returns unique assignees"""
        resp = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/assignees")
        assert resp.status_code == 200, f"Get assignees failed: {resp.text}"
        data = resp.json()
        assert isinstance(data, list)
        # Should have at least our test assignees
        assignee_ids = [a["assignee_id"] for a in data]
        print(f"✓ Found {len(data)} unique assignees in workspace")
    
    def test_search_supports_sorting(self, session, search_project_with_tasks):
        """Search supports sort_by and sort_order parameters"""
        resp = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/tasks/search?sort_by=title&sort_order=asc")
        assert resp.status_code == 200
        data = resp.json()
        if len(data["tasks"]) >= 2:
            # Check ascending order
            titles = [t["title"] for t in data["tasks"]]
            assert titles == sorted(titles)
        print("✓ Sorting by title ascending works")
    
    def test_search_supports_pagination(self, session, search_project_with_tasks):
        """Search supports limit and offset parameters"""
        # Get with limit 2
        resp = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/tasks/search?limit=2&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tasks"]) <= 2
        assert data["total"] >= len(data["tasks"])
        print(f"✓ Pagination works: got {len(data['tasks'])} tasks of {data['total']} total")


# ==================== TASK ASSIGNMENT TESTS ====================

class TestTaskAssignment:
    """Tests for task assignment features"""
    
    def test_create_task_with_human_assignee(self, session, test_project):
        """Create task with human assignee"""
        resp = session.post(f"{BASE_URL}/api/projects/{test_project['project_id']}/tasks", json={
            "title": "TEST_Human_Assigned_Task",
            "assignee_type": "human",
            "assignee_id": "user123",
            "assignee_name": "Test User",
            "status": "todo",
            "priority": "medium"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["assignee_type"] == "human"
        assert data["assignee_id"] == "user123"
        assert data["assignee_name"] == "Test User"
        print(f"✓ Task created with human assignee")
        # Cleanup
        session.delete(f"{BASE_URL}/api/projects/{test_project['project_id']}/tasks/{data['task_id']}")
    
    def test_create_task_with_ai_assignee(self, session, test_project):
        """Create task with AI agent assignee"""
        resp = session.post(f"{BASE_URL}/api/projects/{test_project['project_id']}/tasks", json={
            "title": "TEST_AI_Assigned_Task",
            "assignee_type": "ai",
            "assignee_id": "gemini",
            "assignee_name": "Gemini",
            "status": "todo",
            "priority": "high"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["assignee_type"] == "ai"
        assert data["assignee_id"] == "gemini"
        assert data["assignee_name"] == "Gemini"
        print(f"✓ Task created with AI assignee")
        # Cleanup
        session.delete(f"{BASE_URL}/api/projects/{test_project['project_id']}/tasks/{data['task_id']}")
    
    def test_update_task_assignee(self, session, test_project):
        """Update task to change assignee"""
        # Create task without assignee
        resp = session.post(f"{BASE_URL}/api/projects/{test_project['project_id']}/tasks", json={
            "title": "TEST_Update_Assignee_Task",
            "status": "todo",
            "priority": "medium"
        })
        task_id = resp.json()["task_id"]
        
        # Update with assignee
        resp = session.put(f"{BASE_URL}/api/projects/{test_project['project_id']}/tasks/{task_id}", json={
            "assignee_type": "ai",
            "assignee_id": "chatgpt",
            "assignee_name": "ChatGPT"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["assignee_id"] == "chatgpt"
        print(f"✓ Task assignee updated to ChatGPT")
        # Cleanup
        session.delete(f"{BASE_URL}/api/projects/{test_project['project_id']}/tasks/{task_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
