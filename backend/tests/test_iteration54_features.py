"""
Iteration 54: Testing New Features
1. Repo Analytics: GET /workspaces/{ws}/code-repo/analytics returns stats
2. User Preferences: PUT/GET /user/preferences saves and returns theme
3. Workspace Settings: PUT /workspaces/{ws}/settings saves auto_collab_max_rounds
4. Regression: Chat messages, Code repo panel
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
TEST_EMAIL = "test@test.com"
TEST_PASSWORD = "test123"
TEST_WORKSPACE_ID = "ws_f6ec6355bb18"


class TestAuth:
    """Authentication for subsequent tests"""
    session = None
    token = None

    @classmethod
    def get_session(cls):
        if cls.session is None:
            cls.session = requests.Session()
            # Login
            resp = cls.session.post(f"{BASE_URL}/api/auth/login", json={
                "email": TEST_EMAIL, "password": TEST_PASSWORD
            })
            assert resp.status_code == 200, f"Login failed: {resp.text}"
            cls.token = resp.cookies.get("session_token") or resp.json().get("token")
            if cls.token:
                cls.session.headers.update({"Authorization": f"Bearer {cls.token}"})
        return cls.session


# ===================== Repo Analytics Tests =====================

class TestRepoAnalytics:
    """Tests for GET /api/workspaces/{ws}/code-repo/analytics endpoint"""

    def test_repo_analytics_returns_200(self):
        """GET /api/workspaces/{ws}/code-repo/analytics returns 200"""
        session = TestAuth.get_session()
        resp = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/analytics")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_repo_analytics_has_required_fields(self):
        """Analytics response contains all required fields: file_count, commit_count, language_stats, contributors, recent_commits"""
        session = TestAuth.get_session()
        resp = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/analytics")
        assert resp.status_code == 200
        data = resp.json()
        
        # Required fields
        required_fields = ["file_count", "commit_count", "language_stats", "contributors", "recent_commits"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Additional expected fields
        assert "folder_count" in data, "Missing folder_count"
        assert "branch_count" in data, "Missing branch_count"
        assert "review_count" in data, "Missing review_count"

    def test_repo_analytics_field_types(self):
        """Analytics fields have correct types"""
        session = TestAuth.get_session()
        resp = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/analytics")
        assert resp.status_code == 200
        data = resp.json()
        
        assert isinstance(data["file_count"], int), "file_count should be int"
        assert isinstance(data["commit_count"], int), "commit_count should be int"
        assert isinstance(data["language_stats"], list), "language_stats should be list"
        assert isinstance(data["contributors"], list), "contributors should be list"
        assert isinstance(data["recent_commits"], list), "recent_commits should be list"

    def test_repo_analytics_language_stats_structure(self):
        """Language stats have correct structure if present"""
        session = TestAuth.get_session()
        resp = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/analytics")
        assert resp.status_code == 200
        data = resp.json()
        
        if len(data["language_stats"]) > 0:
            lang_stat = data["language_stats"][0]
            assert "language" in lang_stat, "language_stats items should have 'language'"
            assert "count" in lang_stat, "language_stats items should have 'count'"

    def test_repo_analytics_contributors_structure(self):
        """Contributors have correct structure if present"""
        session = TestAuth.get_session()
        resp = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/analytics")
        assert resp.status_code == 200
        data = resp.json()
        
        if len(data["contributors"]) > 0:
            contrib = data["contributors"][0]
            assert "name" in contrib, "contributors items should have 'name'"
            assert "commits" in contrib, "contributors items should have 'commits'"

    def test_repo_analytics_recent_commits_structure(self):
        """Recent commits have correct structure if present"""
        session = TestAuth.get_session()
        resp = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/analytics")
        assert resp.status_code == 200
        data = resp.json()
        
        if len(data["recent_commits"]) > 0:
            commit = data["recent_commits"][0]
            assert "commit_id" in commit, "recent_commits items should have 'commit_id'"
            assert "file_path" in commit, "recent_commits items should have 'file_path'"
            assert "action" in commit, "recent_commits items should have 'action'"
            assert "author_name" in commit, "recent_commits items should have 'author_name'"


# ===================== User Preferences Tests =====================

class TestUserPreferences:
    """Tests for PUT/GET /api/user/preferences endpoints"""

    def test_get_user_preferences_returns_200(self):
        """GET /api/user/preferences returns 200"""
        session = TestAuth.get_session()
        resp = session.get(f"{BASE_URL}/api/user/preferences")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_get_user_preferences_returns_theme_and_language(self):
        """GET /api/user/preferences returns theme and language"""
        session = TestAuth.get_session()
        resp = session.get(f"{BASE_URL}/api/user/preferences")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "theme" in data, "Response should contain 'theme'"
        assert "language" in data, "Response should contain 'language'"

    def test_put_user_preferences_theme_dark(self):
        """PUT /api/user/preferences saves theme=dark"""
        session = TestAuth.get_session()
        resp = session.put(f"{BASE_URL}/api/user/preferences", json={"theme": "dark"})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        # Verify persistence
        get_resp = session.get(f"{BASE_URL}/api/user/preferences")
        assert get_resp.status_code == 200
        assert get_resp.json()["theme"] == "dark"

    def test_put_user_preferences_theme_light(self):
        """PUT /api/user/preferences saves theme=light"""
        session = TestAuth.get_session()
        resp = session.put(f"{BASE_URL}/api/user/preferences", json={"theme": "light"})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        # Verify persistence
        get_resp = session.get(f"{BASE_URL}/api/user/preferences")
        assert get_resp.status_code == 200
        assert get_resp.json()["theme"] == "light"

    def test_put_user_preferences_theme_system(self):
        """PUT /api/user/preferences saves theme=system"""
        session = TestAuth.get_session()
        resp = session.put(f"{BASE_URL}/api/user/preferences", json={"theme": "system"})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        # Verify persistence
        get_resp = session.get(f"{BASE_URL}/api/user/preferences")
        assert get_resp.status_code == 200
        assert get_resp.json()["theme"] == "system"

    def test_put_user_preferences_revert_to_dark(self):
        """Reset theme back to dark for clean state"""
        session = TestAuth.get_session()
        resp = session.put(f"{BASE_URL}/api/user/preferences", json={"theme": "dark"})
        assert resp.status_code == 200


# ===================== Workspace Settings Tests =====================

class TestWorkspaceSettings:
    """Tests for PUT/GET /api/workspaces/{ws}/settings endpoints"""

    def test_get_workspace_settings_returns_200(self):
        """GET /api/workspaces/{ws}/settings returns 200"""
        session = TestAuth.get_session()
        resp = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/settings")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_get_workspace_settings_has_auto_collab_max_rounds(self):
        """GET /api/workspaces/{ws}/settings returns auto_collab_max_rounds"""
        session = TestAuth.get_session()
        resp = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/settings")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "auto_collab_max_rounds" in data, "Response should contain 'auto_collab_max_rounds'"
        assert isinstance(data["auto_collab_max_rounds"], int), "auto_collab_max_rounds should be int"

    def test_put_workspace_settings_auto_collab_rounds(self):
        """PUT /api/workspaces/{ws}/settings saves auto_collab_max_rounds"""
        session = TestAuth.get_session()
        # Get current value
        get_resp = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/settings")
        original_rounds = get_resp.json().get("auto_collab_max_rounds", 10)
        
        # Set new value
        new_value = 25
        resp = session.put(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/settings", json={
            "auto_collab_max_rounds": new_value
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        # Verify persistence
        get_resp = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/settings")
        assert get_resp.status_code == 200
        assert get_resp.json()["auto_collab_max_rounds"] == new_value
        
        # Restore original
        session.put(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/settings", json={
            "auto_collab_max_rounds": original_rounds
        })

    def test_put_workspace_settings_min_rounds(self):
        """PUT /api/workspaces/{ws}/settings clamps min value to 5"""
        session = TestAuth.get_session()
        resp = session.put(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/settings", json={
            "auto_collab_max_rounds": 1  # Below min
        })
        assert resp.status_code == 200
        
        get_resp = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/settings")
        assert get_resp.json()["auto_collab_max_rounds"] >= 5, "Value should be clamped to minimum 5"

    def test_put_workspace_settings_max_rounds(self):
        """PUT /api/workspaces/{ws}/settings clamps max value to 50"""
        session = TestAuth.get_session()
        resp = session.put(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/settings", json={
            "auto_collab_max_rounds": 100  # Above max
        })
        assert resp.status_code == 200
        
        get_resp = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/settings")
        assert get_resp.json()["auto_collab_max_rounds"] <= 50, "Value should be clamped to maximum 50"


# ===================== Regression Tests =====================

class TestRegression:
    """Regression tests for existing features"""

    def test_channels_list_returns_200(self):
        """GET /api/workspaces/{ws}/channels returns 200"""
        session = TestAuth.get_session()
        resp = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/channels")
        assert resp.status_code == 200

    def test_messages_endpoint_works(self):
        """GET /api/channels/{ch}/messages returns 200"""
        session = TestAuth.get_session()
        # Get channels first
        ch_resp = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/channels")
        channels = ch_resp.json()
        if len(channels) > 0:
            channel_id = channels[0]["channel_id"]
            msg_resp = session.get(f"{BASE_URL}/api/channels/{channel_id}/messages")
            assert msg_resp.status_code == 200
            assert isinstance(msg_resp.json(), list)

    def test_code_repo_tree_returns_200(self):
        """GET /api/workspaces/{ws}/code-repo/tree returns 200"""
        session = TestAuth.get_session()
        resp = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/tree")
        assert resp.status_code == 200
        data = resp.json()
        assert "files" in data, "Response should contain 'files'"

    def test_code_repo_branches_returns_200(self):
        """GET /api/workspaces/{ws}/code-repo/branches returns 200"""
        session = TestAuth.get_session()
        resp = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/branches")
        assert resp.status_code == 200
        data = resp.json()
        assert "branches" in data, "Response should contain 'branches'"

    def test_workspace_exists(self):
        """GET /api/workspaces/{ws} returns 200"""
        session = TestAuth.get_session()
        resp = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert "workspace_id" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
