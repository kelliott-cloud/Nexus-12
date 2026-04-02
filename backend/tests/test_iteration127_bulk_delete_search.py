"""
Iteration 127 - Bug Fixes Tests
1. Bulk delete workspace function fix (POST /api/workspaces/bulk-delete)
2. Workspace search typeahead (GET /api/workspaces?search=...)

Tests verify:
- Bulk delete returns proper errors (not 403 workspace access error)
- Search filters results server-side
- Single workspace DELETE still works
- Login regression test
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication tests - regression"""
    
    @pytest.fixture(scope="class")
    def session(self):
        """Create authenticated session"""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        return s
    
    @pytest.fixture(scope="class")
    def auth_token(self, session):
        """Login and get session token"""
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": os.environ.get("TEST_ADMIN_EMAIL", "admin@test.local"),
            "password": "test"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "user_id" in data, "No user_id in login response"
        # Get session token from cookies
        token = session.cookies.get("session_token")
        return token
    
    def test_login_works(self, session, auth_token):
        """POST /api/auth/login still works (regression)"""
        assert auth_token is not None or session.cookies.get("session_token") is not None
        print("PASSED: Login works correctly")


class TestBulkDeleteFix:
    """Tests for bulk delete workspace fix - was intercepted by tenant middleware"""
    
    @pytest.fixture(scope="class")
    def session(self):
        """Create authenticated session"""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        # Login
        response = s.post(f"{BASE_URL}/api/auth/login", json={
            "email": os.environ.get("TEST_ADMIN_EMAIL", "admin@test.local"),
            "password": "test"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return s
    
    def test_bulk_delete_empty_list_returns_400(self, session):
        """POST /api/workspaces/bulk-delete with empty list returns 400 'No workspace IDs provided'"""
        response = session.post(f"{BASE_URL}/api/workspaces/bulk-delete", json={
            "workspace_ids": []
        })
        # Should return 400, NOT 403 (which would indicate tenant middleware intercepted it)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "No workspace IDs provided" in str(data.get("detail", "")), f"Wrong error message: {data}"
        print("PASSED: Bulk delete with empty list returns 400 'No workspace IDs provided'")
    
    def test_bulk_delete_fake_ids_returns_not_found(self, session):
        """POST /api/workspaces/bulk-delete with fake IDs returns proper response"""
        fake_id = "ws_fake123456789"
        response = session.post(f"{BASE_URL}/api/workspaces/bulk-delete", json={
            "workspace_ids": [fake_id]
        })
        # Should return 200 with results showing not_found, NOT 403
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "total_requested" in data, f"Missing total_requested: {data}"
        assert data["total_requested"] == 1, f"Wrong total_requested: {data}"
        assert data["deleted"] == 0, f"Should have deleted 0: {data}"
        assert "results" in data, f"Missing results: {data}"
        assert len(data["results"]) == 1, f"Should have 1 result: {data}"
        assert data["results"][0]["status"] == "not_found", f"Wrong status: {data['results']}"
        print("PASSED: Bulk delete with fake IDs returns {total_requested: 1, deleted: 0, results: [{status: 'not_found'}]}")
    
    def test_bulk_delete_not_intercepted_by_tenant_middleware(self, session):
        """Verify bulk-delete is NOT treated as workspace_id by tenant middleware"""
        # The bug was: /workspaces/bulk-delete was matched as workspace_id='bulk-delete'
        # which caused 403 "You do not have access to this workspace"
        response = session.post(f"{BASE_URL}/api/workspaces/bulk-delete", json={
            "workspace_ids": ["ws_nonexistent"]
        })
        # Should NOT be 403 with "You do not have access to this workspace"
        if response.status_code == 403:
            data = response.json()
            assert "You do not have access to this workspace" not in str(data.get("detail", "")), \
                f"BUG: Tenant middleware intercepted bulk-delete as workspace_id: {data}"
        print("PASSED: Bulk delete not intercepted by tenant middleware")


class TestWorkspaceSearchTypeahead:
    """Tests for workspace search with server-side typeahead"""
    
    @pytest.fixture(scope="class")
    def session(self):
        """Create authenticated session"""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        # Login
        response = s.post(f"{BASE_URL}/api/auth/login", json={
            "email": os.environ.get("TEST_ADMIN_EMAIL", "admin@test.local"),
            "password": "test"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return s
    
    def test_search_no_param_returns_all(self, session):
        """GET /api/workspaces (no search) returns all workspaces"""
        response = session.get(f"{BASE_URL}/api/workspaces")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        all_count = len(data)
        print(f"PASSED: GET /workspaces returns {all_count} workspaces")
        return all_count
    
    def test_search_with_query_filters_results(self, session):
        """GET /api/workspaces?search=Zip returns filtered results"""
        # First get all workspaces
        all_response = session.get(f"{BASE_URL}/api/workspaces")
        all_workspaces = all_response.json()
        all_count = len(all_workspaces)
        
        # Now search for "Zip"
        response = session.get(f"{BASE_URL}/api/workspaces?search=Zip")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        
        # Should return fewer results than all (unless all match "Zip")
        search_count = len(data)
        print(f"Search 'Zip' returned {search_count} results (all: {all_count})")
        
        # Verify all returned workspaces contain "Zip" in name or description
        for ws in data:
            name = (ws.get("name") or "").lower()
            desc = (ws.get("description") or "").lower()
            assert "zip" in name or "zip" in desc, \
                f"Workspace '{ws.get('name')}' doesn't match search 'Zip'"
        
        print(f"PASSED: Search 'Zip' returns {search_count} filtered results")
    
    def test_search_nonexistent_returns_empty(self, session):
        """GET /api/workspaces?search=zzzznonexistent returns empty list"""
        response = session.get(f"{BASE_URL}/api/workspaces?search=zzzznonexistent")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        assert len(data) == 0, f"Expected empty list, got {len(data)} results"
        print("PASSED: Search 'zzzznonexistent' returns empty list")
    
    def test_search_case_insensitive(self, session):
        """Search should be case-insensitive"""
        # Search with different cases
        response_lower = session.get(f"{BASE_URL}/api/workspaces?search=zip")
        response_upper = session.get(f"{BASE_URL}/api/workspaces?search=ZIP")
        response_mixed = session.get(f"{BASE_URL}/api/workspaces?search=Zip")
        
        assert response_lower.status_code == 200
        assert response_upper.status_code == 200
        assert response_mixed.status_code == 200
        
        # All should return same count
        count_lower = len(response_lower.json())
        count_upper = len(response_upper.json())
        count_mixed = len(response_mixed.json())
        
        assert count_lower == count_upper == count_mixed, \
            f"Case sensitivity issue: lower={count_lower}, upper={count_upper}, mixed={count_mixed}"
        print(f"PASSED: Search is case-insensitive (all return {count_lower} results)")


class TestSingleWorkspaceDelete:
    """Tests for single workspace DELETE (should still work via routes_workspace_deletion.py)"""
    
    @pytest.fixture(scope="class")
    def session(self):
        """Create authenticated session"""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        # Login
        response = s.post(f"{BASE_URL}/api/auth/login", json={
            "email": os.environ.get("TEST_ADMIN_EMAIL", "admin@test.local"),
            "password": "test"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return s
    
    def test_delete_nonexistent_workspace_returns_403_or_404(self, session):
        """DELETE /api/workspaces/{fake_id} returns 403 (no access) or 404 (not found)
        
        Note: Tenant middleware returns 403 for workspaces user doesn't have access to,
        which includes nonexistent workspaces. This is correct security behavior.
        """
        fake_id = "ws_nonexistent123"
        response = session.delete(f"{BASE_URL}/api/workspaces/{fake_id}")
        # 403 is expected because tenant middleware checks access before route handler
        # 404 would be returned if workspace existed but was deleted
        assert response.status_code in [403, 404], f"Expected 403 or 404, got {response.status_code}: {response.text}"
        print(f"PASSED: DELETE nonexistent workspace returns {response.status_code}")
    
    def test_delete_preview_nonexistent_returns_403_or_404(self, session):
        """GET /api/workspaces/{fake_id}/delete-preview returns 403 (no access) or 404
        
        Note: Tenant middleware returns 403 for workspaces user doesn't have access to.
        """
        fake_id = "ws_nonexistent123"
        response = session.get(f"{BASE_URL}/api/workspaces/{fake_id}/delete-preview")
        assert response.status_code in [403, 404], f"Expected 403 or 404, got {response.status_code}: {response.text}"
        print(f"PASSED: DELETE preview nonexistent workspace returns {response.status_code}")


class TestTenantMiddlewareBypass:
    """Verify tenant middleware correctly bypasses bulk-delete pattern"""
    
    @pytest.fixture(scope="class")
    def session(self):
        """Create authenticated session"""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        # Login
        response = s.post(f"{BASE_URL}/api/auth/login", json={
            "email": os.environ.get("TEST_ADMIN_EMAIL", "admin@test.local"),
            "password": "test"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return s
    
    def test_bulk_delete_bypass_in_middleware(self, session):
        """Verify 'bulk-delete' is in tenant middleware bypass list"""
        # This test verifies the fix by checking the response
        # If middleware intercepts, we'd get 403 "You do not have access to this workspace"
        response = session.post(f"{BASE_URL}/api/workspaces/bulk-delete", json={
            "workspace_ids": []
        })
        
        # Should be 400 (empty list), not 403 (middleware intercept)
        assert response.status_code != 403 or "You do not have access" not in response.text, \
            f"Tenant middleware still intercepting bulk-delete: {response.text}"
        print("PASSED: Tenant middleware correctly bypasses bulk-delete")


class TestHealthEndpoint:
    """Basic health check"""
    
    def test_health(self):
        """GET /api/health returns healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data.get("status") == "healthy", f"Unhealthy: {data}"
        print("PASSED: Health endpoint returns healthy")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
