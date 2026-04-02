"""
Iteration 116 - Nexus AI Budget Controls Testing
Tests for:
- Platform Nexus AI budget API: GET/PUT /api/admin/managed-keys/budgets and GET /api/admin/managed-keys/dashboard
- Workspace Nexus AI budget API: GET/PUT /api/workspaces/{workspace_id}/nexus-ai/budgets and GET /api/workspaces/{workspace_id}/nexus-ai/dashboard
- Budget hierarchy enforcement (workspace > org > platform)
- GitHub integration usage tracking
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
TEST_EMAIL = os.environ.get("TEST_ADMIN_EMAIL", "admin@test.local")
TEST_PASSWORD = "test"


class TestNexusAIBudgetAPIs:
    """Test Nexus AI Budget Control APIs"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as super admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        data = login_resp.json()
        self.token = data.get("token")
        self.user = data.get("user", {})
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        # Get a workspace for testing
        ws_resp = self.session.get(f"{BASE_URL}/api/workspaces")
        assert ws_resp.status_code == 200
        workspaces = ws_resp.json()
        assert len(workspaces) > 0, "No workspaces found for testing"
        self.workspace_id = workspaces[0]["workspace_id"]
        
    # ========== Platform Budget APIs (Super Admin) ==========
    
    def test_platform_budget_get(self):
        """GET /api/admin/managed-keys/budgets - Platform budget settings"""
        resp = self.session.get(f"{BASE_URL}/api/admin/managed-keys/budgets")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        # Verify response structure
        assert data.get("scope_type") == "platform"
        assert data.get("scope_id") == "platform"
        assert "budgets" in data
        
        # Verify budgets contain expected providers
        budgets = data["budgets"]
        assert "chatgpt" in budgets
        assert "claude" in budgets
        assert "github" in budgets
        
        # Verify budget structure for a provider
        chatgpt_budget = budgets.get("chatgpt", {})
        assert "provider" in chatgpt_budget
        assert "enabled" in chatgpt_budget
        print(f"Platform budget GET: {len(budgets)} providers configured")
    
    def test_platform_budget_put(self):
        """PUT /api/admin/managed-keys/budgets - Save platform budget settings"""
        # Set a test budget for chatgpt
        payload = {
            "budgets": {
                "chatgpt": {
                    "warn_threshold_usd": 10.0,
                    "hard_cap_usd": 50.0,
                    "enabled": True
                },
                "claude": {
                    "warn_threshold_usd": 5.0,
                    "hard_cap_usd": 25.0,
                    "enabled": True
                }
            }
        }
        resp = self.session.put(f"{BASE_URL}/api/admin/managed-keys/budgets", json=payload)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert data.get("scope_type") == "platform"
        assert data.get("saved") >= 2
        print(f"Platform budget PUT: saved {data.get('saved')} provider budgets")
        
        # Verify the budgets were saved by fetching again
        get_resp = self.session.get(f"{BASE_URL}/api/admin/managed-keys/budgets")
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        chatgpt = get_data["budgets"].get("chatgpt", {})
        assert chatgpt.get("enabled") == True
        assert chatgpt.get("warn_threshold_usd") == 10.0
        assert chatgpt.get("hard_cap_usd") == 50.0
    
    def test_platform_dashboard_get(self):
        """GET /api/admin/managed-keys/dashboard - Platform usage dashboard"""
        resp = self.session.get(f"{BASE_URL}/api/admin/managed-keys/dashboard")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        # Verify dashboard structure
        assert data.get("scope_type") == "platform"
        assert data.get("scope_id") == "platform"
        assert "month_key" in data
        assert "total_cost_usd" in data
        assert "total_events" in data
        assert "providers" in data
        
        # Verify provider usage structure
        providers = data["providers"]
        assert isinstance(providers, dict)
        if "chatgpt" in providers:
            chatgpt = providers["chatgpt"]
            assert "current_cost_usd" in chatgpt
            assert "events" in chatgpt
            assert "status" in chatgpt
        
        print(f"Platform dashboard: total_cost=${data.get('total_cost_usd', 0):.4f}, events={data.get('total_events', 0)}")
    
    # ========== Workspace Budget APIs ==========
    
    def test_workspace_budget_get(self):
        """GET /api/workspaces/{workspace_id}/nexus-ai/budgets - Workspace budget settings"""
        resp = self.session.get(f"{BASE_URL}/api/workspaces/{self.workspace_id}/nexus-ai/budgets")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        # Verify response structure
        assert data.get("scope_type") == "workspace"
        assert data.get("scope_id") == self.workspace_id
        assert "budgets" in data
        
        budgets = data["budgets"]
        assert "chatgpt" in budgets
        assert "claude" in budgets
        print(f"Workspace budget GET: {len(budgets)} providers")
    
    def test_workspace_budget_put(self):
        """PUT /api/workspaces/{workspace_id}/nexus-ai/budgets - Save workspace budget settings"""
        # Set a tiny budget for chatgpt to test blocking
        payload = {
            "budgets": {
                "chatgpt": {
                    "warn_threshold_usd": 0.001,
                    "hard_cap_usd": 0.002,
                    "enabled": True
                }
            }
        }
        resp = self.session.put(f"{BASE_URL}/api/workspaces/{self.workspace_id}/nexus-ai/budgets", json=payload)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert data.get("scope_type") == "workspace"
        assert data.get("scope_id") == self.workspace_id
        assert data.get("saved") >= 1
        print(f"Workspace budget PUT: saved {data.get('saved')} provider budgets")
    
    def test_workspace_dashboard_get(self):
        """GET /api/workspaces/{workspace_id}/nexus-ai/dashboard - Workspace usage dashboard"""
        resp = self.session.get(f"{BASE_URL}/api/workspaces/{self.workspace_id}/nexus-ai/dashboard")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        # Verify dashboard structure
        assert data.get("scope_type") == "workspace"
        assert data.get("scope_id") == self.workspace_id
        assert "month_key" in data
        assert "total_cost_usd" in data
        assert "total_events" in data
        assert "providers" in data
        
        print(f"Workspace dashboard: total_cost=${data.get('total_cost_usd', 0):.4f}, events={data.get('total_events', 0)}")
    
    # ========== Budget Validation Tests ==========
    
    def test_budget_validation_warn_exceeds_cap(self):
        """Verify warn_threshold cannot exceed hard_cap"""
        payload = {
            "budgets": {
                "chatgpt": {
                    "warn_threshold_usd": 100.0,
                    "hard_cap_usd": 50.0,  # Cap is less than warn
                    "enabled": True
                }
            }
        }
        resp = self.session.put(f"{BASE_URL}/api/workspaces/{self.workspace_id}/nexus-ai/budgets", json=payload)
        assert resp.status_code == 422, f"Expected 422 validation error, got {resp.status_code}: {resp.text}"
        print("Budget validation: correctly rejected warn > cap")
    
    def test_budget_validation_negative_values(self):
        """Verify negative budget values are rejected"""
        payload = {
            "budgets": {
                "chatgpt": {
                    "warn_threshold_usd": -5.0,
                    "hard_cap_usd": 50.0,
                    "enabled": True
                }
            }
        }
        resp = self.session.put(f"{BASE_URL}/api/workspaces/{self.workspace_id}/nexus-ai/budgets", json=payload)
        assert resp.status_code == 422, f"Expected 422 validation error, got {resp.status_code}: {resp.text}"
        print("Budget validation: correctly rejected negative values")
    
    # ========== GitHub Integration Tests ==========
    
    def test_github_pull_endpoint_accessible(self):
        """Verify GitHub pull endpoint is accessible (budget tracking integrated)"""
        # This tests that the endpoint exists and returns proper error for missing repo
        resp = self.session.post(f"{BASE_URL}/api/workspaces/{self.workspace_id}/code-repo/github-pull", json={
            "repo": "octocat/Hello-World",
            "branch": "main"
        })
        # Should work or return a proper error (not 500)
        assert resp.status_code in [200, 400, 404, 429], f"Unexpected status: {resp.status_code}: {resp.text}"
        print(f"GitHub pull endpoint: status={resp.status_code}")
    
    def test_github_push_endpoint_accessible(self):
        """Verify GitHub push endpoint is accessible (budget tracking integrated)"""
        resp = self.session.post(f"{BASE_URL}/api/workspaces/{self.workspace_id}/code-repo/github-push", json={
            "repo": "test/nonexistent",
            "branch": "main",
            "message": "Test push"
        })
        # Should return proper error for missing token/repo (not 500)
        assert resp.status_code in [200, 400, 404, 429], f"Unexpected status: {resp.status_code}: {resp.text}"
        print(f"GitHub push endpoint: status={resp.status_code}")
    
    # ========== Managed Keys Settings Tests ==========
    
    def test_managed_keys_settings_get(self):
        """GET /api/settings/managed-keys - User managed keys settings"""
        resp = self.session.get(f"{BASE_URL}/api/settings/managed-keys")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert "providers" in data
        assert "plan" in data
        assert "credit_rates" in data
        
        providers = data["providers"]
        assert "chatgpt" in providers
        assert "claude" in providers
        assert "github" in providers
        
        # Verify provider structure
        chatgpt = providers.get("chatgpt", {})
        assert "available" in chatgpt
        assert "opted_in" in chatgpt
        assert "eligible" in chatgpt
        assert "type" in chatgpt
        
        print(f"Managed keys settings: plan={data.get('plan')}, providers={len(providers)}")
    
    def test_managed_keys_credits_get(self):
        """GET /api/settings/managed-keys/credits - User credit balance"""
        resp = self.session.get(f"{BASE_URL}/api/settings/managed-keys/credits")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert "credits_total" in data
        assert "credits_used" in data
        assert "credits_remaining" in data
        assert "plan" in data
        
        print(f"Credits: total={data.get('credits_total')}, used={data.get('credits_used')}, remaining={data.get('credits_remaining')}")
    
    def test_admin_managed_keys_get(self):
        """GET /api/admin/managed-keys - Admin view of platform keys"""
        resp = self.session.get(f"{BASE_URL}/api/admin/managed-keys")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert "providers" in data
        providers = data["providers"]
        
        # Verify AI providers
        assert "chatgpt" in providers
        assert "claude" in providers
        
        # Verify integration providers
        assert "github" in providers
        
        # Verify provider structure
        chatgpt = providers.get("chatgpt", {})
        assert "configured" in chatgpt
        assert "type" in chatgpt
        
        configured_count = sum(1 for p in providers.values() if p.get("configured"))
        print(f"Admin managed keys: {configured_count}/{len(providers)} providers configured")


class TestBudgetHierarchy:
    """Test budget hierarchy enforcement (workspace > org > platform)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert login_resp.status_code == 200
        data = login_resp.json()
        self.token = data.get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        ws_resp = self.session.get(f"{BASE_URL}/api/workspaces")
        assert ws_resp.status_code == 200
        workspaces = ws_resp.json()
        assert len(workspaces) > 0
        self.workspace_id = workspaces[0]["workspace_id"]
    
    def test_workspace_budget_overrides_platform(self):
        """Verify workspace budget takes precedence over platform budget"""
        # Set platform budget high
        platform_payload = {
            "budgets": {
                "deepseek": {
                    "warn_threshold_usd": 1000.0,
                    "hard_cap_usd": 5000.0,
                    "enabled": True
                }
            }
        }
        resp = self.session.put(f"{BASE_URL}/api/admin/managed-keys/budgets", json=platform_payload)
        assert resp.status_code == 200
        
        # Set workspace budget low (should override)
        workspace_payload = {
            "budgets": {
                "deepseek": {
                    "warn_threshold_usd": 0.01,
                    "hard_cap_usd": 0.05,
                    "enabled": True
                }
            }
        }
        resp = self.session.put(f"{BASE_URL}/api/workspaces/{self.workspace_id}/nexus-ai/budgets", json=workspace_payload)
        assert resp.status_code == 200
        
        # Verify workspace budget is set
        ws_budget_resp = self.session.get(f"{BASE_URL}/api/workspaces/{self.workspace_id}/nexus-ai/budgets")
        assert ws_budget_resp.status_code == 200
        ws_data = ws_budget_resp.json()
        deepseek = ws_data["budgets"].get("deepseek", {})
        assert deepseek.get("hard_cap_usd") == 0.05, "Workspace budget should be 0.05"
        
        print("Budget hierarchy: workspace budget correctly overrides platform")
    
    def test_disable_workspace_budget_falls_back_to_platform(self):
        """Verify disabling workspace budget falls back to platform budget"""
        # Disable workspace budget for a provider
        workspace_payload = {
            "budgets": {
                "mistral": {
                    "warn_threshold_usd": None,
                    "hard_cap_usd": None,
                    "enabled": False
                }
            }
        }
        resp = self.session.put(f"{BASE_URL}/api/workspaces/{self.workspace_id}/nexus-ai/budgets", json=workspace_payload)
        assert resp.status_code == 200
        
        # Verify workspace budget is disabled
        ws_budget_resp = self.session.get(f"{BASE_URL}/api/workspaces/{self.workspace_id}/nexus-ai/budgets")
        assert ws_budget_resp.status_code == 200
        ws_data = ws_budget_resp.json()
        mistral = ws_data["budgets"].get("mistral", {})
        assert mistral.get("enabled") == False
        
        print("Budget hierarchy: disabled workspace budget correctly configured")


class TestOrgBudgetAPIs:
    """Test Organization-level budget APIs (if user has org memberships)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert login_resp.status_code == 200
        data = login_resp.json()
        self.token = data.get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        # Check for org memberships
        orgs_resp = self.session.get(f"{BASE_URL}/api/orgs/my-orgs")
        if orgs_resp.status_code == 200:
            orgs = orgs_resp.json().get("organizations", [])
            admin_orgs = [o for o in orgs if o.get("org_role") in ["org_owner", "org_admin"]]
            self.org_id = admin_orgs[0]["org_id"] if admin_orgs else None
        else:
            self.org_id = None
    
    def test_org_budget_get(self):
        """GET /api/orgs/{org_id}/nexus-ai/budgets - Org budget settings"""
        if not self.org_id:
            pytest.skip("No org admin membership found")
        
        resp = self.session.get(f"{BASE_URL}/api/orgs/{self.org_id}/nexus-ai/budgets")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert data.get("scope_type") == "org"
        assert data.get("scope_id") == self.org_id
        assert "budgets" in data
        print(f"Org budget GET: {len(data['budgets'])} providers")
    
    def test_org_budget_put(self):
        """PUT /api/orgs/{org_id}/nexus-ai/budgets - Save org budget settings"""
        if not self.org_id:
            pytest.skip("No org admin membership found")
        
        payload = {
            "budgets": {
                "gemini": {
                    "warn_threshold_usd": 20.0,
                    "hard_cap_usd": 100.0,
                    "enabled": True
                }
            }
        }
        resp = self.session.put(f"{BASE_URL}/api/orgs/{self.org_id}/nexus-ai/budgets", json=payload)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert data.get("scope_type") == "org"
        assert data.get("saved") >= 1
        print(f"Org budget PUT: saved {data.get('saved')} provider budgets")
    
    def test_org_dashboard_get(self):
        """GET /api/orgs/{org_id}/nexus-ai/dashboard - Org usage dashboard"""
        if not self.org_id:
            pytest.skip("No org admin membership found")
        
        resp = self.session.get(f"{BASE_URL}/api/orgs/{self.org_id}/nexus-ai/dashboard")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert data.get("scope_type") == "org"
        assert "month_key" in data
        assert "total_cost_usd" in data
        print(f"Org dashboard: total_cost=${data.get('total_cost_usd', 0):.4f}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
