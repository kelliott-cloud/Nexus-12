"""
Test Admin System and Bug Tracking APIs
Tests for:
- POST /api/bugs (submit bug report)
- GET /api/bugs/my-reports (user's bug reports)
- GET /api/admin/check (admin status check)
- GET /api/admin/bugs (admin bug list)
- GET /api/admin/stats (admin platform stats)
- GET /api/admin/users (admin user list)
- GET /api/admin/logs (admin logs)
- PUT /api/admin/bugs/{id} (update bug status)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials - will be set during setup
NORMAL_USER_SESSION = "test_session_bug_1772559366227"
ADMIN_SESSION = "test_admin_session_1772559366238"


@pytest.fixture
def normal_client():
    """Session for normal user"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {NORMAL_USER_SESSION}"
    })
    return session


@pytest.fixture
def admin_client():
    """Session for super admin user"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ADMIN_SESSION}"
    })
    return session


class TestBugReportSubmission:
    """Test bug report submission (authenticated users)"""
    
    def test_submit_bug_report_success(self, normal_client):
        """POST /api/bugs - Submit a bug report"""
        payload = {
            "title": "TEST: Button not clickable",
            "description": "The submit button on the form is not clickable when the form is inside a modal.",
            "steps_to_reproduce": "1. Open modal\n2. Fill form\n3. Try to click submit",
            "expected_behavior": "Button should be clickable",
            "actual_behavior": "Button does nothing when clicked",
            "severity": "high",
            "category": "ui"
        }
        response = normal_client.post(f"{BASE_URL}/api/bugs", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "status" in data
        assert data["status"] == "submitted"
        assert "bug_id" in data
        assert data["bug_id"].startswith("bug_")
        assert "message" in data
        print(f"Bug submitted successfully: {data['bug_id']}")
    
    def test_submit_bug_report_minimal(self, normal_client):
        """POST /api/bugs - Submit bug with only required fields"""
        payload = {
            "title": "TEST: Minimal bug report",
            "description": "This is a minimal bug report with only required fields"
        }
        response = normal_client.post(f"{BASE_URL}/api/bugs", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["status"] == "submitted"
        print(f"Minimal bug submitted: {data['bug_id']}")
    
    def test_submit_bug_report_invalid_title(self, normal_client):
        """POST /api/bugs - Should fail with short title"""
        payload = {
            "title": "Test",  # Too short (min 5 chars)
            "description": "This is a valid description"
        }
        response = normal_client.post(f"{BASE_URL}/api/bugs", json=payload)
        
        # Should get 422 for validation error
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("Validation error for short title as expected")
    
    def test_get_my_bug_reports(self, normal_client):
        """GET /api/bugs/my-reports - Get user's submitted bugs"""
        response = normal_client.get(f"{BASE_URL}/api/bugs/my-reports")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "bugs" in data
        assert "count" in data
        assert isinstance(data["bugs"], list)
        print(f"User has {data['count']} bug reports")


class TestAdminCheck:
    """Test admin status check endpoint"""
    
    def test_admin_check_normal_user(self, normal_client):
        """GET /api/admin/check - Normal user is not admin"""
        response = normal_client.get(f"{BASE_URL}/api/admin/check")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "is_super_admin" in data
        assert data["is_super_admin"] == False
        print(f"Normal user admin check: is_super_admin={data['is_super_admin']}")
    
    def test_admin_check_super_admin(self, admin_client):
        """GET /api/admin/check - Super admin user"""
        response = admin_client.get(f"{BASE_URL}/api/admin/check")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "is_super_admin" in data
        assert data["is_super_admin"] == True
        assert "email" in data
        print(f"Super admin check: is_super_admin={data['is_super_admin']}, email={data['email']}")


class TestAdminBugManagement:
    """Test admin-only bug management endpoints"""
    
    def test_get_all_bugs_normal_user_denied(self, normal_client):
        """GET /api/admin/bugs - Should deny normal user"""
        response = normal_client.get(f"{BASE_URL}/api/admin/bugs")
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("Normal user denied access to admin bugs as expected")
    
    def test_get_all_bugs_admin(self, admin_client):
        """GET /api/admin/bugs - Admin can see all bugs"""
        response = admin_client.get(f"{BASE_URL}/api/admin/bugs")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "bugs" in data
        assert "stats" in data
        assert isinstance(data["bugs"], list)
        
        # Check stats structure
        stats = data["stats"]
        assert "total" in stats
        assert "open" in stats
        print(f"Admin bugs: {len(data['bugs'])} bugs, stats: {stats}")
    
    def test_update_bug_status_admin(self, admin_client, normal_client):
        """PUT /api/admin/bugs/{id} - Admin can update bug status"""
        # First submit a bug to update
        bug_payload = {
            "title": "TEST: Bug to be updated",
            "description": "This bug will have its status updated by admin"
        }
        submit_response = normal_client.post(f"{BASE_URL}/api/bugs", json=bug_payload)
        assert submit_response.status_code == 200
        bug_id = submit_response.json()["bug_id"]
        
        # Now update the bug as admin
        update_payload = {
            "status": "in_progress",
            "priority": "high",
            "admin_notes": "Looking into this issue"
        }
        response = admin_client.put(f"{BASE_URL}/api/admin/bugs/{bug_id}", json=update_payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["status"] == "updated"
        print(f"Bug {bug_id} updated successfully")
    
    def test_update_bug_invalid_status(self, admin_client, normal_client):
        """PUT /api/admin/bugs/{id} - Should reject invalid status"""
        # Submit a bug first
        bug_payload = {
            "title": "TEST: Bug for invalid status test",
            "description": "Testing invalid status update"
        }
        submit_response = normal_client.post(f"{BASE_URL}/api/bugs", json=bug_payload)
        bug_id = submit_response.json()["bug_id"]
        
        # Try to update with invalid status
        update_payload = {"status": "invalid_status"}
        response = admin_client.put(f"{BASE_URL}/api/admin/bugs/{bug_id}", json=update_payload)
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("Invalid status rejected as expected")


class TestAdminStats:
    """Test admin platform stats endpoint"""
    
    def test_get_stats_normal_user_denied(self, normal_client):
        """GET /api/admin/stats - Should deny normal user"""
        response = normal_client.get(f"{BASE_URL}/api/admin/stats")
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("Normal user denied access to admin stats as expected")
    
    def test_get_stats_admin(self, admin_client):
        """GET /api/admin/stats - Admin can see platform stats"""
        response = admin_client.get(f"{BASE_URL}/api/admin/stats")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify stats structure
        assert "users" in data
        assert "workspaces" in data
        assert "messages" in data
        assert "tasks" in data
        assert "bugs" in data
        assert "files" in data
        
        # Verify users has expected fields
        assert "total" in data["users"]
        assert "today" in data["users"]
        assert "this_week" in data["users"]
        
        print(f"Platform stats: users={data['users']['total']}, workspaces={data['workspaces']['total']}")


class TestAdminUsers:
    """Test admin users management endpoint"""
    
    def test_get_users_normal_user_denied(self, normal_client):
        """GET /api/admin/users - Should deny normal user"""
        response = normal_client.get(f"{BASE_URL}/api/admin/users")
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("Normal user denied access to admin users as expected")
    
    def test_get_users_admin(self, admin_client):
        """GET /api/admin/users - Admin can see all users"""
        response = admin_client.get(f"{BASE_URL}/api/admin/users")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "users" in data
        assert "total" in data
        assert isinstance(data["users"], list)
        
        if len(data["users"]) > 0:
            user = data["users"][0]
            assert "user_id" in user
            assert "email" in user
            assert "name" in user
        
        print(f"Admin users: {len(data['users'])} users, total: {data['total']}")


class TestAdminLogs:
    """Test admin platform logs endpoint"""
    
    def test_get_logs_normal_user_denied(self, normal_client):
        """GET /api/admin/logs - Should deny normal user"""
        response = normal_client.get(f"{BASE_URL}/api/admin/logs")
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("Normal user denied access to admin logs as expected")
    
    def test_get_logs_admin(self, admin_client):
        """GET /api/admin/logs - Admin can see platform logs"""
        response = admin_client.get(f"{BASE_URL}/api/admin/logs?limit=10")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "logs" in data
        assert "count" in data
        assert isinstance(data["logs"], list)
        
        print(f"Admin logs: {data['count']} logs retrieved")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
