from conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, BASE_URL
"""
Iteration 14: Platform Role Management Tests
Tests:
- Admin check returns is_super_admin, is_staff, platform_role fields
- Super admin can change user roles via PUT /api/admin/users/{user_id}/role
- Super admin cannot change their own role
- Invalid role values are rejected
- Moderators can access GET /api/admin/bugs, /api/admin/users, /api/admin/stats, /api/admin/logs
- Moderators cannot update bug status (PUT /api/admin/bugs/{bug_id})
- Regular users cannot access admin endpoints (should get 403)
- Auth/me endpoint returns platform_role for all users
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Credentials from review_request
SUPER_ADMIN_SESSION = "Fp_kWAvgxh8krRP-eEhEicsB06MwP3UtRkzlM66fMVA"  # TEST_ADMIN_EMAIL
SUPER_ADMIN_USER_ID = "user_2742be3ace24"
TEST_USER_EMAIL = "testuser@test.com"
TEST_USER_PASSWORD = "Test1234!"
TEST_USER_ID = "user_32b6bdf8ce48"

class TestAdminCheck:
    """Admin check endpoint returns proper fields"""
    
    def test_admin_check_returns_required_fields(self):
        """GET /api/admin/check returns is_super_admin, is_staff, platform_role"""
        response = requests.get(
            f"{BASE_URL}/api/admin/check",
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields exist
        assert "is_super_admin" in data
        assert "is_staff" in data
        assert "platform_role" in data
        
        # Super admin should have all flags True and role=super_admin
        assert data["is_super_admin"] == True
        assert data["is_staff"] == True
        assert data["platform_role"] == "super_admin"
        print(f"Admin check response: {data}")
    
    def test_auth_me_returns_platform_role(self):
        """GET /api/auth/me returns platform_role for all users"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "platform_role" in data
        assert data["platform_role"] == "super_admin"
        print(f"Auth/me response includes platform_role: {data['platform_role']}")


class TestRoleManagement:
    """Super admin role change functionality"""
    
    @pytest.fixture
    def get_test_user_current_role(self):
        """Get current role of test user before changes"""
        response = requests.get(
            f"{BASE_URL}/api/admin/users",
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        if response.status_code == 200:
            users = response.json().get("users", [])
            for u in users:
                if u.get("user_id") == TEST_USER_ID:
                    return u.get("platform_role", "user")
        return "user"
    
    def test_super_admin_can_change_user_role_to_moderator(self):
        """PUT /api/admin/users/{user_id}/role changes role successfully"""
        response = requests.put(
            f"{BASE_URL}/api/admin/users/{TEST_USER_ID}/role",
            json={"platform_role": "moderator"},
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "updated"
        assert data["platform_role"] == "moderator"
        print(f"Role change response: {data}")
        
        # Verify the change persisted
        verify = requests.get(
            f"{BASE_URL}/api/admin/users",
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        users = verify.json().get("users", [])
        test_user = next((u for u in users if u.get("user_id") == TEST_USER_ID), None)
        assert test_user is not None
        assert test_user["platform_role"] == "moderator"
    
    def test_super_admin_can_change_user_role_to_admin(self):
        """Super admin can promote user to admin"""
        response = requests.put(
            f"{BASE_URL}/api/admin/users/{TEST_USER_ID}/role",
            json={"platform_role": "admin"},
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["platform_role"] == "admin"
        
    def test_super_admin_can_change_user_role_back_to_user(self):
        """Super admin can demote back to regular user"""
        response = requests.put(
            f"{BASE_URL}/api/admin/users/{TEST_USER_ID}/role",
            json={"platform_role": "user"},
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["platform_role"] == "user"
    
    def test_super_admin_cannot_change_own_role(self):
        """Super admin cannot modify their own role"""
        response = requests.put(
            f"{BASE_URL}/api/admin/users/{SUPER_ADMIN_USER_ID}/role",
            json={"platform_role": "admin"},
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        # Should be rejected with 400
        assert response.status_code == 400
        data = response.json()
        assert "Cannot change super admin role" in data.get("detail", "")
        print(f"Cannot change own role: {data}")
    
    def test_invalid_role_rejected(self):
        """Invalid role values are rejected with 400"""
        response = requests.put(
            f"{BASE_URL}/api/admin/users/{TEST_USER_ID}/role",
            json={"platform_role": "super_admin"},  # Not allowed to set super_admin via API
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        assert response.status_code == 400
        print(f"Invalid role rejection: {response.json()}")
        
    def test_invalid_role_value_invalid_string(self):
        """Garbage role values are rejected"""
        response = requests.put(
            f"{BASE_URL}/api/admin/users/{TEST_USER_ID}/role",
            json={"platform_role": "invalidrole123"},
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        assert response.status_code == 400


class TestModeratorAccess:
    """Moderators can view admin data but not modify"""
    
    @pytest.fixture(autouse=True)
    def setup_moderator_role(self):
        """Set test user to moderator role for these tests"""
        # Set as moderator
        requests.put(
            f"{BASE_URL}/api/admin/users/{TEST_USER_ID}/role",
            json={"platform_role": "moderator"},
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        
        # Login as test user to get session
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
        )
        if login_response.status_code == 200:
            self.moderator_session = login_response.cookies.get("session_token")
        else:
            pytest.skip("Could not login as test user")
        
        yield
        
        # Cleanup - set back to user role
        requests.put(
            f"{BASE_URL}/api/admin/users/{TEST_USER_ID}/role",
            json={"platform_role": "user"},
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
    
    def test_moderator_admin_check_shows_staff(self):
        """Moderator is_staff=True, is_super_admin=False"""
        response = requests.get(
            f"{BASE_URL}/api/admin/check",
            cookies={"session_token": self.moderator_session}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["is_staff"] == True
        assert data["is_super_admin"] == False
        assert data["platform_role"] == "moderator"
        print(f"Moderator admin check: {data}")
    
    def test_moderator_can_access_admin_bugs(self):
        """Moderator can GET /api/admin/bugs"""
        response = requests.get(
            f"{BASE_URL}/api/admin/bugs",
            cookies={"session_token": self.moderator_session}
        )
        assert response.status_code == 200
        data = response.json()
        assert "bugs" in data
        assert "stats" in data
        print(f"Moderator can view {len(data['bugs'])} bugs")
    
    def test_moderator_can_access_admin_users(self):
        """Moderator can GET /api/admin/users"""
        response = requests.get(
            f"{BASE_URL}/api/admin/users",
            cookies={"session_token": self.moderator_session}
        )
        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        print(f"Moderator can view {len(data['users'])} users")
    
    def test_moderator_can_access_admin_stats(self):
        """Moderator can GET /api/admin/stats"""
        response = requests.get(
            f"{BASE_URL}/api/admin/stats",
            cookies={"session_token": self.moderator_session}
        )
        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert "workspaces" in data
        print(f"Moderator can view stats")
    
    def test_moderator_can_access_admin_logs(self):
        """Moderator can GET /api/admin/logs"""
        response = requests.get(
            f"{BASE_URL}/api/admin/logs",
            cookies={"session_token": self.moderator_session}
        )
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        print(f"Moderator can view {len(data['logs'])} logs")
    
    def test_moderator_cannot_update_bug_status(self):
        """Moderator cannot PUT /api/admin/bugs/{bug_id} - should get 403"""
        # First get a bug id
        bugs_response = requests.get(
            f"{BASE_URL}/api/admin/bugs",
            cookies={"session_token": self.moderator_session}
        )
        bugs = bugs_response.json().get("bugs", [])
        if not bugs:
            pytest.skip("No bugs to test with")
        
        bug_id = bugs[0]["bug_id"]
        
        # Try to update bug status as moderator
        response = requests.put(
            f"{BASE_URL}/api/admin/bugs/{bug_id}",
            json={"status": "in_progress"},
            cookies={"session_token": self.moderator_session}
        )
        # Should be forbidden
        assert response.status_code == 403
        data = response.json()
        assert "Admin access required" in data.get("detail", "")
        print(f"Moderator correctly denied bug update: {data}")
    
    def test_moderator_cannot_change_user_roles(self):
        """Moderator cannot PUT /api/admin/users/{user_id}/role - should get 403"""
        # Create a dummy user ID to test with (or use a real one we know exists)
        response = requests.put(
            f"{BASE_URL}/api/admin/users/{TEST_USER_ID}/role",
            json={"platform_role": "admin"},
            cookies={"session_token": self.moderator_session}
        )
        # Should be forbidden
        assert response.status_code == 403
        print(f"Moderator correctly denied role change")


class TestRegularUserAccess:
    """Regular users get 403 on admin endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup_regular_user(self):
        """Ensure test user has 'user' role and get session"""
        # Set as regular user
        requests.put(
            f"{BASE_URL}/api/admin/users/{TEST_USER_ID}/role",
            json={"platform_role": "user"},
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        
        # Login as test user
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
        )
        if login_response.status_code == 200:
            self.user_session = login_response.cookies.get("session_token")
        else:
            pytest.skip("Could not login as test user")
        
        yield
    
    def test_regular_user_admin_check_not_staff(self):
        """Regular user is_staff=False, is_super_admin=False"""
        response = requests.get(
            f"{BASE_URL}/api/admin/check",
            cookies={"session_token": self.user_session}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["is_staff"] == False
        assert data["is_super_admin"] == False
        assert data["platform_role"] == "user"
        print(f"Regular user admin check: {data}")
    
    def test_regular_user_cannot_access_admin_bugs(self):
        """Regular user cannot GET /api/admin/bugs - should get 403"""
        response = requests.get(
            f"{BASE_URL}/api/admin/bugs",
            cookies={"session_token": self.user_session}
        )
        assert response.status_code == 403
        print(f"Regular user correctly denied admin/bugs access")
    
    def test_regular_user_cannot_access_admin_users(self):
        """Regular user cannot GET /api/admin/users - should get 403"""
        response = requests.get(
            f"{BASE_URL}/api/admin/users",
            cookies={"session_token": self.user_session}
        )
        assert response.status_code == 403
        print(f"Regular user correctly denied admin/users access")
    
    def test_regular_user_cannot_access_admin_stats(self):
        """Regular user cannot GET /api/admin/stats - should get 403"""
        response = requests.get(
            f"{BASE_URL}/api/admin/stats",
            cookies={"session_token": self.user_session}
        )
        assert response.status_code == 403
        print(f"Regular user correctly denied admin/stats access")
    
    def test_regular_user_cannot_access_admin_logs(self):
        """Regular user cannot GET /api/admin/logs - should get 403"""
        response = requests.get(
            f"{BASE_URL}/api/admin/logs",
            cookies={"session_token": self.user_session}
        )
        assert response.status_code == 403
        print(f"Regular user correctly denied admin/logs access")


class TestDownloadAndMyBugsEndpoints:
    """Test endpoints for /download and /my-bugs pages"""
    
    def test_my_bug_reports_endpoint_works(self):
        """GET /api/bugs/my-reports returns user's bug reports"""
        response = requests.get(
            f"{BASE_URL}/api/bugs/my-reports",
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        assert response.status_code == 200
        data = response.json()
        assert "bugs" in data
        assert "count" in data
        print(f"My bug reports: {data['count']} bugs")
    
    def test_api_health_check(self):
        """Basic API health check"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
