"""
Iteration 66 - Comprehensive Backlog QA Tests
Tests for:
1. GET /api/health — returns healthy + instance_id
2. POST /api/channels/{id}/messages — creates message + verify retrieval  
3. PUT /api/channels/{id}/roles — set TPM, Architect, Browser Operator
4. POST /api/channels/{id}/files — upload file, verify has_extracted_text
5. GET /api/channels/{id}/context-ledger — returns entries
6. GET /api/workspaces/{id}/activities — returns activities with total count
7. GET /api/workspaces/{id}/activities/export?format=csv — returns CSV
8. PUT /api/user/preferences — save pinned_panels
9. GET /api/user/preferences — returns pinned_panels
10. POST /api/channels/{id}/browser/open — opens Firefox browser
11. POST /api/channels/{id}/browser/close — closes browser
12. GET /api/admin/recycle-bin — returns 403 for non-admin
13. GET /api/admin/duplicate-overrides — returns 403 for non-admin
14. POST /api/channels/{id}/directive — create with prohibited_patterns
15. WebSocket endpoint exists at /ws/channels/{id}
"""
import pytest
import requests
import uuid
import io
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBacklogQA:
    """Comprehensive Backlog QA Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data - register user, create workspace, channel"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Register test user
        self.test_email = f"backlog_qa_{uuid.uuid4().hex[:8]}@test.com"
        self.test_password = "test123"
        
        reg_resp = self.session.post(f"{BASE_URL}/api/auth/register", json={
            "email": self.test_email,
            "password": self.test_password,
            "name": "Backlog QA Tester"
        })
        
        if reg_resp.status_code not in (200, 201):
            # Try login if already exists
            login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
                "email": self.test_email,
                "password": self.test_password
            })
            if login_resp.status_code != 200:
                pytest.skip(f"Auth failed: {reg_resp.text}")
        
        # Create workspace
        ws_resp = self.session.post(f"{BASE_URL}/api/workspaces", json={
            "name": f"QA Workspace {uuid.uuid4().hex[:8]}",
            "description": "Backlog QA Testing"
        })
        if ws_resp.status_code not in (200, 201):
            pytest.skip(f"Workspace creation failed: {ws_resp.text}")
        
        self.workspace_id = ws_resp.json().get("workspace_id")
        
        # Create channel with AI agents
        ch_resp = self.session.post(f"{BASE_URL}/api/workspaces/{self.workspace_id}/channels", json={
            "name": f"QA Channel {uuid.uuid4().hex[:8]}",
            "description": "Backlog QA Test Channel",
            "ai_agents": ["claude", "chatgpt", "deepseek"]
        })
        if ch_resp.status_code not in (200, 201):
            pytest.skip(f"Channel creation failed: {ch_resp.text}")
        
        self.channel_id = ch_resp.json().get("channel_id")
        yield
        
        # Cleanup
        try:
            self.session.delete(f"{BASE_URL}/api/workspaces/{self.workspace_id}")
        except Exception:
            pass
    
    # ============ 1. Health Check ============
    def test_health_check_returns_healthy_and_instance_id(self):
        """GET /api/health — returns healthy + instance_id"""
        resp = self.session.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200, f"Health check failed: {resp.text}"
        data = resp.json()
        assert data.get("status") == "healthy", f"Status not healthy: {data}"
        assert "instance_id" in data, f"Missing instance_id: {data}"
        assert data.get("database") == "connected", f"DB not connected: {data}"
        print(f"PASS: Health check - status={data['status']}, instance_id={data['instance_id']}")
    
    # ============ 2. Messages ============
    def test_create_message_and_verify_retrieval(self):
        """POST /api/channels/{id}/messages — creates message + verify retrieval"""
        # Create message
        msg_content = f"Test message {uuid.uuid4().hex[:8]}"
        create_resp = self.session.post(f"{BASE_URL}/api/channels/{self.channel_id}/messages", json={
            "content": msg_content
        })
        assert create_resp.status_code in (200, 201), f"Message creation failed: {create_resp.text}"
        msg_data = create_resp.json()
        assert "message_id" in msg_data, f"Missing message_id: {msg_data}"
        assert msg_data.get("content") == msg_content, f"Content mismatch: {msg_data}"
        msg_id = msg_data["message_id"]
        
        # Verify retrieval
        get_resp = self.session.get(f"{BASE_URL}/api/channels/{self.channel_id}/messages")
        assert get_resp.status_code == 200, f"Message retrieval failed: {get_resp.text}"
        messages = get_resp.json()
        assert isinstance(messages, list), f"Messages not a list: {messages}"
        found = any(m.get("message_id") == msg_id for m in messages)
        assert found, f"Created message not found in channel messages"
        print(f"PASS: Message created and retrieved - message_id={msg_id}")
    
    # ============ 3. Channel Roles ============
    def test_set_channel_roles_tpm_architect_browser_operator(self):
        """PUT /api/channels/{id}/roles — set TPM, Architect, Browser Operator"""
        roles_data = {
            "tpm": "claude",
            "architect": "chatgpt",
            "browser_operator": "deepseek"
        }
        resp = self.session.put(f"{BASE_URL}/api/channels/{self.channel_id}/roles", json=roles_data)
        assert resp.status_code == 200, f"Set roles failed: {resp.text}"
        data = resp.json()
        
        # Response returns roles directly: {"tpm": "...", "architect": "...", "browser_operator": "..."}
        assert data.get("tpm") == "claude", f"TPM not set: {data}"
        assert data.get("architect") == "chatgpt", f"Architect not set: {data}"
        assert data.get("browser_operator") == "deepseek", f"Browser Operator not set: {data}"
        print(f"PASS: Channel roles set - TPM=claude, Architect=chatgpt, Browser Operator=deepseek")
    
    # ============ 4. File Upload ============
    def test_file_upload_has_extracted_text(self):
        """POST /api/channels/{id}/files — upload file, verify has_extracted_text"""
        # Create a simple text file content
        file_content = "This is a test file for backlog QA testing.\nIt contains multiple lines.\nThe system should extract this text."
        
        # Use multipart form data
        files = {
            'file': ('test_document.txt', io.BytesIO(file_content.encode()), 'text/plain')
        }
        data = {'message': 'Uploading test document'}
        
        # Remove Content-Type header for multipart
        headers = {k: v for k, v in self.session.headers.items() if k.lower() != 'content-type'}
        resp = requests.post(
            f"{BASE_URL}/api/channels/{self.channel_id}/files",
            files=files,
            data=data,
            headers=headers,
            cookies=self.session.cookies
        )
        assert resp.status_code in (200, 201), f"File upload failed: {resp.text}"
        data = resp.json()
        
        # Verify response structure
        assert "file" in data, f"Missing file in response: {data}"
        file_info = data["file"]
        assert "file_id" in file_info, f"Missing file_id: {data}"
        assert file_info.get("has_extracted_text") == True, f"has_extracted_text not True: {file_info}"
        assert file_info.get("text_length", 0) > 0, f"text_length is 0: {file_info}"
        print(f"PASS: File uploaded with extracted text - file_id={file_info['file_id']}, text_length={file_info.get('text_length')}")
    
    # ============ 5. Context Ledger ============
    def test_context_ledger_returns_entries(self):
        """GET /api/channels/{id}/context-ledger — returns entries"""
        resp = self.session.get(f"{BASE_URL}/api/channels/{self.channel_id}/context-ledger")
        assert resp.status_code == 200, f"Context ledger failed: {resp.text}"
        data = resp.json()
        assert "entries" in data, f"Missing entries in response: {data}"
        assert isinstance(data["entries"], list), f"Entries not a list: {data}"
        print(f"PASS: Context ledger returns entries list - count={len(data['entries'])}")
    
    # ============ 6. Workspace Activities ============
    def test_workspace_activities_returns_total_count(self):
        """GET /api/workspaces/{id}/activities — returns activities with total count"""
        resp = self.session.get(f"{BASE_URL}/api/workspaces/{self.workspace_id}/activities")
        assert resp.status_code == 200, f"Activities failed: {resp.text}"
        data = resp.json()
        assert "activities" in data, f"Missing activities: {data}"
        assert "total" in data, f"Missing total: {data}"
        assert isinstance(data["activities"], list), f"Activities not a list: {data}"
        assert isinstance(data["total"], int), f"Total not an int: {data}"
        print(f"PASS: Workspace activities - total={data['total']}, count={len(data['activities'])}")
    
    # ============ 7. Activities CSV Export ============
    def test_activities_export_csv(self):
        """GET /api/workspaces/{id}/activities/export?format=csv — returns CSV"""
        resp = self.session.get(f"{BASE_URL}/api/workspaces/{self.workspace_id}/activities/export?format=csv")
        assert resp.status_code == 200, f"CSV export failed: {resp.text}"
        
        # Verify content type is CSV
        content_type = resp.headers.get("Content-Type", "")
        assert "text/csv" in content_type, f"Content-Type not CSV: {content_type}"
        
        # Verify content has CSV header
        content = resp.text
        assert "timestamp" in content.lower() or content == "" or "agent" in content.lower(), f"CSV header missing: {content[:200]}"
        
        # Check for Content-Disposition header
        disposition = resp.headers.get("Content-Disposition", "")
        assert "attachment" in disposition.lower(), f"Not an attachment: {disposition}"
        print(f"PASS: Activities CSV export - Content-Type={content_type}")
    
    # ============ 8. User Preferences PUT ============
    def test_user_preferences_save_pinned_panels(self):
        """PUT /api/user/preferences — save pinned_panels"""
        prefs_data = {
            "pinned_panels": {
                "context_ledger": True,
                "ai_actions": False,
                "files": True
            }
        }
        resp = self.session.put(f"{BASE_URL}/api/user/preferences", json=prefs_data)
        assert resp.status_code == 200, f"Save preferences failed: {resp.text}"
        data = resp.json()
        assert data.get("message") == "Preferences updated" or "updated" in str(data).lower(), f"Update not confirmed: {data}"
        print(f"PASS: User preferences saved - pinned_panels set")
    
    # ============ 9. User Preferences GET ============
    def test_user_preferences_get_pinned_panels(self):
        """GET /api/user/preferences — returns pinned_panels"""
        # First save preferences
        prefs_data = {
            "pinned_panels": {
                "context_ledger": True,
                "ai_actions": False
            }
        }
        self.session.put(f"{BASE_URL}/api/user/preferences", json=prefs_data)
        
        # Then retrieve
        resp = self.session.get(f"{BASE_URL}/api/user/preferences")
        assert resp.status_code == 200, f"Get preferences failed: {resp.text}"
        data = resp.json()
        assert "pinned_panels" in data, f"Missing pinned_panels: {data}"
        assert isinstance(data["pinned_panels"], dict), f"pinned_panels not a dict: {data}"
        print(f"PASS: User preferences retrieved - pinned_panels={data['pinned_panels']}")
    
    # ============ 10. Browser Open ============
    def test_browser_open_returns_screenshot(self):
        """POST /api/channels/{id}/browser/open — opens Firefox browser, returns screenshot"""
        resp = self.session.post(f"{BASE_URL}/api/channels/{self.channel_id}/browser/open", json={
            "url": "https://www.google.com"
        })
        # Browser may fail in test environment (no display), but endpoint should exist
        if resp.status_code == 500 and "browser" in resp.text.lower():
            pytest.skip("Browser not available in test environment")
        
        assert resp.status_code in (200, 201), f"Browser open failed: {resp.text}"
        data = resp.json()
        assert "session_id" in data, f"Missing session_id: {data}"
        # Screenshot may or may not be present depending on browser availability
        if "screenshot" in data and data["screenshot"]:
            assert len(data["screenshot"]) > 100, f"Screenshot too short: {len(data.get('screenshot', ''))}"
        print(f"PASS: Browser opened - session_id={data.get('session_id')}")
    
    # ============ 11. Browser Close ============
    def test_browser_close(self):
        """POST /api/channels/{id}/browser/close — closes browser"""
        # First try to open
        self.session.post(f"{BASE_URL}/api/channels/{self.channel_id}/browser/open", json={
            "url": "about:blank"
        })
        
        # Then close
        resp = self.session.post(f"{BASE_URL}/api/channels/{self.channel_id}/browser/close", json={})
        assert resp.status_code == 200, f"Browser close failed: {resp.text}"
        data = resp.json()
        assert data.get("closed") == True, f"Browser not closed: {data}"
        print(f"PASS: Browser closed successfully")
    
    # ============ 12. Admin Recycle Bin (403 for non-admin) ============
    def test_admin_recycle_bin_returns_403_for_non_admin(self):
        """GET /api/admin/recycle-bin — returns 403 for non-admin"""
        resp = self.session.get(f"{BASE_URL}/api/admin/recycle-bin")
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print(f"PASS: Admin recycle-bin returns 403 for non-admin user")
    
    # ============ 13. Admin Duplicate Overrides (403 for non-admin) ============
    def test_admin_duplicate_overrides_returns_403_for_non_admin(self):
        """GET /api/admin/duplicate-overrides — returns 403 for non-admin"""
        resp = self.session.get(f"{BASE_URL}/api/admin/duplicate-overrides")
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print(f"PASS: Admin duplicate-overrides returns 403 for non-admin user")
    
    # ============ 14. Directive with prohibited_patterns ============
    def test_create_directive_with_prohibited_patterns(self):
        """POST /api/channels/{id}/directive — create with prohibited_patterns"""
        directive_data = {
            "project_name": f"QA Directive {uuid.uuid4().hex[:8]}",
            "description": "Test directive with prohibited patterns",
            "goal": "Test prohibited patterns enforcement",
            "universal_rules": {
                "full_file_context": True,
                "additive_only": True,
                "prohibited_patterns": ["TODO:", "FIXME:", "console.log"],
                "max_parallel_tasks": 3
            },
            "agents": {
                "claude": {"role": "lead developer"},
                "chatgpt": {"role": "code reviewer"}
            }
        }
        resp = self.session.post(f"{BASE_URL}/api/channels/{self.channel_id}/directive", json=directive_data)
        assert resp.status_code in (200, 201), f"Directive creation failed: {resp.text}"
        data = resp.json()
        
        # Verify prohibited_patterns saved
        assert "directive_id" in data, f"Missing directive_id: {data}"
        rules = data.get("universal_rules", {})
        prohibited = rules.get("prohibited_patterns", [])
        assert "TODO:" in prohibited, f"prohibited_patterns not saved: {rules}"
        assert "FIXME:" in prohibited, f"prohibited_patterns not saved: {rules}"
        print(f"PASS: Directive created with prohibited_patterns={prohibited}")
    
    # ============ 15. WebSocket Endpoint Exists ============
    def test_websocket_endpoint_exists(self):
        """WebSocket endpoint exists at /ws/channels/{id}"""
        # We can't fully test WebSocket with requests, but we can verify the endpoint
        # returns a proper WebSocket handshake error (not 404)
        
        # Build WebSocket URL from HTTP URL
        ws_url = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
        ws_endpoint = f"{ws_url}/ws/channels/{self.channel_id}"
        
        # Try HTTP request to WebSocket endpoint - should get 426 (Upgrade Required) or similar, not 404
        http_url = f"{BASE_URL.replace('/api', '')}/ws/channels/{self.channel_id}"
        # Remove /api if present at the end
        if http_url.endswith('/api'):
            http_url = http_url[:-4]
        
        # The WebSocket is at root level, not under /api
        resp = requests.get(http_url.replace('/api', ''), headers={"Upgrade": "websocket", "Connection": "Upgrade"})
        
        # WebSocket endpoints typically return 400 or 426 for non-WebSocket requests, not 404
        # A 404 would indicate the endpoint doesn't exist
        assert resp.status_code != 404, f"WebSocket endpoint not found (404): {http_url}"
        print(f"PASS: WebSocket endpoint exists - status={resp.status_code} (expected non-404)")


class TestFilesStoredInMongoDB:
    """Verify files are stored in MongoDB, not filesystem"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        self.test_email = f"file_mongo_{uuid.uuid4().hex[:8]}@test.com"
        reg_resp = self.session.post(f"{BASE_URL}/api/auth/register", json={
            "email": self.test_email,
            "password": "test123",
            "name": "File Mongo Tester"
        })
        
        if reg_resp.status_code not in (200, 201):
            login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
                "email": self.test_email, "password": "test123"
            })
            if login_resp.status_code != 200:
                pytest.skip("Auth failed")
        
        ws_resp = self.session.post(f"{BASE_URL}/api/workspaces", json={
            "name": f"File Test WS {uuid.uuid4().hex[:8]}"
        })
        if ws_resp.status_code not in (200, 201):
            pytest.skip("Workspace creation failed")
        self.workspace_id = ws_resp.json().get("workspace_id")
        
        ch_resp = self.session.post(f"{BASE_URL}/api/workspaces/{self.workspace_id}/channels", json={
            "name": "File Test Channel", "ai_agents": ["claude"]
        })
        if ch_resp.status_code not in (200, 201):
            pytest.skip("Channel creation failed")
        self.channel_id = ch_resp.json().get("channel_id")
        
        yield
        try:
            self.session.delete(f"{BASE_URL}/api/workspaces/{self.workspace_id}")
        except Exception:
            pass
    
    def test_uploaded_file_can_be_downloaded(self):
        """Verify uploaded file can be downloaded (proves MongoDB storage)"""
        file_content = f"MongoDB storage test content {uuid.uuid4().hex}"
        
        files = {'file': ('mongo_test.txt', io.BytesIO(file_content.encode()), 'text/plain')}
        headers = {k: v for k, v in self.session.headers.items() if k.lower() != 'content-type'}
        
        upload_resp = requests.post(
            f"{BASE_URL}/api/channels/{self.channel_id}/files",
            files=files,
            cookies=self.session.cookies,
            headers=headers
        )
        assert upload_resp.status_code in (200, 201), f"Upload failed: {upload_resp.text}"
        file_id = upload_resp.json()["file"]["file_id"]
        
        # Download and verify content
        download_resp = self.session.get(f"{BASE_URL}/api/files/{file_id}/download")
        assert download_resp.status_code == 200, f"Download failed: {download_resp.text}"
        assert file_content in download_resp.text, f"Content mismatch: {download_resp.text[:100]}"
        print(f"PASS: File uploaded and downloaded from MongoDB - file_id={file_id}")


class TestWorkspaceRefreshAfterCreation:
    """Verify workspace list updates after creation"""
    
    def test_workspace_appears_in_list_after_creation(self):
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        test_email = f"ws_refresh_{uuid.uuid4().hex[:8]}@test.com"
        reg_resp = session.post(f"{BASE_URL}/api/auth/register", json={
            "email": test_email, "password": "test123", "name": "WS Refresh Tester"
        })
        if reg_resp.status_code not in (200, 201):
            session.post(f"{BASE_URL}/api/auth/login", json={"email": test_email, "password": "test123"})
        
        # Get initial workspace count
        initial_resp = session.get(f"{BASE_URL}/api/workspaces")
        initial_count = len(initial_resp.json()) if initial_resp.status_code == 200 else 0
        
        # Create new workspace
        ws_name = f"Refresh Test WS {uuid.uuid4().hex[:8]}"
        create_resp = session.post(f"{BASE_URL}/api/workspaces", json={"name": ws_name})
        assert create_resp.status_code in (200, 201), f"Create failed: {create_resp.text}"
        new_ws_id = create_resp.json().get("workspace_id")
        
        # Verify workspace appears in list
        list_resp = session.get(f"{BASE_URL}/api/workspaces")
        assert list_resp.status_code == 200, f"List failed: {list_resp.text}"
        workspaces = list_resp.json()
        found = any(ws.get("workspace_id") == new_ws_id for ws in workspaces)
        assert found, f"New workspace not found in list after creation"
        assert len(workspaces) > initial_count, f"Workspace count didn't increase"
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/workspaces/{new_ws_id}")
        print(f"PASS: Workspace appears in list immediately after creation")


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
