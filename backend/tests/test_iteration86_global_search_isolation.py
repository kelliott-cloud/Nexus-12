"""
Iteration 86: Global Search Workspace Isolation Tests
CRITICAL SECURITY: Tests that global search is properly scoped by workspace membership.
User A should NOT see results from workspaces they don't belong to.
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestGlobalSearchWorkspaceIsolation:
    """CRITICAL SECURITY: Global search must be scoped to user's workspace memberships."""

    @pytest.fixture(scope="class")
    def user_a_session(self):
        """Create and login User A with unique email."""
        session = requests.Session()
        unique_id = uuid.uuid4().hex[:8]
        email_a = f"tester_a_{unique_id}@nexustest.com"
        
        # Register User A
        reg_res = session.post(f"{BASE_URL}/api/auth/register", json={
            "email": email_a,
            "password": "Test1234!",
            "name": "Test User A"
        })
        # If already exists, just login
        if reg_res.status_code != 200:
            login_res = session.post(f"{BASE_URL}/api/auth/login", json={
                "email": email_a,
                "password": "Test1234!"
            })
            if login_res.status_code != 200:
                # Fallback to admin
                session.post(f"{BASE_URL}/api/auth/login", json={
                    "email": "admin@nexus.com",
                    "password": "Test1234!"
                })
        return {"session": session, "email": email_a, "unique_id": unique_id}
    
    @pytest.fixture(scope="class")
    def user_b_session(self):
        """Create and login User B with unique email."""
        session = requests.Session()
        unique_id = uuid.uuid4().hex[:8]
        email_b = f"tester_b_{unique_id}@nexustest.com"
        
        # Register User B
        reg_res = session.post(f"{BASE_URL}/api/auth/register", json={
            "email": email_b,
            "password": "Test1234!",
            "name": "Test User B"
        })
        if reg_res.status_code != 200:
            session.post(f"{BASE_URL}/api/auth/login", json={
                "email": email_b,
                "password": "Test1234!"
            })
        return {"session": session, "email": email_b, "unique_id": unique_id}

    @pytest.fixture(scope="class")
    def user_a_workspace(self, user_a_session):
        """Create workspace for User A with unique searchable content."""
        session = user_a_session["session"]
        unique = user_a_session["unique_id"]
        
        # Create workspace
        ws_res = session.post(f"{BASE_URL}/api/workspaces", json={
            "name": f"Workspace A {unique}",
            "description": f"ALPHA_SECRET_{unique}"
        })
        assert ws_res.status_code == 200, f"Failed to create workspace A: {ws_res.text}"
        ws_data = ws_res.json()
        workspace_id = ws_data.get("workspace_id")
        
        # Create channel
        ch_res = session.post(f"{BASE_URL}/api/workspaces/{workspace_id}/channels", json={
            "name": f"channel-a-{unique}",
            "description": "Test channel A"
        })
        assert ch_res.status_code == 200, f"Failed to create channel A: {ch_res.text}"
        channel_id = ch_res.json().get("channel_id")
        
        # Send unique message
        search_keyword = f"ALPHA_KEYWORD_{unique}"
        msg_res = session.post(f"{BASE_URL}/api/channels/{channel_id}/messages", json={
            "content": f"This is User A's message with {search_keyword}"
        })
        assert msg_res.status_code == 200, f"Failed to send message A: {msg_res.text}"
        
        return {
            "workspace_id": workspace_id,
            "channel_id": channel_id,
            "search_keyword": search_keyword
        }
    
    @pytest.fixture(scope="class")
    def user_b_workspace(self, user_b_session):
        """Create workspace for User B with unique searchable content."""
        session = user_b_session["session"]
        unique = user_b_session["unique_id"]
        
        # Create workspace
        ws_res = session.post(f"{BASE_URL}/api/workspaces", json={
            "name": f"Workspace B {unique}",
            "description": f"BRAVO_SECRET_{unique}"
        })
        assert ws_res.status_code == 200, f"Failed to create workspace B: {ws_res.text}"
        ws_data = ws_res.json()
        workspace_id = ws_data.get("workspace_id")
        
        # Create channel
        ch_res = session.post(f"{BASE_URL}/api/workspaces/{workspace_id}/channels", json={
            "name": f"channel-b-{unique}",
            "description": "Test channel B"
        })
        assert ch_res.status_code == 200, f"Failed to create channel B: {ch_res.text}"
        channel_id = ch_res.json().get("channel_id")
        
        # Send unique message
        search_keyword = f"BRAVO_KEYWORD_{unique}"
        msg_res = session.post(f"{BASE_URL}/api/channels/{channel_id}/messages", json={
            "content": f"This is User B's message with {search_keyword}"
        })
        assert msg_res.status_code == 200, f"Failed to send message B: {msg_res.text}"
        
        return {
            "workspace_id": workspace_id,
            "channel_id": channel_id,
            "search_keyword": search_keyword
        }

    def test_user_a_can_search_own_workspace(self, user_a_session, user_a_workspace):
        """User A should find results from their own workspace."""
        session = user_a_session["session"]
        keyword = user_a_workspace["search_keyword"]
        
        res = session.get(f"{BASE_URL}/api/search", params={"q": keyword, "limit": 20})
        assert res.status_code == 200, f"Search failed: {res.text}"
        data = res.json()
        
        # Should find at least one result with the keyword
        results = data.get("results", [])
        found = any(keyword in (r.get("snippet", "") + r.get("title", "")) for r in results)
        assert found, f"User A should find their own message with {keyword}. Results: {results}"
        print(f"PASS: User A found their own content with keyword {keyword}")

    def test_user_b_can_search_own_workspace(self, user_b_session, user_b_workspace):
        """User B should find results from their own workspace."""
        session = user_b_session["session"]
        keyword = user_b_workspace["search_keyword"]
        
        res = session.get(f"{BASE_URL}/api/search", params={"q": keyword, "limit": 20})
        assert res.status_code == 200, f"Search failed: {res.text}"
        data = res.json()
        
        # Should find at least one result with the keyword
        results = data.get("results", [])
        found = any(keyword in (r.get("snippet", "") + r.get("title", "")) for r in results)
        assert found, f"User B should find their own message with {keyword}. Results: {results}"
        print(f"PASS: User B found their own content with keyword {keyword}")

    def test_user_a_cannot_see_user_b_workspace(self, user_a_session, user_b_workspace):
        """CRITICAL SECURITY: User A should NOT see results from User B's workspace."""
        session = user_a_session["session"]
        keyword_b = user_b_workspace["search_keyword"]
        
        res = session.get(f"{BASE_URL}/api/search", params={"q": keyword_b, "limit": 50})
        assert res.status_code == 200, f"Search failed: {res.text}"
        data = res.json()
        
        # User A should NOT find User B's content
        results = data.get("results", [])
        found_leak = any(keyword_b in (r.get("snippet", "") + r.get("title", "")) for r in results)
        assert not found_leak, f"SECURITY VIOLATION: User A found User B's content! Results: {results}"
        print(f"PASS: User A correctly CANNOT see User B's content ({keyword_b})")

    def test_user_b_cannot_see_user_a_workspace(self, user_b_session, user_a_workspace):
        """CRITICAL SECURITY: User B should NOT see results from User A's workspace."""
        session = user_b_session["session"]
        keyword_a = user_a_workspace["search_keyword"]
        
        res = session.get(f"{BASE_URL}/api/search", params={"q": keyword_a, "limit": 50})
        assert res.status_code == 200, f"Search failed: {res.text}"
        data = res.json()
        
        # User B should NOT find User A's content
        results = data.get("results", [])
        found_leak = any(keyword_a in (r.get("snippet", "") + r.get("title", "")) for r in results)
        assert not found_leak, f"SECURITY VIOLATION: User B found User A's content! Results: {results}"
        print(f"PASS: User B correctly CANNOT see User A's content ({keyword_a})")


class TestGlobalSearchAuthentication:
    """Test that global search requires authentication."""

    def test_search_requires_auth(self):
        """Unauthenticated requests should fail or return empty."""
        session = requests.Session()  # No login
        res = session.get(f"{BASE_URL}/api/search", params={"q": "test"})
        # Either 401 or 200 with empty results
        if res.status_code == 200:
            data = res.json()
            # If no auth, results should be empty (no workspaces)
            assert data.get("results", []) == [] or res.status_code == 401
        print("PASS: Search is protected - unauthenticated returns empty or 401")

    def test_empty_query_returns_empty(self):
        """Empty search query should return empty results."""
        session = requests.Session()
        session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@nexus.com",
            "password": "Test1234!"
        })
        res = session.get(f"{BASE_URL}/api/search", params={"q": ""})
        assert res.status_code == 200
        data = res.json()
        assert data.get("results", []) == [], "Empty query should return empty results"
        print("PASS: Empty query returns empty results")


class TestHealthAndMigrations:
    """Test health endpoints and migrations."""

    def test_health_live(self):
        """Health endpoint should return alive:true."""
        res = requests.get(f"{BASE_URL}/api/health/live")
        assert res.status_code == 200
        data = res.json()
        assert data.get("alive") == True, f"Health should return alive:true, got: {data}"
        print("PASS: /api/health/live returns alive:true")

    def test_health_general(self):
        """General health endpoint should work."""
        res = requests.get(f"{BASE_URL}/api/health")
        assert res.status_code == 200
        print("PASS: /api/health returns 200")


class TestEnvExampleFiles:
    """Test that .env.example files exist with correct content."""

    def test_backend_env_example_exists(self):
        """Backend .env.example should exist with key variables."""
        import os
        path = "/app/backend/.env.example"
        assert os.path.exists(path), f"{path} does not exist"
        with open(path, "r") as f:
            content = f.read()
        assert "MONGO_URL" in content, "Missing MONGO_URL"
        assert "DB_NAME" in content, "Missing DB_NAME"
        assert "ENCRYPTION_KEY" in content, "Missing ENCRYPTION_KEY"
        print("PASS: backend/.env.example exists with required vars")

    def test_frontend_env_example_exists(self):
        """Frontend .env.example should exist with key variables."""
        import os
        path = "/app/frontend/.env.example"
        assert os.path.exists(path), f"{path} does not exist"
        with open(path, "r") as f:
            content = f.read()
        assert "REACT_APP_BACKEND_URL" in content, "Missing REACT_APP_BACKEND_URL"
        print("PASS: frontend/.env.example exists with required vars")


class TestGlobalSearchTypes:
    """Test global search returns correct types and structure."""

    @pytest.fixture
    def auth_session(self):
        session = requests.Session()
        session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@nexus.com",
            "password": "Test1234!"
        })
        return session

    def test_search_returns_structured_results(self, auth_session):
        """Search should return results with type/id/title/snippet."""
        res = auth_session.get(f"{BASE_URL}/api/search", params={"q": "test", "limit": 10})
        assert res.status_code == 200
        data = res.json()
        assert "results" in data
        assert "query" in data
        # If results exist, verify structure
        for r in data.get("results", [])[:3]:
            assert "type" in r, f"Missing 'type' in result: {r}"
            assert "id" in r, f"Missing 'id' in result: {r}"
            assert "title" in r, f"Missing 'title' in result: {r}"
        print(f"PASS: Search returns structured results. Found {len(data.get('results', []))} results")

    def test_search_with_types_filter(self, auth_session):
        """Search with types filter should work."""
        res = auth_session.get(f"{BASE_URL}/api/search", params={
            "q": "test",
            "types": "messages,projects",
            "limit": 10
        })
        assert res.status_code == 200
        data = res.json()
        # All results should be messages or projects
        for r in data.get("results", []):
            assert r.get("type") in ["message", "project", "messages", "projects"], f"Unexpected type: {r.get('type')}"
        print("PASS: Search types filter works")

    def test_search_limit_parameter(self, auth_session):
        """Search should respect limit parameter."""
        res = auth_session.get(f"{BASE_URL}/api/search", params={"q": "a", "limit": 3})
        assert res.status_code == 200
        data = res.json()
        assert len(data.get("results", [])) <= 3, "Results exceed limit"
        print("PASS: Search respects limit parameter")
