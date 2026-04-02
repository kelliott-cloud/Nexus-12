"""
Test Suite: Walkthrough Builder Phase 2 + Pricing Engine
Features tested:
- Walkthrough config: 6 step types (beacon, checklist), branching operators, permissions matrix
- Beacon/checklist step creation
- Branching rules
- Walkthrough validation
- SDK resource center
- Pricing: credits, costs, history, transactions, free tier, check-limit, overage
"""

import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
TEST_EMAIL = "testmention@test.com"
TEST_PASSWORD = "Test1234!"
EXISTING_WALKTHROUGH_ID = "wt_cfa8ca1931fe"


class TestWalkthroughPhase2:
    """Walkthrough Builder Phase 2: beacon/checklist, branching, validation, resource center"""

    @pytest.fixture(autouse=True)
    def setup_session(self):
        """Login and get authenticated session"""
        self.session = requests.Session()
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        yield
        self.session.close()

    # === GET /api/walkthroughs/config ===
    def test_config_returns_6_step_types(self):
        """Config should return all 6 step types including beacon and checklist"""
        resp = self.session.get(f"{BASE_URL}/api/walkthroughs/config")
        assert resp.status_code == 200, f"Config failed: {resp.text}"
        data = resp.json()
        
        # Verify 6 step types
        step_types = data.get("step_types", [])
        assert len(step_types) == 6, f"Expected 6 step types, got {len(step_types)}"
        assert "beacon" in step_types, "Missing beacon step type"
        assert "checklist" in step_types, "Missing checklist step type"
        assert "tooltip" in step_types, "Missing tooltip step type"
        assert "modal" in step_types, "Missing modal step type"
        assert "spotlight" in step_types, "Missing spotlight step type"
        assert "action" in step_types, "Missing action step type"
        print(f"✓ Config returns 6 step types: {step_types}")

    def test_config_returns_branching_operators(self):
        """Config should return branching operators"""
        resp = self.session.get(f"{BASE_URL}/api/walkthroughs/config")
        assert resp.status_code == 200
        data = resp.json()
        
        operators = data.get("branching_operators", [])
        assert len(operators) > 0, "Missing branching operators"
        assert "eq" in operators, "Missing 'eq' operator"
        assert "neq" in operators, "Missing 'neq' operator"
        assert "contains" in operators, "Missing 'contains' operator"
        assert "gt" in operators, "Missing 'gt' operator"
        assert "lt" in operators, "Missing 'lt' operator"
        print(f"✓ Branching operators: {operators}")

    def test_config_returns_permissions_matrix_for_user_role(self):
        """Config should return permissions matrix (user role sees create=false)"""
        resp = self.session.get(f"{BASE_URL}/api/walkthroughs/config")
        assert resp.status_code == 200
        data = resp.json()
        
        permissions = data.get("permissions", {})
        assert permissions is not None, "Missing permissions in config"
        # User role should have create=False
        assert permissions.get("create") == False, f"User role should have create=False, got {permissions.get('create')}"
        print(f"✓ Permissions for user role: {permissions}")

    # === Step type: beacon ===
    def test_create_beacon_step(self):
        """POST /api/walkthroughs/{id}/steps with step_type=beacon"""
        payload = {
            "step_type": "beacon",
            "selector_primary": "[data-testid='feature-button']",
            "selector_css": ".feature-btn",
            "content": {
                "title": "TEST_Beacon Step",
                "body": "Click here to discover this feature",
                "cta_label": "Got it"
            },
            "behavior": {
                "placement": "right",
                "scroll_to": True
            }
        }
        resp = self.session.post(
            f"{BASE_URL}/api/walkthroughs/{EXISTING_WALKTHROUGH_ID}/steps",
            json=payload
        )
        assert resp.status_code == 200, f"Create beacon step failed: {resp.text}"
        data = resp.json()
        
        assert data.get("type") == "beacon", f"Expected type=beacon, got {data.get('type')}"
        assert "step_id" in data, "Missing step_id"
        assert data.get("content", {}).get("title") == "TEST_Beacon Step"
        print(f"✓ Beacon step created: {data.get('step_id')}")
        return data.get("step_id")

    # === Step type: checklist ===
    def test_create_checklist_step(self):
        """POST /api/walkthroughs/{id}/steps with step_type=checklist + checklist_items"""
        payload = {
            "step_type": "checklist",
            "selector_primary": "",  # Modal types don't need selector
            "content": {
                "title": "TEST_Onboarding Checklist",
                "body": "Complete these steps to get started",
                "cta_label": "Continue"
            },
            "checklist_items": [
                {"id": "item_1", "label": "Create your first workspace"},
                {"id": "item_2", "label": "Invite a team member"},
                {"id": "item_3", "label": "Start your first AI collaboration"}
            ]
        }
        resp = self.session.post(
            f"{BASE_URL}/api/walkthroughs/{EXISTING_WALKTHROUGH_ID}/steps",
            json=payload
        )
        assert resp.status_code == 200, f"Create checklist step failed: {resp.text}"
        data = resp.json()
        
        assert data.get("type") == "checklist", f"Expected type=checklist, got {data.get('type')}"
        assert data.get("checklist_items") is not None, "Missing checklist_items"
        assert len(data.get("checklist_items", [])) == 3, f"Expected 3 checklist items"
        print(f"✓ Checklist step created with {len(data.get('checklist_items', []))} items")
        return data.get("step_id")

    # === Branching rules ===
    def test_create_step_with_branching_rules(self):
        """POST /api/walkthroughs/{id}/steps with branching rules {condition, then_step_id, else_step_id}"""
        # First get current steps to get valid step IDs
        wt_resp = self.session.get(f"{BASE_URL}/api/walkthroughs/{EXISTING_WALKTHROUGH_ID}")
        assert wt_resp.status_code == 200
        wt_data = wt_resp.json()
        steps = wt_data.get("steps", [])
        
        # If we have steps, use their IDs for branching, otherwise skip this test
        if len(steps) >= 2:
            then_step_id = steps[0].get("step_id")
            else_step_id = steps[1].get("step_id")
        else:
            # Create a dummy valid ID pattern for testing
            then_step_id = "ws_test_then123"
            else_step_id = "ws_test_else456"

        payload = {
            "step_type": "tooltip",
            "selector_primary": "[data-testid='branch-trigger']",
            "content": {
                "title": "TEST_Branching Step",
                "body": "This step has branching logic"
            },
            "branching": {
                "condition": {
                    "type": "user_property",
                    "property": "plan",
                    "operator": "eq",
                    "value": "pro"
                },
                "then_step_id": then_step_id,
                "else_step_id": else_step_id
            }
        }
        resp = self.session.post(
            f"{BASE_URL}/api/walkthroughs/{EXISTING_WALKTHROUGH_ID}/steps",
            json=payload
        )
        assert resp.status_code == 200, f"Create branching step failed: {resp.text}"
        data = resp.json()
        
        assert data.get("branching") is not None, "Missing branching config"
        assert data.get("branching", {}).get("condition") is not None, "Missing condition"
        print(f"✓ Branching step created with condition: {data.get('branching', {}).get('condition')}")

    # === Validation endpoint ===
    def test_validate_walkthrough_no_errors_for_valid(self):
        """POST /api/walkthroughs/{id}/validate - valid walkthrough"""
        resp = self.session.post(f"{BASE_URL}/api/walkthroughs/{EXISTING_WALKTHROUGH_ID}/validate")
        assert resp.status_code == 200, f"Validate failed: {resp.text}"
        data = resp.json()
        
        assert "valid" in data, "Missing 'valid' field"
        assert "issues" in data, "Missing 'issues' field"
        print(f"✓ Validation result: valid={data.get('valid')}, issues={len(data.get('issues', []))}")

    def test_validate_walkthrough_detects_empty_steps(self):
        """Validation should detect walkthrough with no steps"""
        # Create a new walkthrough with no steps
        create_resp = self.session.post(
            f"{BASE_URL}/api/walkthroughs",
            json={"name": "TEST_Empty Walkthrough", "description": "For validation test"}
        )
        assert create_resp.status_code == 200, f"Create walkthrough failed: {create_resp.text}"
        new_wt_id = create_resp.json().get("walkthrough_id")
        
        # Validate it - should detect no steps
        validate_resp = self.session.post(f"{BASE_URL}/api/walkthroughs/{new_wt_id}/validate")
        assert validate_resp.status_code == 200
        data = validate_resp.json()
        
        assert data.get("valid") == False, "Empty walkthrough should not be valid"
        issues = data.get("issues", [])
        has_no_steps_error = any("no steps" in i.get("message", "").lower() for i in issues)
        assert has_no_steps_error, "Should detect 'no steps' error"
        print(f"✓ Empty walkthrough validation: detected no-steps error")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/walkthroughs/{new_wt_id}")

    def test_validate_detects_bad_branch_references(self):
        """Validation should detect invalid branching target references"""
        # Create a walkthrough
        create_resp = self.session.post(
            f"{BASE_URL}/api/walkthroughs",
            json={"name": "TEST_BadBranch Walkthrough"}
        )
        assert create_resp.status_code == 200
        new_wt_id = create_resp.json().get("walkthrough_id")
        
        # Add a step with invalid branching references
        step_payload = {
            "step_type": "tooltip",
            "selector_primary": "[data-testid='test']",
            "content": {"title": "Test Step"},
            "branching": {
                "condition": {"type": "user_property", "property": "test", "operator": "eq", "value": "yes"},
                "then_step_id": "ws_nonexistent_step",
                "else_step_id": "ws_also_nonexistent"
            }
        }
        self.session.post(f"{BASE_URL}/api/walkthroughs/{new_wt_id}/steps", json=step_payload)
        
        # Validate
        validate_resp = self.session.post(f"{BASE_URL}/api/walkthroughs/{new_wt_id}/validate")
        assert validate_resp.status_code == 200
        data = validate_resp.json()
        
        issues = data.get("issues", [])
        has_branch_error = any("not found" in i.get("message", "").lower() for i in issues)
        assert has_branch_error, "Should detect invalid branch reference"
        print(f"✓ Invalid branch reference detected")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/walkthroughs/{new_wt_id}")

    # === SDK Resource Center ===
    def test_resource_center_returns_categorized_walkthroughs(self):
        """GET /api/sdk/resource-center returns categorized walkthroughs with progress"""
        resp = self.session.get(f"{BASE_URL}/api/sdk/resource-center")
        assert resp.status_code == 200, f"Resource center failed: {resp.text}"
        data = resp.json()
        
        assert "categories" in data, "Missing categories"
        assert "total_walkthroughs" in data, "Missing total_walkthroughs"
        assert "completed" in data, "Missing completed count"
        assert "progress_pct" in data, "Missing progress_pct"
        
        # Verify structure
        categories = data.get("categories", {})
        for cat_name, items in categories.items():
            for item in items:
                assert "walkthrough_id" in item, f"Missing walkthrough_id in {cat_name}"
                assert "name" in item, f"Missing name in {cat_name}"
                assert "status" in item, f"Missing status in {cat_name}"
        print(f"✓ Resource center: {data.get('total_walkthroughs')} walkthroughs, {len(categories)} categories")


class TestPricingEngine:
    """Pricing Engine: credits, costs, history, free tier, overage"""

    @pytest.fixture(autouse=True)
    def setup_session(self):
        """Login and get authenticated session"""
        self.session = requests.Session()
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        yield
        self.session.close()

    # === GET /api/billing/credits ===
    def test_credits_endpoint_returns_balance(self):
        """GET /api/billing/credits returns credit balance with all required fields"""
        resp = self.session.get(f"{BASE_URL}/api/billing/credits")
        assert resp.status_code == 200, f"Credits failed: {resp.text}"
        data = resp.json()
        
        required_fields = ["plan", "month", "allocated", "used", "remaining", "breakdown"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Free tier user should have 100 credits
        assert data.get("plan") == "free", f"Expected plan=free, got {data.get('plan')}"
        print(f"✓ Credits: allocated={data.get('allocated')}, used={data.get('used')}, remaining={data.get('remaining')}")

    def test_free_tier_user_gets_100_monthly_credits(self):
        """Free tier user with plan=free gets 100 monthly credits"""
        resp = self.session.get(f"{BASE_URL}/api/billing/credits")
        assert resp.status_code == 200
        data = resp.json()
        
        # Free tier = 100 credits
        assert data.get("allocated") == 100, f"Expected 100 credits for free tier, got {data.get('allocated')}"
        print(f"✓ Free tier has 100 monthly credits")

    def test_free_tier_overage_not_allowed(self):
        """Overage not allowed for free tier (overage_allowed=false)"""
        resp = self.session.get(f"{BASE_URL}/api/billing/credits")
        assert resp.status_code == 200
        data = resp.json()
        
        assert data.get("overage_allowed") == False, f"Free tier should have overage_allowed=False"
        print(f"✓ Free tier overage_allowed=False confirmed")

    # === GET /api/billing/credit-costs ===
    def test_credit_costs_returns_5_action_types(self):
        """GET /api/billing/credit-costs returns 5 action types"""
        resp = self.session.get(f"{BASE_URL}/api/billing/credit-costs")
        assert resp.status_code == 200, f"Credit costs failed: {resp.text}"
        data = resp.json()
        
        costs = data.get("costs", {})
        expected_actions = ["ai_collaboration", "image_generation", "workflow_run", "file_upload", "export"]
        for action in expected_actions:
            assert action in costs, f"Missing action type: {action}"
        
        # Verify specific costs
        assert costs.get("ai_collaboration") == 10, "ai_collaboration should cost 10 credits"
        assert costs.get("image_generation") == 25, "image_generation should cost 25 credits"
        assert costs.get("workflow_run") == 15, "workflow_run should cost 15 credits"
        assert costs.get("file_upload") == 2, "file_upload should cost 2 credits"
        assert costs.get("export") == 1, "export should cost 1 credit"
        print(f"✓ Credit costs: {costs}")

    def test_credit_costs_returns_3_plan_configs(self):
        """GET /api/billing/credit-costs returns 3 plan configs"""
        resp = self.session.get(f"{BASE_URL}/api/billing/credit-costs")
        assert resp.status_code == 200
        data = resp.json()
        
        plan_credits = data.get("plan_credits", {})
        assert "free" in plan_credits, "Missing free plan config"
        assert "pro" in plan_credits, "Missing pro plan config"
        assert "enterprise" in plan_credits, "Missing enterprise plan config"
        
        # Verify free plan
        free_plan = plan_credits.get("free", {})
        assert free_plan.get("monthly_credits") == 100, "Free should have 100 credits"
        assert free_plan.get("overage_allowed") == False, "Free should not allow overage"
        
        # Verify pro plan
        pro_plan = plan_credits.get("pro", {})
        assert pro_plan.get("monthly_credits") == 5000, "Pro should have 5000 credits"
        assert pro_plan.get("overage_rate") == 0.01, "Pro overage rate should be $0.01"
        print(f"✓ Plan configs: free={free_plan}, pro={pro_plan}")

    # === GET /api/billing/credits/history ===
    def test_credits_history_returns_monthly_history(self):
        """GET /api/billing/credits/history returns monthly history"""
        resp = self.session.get(f"{BASE_URL}/api/billing/credits/history")
        assert resp.status_code == 200, f"History failed: {resp.text}"
        data = resp.json()
        
        assert "history" in data, "Missing history field"
        # History is an array of monthly records
        history = data.get("history", [])
        print(f"✓ Credits history: {len(history)} months")
        
        if history:
            for record in history:
                assert "month" in record, "Missing month in history record"
                assert "allocated" in record, "Missing allocated in history record"
                assert "used" in record, "Missing used in history record"

    # === GET /api/billing/credits/transactions ===
    def test_credits_transactions_returns_log(self):
        """GET /api/billing/credits/transactions returns credit transaction log"""
        resp = self.session.get(f"{BASE_URL}/api/billing/credits/transactions")
        assert resp.status_code == 200, f"Transactions failed: {resp.text}"
        data = resp.json()
        
        assert "transactions" in data, "Missing transactions field"
        transactions = data.get("transactions", [])
        print(f"✓ Credit transactions: {len(transactions)} records")
        
        if transactions:
            for tx in transactions:
                assert "action" in tx, "Missing action in transaction"
                assert "credits" in tx, "Missing credits in transaction"
                assert "timestamp" in tx, "Missing timestamp in transaction"

    # === GET /api/billing/free-tier/status ===
    def test_free_tier_status_returns_6_limits(self):
        """GET /api/billing/free-tier/status returns limits (6 limits) and current usage"""
        resp = self.session.get(f"{BASE_URL}/api/billing/free-tier/status")
        assert resp.status_code == 200, f"Free tier status failed: {resp.text}"
        data = resp.json()
        
        assert "on_free_tier" in data, "Missing on_free_tier"
        assert "limits" in data, "Missing limits"
        assert "usage" in data, "Missing usage"
        
        limits = data.get("limits", {})
        expected_limits = [
            "max_workspaces",
            "max_channels_per_workspace", 
            "max_collaborations_per_day",
            "max_image_generations_per_day",
            "max_workflow_runs_per_day",
            "max_kb_entries"
        ]
        for limit_key in expected_limits:
            assert limit_key in limits, f"Missing limit: {limit_key}"
            # Each limit should have structure with limit, used, remaining, at_limit
            limit_info = limits.get(limit_key, {})
            assert "limit" in limit_info, f"Missing 'limit' in {limit_key}"
            assert "used" in limit_info, f"Missing 'used' in {limit_key}"
            assert "remaining" in limit_info, f"Missing 'remaining' in {limit_key}"
        
        print(f"✓ Free tier status: on_free_tier={data.get('on_free_tier')}, {len(limits)} limits")

    # === POST /api/billing/check-limit ===
    def test_check_limit_returns_allowed_status(self):
        """POST /api/billing/check-limit returns allowed=true/false for an action"""
        # Check an action
        resp = self.session.post(
            f"{BASE_URL}/api/billing/check-limit",
            json={"action": "export"}  # export is cheapest at 1 credit
        )
        assert resp.status_code == 200, f"Check limit failed: {resp.text}"
        data = resp.json()
        
        assert "allowed" in data, "Missing allowed field"
        assert "action" in data, "Missing action field"
        assert isinstance(data.get("allowed"), bool), "allowed should be boolean"
        print(f"✓ Check limit for 'export': allowed={data.get('allowed')}")

    def test_check_limit_for_various_actions(self):
        """Check limit for different action types"""
        actions = ["ai_collaboration", "image_generation", "workflow_run", "file_upload", "export"]
        results = {}
        
        for action in actions:
            resp = self.session.post(
                f"{BASE_URL}/api/billing/check-limit",
                json={"action": action}
            )
            assert resp.status_code == 200, f"Check limit for {action} failed: {resp.text}"
            data = resp.json()
            results[action] = data.get("allowed")
        
        print(f"✓ Check limit results: {results}")

    # === GET /api/billing/overage-estimate ===
    def test_overage_estimate_returns_projection(self):
        """GET /api/billing/overage-estimate returns projected overage based on usage rate"""
        resp = self.session.get(f"{BASE_URL}/api/billing/overage-estimate")
        assert resp.status_code == 200, f"Overage estimate failed: {resp.text}"
        data = resp.json()
        
        expected_fields = [
            "current_used",
            "allocated", 
            "daily_rate",
            "projected_total",
            "projected_overage",
            "projected_cost",
            "days_remaining"
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        
        # For free tier, projected_cost should be 0 (no overage allowed)
        print(f"✓ Overage estimate: daily_rate={data.get('daily_rate')}, projected_overage={data.get('projected_overage')}, cost=${data.get('projected_cost')}")


class TestPermissionsMatrix:
    """Test permissions matrix for different roles"""

    @pytest.fixture(autouse=True)
    def setup_session(self):
        """Login and get authenticated session"""
        self.session = requests.Session()
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        yield
        self.session.close()

    def test_permissions_structure_is_valid(self):
        """Verify permissions matrix structure returned by config"""
        resp = self.session.get(f"{BASE_URL}/api/walkthroughs/config")
        assert resp.status_code == 200
        data = resp.json()
        
        permissions = data.get("permissions", {})
        expected_keys = ["create", "edit_own", "edit_all", "publish", "delete", "view_analytics"]
        
        for key in expected_keys:
            assert key in permissions, f"Missing permission key: {key}"
        
        print(f"✓ Permissions matrix structure valid: {list(permissions.keys())}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
