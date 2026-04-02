"""
Test suite for Code Repository API - Per-workspace code repo with file tree, versioning, and linking
Tests: Create file, Create folder, Get file tree, Get file content, Update file, Delete file, Rename file,
       Get history, Get commit detail, AI update file, Create link, Get links, Delete link
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "test@test.com"
TEST_PASSWORD = "test123"
TEST_WORKSPACE_ID = "ws_f6ec6355bb18"


@pytest.fixture(scope="session")
def auth_session():
    """Get authenticated session via email login - returns session with cookies"""
    session = requests.Session()
    response = session.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    if response.status_code != 200:
        pytest.skip(f"Login failed: {response.status_code} - {response.text}")
    
    # Get session token from cookies
    session_token = session.cookies.get("session_token")
    if not session_token:
        pytest.skip("No session token cookie returned")
    
    print(f"Auth successful: session_token={session_token[:20]}...")
    return session, session_token


@pytest.fixture(scope="session")
def auth_headers(auth_session):
    """Return authorization headers using session token"""
    session, token = auth_session
    return {"Authorization": f"Bearer {token}"}


# ============ Repository Meta Tests ============

class TestRepoMeta:
    """Test repo metadata endpoints"""
    
    def test_get_repo_creates_if_not_exists(self, auth_headers):
        """GET /api/workspaces/{workspace_id}/code-repo - Creates repo if not exists"""
        response = requests.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "repo_id" in data
        assert data["workspace_id"] == TEST_WORKSPACE_ID
        assert "file_count" in data
        print(f"PASS: Repo meta fetched - repo_id={data['repo_id']}, file_count={data['file_count']}")

    def test_get_repo_unauthorized(self):
        """GET /api/workspaces/{workspace_id}/code-repo without auth - Returns 401"""
        response = requests.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo")
        assert response.status_code == 401
        print("PASS: Repo meta unauthorized returns 401")


# ============ File Tree Tests ============

class TestFileTree:
    """Test file tree endpoint"""
    
    def test_get_file_tree(self, auth_headers):
        """GET /api/workspaces/{workspace_id}/code-repo/tree - Get file tree"""
        response = requests.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/tree",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert isinstance(data["files"], list)
        print(f"PASS: File tree fetched - {len(data['files'])} items")
        # Print file structure
        for f in data["files"][:10]:
            print(f"  - {f['path']} ({'folder' if f.get('is_folder') else f.get('language', 'file')})")

    def test_get_file_tree_unauthorized(self):
        """GET /api/workspaces/{workspace_id}/code-repo/tree without auth - Returns 401"""
        response = requests.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/tree")
        assert response.status_code == 401
        print("PASS: File tree unauthorized returns 401")


# ============ File CRUD Tests ============

class TestFileCRUD:
    """Test file create, read, update, delete operations"""
    
    def test_create_file(self, auth_headers):
        """POST /api/workspaces/{workspace_id}/code-repo/files - Create a new file"""
        unique_path = f"TEST_file_{uuid.uuid4().hex[:8]}.py"
        response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files",
            headers=auth_headers,
            json={
                "path": unique_path,
                "content": "# Test file\nprint('Hello, World!')",
                "language": "python"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "file_id" in data
        assert data["path"] == unique_path
        assert data["language"] == "python"
        assert data["version"] == 1
        assert data["is_folder"] == False
        print(f"PASS: File created - file_id={data['file_id']}, path={data['path']}")
        return data["file_id"]

    def test_create_file_detects_language(self, auth_headers):
        """POST /api/workspaces/{workspace_id}/code-repo/files - Auto-detect language from extension"""
        unique_path = f"TEST_auto_{uuid.uuid4().hex[:8]}.js"
        response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files",
            headers=auth_headers,
            json={"path": unique_path, "content": "const x = 1;"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["language"] == "javascript", f"Expected javascript, got {data['language']}"
        print(f"PASS: Language auto-detected as {data['language']}")
        # Cleanup
        requests.delete(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/{data['file_id']}", headers=auth_headers)

    def test_create_file_duplicate_path(self, auth_headers):
        """POST /api/workspaces/{workspace_id}/code-repo/files with duplicate path - Returns 409"""
        unique_path = f"TEST_dup_{uuid.uuid4().hex[:8]}.txt"
        # Create first file
        response1 = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files",
            headers=auth_headers,
            json={"path": unique_path, "content": "first"}
        )
        assert response1.status_code == 200
        file_id = response1.json()["file_id"]
        
        # Try to create duplicate
        response2 = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files",
            headers=auth_headers,
            json={"path": unique_path, "content": "second"}
        )
        assert response2.status_code == 409, f"Expected 409 for duplicate, got {response2.status_code}"
        print("PASS: Duplicate file creation returns 409")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/{file_id}", headers=auth_headers)

    def test_get_file_content(self, auth_headers):
        """GET /api/workspaces/{workspace_id}/code-repo/files/{file_id} - Get file content"""
        # First create a file
        unique_path = f"TEST_get_{uuid.uuid4().hex[:8]}.py"
        test_content = "def hello():\n    return 'world'"
        create_response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files",
            headers=auth_headers,
            json={"path": unique_path, "content": test_content}
        )
        file_id = create_response.json()["file_id"]
        
        # Now fetch it
        response = requests.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/{file_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["file_id"] == file_id
        assert data["content"] == test_content
        assert data["path"] == unique_path
        print(f"PASS: File content fetched - {len(data['content'])} bytes")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/{file_id}", headers=auth_headers)

    def test_get_file_not_found(self, auth_headers):
        """GET /api/workspaces/{workspace_id}/code-repo/files/{bad_id} - Returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/rf_nonexistent123",
            headers=auth_headers
        )
        assert response.status_code == 404
        print("PASS: Non-existent file returns 404")

    def test_update_file(self, auth_headers):
        """PUT /api/workspaces/{workspace_id}/code-repo/files/{file_id} - Update file content"""
        # Create file
        unique_path = f"TEST_upd_{uuid.uuid4().hex[:8]}.py"
        create_response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files",
            headers=auth_headers,
            json={"path": unique_path, "content": "v1"}
        )
        file_id = create_response.json()["file_id"]
        
        # Update it
        new_content = "# Version 2\nprint('updated!')"
        response = requests.put(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/{file_id}",
            headers=auth_headers,
            json={"content": new_content, "message": "Update to v2"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == 2
        assert "commit_id" in data
        print(f"PASS: File updated - version={data['version']}, commit_id={data['commit_id']}")
        
        # Verify update persisted
        get_response = requests.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/{file_id}",
            headers=auth_headers
        )
        assert get_response.json()["content"] == new_content
        print("PASS: Updated content persisted correctly")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/{file_id}", headers=auth_headers)

    def test_delete_file(self, auth_headers):
        """DELETE /api/workspaces/{workspace_id}/code-repo/files/{file_id} - Delete file"""
        # Create file
        unique_path = f"TEST_del_{uuid.uuid4().hex[:8]}.py"
        create_response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files",
            headers=auth_headers,
            json={"path": unique_path, "content": "to delete"}
        )
        file_id = create_response.json()["file_id"]
        
        # Delete it
        response = requests.delete(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/{file_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json().get("deleted") == True
        print(f"PASS: File deleted - file_id={file_id}")
        
        # Verify it's gone
        get_response = requests.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/{file_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 404
        print("PASS: Deleted file returns 404")

    def test_rename_file(self, auth_headers):
        """PATCH /api/workspaces/{workspace_id}/code-repo/files/{file_id} - Rename/move file"""
        # Create file
        old_path = f"TEST_rename_{uuid.uuid4().hex[:8]}.py"
        create_response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files",
            headers=auth_headers,
            json={"path": old_path, "content": "to rename"}
        )
        file_id = create_response.json()["file_id"]
        
        # Rename it
        new_path = f"TEST_renamed_{uuid.uuid4().hex[:8]}.py"
        response = requests.patch(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/{file_id}",
            headers=auth_headers,
            json={"path": new_path}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["path"] == new_path
        assert data["name"] == new_path  # No directory, so name == path
        print(f"PASS: File renamed from {old_path} to {new_path}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/{file_id}", headers=auth_headers)

    def test_rename_file_missing_path(self, auth_headers):
        """PATCH /api/workspaces/{workspace_id}/code-repo/files/{file_id} without path - Returns 400"""
        # Create file
        unique_path = f"TEST_ren_err_{uuid.uuid4().hex[:8]}.py"
        create_response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files",
            headers=auth_headers,
            json={"path": unique_path, "content": "test"}
        )
        file_id = create_response.json()["file_id"]
        
        # Try to rename without path
        response = requests.patch(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/{file_id}",
            headers=auth_headers,
            json={}
        )
        assert response.status_code == 400
        print("PASS: Rename without path returns 400")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/{file_id}", headers=auth_headers)


# ============ Folder Tests ============

class TestFolderCRUD:
    """Test folder creation and management"""
    
    def test_create_folder(self, auth_headers):
        """POST /api/workspaces/{workspace_id}/code-repo/folders - Create a new folder"""
        unique_path = f"TEST_folder_{uuid.uuid4().hex[:8]}"
        response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/folders",
            headers=auth_headers,
            json={"path": unique_path}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_folder"] == True
        assert data["path"] == unique_path
        print(f"PASS: Folder created - file_id={data['file_id']}, path={data['path']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/{data['file_id']}", headers=auth_headers)

    def test_create_nested_folder(self, auth_headers):
        """POST /api/workspaces/{workspace_id}/code-repo/folders - Create nested folder"""
        unique_path = f"TEST_parent_{uuid.uuid4().hex[:8]}/child"
        response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/folders",
            headers=auth_headers,
            json={"path": unique_path}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "child"
        print(f"PASS: Nested folder created - path={unique_path}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/{data['file_id']}", headers=auth_headers)

    def test_create_duplicate_folder(self, auth_headers):
        """POST /api/workspaces/{workspace_id}/code-repo/folders with duplicate - Returns 409"""
        unique_path = f"TEST_dupfolder_{uuid.uuid4().hex[:8]}"
        # Create first
        response1 = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/folders",
            headers=auth_headers,
            json={"path": unique_path}
        )
        file_id = response1.json()["file_id"]
        
        # Try duplicate
        response2 = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/folders",
            headers=auth_headers,
            json={"path": unique_path}
        )
        assert response2.status_code == 409
        print("PASS: Duplicate folder returns 409")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/{file_id}", headers=auth_headers)


# ============ Version History Tests ============

class TestVersionHistory:
    """Test version history and commit endpoints"""
    
    def test_get_repo_history(self, auth_headers):
        """GET /api/workspaces/{workspace_id}/code-repo/history - Get commit history"""
        response = requests.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/history",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "commits" in data
        assert isinstance(data["commits"], list)
        print(f"PASS: History fetched - {len(data['commits'])} commits")
        if data["commits"]:
            c = data["commits"][0]
            print(f"  Latest: {c.get('action')} - {c.get('file_path')} by {c.get('author_name')}")

    def test_get_file_history(self, auth_headers):
        """GET /api/workspaces/{workspace_id}/code-repo/history?file_id=X - Get file-specific history"""
        # Create a file
        unique_path = f"TEST_hist_{uuid.uuid4().hex[:8]}.py"
        create_response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files",
            headers=auth_headers,
            json={"path": unique_path, "content": "v1"}
        )
        file_id = create_response.json()["file_id"]
        
        # Update it to create more commits
        requests.put(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/{file_id}",
            headers=auth_headers,
            json={"content": "v2", "message": "Second version"}
        )
        
        # Get file-specific history
        response = requests.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/history?file_id={file_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["commits"]) >= 2, f"Expected at least 2 commits, got {len(data['commits'])}"
        # All commits should be for this file
        for c in data["commits"]:
            assert c["file_id"] == file_id
        print(f"PASS: File history fetched - {len(data['commits'])} commits for file")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/{file_id}", headers=auth_headers)

    def test_get_commit_detail(self, auth_headers):
        """GET /api/workspaces/{workspace_id}/code-repo/commits/{commit_id} - Get commit with diff"""
        # Create and update a file to get a commit
        unique_path = f"TEST_commit_{uuid.uuid4().hex[:8]}.py"
        create_response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files",
            headers=auth_headers,
            json={"path": unique_path, "content": "original"}
        )
        file_id = create_response.json()["file_id"]
        
        update_response = requests.put(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/{file_id}",
            headers=auth_headers,
            json={"content": "updated", "message": "Test update"}
        )
        commit_id = update_response.json()["commit_id"]
        
        # Get commit detail
        response = requests.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/commits/{commit_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["commit_id"] == commit_id
        assert "content_before" in data
        assert "content_after" in data
        assert data["content_before"] == "original"
        assert data["content_after"] == "updated"
        print(f"PASS: Commit detail fetched - action={data['action']}, has diff")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/{file_id}", headers=auth_headers)

    def test_get_commit_not_found(self, auth_headers):
        """GET /api/workspaces/{workspace_id}/code-repo/commits/{bad_id} - Returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/commits/rc_nonexistent123",
            headers=auth_headers
        )
        assert response.status_code == 404
        print("PASS: Non-existent commit returns 404")


# ============ AI Update Tests ============

class TestAIUpdate:
    """Test AI agent file update endpoint"""
    
    def test_ai_create_file(self, auth_headers):
        """POST /api/workspaces/{workspace_id}/code-repo/ai-update - AI creates new file"""
        unique_path = f"TEST_ai_create_{uuid.uuid4().hex[:8]}.py"
        response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/ai-update",
            headers=auth_headers,
            json={
                "path": unique_path,
                "content": "# Generated by AI\nprint('Hello from AI!')",
                "agent_name": "Claude",
                "message": "AI created test file"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "create"
        assert data["version"] == 1
        assert "commit_id" in data
        print(f"PASS: AI created file - file_id={data['file_id']}, action={data['action']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/{data['file_id']}", headers=auth_headers)

    def test_ai_update_existing_file(self, auth_headers):
        """POST /api/workspaces/{workspace_id}/code-repo/ai-update - AI updates existing file"""
        # Create file first
        unique_path = f"TEST_ai_upd_{uuid.uuid4().hex[:8]}.py"
        create_response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files",
            headers=auth_headers,
            json={"path": unique_path, "content": "original"}
        )
        file_id = create_response.json()["file_id"]
        
        # AI updates it
        response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/ai-update",
            headers=auth_headers,
            json={
                "path": unique_path,
                "content": "# Updated by AI\nprint('AI updated this!')",
                "agent_name": "Gemini",
                "message": "AI improved the code"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "update"
        assert data["version"] == 2
        assert data["file_id"] == file_id
        print(f"PASS: AI updated file - action={data['action']}, version={data['version']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/{file_id}", headers=auth_headers)

    def test_ai_update_missing_path(self, auth_headers):
        """POST /api/workspaces/{workspace_id}/code-repo/ai-update without path - Returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/ai-update",
            headers=auth_headers,
            json={"content": "no path", "agent_name": "Test"}
        )
        assert response.status_code == 400
        print("PASS: AI update without path returns 400")


# ============ Linking Tests ============

class TestRepoLinks:
    """Test repository linking to channels/projects/tasks"""
    
    def test_create_channel_link(self, auth_headers):
        """POST /api/workspaces/{workspace_id}/code-repo/links - Link repo to channel"""
        # Get a channel from the workspace first
        channels_response = requests.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/channels",
            headers=auth_headers
        )
        channels = channels_response.json()
        if not channels:
            pytest.skip("No channels in workspace to link")
        
        channel_id = channels[0]["channel_id"]
        
        response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/links",
            headers=auth_headers,
            json={"target_type": "channel", "target_id": channel_id}
        )
        # May return 409 if already linked
        assert response.status_code in [200, 409]
        if response.status_code == 200:
            data = response.json()
            assert data["target_type"] == "channel"
            assert data["target_id"] == channel_id
            print(f"PASS: Channel link created - link_id={data['link_id']}")
        else:
            print("PASS: Channel already linked (409)")

    def test_get_links(self, auth_headers):
        """GET /api/workspaces/{workspace_id}/code-repo/links - Get all links"""
        response = requests.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/links",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "links" in data
        assert isinstance(data["links"], list)
        print(f"PASS: Links fetched - {len(data['links'])} links")
        for link in data["links"]:
            print(f"  - {link['target_type']}: {link.get('target_name') or link['target_id']}")

    def test_create_and_delete_link(self, auth_headers):
        """Create and delete a test link"""
        # Create a unique link to a fake task
        fake_task_id = f"task_{uuid.uuid4().hex[:12]}"
        create_response = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/links",
            headers=auth_headers,
            json={"target_type": "task", "target_id": fake_task_id}
        )
        assert create_response.status_code == 200
        link_id = create_response.json()["link_id"]
        print(f"PASS: Test link created - link_id={link_id}")
        
        # Delete it
        delete_response = requests.delete(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/links/{link_id}",
            headers=auth_headers
        )
        assert delete_response.status_code == 200
        assert delete_response.json().get("deleted") == True
        print("PASS: Test link deleted")

    def test_delete_link_not_found(self, auth_headers):
        """DELETE /api/workspaces/{workspace_id}/code-repo/links/{bad_id} - Returns 404"""
        response = requests.delete(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/links/rl_nonexistent123",
            headers=auth_headers
        )
        assert response.status_code == 404
        print("PASS: Non-existent link deletion returns 404")

    def test_duplicate_link(self, auth_headers):
        """POST /api/workspaces/{workspace_id}/code-repo/links duplicate - Returns 409"""
        fake_task_id = f"task_dup_{uuid.uuid4().hex[:8]}"
        
        # Create first link
        response1 = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/links",
            headers=auth_headers,
            json={"target_type": "task", "target_id": fake_task_id}
        )
        assert response1.status_code == 200
        link_id = response1.json()["link_id"]
        
        # Try duplicate
        response2 = requests.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/links",
            headers=auth_headers,
            json={"target_type": "task", "target_id": fake_task_id}
        )
        assert response2.status_code == 409
        print("PASS: Duplicate link returns 409")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/links/{link_id}", headers=auth_headers)


# ============ Authorization Tests ============

class TestAuthorization:
    """Test that all endpoints require authentication"""
    
    def test_all_endpoints_require_auth(self):
        """All code repo endpoints should return 401 without auth (or 422 for validation errors on POST)"""
        endpoints = [
            ("GET", f"/api/workspaces/{TEST_WORKSPACE_ID}/code-repo"),
            ("GET", f"/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/tree"),
            ("POST", f"/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files"),
            ("POST", f"/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/folders"),
            ("GET", f"/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/rf_test"),
            ("PUT", f"/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/rf_test"),
            ("DELETE", f"/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/rf_test"),
            ("PATCH", f"/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/rf_test"),
            ("GET", f"/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/history"),
            ("GET", f"/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/commits/rc_test"),
            ("POST", f"/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/ai-update"),
            ("POST", f"/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/links"),
            ("GET", f"/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/links"),
            ("DELETE", f"/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/links/rl_test"),
        ]
        
        failed = []
        for method, endpoint in endpoints:
            if method == "GET":
                response = requests.get(f"{BASE_URL}{endpoint}")
            elif method == "POST":
                response = requests.post(f"{BASE_URL}{endpoint}", json={})
            elif method == "PUT":
                response = requests.put(f"{BASE_URL}{endpoint}", json={})
            elif method == "DELETE":
                response = requests.delete(f"{BASE_URL}{endpoint}")
            elif method == "PATCH":
                response = requests.patch(f"{BASE_URL}{endpoint}", json={})
            
            # 401 = no auth, 422 = validation error before auth check (acceptable for POST with empty body)
            # Both indicate the endpoint doesn't grant access
            expected = [401]
            if method == "POST":
                expected.append(422)  # Pydantic validation may run before auth check
            
            if response.status_code not in expected:
                failed.append(f"{method} {endpoint} returned {response.status_code}")
        
        if failed:
            print(f"FAIL: {len(failed)} endpoints don't require auth:\n  " + "\n  ".join(failed))
            assert False, f"Some endpoints don't require auth: {failed}"
        
        print(f"PASS: All {len(endpoints)} endpoints protected (401 or 422)")


# ============ Cleanup Test Data ============

class TestCleanup:
    """Clean up test data created during tests"""
    
    def test_cleanup_test_files(self, auth_headers):
        """Remove all TEST_ prefixed files"""
        # Get all files
        response = requests.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/tree",
            headers=auth_headers
        )
        if response.status_code != 200:
            return
        
        files = response.json().get("files", [])
        deleted = 0
        for f in files:
            if f["path"].startswith("TEST_"):
                del_response = requests.delete(
                    f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/code-repo/files/{f['file_id']}",
                    headers=auth_headers
                )
                if del_response.status_code == 200:
                    deleted += 1
        
        print(f"CLEANUP: Deleted {deleted} test files")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
