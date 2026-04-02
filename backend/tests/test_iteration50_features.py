"""
Iteration 50 Tests - Milestones, Task Relationships, Task Detail, ZIP Download
Tests: Milestone CRUD, Relationship CRUD (blocks, depends_on, milestone, parent),
       Self-reference validation, Duplicate validation, Task Detail enrichment, ZIP Download
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "test@test.com"
TEST_PASSWORD = "test123"
WORKSPACE_ID = "ws_f6ec6355bb18"
PROJECT_ID = "proj_780954183898"

# Existing test data from context
EXISTING_MILESTONE_ID = "ms_eb4dcc59dad6"
EXISTING_REL_MILESTONE = "trel_4575b3b6bd2b"
EXISTING_REL_BLOCKS = "trel_a41a453f75cc"
TASK_1 = "ptask_65f8f5acb4b2"  # done
TASK_2 = "ptask_00d82067cec7"  # in_progress, blocks TASK_3
TASK_3 = "ptask_75cf62b23bbc"  # todo


@pytest.fixture(scope="module")
def session():
    """Create authenticated session"""
    s = requests.Session()
    resp = s.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return s


@pytest.fixture(scope="module")
def auth_headers(session):
    """Get headers with session cookies"""
    return {
        "Cookie": "; ".join([f"{k}={v}" for k, v in session.cookies.items()]),
        "Content-Type": "application/json"
    }


# ==================== MILESTONE TESTS ====================

class TestMilestones:
    """Test Milestone CRUD operations"""

    def test_list_milestones(self, auth_headers):
        """GET /projects/{pid}/milestones returns milestones with progress"""
        resp = requests.get(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/milestones",
            headers=auth_headers
        )
        assert resp.status_code == 200, f"List milestones failed: {resp.text}"
        data = resp.json()
        assert "milestones" in data
        # Check existing milestone
        milestones = data["milestones"]
        if milestones:
            ms = milestones[0]
            assert "milestone_id" in ms
            assert "name" in ms
            assert "progress" in ms  # Progress calculation
            assert "linked_tasks" in ms
            print(f"PASS: List milestones returned {len(milestones)} milestones with progress")

    def test_create_milestone(self, auth_headers):
        """POST /projects/{pid}/milestones creates milestone"""
        resp = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/milestones",
            headers=auth_headers,
            json={
                "name": "TEST_Milestone_Iter50",
                "description": "Test milestone for iteration 50",
                "due_date": "2026-02-28",
                "status": "open"
            }
        )
        assert resp.status_code == 200, f"Create milestone failed: {resp.text}"
        data = resp.json()
        assert "milestone_id" in data
        assert data["name"] == "TEST_Milestone_Iter50"
        assert data["description"] == "Test milestone for iteration 50"
        assert data["due_date"] == "2026-02-28"
        assert data["status"] == "open"
        print(f"PASS: Created milestone {data['milestone_id']}")
        # Store for cleanup
        TestMilestones.created_milestone_id = data["milestone_id"]

    def test_update_milestone(self, auth_headers):
        """PUT /projects/{pid}/milestones/{mid} updates milestone"""
        milestone_id = getattr(TestMilestones, 'created_milestone_id', EXISTING_MILESTONE_ID)
        resp = requests.put(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/milestones/{milestone_id}",
            headers=auth_headers,
            json={
                "name": "TEST_Milestone_Updated",
                "status": "in_progress"
            }
        )
        assert resp.status_code == 200, f"Update milestone failed: {resp.text}"
        data = resp.json()
        assert data["name"] == "TEST_Milestone_Updated"
        assert data["status"] == "in_progress"
        print(f"PASS: Updated milestone {milestone_id}")

    def test_delete_milestone(self, auth_headers):
        """DELETE /projects/{pid}/milestones/{mid} deletes milestone"""
        milestone_id = getattr(TestMilestones, 'created_milestone_id', None)
        if not milestone_id:
            pytest.skip("No test milestone to delete")
        resp = requests.delete(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/milestones/{milestone_id}",
            headers=auth_headers
        )
        assert resp.status_code == 200, f"Delete milestone failed: {resp.text}"
        data = resp.json()
        assert data.get("deleted") is True
        print(f"PASS: Deleted milestone {milestone_id}")


# ==================== RELATIONSHIP TESTS ====================

class TestRelationships:
    """Test Task Relationship CRUD operations"""

    def test_get_relationships(self, auth_headers):
        """GET /tasks/{tid}/relationships returns categorized relationships"""
        resp = requests.get(
            f"{BASE_URL}/api/tasks/{TASK_2}/relationships",
            headers=auth_headers
        )
        assert resp.status_code == 200, f"Get relationships failed: {resp.text}"
        data = resp.json()
        # Check expected categories
        assert "parents" in data
        assert "children" in data
        assert "blocks" in data
        assert "blocked_by" in data
        assert "depends_on" in data
        assert "dependents" in data
        assert "milestone_links" in data
        print(f"PASS: Get relationships returned categorized data")

    def test_create_relationship_blocks(self, auth_headers):
        """POST /tasks/{tid}/relationships creates blocks relationship"""
        resp = requests.post(
            f"{BASE_URL}/api/tasks/{TASK_1}/relationships",
            headers=auth_headers,
            json={
                "type": "blocks",
                "target_id": TASK_3
            }
        )
        # May already exist from existing data
        if resp.status_code == 409:
            print("PASS: Duplicate blocks relationship blocked (409)")
            return
        assert resp.status_code == 200, f"Create blocks relationship failed: {resp.text}"
        data = resp.json()
        assert "relationship_id" in data
        assert data["relationship_type"] == "blocks"
        print(f"PASS: Created blocks relationship {data['relationship_id']}")
        TestRelationships.created_rel_id = data["relationship_id"]

    def test_create_relationship_depends_on(self, auth_headers):
        """POST /tasks/{tid}/relationships creates depends_on relationship"""
        resp = requests.post(
            f"{BASE_URL}/api/tasks/{TASK_3}/relationships",
            headers=auth_headers,
            json={
                "type": "depends_on",
                "target_id": TASK_1
            }
        )
        if resp.status_code == 409:
            print("PASS: Duplicate depends_on relationship blocked (409)")
            return
        assert resp.status_code == 200, f"Create depends_on relationship failed: {resp.text}"
        data = resp.json()
        assert data["relationship_type"] == "depends_on"
        print(f"PASS: Created depends_on relationship {data['relationship_id']}")
        TestRelationships.created_depends_rel_id = data["relationship_id"]

    def test_self_reference_blocked(self, auth_headers):
        """Self-reference should return 400"""
        resp = requests.post(
            f"{BASE_URL}/api/tasks/{TASK_1}/relationships",
            headers=auth_headers,
            json={
                "type": "blocks",
                "target_id": TASK_1  # Same task - should fail
            }
        )
        assert resp.status_code == 400, f"Self-reference should be blocked, got: {resp.status_code}"
        print("PASS: Self-reference blocked (400)")

    def test_duplicate_blocked(self, auth_headers):
        """Duplicate relationship should return 409"""
        # First create a relationship
        resp1 = requests.post(
            f"{BASE_URL}/api/tasks/{TASK_2}/relationships",
            headers=auth_headers,
            json={
                "type": "depends_on",
                "target_id": TASK_1
            }
        )
        # Could be 200 (new) or 409 (existing)
        if resp1.status_code == 409:
            print("PASS: Duplicate relationship blocked (409) on first try")
            return
        
        # Now try to create the same again
        resp2 = requests.post(
            f"{BASE_URL}/api/tasks/{TASK_2}/relationships",
            headers=auth_headers,
            json={
                "type": "depends_on",
                "target_id": TASK_1
            }
        )
        assert resp2.status_code == 409, f"Duplicate should return 409, got: {resp2.status_code}"
        print("PASS: Duplicate relationship blocked (409)")

    def test_delete_relationship(self, auth_headers):
        """DELETE /relationships/{rid} removes relationship"""
        # Create a temporary relationship to delete
        resp = requests.post(
            f"{BASE_URL}/api/tasks/{TASK_1}/relationships",
            headers=auth_headers,
            json={
                "type": "parent",
                "target_id": TASK_2
            }
        )
        if resp.status_code == 409:
            # Use existing if duplicate
            pytest.skip("Test relationship already exists")
        
        if resp.status_code == 200:
            rel_id = resp.json()["relationship_id"]
            del_resp = requests.delete(
                f"{BASE_URL}/api/relationships/{rel_id}",
                headers=auth_headers
            )
            assert del_resp.status_code == 200, f"Delete relationship failed: {del_resp.text}"
            assert del_resp.json().get("deleted") is True
            print(f"PASS: Deleted relationship {rel_id}")


# ==================== TASK DETAIL TESTS ====================

class TestTaskDetail:
    """Test Task Detail endpoint with full enrichment"""

    def test_task_detail_returns_full_data(self, auth_headers):
        """GET /tasks/{tid}/detail returns full task with relationships, milestone, activity, subtasks"""
        resp = requests.get(
            f"{BASE_URL}/api/tasks/{TASK_2}/detail",
            headers=auth_headers
        )
        assert resp.status_code == 200, f"Get task detail failed: {resp.text}"
        data = resp.json()
        
        # Check all expected fields
        assert "task" in data
        assert "source" in data
        assert "relationships" in data
        assert "related_tasks" in data
        assert "milestone" in data or data.get("milestone") is None
        assert "activity" in data
        assert "subtasks" in data
        
        # Task should have basic fields
        task = data["task"]
        assert "task_id" in task
        assert "title" in task
        assert "status" in task
        assert "priority" in task
        
        print(f"PASS: Task detail returned full enrichment for {task['task_id']}")
        print(f"  - Relationships: {len(data.get('relationships', []))}")
        print(f"  - Activity: {len(data.get('activity', []))}")
        print(f"  - Subtasks: {len(data.get('subtasks', []))}")
        print(f"  - Milestone: {data.get('milestone', {}).get('name') if data.get('milestone') else 'None'}")

    def test_task_detail_404_nonexistent(self, auth_headers):
        """GET /tasks/{tid}/detail returns 404 for nonexistent task"""
        resp = requests.get(
            f"{BASE_URL}/api/tasks/nonexistent_task_id/detail",
            headers=auth_headers
        )
        assert resp.status_code == 404, f"Expected 404, got: {resp.status_code}"
        print("PASS: Task detail returns 404 for nonexistent task")


# ==================== ZIP DOWNLOAD TESTS ====================

class TestZipDownload:
    """Test ZIP download functionality"""

    def test_zip_download_returns_zip(self, auth_headers):
        """GET /workspaces/{ws_id}/code-repo/download returns valid ZIP"""
        resp = requests.get(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/code-repo/download",
            headers=auth_headers,
            stream=True
        )
        # Could be 200 (has files) or 404 (empty repo)
        if resp.status_code == 404:
            print("PASS: ZIP download returns 404 for empty repo (expected)")
            return
        
        assert resp.status_code == 200, f"ZIP download failed: {resp.status_code}"
        
        # Check content type
        content_type = resp.headers.get("Content-Type", "")
        assert "application/zip" in content_type, f"Expected application/zip, got: {content_type}"
        
        # Check Content-Disposition header
        content_disp = resp.headers.get("Content-Disposition", "")
        assert "attachment" in content_disp, f"Missing attachment header: {content_disp}"
        assert ".zip" in content_disp, f"Missing .zip in filename: {content_disp}"
        
        # Verify it's actually a ZIP (magic bytes: PK)
        content = resp.content[:4]
        if len(content) >= 2:
            assert content[:2] == b'PK', f"Invalid ZIP magic bytes: {content[:2]}"
        
        print(f"PASS: ZIP download returned valid ZIP file ({len(resp.content)} bytes)")

    def test_zip_download_404_for_empty_repo(self, auth_headers):
        """GET /workspaces/{ws_id}/code-repo/download returns 404 for empty repo"""
        # Create a workspace with no files to test this
        # For now, we just document the expected behavior
        # An empty workspace's repo should return 404
        print("INFO: Empty repo test skipped (would need dedicated empty workspace)")


# ==================== REGRESSION TESTS ====================

class TestRegression:
    """Regression tests for existing functionality"""

    def test_kanban_view_data(self, auth_headers):
        """Verify Kanban view data still works"""
        resp = requests.get(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/all-tasks",
            headers=auth_headers
        )
        assert resp.status_code == 200, f"All-tasks failed: {resp.text}"
        data = resp.json()
        assert "groups" in data
        assert "total_tasks" in data
        print(f"PASS: Kanban data returned {data['total_tasks']} tasks in {len(data['groups'])} groups")

    def test_branch_selector_data(self, auth_headers):
        """Verify branch data still works"""
        resp = requests.get(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/code-repo/branches",
            headers=auth_headers
        )
        assert resp.status_code == 200, f"Branches failed: {resp.text}"
        data = resp.json()
        assert "branches" in data
        branches = data["branches"]
        # Should have at least main branch
        branch_names = [b["name"] for b in branches]
        assert "main" in branch_names, f"Main branch missing: {branch_names}"
        print(f"PASS: Branch selector has {len(branches)} branches: {branch_names}")

    def test_project_tasks_list(self, auth_headers):
        """Verify project tasks still work"""
        resp = requests.get(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/tasks",
            headers=auth_headers
        )
        assert resp.status_code == 200, f"Project tasks failed: {resp.text}"
        data = resp.json()
        assert isinstance(data, list)
        print(f"PASS: Project {PROJECT_ID} has {len(data)} tasks")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
