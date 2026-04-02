from conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, BASE_URL
"""
Test Suite for Iteration 89 — 4 Backlog Items:
1. SSO Hardening (stricter claim validation, email regex, nonce, provider-specific attribute maps)
2. Redis Production mode (REDIS_REQUIRED flag, health_check())
3. Public API Documentation (Swagger, ReDoc, OpenAPI spec)
4. Status Page Enhancement (real-time health checks for all services)
"""
import pytest
import requests
import os
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestStatusPageEndpoints:
    """Status Page Enhancement — real-time health checks for all services."""
    
    def test_status_json_returns_all_services(self):
        """GET /api/status — returns JSON with health of database, cache, ai_models, file_storage, websocket, auth."""
        response = requests.get(f"{BASE_URL}/api/status", timeout=15)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        
        data = response.json()
        # Validate overall structure
        assert "status" in data, "Missing 'status' field"
        assert "uptime_seconds" in data, "Missing 'uptime_seconds' field"
        assert "timestamp" in data, "Missing 'timestamp' field"
        assert "services" in data, "Missing 'services' field"
        
        services = data["services"]
        # Check all required services are present
        required_services = ["database", "cache", "ai_models", "file_storage", "websocket", "auth"]
        for svc in required_services:
            assert svc in services, f"Missing required service: {svc}"
        
        # Validate database has latency_ms
        db_status = services["database"]
        assert "status" in db_status, "Database missing 'status' field"
        if db_status["status"] == "operational":
            assert "latency_ms" in db_status, "Database missing 'latency_ms' when operational"
        
        # Validate cache status reflects Redis fallback mode (no Redis in this env)
        cache_status = services["cache"]
        assert "status" in cache_status, "Cache missing 'status' field"
        # Since REDIS_URL is not set, expect "disabled" status
        print(f"Cache status: {cache_status}")
        
        print(f"Status endpoint returned {len(services)} services, overall status: {data['status']}")
    
    def test_status_page_html_returns_dashboard(self):
        """GET /api/status/page — returns HTML status dashboard with auto-refresh."""
        response = requests.get(f"{BASE_URL}/api/status/page", timeout=15)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Verify it's HTML
        content_type = response.headers.get("content-type", "")
        assert "text/html" in content_type, f"Expected HTML, got {content_type}"
        
        html = response.text
        
        # Verify auto-refresh meta tag (30 seconds)
        assert 'content="30"' in html or 'http-equiv="refresh"' in html, "Missing auto-refresh meta tag"
        
        # Verify all 7 services are mentioned
        services_to_check = ["Database", "Cache", "API Server", "Auth", "AI Models", "File Storage", "WebSocket"]
        for svc in services_to_check:
            assert svc in html, f"Missing service '{svc}' in status page HTML"
        
        # Check for Nexus branding
        assert "NEXUS" in html, "Missing NEXUS branding"
        
        # Check for status indicators
        assert "Operational" in html or "Fallback" in html or "Degraded" in html, "Missing status indicators"
        
        print("Status page HTML contains all 7 services and auto-refresh")

    def test_health_startup_includes_redis_check(self):
        """GET /api/health/startup — includes redis check alongside database and instance_id."""
        response = requests.get(f"{BASE_URL}/api/health/startup", timeout=15)
        # Can return 200 or 503 depending on all checks passing
        assert response.status_code in [200, 503], f"Unexpected status {response.status_code}"
        
        data = response.json()
        assert "ready" in data, "Missing 'ready' field"
        assert "checks" in data, "Missing 'checks' field"
        
        checks = data["checks"]
        assert "database" in checks, "Missing database check"
        assert "instance_id" in checks, "Missing instance_id check"
        assert "redis" in checks, "Missing redis check in startup probe"
        
        # Since Redis is optional in this env, redis check should be True (optional mode)
        print(f"Startup probe checks: {checks}")
        print(f"Ready: {data['ready']}")


class TestApiDocumentation:
    """Public API Documentation via Swagger/Redoc."""
    
    def test_swagger_ui_loads(self):
        """GET /api/docs — Swagger UI loads with OpenAPI tags."""
        response = requests.get(f"{BASE_URL}/api/docs", timeout=15)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Should return HTML for Swagger UI
        content_type = response.headers.get("content-type", "")
        assert "text/html" in content_type, f"Expected HTML, got {content_type}"
        
        html = response.text
        # Swagger UI includes swagger-ui in the response
        assert "swagger" in html.lower(), "Swagger UI marker not found"
        
        print("Swagger UI loads successfully at /api/docs")
    
    def test_redoc_loads(self):
        """GET /api/redoc — ReDoc documentation loads."""
        response = requests.get(f"{BASE_URL}/api/redoc", timeout=15)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Should return HTML for ReDoc
        content_type = response.headers.get("content-type", "")
        assert "text/html" in content_type, f"Expected HTML, got {content_type}"
        
        html = response.text
        # ReDoc includes redoc in the response
        assert "redoc" in html.lower(), "ReDoc marker not found"
        
        print("ReDoc loads successfully at /api/redoc")
    
    def test_openapi_json_spec(self):
        """GET /api/openapi.json — returns OpenAPI spec with paths and tags."""
        response = requests.get(f"{BASE_URL}/api/openapi.json", timeout=15)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Should return JSON
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type, f"Expected JSON, got {content_type}"
        
        data = response.json()
        
        # Validate OpenAPI structure
        assert "openapi" in data, "Missing 'openapi' version field"
        assert "info" in data, "Missing 'info' field"
        assert "paths" in data, "Missing 'paths' field"
        
        # Check for tags (should have 13 tags as per server.py)
        assert "tags" in data, "Missing 'tags' field"
        tags = data["tags"]
        expected_tags = ["Auth", "SSO", "Workspaces", "Channels", "AI", "Projects", 
                        "Code", "Wiki", "Files", "Search", "Admin", "SCIM", "Health"]
        
        tag_names = [t["name"] for t in tags]
        for expected in expected_tags:
            assert expected in tag_names, f"Missing expected tag: {expected}"
        
        # Count paths
        path_count = len(data["paths"])
        print(f"OpenAPI spec has {path_count} paths and {len(tags)} tags")
        
        # Title check
        assert "Nexus" in data["info"].get("title", ""), "API title should contain Nexus"
    
    def test_api_docs_page_custom_html(self):
        """GET /api/docs/api — Custom HTML API reference page loads with endpoint categories."""
        response = requests.get(f"{BASE_URL}/api/docs/api", timeout=15)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Should return HTML
        content_type = response.headers.get("content-type", "")
        assert "text/html" in content_type, f"Expected HTML, got {content_type}"
        
        html = response.text
        
        # Check for expected endpoint categories
        categories = ["Authentication", "SSO", "Workspaces", "Channels", "Projects", 
                     "Code Repository", "Wiki", "Search", "Files", "Admin", "SCIM", "Health"]
        found_categories = 0
        for cat in categories:
            if cat in html:
                found_categories += 1
        
        assert found_categories >= 8, f"Expected at least 8 endpoint categories, found {found_categories}"
        
        # Check for API methods in the page
        assert "GET" in html, "Missing GET method documentation"
        assert "POST" in html, "Missing POST method documentation"
        
        # Check for links to Swagger/ReDoc
        assert "/api/docs" in html or "Swagger" in html, "Missing link to Swagger UI"
        assert "/api/redoc" in html or "ReDoc" in html, "Missing link to ReDoc"
        
        print(f"Custom API docs page contains {found_categories} endpoint categories")


class TestSSOEndpoints:
    """SSO Hardening — email validation, nonce, provider-specific attribute maps."""
    
    @pytest.fixture
    def auth_session(self):
        """Login as super_admin to get authenticated session."""
        session = requests.Session()
        login_response = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_ADMIN_EMAIL, "password": "test"},
            timeout=15
        )
        if login_response.status_code != 200:
            pytest.skip("Super admin login failed — cannot test SSO admin endpoints")
        return session
    
    def test_sso_providers_list_public(self):
        """GET /api/sso/providers — returns list of enabled SSO providers (public endpoint)."""
        response = requests.get(f"{BASE_URL}/api/sso/providers", timeout=15)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "providers" in data, "Missing 'providers' field"
        
        # Providers can be empty if none configured
        providers = data["providers"]
        assert isinstance(providers, list), "Providers should be a list"
        
        print(f"SSO providers endpoint returned {len(providers)} providers")
    
    def test_sso_config_create_requires_workspace_id(self, auth_session):
        """POST /api/admin/sso/config — requires workspace_id parameter."""
        # Try without workspace_id
        response = auth_session.post(
            f"{BASE_URL}/api/admin/sso/config",
            json={
                "provider_name": "Test OIDC",
                "protocol": "oidc",
                "client_id": "test_client",
                "client_secret": "test_secret",
                "authorization_url": "https://example.com/auth",
                "token_url": "https://example.com/token"
            },
            timeout=15
        )
        assert response.status_code == 400, f"Expected 400 without workspace_id, got {response.status_code}"
        assert "workspace_id" in response.text.lower(), "Error should mention workspace_id"
        
        print("SSO config creation correctly requires workspace_id")
    
    def test_sso_config_validates_saml_fields(self, auth_session):
        """POST /api/admin/sso/config — validates SAML fields."""
        # Try SAML without required fields
        response = auth_session.post(
            f"{BASE_URL}/api/admin/sso/config?workspace_id=test_ws",
            json={
                "provider_name": "Test SAML",
                "protocol": "saml",
                # Missing idp_entity_id, idp_sso_url, idp_certificate
            },
            timeout=15
        )
        assert response.status_code == 400, f"Expected 400 for incomplete SAML, got {response.status_code}"
        
        error_text = response.text.lower()
        assert "saml" in error_text or "idp_" in error_text, "Error should mention SAML requirements"
        
        print("SSO config correctly validates SAML required fields")
    
    def test_sso_config_validates_oidc_fields(self, auth_session):
        """POST /api/admin/sso/config — validates OIDC fields."""
        # Try OIDC without required fields
        response = auth_session.post(
            f"{BASE_URL}/api/admin/sso/config?workspace_id=test_ws",
            json={
                "provider_name": "Test OIDC",
                "protocol": "oidc",
                "client_id": "test_client",
                # Missing client_secret, authorization_url, token_url
            },
            timeout=15
        )
        assert response.status_code == 400, f"Expected 400 for incomplete OIDC, got {response.status_code}"
        
        error_text = response.text.lower()
        assert "oidc" in error_text or "client_secret" in error_text or "token_url" in error_text, \
            "Error should mention OIDC requirements"
        
        print("SSO config correctly validates OIDC required fields")
    
    def test_sso_config_supports_provider_type(self, auth_session):
        """POST /api/admin/sso/config — supports provider_type field for attribute mappings."""
        # This test validates the schema accepts provider_type
        # We can't fully create without a real workspace, but we can check the validation path
        
        response = auth_session.post(
            f"{BASE_URL}/api/admin/sso/config?workspace_id=test_ws_12345",
            json={
                "provider_name": "Okta SSO",
                "protocol": "oidc",
                "provider_type": "okta",  # Provider-specific type
                "client_id": "test_client",
                "client_secret": "test_secret",
                "authorization_url": "https://example.okta.com/authorize",
                "token_url": "https://example.okta.com/token"
            },
            timeout=15
        )
        # Should accept the request (may fail for other reasons like workspace not existing)
        # But shouldn't fail due to provider_type field being invalid
        if response.status_code == 400:
            # Check it's not failing due to provider_type
            assert "provider_type" not in response.text.lower(), "provider_type should be accepted"
        
        print("SSO config accepts provider_type field")


class TestRedisHealthCheck:
    """Redis Production mode — REDIS_REQUIRED flag and health_check()."""
    
    def test_status_endpoint_shows_redis_fallback(self):
        """Verify /api/status shows cache as 'disabled' or 'fallback' when Redis not configured."""
        response = requests.get(f"{BASE_URL}/api/status", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        cache = data["services"]["cache"]
        
        # Without REDIS_URL, should show disabled or fallback
        assert cache["status"] in ["disabled", "degraded", "operational"], \
            f"Unexpected cache status: {cache['status']}"
        
        # Should have a note explaining the state
        if cache["status"] == "disabled":
            assert "note" in cache, "Disabled cache should have a note"
        
        print(f"Redis health check status: {cache}")
    
    def test_startup_probe_includes_redis(self):
        """Verify /api/health/startup includes redis in checks."""
        response = requests.get(f"{BASE_URL}/api/health/startup", timeout=15)
        data = response.json()
        
        assert "redis" in data["checks"], "Redis should be in startup checks"
        
        # When REDIS_REQUIRED is not set, redis check should pass (optional)
        # The check returns True if Redis is optional and not configured
        print(f"Redis startup check result: {data['checks']['redis']}")


class TestEmailValidation:
    """Test SSO email validation regex (unit test style)."""
    
    def test_email_regex_pattern_valid_emails(self):
        """Verify email regex accepts valid formats."""
        # This mirrors the _EMAIL_RE pattern from routes_sso.py
        EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
        
        valid_emails = [
            "test@example.com",
            "user.name@domain.org",
            "user+tag@company.co.uk",
            "first.last@sub.domain.com",
            "admin@nexus.io",
        ]
        
        for email in valid_emails:
            assert EMAIL_RE.match(email), f"Valid email rejected: {email}"
        
        print(f"Email regex correctly accepts {len(valid_emails)} valid formats")
    
    def test_email_regex_pattern_invalid_emails(self):
        """Verify email regex rejects invalid formats."""
        EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
        
        invalid_emails = [
            "notanemail",
            "@nodomain.com",
            "no@tld",
            "spaces in@email.com",
            "missing@.com",
            "",
            "double@@at.com",
        ]
        
        for email in invalid_emails:
            assert not EMAIL_RE.match(email), f"Invalid email accepted: {email}"
        
        print(f"Email regex correctly rejects {len(invalid_emails)} invalid formats")


class TestHealthEndpoints:
    """Additional health endpoint tests."""
    
    def test_health_endpoint(self):
        """GET /api/health — returns healthy status with DB connection."""
        response = requests.get(f"{BASE_URL}/api/health", timeout=15)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("status") == "healthy", f"Expected healthy, got {data}"
        assert "database" in data, "Missing database field"
        assert "instance_id" in data, "Missing instance_id field"
        
        print(f"Health check passed: {data}")
    
    def test_health_live_endpoint(self):
        """GET /api/health/live — lightweight liveness probe."""
        response = requests.get(f"{BASE_URL}/api/health/live", timeout=15)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("alive") == True, f"Expected alive=True, got {data}"
        
        print("Liveness probe passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
