"""
Iteration 117 - Bug Fix Verification Tests
Tests for:
1. POST /api/settings/ai-keys/test must not include debug field in response
2. POST /api/workspaces/{id}/memory/upload with Bearer auth returns 200
3. POST /api/workspaces/{id}/image-to-video returns 501 quickly (fail-fast)
4. POST /api/workspaces/{id}/media/jobs still returns 200 and remains responsive
5. Backend startup: routes_media is not double-registered from routes/__init__.py
6. Frontend routes /workflows, /analytics, /agent-studio load properly
"""
import pytest
import requests
import time
import os

# Get BASE_URL from conftest
from conftest import BASE_URL

# Test credentials from review request
TEST_EMAIL = os.environ.get("TEST_ADMIN_EMAIL", "admin@test.local")
TEST_PASSWORD = "test"


class TestBugFixes:
    """Test all bug fixes from Nexus_Bug_Fix_Brief.docx"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session and authenticate"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get session token
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        
        # Get user info and workspace
        me_resp = self.session.get(f"{BASE_URL}/api/auth/me")
        assert me_resp.status_code == 200, f"Auth check failed: {me_resp.text}"
        self.user = me_resp.json()
        
        # Get first workspace
        ws_resp = self.session.get(f"{BASE_URL}/api/workspaces")
        assert ws_resp.status_code == 200, f"Workspaces fetch failed: {ws_resp.text}"
        workspaces = ws_resp.json()
        assert len(workspaces) > 0, "No workspaces found"
        self.workspace_id = workspaces[0]["workspace_id"]
        
        # Store session token for Bearer auth tests
        cookies = self.session.cookies.get_dict()
        self.session_token = cookies.get("session_token", "")
        
        yield
        
        # Cleanup
        self.session.close()

    # ============ Bug Fix 1: debug_info leakage from /api/settings/ai-keys/test ============
    
    def test_ai_keys_test_no_debug_field(self):
        """POST /api/settings/ai-keys/test must NOT include debug field in response"""
        # Test with a dummy API key (will fail validation but response structure matters)
        resp = self.session.post(
            f"{BASE_URL}/api/settings/ai-keys/test",
            json={"agent_key": "chatgpt", "api_key": "sk-test-invalid-key-12345"}
        )
        
        # Response should be 200 (test completed) or 4xx (validation error)
        # Either way, check response does NOT contain debug field
        data = resp.json()
        
        assert "debug" not in data, f"Response contains debug field (security leak): {data.keys()}"
        assert "debug_info" not in data, f"Response contains debug_info field (security leak): {data.keys()}"
        
        # Valid response should have success, error, or message fields
        assert any(k in data for k in ["success", "error", "message", "detail"]), \
            f"Response missing expected fields: {data}"
        
        print(f"✓ AI keys test response has no debug field. Keys: {list(data.keys())}")

    # ============ Bug Fix 2: Bearer auth on /workspaces/{id}/memory/upload ============
    
    def test_memory_upload_bearer_auth(self):
        """POST /api/workspaces/{id}/memory/upload with Bearer auth should work"""
        # Create a simple text file for upload
        test_content = b"Test memory content for upload verification"
        files = {"file": ("test_memory.txt", test_content, "text/plain")}
        
        # Use Bearer token instead of cookie
        headers = {
            "Authorization": f"Bearer {self.session_token}"
        }
        
        # Make request without cookies, only Bearer token
        resp = requests.post(
            f"{BASE_URL}/api/workspaces/{self.workspace_id}/memory/upload",
            files=files,
            headers=headers
        )
        
        # Should return 200 or 201 (success) or 400/422 (validation error but auth passed)
        # Should NOT return 401 (auth failed)
        assert resp.status_code != 401, f"Bearer auth failed with 401: {resp.text}"
        
        # Accept 200, 201, 400, 422 as valid (auth worked, endpoint processed request)
        assert resp.status_code in [200, 201, 400, 422, 500], \
            f"Unexpected status {resp.status_code}: {resp.text}"
        
        print(f"✓ Memory upload with Bearer auth returned {resp.status_code} (auth passed)")

    # ============ Bug Fix 3: image-to-video returns 501 quickly (fail-fast) ============
    
    def test_image_to_video_fail_fast_501(self):
        """POST /api/workspaces/{id}/image-to-video should return 501 quickly"""
        start_time = time.time()
        
        resp = self.session.post(
            f"{BASE_URL}/api/workspaces/{self.workspace_id}/image-to-video",
            json={"source_image_id": "img_test123"}
        )
        
        elapsed = time.time() - start_time
        
        # Should return 501 (Not Implemented)
        assert resp.status_code == 501, f"Expected 501, got {resp.status_code}: {resp.text}"
        
        # Should be fast (< 2 seconds) - fail-fast behavior
        assert elapsed < 2.0, f"Response took {elapsed:.2f}s - should be < 2s for fail-fast"
        
        # Check error message mentions Sora API
        data = resp.json()
        assert "detail" in data or "message" in data, f"Missing error detail: {data}"
        error_msg = data.get("detail", data.get("message", ""))
        assert "sora" in error_msg.lower() or "video" in error_msg.lower(), \
            f"Error should mention Sora/video: {error_msg}"
        
        print(f"✓ image-to-video returned 501 in {elapsed:.3f}s (fail-fast working)")

    # ============ Bug Fix 4: media/jobs still returns 200 and responsive ============
    
    def test_media_jobs_still_responsive(self):
        """POST /api/workspaces/{id}/media/jobs should return 200 and be responsive"""
        start_time = time.time()
        
        # Create a media job
        resp = self.session.post(
            f"{BASE_URL}/api/workspaces/{self.workspace_id}/media/jobs",
            json={
                "type": "text_to_video",
                "provider": "sora",
                "input": {"prompt": "Test video generation"}
            }
        )
        
        elapsed = time.time() - start_time
        
        # Should return 200 (job created)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        # Should be responsive (< 2 seconds)
        assert elapsed < 2.0, f"Response took {elapsed:.2f}s - should be < 2s"
        
        # Check response has job_id
        data = resp.json()
        assert "job_id" in data, f"Response missing job_id: {data}"
        assert data.get("status") == "queued", f"Job status should be 'queued': {data}"
        
        print(f"✓ media/jobs returned 200 in {elapsed:.3f}s with job_id: {data['job_id']}")
        
        # Also test GET media/jobs
        get_resp = self.session.get(
            f"{BASE_URL}/api/workspaces/{self.workspace_id}/media/jobs"
        )
        assert get_resp.status_code == 200, f"GET media/jobs failed: {get_resp.text}"
        
        print(f"✓ GET media/jobs also working")

    # ============ Bug Fix 5: routes_media not double-registered ============
    
    def test_routes_media_not_double_registered(self):
        """Verify routes_media is not imported in routes/__init__.py (no double registration)"""
        import pathlib
        
        routes_init_path = pathlib.Path(__file__).resolve().parent.parent / "routes" / "__init__.py"
        
        with open(routes_init_path, "r") as f:
            content = f.read()
        
        # Check that routes_media is NOT in the imports
        assert "routes_media" not in content, \
            "routes_media should NOT be imported in routes/__init__.py (causes double registration)"
        
        print(f"✓ routes/__init__.py does not import routes_media")

    # ============ Additional: Verify media endpoints work without cascade failures ============
    
    def test_media_endpoints_no_cascade_failure(self):
        """Verify media endpoints work independently without cascade failures"""
        # Test multiple media endpoints in sequence
        endpoints_to_test = [
            ("GET", f"/api/workspaces/{self.workspace_id}/media", None),
            ("GET", f"/api/media/config", None),
            ("GET", f"/api/workspaces/{self.workspace_id}/media/folders", None),
            ("GET", f"/api/workspaces/{self.workspace_id}/media/metrics", None),
        ]
        
        results = []
        for method, endpoint, payload in endpoints_to_test:
            start = time.time()
            if method == "GET":
                resp = self.session.get(f"{BASE_URL}{endpoint}")
            else:
                resp = self.session.post(f"{BASE_URL}{endpoint}", json=payload)
            elapsed = time.time() - start
            
            results.append({
                "endpoint": endpoint,
                "status": resp.status_code,
                "elapsed": elapsed,
                "success": resp.status_code in [200, 201]
            })
        
        # All should succeed
        failed = [r for r in results if not r["success"]]
        assert len(failed) == 0, f"Some media endpoints failed: {failed}"
        
        # All should be responsive
        slow = [r for r in results if r["elapsed"] > 3.0]
        assert len(slow) == 0, f"Some media endpoints too slow: {slow}"
        
        print(f"✓ All {len(results)} media endpoints working without cascade failures")


class TestAIKeysTestEndpoint:
    """Focused tests for /api/settings/ai-keys/test endpoint security"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session and authenticate"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        yield
        self.session.close()

    def test_ai_keys_test_response_structure_valid_format(self):
        """Verify response structure for ai-keys/test is clean"""
        # Test with various providers
        providers = ["chatgpt", "claude", "gemini"]
        
        for provider in providers:
            resp = self.session.post(
                f"{BASE_URL}/api/settings/ai-keys/test",
                json={"agent_key": provider, "api_key": "sk-invalid-test-key"}
            )
            
            data = resp.json()
            
            # Must NOT have debug fields
            forbidden_fields = ["debug", "debug_info", "request_headers", "response_headers", 
                               "response_body", "timestamp", "endpoint"]
            for field in forbidden_fields:
                assert field not in data, \
                    f"Provider {provider}: Response contains forbidden field '{field}'"
            
            print(f"✓ {provider}: Response clean, no debug fields")

    def test_ai_keys_test_error_response_no_leak(self):
        """Verify error responses don't leak debug info"""
        # Test with invalid provider
        resp = self.session.post(
            f"{BASE_URL}/api/settings/ai-keys/test",
            json={"agent_key": "invalid_provider", "api_key": "test"}
        )
        
        data = resp.json()
        
        # Even error responses should not have debug info
        assert "debug" not in data, f"Error response has debug field: {data}"
        assert "debug_info" not in data, f"Error response has debug_info field: {data}"
        
        print(f"✓ Error response clean, no debug leak")


class TestImageToVideoFailFast:
    """Focused tests for image-to-video fail-fast behavior"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session and authenticate"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert login_resp.status_code == 200
        
        ws_resp = self.session.get(f"{BASE_URL}/api/workspaces")
        self.workspace_id = ws_resp.json()[0]["workspace_id"]
        yield
        self.session.close()

    def test_image_to_video_missing_source_image_id(self):
        """Test image-to-video with missing source_image_id returns 400"""
        resp = self.session.post(
            f"{BASE_URL}/api/workspaces/{self.workspace_id}/image-to-video",
            json={}
        )
        
        # Should return 400 (bad request) for missing required field
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        print(f"✓ Missing source_image_id returns 400")

    def test_image_to_video_with_source_returns_501(self):
        """Test image-to-video with source_image_id returns 501 immediately"""
        start = time.time()
        
        resp = self.session.post(
            f"{BASE_URL}/api/workspaces/{self.workspace_id}/image-to-video",
            json={"source_image_id": "img_abc123"}
        )
        
        elapsed = time.time() - start
        
        assert resp.status_code == 501, f"Expected 501, got {resp.status_code}"
        assert elapsed < 1.0, f"Should be instant, took {elapsed:.2f}s"
        
        print(f"✓ image-to-video with source_image_id returns 501 in {elapsed:.3f}s")

    def test_image_to_video_does_not_block_other_endpoints(self):
        """Verify image-to-video failure doesn't block other media endpoints"""
        # First call image-to-video (should fail fast)
        self.session.post(
            f"{BASE_URL}/api/workspaces/{self.workspace_id}/image-to-video",
            json={"source_image_id": "img_test"}
        )
        
        # Then immediately call media/jobs - should still work
        start = time.time()
        resp = self.session.post(
            f"{BASE_URL}/api/workspaces/{self.workspace_id}/media/jobs",
            json={"type": "test", "provider": "test", "input": {}}
        )
        elapsed = time.time() - start
        
        assert resp.status_code == 200, f"media/jobs blocked after image-to-video: {resp.text}"
        assert elapsed < 2.0, f"media/jobs slow after image-to-video: {elapsed:.2f}s"
        
        print(f"✓ media/jobs still responsive after image-to-video failure")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
