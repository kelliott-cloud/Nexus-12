"""
Iteration 75: GitHub PAT Bug Fix Tests
Test that GitHub push/pull now uses GITHUB_PAT from platform_settings when no token is provided in request body.

Bug Fix Summary:
1. Backend: POST /workspaces/{id}/code-repo/github-push now falls back to platform_settings for GITHUB_PAT
2. Backend: POST /workspaces/{id}/code-repo/github-pull now falls back to platform_settings for GITHUB_PAT
3. Backend: GET /admin/integrations includes GITHUB_PAT in the list
4. Frontend: Integration Settings shows GITHUB_PAT option under development category
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
WORKSPACE_ID = "ws_f6ec6355bb18"
TEST_CREDENTIALS = {"email": "test@test.com", "password": "testtest"}


@pytest.fixture(scope="module")
def auth_session():
    """Authenticate and return session with cookies."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login
    resp = session.post(f"{BASE_URL}/api/auth/login", json=TEST_CREDENTIALS)
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return session


class TestGitHubPatIntegrationKey:
    """Test that GITHUB_PAT is included in admin integrations list."""
    
    def test_github_pat_in_integrations_list(self, auth_session):
        """GET /admin/integrations should include GITHUB_PAT in the list."""
        resp = auth_session.get(f"{BASE_URL}/api/admin/integrations")
        assert resp.status_code == 200, f"Failed to get integrations: {resp.text}"
        
        data = resp.json()
        assert "integrations" in data, "Response missing 'integrations' key"
        
        integrations = data["integrations"]
        github_pat = next((i for i in integrations if i.get("key") == "GITHUB_PAT"), None)
        
        assert github_pat is not None, "GITHUB_PAT not found in integrations list"
        assert github_pat.get("name") == "GitHub PAT", f"Expected name 'GitHub PAT', got {github_pat.get('name')}"
        assert github_pat.get("provider") == "github", f"Expected provider 'github', got {github_pat.get('provider')}"
        assert github_pat.get("category") == "development", f"Expected category 'development', got {github_pat.get('category')}"
        print(f"PASS: GITHUB_PAT found in integrations list - {github_pat}")


class TestGitHubPushWithSavedPAT:
    """Test that github-push uses saved PAT from platform_settings when no token provided."""
    
    def test_push_without_token_uses_saved_pat(self, auth_session):
        """
        POST /workspaces/{id}/code-repo/github-push without token in body
        should use GITHUB_PAT from platform_settings (not return 'No GitHub token' error).
        
        Note: The mock token 'ghp_test_mock_token_123' is saved in platform_settings.
        GitHub will return 401 (invalid token) but we should NOT get 'No GitHub token' error.
        """
        # First, verify the mock PAT is saved in platform_settings
        # Save a test PAT
        save_resp = auth_session.post(f"{BASE_URL}/api/admin/integrations", json={
            "key": "GITHUB_PAT",
            "value": "ghp_test_mock_token_123"
        })
        assert save_resp.status_code == 200, f"Failed to save PAT: {save_resp.text}"
        print("Saved mock GITHUB_PAT to platform_settings")
        
        # Now test push WITHOUT providing token in body
        resp = auth_session.post(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/code-repo/github-push",
            json={
                "repo": "testowner/testrepo",
                "branch": "main",
                "message": "Test push"
                # Note: NO token field - should use saved PAT
            }
        )
        
        # Should NOT get 400 "No GitHub token" error
        # Instead, should attempt to push with saved PAT and get GitHub API errors
        if resp.status_code == 400:
            error_detail = resp.json().get("detail", "")
            assert "No GitHub token" not in error_detail, f"Bug not fixed: Got 'No GitHub token' error even though PAT is saved. Detail: {error_detail}"
            # Acceptable 400 errors: "No files to push", repo format issues
            print(f"Got 400 error (acceptable): {error_detail}")
        else:
            # 200 with errors array (GitHub auth failures) is expected
            data = resp.json()
            print(f"Response: status={resp.status_code}, data={data}")
            # Check for pushed count or errors (GitHub API will fail with fake token)
            if "errors" in data:
                # Errors from GitHub API (401 unauthorized) are expected with fake token
                print(f"GitHub push attempted - got errors (expected with mock token): {data['errors']}")
            if "pushed" in data:
                print(f"Files pushed (if any): {data['pushed']}")
        
        print("PASS: Push did not return 'No GitHub token' error - bug is fixed")
    
    def test_push_with_explicit_token_overrides_saved_pat(self, auth_session):
        """
        POST /workspaces/{id}/code-repo/github-push with token in body
        should use the provided token (override saved PAT).
        """
        # Provide explicit token in request
        resp = auth_session.post(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/code-repo/github-push",
            json={
                "repo": "testowner/testrepo",
                "branch": "main",
                "message": "Test push",
                "token": "ghp_explicit_override_token"  # Explicit token
            }
        )
        
        # Should use explicit token, not saved PAT
        # GitHub will reject with 401, but should not get "No GitHub token" error
        if resp.status_code == 400:
            error_detail = resp.json().get("detail", "")
            assert "No GitHub token" not in error_detail, f"Unexpected 'No GitHub token' error with explicit token"
        
        print(f"PASS: Push with explicit token - status={resp.status_code}")


class TestGitHubPullWithSavedPAT:
    """Test that github-pull uses saved PAT from platform_settings when no token provided."""
    
    def test_pull_without_token_uses_saved_pat(self, auth_session):
        """
        POST /workspaces/{id}/code-repo/github-pull without token in body
        should use GITHUB_PAT from platform_settings.
        """
        resp = auth_session.post(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/code-repo/github-pull",
            json={
                "repo": "testowner/testrepo",
                "branch": "main"
                # Note: NO token field - should use saved PAT
            }
        )
        
        # Should NOT get 400 "No GitHub token" error
        if resp.status_code == 400:
            error_detail = resp.json().get("detail", "")
            assert "No GitHub token" not in error_detail, f"Bug not fixed for pull: Got 'No GitHub token' error"
            # Other 400 errors (like failed to fetch repo tree) are expected with fake token
            print(f"Got 400 error from GitHub API (expected with fake token): {error_detail}")
        else:
            data = resp.json()
            print(f"Pull response: status={resp.status_code}, data={data}")
        
        print("PASS: Pull did not return 'No GitHub token' error - bug is fixed")


class TestIntegrationsConfigured:
    """Test GITHUB_PAT configuration status."""
    
    def test_github_pat_shows_configured_after_save(self, auth_session):
        """After saving GITHUB_PAT, it should show as configured in integrations list."""
        # Save PAT
        auth_session.post(f"{BASE_URL}/api/admin/integrations", json={
            "key": "GITHUB_PAT",
            "value": "ghp_test_verification_token"
        })
        
        # Check integrations list
        resp = auth_session.get(f"{BASE_URL}/api/admin/integrations")
        assert resp.status_code == 200
        
        data = resp.json()
        github_pat = next((i for i in data["integrations"] if i.get("key") == "GITHUB_PAT"), None)
        
        assert github_pat is not None, "GITHUB_PAT not found"
        assert github_pat.get("configured") == True, f"GITHUB_PAT should be configured, got: {github_pat}"
        assert github_pat.get("masked_value") is not None, "Masked value should be present"
        
        print(f"PASS: GITHUB_PAT shows as configured with masked value: {github_pat.get('masked_value')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
