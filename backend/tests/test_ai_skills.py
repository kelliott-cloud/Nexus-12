"""
Test AI Skills API - Tests for vendor-supported AI skill libraries feature
Tests skill fetching, workspace skill config, enabling/disabling skills
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from MongoDB seed
SESSION_TOKEN = "test_session_skills_1772556314476"
USER_ID = "test-user-skills-1772556314476"
WORKSPACE_ID = "ws_testskills_1772556314476"
CHANNEL_ID = "ch_testskills_1772556314476"


@pytest.fixture
def api_client():
    """Shared requests session with auth header"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {SESSION_TOKEN}"
    })
    return session


@pytest.fixture
def unauth_client():
    """Session without auth"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestGetAvailableSkills:
    """Test GET /api/ai-skills - fetch all available skills by model"""
    
    def test_get_all_available_skills(self, api_client):
        """Should return all AI skills by model with 9 models"""
        response = api_client.get(f"{BASE_URL}/api/ai-skills")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "skills_by_model" in data, "Response should have skills_by_model"
        assert "categories" in data, "Response should have categories"
        
        # Should have 9 AI models
        skills_by_model = data["skills_by_model"]
        expected_models = ["claude", "chatgpt", "gemini", "deepseek", "grok", "perplexity", "mistral", "cohere", "groq"]
        for model in expected_models:
            assert model in skills_by_model, f"Missing model: {model}"
            assert "name" in skills_by_model[model], f"Model {model} should have name"
            assert "skills" in skills_by_model[model], f"Model {model} should have skills"
            assert len(skills_by_model[model]["skills"]) > 0, f"Model {model} should have at least one skill"
        
        print(f"SUCCESS: Found {len(skills_by_model)} AI models with skills")
    
    def test_skills_have_required_fields(self, api_client):
        """Each skill should have id, name, description, category"""
        response = api_client.get(f"{BASE_URL}/api/ai-skills")
        assert response.status_code == 200
        
        data = response.json()
        for model_key, model_data in data["skills_by_model"].items():
            for skill in model_data["skills"]:
                assert "id" in skill, f"Skill in {model_key} missing id"
                assert "name" in skill, f"Skill in {model_key} missing name"
                assert "description" in skill, f"Skill in {model_key} missing description"
                assert "category" in skill, f"Skill in {model_key} missing category"
        
        print("SUCCESS: All skills have required fields")
    
    def test_categories_returned(self, api_client):
        """Should return skill categories"""
        response = api_client.get(f"{BASE_URL}/api/ai-skills")
        assert response.status_code == 200
        
        data = response.json()
        categories = data["categories"]
        expected_categories = ["code_execution", "search", "functions", "analysis", "generation", "automation"]
        for cat in expected_categories:
            assert cat in categories, f"Missing category: {cat}"
        
        print(f"SUCCESS: Found {len(categories)} skill categories")
    
    def test_requires_authentication(self, unauth_client):
        """Should require authentication"""
        response = unauth_client.get(f"{BASE_URL}/api/ai-skills")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("SUCCESS: Endpoint requires authentication")


class TestWorkspaceSkillsConfig:
    """Test workspace skills configuration endpoints"""
    
    def test_get_workspace_skills_returns_defaults(self, api_client):
        """GET workspace skills should return default config with priority skills enabled"""
        response = api_client.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/ai-skills")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "config" in data, "Response should have config"
        assert "available_skills" in data, "Response should have available_skills"
        assert "categories" in data, "Response should have categories"
        
        config = data["config"]
        assert "enabled_skills" in config, "Config should have enabled_skills"
        
        # Check default enabled skills - code execution skills with priority: true
        enabled = config["enabled_skills"]
        
        # ChatGPT code_interpreter should be enabled by default (priority: true)
        assert "chatgpt" in enabled, "ChatGPT should be in enabled_skills"
        assert "code_interpreter" in enabled.get("chatgpt", []), "ChatGPT code_interpreter should be enabled by default"
        
        # Gemini code_execution should be enabled by default (priority: true)
        assert "gemini" in enabled, "Gemini should be in enabled_skills"
        assert "code_execution" in enabled.get("gemini", []), "Gemini code_execution should be enabled by default"
        
        # DeepSeek code_interpreter should be enabled by default (priority: true)
        assert "deepseek" in enabled, "DeepSeek should be in enabled_skills"
        assert "code_interpreter" in enabled.get("deepseek", []), "DeepSeek code_interpreter should be enabled by default"
        
        # Perplexity web_search should be enabled (always_enabled: true)
        assert "perplexity" in enabled, "Perplexity should be in enabled_skills"
        assert "web_search" in enabled.get("perplexity", []), "Perplexity web_search should be always enabled"
        assert "citations" in enabled.get("perplexity", []), "Perplexity citations should be always enabled"
        
        print("SUCCESS: Default skills configuration returned correctly")
    
    def test_get_workspace_skills_requires_auth(self, unauth_client):
        """Should require authentication"""
        response = unauth_client.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/ai-skills")
        assert response.status_code == 401
        print("SUCCESS: Workspace skills endpoint requires auth")


class TestUpdateWorkspaceSkills:
    """Test PUT /api/workspaces/{id}/ai-skills - update entire skills config"""
    
    def test_update_skills_config(self, api_client):
        """Should update skills configuration for workspace"""
        # Enable specific skills for Claude
        payload = {
            "enabled_skills": {
                "claude": ["tool_use", "vision"],
                "chatgpt": ["code_interpreter", "function_calling"]
            }
        }
        
        response = api_client.put(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/ai-skills", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["status"] == "updated", "Response should indicate updated status"
        assert "config" in data, "Response should return updated config"
        
        # Verify the update
        config = data["config"]
        assert "tool_use" in config["enabled_skills"]["claude"]
        assert "vision" in config["enabled_skills"]["claude"]
        
        print("SUCCESS: Skills configuration updated")
    
    def test_always_enabled_skills_stay_enabled(self, api_client):
        """Always-enabled skills should remain enabled even if not in payload"""
        # Try to set Perplexity skills without web_search
        payload = {
            "enabled_skills": {
                "perplexity": ["academic_search"]  # Omit web_search and citations
            }
        }
        
        response = api_client.put(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/ai-skills", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        perplexity_skills = data["config"]["enabled_skills"]["perplexity"]
        
        # web_search and citations should be auto-added (always_enabled: true)
        assert "web_search" in perplexity_skills, "Perplexity web_search should be always enabled"
        assert "citations" in perplexity_skills, "Perplexity citations should be always enabled"
        assert "academic_search" in perplexity_skills, "academic_search should also be enabled"
        
        print("SUCCESS: Always-enabled skills cannot be disabled")
    
    def test_validates_invalid_model_key(self, api_client):
        """Should reject invalid AI model keys"""
        payload = {
            "enabled_skills": {
                "invalid_model": ["some_skill"]
            }
        }
        
        response = api_client.put(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/ai-skills", json=payload)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert "invalid" in response.text.lower() or "Invalid" in response.text
        
        print("SUCCESS: Invalid model key rejected")
    
    def test_validates_invalid_skill_id(self, api_client):
        """Should reject invalid skill IDs for valid models"""
        payload = {
            "enabled_skills": {
                "claude": ["invalid_skill_id"]
            }
        }
        
        response = api_client.put(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/ai-skills", json=payload)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert "invalid" in response.text.lower() or "Invalid" in response.text
        
        print("SUCCESS: Invalid skill ID rejected")


class TestUpdateModelSkills:
    """Test PUT /api/workspaces/{id}/ai-skills/{model_key} - update single model skills"""
    
    def test_update_single_model_skills(self, api_client):
        """Should update skills for a single AI model"""
        payload = {
            "skill_ids": ["tool_use", "computer_use", "pdf_analysis", "vision"]
        }
        
        response = api_client.put(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/ai-skills/claude", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["status"] == "updated"
        assert data["model"] == "claude"
        assert set(data["enabled_skills"]) == {"tool_use", "computer_use", "pdf_analysis", "vision"}
        
        print("SUCCESS: Single model skills updated")
    
    def test_update_model_validates_skill_ids(self, api_client):
        """Should validate skill IDs for single model update"""
        payload = {
            "skill_ids": ["invalid_skill"]
        }
        
        response = api_client.put(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/ai-skills/claude", json=payload)
        assert response.status_code == 400
        
        print("SUCCESS: Invalid skill ID rejected for single model update")
    
    def test_update_model_validates_model_key(self, api_client):
        """Should validate model key exists"""
        payload = {
            "skill_ids": ["some_skill"]
        }
        
        response = api_client.put(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/ai-skills/invalid_model", json=payload)
        assert response.status_code == 400
        
        print("SUCCESS: Invalid model key rejected")
    
    def test_always_enabled_auto_added(self, api_client):
        """Always-enabled skills should be auto-added for single model update"""
        payload = {
            "skill_ids": []  # Try to disable all skills
        }
        
        response = api_client.put(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/ai-skills/perplexity", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        # web_search and citations should be auto-added
        assert "web_search" in data["enabled_skills"]
        assert "citations" in data["enabled_skills"]
        
        print("SUCCESS: Always-enabled skills auto-added on single model update")


class TestGetModelSkills:
    """Test GET /api/workspaces/{id}/ai-skills/{model_key}"""
    
    def test_get_model_skills(self, api_client):
        """Should return enabled skills for specific model"""
        response = api_client.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/ai-skills/claude")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["model"] == "claude"
        assert "model_name" in data
        assert "enabled_skills" in data
        assert "available_skills" in data
        assert isinstance(data["enabled_skills"], list)
        assert isinstance(data["available_skills"], list)
        
        print(f"SUCCESS: Got skills for Claude - {len(data['enabled_skills'])} enabled, {len(data['available_skills'])} available")
    
    def test_get_model_skills_invalid_model(self, api_client):
        """Should return 400 for invalid model key"""
        response = api_client.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/ai-skills/invalid_model")
        assert response.status_code == 400
        
        print("SUCCESS: Invalid model key returns 400")
    
    def test_get_model_default_skills(self, api_client):
        """Should return default priority skills if no config exists"""
        # Test on a model with priority skills
        response = api_client.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/ai-skills/chatgpt")
        assert response.status_code == 200
        
        data = response.json()
        # Check that available skills are returned
        assert len(data["available_skills"]) > 0
        
        # Find the code_interpreter skill
        code_interpreter = next((s for s in data["available_skills"] if s["id"] == "code_interpreter"), None)
        assert code_interpreter is not None, "ChatGPT should have code_interpreter skill"
        assert code_interpreter.get("priority") == True, "code_interpreter should have priority: true"
        
        print("SUCCESS: Model skills returned with available skills info")


class TestAllModelsHaveSkills:
    """Verify all 9 AI models have proper skill definitions"""
    
    def test_all_nine_models_present(self, api_client):
        """All 9 AI models should be present with skills"""
        response = api_client.get(f"{BASE_URL}/api/ai-skills")
        assert response.status_code == 200
        
        data = response.json()
        skills_by_model = data["skills_by_model"]
        
        models_info = []
        for model in ["claude", "chatgpt", "gemini", "deepseek", "grok", "perplexity", "mistral", "cohere", "groq"]:
            assert model in skills_by_model, f"Missing model: {model}"
            model_data = skills_by_model[model]
            skill_count = len(model_data["skills"])
            models_info.append(f"{model}: {skill_count} skills")
        
        print("SUCCESS: All 9 models present -", ", ".join(models_info))
    
    def test_skill_categories_valid(self, api_client):
        """All skills should have valid categories"""
        response = api_client.get(f"{BASE_URL}/api/ai-skills")
        assert response.status_code == 200
        
        data = response.json()
        valid_categories = set(data["categories"].keys())
        
        for model_key, model_data in data["skills_by_model"].items():
            for skill in model_data["skills"]:
                assert skill["category"] in valid_categories, \
                    f"Invalid category '{skill['category']}' for {model_key}/{skill['id']}"
        
        print(f"SUCCESS: All skills have valid categories from: {valid_categories}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
