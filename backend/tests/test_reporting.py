"""
Iteration 69 - Enterprise Reporting Engine Tests
Tests for:
- Personal usage metrics (GET /api/reports/me/usage)
- CSV/JSON/PDF exports (GET /api/reports/export?format=...)
- Platform health/business (403 for non-admin)
- Org usage/users (403 for non-org-admin)
- Budget governance (PUT/GET /api/reports/org/{org_id}/budget)
- Alerts (403 for non-admin)
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "rptqa@test.com"
TEST_PASSWORD = "ReportQA123!"


class TestReportingEngine:
    """Test the new enterprise reporting engine endpoints"""
    
    @classmethod
    def setup_class(cls):
        """Create test user and session for authenticated requests"""
        cls.session = requests.Session()
        cls.session.headers.update({"Content-Type": "application/json"})
        
        unique_id = uuid.uuid4().hex[:8]
        cls.test_email = f"TEST_report_{unique_id}@test.com"
        cls.test_password = "SecurePass123!"
        name = f"Report Test User {unique_id}"
        
        # Register user
        reg_response = cls.session.post(f"{BASE_URL}/api/auth/register", json={
            "email": cls.test_email,
            "password": cls.test_password,
            "name": name
        })
        
        if reg_response.status_code in [200, 201]:
            cls.user_id = reg_response.json().get("user_id")
            print(f"Registered user: {cls.test_email}")
        else:
            # Try login
            login_response = cls.session.post(f"{BASE_URL}/api/auth/login", json={
                "email": cls.test_email,
                "password": cls.test_password
            })
            if login_response.status_code == 200:
                cls.user_id = login_response.json().get("user_id")
                print(f"Logged in existing user: {cls.test_email}")
            else:
                cls.user_id = None
                print(f"Auth failed: {login_response.status_code}")
        
        # Verify auth works
        me_response = cls.session.get(f"{BASE_URL}/api/auth/me")
        cls.auth_ok = me_response.status_code == 200
        if cls.auth_ok:
            print("Auth verification passed")
        else:
            print(f"Auth verification failed: {me_response.status_code}")
    
    # ============ PERSONAL USAGE METRICS ============
    
    def test_personal_usage_metrics_endpoint_exists(self):
        """GET /api/reports/me/usage - personal usage metrics should return 200"""
        if not self.auth_ok:
            pytest.skip("Auth not available")
        
        response = self.session.get(f"{BASE_URL}/api/reports/me/usage")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "period_days" in data, "Missing period_days"
        assert "total_tokens" in data, "Missing total_tokens"
        assert "total_cost_usd" in data, "Missing total_cost_usd"
        assert "active_days" in data, "Missing active_days"
        assert "favorite_model" in data, "Missing favorite_model (can be null)"
        assert "by_provider" in data, "Missing by_provider"
        assert "daily_trend" in data, "Missing daily_trend"
        
        print(f"PASS: Personal usage metrics returned - tokens: {data.get('total_tokens', 0)}, cost: {data.get('total_cost_usd', 0)}")
    
    def test_personal_usage_with_days_param(self):
        """GET /api/reports/me/usage?days=7 - test days parameter"""
        if not self.auth_ok:
            pytest.skip("Auth not available")
        
        response = self.session.get(f"{BASE_URL}/api/reports/me/usage?days=7")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("period_days") == 7, f"Expected period_days=7, got {data.get('period_days')}"
        print("PASS: Personal usage with days=7 parameter works")
    
    # ============ EXPORT ENDPOINTS ============
    
    def test_export_csv_format(self):
        """GET /api/reports/export?format=csv - CSV export returns text/csv"""
        if not self.auth_ok:
            pytest.skip("Auth not available")
        
        response = self.session.get(f"{BASE_URL}/api/reports/export?format=csv")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        content_type = response.headers.get("Content-Type", "")
        assert "text/csv" in content_type, f"Expected text/csv content type, got: {content_type}"
        
        # Should have Content-Disposition header for download
        content_disp = response.headers.get("Content-Disposition", "")
        assert "attachment" in content_disp, f"Expected attachment disposition, got: {content_disp}"
        
        print(f"PASS: CSV export returned with Content-Type: {content_type}")
    
    def test_export_json_format(self):
        """GET /api/reports/export?format=json - JSON export returns events array"""
        if not self.auth_ok:
            pytest.skip("Auth not available")
        
        response = self.session.get(f"{BASE_URL}/api/reports/export?format=json")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "events" in data, "Missing events array in JSON export"
        assert isinstance(data["events"], list), "events should be a list"
        assert "total" in data, "Missing total count in JSON export"
        assert data.get("format") == "json", f"Expected format=json, got {data.get('format')}"
        
        print(f"PASS: JSON export returned with {len(data.get('events', []))} events, total: {data.get('total')}")
    
    def test_export_pdf_format(self):
        """GET /api/reports/export?format=pdf - PDF export returns application/pdf"""
        if not self.auth_ok:
            pytest.skip("Auth not available")
        
        response = self.session.get(f"{BASE_URL}/api/reports/export?format=pdf")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        content_type = response.headers.get("Content-Type", "")
        assert "application/pdf" in content_type, f"Expected application/pdf content type, got: {content_type}"
        
        # PDF should have some content
        assert len(response.content) > 0, "PDF content should not be empty"
        
        # Should have Content-Disposition header for download
        content_disp = response.headers.get("Content-Disposition", "")
        assert "attachment" in content_disp, f"Expected attachment disposition, got: {content_disp}"
        
        print(f"PASS: PDF export returned with Content-Type: {content_type}, size: {len(response.content)} bytes")
    
    # ============ PLATFORM-LEVEL (SUPER ADMIN ONLY) ============
    
    def test_platform_health_returns_403_for_non_admin(self):
        """GET /api/reports/platform/health - returns 403 for non-super-admin"""
        if not self.auth_ok:
            pytest.skip("Auth not available")
        
        response = self.session.get(f"{BASE_URL}/api/reports/platform/health")
        
        assert response.status_code == 403, f"Expected 403 for non-admin, got {response.status_code}: {response.text}"
        print("PASS: Platform health returns 403 for non-super-admin user")
    
    def test_platform_business_returns_403_for_non_admin(self):
        """GET /api/reports/platform/business - returns 403 for non-super-admin"""
        if not self.auth_ok:
            pytest.skip("Auth not available")
        
        response = self.session.get(f"{BASE_URL}/api/reports/platform/business")
        
        assert response.status_code == 403, f"Expected 403 for non-admin, got {response.status_code}: {response.text}"
        print("PASS: Platform business returns 403 for non-super-admin user")
    
    def test_alerts_returns_403_for_non_admin(self):
        """GET /api/reports/alerts - returns 403 for non-super-admin"""
        if not self.auth_ok:
            pytest.skip("Auth not available")
        
        response = self.session.get(f"{BASE_URL}/api/reports/alerts")
        
        assert response.status_code == 403, f"Expected 403 for non-admin, got {response.status_code}: {response.text}"
        print("PASS: Alerts endpoint returns 403 for non-super-admin user")
    
    # ============ ORG-LEVEL (ORG ADMIN ONLY) ============
    
    def test_org_usage_returns_403_for_non_org_admin(self):
        """GET /api/reports/org/{org_id}/usage - returns 403 for non-org-admin"""
        if not self.auth_ok:
            pytest.skip("Auth not available")
        
        fake_org_id = f"org_{uuid.uuid4().hex[:12]}"
        response = self.session.get(f"{BASE_URL}/api/reports/org/{fake_org_id}/usage")
        
        assert response.status_code == 403, f"Expected 403 for non-org-admin, got {response.status_code}: {response.text}"
        print("PASS: Org usage returns 403 for non-org-admin user")
    
    def test_org_users_returns_403_for_non_org_admin(self):
        """GET /api/reports/org/{org_id}/users - returns 403 for non-org-admin"""
        if not self.auth_ok:
            pytest.skip("Auth not available")
        
        fake_org_id = f"org_{uuid.uuid4().hex[:12]}"
        response = self.session.get(f"{BASE_URL}/api/reports/org/{fake_org_id}/users")
        
        assert response.status_code == 403, f"Expected 403 for non-org-admin, got {response.status_code}: {response.text}"
        print("PASS: Org users returns 403 for non-org-admin user")
    
    # ============ BUDGET GOVERNANCE ============
    
    def test_set_and_get_org_budget(self):
        """PUT/GET /api/reports/org/{org_id}/budget - set and retrieve budget"""
        if not self.auth_ok:
            pytest.skip("Auth not available")
        
        org_id = f"TEST_org_{uuid.uuid4().hex[:12]}"
        
        # Set budget
        budget_data = {
            "monthly_token_limit": 1000000,
            "monthly_cost_limit_usd": 100.00,
            "per_user_daily_limit": 50000
        }
        put_response = self.session.put(f"{BASE_URL}/api/reports/org/{org_id}/budget", json=budget_data)
        
        assert put_response.status_code == 200, f"Expected 200 on budget set, got {put_response.status_code}: {put_response.text}"
        put_data = put_response.json()
        assert put_data.get("status") == "budget_set", f"Expected status=budget_set, got {put_data}"
        print(f"PASS: Budget set for org {org_id}")
        
        # Get budget
        get_response = self.session.get(f"{BASE_URL}/api/reports/org/{org_id}/budget")
        assert get_response.status_code == 200, f"Expected 200 on budget get, got {get_response.status_code}: {get_response.text}"
        
        get_data = get_response.json()
        assert get_data.get("org_id") == org_id, f"Expected org_id={org_id}, got {get_data.get('org_id')}"
        assert get_data.get("monthly_token_limit") == 1000000, f"Expected monthly_token_limit=1000000, got {get_data.get('monthly_token_limit')}"
        assert get_data.get("monthly_cost_limit_usd") == 100.00, f"Expected monthly_cost_limit_usd=100.00, got {get_data.get('monthly_cost_limit_usd')}"
        assert get_data.get("per_user_daily_limit") == 50000, f"Expected per_user_daily_limit=50000, got {get_data.get('per_user_daily_limit')}"
        
        print(f"PASS: Budget retrieved successfully - token limit: {get_data.get('monthly_token_limit')}, cost limit: ${get_data.get('monthly_cost_limit_usd')}")
    
    def test_get_budget_for_nonexistent_org(self):
        """GET /api/reports/org/{org_id}/budget - returns default for nonexistent org"""
        if not self.auth_ok:
            pytest.skip("Auth not available")
        
        nonexistent_org = f"org_nonexistent_{uuid.uuid4().hex[:8]}"
        
        response = self.session.get(f"{BASE_URL}/api/reports/org/{nonexistent_org}/budget")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # For nonexistent org, should return default with null limits
        assert data.get("org_id") == nonexistent_org
        assert data.get("monthly_token_limit") is None, "Expected null monthly_token_limit for new org"
        assert data.get("monthly_cost_limit_usd") is None, "Expected null monthly_cost_limit_usd for new org"
        
        print("PASS: Budget for nonexistent org returns default null values")
    
    # ============ UNAUTHENTICATED ACCESS ============
    
    def test_unauthenticated_personal_usage(self):
        """GET /api/reports/me/usage without auth returns 401"""
        session = requests.Session()
        response = session.get(f"{BASE_URL}/api/reports/me/usage")
        
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("PASS: Personal usage returns 401 without authentication")
    
    def test_unauthenticated_export(self):
        """GET /api/reports/export without auth returns 401"""
        session = requests.Session()
        response = session.get(f"{BASE_URL}/api/reports/export?format=json")
        
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("PASS: Export returns 401 without authentication")


class TestReportingEndpointRouting:
    """Test that all reporting endpoints are properly registered"""
    
    @classmethod
    def setup_class(cls):
        """Get authenticated session"""
        cls.session = requests.Session()
        cls.session.headers.update({"Content-Type": "application/json"})
        
        unique_id = uuid.uuid4().hex[:8]
        email = f"TEST_routing_{unique_id}@test.com"
        password = "SecurePass123!"
        
        reg_response = cls.session.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": password,
            "name": f"Routing Test {unique_id}"
        })
        
        if reg_response.status_code in [200, 201]:
            print(f"Registered routing test user")
        else:
            # Try login
            login_response = cls.session.post(f"{BASE_URL}/api/auth/login", json={
                "email": email,
                "password": password
            })
            if login_response.status_code == 200:
                print(f"Logged in routing test user")
        
        # Verify auth
        me_resp = cls.session.get(f"{BASE_URL}/api/auth/me")
        cls.auth_ok = me_resp.status_code == 200
        if cls.auth_ok:
            print(f"Auth verified for routing tests")
        else:
            print(f"Auth verification failed: {me_resp.status_code}")
    
    def test_all_reporting_routes_registered(self):
        """Verify all reporting routes return proper status codes (not 404)"""
        if not self.auth_ok:
            pytest.skip("Auth not available")
        
        routes_to_test = [
            ("GET", "/api/reports/me/usage", 200),
            ("GET", "/api/reports/export?format=json", 200),
            ("GET", "/api/reports/export?format=csv", 200),
            ("GET", "/api/reports/export?format=pdf", 200),
            ("GET", "/api/reports/platform/health", 403),  # 403 for non-admin
            ("GET", "/api/reports/platform/business", 403),  # 403 for non-admin
            ("GET", "/api/reports/alerts", 403),  # 403 for non-admin
            ("GET", "/api/reports/org/test_org/usage", 403),  # 403 for non-org-admin
            ("GET", "/api/reports/org/test_org/users", 403),  # 403 for non-org-admin
            ("PUT", "/api/reports/org/test_org/budget", 200),
            ("GET", "/api/reports/org/test_org/budget", 200),
        ]
        
        results = []
        for method, path, expected_status in routes_to_test:
            url = f"{BASE_URL}{path}"
            if method == "GET":
                response = self.session.get(url)
            elif method == "PUT":
                response = self.session.put(url, json={"monthly_token_limit": 100000})
            else:
                response = self.session.request(method, url)
            
            # Main check: route should NOT return 404 (not found)
            is_registered = response.status_code != 404
            meets_expectation = response.status_code == expected_status
            
            result = {
                "path": path,
                "method": method,
                "expected": expected_status,
                "actual": response.status_code,
                "registered": is_registered,
                "pass": meets_expectation
            }
            results.append(result)
            
            if not is_registered:
                print(f"FAIL: {method} {path} returned 404 - route not registered!")
            elif meets_expectation:
                print(f"PASS: {method} {path} returned {response.status_code} as expected")
            else:
                print(f"INFO: {method} {path} returned {response.status_code} (expected {expected_status})")
        
        # All routes should be registered (not 404)
        unregistered = [r for r in results if not r["registered"]]
        assert len(unregistered) == 0, f"Routes not registered: {unregistered}"
        
        # Check expected status codes
        failed = [r for r in results if not r["pass"]]
        assert len(failed) == 0, f"Routes with unexpected status: {failed}"
        
        print(f"\nSUMMARY: All {len(results)} reporting routes verified")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
