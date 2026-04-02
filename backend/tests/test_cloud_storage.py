"""
Cloud Storage Connectors Tests - Google Drive, OneDrive, Dropbox
Testing: Providers listing, connection CRUD, OAuth flows (501 when keys not configured)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestCloudStorageProviders:
    """Test cloud storage providers endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as test user
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testmention@test.com",
            "password": "Test1234!"
        })
        if login_resp.status_code == 200:
            self.token = login_resp.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Login failed - skipping tests")
    
    def test_get_providers_returns_three_providers(self):
        """GET /api/cloud-storage/providers — returns 3 providers"""
        resp = self.session.get(f"{BASE_URL}/api/cloud-storage/providers")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "providers" in data, "Response should have 'providers' key"
        providers = data["providers"]
        
        # Should have exactly 3 providers
        assert len(providers) == 3, f"Expected 3 providers, got {len(providers)}"
        
        # Check provider names
        provider_keys = [p["provider"] for p in providers]
        assert "google_drive" in provider_keys, "google_drive provider missing"
        assert "onedrive" in provider_keys, "onedrive provider missing"
        assert "dropbox" in provider_keys, "dropbox provider missing"
    
    def test_providers_have_required_fields(self):
        """Providers should have name, icon, configured, setup_instructions"""
        resp = self.session.get(f"{BASE_URL}/api/cloud-storage/providers")
        assert resp.status_code == 200
        
        providers = resp.json()["providers"]
        for prov in providers:
            assert "provider" in prov, f"Provider missing 'provider' key"
            assert "name" in prov, f"Provider {prov.get('provider')} missing 'name'"
            assert "icon" in prov, f"Provider {prov.get('provider')} missing 'icon'"
            assert "configured" in prov, f"Provider {prov.get('provider')} missing 'configured'"
            assert "setup_instructions" in prov, f"Provider {prov.get('provider')} missing 'setup_instructions'"
    
    def test_unconfigured_providers_have_setup_instructions(self):
        """Unconfigured providers should show setup instructions"""
        resp = self.session.get(f"{BASE_URL}/api/cloud-storage/providers")
        assert resp.status_code == 200
        
        providers = resp.json()["providers"]
        for prov in providers:
            if not prov["configured"]:
                assert "Add" in prov["setup_instructions"], f"Setup instructions should mention how to add keys"


class TestCloudStorageConnect:
    """Test initiating cloud storage connections"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as org admin"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.org_id = "org_cba36eb8305f"
        
        # Login as org admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@urtech.org",
            "password": "Test1234!"
        })
        if login_resp.status_code == 200:
            self.token = login_resp.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Login failed - skipping tests")
    
    def test_connect_google_drive_returns_501_when_not_configured(self):
        """POST /api/cloud-storage/connect with google_drive returns 501 when not configured"""
        resp = self.session.post(f"{BASE_URL}/api/cloud-storage/connect", json={
            "provider": "google_drive",
            "scope": "user"
        })
        
        # 501 = Not Implemented (provider not configured)
        assert resp.status_code == 501, f"Expected 501 when provider not configured, got {resp.status_code}: {resp.text}"
        assert "not configured" in resp.json().get("detail", "").lower(), "Error message should mention 'not configured'"
    
    def test_connect_onedrive_returns_501_when_not_configured(self):
        """POST /api/cloud-storage/connect with onedrive returns 501 when not configured"""
        resp = self.session.post(f"{BASE_URL}/api/cloud-storage/connect", json={
            "provider": "onedrive",
            "scope": "user"
        })
        
        assert resp.status_code == 501, f"Expected 501, got {resp.status_code}: {resp.text}"
        assert "not configured" in resp.json().get("detail", "").lower()
    
    def test_connect_dropbox_returns_501_when_not_configured(self):
        """POST /api/cloud-storage/connect with dropbox returns 501 when not configured"""
        resp = self.session.post(f"{BASE_URL}/api/cloud-storage/connect", json={
            "provider": "dropbox",
            "scope": "user"
        })
        
        assert resp.status_code == 501, f"Expected 501, got {resp.status_code}: {resp.text}"
        assert "not configured" in resp.json().get("detail", "").lower()
    
    def test_connect_invalid_provider_returns_400(self):
        """POST /api/cloud-storage/connect with invalid provider returns 400"""
        resp = self.session.post(f"{BASE_URL}/api/cloud-storage/connect", json={
            "provider": "invalid_provider",
            "scope": "user"
        })
        
        assert resp.status_code == 400, f"Expected 400 for invalid provider, got {resp.status_code}"
    
    def test_connect_org_scope_requires_org_id(self):
        """POST /api/cloud-storage/connect with org scope requires org_id"""
        resp = self.session.post(f"{BASE_URL}/api/cloud-storage/connect", json={
            "provider": "google_drive",
            "scope": "org"
            # Missing org_id
        })
        
        # Should return 400 for missing org_id or 501 for not configured
        # 400 takes precedence if validation happens first
        assert resp.status_code in [400, 501], f"Expected 400 or 501, got {resp.status_code}"


class TestCloudStorageConnections:
    """Test listing and managing cloud storage connections"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as test user"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.org_id = "org_cba36eb8305f"
        
        # Login as test user
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testmention@test.com",
            "password": "Test1234!"
        })
        if login_resp.status_code == 200:
            self.token = login_resp.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Login failed - skipping tests")
    
    def test_list_user_connections(self):
        """GET /api/cloud-storage/connections?scope=user — returns user connections"""
        resp = self.session.get(f"{BASE_URL}/api/cloud-storage/connections", params={
            "scope": "user"
        })
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "connections" in data, "Response should have 'connections' key"
        assert isinstance(data["connections"], list), "connections should be a list"
    
    def test_list_org_connections(self):
        """GET /api/cloud-storage/connections?scope=org&org_id={id} — returns org connections"""
        resp = self.session.get(f"{BASE_URL}/api/cloud-storage/connections", params={
            "scope": "org",
            "org_id": self.org_id
        })
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "connections" in data, "Response should have 'connections' key"
        assert isinstance(data["connections"], list), "connections should be a list"
    
    def test_connections_exclude_sensitive_tokens(self):
        """Connections list should not expose access_token or refresh_token"""
        resp = self.session.get(f"{BASE_URL}/api/cloud-storage/connections", params={
            "scope": "user"
        })
        
        assert resp.status_code == 200
        connections = resp.json()["connections"]
        
        for conn in connections:
            assert "access_token" not in conn, "access_token should not be exposed"
            assert "refresh_token" not in conn, "refresh_token should not be exposed"
            assert "oauth_state" not in conn, "oauth_state should not be exposed"


class TestCloudStorageCallback:
    """Test OAuth callback endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as test user"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testmention@test.com",
            "password": "Test1234!"
        })
        if login_resp.status_code == 200:
            self.token = login_resp.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Login failed")
    
    def test_callback_requires_code_and_state(self):
        """POST /api/cloud-storage/callback requires code and state"""
        resp = self.session.post(f"{BASE_URL}/api/cloud-storage/callback", json={})
        assert resp.status_code == 400, f"Expected 400 for missing params, got {resp.status_code}"
        
        resp = self.session.post(f"{BASE_URL}/api/cloud-storage/callback", json={
            "code": "test_code"
        })
        assert resp.status_code == 400, f"Expected 400 for missing state, got {resp.status_code}"
    
    def test_callback_with_invalid_state_returns_404(self):
        """POST /api/cloud-storage/callback with invalid state returns 404"""
        resp = self.session.post(f"{BASE_URL}/api/cloud-storage/callback", json={
            "code": "test_authorization_code",
            "state": "invalid_state_token_xyz"
        })
        
        # 404 = Connection not found (invalid state)
        assert resp.status_code == 404, f"Expected 404 for invalid state, got {resp.status_code}: {resp.text}"


class TestCloudStorageRevoke:
    """Test revoking cloud storage connections"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as test user"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testmention@test.com",
            "password": "Test1234!"
        })
        if login_resp.status_code == 200:
            self.token = login_resp.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Login failed")
    
    def test_revoke_nonexistent_connection(self):
        """DELETE /api/cloud-storage/connections/{id} with non-existent id"""
        resp = self.session.delete(f"{BASE_URL}/api/cloud-storage/connections/nonexistent_id_xyz")
        
        # Should return 200 (idempotent) or success even if not found
        # The endpoint just sets status to 'revoked' so it's fine if connection doesn't exist
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert "message" in resp.json() or "Disconnected" in resp.text


class TestCloudStorageFileBrowsing:
    """Test file browsing endpoint (requires active connection)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as test user"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testmention@test.com",
            "password": "Test1234!"
        })
        if login_resp.status_code == 200:
            self.token = login_resp.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Login failed")
    
    def test_browse_files_nonexistent_connection(self):
        """GET /api/cloud-storage/connections/{id}/files with non-existent connection"""
        resp = self.session.get(f"{BASE_URL}/api/cloud-storage/connections/nonexistent_conn_id/files")
        
        # Should return 404 - connection not found
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"


class TestCloudStorageImport:
    """Test file import endpoint (requires active connection)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as test user"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.org_id = "org_cba36eb8305f"
        
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testmention@test.com",
            "password": "Test1234!"
        })
        if login_resp.status_code == 200:
            self.token = login_resp.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Login failed")
    
    def test_import_file_nonexistent_connection(self):
        """POST /api/cloud-storage/connections/{id}/import with non-existent connection"""
        resp = self.session.post(f"{BASE_URL}/api/cloud-storage/connections/nonexistent_conn_id/import", json={
            "file_id": "test_file_id",
            "org_id": self.org_id
        })
        
        # Should return 404 - connection not found
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"


class TestCloudStorageSync:
    """Test sync endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as test user"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testmention@test.com",
            "password": "Test1234!"
        })
        if login_resp.status_code == 200:
            self.token = login_resp.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Login failed")
    
    def test_sync_nonexistent_connection(self):
        """POST /api/cloud-storage/connections/{id}/sync with non-existent connection"""
        resp = self.session.post(f"{BASE_URL}/api/cloud-storage/connections/nonexistent_conn_id/sync")
        
        # Should return 404 - connection not found
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"


class TestCloudStorageConnectionStatus:
    """Test connection status endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as test user"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testmention@test.com",
            "password": "Test1234!"
        })
        if login_resp.status_code == 200:
            self.token = login_resp.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Login failed")
    
    def test_get_connection_status_nonexistent(self):
        """GET /api/cloud-storage/connections/{id}/status with non-existent id returns 404"""
        resp = self.session.get(f"{BASE_URL}/api/cloud-storage/connections/nonexistent_conn_id/status")
        
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
