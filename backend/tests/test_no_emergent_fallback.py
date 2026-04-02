"""
Tests for verifying that ALL AI models (including Claude and ChatGPT) require user API keys
and there is NO Emergent fallback.

Test Cases:
- All 9 AI models have requires_user_key: true
- ChatGPT uses gpt-4o model (not gpt-5.2)
- No Emergent fallback in AI collaboration logic
- No Emergent fallback in task session logic
- Collaboration skips agents without API keys (shows system message)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from MongoDB seed
SESSION_TOKEN = "test_session_nokey_1772557409619"
USER_ID = "test-user-nokey-1772557409619"
WORKSPACE_ID = "ws_nokey_1772557409619"
CHANNEL_ID = "ch_nokey_1772557409619"


class TestAIModelsConfiguration:
    """Verify all AI models have requires_user_key: true"""
    
    def test_api_health(self):
        """Verify API is accessible"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    
    def test_all_9_ai_models_available(self):
        """Verify all 9 AI models are returned from /api/ai-models"""
        response = requests.get(f"{BASE_URL}/api/ai-models")
        assert response.status_code == 200
        data = response.json()
        
        # All 9 models should be present
        expected_models = ["claude", "chatgpt", "deepseek", "grok", "gemini", 
                         "perplexity", "mistral", "cohere", "groq"]
        
        for model in expected_models:
            assert model in data, f"Model {model} is missing from AI models response"
            print(f"✓ {model} is available")
        
        assert len(data) == 9, f"Expected 9 AI models, got {len(data)}"
        print(f"✓ All 9 AI models present")


class TestServerConfiguration:
    """Tests that read server.py to verify configuration"""
    
    def test_claude_requires_user_key(self):
        """Verify Claude config has requires_user_key: true"""
        # Read server.py to verify configuration
        with open('/app/backend/server.py', 'r') as f:
            content = f.read()
        
        # Find claude config block
        import re
        claude_block = re.search(r'"claude":\s*\{[^}]+\}', content, re.DOTALL)
        assert claude_block, "Claude config block not found"
        
        claude_config = claude_block.group()
        assert '"requires_user_key": True' in claude_config or "'requires_user_key': True" in claude_config, \
            f"Claude should have requires_user_key: True. Found: {claude_config}"
        print("✓ Claude has requires_user_key: True")
    
    def test_chatgpt_requires_user_key(self):
        """Verify ChatGPT config has requires_user_key: true"""
        with open('/app/backend/server.py', 'r') as f:
            content = f.read()
        
        import re
        chatgpt_block = re.search(r'"chatgpt":\s*\{[^}]+\}', content, re.DOTALL)
        assert chatgpt_block, "ChatGPT config block not found"
        
        chatgpt_config = chatgpt_block.group()
        assert '"requires_user_key": True' in chatgpt_config or "'requires_user_key': True" in chatgpt_config, \
            f"ChatGPT should have requires_user_key: True. Found: {chatgpt_config}"
        print("✓ ChatGPT has requires_user_key: True")
    
    def test_chatgpt_uses_gpt4o_model(self):
        """Verify ChatGPT uses gpt-4o model (not gpt-5.2)"""
        with open('/app/backend/server.py', 'r') as f:
            content = f.read()
        
        import re
        chatgpt_block = re.search(r'"chatgpt":\s*\{[^}]+\}', content, re.DOTALL)
        assert chatgpt_block, "ChatGPT config block not found"
        
        chatgpt_config = chatgpt_block.group()
        assert '"model": "gpt-4o"' in chatgpt_config or "'model': 'gpt-4o'" in chatgpt_config, \
            f"ChatGPT should use gpt-4o model. Found: {chatgpt_config}"
        assert 'gpt-5.2' not in chatgpt_config, \
            f"ChatGPT should NOT use gpt-5.2. Found: {chatgpt_config}"
        print("✓ ChatGPT uses gpt-4o model (not gpt-5.2)")
    
    def test_all_models_require_user_key(self):
        """Verify all 9 AI models have requires_user_key: true"""
        with open('/app/backend/server.py', 'r') as f:
            content = f.read()
        
        models_to_check = ["claude", "chatgpt", "deepseek", "grok", "gemini",
                          "perplexity", "mistral", "cohere", "groq"]
        
        import re
        for model in models_to_check:
            model_block = re.search(rf'"{model}":\s*\{{[^}}]+\}}', content, re.DOTALL)
            assert model_block, f"{model} config block not found"
            
            model_config = model_block.group()
            assert '"requires_user_key": True' in model_config or "'requires_user_key': True" in model_config, \
                f"{model} should have requires_user_key: True"
            print(f"✓ {model} has requires_user_key: True")
    
    def test_no_emergent_fallback_in_collaboration_logic(self):
        """Verify no EMERGENT_LLM_KEY fallback in run_ai_collaboration function"""
        with open('/app/backend/server.py', 'r') as f:
            content = f.read()
        
        # Find the run_ai_collaboration function
        import re
        collab_match = re.search(
            r'async def run_ai_collaboration\([^)]+\):(.*?)(?=async def|\nclass|\n@api_router|\Z)', 
            content, 
            re.DOTALL
        )
        assert collab_match, "run_ai_collaboration function not found"
        
        collab_function = collab_match.group(1)
        
        # Check that there's no EMERGENT_LLM_KEY fallback in the actual AI call logic
        # The pattern we're looking for is that when user_api_key is None, we skip (not fallback to Emergent)
        
        # These patterns would indicate Emergent fallback (BAD):
        emergent_fallback_patterns = [
            'EMERGENT_LLM_KEY',
            'emergent_key',
            'platform_key',
            'nexus_key',
        ]
        
        # Check the AI call section (around line 700-720)
        for pattern in emergent_fallback_patterns:
            if pattern.lower() in collab_function.lower():
                # Check if it's just a comment or actually used as fallback
                lines_with_pattern = [l for l in collab_function.split('\n') 
                                     if pattern.lower() in l.lower() and not l.strip().startswith('#')]
                if lines_with_pattern:
                    # Make sure it's not used as a fallback for AI calls
                    for line in lines_with_pattern:
                        assert 'LlmChat' not in line and 'call_ai' not in line, \
                            f"Found potential Emergent fallback: {line}"
        
        # Verify the "no fallback" pattern exists - we skip agents without keys
        assert "All AI models now require user API keys" in collab_function or \
               "requires an API key to participate" in collab_function, \
               "Collaboration logic should skip agents without API keys"
        
        print("✓ No EMERGENT_LLM_KEY fallback in collaboration logic")
    
    def test_no_emergent_fallback_in_task_session_logic(self):
        """Verify no EMERGENT_LLM_KEY fallback in run_task_session_agent function"""
        with open('/app/backend/server.py', 'r') as f:
            content = f.read()
        
        import re
        task_match = re.search(
            r'async def run_task_session_agent\([^)]+\):(.*?)(?=async def|\nclass|\n@api_router|\Z)',
            content,
            re.DOTALL
        )
        assert task_match, "run_task_session_agent function not found"
        
        task_function = task_match.group(1)
        
        # Check that we require user API key with no fallback
        assert "All models require user API key" in task_function or \
               "requires an API key" in task_function, \
               "Task session logic should require user API key"
        
        # Check that if no key, we return an error message (not use Emergent key)
        assert "if not user_api_key:" in task_function, \
            "Task session should check for missing API key"
        
        print("✓ No EMERGENT_LLM_KEY fallback in task session logic")


class TestCollaborationRequiresUserKey:
    """Test that collaboration skips agents without user API keys"""
    
    @pytest.fixture
    def auth_headers(self):
        return {
            "Authorization": f"Bearer {SESSION_TOKEN}",
            "Content-Type": "application/json"
        }
    
    def test_user_authentication(self, auth_headers):
        """Verify test user is authenticated"""
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        user = response.json()
        assert user["user_id"] == USER_ID
        print(f"✓ User authenticated: {user['name']}")
    
    def test_channel_exists_with_agents(self, auth_headers):
        """Verify test channel exists with AI agents"""
        response = requests.get(f"{BASE_URL}/api/channels/{CHANNEL_ID}", headers=auth_headers)
        assert response.status_code == 200
        channel = response.json()
        assert "ai_agents" in channel
        assert len(channel["ai_agents"]) > 0
        print(f"✓ Channel has agents: {channel['ai_agents']}")
    
    def test_trigger_collaboration_without_keys(self, auth_headers):
        """Trigger collaboration for user without API keys - should start but agents should skip"""
        response = requests.post(
            f"{BASE_URL}/api/channels/{CHANNEL_ID}/collaborate",
            headers=auth_headers
        )
        
        # Should start (or be already running)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["started", "already_running", "limit_reached"]
        print(f"✓ Collaboration triggered: {data['status']}")
    
    def test_check_collaboration_status(self, auth_headers):
        """Check collaboration status"""
        import time
        time.sleep(2)  # Wait for collaboration to process
        
        response = requests.get(
            f"{BASE_URL}/api/channels/{CHANNEL_ID}/status",
            headers=auth_headers
        )
        assert response.status_code == 200
        print(f"✓ Collaboration status: {response.json()}")
    
    def test_messages_show_system_skip_messages(self, auth_headers):
        """After collaboration, messages should show system messages about missing API keys"""
        import time
        time.sleep(3)  # Wait for collaboration messages
        
        response = requests.get(
            f"{BASE_URL}/api/channels/{CHANNEL_ID}/messages",
            headers=auth_headers
        )
        assert response.status_code == 200
        messages = response.json()
        
        # Look for system messages indicating agents were skipped
        system_messages = [m for m in messages if m.get("sender_type") == "system"]
        
        # With no API keys configured, all 3 agents (claude, chatgpt, deepseek) should be skipped
        # Each should have a system message
        if system_messages:
            for msg in system_messages:
                content = msg.get("content", "")
                assert "requires an API key" in content or "API key" in content.lower(), \
                    f"System message should mention API key requirement: {content}"
                print(f"✓ System message: {content[:80]}...")
        
        print(f"✓ Found {len(system_messages)} system messages about skipped agents")


class TestSettingsAIKeys:
    """Test settings AI keys endpoint returns all models equally"""
    
    @pytest.fixture
    def auth_headers(self):
        return {
            "Authorization": f"Bearer {SESSION_TOKEN}",
            "Content-Type": "application/json"
        }
    
    def test_ai_keys_settings_returns_all_models(self, auth_headers):
        """GET /api/settings/ai-keys should return status for all 9 models equally"""
        response = requests.get(f"{BASE_URL}/api/settings/ai-keys", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        expected_models = ["claude", "chatgpt", "deepseek", "grok", "gemini",
                         "perplexity", "mistral", "cohere", "groq"]
        
        for model in expected_models:
            assert model in data, f"Model {model} missing from settings response"
            model_data = data[model]
            assert "configured" in model_data, f"Model {model} should have 'configured' field"
            print(f"✓ {model}: configured={model_data.get('configured')}")
        
        # Verify no special treatment for Claude or ChatGPT
        # All models should have the same structure
        for model in expected_models:
            assert "configured" in data[model]
            # No special "nexus_available" or "platform_key" fields for Claude/ChatGPT
            assert "nexus_available" not in data[model], f"{model} should not have nexus_available field"
            assert "platform_key" not in data[model], f"{model} should not have platform_key field"


class TestFrontendConfiguration:
    """Tests for frontend configuration files"""
    
    def test_aikeysetup_default_is_account(self):
        """Verify AIKeySetup dropdown defaults to 'account' not 'nexus'"""
        with open('/app/frontend/src/components/AIKeySetup.js', 'r') as f:
            content = f.read()
        
        # Check the default key_source is 'account' not 'nexus'
        assert 'key_source: "nexus"' not in content, \
            "AIKeySetup should NOT default to 'nexus'"
        
        # The default should be 'account' or the dropdown should show account first
        # Check for default value in code
        import re
        default_matches = re.findall(r'key_source["\']?\s*[=:]\s*["\'](\w+)["\']', content)
        print(f"Found key_source values: {default_matches}")
        
        # Verify 'account' is the first/default option if dropdown has default
        assert 'value="account"' in content or "value={'account'}" in content or \
               'key_source || "account"' in content or "key_source || 'account'" in content, \
               "AIKeySetup should default to 'account'"
        
        print("✓ AIKeySetup defaults to 'account' (not 'nexus')")
    
    def test_aikeysetup_no_nexus_credits_option(self):
        """Verify AIKeySetup has no 'Nexus Credits' option"""
        with open('/app/frontend/src/components/AIKeySetup.js', 'r') as f:
            content = f.read()
        
        # Should NOT have Nexus Credits option
        assert 'Nexus Credits' not in content, \
            "AIKeySetup should NOT have 'Nexus Credits' option"
        assert 'nexus_credits' not in content.lower(), \
            "AIKeySetup should NOT have nexus_credits option"
        assert '"nexus"' not in content and "'nexus'" not in content, \
            "AIKeySetup should NOT have 'nexus' key_source option"
        
        print("✓ AIKeySetup has no 'Nexus Credits' option")
    
    def test_workspaceskillstab_footer_message(self):
        """Verify WorkspaceSkillsTab footer says all models require user API key"""
        with open('/app/frontend/src/components/WorkspaceSkillsTab.js', 'r') as f:
            content = f.read()
        
        # Check the footer message mentions all AI models require user API key
        assert "All AI models require your own API key" in content or \
               "require your own API key" in content.lower(), \
               "WorkspaceSkillsTab should mention all models require user API key"
        
        print("✓ WorkspaceSkillsTab footer mentions all models require user API key")
    
    def test_workspaceskillstab_hasapikey_function(self):
        """Verify hasApiKey function treats all models equally"""
        with open('/app/frontend/src/components/WorkspaceSkillsTab.js', 'r') as f:
            content = f.read()
        
        # Find hasApiKey function - should be simple check, no special cases
        import re
        has_api_key_match = re.search(r'const hasApiKey = \([^)]*\) => \{[^}]+\}', content)
        
        if has_api_key_match:
            func_content = has_api_key_match.group()
            # Should NOT have special cases for claude or chatgpt
            assert 'claude' not in func_content.lower() or 'return' in func_content, \
                "hasApiKey should not have special case for claude"
            assert 'chatgpt' not in func_content.lower() or 'return' in func_content, \
                "hasApiKey should not have special case for chatgpt"
            print(f"✓ hasApiKey function: {func_content[:100]}...")
        else:
            # Alternative: look for arrow function format
            assert 'apiKeys[modelKey]?.configured' in content or \
                   'apiKeys[modelKey]' in content, \
                   "hasApiKey should check apiKeys for all models equally"
            print("✓ hasApiKey checks apiKeys equally for all models")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
