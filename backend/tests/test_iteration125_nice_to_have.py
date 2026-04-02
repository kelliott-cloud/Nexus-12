"""Iteration 125 - Nice-to-Have Features Tests

Tests for:
1. InlineMediaPlayer.js component exists and exports correctly
2. MessageBubble.js imports InlineMediaPlayer and renders for media_attachment and auto-detected IDs
3. e2e_deployment.py Playwright tests exist with 5 test classes
4. CUTOVER_GOVERNANCE.md exists with backup, restore, rollback, soak window sections
5. Regression: POST /api/auth/login works
6. Regression: GET /api/media/config features all enabled
7. Regression: Smoke test passes 9/9
"""
import os
import pytest
import requests
import subprocess

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "http://localhost:8080"
ADMIN_EMAIL = os.environ.get("TEST_ADMIN_EMAIL", "admin@test.local")
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "test")


@pytest.fixture(scope="module")
def admin_token():
    """Get admin session token."""
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code == 200:
        return r.json().get("session_token", "")
    pytest.skip("Login failed")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    """Headers with admin auth."""
    return {"Authorization": f"Bearer {admin_token}"}


class TestInlineMediaPlayerComponent:
    """Test InlineMediaPlayer.js component exists and exports correctly."""

    def test_inline_media_player_file_exists(self):
        """InlineMediaPlayer.js file exists."""
        path = "/app/frontend/src/components/InlineMediaPlayer.js"
        assert os.path.exists(path), f"InlineMediaPlayer.js not found at {path}"

    def test_inline_media_player_has_named_export(self):
        """InlineMediaPlayer.js has named export."""
        path = "/app/frontend/src/components/InlineMediaPlayer.js"
        with open(path, "r") as f:
            content = f.read()
        assert "export const InlineMediaPlayer" in content, "Missing named export"

    def test_inline_media_player_has_default_export(self):
        """InlineMediaPlayer.js has default export."""
        path = "/app/frontend/src/components/InlineMediaPlayer.js"
        with open(path, "r") as f:
            content = f.read()
        assert "export default InlineMediaPlayer" in content, "Missing default export"

    def test_inline_media_player_has_play_pause_controls(self):
        """InlineMediaPlayer has play/pause button."""
        path = "/app/frontend/src/components/InlineMediaPlayer.js"
        with open(path, "r") as f:
            content = f.read()
        assert "Play" in content and "Pause" in content, "Missing Play/Pause controls"

    def test_inline_media_player_has_progress_bar(self):
        """InlineMediaPlayer has progress bar."""
        path = "/app/frontend/src/components/InlineMediaPlayer.js"
        with open(path, "r") as f:
            content = f.read()
        assert "progress" in content.lower(), "Missing progress bar"

    def test_inline_media_player_has_download_button(self):
        """InlineMediaPlayer has download button."""
        path = "/app/frontend/src/components/InlineMediaPlayer.js"
        with open(path, "r") as f:
            content = f.read()
        assert "Download" in content, "Missing Download button"

    def test_inline_media_player_has_mute_controls(self):
        """InlineMediaPlayer has mute controls."""
        path = "/app/frontend/src/components/InlineMediaPlayer.js"
        with open(path, "r") as f:
            content = f.read()
        assert "Volume2" in content or "VolumeX" in content, "Missing mute controls"

    def test_inline_media_player_supports_video_music_sfx_audio(self):
        """InlineMediaPlayer supports video, music, sfx, audio types."""
        path = "/app/frontend/src/components/InlineMediaPlayer.js"
        with open(path, "r") as f:
            content = f.read()
        assert "video:" in content, "Missing video type"
        assert "music:" in content, "Missing music type"
        assert "sfx:" in content, "Missing sfx type"
        assert "audio:" in content, "Missing audio type"


class TestMessageBubbleIntegration:
    """Test MessageBubble.js imports InlineMediaPlayer and renders correctly."""

    def test_message_bubble_imports_inline_media_player(self):
        """MessageBubble.js imports InlineMediaPlayer."""
        path = "/app/frontend/src/components/MessageBubble.js"
        with open(path, "r") as f:
            content = f.read()
        assert 'import InlineMediaPlayer from "@/components/InlineMediaPlayer"' in content, "Missing import"

    def test_message_bubble_renders_for_media_attachment(self):
        """MessageBubble renders InlineMediaPlayer for media_attachment."""
        path = "/app/frontend/src/components/MessageBubble.js"
        with open(path, "r") as f:
            content = f.read()
        assert "message.media_attachment" in content, "Missing media_attachment check"
        assert "<InlineMediaPlayer" in content, "Missing InlineMediaPlayer render"

    def test_message_bubble_auto_detects_media_ids(self):
        """MessageBubble auto-detects media IDs in content."""
        path = "/app/frontend/src/components/MessageBubble.js"
        with open(path, "r") as f:
            content = f.read()
        assert "vid_" in content, "Missing vid_ detection"
        assert "mus_" in content, "Missing mus_ detection"
        assert "sfx_" in content, "Missing sfx_ detection"
        assert "aud_" in content, "Missing aud_ detection"


class TestE2EDeploymentTests:
    """Test e2e_deployment.py Playwright tests exist with correct classes."""

    def test_e2e_deployment_file_exists(self):
        """e2e_deployment.py file exists."""
        path = "/app/backend/tests/e2e_deployment.py"
        assert os.path.exists(path), f"e2e_deployment.py not found at {path}"

    def test_e2e_has_test_landing_page_class(self):
        """e2e_deployment.py has TestLandingPage class."""
        path = "/app/backend/tests/e2e_deployment.py"
        with open(path, "r") as f:
            content = f.read()
        assert "class TestLandingPage:" in content, "Missing TestLandingPage class"

    def test_e2e_has_test_auth_flow_class(self):
        """e2e_deployment.py has TestAuthFlow class."""
        path = "/app/backend/tests/e2e_deployment.py"
        with open(path, "r") as f:
            content = f.read()
        assert "class TestAuthFlow:" in content, "Missing TestAuthFlow class"

    def test_e2e_has_test_dashboard_class(self):
        """e2e_deployment.py has TestDashboard class."""
        path = "/app/backend/tests/e2e_deployment.py"
        with open(path, "r") as f:
            content = f.read()
        assert "class TestDashboard:" in content, "Missing TestDashboard class"

    def test_e2e_has_test_media_features_class(self):
        """e2e_deployment.py has TestMediaFeatures class."""
        path = "/app/backend/tests/e2e_deployment.py"
        with open(path, "r") as f:
            content = f.read()
        assert "class TestMediaFeatures:" in content, "Missing TestMediaFeatures class"

    def test_e2e_has_test_api_health_class(self):
        """e2e_deployment.py has TestAPIHealth class."""
        path = "/app/backend/tests/e2e_deployment.py"
        with open(path, "r") as f:
            content = f.read()
        assert "class TestAPIHealth:" in content, "Missing TestAPIHealth class"


class TestCutoverGovernanceDocs:
    """Test CUTOVER_GOVERNANCE.md exists with required sections."""

    def test_cutover_governance_file_exists(self):
        """CUTOVER_GOVERNANCE.md file exists."""
        path = "/app/CUTOVER_GOVERNANCE.md"
        assert os.path.exists(path), f"CUTOVER_GOVERNANCE.md not found at {path}"

    def test_cutover_has_backup_section(self):
        """CUTOVER_GOVERNANCE.md has backup section."""
        path = "/app/CUTOVER_GOVERNANCE.md"
        with open(path, "r") as f:
            content = f.read()
        assert "Backup" in content, "Missing Backup section"
        assert "mongodump" in content, "Missing mongodump command"

    def test_cutover_has_restore_section(self):
        """CUTOVER_GOVERNANCE.md has restore section."""
        path = "/app/CUTOVER_GOVERNANCE.md"
        with open(path, "r") as f:
            content = f.read()
        assert "mongorestore" in content, "Missing mongorestore command"

    def test_cutover_has_rollback_section(self):
        """CUTOVER_GOVERNANCE.md has rollback section."""
        path = "/app/CUTOVER_GOVERNANCE.md"
        with open(path, "r") as f:
            content = f.read()
        assert "Rollback" in content, "Missing Rollback section"

    def test_cutover_has_soak_window_section(self):
        """CUTOVER_GOVERNANCE.md has soak window section."""
        path = "/app/CUTOVER_GOVERNANCE.md"
        with open(path, "r") as f:
            content = f.read()
        assert "Soak Window" in content, "Missing Soak Window section"

    def test_cutover_has_7_sections(self):
        """CUTOVER_GOVERNANCE.md has 7 main sections."""
        path = "/app/CUTOVER_GOVERNANCE.md"
        with open(path, "r") as f:
            content = f.read()
        # Count ## N. pattern
        import re
        sections = re.findall(r"^## \d+\.", content, re.MULTILINE)
        assert len(sections) >= 7, f"Expected 7 sections, found {len(sections)}"


class TestRegressionAuth:
    """Regression tests for auth endpoints."""

    def test_auth_login_works(self):
        """POST /api/auth/login works."""
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200, f"Login failed: {r.status_code}"
        data = r.json()
        assert "session_token" in data, "Missing session_token"


class TestRegressionMediaConfig:
    """Regression tests for media config."""

    def test_media_config_features_enabled(self, admin_headers):
        """GET /api/media/config shows all features enabled."""
        r = requests.get(f"{BASE_URL}/api/media/config", headers=admin_headers)
        assert r.status_code == 200, f"Media config failed: {r.status_code}"
        data = r.json()
        features = data.get("features", {})
        assert features.get("video_generation", {}).get("enabled"), "Video not enabled"
        assert features.get("music_generation", {}).get("enabled"), "Music not enabled"
        assert features.get("sfx_generation", {}).get("enabled"), "SFX not enabled"


class TestSmokeTestRegression:
    """Regression test for smoke test."""

    def test_smoke_test_passes(self):
        """Smoke test passes 9/9."""
        result = subprocess.run(
            ["python", "smoke_test.py", BASE_URL],
            cwd="/app/backend",
            capture_output=True,
            text=True,
            env={**os.environ, "TEST_ADMIN_EMAIL": ADMIN_EMAIL, "TEST_ADMIN_PASSWORD": ADMIN_PASSWORD}
        )
        assert "9 passed, 0 failed" in result.stdout, f"Smoke test failed: {result.stdout}"
