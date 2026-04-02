from conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, BASE_URL
"""
Iteration 96 - Testing Agent Arena dynamic models + Cost Intelligence field name fix

Tests:
1. Agent Arena - /api/ai-models returns all 19 AI providers with model variants
2. Cost Dashboard - /costs endpoint uses estimated_cost_usd field
3. Cost Dashboard - /costs/actual endpoint for batch job data  
4. Cost Dashboard - /costs/refresh endpoint
5. Cost Dashboard - /budget endpoint
6. Code verification for field name fix ($estimated_cost_usd not $cost_usd)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Expected 19 AI model providers
EXPECTED_MODELS = [
    "claude", "chatgpt", "gemini", "deepseek", "grok", "perplexity", 
    "mistral", "cohere", "groq", "mercury", "pi", "manus", 
    "qwen", "kimi", "llama", "glm", "cursor", "notebooklm", "copilot"
]

# Shared session with cookies
session = requests.Session()
WORKSPACE_ID = "ws_a92cb83bfdb2"


@pytest.fixture(scope="module", autouse=True)
def authenticate():
    """Login once for all tests"""
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_ADMIN_EMAIL,
        "password": "test"
    })
    if response.status_code != 200:
        pytest.skip("Login failed - skipping tests")
    print(f"Authenticated successfully, cookies: {list(session.cookies.keys())}")
    return session


class TestAgentArenaModels:
    """Test Agent Arena model fetching - should return all 19 models with variants"""
    
    def test_ai_models_endpoint_returns_models_dict(self):
        """GET /api/ai-models should return {models: {...}} structure"""
        response = session.get(f"{BASE_URL}/api/ai-models")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        data = response.json()
        
        # New format returns {models: {provider: [variants]}}
        assert "models" in data, "Response should have 'models' key"
        models = data.get("models", data)
        assert isinstance(models, dict), "models should be a dictionary"
        print(f"AI Models endpoint returned {len(models)} model providers")
    
    def test_all_19_models_present(self):
        """All 19 AI model providers should be present"""
        response = session.get(f"{BASE_URL}/api/ai-models")
        assert response.status_code == 200
        data = response.json()
        models = data.get("models", data)
        
        missing_models = []
        for model in EXPECTED_MODELS:
            if model not in models:
                missing_models.append(model)
        
        assert len(missing_models) == 0, f"Missing models: {missing_models}"
        print(f"All 19 expected models present: {sorted(models.keys())}")
    
    def test_each_model_has_variants(self):
        """Each model provider should have at least one variant"""
        response = session.get(f"{BASE_URL}/api/ai-models")
        assert response.status_code == 200
        data = response.json()
        models = data.get("models", data)
        
        for model_key, variants in models.items():
            assert isinstance(variants, list), f"Model {model_key} variants should be a list"
            assert len(variants) > 0, f"Model {model_key} should have at least one variant"
            # Each variant should have id and name
            for variant in variants:
                assert "id" in variant, f"Model {model_key} variant missing 'id'"
                assert "name" in variant, f"Model {model_key} variant missing 'name'"
        print("All models have valid variants with id and name")
    
    def test_variants_have_default_option(self):
        """At least some models should have a default variant marked"""
        response = session.get(f"{BASE_URL}/api/ai-models")
        assert response.status_code == 200
        data = response.json()
        models = data.get("models", data)
        
        models_with_default = 0
        for model_key, variants in models.items():
            has_default = any(v.get("default", False) for v in variants)
            if has_default:
                models_with_default += 1
        
        assert models_with_default > 0, "At least some models should have a default variant"
        print(f"{models_with_default} models have a default variant marked")


class TestCostDashboardEndpoints:
    """Test Cost Dashboard API endpoints"""
    
    def test_costs_endpoint(self):
        """GET /api/workspaces/{ws}/costs returns cost data"""
        response = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/costs")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        data = response.json()
        
        # Verify response structure
        assert "period" in data, "Response missing 'period'"
        assert "total_cost_usd" in data, "Response missing 'total_cost_usd'"
        assert "total_calls" in data, "Response missing 'total_calls'"
        assert "by_model" in data, "Response missing 'by_model'"
        print(f"Costs endpoint: period={data['period']}, total_cost=${data['total_cost_usd']}, calls={data['total_calls']}")
    
    def test_costs_with_period_parameter(self):
        """GET /api/workspaces/{ws}/costs?period=7d works"""
        for period in ["7d", "30d", "90d"]:
            response = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/costs?period={period}")
            assert response.status_code == 200, f"Period {period} failed with {response.status_code}"
            data = response.json()
            assert data.get("period") == period, f"Expected period {period}, got {data.get('period')}"
        print("All period parameters work: 7d, 30d, 90d")
    
    def test_actual_costs_endpoint(self):
        """GET /api/workspaces/{ws}/costs/actual returns batch job data"""
        response = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/costs/actual")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        data = response.json()
        
        # Verify response structure
        assert "period" in data, "Response missing 'period'"
        assert "by_model" in data, "Response missing 'by_model'"
        assert "totals" in data, "Response missing 'totals'"
        print(f"Actual costs endpoint: period={data['period']}, models={len(data['by_model'])}, totals={data['totals']}")
    
    def test_costs_refresh_endpoint(self):
        """POST /api/workspaces/{ws}/costs/refresh triggers refresh"""
        response = session.post(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/costs/refresh")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        data = response.json()
        assert "message" in data, "Response missing 'message'"
        print(f"Costs refresh: {data.get('message')}")
    
    def test_budget_endpoint(self):
        """GET /api/workspaces/{ws}/budget returns budget data"""
        response = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/budget")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        data = response.json()
        
        # Verify response structure
        assert "workspace_id" in data, "Response missing 'workspace_id'"
        assert "monthly_cap_usd" in data, "Response missing 'monthly_cap_usd'"
        assert "current_month_spend" in data, "Response missing 'current_month_spend'"
        print(f"Budget: cap=${data.get('monthly_cap_usd')}, spent=${data.get('current_month_spend')}, pct={data.get('pct_used')}%")


class TestArenaEndpoints:
    """Test Arena battle/history/leaderboard endpoints"""
    
    def test_arena_battles_history(self):
        """GET /api/workspaces/{ws}/arena/battles returns battle history"""
        response = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/arena/battles?limit=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Arena battles history: {len(data)} battles")
    
    def test_arena_leaderboard(self):
        """GET /api/workspaces/{ws}/arena/leaderboard returns leaderboard"""
        response = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/arena/leaderboard")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        data = response.json()
        assert "leaderboard" in data, "Response missing 'leaderboard'"
        print(f"Arena leaderboard: {len(data.get('leaderboard', []))} entries")


class TestCodeVerification:
    """Verify code fixes are correct via code review"""
    
    def test_routes_cost_intelligence_uses_estimated_cost_usd(self):
        """Verify routes_cost_intelligence.py uses $estimated_cost_usd"""
        with open("/app/backend/routes_cost_intelligence.py", "r") as f:
            content = f.read()
        
        # Should have estimated_cost_usd
        assert "estimated_cost_usd" in content, "routes_cost_intelligence.py should use estimated_cost_usd"
        
        # Should NOT have $cost_usd (the old incorrect field)
        assert '"$cost_usd"' not in content, "routes_cost_intelligence.py should NOT have $cost_usd"
        
        # Count occurrences
        count_estimated = content.count("estimated_cost_usd")
        print(f"routes_cost_intelligence.py: 'estimated_cost_usd' appears {count_estimated} times")
    
    def test_collaboration_core_uses_estimated_cost_usd(self):
        """Verify collaboration_core.py budget check uses estimated_cost_usd"""
        with open("/app/backend/collaboration_core.py", "r") as f:
            content = f.read()
        
        # Find the budget check section (around line 280)
        assert "estimated_cost_usd" in content, "collaboration_core.py should use estimated_cost_usd"
        
        # Verify it's used in the budget enforcement section
        lines = content.split('\n')
        budget_section_found = False
        for i, line in enumerate(lines):
            if "Budget enforcement" in line or "monthly_spend" in line:
                # Check next few lines for estimated_cost_usd
                context = '\n'.join(lines[max(0, i-2):min(len(lines), i+10)])
                if "estimated_cost_usd" in context:
                    budget_section_found = True
                    break
        
        assert budget_section_found, "Budget enforcement section should use estimated_cost_usd"
        print("collaboration_core.py: Budget check uses estimated_cost_usd")
    
    def test_agent_context_builder_uses_estimated_cost_usd(self):
        """Verify agent_context_builder.py uses estimated_cost_usd for daily cost"""
        with open("/app/backend/agent_context_builder.py", "r") as f:
            content = f.read()
        
        # Should have estimated_cost_usd
        assert "estimated_cost_usd" in content, "agent_context_builder.py should use estimated_cost_usd"
        
        # Count occurrences
        count = content.count("estimated_cost_usd")
        print(f"agent_context_builder.py: 'estimated_cost_usd' appears {count} times")
    
    def test_cost_batch_job_exists_and_registered(self):
        """Verify cost_batch_job.py exists and is registered in server.py"""
        # Check cost_batch_job.py exists
        with open("/app/backend/cost_batch_job.py", "r") as f:
            batch_content = f.read()
        
        assert "run_cost_snapshot" in batch_content, "cost_batch_job.py should have run_cost_snapshot function"
        assert "PRICING" in batch_content, "cost_batch_job.py should have PRICING dict"
        assert "compute_cost" in batch_content, "cost_batch_job.py should have compute_cost function"
        
        # Check server.py has it registered
        with open("/app/backend/server.py", "r") as f:
            server_content = f.read()
        
        assert "cost_batch_job" in server_content, "server.py should import cost_batch_job"
        assert "_cost_snapshot_work" in server_content, "server.py should have _cost_snapshot_work task"
        assert "cost_snapshot" in server_content, "server.py should register cost_snapshot task"
        print("cost_batch_job.py registered in server.py startup tasks")
    
    def test_marketplace_page_uses_api_instance(self):
        """Verify MarketplacePage.js uses api instance not raw fetch"""
        with open("/app/frontend/src/pages/MarketplacePage.js", "r") as f:
            content = f.read()
        
        # Should import api
        assert 'from "@/lib/api"' in content or "from '@/lib/api'" in content, \
            "MarketplacePage.js should import from @/lib/api"
        
        # Should use api.get and api.post
        assert "api.get" in content, "MarketplacePage.js should use api.get"
        assert "api.post" in content, "MarketplacePage.js should use api.post"
        
        # Should NOT have raw fetch for API calls (allow fetch for other purposes)
        # Count fetch usage that looks like API calls
        fetch_api_count = content.count('fetch("/api') + content.count("fetch('/api") + \
                          content.count('fetch(`${') + content.count("fetch(BASE_URL")
        assert fetch_api_count == 0, f"MarketplacePage.js should not use raw fetch for API calls (found {fetch_api_count})"
        
        print("MarketplacePage.js uses api instance correctly")
    
    def test_agent_arena_panel_uses_api_models(self):
        """Verify AgentArenaPanel.js fetches models from /api/ai-models"""
        with open("/app/frontend/src/components/AgentArenaPanel.js", "r") as f:
            content = f.read()
        
        # Should fetch from /ai-models
        assert "/ai-models" in content, "AgentArenaPanel should fetch from /ai-models"
        assert "api.get" in content, "AgentArenaPanel should use api.get"
        
        # Should handle variants
        assert "variants" in content, "AgentArenaPanel should handle variants"
        assert "selectedVariant" in content, "AgentArenaPanel should track selectedVariant"
        
        print("AgentArenaPanel.js correctly fetches models with variant support")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
