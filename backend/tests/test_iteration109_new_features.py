from conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, BASE_URL
"""
Iteration 109 - Testing 5 New Features:
1. Multi-Agent Orchestration
2. Fine-Tuning Pipeline 
3. Marketplace Reviews & Ratings
4. Webhook Integrations
5. Agent Performance Benchmarks
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8080")

class TestSession:
    """Shared session for all tests"""
    session = requests.Session()
    session_token = None
    workspace_id = "ws_a970eafa9591"
    agent_id = None  # Will be set after creating agent
    orchestration_id = None
    webhook_id = None
    dataset_id = None
    finetune_job_id = None
    benchmark_suite_id = None
    benchmark_run_id = None
    marketplace_template_id = None
    review_id = None


@pytest.fixture(scope="module", autouse=True)
def setup_session():
    """Login and get session token"""
    login_resp = TestSession.session.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_ADMIN_EMAIL, "password": "test"}
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    
    # Extract session token from cookies
    TestSession.session_token = TestSession.session.cookies.get("session_token")
    assert TestSession.session_token, "No session token in cookies"
    
    yield
    
    # Cleanup after tests
    # Delete test agent if created
    if TestSession.agent_id:
        TestSession.session.delete(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/agents/{TestSession.agent_id}"
        )


# =====================================================
# ORCHESTRATION TESTS (Multi-Agent Orchestration)
# =====================================================

class TestOrchestration:
    """Test Multi-Agent Orchestration endpoints"""
    
    def test_list_orchestrations_empty(self):
        """Test listing orchestrations when none exist"""
        resp = TestSession.session.get(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/orchestrations"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "orchestrations" in data
        assert isinstance(data["orchestrations"], list)
    
    def test_create_agent_for_orchestration(self):
        """Create an agent to use in orchestration"""
        resp = TestSession.session.post(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/agents",
            json={
                "name": "Orchestration Test Agent",
                "description": "Agent for orchestration testing",
                "base_model": "claude",
                "system_prompt": "You are a helpful assistant for orchestration tests.",
                "skills": ["orchestration", "testing"]
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "agent_id" in data
        TestSession.agent_id = data["agent_id"]
    
    def test_create_orchestration(self):
        """Test creating a new orchestration"""
        resp = TestSession.session.post(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/orchestrations",
            json={
                "name": "Test Orchestration Pipeline",
                "description": "A test orchestration for QA",
                "execution_mode": "sequential",
                "steps": [
                    {
                        "agent_id": TestSession.agent_id,
                        "prompt_template": "{input}",
                        "condition": ""
                    }
                ]
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "orchestration_id" in data
        assert data["name"] == "Test Orchestration Pipeline"
        assert data["execution_mode"] == "sequential"
        assert len(data["steps"]) == 1
        TestSession.orchestration_id = data["orchestration_id"]
    
    def test_list_orchestrations(self):
        """Test listing orchestrations after creation"""
        resp = TestSession.session.get(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/orchestrations"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["orchestrations"]) >= 1
        # Find our orchestration
        orch = next((o for o in data["orchestrations"] if o["orchestration_id"] == TestSession.orchestration_id), None)
        assert orch is not None
    
    def test_get_orchestration_detail(self):
        """Test getting orchestration detail"""
        resp = TestSession.session.get(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/orchestrations/{TestSession.orchestration_id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["orchestration_id"] == TestSession.orchestration_id
        assert data["name"] == "Test Orchestration Pipeline"
    
    def test_run_orchestration(self):
        """Test running an orchestration"""
        resp = TestSession.session.post(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/orchestrations/{TestSession.orchestration_id}/run",
            json={
                "input_text": "Test input for orchestration run",
                "context": {"test_key": "test_value"}
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data
        assert data["status"] in ["running", "completed", "queued"]
        TestSession.orchestration_run_id = data["run_id"]
    
    def test_list_orchestration_runs(self):
        """Test listing orchestration runs"""
        resp = TestSession.session.get(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/orchestrations/{TestSession.orchestration_id}/runs"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "runs" in data
        assert isinstance(data["runs"], list)
    
    def test_get_orchestration_run_detail(self):
        """Test getting orchestration run detail"""
        # Wait briefly for run to complete
        time.sleep(1)
        resp = TestSession.session.get(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/orchestration-runs/{TestSession.orchestration_run_id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == TestSession.orchestration_run_id
        assert "status" in data
        assert "step_results" in data
    
    def test_delete_orchestration(self):
        """Test deleting orchestration"""
        resp = TestSession.session.delete(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/orchestrations/{TestSession.orchestration_id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] == TestSession.orchestration_id


# =====================================================
# WEBHOOK TESTS
# =====================================================

class TestWebhooks:
    """Test Webhook Integration endpoints"""
    
    def test_list_webhooks_empty(self):
        """Test listing webhooks"""
        resp = TestSession.session.get(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/webhooks"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
    
    def test_get_webhook_events(self):
        """Test getting available webhook events"""
        resp = TestSession.session.get(
            f"{BASE_URL}/api/webhooks/events"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert "message.created" in data["events"]
        assert "task.created" in data["events"]
    
    def test_create_webhook(self):
        """Test creating a webhook"""
        resp = TestSession.session.post(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/webhooks",
            json={
                "url": "https://httpbin.org/post",
                "name": "Test Webhook",
                "events": ["message.created", "task.created"],
                "secret": "test_secret_123"
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "webhook_id" in data
        assert data["name"] == "Test Webhook"
        assert data["enabled"] == True
        assert len(data["events"]) == 2
        TestSession.webhook_id = data["webhook_id"]
    
    def test_list_webhooks_after_create(self):
        """Test listing webhooks after creation"""
        resp = TestSession.session.get(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/webhooks"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        # Find our webhook
        webhook = next((w for w in data if w["webhook_id"] == TestSession.webhook_id), None)
        assert webhook is not None
    
    def test_toggle_webhook_disable(self):
        """Test disabling a webhook"""
        resp = TestSession.session.put(
            f"{BASE_URL}/api/webhooks/{TestSession.webhook_id}",
            json={"enabled": False}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] == False
    
    def test_toggle_webhook_enable(self):
        """Test enabling a webhook"""
        resp = TestSession.session.put(
            f"{BASE_URL}/api/webhooks/{TestSession.webhook_id}",
            json={"enabled": True}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] == True
    
    def test_test_webhook(self):
        """Test sending a test webhook"""
        resp = TestSession.session.post(
            f"{BASE_URL}/api/webhooks/{TestSession.webhook_id}/test"
        )
        assert resp.status_code == 200
        data = resp.json()
        # The test may succeed or fail depending on external service, but endpoint should work
        assert "success" in data
        assert "status_code" in data
        assert "delivery_id" in data
    
    def test_get_webhook_deliveries(self):
        """Test getting webhook deliveries"""
        resp = TestSession.session.get(
            f"{BASE_URL}/api/webhooks/{TestSession.webhook_id}/deliveries"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Should have at least 1 delivery from test
        assert len(data) >= 1
    
    def test_delete_webhook(self):
        """Test deleting a webhook"""
        resp = TestSession.session.delete(
            f"{BASE_URL}/api/webhooks/{TestSession.webhook_id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Webhook deleted"


# =====================================================
# FINE-TUNING TESTS
# =====================================================

class TestFineTuning:
    """Test Fine-Tuning Pipeline endpoints"""
    
    def test_list_datasets_empty(self):
        """Test listing datasets when none exist"""
        # First ensure we have an agent
        if not TestSession.agent_id:
            resp = TestSession.session.post(
                f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/agents",
                json={
                    "name": "FineTune Test Agent",
                    "description": "Agent for fine-tuning testing",
                    "base_model": "claude",
                    "system_prompt": "You are a fine-tuning test assistant.",
                    "skills": ["finetune", "testing"]
                }
            )
            assert resp.status_code == 200
            TestSession.agent_id = resp.json()["agent_id"]
        
        resp = TestSession.session.get(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/agents/{TestSession.agent_id}/finetune/datasets"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "datasets" in data
        assert isinstance(data["datasets"], list)
    
    def test_create_dataset(self):
        """Test creating a training dataset"""
        resp = TestSession.session.post(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/agents/{TestSession.agent_id}/finetune/datasets",
            json={
                "name": "Test Training Dataset",
                "include_knowledge": True,
                "include_conversations": True,
                "min_quality_score": 0.5,
                "max_examples": 100
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "dataset_id" in data
        assert data["name"] == "Test Training Dataset"
        assert "example_count" in data  # May be 0 if no knowledge exists
        TestSession.dataset_id = data["dataset_id"]
    
    def test_list_datasets(self):
        """Test listing datasets after creation"""
        resp = TestSession.session.get(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/agents/{TestSession.agent_id}/finetune/datasets"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["datasets"]) >= 1
    
    def test_export_dataset(self):
        """Test exporting dataset as JSONL"""
        resp = TestSession.session.get(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/agents/{TestSession.agent_id}/finetune/datasets/{TestSession.dataset_id}/export"
        )
        assert resp.status_code == 200
        # Should return JSONL content
        assert resp.headers.get("Content-Type") == "application/jsonl"
    
    def test_list_finetune_jobs_empty(self):
        """Test listing fine-tune jobs"""
        resp = TestSession.session.get(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/agents/{TestSession.agent_id}/finetune/jobs"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "jobs" in data
        assert isinstance(data["jobs"], list)
    
    def test_create_finetune_job(self):
        """Test creating a fine-tune job"""
        resp = TestSession.session.post(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/agents/{TestSession.agent_id}/finetune/jobs",
            json={
                "dataset_id": TestSession.dataset_id,
                "base_model": "claude-sonnet-4-5-20250929",
                "provider": "anthropic"
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data
        assert data["status"] in ["running", "queued", "evaluating_dataset", "generating_prompt"]
        TestSession.finetune_job_id = data["job_id"]
    
    def test_get_finetune_job(self):
        """Test getting fine-tune job detail"""
        # Wait a bit for job to progress
        time.sleep(2)
        resp = TestSession.session.get(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/agents/{TestSession.agent_id}/finetune/jobs/{TestSession.finetune_job_id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == TestSession.finetune_job_id
        assert "status" in data
        assert "progress" in data
    
    def test_delete_dataset(self):
        """Test deleting a dataset"""
        resp = TestSession.session.delete(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/agents/{TestSession.agent_id}/finetune/datasets/{TestSession.dataset_id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] == TestSession.dataset_id


# =====================================================
# BENCHMARK TESTS
# =====================================================

class TestBenchmarks:
    """Test Agent Performance Benchmark endpoints"""
    
    def test_list_benchmark_suites_empty(self):
        """Test listing benchmark suites"""
        if not TestSession.agent_id:
            pytest.skip("No agent created")
        
        resp = TestSession.session.get(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/agents/{TestSession.agent_id}/benchmarks/suites"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "suites" in data
        assert isinstance(data["suites"], list)
    
    def test_create_benchmark_suite(self):
        """Test creating a benchmark suite"""
        resp = TestSession.session.post(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/agents/{TestSession.agent_id}/benchmarks/suites",
            json={
                "name": "Test Benchmark Suite",
                "cases": [
                    {
                        "question": "What is the capital of France?",
                        "expected_keywords": ["Paris", "France", "capital"],
                        "expected_topic": "geography",
                        "category": "knowledge"
                    },
                    {
                        "question": "Explain the process of photosynthesis",
                        "expected_keywords": ["sunlight", "chlorophyll", "glucose"],
                        "expected_topic": "biology",
                        "category": "reasoning"
                    }
                ]
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "suite_id" in data
        assert data["name"] == "Test Benchmark Suite"
        assert data["case_count"] == 2
        TestSession.benchmark_suite_id = data["suite_id"]
    
    def test_list_benchmark_suites(self):
        """Test listing benchmark suites after creation"""
        resp = TestSession.session.get(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/agents/{TestSession.agent_id}/benchmarks/suites"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["suites"]) >= 1
    
    def test_run_benchmark(self):
        """Test running a benchmark"""
        resp = TestSession.session.post(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/agents/{TestSession.agent_id}/benchmarks/run",
            json={"suite_id": TestSession.benchmark_suite_id}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data
        assert data["status"] in ["running", "queued"]
        TestSession.benchmark_run_id = data["run_id"]
    
    def test_list_benchmark_runs(self):
        """Test listing benchmark runs"""
        resp = TestSession.session.get(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/agents/{TestSession.agent_id}/benchmarks/runs"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "runs" in data
        assert isinstance(data["runs"], list)
    
    def test_get_benchmark_run_detail(self):
        """Test getting benchmark run detail"""
        # Wait for benchmark to complete
        time.sleep(2)
        resp = TestSession.session.get(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/agents/{TestSession.agent_id}/benchmarks/runs/{TestSession.benchmark_run_id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == TestSession.benchmark_run_id
        assert "status" in data
        assert "results" in data
    
    def test_delete_benchmark_suite(self):
        """Test deleting a benchmark suite"""
        resp = TestSession.session.delete(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/agents/{TestSession.agent_id}/benchmarks/suites/{TestSession.benchmark_suite_id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] == TestSession.benchmark_suite_id


# =====================================================
# MARKETPLACE REVIEWS TESTS
# =====================================================

class TestMarketplaceReviews:
    """Test Marketplace Reviews & Ratings endpoints"""
    
    def test_get_marketplace_templates(self):
        """Test getting marketplace templates to review"""
        resp = TestSession.session.get(f"{BASE_URL}/api/marketplace")
        assert resp.status_code == 200
        data = resp.json()
        assert "templates" in data or isinstance(data, list)
        templates = data.get("templates", data) if isinstance(data, dict) else data
        if templates:
            TestSession.marketplace_template_id = templates[0].get("marketplace_id")
    
    def test_list_reviews_empty(self):
        """Test listing reviews for a template"""
        if not TestSession.marketplace_template_id:
            pytest.skip("No marketplace template available")
        
        resp = TestSession.session.get(
            f"{BASE_URL}/api/marketplace/{TestSession.marketplace_template_id}/reviews"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "reviews" in data
        assert "rating_breakdown" in data
    
    def test_create_review(self):
        """Test creating a review"""
        if not TestSession.marketplace_template_id:
            pytest.skip("No marketplace template available")
        
        resp = TestSession.session.post(
            f"{BASE_URL}/api/marketplace/{TestSession.marketplace_template_id}/reviews",
            json={
                "rating": 4,
                "title": "Great Template!",
                "content": "This template is very useful for testing purposes."
            }
        )
        # May fail if user already reviewed or is the publisher
        if resp.status_code == 200:
            data = resp.json()
            assert "review_id" in data
            assert data["rating"] == 4
            TestSession.review_id = data["review_id"]
        else:
            # 400 means already reviewed or own template
            assert resp.status_code == 400
            TestSession.review_id = None
    
    def test_list_reviews_with_sort(self):
        """Test listing reviews with different sort options"""
        if not TestSession.marketplace_template_id:
            pytest.skip("No marketplace template available")
        
        for sort_opt in ["recent", "rating", "helpful"]:
            resp = TestSession.session.get(
                f"{BASE_URL}/api/marketplace/{TestSession.marketplace_template_id}/reviews?sort={sort_opt}"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "reviews" in data
    
    def test_mark_review_helpful(self):
        """Test marking a review as helpful"""
        if not TestSession.marketplace_template_id:
            pytest.skip("No marketplace template available")
        
        # First get a review to mark helpful
        resp = TestSession.session.get(
            f"{BASE_URL}/api/marketplace/{TestSession.marketplace_template_id}/reviews"
        )
        reviews = resp.json().get("reviews", [])
        if not reviews:
            pytest.skip("No reviews to mark helpful")
        
        review_id = reviews[0]["review_id"]
        resp = TestSession.session.post(
            f"{BASE_URL}/api/marketplace/{TestSession.marketplace_template_id}/reviews/{review_id}/helpful"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["marked_helpful"] == review_id
    
    def test_flag_review(self):
        """Test flagging a review"""
        if not TestSession.marketplace_template_id:
            pytest.skip("No marketplace template available")
        
        # Get a review to flag
        resp = TestSession.session.get(
            f"{BASE_URL}/api/marketplace/{TestSession.marketplace_template_id}/reviews"
        )
        reviews = resp.json().get("reviews", [])
        if not reviews:
            pytest.skip("No reviews to flag")
        
        review_id = reviews[0]["review_id"]
        resp = TestSession.session.post(
            f"{BASE_URL}/api/marketplace/{TestSession.marketplace_template_id}/reviews/{review_id}/flag",
            json={"reason": "test_flag"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["flagged"] == review_id
    
    def test_update_review(self):
        """Test updating a review"""
        if not TestSession.review_id:
            pytest.skip("No review created to update")
        
        resp = TestSession.session.put(
            f"{BASE_URL}/api/marketplace/{TestSession.marketplace_template_id}/reviews/{TestSession.review_id}",
            json={
                "rating": 5,
                "title": "Updated: Excellent Template!",
                "content": "Updated review content - even better after more testing."
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated"] == TestSession.review_id
    
    def test_delete_review(self):
        """Test deleting a review"""
        if not TestSession.review_id:
            pytest.skip("No review created to delete")
        
        resp = TestSession.session.delete(
            f"{BASE_URL}/api/marketplace/{TestSession.marketplace_template_id}/reviews/{TestSession.review_id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] == TestSession.review_id


# =====================================================
# CLEANUP - Delete test agent at the end
# =====================================================

class TestCleanup:
    """Cleanup test data"""
    
    def test_delete_test_agent(self):
        """Delete the test agent created during tests"""
        if not TestSession.agent_id:
            pytest.skip("No agent to delete")
        
        resp = TestSession.session.delete(
            f"{BASE_URL}/api/workspaces/{TestSession.workspace_id}/agents/{TestSession.agent_id}"
        )
        assert resp.status_code == 200
        TestSession.agent_id = None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
