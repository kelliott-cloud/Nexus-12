from conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, BASE_URL
"""
Iteration 94 - Agent Creator Studio, Skills Matrix, Agent Catalog Testing
Tests for:
- Skills API: GET /api/skills, GET /api/skills/{skill_id}, POST /api/skills
- Catalog API: GET /api/catalog/templates, GET /api/catalog/templates/{template_id}
- Agent Studio API: POST/PUT/PATCH agents/studio, clone, preview, versions
- Skills Matrix API: agent skills proficiency, assessment, leaderboard
- Agent Analytics API: analytics, compare
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
WORKSPACE_ID = "ws_a92cb83bfdb2"


@pytest.fixture(scope="module")
def session():
    """Create authenticated session."""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    # Login
    login_res = s.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_ADMIN_EMAIL,
        "password": "test"
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    return s


# ==================== SKILLS API ====================

class TestSkillsAPI:
    """Skills endpoint tests (public endpoints)"""

    def test_list_all_skills(self):
        """GET /api/skills - List all 26 skill definitions across 4 categories"""
        res = requests.get(f"{BASE_URL}/api/skills")
        assert res.status_code == 200
        data = res.json()
        assert "skills" in data
        assert "categories" in data
        # Should have 26 builtin skills
        assert len(data["skills"]) >= 26, f"Expected 26+ skills, got {len(data['skills'])}"
        # Should have 4 categories
        assert len(data["categories"]) == 4
        expected_categories = ["engineering", "product", "data", "operations"]
        for cat in expected_categories:
            assert cat in data["categories"], f"Missing category: {cat}"
        print(f"✓ GET /api/skills: {len(data['skills'])} skills, {len(data['categories'])} categories")

    def test_list_skills_by_category(self):
        """GET /api/skills?category=engineering - Filter by category"""
        res = requests.get(f"{BASE_URL}/api/skills", params={"category": "engineering"})
        assert res.status_code == 200
        data = res.json()
        # All returned skills should be engineering
        for skill in data["skills"]:
            assert skill["category"] == "engineering"
        print(f"✓ GET /api/skills?category=engineering: {len(data['skills'])} engineering skills")

    def test_get_specific_skill(self):
        """GET /api/skills/{skill_id} - Get specific skill (e.g. code_review)"""
        res = requests.get(f"{BASE_URL}/api/skills/code_review")
        assert res.status_code == 200
        skill = res.json()
        assert skill["skill_id"] == "code_review"
        assert skill["category"] == "engineering"
        assert skill["name"] == "Code Review"
        assert "prompt_injection" in skill
        assert "levels" in skill
        print(f"✓ GET /api/skills/code_review: {skill['name']}")

    def test_get_nonexistent_skill(self):
        """GET /api/skills/{skill_id} - 404 for nonexistent skill"""
        res = requests.get(f"{BASE_URL}/api/skills/nonexistent_skill_xyz")
        assert res.status_code == 404
        print("✓ GET /api/skills/nonexistent_skill_xyz returns 404")

    def test_create_custom_skill(self, session):
        """POST /api/skills - Create custom skill definition"""
        custom_skill = {
            "skill_id": f"TEST_custom_skill_{int(time.time())}",
            "category": "engineering",
            "name": "TEST Custom Skill",
            "description": "A test custom skill for testing",
            "icon": "star",
            "color": "#6366f1"
        }
        res = session.post(f"{BASE_URL}/api/skills", json=custom_skill)
        assert res.status_code == 200, f"Create skill failed: {res.text}"
        data = res.json()
        assert data["skill_id"] == custom_skill["skill_id"]
        assert data["name"] == custom_skill["name"]
        assert data["is_builtin"] == False
        print(f"✓ POST /api/skills: Created custom skill {data['skill_id']}")

    def test_create_duplicate_skill_fails(self, session):
        """POST /api/skills - Creating existing skill_id fails"""
        res = session.post(f"{BASE_URL}/api/skills", json={
            "skill_id": "code_review",  # This is a builtin
            "category": "engineering",
            "name": "Duplicate Test",
        })
        assert res.status_code == 400
        print("✓ POST /api/skills with duplicate ID returns 400")


# ==================== CATALOG API ====================

class TestCatalogAPI:
    """Agent Catalog endpoint tests (public endpoints)"""

    def test_list_templates(self):
        """GET /api/catalog/templates - List all 12 builtin agent templates"""
        res = requests.get(f"{BASE_URL}/api/catalog/templates")
        assert res.status_code == 200
        data = res.json()
        assert "templates" in data
        assert "total" in data
        assert data["total"] >= 12, f"Expected 12+ templates, got {data['total']}"
        # Check for expected templates
        template_ids = [t["template_id"] for t in data["templates"]]
        assert "tpl_security_auditor" in template_ids
        assert "tpl_fullstack_dev" in template_ids
        print(f"✓ GET /api/catalog/templates: {data['total']} templates")

    def test_list_templates_by_category(self):
        """GET /api/catalog/templates?category=engineering - Filter by category"""
        res = requests.get(f"{BASE_URL}/api/catalog/templates", params={"category": "engineering"})
        assert res.status_code == 200
        data = res.json()
        for tpl in data["templates"]:
            assert tpl["category"] == "engineering"
        print(f"✓ GET /api/catalog/templates?category=engineering: {len(data['templates'])} templates")

    def test_get_specific_template(self):
        """GET /api/catalog/templates/{template_id} - Get specific template"""
        res = requests.get(f"{BASE_URL}/api/catalog/templates/tpl_security_auditor")
        assert res.status_code == 200
        tpl = res.json()
        assert tpl["template_id"] == "tpl_security_auditor"
        assert tpl["name"] == "Security Auditor"
        assert "skills" in tpl
        assert "personality" in tpl
        assert "guardrails" in tpl
        assert tpl["avg_rating"] > 0
        print(f"✓ GET /api/catalog/templates/tpl_security_auditor: {tpl['name']}")

    def test_get_nonexistent_template(self):
        """GET /api/catalog/templates/{template_id} - 404 for nonexistent template"""
        res = requests.get(f"{BASE_URL}/api/catalog/templates/nonexistent_tpl_xyz")
        assert res.status_code == 404
        print("✓ GET /api/catalog/templates/nonexistent_tpl_xyz returns 404")


# ==================== AGENT STUDIO API ====================

class TestAgentStudioAPI:
    """Agent Creator Studio endpoint tests (authenticated)"""

    created_agent_id = None

    def test_create_agent_via_studio(self, session):
        """POST /api/workspaces/{ws_id}/agents/studio - Create agent via studio wizard"""
        agent_data = {
            "name": f"TEST Studio Agent {int(time.time())}",
            "description": "A test agent created via studio wizard",
            "base_model": "claude",
            "system_prompt": "You are a helpful assistant for testing.",
            "color": "#3B82F6",
            "category": "engineering",
            "tags": ["test", "automation"],
            "skills": [
                {"skill_id": "code_review", "level": "expert", "priority": 1, "custom_instructions": "Focus on Python code"},
                {"skill_id": "debugging", "level": "advanced", "priority": 2, "custom_instructions": ""}
            ],
            "personality": {
                "tone": "precise",
                "verbosity": "balanced",
                "risk_tolerance": "moderate",
                "collaboration_style": "contributor"
            },
            "guardrails": {
                "max_response_length": 4000,
                "require_citations": True,
                "require_confidence": True,
                "forbidden_topics": ["politics"],
                "escalation_threshold": 0.4
            },
            "preferred_role": "contributor"
        }
        res = session.post(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/studio", json=agent_data)
        assert res.status_code == 200, f"Create agent failed: {res.text}"
        agent = res.json()
        assert "agent_id" in agent
        assert agent["name"] == agent_data["name"]
        assert agent["base_model"] == "claude"
        assert len(agent["skills"]) == 2
        assert agent["personality"]["tone"] == "precise"
        assert agent["guardrails"]["require_citations"] == True
        TestAgentStudioAPI.created_agent_id = agent["agent_id"]
        print(f"✓ POST /api/workspaces/{WORKSPACE_ID}/agents/studio: Created {agent['agent_id']}")

    def test_update_agent_via_studio(self, session):
        """PUT /api/workspaces/{ws_id}/agents/{agent_id}/studio - Update agent"""
        if not TestAgentStudioAPI.created_agent_id:
            pytest.skip("No agent created to update")
        
        update_data = {
            "description": "Updated description via studio",
            "personality": {
                "tone": "friendly",
                "verbosity": "detailed",
                "risk_tolerance": "conservative",
                "collaboration_style": "reviewer"
            }
        }
        res = session.put(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{TestAgentStudioAPI.created_agent_id}/studio",
            json=update_data
        )
        assert res.status_code == 200, f"Update failed: {res.text}"
        agent = res.json()
        assert agent["description"] == "Updated description via studio"
        assert agent["personality"]["tone"] == "friendly"
        assert agent["version"] == 2  # Version should increment
        print(f"✓ PUT /api/workspaces/{WORKSPACE_ID}/agents/{TestAgentStudioAPI.created_agent_id}/studio: Version {agent['version']}")

    def test_get_agent_versions(self, session):
        """GET /api/workspaces/{ws_id}/agents/{agent_id}/versions - Get version history"""
        if not TestAgentStudioAPI.created_agent_id:
            pytest.skip("No agent created")
        
        res = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{TestAgentStudioAPI.created_agent_id}/versions")
        assert res.status_code == 200
        data = res.json()
        assert "current_version" in data
        assert "history" in data
        assert data["current_version"] >= 2
        print(f"✓ GET /api/workspaces/{WORKSPACE_ID}/agents/{TestAgentStudioAPI.created_agent_id}/versions: Current version {data['current_version']}")

    def test_clone_agent(self, session):
        """POST /api/workspaces/{ws_id}/agents/{agent_id}/clone - Clone an agent"""
        if not TestAgentStudioAPI.created_agent_id:
            pytest.skip("No agent created to clone")
        
        res = session.post(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{TestAgentStudioAPI.created_agent_id}/clone")
        assert res.status_code == 200, f"Clone failed: {res.text}"
        clone = res.json()
        assert "agent_id" in clone
        assert clone["agent_id"] != TestAgentStudioAPI.created_agent_id
        assert "(Clone)" in clone["name"]
        assert clone["forked_from"] == TestAgentStudioAPI.created_agent_id
        print(f"✓ POST /api/workspaces/{WORKSPACE_ID}/agents/{TestAgentStudioAPI.created_agent_id}/clone: Created {clone['agent_id']}")

    def test_update_agent_status(self, session):
        """PATCH /api/workspaces/{ws_id}/agents/{agent_id}/status - Update status (active/paused)"""
        if not TestAgentStudioAPI.created_agent_id:
            pytest.skip("No agent created")
        
        # Pause
        res = session.patch(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{TestAgentStudioAPI.created_agent_id}/status",
            json={"status": "paused"}
        )
        assert res.status_code == 200
        assert res.json()["status"] == "paused"
        
        # Activate
        res = session.patch(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{TestAgentStudioAPI.created_agent_id}/status",
            json={"status": "active"}
        )
        assert res.status_code == 200
        assert res.json()["status"] == "active"
        print(f"✓ PATCH /api/workspaces/{WORKSPACE_ID}/agents/{TestAgentStudioAPI.created_agent_id}/status: active")

    def test_preview_agent_prompt(self, session):
        """POST /api/workspaces/{ws_id}/agents/{agent_id}/preview - Preview assembled prompt"""
        if not TestAgentStudioAPI.created_agent_id:
            pytest.skip("No agent created")
        
        res = session.post(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{TestAgentStudioAPI.created_agent_id}/preview",
            json={"prompt": "Hello, introduce yourself."}
        )
        assert res.status_code == 200, f"Preview failed: {res.text}"
        data = res.json()
        assert "assembled_prompt_preview" in data
        assert "prompt_length" in data
        assert data["prompt_length"] > 0
        print(f"✓ POST /api/workspaces/{WORKSPACE_ID}/agents/{TestAgentStudioAPI.created_agent_id}/preview: {data['prompt_length']} chars")


# ==================== SKILLS MATRIX API ====================

class TestSkillsMatrixAPI:
    """Agent Skills Matrix endpoint tests (authenticated)"""

    def test_get_agent_skills(self, session):
        """GET /api/workspaces/{ws_id}/agents/{agent_id}/skills - Get agent skill proficiency"""
        # Use existing test agent
        agent_id = "nxa_80888f5c29d3"
        res = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{agent_id}/skills")
        assert res.status_code == 200, f"Get skills failed: {res.text}"
        data = res.json()
        assert "proficiency" in data
        assert "configured_skills" in data
        assert "evaluation" in data
        print(f"✓ GET /api/workspaces/{WORKSPACE_ID}/agents/{agent_id}/skills: {len(data['configured_skills'])} configured skills")

    def test_run_skill_assessment(self, session):
        """POST /api/workspaces/{ws_id}/agents/{agent_id}/skills/assess - Run skill assessment"""
        agent_id = "nxa_80888f5c29d3"
        res = session.post(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{agent_id}/skills/assess",
            json={"skill_ids": ["code_review"]}
        )
        assert res.status_code == 200, f"Assess failed: {res.text}"
        data = res.json()
        assert "assessment_id" in data
        assert data["status"] == "pending"
        assert data["agent_id"] == agent_id
        print(f"✓ POST /api/workspaces/{WORKSPACE_ID}/agents/{agent_id}/skills/assess: {data['assessment_id']}")

    def test_workspace_skill_leaderboard(self, session):
        """GET /api/workspaces/{ws_id}/skills/leaderboard - Workspace skill leaderboard"""
        res = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/skills/leaderboard")
        assert res.status_code == 200, f"Leaderboard failed: {res.text}"
        data = res.json()
        assert "leaderboard" in data
        print(f"✓ GET /api/workspaces/{WORKSPACE_ID}/skills/leaderboard: {len(data['leaderboard'])} entries")


# ==================== AGENT ANALYTICS API ====================

class TestAgentAnalyticsAPI:
    """Agent Analytics endpoint tests (authenticated)"""

    def test_get_agent_analytics(self, session):
        """GET /api/workspaces/{ws_id}/agents/{agent_id}/analytics - Agent analytics dashboard"""
        agent_id = "nxa_80888f5c29d3"
        res = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{agent_id}/analytics")
        assert res.status_code == 200, f"Analytics failed: {res.text}"
        data = res.json()
        assert "agent" in data
        assert "stats" in data
        assert "evaluation" in data
        assert "skills" in data
        assert "period_days" in data
        print(f"✓ GET /api/workspaces/{WORKSPACE_ID}/agents/{agent_id}/analytics: period={data['period_days']} days")

    def test_compare_agents(self, session):
        """GET /api/workspaces/{ws_id}/agents/compare?agents=id1,id2 - Compare agents"""
        # First get list of agents to compare
        agents_res = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents")
        agents = agents_res.json().get("agents", [])
        if len(agents) < 2:
            pytest.skip("Need at least 2 agents to compare")
        
        agent_ids = ",".join([a["agent_id"] for a in agents[:2]])
        res = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/compare", params={"agents": agent_ids})
        assert res.status_code == 200, f"Compare failed: {res.text}"
        data = res.json()
        assert "agents" in data
        assert len(data["agents"]) == 2
        print(f"✓ GET /api/workspaces/{WORKSPACE_ID}/agents/compare: Compared {len(data['agents'])} agents")

    def test_compare_requires_two_agents(self, session):
        """GET /api/workspaces/{ws_id}/agents/compare - Requires at least 2 agent IDs"""
        res = session.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/compare", params={"agents": "single_id"})
        assert res.status_code == 400
        print("✓ GET compare with single agent returns 400")


# ==================== VALIDATION TESTS ====================

class TestValidation:
    """Input validation tests"""

    def test_create_agent_requires_name(self, session):
        """Agent creation requires name field"""
        res = session.post(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/studio", json={
            "base_model": "claude"
            # Missing name
        })
        assert res.status_code == 422
        print("✓ Create agent without name returns 422")

    def test_create_agent_requires_valid_model(self, session):
        """Agent creation validates base_model"""
        res = session.post(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/studio", json={
            "name": "Test Agent",
            "base_model": "invalid_model_xyz"
        })
        assert res.status_code == 400
        print("✓ Create agent with invalid model returns 400")

    def test_status_update_validates_status(self, session):
        """Status update validates status value"""
        agent_id = "nxa_80888f5c29d3"
        res = session.patch(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/agents/{agent_id}/status",
            json={"status": "invalid_status"}
        )
        assert res.status_code == 400
        print("✓ Status update with invalid status returns 400")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
