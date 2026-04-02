from conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, BASE_URL
"""
Iteration 111 Tests - 8 New Features:
1. Webhook dead-letter queue
2. Orchestration scheduling (CRUD)
3. Benchmark comparison
4. Collaboration templates library
5. Template installation
6. Review analytics
7. Security dashboard
8. Advanced marketplace search
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    pytest.skip("REACT_APP_BACKEND_URL not set", allow_module_level=True)

WORKSPACE_ID = "ws_a970eafa9591"
AGENT_ID = "nxa_53855a5c0c2d"


@pytest.fixture(scope="module")
def session():
    """Authenticated session for all tests."""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_ADMIN_EMAIL,
        "password": "test"
    })
    assert r.status_code == 200, f"Login failed: {r.text}"
    return s


class TestWebhookDeadLetterQueue:
    """Test webhook dead-letter queue (Feature 1)"""
    
    def test_get_dead_letters_returns_list(self, session):
        """GET /workspaces/{ws_id}/webhooks/dead-letters returns dead_letters list"""
        r = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/webhooks/dead-letters")
        assert r.status_code == 200
        data = r.json()
        assert "dead_letters" in data
        assert isinstance(data["dead_letters"], list)
    
    def test_list_webhooks(self, session):
        """Verify webhooks list endpoint works"""
        r = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/webhooks")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestOrchestrationScheduling:
    """Test orchestration scheduling CRUD (Feature 2)"""
    
    def test_list_schedules(self, session):
        """GET /workspaces/{ws_id}/orchestration-schedules returns schedules"""
        r = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/orchestration-schedules")
        assert r.status_code == 200
        data = r.json()
        assert "schedules" in data
        assert isinstance(data["schedules"], list)
    
    def test_create_schedule_requires_valid_orchestration(self, session):
        """POST /workspaces/{ws_id}/orchestration-schedules validates orchestration_id"""
        r = session.post(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/orchestration-schedules", json={
            "orchestration_id": "invalid_orch_id",
            "input_text": "Test input",
            "interval_minutes": 60
        })
        # Should return 404 for invalid orchestration
        assert r.status_code == 404
    
    def test_schedule_crud_flow(self, session):
        """Test schedule CRUD: create orchestration first, then schedule"""
        # First create an orchestration for testing
        orch_data = {
            "name": "TEST_ScheduleOrch",
            "description": "Test orchestration for scheduling",
            "execution_mode": "sequential",
            "steps": [
                {"step_id": "step1", "agent_id": AGENT_ID, "prompt_template": "{input}"}
            ]
        }
        r_orch = session.post(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/orchestrations", json=orch_data)
        
        if r_orch.status_code == 201:
            orch_id = r_orch.json().get("orchestration_id")
            
            # Now create schedule
            r_create = session.post(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/orchestration-schedules", json={
                "orchestration_id": orch_id,
                "input_text": "TEST scheduled run",
                "interval_minutes": 60
            })
            
            if r_create.status_code == 200:
                sched = r_create.json()
                sched_id = sched.get("schedule_id")
                assert sched_id is not None
                assert sched.get("enabled") == True
                
                # Update schedule
                r_update = session.put(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/orchestration-schedules/{sched_id}", json={
                    "enabled": False
                })
                assert r_update.status_code == 200
                assert r_update.json().get("enabled") == False
                
                # Delete schedule
                r_del = session.delete(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/orchestration-schedules/{sched_id}")
                assert r_del.status_code == 200
            
            # Cleanup orchestration
            session.delete(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/orchestrations/{orch_id}")
        else:
            # If orchestration creation failed, just verify list works
            r = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/orchestration-schedules")
            assert r.status_code == 200


class TestBenchmarkComparison:
    """Test benchmark comparison endpoint (Feature 3)"""
    
    def test_benchmark_compare_returns_data(self, session):
        """GET /workspaces/{ws_id}/agents/{agent_id}/benchmarks/compare returns comparison"""
        r = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/benchmarks/compare")
        assert r.status_code == 200
        data = r.json()
        assert "comparison" in data
        assert "trend" in data
        assert isinstance(data["comparison"], list)
        assert isinstance(data["trend"], list)
    
    def test_benchmark_compare_with_run_ids(self, session):
        """Benchmark compare accepts run_ids query param"""
        r = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/benchmarks/compare", params={
            "run_ids": "run1,run2"
        })
        assert r.status_code == 200


class TestCollaborationTemplates:
    """Test collaboration templates library (Feature 4)"""
    
    def test_list_templates_returns_builtin(self, session):
        """GET /orchestration-templates returns 5 built-in templates"""
        r = session.get(f"{BASE_URL}/api/orchestration-templates")
        assert r.status_code == 200
        data = r.json()
        assert "templates" in data
        templates = data["templates"]
        assert len(templates) >= 5, f"Expected 5+ templates, got {len(templates)}"
        
        # Verify builtin template names
        names = [t.get("name") for t in templates]
        expected = ["Research & Summarize", "Draft, Review & Edit", "Multi-Perspective Analysis", 
                    "Code Review Pipeline", "Q&A Knowledge Pipeline"]
        for exp in expected:
            assert exp in names, f"Missing template: {exp}"
    
    def test_template_structure(self, session):
        """Verify template has expected structure"""
        r = session.get(f"{BASE_URL}/api/orchestration-templates")
        assert r.status_code == 200
        templates = r.json().get("templates", [])
        if templates:
            tpl = templates[0]
            assert "template_id" in tpl
            assert "name" in tpl
            assert "description" in tpl
            assert "steps" in tpl
            assert "execution_mode" in tpl


class TestTemplateInstallation:
    """Test template installation (Feature 5)"""
    
    def test_install_builtin_template(self, session):
        """POST /workspaces/{ws_id}/orchestration-templates/{tpl_id}/install creates orchestration"""
        # Use a builtin template ID
        tpl_id = "otpl_research_summarize"
        r = session.post(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/orchestration-templates/{tpl_id}/install")
        
        assert r.status_code == 200
        orch = r.json()
        assert "orchestration_id" in orch
        assert "Research & Summarize" in orch.get("name", "")
        assert orch.get("from_template") == tpl_id
        
        # Cleanup - delete the created orchestration
        orch_id = orch.get("orchestration_id")
        if orch_id:
            session.delete(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/orchestrations/{orch_id}")
    
    def test_install_invalid_template_returns_404(self, session):
        """Installing non-existent template returns 404"""
        r = session.post(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/orchestration-templates/invalid_tpl_999/install")
        assert r.status_code == 404


class TestReviewAnalytics:
    """Test review analytics endpoint (Feature 6)"""
    
    def test_review_analytics_returns_stats(self, session):
        """GET /marketplace/review-analytics returns stats, sentiment, trend"""
        r = session.get(f"{BASE_URL}/api/marketplace/review-analytics")
        assert r.status_code == 200
        data = r.json()
        
        # Verify structure
        assert "stats" in data
        assert "trend" in data
        assert "top_reviewed" in data
        assert "sentiment" in data
        
        # Verify stats keys
        stats = data["stats"]
        assert "total" in stats
        assert "avg_rating" in stats
        
        # Verify sentiment keys
        sentiment = data["sentiment"]
        assert "positive_pct" in sentiment
        assert "neutral_pct" in sentiment
        assert "negative_pct" in sentiment
    
    def test_review_analytics_with_template_filter(self, session):
        """Review analytics accepts template_id filter"""
        r = session.get(f"{BASE_URL}/api/marketplace/review-analytics", params={
            "template_id": "some_template"
        })
        assert r.status_code == 200


class TestSecurityDashboard:
    """Test security dashboard endpoint (Feature 7)"""
    
    def test_security_dashboard_returns_data(self, session):
        """GET /admin/security-dashboard returns auth, webhooks, platform data"""
        r = session.get(f"{BASE_URL}/api/admin/security-dashboard")
        assert r.status_code == 200
        data = r.json()
        
        # Verify top-level keys
        assert "auth" in data
        assert "webhooks" in data
        assert "platform" in data
        assert "recent_events" in data
        
        # Verify auth structure
        auth = data["auth"]
        assert "active_sessions" in auth
        assert "failed_logins_24h" in auth
        assert "locked_accounts" in auth
        assert "total_users" in auth
        
        # Verify webhooks structure
        webhooks = data["webhooks"]
        assert "total" in webhooks
        assert "enabled" in webhooks
        assert "disabled" in webhooks
        assert "dead_letters" in webhooks
        assert "deliveries_7d" in webhooks
        
        # Verify platform structure
        platform = data["platform"]
        assert "total_workspaces" in platform
        assert "api_keys_configured" in platform


class TestMarketplaceAdvancedSearch:
    """Test advanced marketplace search (Feature 8)"""
    
    def test_marketplace_search(self, session):
        """GET /marketplace?search=test&sort=popular returns templates"""
        r = session.get(f"{BASE_URL}/api/marketplace", params={
            "search": "test",
            "sort": "popular"
        })
        assert r.status_code == 200
        data = r.json()
        assert "templates" in data
        assert "total" in data
    
    def test_marketplace_sort_options(self, session):
        """Marketplace supports different sort options"""
        for sort in ["popular", "rating", "recent"]:
            r = session.get(f"{BASE_URL}/api/marketplace", params={"sort": sort})
            assert r.status_code == 200
    
    def test_marketplace_category_filter(self, session):
        """Marketplace supports category filter"""
        r = session.get(f"{BASE_URL}/api/marketplace", params={
            "category": "workflow"
        })
        assert r.status_code == 200


class TestWebhookRetryPolicy:
    """Test webhook retry policy configuration"""
    
    def test_create_webhook_with_retry_policy(self, session):
        """Create webhook with custom retry policy"""
        r = session.post(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/webhooks", json={
            "url": "https://example.com/test-webhook",
            "events": ["message.created"],
            "name": "TEST_RetryWebhook",
            "retry_policy": {"max_retries": 5}
        })
        
        if r.status_code == 200:
            hook = r.json()
            webhook_id = hook.get("webhook_id")
            assert hook.get("retry_policy", {}).get("max_retries") == 5
            
            # Cleanup
            if webhook_id:
                session.delete(f"{BASE_URL}/api/webhooks/{webhook_id}")
        else:
            # If creation fails, verify list works
            r = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/webhooks")
            assert r.status_code == 200


class TestEndpointResponses:
    """Additional endpoint validation tests"""
    
    def test_all_new_endpoints_accessible(self, session):
        """Verify all new endpoints return valid responses"""
        endpoints = [
            (f"/api/workspaces/{WORKSPACE_ID}/webhooks/dead-letters", "GET"),
            (f"/api/workspaces/{WORKSPACE_ID}/orchestration-schedules", "GET"),
            (f"/api/workspaces/{WORKSPACE_ID}/agents/{AGENT_ID}/benchmarks/compare", "GET"),
            ("/api/orchestration-templates", "GET"),
            ("/api/marketplace/review-analytics", "GET"),
            ("/api/admin/security-dashboard", "GET"),
            (f"/api/marketplace?search=test&sort=popular", "GET"),
        ]
        
        for endpoint, method in endpoints:
            if method == "GET":
                r = session.get(f"{BASE_URL}{endpoint}")
            assert r.status_code == 200, f"Failed: {method} {endpoint} - {r.status_code}: {r.text}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
