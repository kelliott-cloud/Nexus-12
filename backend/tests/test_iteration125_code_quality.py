"""
Iteration 125 - Code Quality Improvements Testing
Tests for:
1. Backend: ruff F821 check returns 0 undefined variables
2. Backend: agent_context_builder.py has separate helper functions
3. Backend: agent_context_builder.py build_agent_context_block has type hints
4. Backend: agent_certification.py evaluate_badges has type hints
5. Backend: data_guard.py DataGuard.sanitize_for_ai has type hints
6. Backend: cost_batch_job.py compute_cost has type hints
7. Frontend: LandingPage.js uses stable keys (plan.name, f.title, s.step etc)
8. Frontend: LegalPage.js uses lineKey not key={i}
9. Frontend: CodeRepoPanel.js imports useMemo and uses it for filteredFiles and tree
10. Frontend: WorkspacePage.js keyboard effect deps include NAV_MENUS
"""

import pytest
import requests
import os
import re
import subprocess

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestHealthCheck:
    """Health endpoint tests"""
    
    def test_health_endpoint_returns_200(self):
        """Verify /api/health returns 200"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("PASSED: Health endpoint returns 200 with status=healthy")


class TestAuthentication:
    """Authentication tests"""
    
    def test_login_with_super_admin(self):
        """Verify login with kelliott@urtech.org / test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "kelliott@urtech.org",
            "password": "test"
        })
        assert response.status_code == 200
        data = response.json()
        assert "session_token" in data or "user" in data
        print("PASSED: Login with super admin credentials works")


class TestRuffF821Check:
    """Verify ruff F821 (undefined variables) returns 0 errors"""
    
    def test_ruff_f821_no_undefined_variables(self):
        """Run ruff check --select=F821 and verify 0 errors"""
        result = subprocess.run(
            ["ruff", "check", "--select=F821", "/app/backend"],
            capture_output=True,
            text=True
        )
        # Exit code 0 means no errors
        assert result.returncode == 0, f"ruff F821 found errors: {result.stdout}"
        print("PASSED: ruff F821 check returns 0 undefined variables")


class TestAgentContextBuilderRefactoring:
    """Verify agent_context_builder.py has been refactored with helper functions"""
    
    def test_helper_functions_exist(self):
        """Verify separate helper functions exist"""
        with open("/app/backend/agent_context_builder.py", "r") as f:
            content = f.read()
        
        # Check for helper functions
        helpers = [
            "_build_workspace_context",
            "_build_project_context",
            "_build_assignment_context",
            "_build_cost_context",
            "_build_user_context",
            "_build_feedback_context",
            "_build_skills_context",
            "_build_badges_context",
        ]
        
        for helper in helpers:
            assert f"async def {helper}" in content, f"Missing helper function: {helper}"
        
        print(f"PASSED: All {len(helpers)} helper functions found in agent_context_builder.py")
    
    def test_build_agent_context_block_has_type_hints(self):
        """Verify build_agent_context_block has type hints"""
        with open("/app/backend/agent_context_builder.py", "r") as f:
            content = f.read()
        
        # Check for type hints in function signature
        assert "async def build_agent_context_block(" in content
        # Should have return type hint -> str
        assert "-> str:" in content
        # Should import List from typing
        assert "from typing import" in content
        assert "List" in content
        
        print("PASSED: build_agent_context_block has type hints")
    
    def test_uses_asyncio_gather(self):
        """Verify asyncio.gather is used for parallel DB queries"""
        with open("/app/backend/agent_context_builder.py", "r") as f:
            content = f.read()
        
        assert "asyncio.gather" in content
        print("PASSED: agent_context_builder.py uses asyncio.gather for parallel queries")


class TestAgentCertificationTypeHints:
    """Verify agent_certification.py has type hints"""
    
    def test_evaluate_badges_has_type_hints(self):
        """Verify evaluate_badges has type hints (str, str) -> List[str]"""
        with open("/app/backend/agent_certification.py", "r") as f:
            content = f.read()
        
        # Check for type hints
        assert "from typing import" in content
        assert "List" in content
        # Check function signature has type hints
        assert "async def evaluate_badges(" in content
        assert "-> List[str]:" in content
        
        print("PASSED: evaluate_badges has type hints")
    
    def test_check_and_award_badges_has_type_hints(self):
        """Verify check_and_award_badges has type hints"""
        with open("/app/backend/agent_certification.py", "r") as f:
            content = f.read()
        
        assert "async def check_and_award_badges(" in content
        assert "Dict" in content or "Any" in content
        
        print("PASSED: check_and_award_badges has type hints")


class TestDataGuardTypeHints:
    """Verify data_guard.py DataGuard.sanitize_for_ai has type hints"""
    
    def test_sanitize_for_ai_has_type_hints(self):
        """Verify DataGuard.sanitize_for_ai has type hints"""
        with open("/app/backend/data_guard.py", "r") as f:
            content = f.read()
        
        # Check for type hints
        assert "from typing import" in content
        # Check sanitize_for_ai has type hints
        assert "def sanitize_for_ai(" in content
        assert "text: str" in content
        assert "-> str:" in content
        
        print("PASSED: DataGuard.sanitize_for_ai has type hints")
    
    def test_get_no_train_headers_has_type_hints(self):
        """Verify get_no_train_headers has type hints"""
        with open("/app/backend/data_guard.py", "r") as f:
            content = f.read()
        
        assert "def get_no_train_headers(" in content
        assert "provider: str" in content
        assert "-> Dict[str, str]:" in content
        
        print("PASSED: get_no_train_headers has type hints")


class TestCostBatchJobTypeHints:
    """Verify cost_batch_job.py compute_cost has type hints"""
    
    def test_compute_cost_has_type_hints(self):
        """Verify compute_cost has type hints"""
        with open("/app/backend/cost_batch_job.py", "r") as f:
            content = f.read()
        
        # Check function signature
        assert "def compute_cost(" in content
        assert "provider: str" in content
        assert "input_tokens: int" in content
        assert "output_tokens: int" in content
        assert "-> float:" in content
        
        print("PASSED: compute_cost has type hints")
    
    def test_run_cost_snapshot_has_type_hints(self):
        """Verify run_cost_snapshot has type hints"""
        with open("/app/backend/cost_batch_job.py", "r") as f:
            content = f.read()
        
        assert "async def run_cost_snapshot(" in content
        assert "-> None:" in content
        
        print("PASSED: run_cost_snapshot has type hints")


class TestAgentEvaluatorTypeHints:
    """Verify agent_evaluator.py has type hints"""
    
    def test_run_real_assessment_has_type_hints(self):
        """Verify run_real_assessment has type hints"""
        with open("/app/backend/agent_evaluator.py", "r") as f:
            content = f.read()
        
        assert "from typing import" in content
        assert "async def run_real_assessment(" in content
        assert "-> Dict[str, Any]:" in content
        
        print("PASSED: run_real_assessment has type hints")


class TestAgentPromptBuilderTypeHints:
    """Verify agent_prompt_builder.py has type hints"""
    
    def test_build_agent_prompt_has_type_hints(self):
        """Verify build_agent_prompt has type hints"""
        with open("/app/backend/agent_prompt_builder.py", "r") as f:
            content = f.read()
        
        assert "from typing import" in content
        assert "async def build_agent_prompt(" in content
        assert "agent_config: Dict[str, Any]" in content
        assert "-> str:" in content
        
        print("PASSED: build_agent_prompt has type hints")


class TestAgentSkillDefinitionsTypeHints:
    """Verify agent_skill_definitions.py has type hints"""
    
    def test_get_skill_has_type_hints(self):
        """Verify get_skill has type hints"""
        with open("/app/backend/agent_skill_definitions.py", "r") as f:
            content = f.read()
        
        assert "def get_skill(skill_id: str) -> dict:" in content
        print("PASSED: get_skill has type hints")
    
    def test_get_skills_by_category_has_type_hints(self):
        """Verify get_skills_by_category has type hints"""
        with open("/app/backend/agent_skill_definitions.py", "r") as f:
            content = f.read()
        
        assert "def get_skills_by_category(category: str) -> list:" in content
        print("PASSED: get_skills_by_category has type hints")
    
    def test_get_all_skill_ids_has_type_hints(self):
        """Verify get_all_skill_ids has type hints"""
        with open("/app/backend/agent_skill_definitions.py", "r") as f:
            content = f.read()
        
        assert "def get_all_skill_ids() -> list:" in content
        print("PASSED: get_all_skill_ids has type hints")
    
    def test_build_skill_prompt_fragment_has_type_hints(self):
        """Verify build_skill_prompt_fragment has type hints"""
        with open("/app/backend/agent_skill_definitions.py", "r") as f:
            content = f.read()
        
        assert "def build_skill_prompt_fragment(skills: list) -> str:" in content
        print("PASSED: build_skill_prompt_fragment has type hints")


class TestFrontendLandingPageStableKeys:
    """Verify LandingPage.js uses stable keys instead of key={i}"""
    
    def test_uses_stable_keys_for_agents(self):
        """Verify AI_AGENTS map uses a.name as key"""
        with open("/app/frontend/src/pages/LandingPage.js", "r") as f:
            content = f.read()
        
        # Check for key={a.name} pattern in AI_AGENTS map
        assert "key={a.name}" in content
        print("PASSED: LandingPage.js uses key={a.name} for AI agents")
    
    def test_uses_stable_keys_for_stats(self):
        """Verify stats section uses stable keys"""
        with open("/app/frontend/src/pages/LandingPage.js", "r") as f:
            content = f.read()
        
        # Check for key={s.label} or similar stable key
        assert "key={s.label" in content or "key={s.value}" in content
        print("PASSED: LandingPage.js uses stable keys for stats")
    
    def test_uses_stable_keys_for_features(self):
        """Verify features section uses stable keys"""
        with open("/app/frontend/src/pages/LandingPage.js", "r") as f:
            content = f.read()
        
        # Check for key={f.title} pattern
        assert "key={f.title}" in content
        print("PASSED: LandingPage.js uses key={f.title} for features")
    
    def test_uses_stable_keys_for_steps(self):
        """Verify how-it-works steps use stable keys"""
        with open("/app/frontend/src/pages/LandingPage.js", "r") as f:
            content = f.read()
        
        # Check for key={s.step} pattern
        assert "key={s.step}" in content
        print("PASSED: LandingPage.js uses key={s.step} for steps")
    
    def test_uses_stable_keys_for_pricing(self):
        """Verify pricing plans use stable keys"""
        with open("/app/frontend/src/pages/LandingPage.js", "r") as f:
            content = f.read()
        
        # Check for key={plan.name} pattern
        assert "key={plan.name}" in content
        print("PASSED: LandingPage.js uses key={plan.name} for pricing")
    
    def test_no_array_index_keys(self):
        """Verify no key={i} or key={index} patterns exist"""
        with open("/app/frontend/src/pages/LandingPage.js", "r") as f:
            content = f.read()
        
        # Check that key={i} is not used (except in nested feature lists which is acceptable)
        # The only key={j} should be in the nested features list
        key_i_count = content.count("key={i}")
        key_index_count = content.count("key={index}")
        
        # Should have 0 key={i} and 0 key={index}
        assert key_i_count == 0, f"Found {key_i_count} instances of key={{i}}"
        assert key_index_count == 0, f"Found {key_index_count} instances of key={{index}}"
        print("PASSED: LandingPage.js has no key={i} or key={index} patterns")


class TestFrontendLegalPageStableKeys:
    """Verify LegalPage.js uses lineKey instead of key={i}"""
    
    def test_uses_linekey_for_content(self):
        """Verify content lines use lineKey"""
        with open("/app/frontend/src/pages/LegalPage.js", "r") as f:
            content = f.read()
        
        # Check for lineKey pattern
        assert "lineKey" in content
        assert "key={lineKey}" in content
        print("PASSED: LegalPage.js uses lineKey for content")
    
    def test_no_array_index_keys(self):
        """Verify no key={i} patterns exist"""
        with open("/app/frontend/src/pages/LegalPage.js", "r") as f:
            content = f.read()
        
        # Should not have key={i}
        assert "key={i}" not in content
        print("PASSED: LegalPage.js has no key={i} patterns")


class TestFrontendCodeRepoPanelUseMemo:
    """Verify CodeRepoPanel.js imports useMemo and uses it"""
    
    def test_imports_usememo(self):
        """Verify useMemo is imported"""
        with open("/app/frontend/src/components/CodeRepoPanel.js", "r") as f:
            content = f.read()
        
        # Check import statement includes useMemo
        assert "useMemo" in content
        # Check it's imported from react
        import_match = re.search(r'import\s*\{[^}]*useMemo[^}]*\}\s*from\s*["\']react["\']', content)
        assert import_match is not None, "useMemo not imported from react"
        print("PASSED: CodeRepoPanel.js imports useMemo from react")
    
    def test_uses_usememo_for_filtered_files(self):
        """Verify useMemo is used for filteredFiles"""
        with open("/app/frontend/src/components/CodeRepoPanel.js", "r") as f:
            content = f.read()
        
        # Check for useMemo usage with filteredFiles
        assert "const filteredFiles = useMemo(" in content
        print("PASSED: CodeRepoPanel.js uses useMemo for filteredFiles")
    
    def test_uses_usememo_for_tree(self):
        """Verify useMemo is used for tree"""
        with open("/app/frontend/src/components/CodeRepoPanel.js", "r") as f:
            content = f.read()
        
        # Check for useMemo usage with tree
        assert "const tree = useMemo(" in content
        print("PASSED: CodeRepoPanel.js uses useMemo for tree")


class TestFrontendWorkspacePageKeyboardDeps:
    """Verify WorkspacePage.js keyboard effect deps include NAV_MENUS"""
    
    def test_keyboard_effect_includes_nav_menus(self):
        """Verify keyboard navigation effect deps include NAV_MENUS"""
        with open("/app/frontend/src/pages/WorkspacePage.js", "r") as f:
            content = f.read()
        
        # Find the keyboard navigation useEffect
        # Look for the effect that handles keyboard navigation
        # It should have NAV_MENUS in its dependency array
        
        # Check that NAV_MENUS is in a dependency array
        # The pattern should be something like [openMenu, focusedIndex, setActiveTab, NAV_MENUS]
        assert "NAV_MENUS" in content
        
        # Check for the specific dependency array pattern
        dep_pattern = re.search(r'\[openMenu,\s*focusedIndex,\s*setActiveTab,\s*NAV_MENUS\]', content)
        assert dep_pattern is not None, "NAV_MENUS not found in keyboard effect dependency array"
        
        print("PASSED: WorkspacePage.js keyboard effect deps include NAV_MENUS")


class TestFrontendLoads:
    """Verify frontend loads correctly"""
    
    def test_landing_page_loads(self):
        """Verify landing page loads without errors"""
        response = requests.get(BASE_URL)
        assert response.status_code == 200
        print("PASSED: Landing page loads correctly")
    
    def test_auth_page_loads(self):
        """Verify auth page loads"""
        response = requests.get(f"{BASE_URL}/auth")
        assert response.status_code == 200
        print("PASSED: Auth page loads correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
