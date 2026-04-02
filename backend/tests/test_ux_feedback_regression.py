"""
Regression tests for UX feedback iteration - testing backend APIs remain functional
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s

@pytest.fixture
def auth_session(session):
    """Login and return authenticated session"""
    login_res = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "testmention@test.com",
        "password": "Test1234!"
    })
    if login_res.status_code == 200:
        token = login_res.json().get("token")
        if token:
            session.headers.update({"Authorization": f"Bearer {token}"})
    return session


class TestBackendRegression:
    """Verify critical backend APIs still work after UX changes"""
    
    def test_health_endpoint(self, session):
        """GET /api/health - Health check"""
        res = session.get(f"{BASE_URL}/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") in ["healthy", "ok"]
        print("PASS: Health endpoint returns healthy status")
    
    def test_auth_login(self, session):
        """POST /api/auth/login - Login with test credentials"""
        res = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testmention@test.com",
            "password": "Test1234!"
        })
        assert res.status_code == 200
        data = res.json()
        # Login returns user data directly with user_id
        assert "user_id" in data or "token" in data
        assert "email" in data or "user" in data
        print(f"PASS: Login successful for user {data.get('email', data.get('user', {}).get('email'))}")
    
    def test_auth_me(self, auth_session):
        """GET /api/auth/me - Get current user"""
        res = auth_session.get(f"{BASE_URL}/api/auth/me")
        assert res.status_code == 200
        data = res.json()
        assert "email" in data
        assert "user_id" in data
        print(f"PASS: Auth/me returns user {data.get('email')}")
    
    def test_workspaces_list(self, auth_session):
        """GET /api/workspaces - List workspaces"""
        res = auth_session.get(f"{BASE_URL}/api/workspaces")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        print(f"PASS: Workspaces list returns {len(data)} workspaces")
    
    def test_settings_ai_keys(self, auth_session):
        """GET /api/settings/ai-keys - Get AI keys status"""
        res = auth_session.get(f"{BASE_URL}/api/settings/ai-keys")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, dict)
        print(f"PASS: AI keys endpoint returns {len(data)} agent configurations")
    
    def test_create_and_delete_workspace(self, auth_session):
        """POST/DELETE /api/workspaces - Create and delete workspace"""
        # Create
        create_res = auth_session.post(f"{BASE_URL}/api/workspaces", json={
            "name": "TEST_UX_REGRESSION_WS",
            "description": "Test workspace for UX regression"
        })
        assert create_res.status_code == 200
        ws_data = create_res.json()
        assert "workspace_id" in ws_data
        ws_id = ws_data["workspace_id"]
        print(f"PASS: Created workspace {ws_id}")
        
        # Get workspace details
        get_res = auth_session.get(f"{BASE_URL}/api/workspaces/{ws_id}")
        assert get_res.status_code == 200
        assert get_res.json()["name"] == "TEST_UX_REGRESSION_WS"
        print("PASS: Workspace GET returns correct data")
        
        # Delete
        del_res = auth_session.delete(f"{BASE_URL}/api/workspaces/{ws_id}")
        assert del_res.status_code == 200
        print("PASS: Workspace deleted successfully")

    def test_workspace_gantt_endpoint(self, auth_session):
        """GET /api/workspaces/{id}/gantt - Gantt chart data"""
        # Get first workspace
        ws_res = auth_session.get(f"{BASE_URL}/api/workspaces")
        if ws_res.status_code == 200 and len(ws_res.json()) > 0:
            ws_id = ws_res.json()[0]["workspace_id"]
            gantt_res = auth_session.get(f"{BASE_URL}/api/workspaces/{ws_id}/gantt")
            assert gantt_res.status_code == 200
            data = gantt_res.json()
            assert "items" in data
            print(f"PASS: Gantt endpoint returns {len(data['items'])} items")
        else:
            pytest.skip("No workspaces available for gantt test")

    def test_notifications_endpoint(self, auth_session):
        """GET /api/notifications - User notifications"""
        res = auth_session.get(f"{BASE_URL}/api/notifications")
        assert res.status_code == 200
        data = res.json()
        assert "notifications" in data
        print(f"PASS: Notifications endpoint returns {len(data['notifications'])} notifications")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
