"""
Iteration 121 - Code Audit Fixes Testing
Tests for fixes from Nexus_Full_Code_Audit.docx:
1. OpenClaw now_iso import + cleanup
2. Tier23 custom agent test route real AI execution
3. Research report route AI generation
4. Media feature flags (video/music/sfx)
5. Platform capabilities features block
6. MFA invalid timestamp handling
7. A2A/operator JSON parse failures logging
8. No syntax/runtime regression in touched files
"""

import pytest
import requests
import os
import json
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8080').rstrip('/')

# Test credentials
TEST_EMAIL = os.environ.get("TEST_ADMIN_EMAIL", "admin@test.local")
TEST_PASSWORD = "test"


class TestAuthSetup:
    """Authentication setup for all tests"""
    
    @pytest.fixture(scope="class")
    def session(self):
        """Create authenticated session"""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        return s
    
    @pytest.fixture(scope="class")
    def auth_token(self, session):
        """Get authentication token"""
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            token = data.get("session_token")
            if token:
                session.cookies.set("session_token", token)
            return token
        pytest.skip(f"Authentication failed: {response.status_code}")
    
    @pytest.fixture(scope="class")
    def workspace_id(self, session, auth_token):
        """Get a workspace ID for testing"""
        response = session.get(f"{BASE_URL}/api/workspaces")
        if response.status_code == 200:
            data = response.json()
            # API returns list directly, not {"workspaces": [...]}
            workspaces = data if isinstance(data, list) else data.get("workspaces", [])
            if workspaces:
                return workspaces[0]["workspace_id"]
        pytest.skip("No workspaces available for testing")


class TestOpenClawEndpoints(TestAuthSetup):
    """Test OpenClaw endpoints - now_iso import fix verification"""
    
    def test_openclaw_health_returns_200(self, session, auth_token):
        """OpenClaw health endpoint should return 200 without NameError"""
        response = session.get(f"{BASE_URL}/api/openclaw/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"
        assert "version" in data
        assert "connected_workspaces" in data
        assert "active_sessions" in data
        print(f"OpenClaw health: {data}")
    
    def test_openclaw_health_no_nameerror(self, session, auth_token):
        """Verify no NameError for now_iso in OpenClaw routes"""
        # Multiple calls to ensure no intermittent NameError
        for i in range(3):
            response = session.get(f"{BASE_URL}/api/openclaw/health")
            assert response.status_code == 200, f"Call {i+1} failed: {response.text}"
            assert "error" not in response.text.lower() or "nameerror" not in response.text.lower()


class TestTier23CustomAgentTest(TestAuthSetup):
    """Test custom agent test route - real AI execution instead of fake template"""
    
    def test_custom_agent_create_and_test(self, session, auth_token):
        """Create a custom agent and test it - should attempt real AI call"""
        # Create a custom agent
        create_response = session.post(f"{BASE_URL}/api/agents/custom", json={
            "name": "TEST_Audit_Agent",
            "model": "chatgpt",
            "system_prompt": "You are a helpful test assistant.",
            "temperature": 0.7,
            "max_tokens": 100
        })
        assert create_response.status_code == 200, f"Failed to create agent: {create_response.text}"
        agent_data = create_response.json()
        agent_id = agent_data.get("agent_id")
        assert agent_id, "No agent_id returned"
        
        # Test the agent - should return real response or clean 400/500
        test_response = session.post(f"{BASE_URL}/api/agents/custom/{agent_id}/test", json={
            "message": "Hello, introduce yourself."
        })
        
        # Should NOT return the old fake template string
        if test_response.status_code == 200:
            data = test_response.json()
            response_text = data.get("response", "")
            # Old fake template was: "Hello! I'm {agent_name}, a custom AI agent..."
            assert "I'm {agent_name}" not in response_text, "Still returning fake template response"
            assert "agent" in data
            assert "model" in data
            print(f"Custom agent test response: {data.get('response', '')[:200]}...")
        elif test_response.status_code == 400:
            # Clean 400 when no API key available
            data = test_response.json()
            detail = data.get("detail", "")
            assert "API key" in detail or "key" in detail.lower() or "fallback" in detail.lower(), \
                f"Expected clean API key error, got: {detail}"
            print(f"Custom agent test returned clean 400: {detail}")
        else:
            # 500 is acceptable if it's a real error, not a crash
            assert test_response.status_code in [400, 500], f"Unexpected status: {test_response.status_code}"
        
        # Cleanup - delete the test agent
        session.delete(f"{BASE_URL}/api/agents/custom/{agent_id}")


class TestResearchReportRoute(TestAuthSetup):
    """Test research report route - AI generation instead of static placeholder"""
    
    def test_research_report_no_static_placeholder(self, session, auth_token, workspace_id):
        """Research report should not contain old static placeholder text"""
        # Start a research session
        start_response = session.post(f"{BASE_URL}/api/research/start", json={
            "workspace_id": workspace_id,
            "query": "What is artificial intelligence?",
            "depth": "quick",
            "model": "claude"
        })
        assert start_response.status_code == 200, f"Failed to start research: {start_response.text}"
        session_data = start_response.json()
        session_id = session_data.get("session_id")
        assert session_id, "No session_id returned"
        
        # Wait a moment for processing
        time.sleep(2)
        
        # Get the report
        report_response = session.get(f"{BASE_URL}/api/research/{session_id}/report")
        assert report_response.status_code == 200, f"Failed to get report: {report_response.text}"
        report_data = report_response.json()
        
        # Check that it doesn't contain the old static placeholder text
        structure = report_data.get("structure", {})
        sections = structure.get("sections", [])
        
        # Old placeholder findings text was: "Based on analysis of X sources..."
        # Old placeholder conclusions text was: "The research indicates..."
        for section in sections:
            content = section.get("content", "")
            # These were the exact static strings in the old code
            assert "Based on analysis of X sources" not in content, \
                f"Found old static placeholder in section '{section.get('title')}'"
        
        print(f"Research report structure: {[s.get('title') for s in sections]}")
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/research/{session_id}")


class TestMediaFeatureFlags(TestAuthSetup):
    """Test media feature flags - video/music/sfx return explicit reasons"""
    
    def test_generate_video_returns_feature_flag_reason(self, session, auth_token, workspace_id):
        """POST /generate-video should return 501 with feature flag reason"""
        response = session.post(f"{BASE_URL}/api/workspaces/{workspace_id}/generate-video", json={
            "prompt": "A test video",
            "size": "1280x720",
            "duration": 4
        })
        assert response.status_code == 501, f"Expected 501, got {response.status_code}"
        data = response.json()
        detail = data.get("detail", "")
        assert "video generation" in detail.lower() or "sora" in detail.lower() or "not enabled" in detail.lower(), \
            f"Expected feature flag reason, got: {detail}"
        print(f"Video generation response: {detail}")
    
    def test_image_to_video_returns_feature_flag_reason(self, session, auth_token, workspace_id):
        """POST /image-to-video should return 501 with feature flag reason"""
        response = session.post(f"{BASE_URL}/api/workspaces/{workspace_id}/image-to-video", json={
            "source_image_id": "test_image_id"
        })
        assert response.status_code == 501, f"Expected 501, got {response.status_code}"
        data = response.json()
        detail = data.get("detail", "")
        assert "video" in detail.lower() or "not enabled" in detail.lower(), \
            f"Expected feature flag reason, got: {detail}"
        print(f"Image-to-video response: {detail}")
    
    def test_generate_music_returns_feature_flag_reason(self, session, auth_token, workspace_id):
        """POST /generate-music should return 501 with feature flag reason"""
        response = session.post(f"{BASE_URL}/api/workspaces/{workspace_id}/generate-music", json={
            "prompt": "A test music track"
        })
        assert response.status_code == 501, f"Expected 501, got {response.status_code}"
        data = response.json()
        detail = data.get("detail", "")
        assert "music" in detail.lower() or "suno" in detail.lower() or "udio" in detail.lower() or "not enabled" in detail.lower(), \
            f"Expected feature flag reason, got: {detail}"
        print(f"Music generation response: {detail}")
    
    def test_generate_sfx_returns_feature_flag_reason(self, session, auth_token, workspace_id):
        """POST /generate-sfx should return 501 with feature flag reason"""
        response = session.post(f"{BASE_URL}/api/workspaces/{workspace_id}/generate-sfx", json={
            "prompt": "A test sound effect"
        })
        assert response.status_code == 501, f"Expected 501, got {response.status_code}"
        data = response.json()
        detail = data.get("detail", "")
        assert "sound" in detail.lower() or "sfx" in detail.lower() or "audio" in detail.lower() or "not enabled" in detail.lower(), \
            f"Expected feature flag reason, got: {detail}"
        print(f"SFX generation response: {detail}")


class TestPlatformCapabilities(TestAuthSetup):
    """Test platform capabilities - features block with video/music/sfx flags"""
    
    def test_platform_capabilities_includes_features(self, session, auth_token):
        """GET /platform/capabilities should include features block"""
        response = session.get(f"{BASE_URL}/api/platform/capabilities")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Check for features block
        assert "features" in data, "Missing 'features' block in capabilities"
        features = data["features"]
        
        # Check for video_generation flag
        assert "video_generation" in features, "Missing video_generation in features"
        assert "enabled" in features["video_generation"], "Missing enabled field in video_generation"
        assert "reason" in features["video_generation"], "Missing reason field in video_generation"
        
        # Check for music_generation flag
        assert "music_generation" in features, "Missing music_generation in features"
        assert "enabled" in features["music_generation"], "Missing enabled field in music_generation"
        assert "reason" in features["music_generation"], "Missing reason field in music_generation"
        
        # Check for sfx_generation flag
        assert "sfx_generation" in features, "Missing sfx_generation in features"
        assert "enabled" in features["sfx_generation"], "Missing enabled field in sfx_generation"
        assert "reason" in features["sfx_generation"], "Missing reason field in sfx_generation"
        
        print(f"Platform capabilities features: {json.dumps(features, indent=2)}")
    
    def test_media_config_includes_features(self, session, auth_token):
        """GET /media/config should include features block"""
        response = session.get(f"{BASE_URL}/api/media/config")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Check for features block
        assert "features" in data, "Missing 'features' block in media config"
        features = data["features"]
        
        assert "video_generation" in features, "Missing video_generation in media config features"
        assert "music_generation" in features, "Missing music_generation in media config features"
        assert "sfx_generation" in features, "Missing sfx_generation in media config features"
        
        print(f"Media config features: {json.dumps(features, indent=2)}")


class TestMFAInvalidTimestamp(TestAuthSetup):
    """Test MFA invalid/corrupt challenge timestamps - should return 400"""
    
    def test_mfa_verify_without_challenge_returns_400(self, session):
        """MFA verify without pending challenge should return 400"""
        response = session.post(f"{BASE_URL}/api/auth/mfa/verify", json={
            "code": "123456",
            "email": "nonexistent@test.com"
        })
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        detail = data.get("detail", "")
        # Should indicate no pending challenge or invalid/expired
        assert "challenge" in detail.lower() or "expired" in detail.lower() or "invalid" in detail.lower(), \
            f"Expected challenge/expired error, got: {detail}"
        print(f"MFA verify without challenge: {detail}")
    
    def test_mfa_verify_with_invalid_token_returns_400(self, session):
        """MFA verify with invalid challenge token should return 400"""
        response = session.post(f"{BASE_URL}/api/auth/mfa/verify", json={
            "code": "123456",
            "challenge_token": "invalid_token_12345"
        })
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        detail = data.get("detail", "")
        assert "challenge" in detail.lower() or "expired" in detail.lower() or "invalid" in detail.lower(), \
            f"Expected challenge/expired error, got: {detail}"
        print(f"MFA verify with invalid token: {detail}")


class TestA2APipelineJSONParsing(TestAuthSetup):
    """Test A2A pipeline trigger/resume - accept empty/non-JSON bodies"""
    
    def test_a2a_pipeline_trigger_with_empty_body(self, session, auth_token, workspace_id):
        """A2A pipeline trigger should handle empty body gracefully"""
        # First create a pipeline
        create_response = session.post(f"{BASE_URL}/api/workspaces/{workspace_id}/a2a/pipelines", json={
            "name": "TEST_Audit_Pipeline",
            "description": "Test pipeline for audit",
            "steps": []
        })
        
        if create_response.status_code != 200:
            pytest.skip(f"Could not create pipeline: {create_response.text}")
        
        pipeline_data = create_response.json()
        pipeline_id = pipeline_data.get("pipeline_id")
        
        # Try to trigger with empty body - should not crash
        trigger_response = session.post(
            f"{BASE_URL}/api/a2a/pipelines/{pipeline_id}/trigger",
            data="",  # Empty body
            headers={"Content-Type": "application/json"}
        )
        # Should either succeed or return a clean error, not crash
        assert trigger_response.status_code in [200, 400, 404, 422], \
            f"Unexpected status: {trigger_response.status_code}"
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/a2a/pipelines/{pipeline_id}")
        print(f"A2A trigger with empty body: {trigger_response.status_code}")


class TestOperatorJSONParsing(TestAuthSetup):
    """Test operator approve-plan - accept empty/non-JSON bodies"""
    
    def test_operator_approve_plan_with_empty_body(self, session, auth_token, workspace_id):
        """Operator approve-plan should handle empty body gracefully"""
        # Create an operator session first
        create_response = session.post(f"{BASE_URL}/api/workspaces/{workspace_id}/operator/sessions", json={
            "goal": "TEST_Audit_Goal: Analyze test data",
            "goal_type": "research",
            "auto_approve": False
        })
        
        if create_response.status_code != 200:
            pytest.skip(f"Could not create operator session: {create_response.text}")
        
        session_data = create_response.json()
        session_id = session_data.get("session_id")
        
        # Wait for planning
        time.sleep(2)
        
        # Try to approve with empty body - should not crash
        approve_response = session.post(
            f"{BASE_URL}/api/operator/sessions/{session_id}/approve-plan",
            data="",  # Empty body
            headers={"Content-Type": "application/json"}
        )
        # Should either succeed or return a clean error, not crash
        assert approve_response.status_code in [200, 400, 404, 422], \
            f"Unexpected status: {approve_response.status_code}"
        
        # Cleanup
        session.post(f"{BASE_URL}/api/operator/sessions/{session_id}/cancel")
        print(f"Operator approve with empty body: {approve_response.status_code}")


class TestNoSyntaxRegression(TestAuthSetup):
    """Test that touched files have no syntax/runtime regression"""
    
    def test_routes_openclaw_no_import_error(self, session, auth_token):
        """routes_openclaw.py should have no import errors"""
        # If OpenClaw health works, imports are fine
        response = session.get(f"{BASE_URL}/api/openclaw/health")
        assert response.status_code == 200, f"OpenClaw import error: {response.text}"
    
    def test_routes_tier23_no_import_error(self, session, auth_token):
        """routes_tier23.py should have no import errors"""
        # Test an endpoint from tier23
        response = session.get(f"{BASE_URL}/api/workflow-templates/extended")
        assert response.status_code == 200, f"Tier23 import error: {response.text}"
    
    def test_routes_research_no_import_error(self, session, auth_token):
        """routes_research.py should have no import errors"""
        # Test research config endpoint
        response = session.get(f"{BASE_URL}/api/research/config")
        assert response.status_code == 200, f"Research import error: {response.text}"
    
    def test_routes_media_no_import_error(self, session, auth_token):
        """routes_media.py should have no import errors"""
        # Test media config endpoint
        response = session.get(f"{BASE_URL}/api/media/config")
        assert response.status_code == 200, f"Media import error: {response.text}"
    
    def test_routes_mfa_no_import_error(self, session, auth_token):
        """routes_mfa.py should have no import errors"""
        # Test MFA status endpoint
        response = session.get(f"{BASE_URL}/api/auth/mfa/status")
        assert response.status_code == 200, f"MFA import error: {response.text}"
    
    def test_routes_a2a_pipelines_no_import_error(self, session, auth_token, workspace_id):
        """routes_a2a_pipelines.py should have no import errors"""
        # Test A2A templates endpoint
        response = session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/a2a/templates")
        assert response.status_code == 200, f"A2A import error: {response.text}"
    
    def test_routes_operator_no_import_error(self, session, auth_token, workspace_id):
        """routes_operator.py should have no import errors"""
        # Test operator templates endpoint
        response = session.get(f"{BASE_URL}/api/workspaces/{workspace_id}/operator/templates")
        assert response.status_code == 200, f"Operator import error: {response.text}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
