"""
Iteration 122 - P2 Backlog Features Testing
Tests for:
1. Alert history endpoint with pagination and filters
2. Dismiss alert endpoint
3. Budget tracking in image gen, image understanding, research routes
4. Regression tests for dashboard, alerts, login
5. Org admin audit/export endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

class TestAuthRegression:
    """Regression: Login still works"""
    
    def test_login_success(self):
        """POST /api/auth/login - Super admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": os.environ.get("TEST_ADMIN_EMAIL", "admin@test.local"),
            "password": "test"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "session_token" in data or "user_id" in data, f"Missing auth data: {data}"
        print(f"✓ Login successful: user_id={data.get('user_id')}")


class TestManagedKeysAlertHistory:
    """Tests for new alert history endpoint with pagination and filters"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get session"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": os.environ.get("TEST_ADMIN_EMAIL", "admin@test.local"),
            "password": "test"
        })
        assert login_res.status_code == 200
        self.session = requests.Session()
        cookies = login_res.cookies
        for cookie in cookies:
            self.session.cookies.set(cookie.name, cookie.value)
    
    def test_alert_history_endpoint_exists(self):
        """GET /api/admin/managed-keys/alerts/history - endpoint exists and returns paginated data"""
        response = self.session.get(f"{BASE_URL}/api/admin/managed-keys/alerts/history")
        assert response.status_code == 200, f"Alert history failed: {response.text}"
        data = response.json()
        assert "alerts" in data, f"Missing alerts key: {data}"
        assert "total" in data, f"Missing total key: {data}"
        assert "offset" in data, f"Missing offset key: {data}"
        assert "limit" in data, f"Missing limit key: {data}"
        print(f"✓ Alert history: {data['total']} total alerts, showing {len(data['alerts'])}")
    
    def test_alert_history_pagination(self):
        """GET /api/admin/managed-keys/alerts/history - pagination works"""
        response = self.session.get(f"{BASE_URL}/api/admin/managed-keys/alerts/history?limit=5&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 5
        assert data["offset"] == 0
        print(f"✓ Pagination works: limit={data['limit']}, offset={data['offset']}")
    
    def test_alert_history_filter_by_type(self):
        """GET /api/admin/managed-keys/alerts/history - filter by alert_type"""
        response = self.session.get(f"{BASE_URL}/api/admin/managed-keys/alerts/history?alert_type=warning")
        assert response.status_code == 200
        data = response.json()
        # All returned alerts should be of type 'warning' (if any)
        for alert in data.get("alerts", []):
            assert alert.get("alert_type") == "warning", f"Filter failed: {alert}"
        print(f"✓ Filter by type works: {len(data['alerts'])} warning alerts")
    
    def test_alert_history_filter_by_provider(self):
        """GET /api/admin/managed-keys/alerts/history - filter by provider"""
        response = self.session.get(f"{BASE_URL}/api/admin/managed-keys/alerts/history?provider=chatgpt")
        assert response.status_code == 200
        data = response.json()
        # All returned alerts should be for 'chatgpt' provider (if any)
        for alert in data.get("alerts", []):
            assert alert.get("provider") == "chatgpt", f"Filter failed: {alert}"
        print(f"✓ Filter by provider works: {len(data['alerts'])} chatgpt alerts")


class TestDismissAlert:
    """Tests for dismiss alert endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get session"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": os.environ.get("TEST_ADMIN_EMAIL", "admin@test.local"),
            "password": "test"
        })
        assert login_res.status_code == 200
        self.session = requests.Session()
        cookies = login_res.cookies
        for cookie in cookies:
            self.session.cookies.set(cookie.name, cookie.value)
    
    def test_dismiss_alert_endpoint_exists(self):
        """PUT /api/admin/managed-keys/alerts/{alert_key}/dismiss - endpoint exists"""
        # First get an alert key from history
        history_res = self.session.get(f"{BASE_URL}/api/admin/managed-keys/alerts/history?limit=1")
        assert history_res.status_code == 200
        alerts = history_res.json().get("alerts", [])
        
        if alerts:
            alert_key = alerts[0].get("alert_key")
            response = self.session.put(f"{BASE_URL}/api/admin/managed-keys/alerts/{alert_key}/dismiss")
            assert response.status_code == 200, f"Dismiss failed: {response.text}"
            data = response.json()
            assert data.get("status") == "dismissed", f"Unexpected response: {data}"
            print(f"✓ Dismiss alert works: {alert_key}")
        else:
            # No alerts to dismiss, test with a fake key to verify 404
            response = self.session.put(f"{BASE_URL}/api/admin/managed-keys/alerts/fake_alert_key/dismiss")
            assert response.status_code == 404, f"Expected 404 for fake alert: {response.status_code}"
            print("✓ Dismiss endpoint returns 404 for non-existent alert")


class TestManagedKeysDashboardRegression:
    """Regression: Dashboard endpoint still works"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get session"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": os.environ.get("TEST_ADMIN_EMAIL", "admin@test.local"),
            "password": "test"
        })
        assert login_res.status_code == 200
        self.session = requests.Session()
        cookies = login_res.cookies
        for cookie in cookies:
            self.session.cookies.set(cookie.name, cookie.value)
    
    def test_dashboard_endpoint(self):
        """GET /api/admin/managed-keys/dashboard - still works"""
        response = self.session.get(f"{BASE_URL}/api/admin/managed-keys/dashboard")
        assert response.status_code == 200, f"Dashboard failed: {response.text}"
        data = response.json()
        assert "month_key" in data or "total_cost_usd" in data or "providers" in data, f"Unexpected response: {data}"
        print(f"✓ Dashboard works: {data.get('month_key', 'N/A')}")
    
    def test_alerts_endpoint(self):
        """GET /api/admin/managed-keys/alerts - still works"""
        response = self.session.get(f"{BASE_URL}/api/admin/managed-keys/alerts")
        assert response.status_code == 200, f"Alerts failed: {response.text}"
        data = response.json()
        assert "alerts" in data, f"Missing alerts key: {data}"
        print(f"✓ Alerts endpoint works: {len(data['alerts'])} alerts")


class TestOrgAdminAuditEndpoints:
    """Tests for new org admin audit/export endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get session, find an org"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": os.environ.get("TEST_ADMIN_EMAIL", "admin@test.local"),
            "password": "test"
        })
        assert login_res.status_code == 200
        self.session = requests.Session()
        cookies = login_res.cookies
        for cookie in cookies:
            self.session.cookies.set(cookie.name, cookie.value)
        
        # Get user's orgs
        orgs_res = self.session.get(f"{BASE_URL}/api/orgs/my-orgs")
        self.orgs = orgs_res.json().get("organizations", []) if orgs_res.status_code == 200 else []
        self.org_id = self.orgs[0]["org_id"] if self.orgs else None
    
    def test_org_audit_log_endpoint(self):
        """GET /api/orgs/{org_id}/admin/audit-log - returns paginated audit log"""
        if not self.org_id:
            pytest.skip("No org available for testing")
        
        response = self.session.get(f"{BASE_URL}/api/orgs/{self.org_id}/admin/audit-log")
        assert response.status_code == 200, f"Audit log failed: {response.text}"
        data = response.json()
        assert "logs" in data, f"Missing logs key: {data}"
        assert "total" in data, f"Missing total key: {data}"
        print(f"✓ Org audit log works: {data['total']} total logs")
    
    def test_org_audit_log_actions(self):
        """GET /api/orgs/{org_id}/admin/audit-log/actions - returns distinct actions"""
        if not self.org_id:
            pytest.skip("No org available for testing")
        
        response = self.session.get(f"{BASE_URL}/api/orgs/{self.org_id}/admin/audit-log/actions")
        assert response.status_code == 200, f"Audit actions failed: {response.text}"
        data = response.json()
        assert "actions" in data, f"Missing actions key: {data}"
        print(f"✓ Org audit actions works: {len(data['actions'])} distinct actions")
    
    def test_org_budget_audit_endpoint(self):
        """GET /api/orgs/{org_id}/admin/budget-audit - returns budget usage events"""
        if not self.org_id:
            pytest.skip("No org available for testing")
        
        response = self.session.get(f"{BASE_URL}/api/orgs/{self.org_id}/admin/budget-audit")
        assert response.status_code == 200, f"Budget audit failed: {response.text}"
        data = response.json()
        assert "events" in data, f"Missing events key: {data}"
        assert "total" in data, f"Missing total key: {data}"
        assert "spend_by_provider" in data, f"Missing spend_by_provider key: {data}"
        print(f"✓ Org budget audit works: {data['total']} events, {len(data['spend_by_provider'])} providers")
    
    def test_org_member_activity_endpoint(self):
        """GET /api/orgs/{org_id}/admin/member-activity - returns member activity summary"""
        if not self.org_id:
            pytest.skip("No org available for testing")
        
        response = self.session.get(f"{BASE_URL}/api/orgs/{self.org_id}/admin/member-activity")
        assert response.status_code == 200, f"Member activity failed: {response.text}"
        data = response.json()
        assert "members" in data, f"Missing members key: {data}"
        print(f"✓ Org member activity works: {len(data['members'])} members")
    
    def test_org_export_csv_audit(self):
        """GET /api/orgs/{org_id}/admin/export/csv?data_type=audit - returns CSV"""
        if not self.org_id:
            pytest.skip("No org available for testing")
        
        response = self.session.get(f"{BASE_URL}/api/orgs/{self.org_id}/admin/export/csv?data_type=audit")
        assert response.status_code == 200, f"Export audit CSV failed: {response.text}"
        assert "text/csv" in response.headers.get("content-type", ""), f"Not CSV: {response.headers}"
        print("✓ Org export audit CSV works")
    
    def test_org_export_csv_budget(self):
        """GET /api/orgs/{org_id}/admin/export/csv?data_type=budget - returns CSV"""
        if not self.org_id:
            pytest.skip("No org available for testing")
        
        response = self.session.get(f"{BASE_URL}/api/orgs/{self.org_id}/admin/export/csv?data_type=budget")
        assert response.status_code == 200, f"Export budget CSV failed: {response.text}"
        assert "text/csv" in response.headers.get("content-type", ""), f"Not CSV: {response.headers}"
        print("✓ Org export budget CSV works")
    
    def test_org_export_csv_members(self):
        """GET /api/orgs/{org_id}/admin/export/csv?data_type=members - returns CSV"""
        if not self.org_id:
            pytest.skip("No org available for testing")
        
        response = self.session.get(f"{BASE_URL}/api/orgs/{self.org_id}/admin/export/csv?data_type=members")
        assert response.status_code == 200, f"Export members CSV failed: {response.text}"
        assert "text/csv" in response.headers.get("content-type", ""), f"Not CSV: {response.headers}"
        print("✓ Org export members CSV works")


class TestBudgetTrackingCodePresence:
    """Verify budget tracking code exists in image gen, image understanding, research routes"""
    
    def test_image_gen_budget_precheck(self):
        """routes_image_gen.py has budget pre-check code"""
        with open("/app/backend/routes/routes_image_gen.py", "r") as f:
            content = f.read()
        
        assert "check_usage_budget" in content, "Missing check_usage_budget import/call"
        assert "budget.get(\"blocked\")" in content or 'budget.get("blocked")' in content, "Missing blocked check"
        assert "record_usage_event" in content, "Missing record_usage_event call"
        print("✓ Image gen has budget pre-check and post-record")
    
    def test_image_understanding_budget_precheck(self):
        """routes_image_understanding.py has budget pre-check code"""
        with open("/app/backend/routes/routes_image_understanding.py", "r") as f:
            content = f.read()
        
        assert "check_usage_budget" in content, "Missing check_usage_budget import/call"
        assert "budget.get(\"blocked\")" in content or 'budget.get("blocked")' in content, "Missing blocked check"
        assert "record_usage_event" in content, "Missing record_usage_event call"
        print("✓ Image understanding has budget pre-check and post-record")
    
    def test_research_budget_precheck(self):
        """routes_research.py has budget pre-check code"""
        with open("/app/backend/routes/routes_research.py", "r") as f:
            content = f.read()
        
        assert "check_usage_budget" in content, "Missing check_usage_budget import/call"
        assert "budget.get(\"blocked\")" in content or 'budget.get("blocked")' in content, "Missing blocked check"
        assert "record_usage_event" in content, "Missing record_usage_event call"
        print("✓ Research has budget pre-check and post-record")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
