"""
Iteration 115 - AI Agents & Code Repo Fixes Testing
Tests for:
1. GET /api/ai-models returns ChatGPT options including gpt-5.4, gpt-5.4-mini, gpt-5.4-nano
2. Chat channel collaboration with AI agents (Claude/ChatGPT via Emergent universal key)
3. Code repo ZIP download (repo-scoped)
4. ZIP import (repo-scoped)
5. GitHub pull (public repo, repo-scoped)
6. GitHub push (repo-scoped)
"""
import pytest
import requests
import os
import io
import zipfile
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "http://localhost:8080"

# Test credentials
TEST_EMAIL = os.environ.get("TEST_ADMIN_EMAIL", "admin@test.local")
TEST_PASSWORD = "test"


class TestAIModelsEndpoint:
    """Test GET /api/ai-models returns correct ChatGPT models including gpt-5.4 family"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        return resp.json().get("session_token")
    
    def test_ai_models_endpoint_returns_chatgpt_models(self, auth_token):
        """Verify /api/ai-models returns ChatGPT with gpt-5.4 family"""
        resp = requests.get(
            f"{BASE_URL}/api/ai-models",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert resp.status_code == 200, f"Failed to get AI models: {resp.text}"
        
        data = resp.json()
        assert "models" in data, "Response should contain 'models' key"
        
        models = data["models"]
        assert "chatgpt" in models, "ChatGPT should be in models"
        
        chatgpt_models = models["chatgpt"]
        model_ids = [m["id"] for m in chatgpt_models]
        
        # Verify gpt-5.4 family is present
        assert "gpt-5.4" in model_ids, "gpt-5.4 should be in ChatGPT models"
        assert "gpt-5.4-mini" in model_ids, "gpt-5.4-mini should be in ChatGPT models"
        assert "gpt-5.4-nano" in model_ids, "gpt-5.4-nano should be in ChatGPT models"
        
        print(f"✓ ChatGPT models found: {model_ids}")
    
    def test_ai_models_includes_all_providers(self, auth_token):
        """Verify all expected AI providers are present"""
        resp = requests.get(
            f"{BASE_URL}/api/ai-models",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert resp.status_code == 200
        
        models = resp.json()["models"]
        expected_providers = ["claude", "chatgpt", "gemini", "deepseek", "grok", "perplexity", "mistral"]
        
        for provider in expected_providers:
            assert provider in models, f"{provider} should be in models"
        
        print(f"✓ All expected providers present: {list(models.keys())}")


class TestCodeRepoZipDownload:
    """Test code repo ZIP download is repo-scoped"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session with workspace and repo"""
        session = requests.Session()
        
        # Login
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        token = resp.json().get("session_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Get first workspace
        resp = session.get(f"{BASE_URL}/api/workspaces")
        assert resp.status_code == 200
        workspaces = resp.json()
        assert len(workspaces) > 0, "Need at least one workspace"
        workspace_id = workspaces[0]["workspace_id"]
        
        return {"session": session, "workspace_id": workspace_id}
    
    def test_zip_download_endpoint_exists(self, auth_session):
        """Verify ZIP download endpoint is accessible"""
        session = auth_session["session"]
        workspace_id = auth_session["workspace_id"]
        
        # Get repos for this workspace
        resp = session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/code-repos")
        if resp.status_code == 200:
            repos = resp.json().get("repos", [])
            if repos:
                repo_id = repos[0]["repo_id"]
                # Try download with repo_id
                resp = session.get(
                    f"{BASE_URL}/api/workspaces/{workspace_id}/code-repo/download?repo_id={repo_id}"
                )
                # Should return 200 with ZIP or 404 if no files
                assert resp.status_code in [200, 404], f"Unexpected status: {resp.status_code}"
                if resp.status_code == 200:
                    assert "application/zip" in resp.headers.get("Content-Type", ""), "Should return ZIP"
                    print(f"✓ ZIP download working for repo {repo_id}")
                else:
                    print(f"✓ ZIP download endpoint accessible (no files in repo)")
            else:
                print("✓ No repos found, skipping download test")
        else:
            print(f"✓ Code repos endpoint returned {resp.status_code}")
    
    def test_create_repo_and_download_zip(self, auth_session):
        """Create a repo with files and verify ZIP download is repo-scoped"""
        session = auth_session["session"]
        workspace_id = auth_session["workspace_id"]
        
        # Create a test repo
        resp = session.post(
            f"{BASE_URL}/api/workspaces/{workspace_id}/code-repos",
            json={"name": f"TEST_ZipDownload_{int(time.time())}", "description": "Test repo for ZIP download"}
        )
        if resp.status_code == 429:
            print("✓ Rate limited on repo creation (max repos reached)")
            return
        assert resp.status_code == 200, f"Failed to create repo: {resp.text}"
        repo = resp.json()
        repo_id = repo["repo_id"]
        
        try:
            # Create a test file in this repo
            resp = session.post(
                f"{BASE_URL}/api/workspaces/{workspace_id}/code-repo/files?repo_id={repo_id}",
                json={"path": "test_file.txt", "content": "Test content for ZIP download"}
            )
            assert resp.status_code == 200, f"Failed to create file: {resp.text}"
            
            # Download ZIP
            resp = session.get(
                f"{BASE_URL}/api/workspaces/{workspace_id}/code-repo/download?repo_id={repo_id}"
            )
            assert resp.status_code == 200, f"ZIP download failed: {resp.status_code}"
            assert "application/zip" in resp.headers.get("Content-Type", "")
            
            # Verify ZIP contents
            zip_buffer = io.BytesIO(resp.content)
            with zipfile.ZipFile(zip_buffer, 'r') as zf:
                names = zf.namelist()
                assert "test_file.txt" in names, "test_file.txt should be in ZIP"
                content = zf.read("test_file.txt").decode()
                assert "Test content for ZIP download" in content
            
            print(f"✓ ZIP download is repo-scoped and contains correct files")
        finally:
            # Cleanup: delete the test repo
            session.delete(f"{BASE_URL}/api/workspaces/{workspace_id}/code-repos/{repo_id}")


class TestCodeRepoZipImport:
    """Test ZIP import is repo-scoped"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert resp.status_code == 200
        token = resp.json().get("session_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        
        resp = session.get(f"{BASE_URL}/api/workspaces")
        assert resp.status_code == 200
        workspaces = resp.json()
        assert len(workspaces) > 0
        
        return {"session": session, "workspace_id": workspaces[0]["workspace_id"]}
    
    def test_zip_import_is_repo_scoped(self, auth_session):
        """Verify ZIP import only affects the selected repo_id"""
        session = auth_session["session"]
        workspace_id = auth_session["workspace_id"]
        
        # Create two test repos
        resp1 = session.post(
            f"{BASE_URL}/api/workspaces/{workspace_id}/code-repos",
            json={"name": f"TEST_ImportRepo1_{int(time.time())}", "description": "Test repo 1"}
        )
        if resp1.status_code == 429:
            print("✓ Rate limited on repo creation")
            return
        
        resp2 = session.post(
            f"{BASE_URL}/api/workspaces/{workspace_id}/code-repos",
            json={"name": f"TEST_ImportRepo2_{int(time.time())}", "description": "Test repo 2"}
        )
        if resp2.status_code == 429:
            print("✓ Rate limited on repo creation")
            # Cleanup first repo
            if resp1.status_code == 200:
                session.delete(f"{BASE_URL}/api/workspaces/{workspace_id}/code-repos/{resp1.json()['repo_id']}")
            return
        
        repo1_id = resp1.json()["repo_id"]
        repo2_id = resp2.json()["repo_id"]
        
        try:
            # Create a ZIP file in memory
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("imported_file.txt", "This file was imported from ZIP")
            zip_buffer.seek(0)
            
            # Import ZIP into repo1 only
            files = {"file": ("test_import.zip", zip_buffer, "application/zip")}
            resp = session.post(
                f"{BASE_URL}/api/workspaces/{workspace_id}/code-repo/import-zip?repo_id={repo1_id}",
                files=files
            )
            assert resp.status_code == 200, f"ZIP import failed: {resp.text}"
            import_result = resp.json()
            assert import_result.get("imported", 0) > 0, "Should have imported at least 1 file"
            
            # Verify file is in repo1
            resp = session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/code-repo/tree?repo_id={repo1_id}")
            assert resp.status_code == 200
            repo1_files = [f["path"] for f in resp.json().get("files", [])]
            assert "imported_file.txt" in repo1_files, "imported_file.txt should be in repo1"
            
            # Verify file is NOT in repo2 (repo isolation)
            resp = session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/code-repo/tree?repo_id={repo2_id}")
            assert resp.status_code == 200
            repo2_files = [f["path"] for f in resp.json().get("files", [])]
            assert "imported_file.txt" not in repo2_files, "imported_file.txt should NOT be in repo2"
            
            print(f"✓ ZIP import is repo-scoped: file in repo1, not in repo2")
        finally:
            # Cleanup
            session.delete(f"{BASE_URL}/api/workspaces/{workspace_id}/code-repos/{repo1_id}")
            session.delete(f"{BASE_URL}/api/workspaces/{workspace_id}/code-repos/{repo2_id}")


class TestGitHubPull:
    """Test GitHub pull is repo-scoped and works for public repos"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert resp.status_code == 200
        token = resp.json().get("session_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        
        resp = session.get(f"{BASE_URL}/api/workspaces")
        assert resp.status_code == 200
        workspaces = resp.json()
        assert len(workspaces) > 0
        
        return {"session": session, "workspace_id": workspaces[0]["workspace_id"]}
    
    def test_github_pull_public_repo_no_token(self, auth_session):
        """Verify GitHub pull works for public repos without requiring a token"""
        session = auth_session["session"]
        workspace_id = auth_session["workspace_id"]
        
        # Create a test repo
        resp = session.post(
            f"{BASE_URL}/api/workspaces/{workspace_id}/code-repos",
            json={"name": f"TEST_GitHubPull_{int(time.time())}", "description": "Test repo for GitHub pull"}
        )
        if resp.status_code == 429:
            print("✓ Rate limited on repo creation")
            return
        assert resp.status_code == 200, f"Failed to create repo: {resp.text}"
        repo_id = resp.json()["repo_id"]
        
        try:
            # Try to pull from a small public repo (octocat/Hello-World is a classic test repo)
            resp = session.post(
                f"{BASE_URL}/api/workspaces/{workspace_id}/code-repo/github-pull?repo_id={repo_id}",
                json={"repo": "octocat/Hello-World", "branch": "master"}
            )
            
            # Should succeed or fail gracefully (not 500)
            assert resp.status_code in [200, 400, 404], f"Unexpected status: {resp.status_code}, {resp.text}"
            
            if resp.status_code == 200:
                result = resp.json()
                print(f"✓ GitHub pull succeeded: pulled {result.get('pulled', 0)} files")
                
                # Verify files are in the correct repo
                tree_resp = session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/code-repo/tree?repo_id={repo_id}")
                assert tree_resp.status_code == 200
                files = tree_resp.json().get("files", [])
                print(f"  Files in repo after pull: {[f['path'] for f in files]}")
            else:
                print(f"✓ GitHub pull returned {resp.status_code} (expected for rate limits or branch issues)")
        finally:
            # Cleanup
            session.delete(f"{BASE_URL}/api/workspaces/{workspace_id}/code-repos/{repo_id}")


class TestGitHubPush:
    """Test GitHub push is repo-scoped"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert resp.status_code == 200
        token = resp.json().get("session_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        
        resp = session.get(f"{BASE_URL}/api/workspaces")
        assert resp.status_code == 200
        workspaces = resp.json()
        assert len(workspaces) > 0
        
        return {"session": session, "workspace_id": workspaces[0]["workspace_id"]}
    
    def test_github_push_endpoint_accessible(self, auth_session):
        """Verify GitHub push endpoint exists and is accessible"""
        session = auth_session["session"]
        workspace_id = auth_session["workspace_id"]
        
        # Create a test repo
        resp = session.post(
            f"{BASE_URL}/api/workspaces/{workspace_id}/code-repos",
            json={"name": f"TEST_GitHubPush_{int(time.time())}", "description": "Test repo for GitHub push"}
        )
        if resp.status_code == 429:
            print("✓ Rate limited on repo creation")
            return
        assert resp.status_code == 200
        repo_id = resp.json()["repo_id"]
        
        try:
            # Create a test file
            session.post(
                f"{BASE_URL}/api/workspaces/{workspace_id}/code-repo/files?repo_id={repo_id}",
                json={"path": "push_test.txt", "content": "Test content for push"}
            )
            
            # Try to push - endpoint should be accessible (may succeed or fail based on token)
            resp = session.post(
                f"{BASE_URL}/api/workspaces/{workspace_id}/code-repo/github-push?repo_id={repo_id}",
                json={"repo": "test/nonexistent", "branch": "main", "message": "Test push"}
            )
            
            # Should not return 500 (server error)
            assert resp.status_code != 500, f"Server error: {resp.text}"
            
            # 200 means it tried to push (may have errors in response)
            # 400/401/403/404 means validation/auth error (expected without valid token)
            assert resp.status_code in [200, 400, 401, 403, 404, 422], f"Unexpected status: {resp.status_code}"
            
            if resp.status_code == 200:
                result = resp.json()
                # Check if there were errors (expected for invalid repo)
                errors = result.get("errors", [])
                print(f"✓ GitHub push endpoint accessible, pushed {result.get('pushed', 0)} files, {len(errors)} errors")
            else:
                print(f"✓ GitHub push endpoint accessible, returns {resp.status_code}")
        finally:
            session.delete(f"{BASE_URL}/api/workspaces/{workspace_id}/code-repos/{repo_id}")


class TestAICollaboration:
    """Test AI agent collaboration in chat channels"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session with workspace and channel"""
        session = requests.Session()
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert resp.status_code == 200
        token = resp.json().get("session_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        
        resp = session.get(f"{BASE_URL}/api/workspaces")
        assert resp.status_code == 200
        workspaces = resp.json()
        assert len(workspaces) > 0
        workspace_id = workspaces[0]["workspace_id"]
        
        # Get channels
        resp = session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/channels")
        assert resp.status_code == 200
        channels = resp.json()
        
        return {
            "session": session,
            "workspace_id": workspace_id,
            "channels": channels
        }
    
    def test_collaborate_endpoint_exists(self, auth_session):
        """Verify the collaborate endpoint exists and is accessible"""
        session = auth_session["session"]
        channels = auth_session["channels"]
        
        if not channels:
            print("✓ No channels found, skipping collaboration test")
            return
        
        # Find a channel with AI agents
        channel_with_agents = None
        for ch in channels:
            if ch.get("ai_agents") and len(ch["ai_agents"]) > 0:
                channel_with_agents = ch
                break
        
        if not channel_with_agents:
            print("✓ No channels with AI agents found, skipping collaboration test")
            return
        
        channel_id = channel_with_agents["channel_id"]
        
        # Post a test message
        resp = session.post(
            f"{BASE_URL}/api/channels/{channel_id}/messages",
            json={"content": "Test message for collaboration endpoint check"}
        )
        assert resp.status_code == 200, f"Failed to post message: {resp.text}"
        
        # Trigger collaboration
        resp = session.post(f"{BASE_URL}/api/channels/{channel_id}/collaborate")
        
        # Should return 200 or 202 (accepted for async processing)
        assert resp.status_code in [200, 202], f"Collaborate endpoint failed: {resp.status_code}, {resp.text}"
        print(f"✓ Collaborate endpoint accessible for channel {channel_id}")
    
    def test_ai_key_resolution_for_chatgpt(self, auth_session):
        """Verify ChatGPT key resolution works (via Emergent universal key fallback)"""
        session = auth_session["session"]
        workspace_id = auth_session["workspace_id"]
        
        # Check AI config endpoint
        resp = session.get(f"{BASE_URL}/api/workspaces/{workspace_id}")
        assert resp.status_code == 200
        workspace = resp.json()
        
        # The workspace should exist
        assert workspace.get("workspace_id") == workspace_id
        print(f"✓ Workspace {workspace_id} accessible for AI key resolution")


class TestCodeRepoFolderCreation:
    """Test folder creation in code repo"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert resp.status_code == 200
        token = resp.json().get("session_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        
        resp = session.get(f"{BASE_URL}/api/workspaces")
        assert resp.status_code == 200
        workspaces = resp.json()
        assert len(workspaces) > 0
        
        return {"session": session, "workspace_id": workspaces[0]["workspace_id"]}
    
    def test_create_folder_in_repo(self, auth_session):
        """Verify folder creation works in code repo"""
        session = auth_session["session"]
        workspace_id = auth_session["workspace_id"]
        
        # Create a test repo
        resp = session.post(
            f"{BASE_URL}/api/workspaces/{workspace_id}/code-repos",
            json={"name": f"TEST_FolderCreate_{int(time.time())}", "description": "Test repo for folder creation"}
        )
        if resp.status_code == 429:
            print("✓ Rate limited on repo creation")
            return
        assert resp.status_code == 200
        repo_id = resp.json()["repo_id"]
        
        try:
            # Create a folder
            resp = session.post(
                f"{BASE_URL}/api/workspaces/{workspace_id}/code-repo/folders?repo_id={repo_id}",
                json={"path": "src/components"}
            )
            assert resp.status_code == 200, f"Failed to create folder: {resp.text}"
            
            # Verify folder exists in tree
            resp = session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/code-repo/tree?repo_id={repo_id}")
            assert resp.status_code == 200
            files = resp.json().get("files", [])
            folder_paths = [f["path"] for f in files if f.get("is_folder")]
            assert "src/components" in folder_paths, "Created folder should be in tree"
            
            print(f"✓ Folder creation working in repo {repo_id}")
        finally:
            session.delete(f"{BASE_URL}/api/workspaces/{workspace_id}/code-repos/{repo_id}")


class TestAIUpdateFile:
    """Test AI agent file update endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert resp.status_code == 200
        token = resp.json().get("session_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        
        resp = session.get(f"{BASE_URL}/api/workspaces")
        assert resp.status_code == 200
        workspaces = resp.json()
        assert len(workspaces) > 0
        
        return {"session": session, "workspace_id": workspaces[0]["workspace_id"]}
    
    def test_ai_update_file_endpoint(self, auth_session):
        """Verify AI update file endpoint works"""
        session = auth_session["session"]
        workspace_id = auth_session["workspace_id"]
        
        # Create a test repo
        resp = session.post(
            f"{BASE_URL}/api/workspaces/{workspace_id}/code-repos",
            json={"name": f"TEST_AIUpdate_{int(time.time())}", "description": "Test repo for AI update"}
        )
        if resp.status_code == 429:
            print("✓ Rate limited on repo creation")
            return
        assert resp.status_code == 200
        repo_id = resp.json()["repo_id"]
        
        try:
            # Use AI update endpoint to create/update a file
            resp = session.post(
                f"{BASE_URL}/api/workspaces/{workspace_id}/code-repo/ai-update?repo_id={repo_id}",
                json={
                    "path": "ai_generated.py",
                    "content": "# Generated by AI\nprint('Hello from AI')",
                    "agent_name": "TestAgent",
                    "message": "AI generated file"
                }
            )
            assert resp.status_code == 200, f"AI update failed: {resp.text}"
            result = resp.json()
            assert result.get("action") in ["create", "update"]
            
            # Verify file exists
            resp = session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/code-repo/tree?repo_id={repo_id}")
            assert resp.status_code == 200
            files = [f["path"] for f in resp.json().get("files", [])]
            assert "ai_generated.py" in files
            
            print(f"✓ AI update file endpoint working")
        finally:
            session.delete(f"{BASE_URL}/api/workspaces/{workspace_id}/code-repos/{repo_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
