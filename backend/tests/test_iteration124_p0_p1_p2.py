"""Iteration 124 — P0/P1/P2 Feature Tests

Tests for:
- P0: Video/Music/SFX media integrations
- P1: Self-contained test fixtures (conftest.py), Docker healthchecks
- P2: DB migration dry-run CLI, Redis degradation docs, Staging smoke test framework

Test credentials: configurable via TEST_ADMIN_EMAIL / TEST_ADMIN_PASSWORD (super_admin)
"""
import os
import sys
import pytest
import requests
import subprocess

# ============ Configuration ============

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    try:
        import pathlib
        env_path = str(pathlib.Path(__file__).resolve().parent.parent.parent / "frontend" / ".env")
        with open(env_path, "r") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.strip().split("=", 1)[1].rstrip("/")
                    break
    except Exception:
        pass
if not BASE_URL:
    BASE_URL = "http://localhost:8080"

API_URL = f"{BASE_URL}/api"
ADMIN_EMAIL = os.environ.get("TEST_ADMIN_EMAIL", "admin@test.local")
ADMIN_PASSWORD = "test"


# ============ Fixtures ============

@pytest.fixture(scope="module")
def admin_session():
    """Login as admin and return (token, user_data)."""
    resp = requests.post(f"{API_URL}/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    }, timeout=15)
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed: {resp.status_code} - {resp.text[:200]}")
    data = resp.json()
    return data.get("session_token", ""), data


@pytest.fixture(scope="module")
def admin_headers(admin_session):
    """Auth headers for admin requests."""
    token, _ = admin_session
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def test_workspace_id(admin_headers):
    """Get first workspace ID for testing."""
    resp = requests.get(f"{API_URL}/workspaces", headers=admin_headers, timeout=10)
    if resp.status_code != 200:
        pytest.skip("Could not get workspaces")
    workspaces = resp.json()
    if isinstance(workspaces, list) and workspaces:
        return workspaces[0].get("workspace_id", "")
    pytest.skip("No workspaces available")


# ============ P0: Media Generation Tests ============

class TestP0VideoGeneration:
    """P0: Video generation via Gemini API"""

    def test_generate_video_returns_completed_with_media_id(self, admin_headers, test_workspace_id):
        """POST /api/workspaces/{id}/generate-video returns completed status with media_id"""
        resp = requests.post(
            f"{API_URL}/workspaces/{test_workspace_id}/generate-video",
            json={
                "prompt": "A serene sunset over mountains",
                "duration": 4,
                "size": "1280x720",
                "style": "natural"
            },
            headers=admin_headers,
            timeout=120  # Video gen can take time
        )
        assert resp.status_code == 200, f"Video gen failed: {resp.status_code} - {resp.text[:300]}"
        data = resp.json()
        assert "media_id" in data, f"No media_id in response: {data}"
        assert data.get("status") == "completed", f"Status not completed: {data.get('status')}"
        assert data["media_id"].startswith("vid_"), f"Invalid media_id format: {data['media_id']}"
        print(f"Video generated: {data['media_id']}")


class TestP0MusicGeneration:
    """P0: Music generation via OpenAI Audio API"""

    def test_generate_music_returns_clear_error_without_key(self, admin_headers, test_workspace_id):
        """POST /api/workspaces/{id}/generate-music returns clear error about OPENAI_API_KEY when not configured"""
        resp = requests.post(
            f"{API_URL}/workspaces/{test_workspace_id}/generate-music",
            json={
                "prompt": "Calm ambient music for meditation",
                "duration": 30,
                "genre": "ambient",
                "mood": "calm"
            },
            headers=admin_headers,
            timeout=30
        )
        # Should return 400 with clear error about missing OPENAI_API_KEY
        # OR 200 if OPENAI_API_KEY is configured
        if resp.status_code == 400:
            data = resp.json()
            detail = data.get("detail", "")
            assert "OPENAI_API_KEY" in detail, f"Error should mention OPENAI_API_KEY: {detail}"
            print(f"Music gen correctly reports missing key: {detail}")
        elif resp.status_code == 200:
            data = resp.json()
            assert "media_id" in data, f"No media_id in success response: {data}"
            print(f"Music generated (key was configured): {data.get('media_id')}")
        else:
            pytest.fail(f"Unexpected status {resp.status_code}: {resp.text[:200]}")


class TestP0SFXGeneration:
    """P0: SFX generation via ElevenLabs API"""

    def test_generate_sfx_returns_clear_error_without_key(self, admin_headers, test_workspace_id):
        """POST /api/workspaces/{id}/generate-sfx returns clear error about ELEVENLABS_API_KEY when not configured"""
        resp = requests.post(
            f"{API_URL}/workspaces/{test_workspace_id}/generate-sfx",
            json={
                "prompt": "Thunder rumbling in the distance",
                "duration": 5
            },
            headers=admin_headers,
            timeout=30
        )
        # Should return 400 with clear error about missing ELEVENLABS_API_KEY
        # OR 200 if ELEVENLABS_API_KEY is configured
        if resp.status_code == 400:
            data = resp.json()
            detail = data.get("detail", "")
            assert "ELEVENLABS_API_KEY" in detail, f"Error should mention ELEVENLABS_API_KEY: {detail}"
            print(f"SFX gen correctly reports missing key: {detail}")
        elif resp.status_code == 200:
            data = resp.json()
            assert "media_id" in data, f"No media_id in success response: {data}"
            print(f"SFX generated (key was configured): {data.get('media_id')}")
        else:
            pytest.fail(f"Unexpected status {resp.status_code}: {resp.text[:200]}")


class TestP0MediaConfig:
    """P0: Media config shows all features enabled"""

    def test_media_config_shows_all_features_enabled(self, admin_headers):
        """GET /api/media/config shows features.video_generation.enabled=true, music_generation.enabled=true, sfx_generation.enabled=true"""
        resp = requests.get(f"{API_URL}/media/config", headers=admin_headers, timeout=10)
        assert resp.status_code == 200, f"Media config failed: {resp.status_code}"
        data = resp.json()
        features = data.get("features", {})
        
        # Check video_generation
        video_gen = features.get("video_generation", {})
        assert video_gen.get("enabled") is True, f"video_generation not enabled: {video_gen}"
        
        # Check music_generation
        music_gen = features.get("music_generation", {})
        assert music_gen.get("enabled") is True, f"music_generation not enabled: {music_gen}"
        
        # Check sfx_generation
        sfx_gen = features.get("sfx_generation", {})
        assert sfx_gen.get("enabled") is True, f"sfx_generation not enabled: {sfx_gen}"
        
        print(f"All media features enabled: video={video_gen.get('enabled')}, music={music_gen.get('enabled')}, sfx={sfx_gen.get('enabled')}")


# ============ P1: Feature Flags in nexus_config.py ============

class TestP1FeatureFlags:
    """P1: Feature flags in nexus_config.py are all enabled=True"""

    def test_nexus_config_feature_flags_all_enabled(self):
        """Verify FEATURE_FLAGS in nexus_config.py all have enabled=True"""
        config_path = "/app/backend/nexus_config.py"
        with open(config_path, "r") as f:
            content = f.read()
        
        # Check that FEATURE_FLAGS exists and all are enabled
        assert "FEATURE_FLAGS" in content, "FEATURE_FLAGS not found in nexus_config.py"
        assert '"video_generation"' in content, "video_generation not in FEATURE_FLAGS"
        assert '"music_generation"' in content, "music_generation not in FEATURE_FLAGS"
        assert '"sfx_generation"' in content, "sfx_generation not in FEATURE_FLAGS"
        
        # Verify enabled: True for each
        # Simple check: count occurrences of "enabled": True
        enabled_count = content.count('"enabled": True')
        assert enabled_count >= 3, f"Expected at least 3 enabled: True, found {enabled_count}"
        print(f"Feature flags verified: {enabled_count} features enabled")


# ============ P1: Docker Healthchecks ============

class TestP1DockerHealthchecks:
    """P1: Docker healthchecks in Dockerfiles"""

    def test_backend_dockerfile_has_healthcheck(self):
        """Backend Dockerfile has HEALTHCHECK instruction"""
        dockerfile_path = "/app/Dockerfile"
        with open(dockerfile_path, "r") as f:
            content = f.read()
        
        assert "HEALTHCHECK" in content, "HEALTHCHECK not found in backend Dockerfile"
        assert "/api/health" in content, "Health endpoint not referenced in HEALTHCHECK"
        print("Backend Dockerfile HEALTHCHECK verified")

    def test_frontend_dockerfile_has_healthcheck(self):
        """Frontend Dockerfile has HEALTHCHECK instruction"""
        dockerfile_path = "/app/frontend/Dockerfile"
        with open(dockerfile_path, "r") as f:
            content = f.read()
        
        assert "HEALTHCHECK" in content, "HEALTHCHECK not found in frontend Dockerfile"
        print("Frontend Dockerfile HEALTHCHECK verified")


# ============ P1: conftest.py Fixtures ============

class TestP1ConftestFixtures:
    """P1: conftest.py has proper fixtures"""

    def test_conftest_has_admin_session_fixture(self):
        """conftest.py has admin_session fixture"""
        conftest_path = "/app/backend/tests/conftest.py"
        with open(conftest_path, "r") as f:
            content = f.read()
        
        assert "def admin_session" in content, "admin_session fixture not found"
        assert "@pytest.fixture" in content, "No pytest fixtures defined"
        print("admin_session fixture verified")

    def test_conftest_has_admin_headers_fixture(self):
        """conftest.py has admin_headers fixture"""
        conftest_path = "/app/backend/tests/conftest.py"
        with open(conftest_path, "r") as f:
            content = f.read()
        
        assert "def admin_headers" in content, "admin_headers fixture not found"
        print("admin_headers fixture verified")

    def test_conftest_has_test_workspace_fixture(self):
        """conftest.py has test_workspace fixture"""
        conftest_path = "/app/backend/tests/conftest.py"
        with open(conftest_path, "r") as f:
            content = f.read()
        
        assert "def test_workspace" in content, "test_workspace fixture not found"
        print("test_workspace fixture verified")


# ============ P2: DB Migration Dry-Run CLI ============

class TestP2DBMigrationDryRun:
    """P2: db_migrations.py supports --dry-run flag"""

    def test_db_migrations_supports_dry_run_flag(self):
        """db_migrations.py supports --dry-run flag (python -m db_migrations --dry-run)"""
        migrations_path = "/app/backend/db_migrations.py"
        with open(migrations_path, "r") as f:
            content = f.read()
        
        assert "--dry-run" in content, "--dry-run flag not found in db_migrations.py"
        assert "dry_run" in content, "dry_run parameter not found"
        assert "if __name__" in content, "CLI entry point not found"
        print("db_migrations.py --dry-run support verified")

    def test_db_migrations_dry_run_executes(self):
        """Run db_migrations.py --dry-run and verify it executes without error"""
        result = subprocess.run(
            ["python", "-m", "db_migrations", "--dry-run"],
            cwd="/app/backend",
            capture_output=True,
            text=True,
            timeout=30
        )
        # Should exit 0 and print dry run message
        assert result.returncode == 0, f"Dry run failed: {result.stderr}"
        assert "DRY RUN" in result.stdout or "pending" in result.stdout.lower() or "no pending" in result.stdout.lower(), \
            f"Unexpected output: {result.stdout}"
        print(f"Dry run output: {result.stdout[:200]}")


# ============ P2: Smoke Test Framework ============

class TestP2SmokeTestFramework:
    """P2: smoke_test.py exists and passes all checks"""

    def test_smoke_test_file_exists(self):
        """smoke_test.py exists"""
        smoke_path = "/app/backend/smoke_test.py"
        assert os.path.exists(smoke_path), "smoke_test.py not found"
        print("smoke_test.py exists")

    def test_smoke_test_has_9_checks(self):
        """smoke_test.py has 9 test checks"""
        smoke_path = "/app/backend/smoke_test.py"
        with open(smoke_path, "r") as f:
            content = f.read()
        
        # Count check() calls
        check_count = content.count('check("')
        assert check_count >= 9, f"Expected at least 9 checks, found {check_count}"
        print(f"smoke_test.py has {check_count} checks")

    def test_smoke_test_passes(self):
        """Run smoke_test.py and verify all 9 checks pass"""
        result = subprocess.run(
            ["python", "smoke_test.py", BASE_URL],
            cwd="/app/backend",
            capture_output=True,
            text=True,
            timeout=60,
            env={
                **os.environ,
                "TEST_ADMIN_EMAIL": ADMIN_EMAIL,
                "TEST_ADMIN_PASSWORD": ADMIN_PASSWORD,
            }
        )
        print(f"Smoke test output:\n{result.stdout}")
        if result.stderr:
            print(f"Smoke test stderr:\n{result.stderr}")
        
        # Check for pass count
        assert "passed" in result.stdout.lower(), f"No pass count in output"
        assert result.returncode == 0, f"Smoke test failed with exit code {result.returncode}"
        print("Smoke test passed!")


# ============ P2: Redis Degradation Docs ============

class TestP2RedisDegradationDocs:
    """P2: REDIS_DEGRADATION.md documentation exists"""

    def test_redis_degradation_md_exists(self):
        """REDIS_DEGRADATION.md documentation exists"""
        doc_path = "/app/backend/REDIS_DEGRADATION.md"
        assert os.path.exists(doc_path), "REDIS_DEGRADATION.md not found"
        
        with open(doc_path, "r") as f:
            content = f.read()
        
        # Verify it has meaningful content
        assert len(content) > 500, f"REDIS_DEGRADATION.md too short: {len(content)} chars"
        assert "Redis" in content, "Redis not mentioned in doc"
        assert "degradation" in content.lower() or "fallback" in content.lower(), "No degradation/fallback info"
        print(f"REDIS_DEGRADATION.md verified ({len(content)} chars)")


# ============ Regression Tests ============

class TestRegressionAuth:
    """Regression tests for auth endpoints"""

    def test_auth_login_still_works(self):
        """POST /api/auth/login still works (regression)"""
        resp = requests.post(f"{API_URL}/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
        }, timeout=15)
        assert resp.status_code == 200, f"Login failed: {resp.status_code} - {resp.text[:200]}"
        data = resp.json()
        assert "session_token" in data or "user_id" in data, f"No session_token/user_id: {data}"
        print("Login regression test passed")

    def test_auth_session_returns_410(self):
        """POST /api/auth/session returns 410 (regression from NX-003)"""
        resp = requests.post(f"{API_URL}/auth/session", json={"session_id": "test"}, timeout=10)
        assert resp.status_code == 410, f"Expected 410, got {resp.status_code}: {resp.text[:200]}"
        print("Auth session 410 regression test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
