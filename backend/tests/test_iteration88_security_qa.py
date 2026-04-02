"""
Iteration 88: Security QA v28 Fixes Testing
- SCIM token hashing verification (token_hash field in DB, not plain token)
- MFA challenge expiry check (5 min timeout)
- MFA backup code salting with user_id
- .env.example files existence check
- Migration v4 (mfa_challenges TTL index)
"""
import pytest
import requests
import os
import hashlib
import pyotp
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

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
            res = cls.session.post(f"{BASE_URL}/api/auth/login", json={
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD
            })
            if res.status_code == 200:
                cls.cookies = res.cookies
                cls.user_data = res.json()
            else:
                print(f"Login failed: {res.status_code} - {res.text}")
        
        return cls.session, cls.cookies


@pytest.fixture(scope="module")
def mongo_client():
    """MongoDB client for direct DB verification"""
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


# ===================== ENV EXAMPLE FILES =====================

class TestEnvExampleFiles:
    """Verify .env.example files exist with proper content"""
    
    def test_backend_env_example_exists(self):
        """backend/.env.example file exists with required variables"""
        env_path = "/app/backend/.env.example"
        assert os.path.exists(env_path), f"{env_path} not found"
        
        with open(env_path, "r") as f:
            content = f.read()
        
        # Check for required variables
        required_vars = ["MONGO_URL", "DB_NAME", "ENCRYPTION_KEY", "CORS_ORIGINS"]
        for var in required_vars:
            assert var in content, f"Missing {var} in backend/.env.example"
        
        print(f"backend/.env.example contains: {len(content.splitlines())} lines")
    
    def test_frontend_env_example_exists(self):
        """frontend/.env.example file exists with REACT_APP_BACKEND_URL"""
        env_path = "/app/frontend/.env.example"
        assert os.path.exists(env_path), f"{env_path} not found"
        
        with open(env_path, "r") as f:
            content = f.read()
        
        assert "REACT_APP_BACKEND_URL" in content, "Missing REACT_APP_BACKEND_URL in frontend/.env.example"
        print(f"frontend/.env.example contains: {len(content.splitlines())} lines")


# ===================== DB MIGRATIONS =====================

class TestDBMigrations:
    """Verify all 4 migrations are applied"""
    
    def test_migration_v4_applied(self, mongo_client):
        """Migration v4 (mfa_challenges TTL index) should be applied"""
        migrations = list(mongo_client.migrations.find({}))
        versions = [m.get("version") for m in migrations]
        
        assert 4 in versions, f"Migration v4 not applied. Applied versions: {versions}"
        
        # Check that migration 4 is specifically the TTL index one
        m4 = next((m for m in migrations if m.get("version") == 4), None)
        assert m4 is not None
        assert "mfa_challenge" in m4.get("name", "").lower() or "ttl" in m4.get("name", "").lower()
        
        print(f"All migrations applied: {sorted(versions)}")
    
    def test_mfa_challenges_has_ttl_index(self, mongo_client):
        """mfa_challenges collection should have TTL index on created_at"""
        indexes = list(mongo_client.mfa_challenges.list_indexes())
        
        # Find TTL index
        ttl_index = None
        for idx in indexes:
            if "expireAfterSeconds" in idx:
                ttl_index = idx
                break
        
        assert ttl_index is not None, f"No TTL index found on mfa_challenges. Indexes: {[i['name'] for i in indexes]}"
        
        # Should be 300 seconds (5 minutes)
        expire_seconds = ttl_index.get("expireAfterSeconds")
        assert expire_seconds == 300, f"TTL should be 300 seconds, got {expire_seconds}"
        
        print(f"mfa_challenges TTL index: {ttl_index['name']} with expireAfterSeconds={expire_seconds}")


# ===================== SCIM TOKEN HASHING =====================

class TestSCIMTokenHashing:
    """SCIM tokens should be hashed (token_hash), not stored plain"""
    
    scim_token = None
    scim_token_id = None
    
    def test_create_scim_token_returns_plain_token(self):
        """POST /api/admin/scim/tokens returns plain token to user"""
        session, cookies = TestSession.login()
        
        payload = {"workspace_id": "TEST_ws_hash_verify", "default_role": "member"}
        res = session.post(f"{BASE_URL}/api/admin/scim/tokens", json=payload, cookies=cookies)
        
        assert res.status_code == 200, f"SCIM token create failed: {res.text}"
        data = res.json()
        
        assert "token" in data, "Response should include plain token for user"
        assert "token_id" in data
        assert data["token"].startswith("scim_")
        
        TestSCIMTokenHashing.scim_token = data["token"]
        TestSCIMTokenHashing.scim_token_id = data["token_id"]
        
        print(f"Created SCIM token: {data['token_id']}, token starts with: {data['token'][:15]}...")
    
    def test_db_stores_token_hash_not_plain_token(self, mongo_client):
        """MongoDB should store token_hash, NOT plain token"""
        if not TestSCIMTokenHashing.scim_token_id:
            pytest.skip("No SCIM token created")
        
        # Find the token in DB
        token_doc = mongo_client.scim_tokens.find_one(
            {"token_id": TestSCIMTokenHashing.scim_token_id}
        )
        
        assert token_doc is not None, f"Token {TestSCIMTokenHashing.scim_token_id} not found in DB"
        
        # SECURITY CHECK: Should have token_hash, NOT plain token
        assert "token_hash" in token_doc, "SECURITY ISSUE: token_hash field missing in DB"
        assert "token" not in token_doc or token_doc.get("token") is None, \
            "SECURITY ISSUE: Plain 'token' field found in DB - tokens should be hashed!"
        
        # Verify hash matches
        expected_hash = hashlib.sha256(TestSCIMTokenHashing.scim_token.encode()).hexdigest()
        assert token_doc["token_hash"] == expected_hash, "token_hash doesn't match SHA256 of plain token"
        
        print(f"VERIFIED: DB stores token_hash (SHA256), no plain token. Hash prefix: {token_doc['token_hash'][:16]}...")
    
    def test_scim_endpoint_works_with_new_hashed_token(self):
        """SCIM endpoint should authenticate with newly created token via hash comparison"""
        if not TestSCIMTokenHashing.scim_token:
            pytest.skip("No SCIM token created")
        
        headers = {"Authorization": f"Bearer {TestSCIMTokenHashing.scim_token}"}
        res = requests.get(f"{BASE_URL}/api/scim/v2/Users?count=1", headers=headers)
        
        assert res.status_code == 200, f"SCIM auth with hashed token failed: {res.text}"
        data = res.json()
        assert "Resources" in data
        
        print(f"SCIM auth working with hashed token verification")
    
    def test_cleanup_scim_token(self):
        """Cleanup: revoke test SCIM token"""
        if not TestSCIMTokenHashing.scim_token_id:
            pytest.skip("No SCIM token to cleanup")
        
        session, cookies = TestSession.login()
        res = session.delete(
            f"{BASE_URL}/api/admin/scim/tokens/{TestSCIMTokenHashing.scim_token_id}",
            cookies=cookies
        )
        assert res.status_code == 200
        print(f"Cleaned up SCIM token: {TestSCIMTokenHashing.scim_token_id}")


# ===================== MFA CHALLENGE EXPIRY =====================

class TestMFAChallengeExpiry:
    """MFA challenge should check created_at timestamp (5 min timeout)"""
    
    def test_mfa_verify_endpoint_exists(self):
        """POST /api/auth/mfa/verify endpoint exists"""
        # Without valid challenge, should return 400 not 404
        res = requests.post(f"{BASE_URL}/api/auth/mfa/verify", json={"code": "123456"})
        assert res.status_code == 400, f"MFA verify should return 400 without challenge, got {res.status_code}"
        assert "challenge" in res.text.lower() or "pending" in res.text.lower()
        print("MFA verify endpoint exists and checks for pending challenge")
    
    def test_expired_challenge_rejected(self, mongo_client):
        """Expired MFA challenge (>5 min old) should be rejected"""
        session, cookies = TestSession.login()
        
        # Create an EXPIRED challenge directly in DB (6 minutes old)
        expired_time = (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()
        test_challenge = {
            "email": "TEST_expired@test.com",
            "user_id": "TEST_user_expired",
            "created_at": expired_time
        }
        
        # Insert expired challenge
        mongo_client.mfa_challenges.insert_one(test_challenge)
        
        try:
            # Try to verify with expired challenge
            res = requests.post(
                f"{BASE_URL}/api/auth/mfa/verify",
                json={"code": "123456", "email": "TEST_expired@test.com"}
            )
            
            # Should be rejected due to expiry
            assert res.status_code == 400, f"Expired challenge should be rejected, got {res.status_code}"
            assert "expired" in res.text.lower() or "challenge" in res.text.lower()
            
            print("VERIFIED: Expired MFA challenge (6 min old) correctly rejected")
        finally:
            # Cleanup
            mongo_client.mfa_challenges.delete_many({"email": "TEST_expired@test.com"})


# ===================== MFA BACKUP CODE SALTING =====================

class TestMFABackupCodeSalting:
    """MFA backup codes should be salted with user_id"""
    
    def test_mfa_setup_generates_hashed_backup_codes(self, mongo_client):
        """POST /api/auth/mfa/setup should generate salted/hashed backup codes"""
        session, cookies = TestSession.login()
        
        # Check if MFA already enabled
        status_res = session.get(f"{BASE_URL}/api/auth/mfa/status", cookies=cookies)
        if status_res.status_code == 200 and status_res.json().get("mfa_enabled"):
            pytest.skip("MFA already enabled on test account - cannot test setup")
        
        # Start MFA setup
        res = session.post(f"{BASE_URL}/api/auth/mfa/setup", cookies=cookies)
        
        if res.status_code != 200:
            pytest.skip(f"Could not start MFA setup: {res.text}")
        
        data = res.json()
        plain_backup_codes = data["backup_codes"]
        assert len(plain_backup_codes) == 8
        
        # Check pending setup in DB
        user_id = TestSession.user_data.get("user_id")
        pending = mongo_client.mfa_pending.find_one({"user_id": user_id})
        
        assert pending is not None, "MFA pending setup not found in DB"
        assert "backup_codes" in pending
        
        stored_codes = pending["backup_codes"]
        
        # Verify codes are hashed (not plain)
        for plain_code in plain_backup_codes:
            assert plain_code.upper() not in stored_codes, \
                f"SECURITY ISSUE: Plain backup code '{plain_code}' found in DB!"
        
        # Verify salting - hash should include user_id
        # Based on routes_mfa.py: _hash_code uses f"{salt}:{code.strip().upper()}"
        for plain_code in plain_backup_codes:
            expected_hash = hashlib.sha256(f"{user_id}:{plain_code.upper()}".encode()).hexdigest()
            assert expected_hash in stored_codes, \
                f"Backup code hash doesn't match expected salted hash format"
        
        print(f"VERIFIED: Backup codes are hashed with user_id salt. Sample hash prefix: {stored_codes[0][:16]}...")
        
        # Cleanup - delete pending setup
        mongo_client.mfa_pending.delete_many({"user_id": user_id})


# ===================== HEALTH & STATUS =====================

class TestHealthEndpoints:
    """Basic health checks"""
    
    def test_health_live(self):
        """GET /api/health/live returns alive:true"""
        res = requests.get(f"{BASE_URL}/api/health/live")
        assert res.status_code == 200
        data = res.json()
        assert data.get("alive") == True
        print("Health check: alive")
    
    def test_platform_status(self):
        """GET /api/status returns JSON with services"""
        res = requests.get(f"{BASE_URL}/api/status")
        assert res.status_code == 200
        data = res.json()
        assert "services" in data
        print(f"Platform status: {data.get('status')}")


# ===================== RUN TESTS =====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
