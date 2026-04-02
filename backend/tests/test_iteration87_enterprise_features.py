"""
Iteration 87: Enterprise Features Testing
- MFA/TOTP endpoints
- SSO SAML/OIDC configuration
- Error Tracking
- SCIM 2.0 Provisioning
- Status Page & API Docs
"""
import pytest
import requests
import os
import pyotp

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
TEST_EMAIL = "admin@nexus.com"
TEST_PASSWORD = "Test1234!"


class TestSession:
    """Shared session with auth cookies"""
    session = None
    cookies = None
    user_data = None
    
    @classmethod
    def login(cls):
        if cls.session is None:
            cls.session = requests.Session()
            cls.session.headers.update({"Content-Type": "application/json"})
        
        if cls.cookies is None:
            # Login and get session cookie
            res = cls.session.post(f"{BASE_URL}/api/auth/login", json={
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD
            })
            if res.status_code == 200:
                cls.cookies = res.cookies
                cls.user_data = res.json()
                # Handle MFA if required
                if cls.user_data.get("mfa_required"):
                    # Skip MFA tests if MFA is enabled on account
                    pass
            else:
                print(f"Login failed: {res.status_code} - {res.text}")
        
        return cls.session, cls.cookies


# ===================== PUBLIC STATUS ENDPOINTS =====================

class TestStatusEndpoints:
    """Test public status and documentation endpoints"""
    
    def test_platform_status_json(self):
        """GET /api/status returns JSON with services health"""
        res = requests.get(f"{BASE_URL}/api/status")
        assert res.status_code == 200, f"Status failed: {res.text}"
        data = res.json()
        assert "status" in data
        assert "uptime_seconds" in data
        assert "services" in data
        assert "database" in data["services"]
        print(f"Platform status: {data['status']}, uptime: {data['uptime_seconds']}s")
    
    def test_status_page_html(self):
        """GET /api/status/page returns HTML status page"""
        res = requests.get(f"{BASE_URL}/api/status/page")
        assert res.status_code == 200
        assert "text/html" in res.headers.get("content-type", "")
        assert "NEXUS" in res.text
        assert "System Status" in res.text or "Operational" in res.text
        print("Status page HTML returned successfully")
    
    def test_api_docs_page_html(self):
        """GET /api/docs/api returns HTML API reference"""
        res = requests.get(f"{BASE_URL}/api/docs/api")
        assert res.status_code == 200
        assert "text/html" in res.headers.get("content-type", "")
        assert "API" in res.text
        assert "/api/auth" in res.text or "Authentication" in res.text
        print("API docs page HTML returned successfully")


# ===================== SSO ENDPOINTS =====================

class TestSSOEndpoints:
    """Test SSO provider listing and configuration"""
    
    def test_sso_providers_list_public(self):
        """GET /api/sso/providers returns providers list (public)"""
        res = requests.get(f"{BASE_URL}/api/sso/providers")
        assert res.status_code == 200, f"SSO providers failed: {res.text}"
        data = res.json()
        assert "providers" in data
        # May be empty list if no SSO configured
        assert isinstance(data["providers"], list)
        print(f"SSO providers count: {len(data['providers'])}")
    
    def test_admin_sso_configs_list(self):
        """GET /api/admin/sso/configs requires admin auth"""
        session, cookies = TestSession.login()
        res = session.get(f"{BASE_URL}/api/admin/sso/configs", cookies=cookies)
        assert res.status_code == 200, f"SSO configs list failed: {res.text}"
        data = res.json()
        assert "configs" in data
        print(f"SSO configs count: {len(data['configs'])}")
    
    def test_admin_sso_create_saml_config(self):
        """POST /api/admin/sso/config creates SAML configuration"""
        session, cookies = TestSession.login()
        
        # First get a workspace ID
        ws_res = session.get(f"{BASE_URL}/api/workspaces", cookies=cookies)
        workspaces = ws_res.json() if ws_res.status_code == 200 else []
        if not workspaces:
            pytest.skip("No workspaces available for SSO config test")
        
        workspace_id = workspaces[0].get("workspace_id")
        
        payload = {
            "protocol": "saml",
            "provider_name": "TestOkta",
            "idp_entity_id": "https://test-okta.example.com",
            "idp_sso_url": "https://test-okta.example.com/sso",
            "idp_certificate": "MIIC8DCCAdigAwIBAgIQF...test-cert...",
            "auto_provision": True,
            "default_role": "member"
        }
        
        res = session.post(
            f"{BASE_URL}/api/admin/sso/config?workspace_id={workspace_id}",
            json=payload,
            cookies=cookies
        )
        
        # 200 for success, 400 if validation error
        assert res.status_code in [200, 400], f"SSO config create failed: {res.text}"
        
        if res.status_code == 200:
            data = res.json()
            assert "config_id" in data
            assert data["protocol"] == "saml"
            print(f"Created SAML SSO config: {data['config_id']}")
            
            # Cleanup - delete the config
            session.delete(f"{BASE_URL}/api/admin/sso/config/{data['config_id']}", cookies=cookies)
        else:
            print(f"SAML config validation: {res.text}")


# ===================== MFA ENDPOINTS =====================

class TestMFAEndpoints:
    """Test MFA/TOTP endpoints"""
    
    def test_mfa_status_requires_auth(self):
        """GET /api/auth/mfa/status requires authentication"""
        res = requests.get(f"{BASE_URL}/api/auth/mfa/status")
        # Should return 401 without auth
        assert res.status_code == 401, f"MFA status without auth should be 401, got: {res.status_code}"
        print("MFA status correctly requires auth")
    
    def test_mfa_status_authenticated(self):
        """GET /api/auth/mfa/status returns mfa_enabled and backup_codes_remaining"""
        session, cookies = TestSession.login()
        res = session.get(f"{BASE_URL}/api/auth/mfa/status", cookies=cookies)
        assert res.status_code == 200, f"MFA status failed: {res.text}"
        data = res.json()
        assert "mfa_enabled" in data
        assert "backup_codes_remaining" in data
        print(f"MFA enabled: {data['mfa_enabled']}, backup codes: {data['backup_codes_remaining']}")
    
    def test_mfa_setup_returns_qr_and_secret(self):
        """POST /api/auth/mfa/setup returns QR code, secret, and backup codes"""
        session, cookies = TestSession.login()
        
        # Check if MFA already enabled
        status_res = session.get(f"{BASE_URL}/api/auth/mfa/status", cookies=cookies)
        if status_res.status_code == 200 and status_res.json().get("mfa_enabled"):
            pytest.skip("MFA already enabled on test account")
        
        res = session.post(f"{BASE_URL}/api/auth/mfa/setup", cookies=cookies)
        
        # 200 for success, 400 if already enabled
        assert res.status_code in [200, 400], f"MFA setup failed: {res.text}"
        
        if res.status_code == 200:
            data = res.json()
            assert "secret" in data
            assert "qr_code" in data
            assert "backup_codes" in data
            assert data["qr_code"].startswith("data:image/png;base64,")
            assert len(data["backup_codes"]) == 8
            print(f"MFA setup returned secret (length: {len(data['secret'])}), QR code, and 8 backup codes")
        else:
            print(f"MFA setup: {res.json().get('detail', res.text)}")
    
    def test_mfa_setup_confirm_validates_code(self):
        """POST /api/auth/mfa/setup/confirm validates TOTP code"""
        session, cookies = TestSession.login()
        
        # Check if MFA already enabled
        status_res = session.get(f"{BASE_URL}/api/auth/mfa/status", cookies=cookies)
        if status_res.status_code == 200 and status_res.json().get("mfa_enabled"):
            pytest.skip("MFA already enabled on test account")
        
        # Start setup to get secret
        setup_res = session.post(f"{BASE_URL}/api/auth/mfa/setup", cookies=cookies)
        if setup_res.status_code != 200:
            pytest.skip("Could not start MFA setup")
        
        secret = setup_res.json()["secret"]
        
        # Generate valid TOTP code
        totp = pyotp.TOTP(secret)
        code = totp.now()
        
        res = session.post(
            f"{BASE_URL}/api/auth/mfa/setup/confirm",
            json={"code": code},
            cookies=cookies
        )
        
        # Should succeed with valid code
        assert res.status_code == 200, f"MFA confirm failed: {res.text}"
        data = res.json()
        assert data.get("status") == "mfa_enabled"
        print("MFA setup confirmed successfully with valid TOTP code")
        
        # Now disable MFA to clean up for future tests
        # First generate a new code
        disable_code = totp.now()
        session.post(
            f"{BASE_URL}/api/auth/mfa/disable",
            json={"code": disable_code, "password": TEST_PASSWORD},
            cookies=cookies
        )


# ===================== ERROR TRACKING ENDPOINTS =====================

class TestErrorTrackingEndpoints:
    """Test error tracking capture and viewer"""
    
    def test_report_error_public(self):
        """POST /api/errors/report captures frontend errors"""
        payload = {
            "message": "TEST_Error: Something went wrong in frontend",
            "stack": "Error: TEST at Component.render (app.js:123)",
            "source": "frontend",
            "component": "TestComponent",
            "url": "https://example.com/test-page"
        }
        
        res = requests.post(f"{BASE_URL}/api/errors/report", json=payload)
        assert res.status_code == 200, f"Error report failed: {res.text}"
        data = res.json()
        assert "status" in data
        assert data["status"] == "recorded"
        assert "error_id" in data
        print(f"Error recorded: {data['error_id']}, deduplicated: {data.get('deduplicated', False)}")
    
    def test_admin_errors_list_requires_admin(self):
        """GET /api/admin/errors requires admin auth"""
        session, cookies = TestSession.login()
        res = session.get(f"{BASE_URL}/api/admin/errors", cookies=cookies)
        assert res.status_code == 200, f"Admin errors list failed: {res.text}"
        data = res.json()
        assert "errors" in data
        assert "total" in data
        print(f"Total errors: {data['total']}, showing: {len(data['errors'])}")
    
    def test_admin_errors_stats(self):
        """GET /api/admin/errors/stats returns error statistics"""
        session, cookies = TestSession.login()
        res = session.get(f"{BASE_URL}/api/admin/errors/stats", cookies=cookies)
        assert res.status_code == 200, f"Error stats failed: {res.text}"
        data = res.json()
        assert "total" in data
        assert "unresolved" in data
        assert "frontend" in data
        assert "backend" in data
        print(f"Error stats - Total: {data['total']}, Unresolved: {data['unresolved']}, Frontend: {data['frontend']}, Backend: {data['backend']}")


# ===================== SCIM ENDPOINTS =====================

class TestSCIMEndpoints:
    """Test SCIM 2.0 provisioning endpoints"""
    
    def test_scim_users_requires_bearer_token(self):
        """GET /api/scim/v2/Users returns 401 without SCIM bearer token"""
        res = requests.get(f"{BASE_URL}/api/scim/v2/Users")
        assert res.status_code == 401, f"SCIM should require auth, got: {res.status_code}"
        print("SCIM Users endpoint correctly requires bearer token")
    
    def test_admin_scim_tokens_create(self):
        """POST /api/admin/scim/tokens creates SCIM bearer token"""
        session, cookies = TestSession.login()
        
        payload = {
            "workspace_id": "test_workspace",
            "default_role": "member"
        }
        
        res = session.post(f"{BASE_URL}/api/admin/scim/tokens", json=payload, cookies=cookies)
        assert res.status_code == 200, f"SCIM token create failed: {res.text}"
        data = res.json()
        assert "token_id" in data
        assert "token" in data
        assert data["token"].startswith("scim_")
        print(f"Created SCIM token: {data['token_id']}")
        
        # Store token for next test
        TestSCIMEndpoints.scim_token = data["token"]
        TestSCIMEndpoints.scim_token_id = data["token_id"]
    
    scim_token = None
    scim_token_id = None
    
    def test_scim_users_with_token(self):
        """GET /api/scim/v2/Users works with valid SCIM token"""
        # First create token if not exists
        if not TestSCIMEndpoints.scim_token:
            self.test_admin_scim_tokens_create()
        
        if not TestSCIMEndpoints.scim_token:
            pytest.skip("Could not create SCIM token")
        
        headers = {"Authorization": f"Bearer {TestSCIMEndpoints.scim_token}"}
        res = requests.get(f"{BASE_URL}/api/scim/v2/Users", headers=headers)
        assert res.status_code == 200, f"SCIM Users list failed: {res.text}"
        data = res.json()
        assert "schemas" in data
        assert "totalResults" in data
        assert "Resources" in data
        print(f"SCIM Users list: {data['totalResults']} users")
    
    def test_admin_scim_tokens_list(self):
        """GET /api/admin/scim/tokens lists SCIM tokens"""
        session, cookies = TestSession.login()
        res = session.get(f"{BASE_URL}/api/admin/scim/tokens", cookies=cookies)
        assert res.status_code == 200, f"SCIM tokens list failed: {res.text}"
        data = res.json()
        assert "tokens" in data
        print(f"SCIM tokens count: {len(data['tokens'])}")
    
    def test_admin_scim_token_revoke(self):
        """DELETE /api/admin/scim/tokens/{token_id} revokes token"""
        if not TestSCIMEndpoints.scim_token_id:
            pytest.skip("No SCIM token to revoke")
        
        session, cookies = TestSession.login()
        res = session.delete(
            f"{BASE_URL}/api/admin/scim/tokens/{TestSCIMEndpoints.scim_token_id}",
            cookies=cookies
        )
        assert res.status_code == 200, f"SCIM token revoke failed: {res.text}"
        print(f"Revoked SCIM token: {TestSCIMEndpoints.scim_token_id}")


# ===================== RUN TESTS =====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
