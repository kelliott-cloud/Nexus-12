from conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, BASE_URL
"""
Iteration 92 — Tests for 7 new AI agents integration
Tests: Qwen, Kimi, Llama, GLM, Cursor, NotebookLM, GitHub Copilot

New agents integrated into:
- Backend: nexus_config.py, ai_providers.py, smart_routing.py, routes_workspaces.py
- Frontend: All agent lists in ChatPanel.js, Sidebar.js, LandingPage.js, SettingsPage.js, etc.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# All 19 expected agents
EXPECTED_AGENTS = [
    "claude", "chatgpt", "gemini", "perplexity", "mistral", "cohere", "groq",
    "deepseek", "grok", "mercury", "pi", "manus",  # 12 original
    "qwen", "kimi", "llama", "glm", "cursor", "notebooklm", "copilot"  # 7 new
]

# New agents with expected model variants
NEW_AGENTS_MODELS = {
    "qwen": ["qwen-plus", "qwen-max", "qwen-turbo"],
    "kimi": ["kimi-k2.5", "moonshot-v1-128k"],
    "llama": ["meta-llama/Llama-4-Scout-17B-16E-Instruct", "meta-llama/Llama-4-Maverick-17B-128E-Instruct", "meta-llama/Llama-3.3-70B-Instruct-Turbo"],
    "glm": ["glm-4-plus", "glm-4"],
    "cursor": ["anthropic/claude-sonnet-4", "anthropic/claude-3.5-sonnet"],
    "notebooklm": ["google/gemini-2.5-pro-preview", "google/gemini-2.0-flash-001"],
    "copilot": ["openai/gpt-4o", "openai/gpt-4o-mini"]
}


@pytest.fixture(scope="module")
def session():
    """Get authenticated session"""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    
    # Login
    res = s.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_ADMIN_EMAIL,
        "password": "test"
    })
    if res.status_code != 200:
        pytest.skip("Could not authenticate")
    return s


class TestAiModelsEndpoint:
    """Tests for GET /api/ai-models endpoint"""
    
    def test_ai_models_returns_19_agents(self, session):
        """Verify /api/ai-models returns exactly 19 agents"""
        res = session.get(f"{BASE_URL}/api/ai-models")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        
        data = res.json()
        assert "models" in data
        agent_keys = list(data["models"].keys())
        
        assert len(agent_keys) == 19, f"Expected 19 agents, got {len(agent_keys)}"
        print(f"✓ /api/ai-models returns 19 agents")
    
    def test_all_expected_agents_present(self, session):
        """Verify all 19 expected agents are in the response"""
        res = session.get(f"{BASE_URL}/api/ai-models")
        assert res.status_code == 200
        
        data = res.json()
        agent_keys = list(data["models"].keys())
        
        for agent in EXPECTED_AGENTS:
            assert agent in agent_keys, f"Missing agent: {agent}"
        print(f"✓ All 19 expected agents present")
    
    def test_new_agents_have_models(self, session):
        """Verify each new agent has model variants"""
        res = session.get(f"{BASE_URL}/api/ai-models")
        assert res.status_code == 200
        
        data = res.json()
        models = data["models"]
        
        for agent_key, expected_model_ids in NEW_AGENTS_MODELS.items():
            assert agent_key in models, f"New agent {agent_key} not in response"
            agent_models = models[agent_key]
            assert len(agent_models) > 0, f"Agent {agent_key} has no models"
            
            # Check at least the first expected model is present
            model_ids = [m["id"] for m in agent_models]
            assert expected_model_ids[0] in model_ids, f"Agent {agent_key} missing default model {expected_model_ids[0]}"
            print(f"✓ {agent_key}: {len(agent_models)} model(s) available")
    
    def test_qwen_models(self, session):
        """Test Qwen (Alibaba Cloud) model variants"""
        res = session.get(f"{BASE_URL}/api/ai-models")
        assert res.status_code == 200
        
        models = res.json()["models"]
        assert "qwen" in models
        
        qwen_models = models["qwen"]
        model_ids = [m["id"] for m in qwen_models]
        
        assert "qwen-plus" in model_ids, "Missing qwen-plus"
        assert any(m.get("default") for m in qwen_models), "Qwen should have a default model"
        print(f"✓ Qwen models: {model_ids}")
    
    def test_kimi_models(self, session):
        """Test Kimi (Moonshot AI) model variants"""
        res = session.get(f"{BASE_URL}/api/ai-models")
        assert res.status_code == 200
        
        models = res.json()["models"]
        assert "kimi" in models
        
        kimi_models = models["kimi"]
        model_ids = [m["id"] for m in kimi_models]
        
        assert "kimi-k2.5" in model_ids, "Missing kimi-k2.5"
        print(f"✓ Kimi models: {model_ids}")
    
    def test_llama_models(self, session):
        """Test Llama (Meta AI via Together) model variants"""
        res = session.get(f"{BASE_URL}/api/ai-models")
        assert res.status_code == 200
        
        models = res.json()["models"]
        assert "llama" in models
        
        llama_models = models["llama"]
        model_ids = [m["id"] for m in llama_models]
        
        assert any("Llama-4" in m for m in model_ids), "Missing Llama 4 model"
        print(f"✓ Llama models: {model_ids}")
    
    def test_glm_models(self, session):
        """Test GLM (Zhipu AI) model variants"""
        res = session.get(f"{BASE_URL}/api/ai-models")
        assert res.status_code == 200
        
        models = res.json()["models"]
        assert "glm" in models
        
        glm_models = models["glm"]
        model_ids = [m["id"] for m in glm_models]
        
        assert "glm-4-plus" in model_ids, "Missing glm-4-plus"
        print(f"✓ GLM models: {model_ids}")
    
    def test_cursor_models(self, session):
        """Test Cursor (via OpenRouter) model variants"""
        res = session.get(f"{BASE_URL}/api/ai-models")
        assert res.status_code == 200
        
        models = res.json()["models"]
        assert "cursor" in models
        
        cursor_models = models["cursor"]
        model_ids = [m["id"] for m in cursor_models]
        
        assert "anthropic/claude-sonnet-4" in model_ids, "Missing Claude Sonnet 4 for Cursor"
        print(f"✓ Cursor models: {model_ids}")
    
    def test_notebooklm_models(self, session):
        """Test NotebookLM (via OpenRouter) model variants"""
        res = session.get(f"{BASE_URL}/api/ai-models")
        assert res.status_code == 200
        
        models = res.json()["models"]
        assert "notebooklm" in models
        
        nlm_models = models["notebooklm"]
        model_ids = [m["id"] for m in nlm_models]
        
        assert "google/gemini-2.5-pro-preview" in model_ids, "Missing Gemini 2.5 Pro for NotebookLM"
        print(f"✓ NotebookLM models: {model_ids}")
    
    def test_copilot_models(self, session):
        """Test GitHub Copilot (via OpenRouter) model variants"""
        res = session.get(f"{BASE_URL}/api/ai-models")
        assert res.status_code == 200
        
        models = res.json()["models"]
        assert "copilot" in models
        
        copilot_models = models["copilot"]
        model_ids = [m["id"] for m in copilot_models]
        
        assert "openai/gpt-4o" in model_ids, "Missing GPT-4o for Copilot"
        print(f"✓ Copilot models: {model_ids}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
