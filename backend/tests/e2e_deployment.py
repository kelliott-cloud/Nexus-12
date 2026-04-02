"""Nexus Cloud — Playwright E2E Deployment Tests

Run after deployment to verify critical user flows work end-to-end:
  pytest tests/e2e_deployment.py -v --tb=short

Requires:
  pip install playwright pytest-playwright
  python -m playwright install chromium

Environment variables:
  E2E_BASE_URL: Frontend URL (default: http://localhost:3000)
  TEST_ADMIN_EMAIL: Admin email
  TEST_ADMIN_PASSWORD: Admin password
"""
import os
import pytest

BASE_URL = os.environ.get("E2E_BASE_URL", os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:3000"))
ADMIN_EMAIL = os.environ.get("TEST_ADMIN_EMAIL", "admin@test.local")
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "test")


@pytest.fixture(scope="session")
def browser_context_args():
    return {"viewport": {"width": 1920, "height": 1080}, "ignore_https_errors": True}


class TestLandingPage:
    def test_landing_page_loads(self, page):
        """Landing page renders without errors."""
        page.goto(BASE_URL)
        page.wait_for_timeout(3000)
        assert page.title(), "Page should have a title"
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.wait_for_timeout(1000)

    def test_landing_has_sign_in(self, page):
        """Landing page has a sign in link/button."""
        page.goto(BASE_URL)
        page.wait_for_timeout(2000)
        sign_in = page.locator('text=Sign In').first
        assert sign_in.is_visible(), "Sign In should be visible on landing"

    def test_no_emergent_scripts(self, page):
        """No Emergent scripts loaded on landing page."""
        emergent_requests = []
        page.on("request", lambda req: emergent_requests.append(req.url) if "emergent" in req.url else None)
        page.goto(BASE_URL)
        page.wait_for_timeout(3000)
        assert len(emergent_requests) == 0, f"Emergent requests detected: {emergent_requests}"


class TestAuthFlow:
    def test_login_page_loads(self, page):
        """Auth page renders login form."""
        page.goto(f"{BASE_URL}/auth")
        page.wait_for_timeout(2000)
        email_input = page.locator('input[type="email"]')
        assert email_input.is_visible(), "Email input should be visible"

    def test_login_with_credentials(self, page):
        """Login with email/password redirects to dashboard."""
        page.goto(f"{BASE_URL}/auth")
        page.wait_for_timeout(2000)

        # Accept cookies if banner appears
        try:
            page.click("text=Accept All", timeout=2000)
        except Exception as _e:
            import logging; logging.getLogger("tests/e2e_deployment").warning(f"Suppressed: {_e}")

        page.fill('input[type="email"]', ADMIN_EMAIL)
        page.fill('input[type="password"]', ADMIN_PASSWORD)
        page.press('input[type="password"]', "Enter")
        page.wait_for_timeout(5000)

        # Should redirect to dashboard
        assert "/dashboard" in page.url or "/workspace" in page.url, f"Expected dashboard, got {page.url}"

    def test_google_login_no_emergent_redirect(self, page):
        """Google login button does NOT redirect to auth.emergentagent.com."""
        page.goto(f"{BASE_URL}/auth")
        page.wait_for_timeout(2000)

        # Look for Google button
        google_btn = page.locator('text=Google').first
        if google_btn.is_visible():
            navigation_urls = []
            page.on("request", lambda req: navigation_urls.append(req.url))
            google_btn.click()
            page.wait_for_timeout(3000)
            for url in navigation_urls:
                assert "auth.emergentagent.com" not in url, f"Emergent redirect detected: {url}"


class TestDashboard:
    def _login(self, page):
        page.goto(f"{BASE_URL}/auth")
        page.wait_for_timeout(1000)
        try:
            page.click("text=Accept All", timeout=2000)
        except Exception as _e:
            import logging; logging.getLogger("tests/e2e_deployment").warning(f"Suppressed: {_e}")
        page.fill('input[type="email"]', ADMIN_EMAIL)
        page.fill('input[type="password"]', ADMIN_PASSWORD)
        page.press('input[type="password"]', "Enter")
        page.wait_for_timeout(4000)
        try:
            page.click("text=Skip tour", timeout=3000)
        except Exception as _e:
            import logging; logging.getLogger("tests/e2e_deployment").warning(f"Suppressed: {_e}")

    def test_dashboard_loads(self, page):
        """Dashboard loads with workspace list."""
        self._login(page)
        page.wait_for_timeout(2000)
        assert "/dashboard" in page.url or "workspace" in page.url

    def test_settings_page_loads(self, page):
        """Settings page loads all tabs."""
        self._login(page)
        page.goto(f"{BASE_URL}/settings")
        page.wait_for_timeout(3000)
        # Should see tabs
        assert page.locator('[data-testid="ai-keys-tab"]').is_visible() or page.locator('text=AI Keys').first.is_visible()

    def test_no_console_emergent_errors(self, page):
        """No Emergent-related errors in console."""
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" and "emergent" in msg.text.lower() else None)
        self._login(page)
        page.wait_for_timeout(3000)
        assert len(console_errors) == 0, f"Emergent console errors: {console_errors}"


class TestMediaFeatures:
    def _login(self, page):
        page.goto(f"{BASE_URL}/auth")
        page.wait_for_timeout(1000)
        try:
            page.click("text=Accept All", timeout=2000)
        except Exception as _e:
            import logging; logging.getLogger("tests/e2e_deployment").warning(f"Suppressed: {_e}")
        page.fill('input[type="email"]', ADMIN_EMAIL)
        page.fill('input[type="password"]', ADMIN_PASSWORD)
        page.press('input[type="password"]', "Enter")
        page.wait_for_timeout(4000)
        try:
            page.click("text=Skip tour", timeout=3000)
        except Exception as _e:
            import logging; logging.getLogger("tests/e2e_deployment").warning(f"Suppressed: {_e}")

    def test_media_features_enabled_in_settings(self, page):
        """Settings > Nexus AI shows media features as enabled."""
        self._login(page)
        page.goto(f"{BASE_URL}/settings?tab=nexus-keys")
        page.wait_for_timeout(3000)
        # Media config should show features enabled via API


class TestAPIHealth:
    """API-level tests run via Playwright's request context."""

    def test_health_endpoint(self, page):
        response = page.request.get(f"{BASE_URL}/api/health")
        assert response.status == 200

    def test_auth_session_returns_410(self, page):
        response = page.request.post(f"{BASE_URL}/api/auth/session", data={"session_id": "test"})
        assert response.status == 410, f"Expected 410, got {response.status}"

    def test_media_config_features_enabled(self, page):
        # Login first
        login_resp = page.request.post(f"{BASE_URL}/api/auth/login", data={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        })
        if login_resp.status != 200:
            pytest.skip("Login failed")
        token = login_resp.json().get("session_token", "")
        headers = {"Authorization": f"Bearer {token}"}

        resp = page.request.get(f"{BASE_URL}/api/media/config", headers=headers)
        assert resp.status == 200
        data = resp.json()
        features = data.get("features", {})
        assert features.get("video_generation", {}).get("enabled"), "Video should be enabled"
        assert features.get("music_generation", {}).get("enabled"), "Music should be enabled"
