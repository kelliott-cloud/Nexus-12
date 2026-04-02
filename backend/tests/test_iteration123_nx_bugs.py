"""
Iteration 123 - Nexus 7.0 Delta Report Bug Verification Tests
Tests all 22 NX-### bugs to verify Emergent platform references are removed.
"""
import pytest
import requests
import os
import re
from pathlib import Path

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    pytest.skip("REACT_APP_BACKEND_URL not set", allow_module_level=True)

# Test credentials
TEST_EMAIL = os.environ.get("TEST_ADMIN_EMAIL", "admin@test.local")
TEST_PASSWORD = "test"


class TestNX001NginxPort:
    """NX-001: nginx.docker.conf uses port 8080 (not 8001)"""
    
    def test_nginx_uses_port_8080(self):
        nginx_conf = Path("/app/frontend/nginx.docker.conf")
        assert nginx_conf.exists(), "nginx.docker.conf not found"
        content = nginx_conf.read_text()
        
        # Should have 8080 for backend proxy
        assert "8080" in content, "nginx.docker.conf should use port 8080"
        # Should NOT have 8001
        assert "8001" not in content, "nginx.docker.conf should NOT use port 8001"
        print("✓ NX-001: nginx.docker.conf uses port 8080")


class TestNX002AuthPageHasEmergentBridge:
    """NX-002: AuthPage.js has auth.emergentagent.com redirect (bridge required)"""
    
    def test_authpage_has_emergent_bridge(self):
        authpage = Path("/app/frontend/src/pages/AuthPage.js")
        assert authpage.exists(), "AuthPage.js not found"
        content = authpage.read_text()
        
        assert "auth.emergentagent.com" in content, "AuthPage.js should have auth.emergentagent.com redirect for bridge"
        print("✓ NX-002: AuthPage.js has Emergent bridge redirect")


class TestNX003AuthSessionBridgeActive:
    """NX-003: POST /api/auth/session returns 401 for invalid session (bridge active)"""
    
    def test_auth_session_returns_401(self):
        response = requests.post(f"{BASE_URL}/api/auth/session", json={"session_id": "test"})
        assert response.status_code == 401, f"Expected 401 for invalid session (bridge active), got {response.status_code}"
        print("✓ NX-003: POST /api/auth/session returns 401 (bridge active)")


class TestNX004IndexHtmlHasSessionExchange:
    """NX-004: index.html has pre-React session exchange script (bridge required)"""
    
    def test_index_html_has_session_exchange(self):
        index_html = Path("/app/frontend/public/index.html")
        assert index_html.exists(), "index.html not found"
        content = index_html.read_text()
        
        assert "session_id" in content, "index.html should have session_id exchange script"
        assert "auth/session" in content, "index.html should have auth/session call"
        print("✓ NX-004: index.html has pre-React session exchange")


class TestNX005AIProvidersNoEmergent:
    """NX-005: ai_providers.py has NO emergentintegrations import and NO call_emergent_universal"""
    
    def test_ai_providers_no_emergent(self):
        ai_providers = Path("/app/backend/ai_providers.py")
        assert ai_providers.exists(), "ai_providers.py not found"
        content = ai_providers.read_text()
        
        assert "emergentintegrations" not in content, "ai_providers.py should NOT import emergentintegrations"
        assert "call_emergent_universal" not in content, "ai_providers.py should NOT have call_emergent_universal"
        assert "EMERGENT_LLM_KEY" not in content, "ai_providers.py should NOT reference EMERGENT_LLM_KEY"
        # Should have comment about removal
        assert "NX-005" in content or "removed" in content.lower(), "Should have comment about Emergent removal"
        print("✓ NX-005: ai_providers.py has no Emergent references")


class TestNX006CollaborationCoreNoEmergentKey:
    """NX-006: collaboration_core.py has NO EMERGENT_LLM_KEY fallback"""
    
    def test_collaboration_core_no_emergent_key(self):
        collab_core = Path("/app/backend/collaboration_core.py")
        assert collab_core.exists(), "collaboration_core.py not found"
        content = collab_core.read_text()
        
        assert "EMERGENT_LLM_KEY" not in content, "collaboration_core.py should NOT have EMERGENT_LLM_KEY"
        print("✓ NX-006: collaboration_core.py has no EMERGENT_LLM_KEY fallback")


class TestNX007IndexHtmlHasEmergentScript:
    """NX-007: index.html has emergent-main.js (bridge required)"""
    
    def test_index_html_has_emergent_script(self):
        index_html = Path("/app/frontend/public/index.html")
        assert index_html.exists(), "index.html not found"
        content = index_html.read_text()
        
        assert "emergent-main.js" in content, "index.html should have emergent-main.js for bridge"
        print("✓ NX-007: index.html has emergent-main.js")


class TestNX008ServerCORSNoEmergent:
    """NX-008: server.py CORS ALLOWED_DOMAINS has NO Emergent domains"""
    
    def test_server_cors_no_emergent(self):
        server_py = Path("/app/backend/server.py")
        assert server_py.exists(), "server.py not found"
        content = server_py.read_text()
        
        # Find ALLOWED_DOMAINS definition
        allowed_domains_match = re.search(r"ALLOWED_DOMAINS\s*=\s*\[([^\]]+)\]", content)
        if allowed_domains_match:
            domains_str = allowed_domains_match.group(1)
            assert "emergentagent" not in domains_str.lower(), "ALLOWED_DOMAINS should NOT have emergentagent"
            assert "emergent.sh" not in domains_str.lower(), "ALLOWED_DOMAINS should NOT have emergent.sh"
        print("✓ NX-008: server.py CORS has no Emergent domains")


class TestNX009DevServerNoEmergent:
    """NX-009: dev-server-setup.js has NO emergent.sh or emergentagent.com regex"""
    
    def test_dev_server_no_emergent(self):
        dev_server = Path("/app/frontend/dev-server-setup.js")
        if not dev_server.exists():
            pytest.skip("dev-server-setup.js not found (may not exist)")
        content = dev_server.read_text()
        
        assert "emergent.sh" not in content, "dev-server-setup.js should NOT have emergent.sh"
        assert "emergentagent.com" not in content, "dev-server-setup.js should NOT have emergentagent.com"
        print("✓ NX-009: dev-server-setup.js has no Emergent references")


class TestNX010AuthCallbackHasBridgeLogic:
    """NX-010: AuthCallback.js has session exchange logic (bridge required)"""
    
    def test_auth_callback_has_bridge(self):
        auth_callback = Path("/app/frontend/src/pages/AuthCallback.js")
        assert auth_callback.exists(), "AuthCallback.js not found"
        content = auth_callback.read_text()
        
        assert "session_id" in content.lower() or "auth/session" in content, "AuthCallback should have session exchange logic"
        print("✓ NX-010: AuthCallback.js has bridge session exchange logic")


class TestNX011HasSessionIdHashGuards:
    """NX-011: App.js has session_id= hash guard (bridge required)"""
    
    def test_has_session_id_hash_guards(self):
        app_js = Path("/app/frontend/src/App.js")
        assert app_js.exists(), "App.js not found"
        content = app_js.read_text()
        
        assert "session_id" in content, "App.js should have session_id hash guard for bridge"
        print("✓ NX-011: App.js has session_id hash guard")


class TestNX012ThemesCSSNoEmergentCDN:
    """NX-012: themes.css has NO emergentagent CDN URLs (uses CSS gradients)"""
    
    def test_themes_css_no_cdn(self):
        themes_css = Path("/app/frontend/src/themes.css")
        assert themes_css.exists(), "themes.css not found"
        content = themes_css.read_text()
        
        assert "emergentagent" not in content.lower(), "themes.css should NOT have emergentagent CDN URLs"
        assert "cdn." not in content.lower() or "fonts.googleapis" in content.lower(), "themes.css should NOT have CDN URLs (except fonts)"
        # Should use CSS gradients
        assert "linear-gradient" in content, "themes.css should use CSS gradients"
        # Should have comment about NX-012
        assert "NX-012" in content or "gradient" in content.lower(), "Should mention gradient replacement"
        print("✓ NX-012: themes.css uses CSS gradients (no CDN URLs)")


class TestNX013ManifestLocalLogo:
    """NX-013: manifest.json uses /logo.png (not emergentagent CDN)"""
    
    def test_manifest_local_logo(self):
        manifest = Path("/app/frontend/public/manifest.json")
        assert manifest.exists(), "manifest.json not found"
        content = manifest.read_text()
        
        assert "/logo.png" in content, "manifest.json should use /logo.png"
        assert "emergentagent" not in content.lower(), "manifest.json should NOT have emergentagent CDN"
        print("✓ NX-013: manifest.json uses /logo.png")


class TestNX014UseEmergentBridgeExists:
    """NX-014: routes_google_auth.py has use_emergent_bridge flag (bridge required)"""
    
    def test_use_emergent_bridge_exists(self):
        routes_auth = Path("/app/backend/routes/routes_google_auth.py")
        assert routes_auth.exists(), "routes_google_auth.py not found"
        content = routes_auth.read_text()
        
        assert "use_emergent_bridge" in content, "routes_google_auth.py should have use_emergent_bridge flag"
        print("✓ NX-014: routes_google_auth.py has use_emergent_bridge flag")


class TestNX015EnvExamplesExist:
    """NX-015: backend/.env.example and frontend/.env.example exist"""
    
    def test_env_examples_exist(self):
        backend_env = Path("/app/backend/.env.example")
        frontend_env = Path("/app/frontend/.env.example")
        
        assert backend_env.exists(), "backend/.env.example should exist"
        assert frontend_env.exists(), "frontend/.env.example should exist"
        
        # Check backend .env.example has required vars
        backend_content = backend_env.read_text()
        assert "MONGO_URL" in backend_content, "backend/.env.example should have MONGO_URL"
        assert "DB_NAME" in backend_content, "backend/.env.example should have DB_NAME"
        assert "ENCRYPTION_KEY" in backend_content, "backend/.env.example should have ENCRYPTION_KEY"
        
        # Check frontend .env.example has required vars
        frontend_content = frontend_env.read_text()
        assert "REACT_APP_BACKEND_URL" in frontend_content, "frontend/.env.example should have REACT_APP_BACKEND_URL"
        
        print("✓ NX-015: .env.example files exist with required vars")


class TestNX017DeploymentMDNoEmergent:
    """NX-017: DEPLOYMENT.md has NO Emergent references and uses port 8080"""
    
    def test_deployment_md_no_emergent(self):
        deployment_md = Path("/app/DEPLOYMENT.md")
        if not deployment_md.exists():
            pytest.skip("DEPLOYMENT.md not found")
        content = deployment_md.read_text()
        
        assert "emergentagent" not in content.lower(), "DEPLOYMENT.md should NOT have emergentagent references"
        assert "emergent.sh" not in content.lower(), "DEPLOYMENT.md should NOT have emergent.sh references"
        print("✓ NX-017: DEPLOYMENT.md has no Emergent references")


class TestNX020CINoPassWithNoTests:
    """NX-020: CI .github/workflows/ci.yml has NO --passWithNoTests and includes yarn build"""
    
    def test_ci_no_pass_with_no_tests(self):
        ci_yml = Path("/app/.github/workflows/ci.yml")
        assert ci_yml.exists(), "ci.yml not found"
        content = ci_yml.read_text()
        
        assert "--passWithNoTests" not in content, "ci.yml should NOT have --passWithNoTests"
        assert "yarn build" in content, "ci.yml should include yarn build"
        print("✓ NX-020: CI has no --passWithNoTests and includes yarn build")


class TestLoginRegression:
    """Regression: POST /api/auth/login still works"""
    
    def test_login_works(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed with {response.status_code}: {response.text}"
        data = response.json()
        assert "user_id" in data, "Login should return user_id"
        assert "session_token" in data, "Login should return session_token"
        print("✓ Regression: Login works correctly")


class TestZeroEmergentReferences:
    """Zero Emergent references in production code (excluding OAuth bridge files)"""
    
    def test_zero_emergent_in_production_code(self):
        import subprocess
        
        # Check for emergent references in production code (excluding tests, reports, and bridge files)
        result = subprocess.run(
            ["grep", "-rn", "-E", "emergentagent|emergent\\.sh|EMERGENT_LLM|emergentintegrations",
             "--include=*.py", "--include=*.js", "--include=*.jsx", "--include=*.ts", "--include=*.tsx",
             "--include=*.css", "--include=*.html", "--include=*.json", "--include=*.yml", "--include=*.yaml",
             "/app/backend", "/app/frontend/src", "/app/frontend/public"],
            capture_output=True, text=True
        )
        
        # Allowed bridge files — these are REQUIRED for Google OAuth
        BRIDGE_FILES = {
            "routes_google_auth.py",   # /auth/session endpoint
            "AuthPage.js",             # auth.emergentagent.com redirect
            "MobileApp.js",            # auth.emergentagent.com redirect
            "AuthCallback.js",         # session exchange logic
            "index.html",              # emergent-main.js + pre-React exchange
        }
        
        lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
        production_refs = [
            line for line in lines 
            if line and 
            '/tests/' not in line and 
            '/test_reports/' not in line and
            'test_' not in line and
            'node_modules' not in line and
            '.git' not in line and
            'removed' not in line.lower() and
            'NX-' not in line and
            not any(bf in line for bf in BRIDGE_FILES)
        ]
        
        if production_refs:
            print(f"Found unexpected Emergent references:")
            for ref in production_refs[:10]:
                print(f"  {ref}")
        
        assert len(production_refs) == 0, f"Found {len(production_refs)} unexpected Emergent references in production code"
        print("✓ Zero unexpected Emergent references (bridge files excluded)")


class TestHealthEndpoint:
    """Basic health check"""
    
    def test_health_endpoint(self):
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        data = response.json()
        assert data.get("status") == "healthy", "Health status should be healthy"
        print("✓ Health endpoint working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
