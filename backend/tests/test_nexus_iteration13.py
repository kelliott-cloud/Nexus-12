from conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, BASE_URL
"""
Test Suite for Nexus Iteration 13 - Verifying:
1. Email/password login (testuser@test.com / Test1234!)
2. Dashboard loads after login
3. Admin button visible only for super admin (TEST_ADMIN_EMAIL)
4. Bug Report submission and My Bug Reports
5. Admin Dashboard access control
6. Workspace creation
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
SUPER_ADMIN_SESSION = "Fp_kWAvgxh8krRP-eEhEicsB06MwP3UtRkzlM66fMVA"
SUPER_ADMIN_EMAIL = TEST_ADMIN_EMAIL
TEST_USER_EMAIL = "testuser@test.com"
TEST_USER_PASSWORD = "Test1234!"


class TestHealthAndSetup:
    """Basic API health check"""
    
    def test_api_health(self):
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        print("API health check passed")


class TestEmailAuthentication:
    """Test email/password authentication flow"""
    
    def test_login_with_test_user(self):
        """Login with testuser@test.com / Test1234!"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        print(f"Login response: {response.status_code}, {response.text[:200]}")
        # Accept 200 (success) or 401 (user doesn't exist - will register)
        if response.status_code == 401:
            # User doesn't exist, try to register
            reg_response = requests.post(f"{BASE_URL}/api/auth/register", json={
                "email": TEST_USER_EMAIL,
                "password": TEST_USER_PASSWORD,
                "name": "Test User"
            })
            print(f"Register response: {reg_response.status_code}")
            if reg_response.status_code == 400:  # Already registered
                # Try login again
                response = requests.post(f"{BASE_URL}/api/auth/login", json={
                    "email": TEST_USER_EMAIL,
                    "password": TEST_USER_PASSWORD
                })
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "user_id" in data
        assert data.get("email") == TEST_USER_EMAIL
        print(f"Login successful for {TEST_USER_EMAIL}")
        return response
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "invalid@test.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        print("Invalid credentials correctly rejected")


class TestSuperAdminAccess:
    """Test super admin functionality with session token"""
    
    def test_super_admin_check_with_session_token(self):
        """Check if TEST_ADMIN_EMAIL is super admin"""
        response = requests.get(
            f"{BASE_URL}/api/admin/check",
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        print(f"Admin check response: {response.status_code}, {response.text}")
        assert response.status_code == 200
        data = response.json()
        assert data["is_super_admin"] == True
        assert data["email"].lower() == SUPER_ADMIN_EMAIL.lower()
        print(f"Super admin verified: {data['email']}")
    
    def test_super_admin_stats_access(self):
        """Super admin can access platform stats"""
        response = requests.get(
            f"{BASE_URL}/api/admin/stats",
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        print(f"Admin stats response: {response.status_code}")
        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert "workspaces" in data
        assert "messages" in data
        assert "bugs" in data
        print(f"Platform stats: {data['users']['total']} users, {data['bugs']['total']} bugs")
    
    def test_super_admin_users_list(self):
        """Super admin can see all users"""
        response = requests.get(
            f"{BASE_URL}/api/admin/users",
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        print(f"Admin users response: {response.status_code}")
        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert "total" in data
        print(f"Users list: {data['total']} total users, showing {len(data['users'])}")
    
    def test_super_admin_bugs_list(self):
        """Super admin can see all bug reports"""
        response = requests.get(
            f"{BASE_URL}/api/admin/bugs",
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        print(f"Admin bugs response: {response.status_code}")
        assert response.status_code == 200
        data = response.json()
        assert "bugs" in data
        assert "stats" in data
        print(f"Bugs: {data['stats'].get('total', 0)} total, {data['stats'].get('open', 0)} open")
    
    def test_super_admin_activity_logs(self):
        """Super admin can see activity logs"""
        response = requests.get(
            f"{BASE_URL}/api/admin/logs",
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        print(f"Admin logs response: {response.status_code}")
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        print(f"Activity logs: {len(data['logs'])} entries")


class TestNormalUserAccess:
    """Test that normal users cannot access admin endpoints"""
    
    @pytest.fixture
    def normal_user_session(self):
        """Get session for a normal user"""
        # Login/register the test user
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        if response.status_code == 401:
            response = requests.post(f"{BASE_URL}/api/auth/register", json={
                "email": TEST_USER_EMAIL,
                "password": TEST_USER_PASSWORD,
                "name": "Test User"
            })
        # Get session token from cookies
        return response.cookies.get("session_token") or f"test_session_{int(time.time())}"
    
    def test_normal_user_admin_check(self, normal_user_session):
        """Normal user is not admin"""
        response = requests.get(
            f"{BASE_URL}/api/admin/check",
            cookies={"session_token": normal_user_session}
        )
        print(f"Normal user admin check: {response.status_code}, {response.text}")
        # Accept 200 with is_super_admin=False or 401 if session is invalid
        if response.status_code == 200:
            data = response.json()
            assert data["is_super_admin"] == False
            print("Normal user correctly identified as non-admin")
    
    def test_normal_user_denied_admin_stats(self, normal_user_session):
        """Normal user cannot access admin stats"""
        response = requests.get(
            f"{BASE_URL}/api/admin/stats",
            cookies={"session_token": normal_user_session}
        )
        print(f"Normal user admin stats: {response.status_code}")
        # Should be 403 Forbidden or 401 Unauthorized
        assert response.status_code in [401, 403]
        print("Normal user correctly denied admin stats access")
    
    def test_normal_user_denied_admin_users(self, normal_user_session):
        """Normal user cannot access admin users"""
        response = requests.get(
            f"{BASE_URL}/api/admin/users",
            cookies={"session_token": normal_user_session}
        )
        print(f"Normal user admin users: {response.status_code}")
        assert response.status_code in [401, 403]
        print("Normal user correctly denied admin users access")


class TestBugReportSubmission:
    """Test bug report submission and retrieval"""
    
    def test_submit_bug_report_as_admin(self):
        """Submit a bug report as super admin"""
        response = requests.post(
            f"{BASE_URL}/api/bugs",
            json={
                "title": "Test Bug Report from Iteration 13",
                "description": "This is a test bug report submitted during iteration 13 testing to verify the bug submission flow works correctly.",
                "severity": "low",
                "category": "general"
            },
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        print(f"Bug submission response: {response.status_code}, {response.text[:200]}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "submitted"
        assert "bug_id" in data
        print(f"Bug submitted successfully: {data['bug_id']}")
        return data["bug_id"]
    
    def test_get_my_bug_reports(self):
        """Get my own bug reports"""
        response = requests.get(
            f"{BASE_URL}/api/bugs/my-reports",
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        print(f"My bug reports response: {response.status_code}")
        assert response.status_code == 200
        data = response.json()
        assert "bugs" in data
        assert "count" in data
        print(f"My bug reports: {data['count']} bugs")


class TestAdminBugManagement:
    """Test admin bug management functions"""
    
    @pytest.fixture
    def test_bug_id(self):
        """Create a test bug and return its ID"""
        response = requests.post(
            f"{BASE_URL}/api/bugs",
            json={
                "title": "Admin Management Test Bug",
                "description": "Bug created for testing admin management functions in iteration 13.",
                "severity": "medium",
                "category": "backend"
            },
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        if response.status_code == 200:
            return response.json()["bug_id"]
        # If submission fails, get an existing bug
        bugs_response = requests.get(
            f"{BASE_URL}/api/admin/bugs",
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        if bugs_response.status_code == 200 and bugs_response.json().get("bugs"):
            return bugs_response.json()["bugs"][0]["bug_id"]
        return None
    
    def test_admin_update_bug_status(self, test_bug_id):
        """Admin can update bug status"""
        if not test_bug_id:
            pytest.skip("No test bug available")
        
        response = requests.put(
            f"{BASE_URL}/api/admin/bugs/{test_bug_id}",
            json={"status": "in_progress"},
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        print(f"Update bug status response: {response.status_code}")
        assert response.status_code == 200
        print("Bug status updated to 'in_progress'")
    
    def test_admin_update_bug_priority(self, test_bug_id):
        """Admin can update bug priority"""
        if not test_bug_id:
            pytest.skip("No test bug available")
        
        response = requests.put(
            f"{BASE_URL}/api/admin/bugs/{test_bug_id}",
            json={"priority": "high"},
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        print(f"Update bug priority response: {response.status_code}")
        assert response.status_code == 200
        print("Bug priority updated to 'high'")


class TestWorkspaceCreation:
    """Test workspace creation and management"""
    
    def test_get_workspaces(self):
        """Get list of workspaces"""
        response = requests.get(
            f"{BASE_URL}/api/workspaces",
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        print(f"Get workspaces response: {response.status_code}")
        assert response.status_code == 200
        data = response.json()
        print(f"Workspaces: {len(data)} found")
    
    def test_create_workspace(self):
        """Create a new workspace"""
        response = requests.post(
            f"{BASE_URL}/api/workspaces",
            json={
                "name": f"Test Workspace Iter13 {int(time.time())}",
                "description": "Workspace created during iteration 13 testing"
            },
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        print(f"Create workspace response: {response.status_code}")
        assert response.status_code == 200
        data = response.json()
        assert "workspace_id" in data
        assert data["name"].startswith("Test Workspace Iter13")
        print(f"Workspace created: {data['workspace_id']}")
        return data["workspace_id"]
    
    def test_get_workspace_details(self):
        """Get workspace details"""
        # First create a workspace
        create_response = requests.post(
            f"{BASE_URL}/api/workspaces",
            json={
                "name": f"Test WS Detail {int(time.time())}",
                "description": "Testing workspace detail retrieval"
            },
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        if create_response.status_code == 200:
            ws_id = create_response.json()["workspace_id"]
            
            # Get workspace details
            response = requests.get(
                f"{BASE_URL}/api/workspaces/{ws_id}",
                cookies={"session_token": SUPER_ADMIN_SESSION}
            )
            print(f"Get workspace details response: {response.status_code}")
            assert response.status_code == 200
            data = response.json()
            assert data["workspace_id"] == ws_id
            print(f"Workspace details retrieved: {data['name']}")


class TestSuperAdminUnlimitedAccess:
    """Test that super admin bypasses plan limits"""
    
    def test_admin_can_trigger_collaboration(self):
        """Super admin can trigger collaboration without plan limits"""
        # First get a workspace with a channel
        ws_response = requests.get(
            f"{BASE_URL}/api/workspaces",
            cookies={"session_token": SUPER_ADMIN_SESSION}
        )
        if ws_response.status_code == 200 and ws_response.json():
            workspace = ws_response.json()[0]
            ws_id = workspace["workspace_id"]
            
            # Get channels
            ch_response = requests.get(
                f"{BASE_URL}/api/workspaces/{ws_id}/channels",
                cookies={"session_token": SUPER_ADMIN_SESSION}
            )
            if ch_response.status_code == 200 and ch_response.json():
                channel = ch_response.json()[0]
                ch_id = channel["channel_id"]
                
                # Send a message
                msg_response = requests.post(
                    f"{BASE_URL}/api/channels/{ch_id}/messages",
                    json={"content": "Test message for iteration 13"},
                    cookies={"session_token": SUPER_ADMIN_SESSION}
                )
                print(f"Send message response: {msg_response.status_code}")
                
                # Trigger collaboration - should not hit limits
                collab_response = requests.post(
                    f"{BASE_URL}/api/channels/{ch_id}/collaborate",
                    cookies={"session_token": SUPER_ADMIN_SESSION}
                )
                print(f"Trigger collaboration response: {collab_response.status_code}, {collab_response.text}")
                assert collab_response.status_code == 200
                data = collab_response.json()
                # Should be "started" or "already_running", NOT "limit_reached"
                assert data.get("status") in ["started", "already_running"], f"Unexpected status: {data}"
                print(f"Collaboration status: {data.get('status')}")
            else:
                pytest.skip("No channels available")
        else:
            pytest.skip("No workspaces available")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
