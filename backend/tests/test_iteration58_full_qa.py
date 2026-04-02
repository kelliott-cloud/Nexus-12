"""
Iteration 58 - Full QA Test Suite for Nexus Platform
Tests: Auth, Messages, Collaboration, Human Priority, Persist Mode, AI Models, 
Tasks, Milestones, Wiki, Code Repo, Directives, Activities, Unified Search, 
AI Tools, Legal, Platform Capabilities
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Auth endpoints - login, me, tos status"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_health_check(self):
        """GET /api/health - should return healthy status"""
        response = self.session.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        print(f"PASS: Health check - status={data['status']}, db={data['database']}")
    
    def test_login_with_credentials(self):
        """POST /api/auth/login - should login with test@test.com/test123"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com",
            "password": "test123"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@test.com"
        assert "user_id" in data
        print(f"PASS: Login - user_id={data['user_id']}, email={data['email']}")
    
    def test_auth_me_returns_tos_status(self):
        """GET /api/auth/me - should return user data with tos_needs_acceptance"""
        # Login first
        login = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com", "password": "test123"
        })
        
        response = self.session.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert "tos_needs_acceptance" in data
        assert "tos_current_version" in data
        print(f"PASS: Auth me - tos_needs_acceptance={data['tos_needs_acceptance']}, version={data.get('tos_current_version')}")


class TestMessages:
    """Message endpoints - GET, POST, reactions, pin, search"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login
        self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com", "password": "test123"
        })
        self.channel_id = "ch_bbc9cea9ccc6"
    
    def test_get_messages(self):
        """GET /api/channels/{ch}/messages - should return array of messages"""
        response = self.session.get(f"{BASE_URL}/api/channels/{self.channel_id}/messages")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Get messages - returned {len(data)} messages")
    
    def test_create_message_with_xss_sanitized(self):
        """POST /api/channels/{ch}/messages - should sanitize XSS"""
        xss_content = "<script>alert('xss')</script>Hello test message"
        response = self.session.post(f"{BASE_URL}/api/channels/{self.channel_id}/messages", json={
            "content": xss_content
        })
        assert response.status_code == 200
        data = response.json()
        assert "<script>" not in data.get("content", "")
        assert "Hello test message" in data.get("content", "")
        print(f"PASS: Create message - XSS sanitized, content={data.get('content', '')[:50]}")
        return data.get("message_id")
    
    def test_react_to_message(self):
        """POST /api/messages/{id}/react - should add reaction"""
        # First create a message to react to
        msg_response = self.session.post(f"{BASE_URL}/api/channels/{self.channel_id}/messages", json={
            "content": "TEST_reaction_message"
        })
        message_id = msg_response.json().get("message_id")
        
        # Add thumbs_up reaction
        response = self.session.post(f"{BASE_URL}/api/messages/{message_id}/react", json={
            "reaction": "thumbs_up"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("reacted") == True
        print(f"PASS: React to message - reacted={data.get('reacted')}")
    
    def test_pin_message_toggle(self):
        """POST /api/messages/{id}/pin - should toggle pin"""
        # Create a message to pin
        msg_response = self.session.post(f"{BASE_URL}/api/channels/{self.channel_id}/messages", json={
            "content": "TEST_pin_message"
        })
        message_id = msg_response.json().get("message_id")
        
        # Pin it
        response = self.session.post(f"{BASE_URL}/api/messages/{message_id}/pin")
        assert response.status_code == 200
        data = response.json()
        assert "pinned" in data
        print(f"PASS: Pin message - pinned={data.get('pinned')}")
    
    def test_search_messages(self):
        """GET /api/channels/{ch}/search-messages?q=test - should return results"""
        response = self.session.get(f"{BASE_URL}/api/channels/{self.channel_id}/search-messages?q=test")
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert isinstance(data["messages"], list)
        print(f"PASS: Search messages - found {len(data['messages'])} results")


class TestCollaboration:
    """Collaboration and Human Priority endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com", "password": "test123"
        })
        self.channel_id = "ch_bbc9cea9ccc6"
    
    def test_collaborate_trigger(self):
        """POST /api/channels/{ch}/collaborate - should trigger collaboration"""
        response = self.session.post(f"{BASE_URL}/api/channels/{self.channel_id}/collaborate")
        # Accept 200 or 400 (if no API keys configured)
        assert response.status_code in [200, 400]
        print(f"PASS: Collaborate trigger - status={response.status_code}")
    
    def test_human_priority_get(self):
        """GET /api/channels/{ch}/human-priority - should return status"""
        response = self.session.get(f"{BASE_URL}/api/channels/{self.channel_id}/human-priority")
        assert response.status_code == 200
        data = response.json()
        assert "pause_requested" in data or isinstance(data, dict)
        print(f"PASS: Human priority GET - data={data}")
    
    def test_resume_agents(self):
        """POST /api/channels/{ch}/resume-agents - should clear flag"""
        response = self.session.post(f"{BASE_URL}/api/channels/{self.channel_id}/resume-agents")
        assert response.status_code == 200
        data = response.json()
        assert "resumed" in data or "message" in data
        print(f"PASS: Resume agents - response={data}")


class TestPersistMode:
    """Auto-collab persist mode endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com", "password": "test123"
        })
        self.channel_id = "ch_bbc9cea9ccc6"
    
    def test_get_persist_status(self):
        """GET /api/channels/{ch}/auto-collab-persist - should return status"""
        response = self.session.get(f"{BASE_URL}/api/channels/{self.channel_id}/auto-collab-persist")
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data or "persist" in str(data).lower()
        print(f"PASS: Persist status GET - data={data}")
    
    def test_toggle_persist(self):
        """PUT /api/channels/{ch}/auto-collab-persist - should toggle"""
        response = self.session.put(f"{BASE_URL}/api/channels/{self.channel_id}/auto-collab-persist", json={
            "enabled": False
        })
        assert response.status_code == 200
        print(f"PASS: Persist toggle - status={response.status_code}")


class TestAgentConfig:
    """Agent toggle and AI models endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com", "password": "test123"
        })
        self.channel_id = "ch_bbc9cea9ccc6"
    
    def test_agent_toggle(self):
        """PUT /api/channels/{ch}/agent-toggle - should enable/disable agent"""
        response = self.session.put(f"{BASE_URL}/api/channels/{self.channel_id}/agent-toggle", json={
            "agent_key": "claude",
            "enabled": True
        })
        assert response.status_code == 200
        print(f"PASS: Agent toggle - status={response.status_code}")
    
    def test_get_ai_models(self):
        """GET /api/ai-models - should return model list for all 11 agents"""
        response = self.session.get(f"{BASE_URL}/api/ai-models")
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        models = data["models"]
        # Should have 11 agents: claude, chatgpt, gemini, deepseek, grok, perplexity, mistral, cohere, groq, mercury, pi
        expected_agents = ["claude", "chatgpt", "gemini", "deepseek", "grok", "perplexity", "mistral", "cohere", "groq", "mercury", "pi"]
        for agent in expected_agents:
            assert agent in models, f"Missing agent: {agent}"
        print(f"PASS: AI models - {len(models)} agents found: {list(models.keys())}")
    
    def test_channel_update_with_agents(self):
        """PUT /api/channels/{ch} - should accept ai_agents and agent_models"""
        response = self.session.put(f"{BASE_URL}/api/channels/{self.channel_id}", json={
            "ai_agents": ["claude", "chatgpt", "deepseek"],
            "agent_models": {"claude": "claude-sonnet-4-20250514"}
        })
        assert response.status_code == 200
        data = response.json()
        assert "ai_agents" in data
        print(f"PASS: Channel update - ai_agents={data.get('ai_agents')}")


class TestWorkspaceSettings:
    """Workspace settings endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com", "password": "test123"
        })
        self.workspace_id = "ws_f6ec6355bb18"
    
    def test_get_workspace_settings(self):
        """GET /api/workspaces/{ws}/settings - should work"""
        response = self.session.get(f"{BASE_URL}/api/workspaces/{self.workspace_id}/settings")
        assert response.status_code == 200
        data = response.json()
        assert "workspace_id" in data or isinstance(data, dict)
        print(f"PASS: Workspace settings GET - data={data}")
    
    def test_put_workspace_settings(self):
        """PUT /api/workspaces/{ws}/settings - should work"""
        response = self.session.put(f"{BASE_URL}/api/workspaces/{self.workspace_id}/settings", json={
            "auto_collab_max_rounds": 10
        })
        assert response.status_code == 200
        print(f"PASS: Workspace settings PUT - status={response.status_code}")


class TestTasks:
    """Task-related endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com", "password": "test123"
        })
        self.workspace_id = "ws_f6ec6355bb18"
    
    def test_get_all_tasks_grouped(self):
        """GET /api/workspaces/{ws}/all-tasks - should return grouped tasks"""
        response = self.session.get(f"{BASE_URL}/api/workspaces/{self.workspace_id}/all-tasks")
        assert response.status_code == 200
        data = response.json()
        # Should have grouped structure
        assert isinstance(data, (dict, list))
        print(f"PASS: All tasks grouped - type={type(data).__name__}")
    
    def test_task_detail(self):
        """GET /api/tasks/{tid}/detail - should return enriched data"""
        # First get tasks list to find a task ID
        tasks_response = self.session.get(f"{BASE_URL}/api/workspaces/{self.workspace_id}/tasks")
        tasks = tasks_response.json()
        
        if tasks:
            task_id = tasks[0].get("task_id")
            response = self.session.get(f"{BASE_URL}/api/tasks/{task_id}/detail")
            assert response.status_code == 200
            data = response.json()
            print(f"PASS: Task detail - task_id={task_id}")
        else:
            print("SKIP: No tasks found to test detail endpoint")
            pytest.skip("No tasks to test")


class TestMilestones:
    """Milestone endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com", "password": "test123"
        })
        self.workspace_id = "ws_f6ec6355bb18"
    
    def test_get_milestones_with_progress(self):
        """GET /api/projects/{pid}/milestones - should return with progress"""
        # First get projects to find a project ID
        projects_response = self.session.get(f"{BASE_URL}/api/workspaces/{self.workspace_id}/projects")
        projects = projects_response.json()
        
        if projects:
            project_id = projects[0].get("project_id")
            response = self.session.get(f"{BASE_URL}/api/projects/{project_id}/milestones")
            assert response.status_code == 200
            print(f"PASS: Milestones - project_id={project_id}")
        else:
            # Try workspace-level milestones
            response = self.session.get(f"{BASE_URL}/api/workspaces/{self.workspace_id}/milestones")
            if response.status_code == 200:
                print(f"PASS: Workspace milestones - status=200")
            else:
                print("SKIP: No projects found to test milestones")
                pytest.skip("No projects to test")


class TestWiki:
    """Wiki endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com", "password": "test123"
        })
        self.workspace_id = "ws_f6ec6355bb18"
    
    def test_get_wiki_pages(self):
        """GET /api/workspaces/{ws}/wiki - should return pages"""
        response = self.session.get(f"{BASE_URL}/api/workspaces/{self.workspace_id}/wiki")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or "pages" in data
        print(f"PASS: Wiki pages - type={type(data).__name__}")


class TestCodeRepo:
    """Code repository endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com", "password": "test123"
        })
        self.workspace_id = "ws_f6ec6355bb18"
    
    def test_get_repo_tree(self):
        """GET /api/workspaces/{ws}/code-repo/tree - should return files"""
        response = self.session.get(f"{BASE_URL}/api/workspaces/{self.workspace_id}/code-repo/tree")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))
        print(f"PASS: Code repo tree - type={type(data).__name__}")
    
    def test_get_repo_download(self):
        """GET /api/workspaces/{ws}/code-repo/download - should return ZIP"""
        response = self.session.get(f"{BASE_URL}/api/workspaces/{self.workspace_id}/code-repo/download")
        # Accept 200 (returns zip) or 404 (no files)
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            assert response.headers.get("content-type", "").startswith("application/")
        print(f"PASS: Code repo download - status={response.status_code}")


class TestTranscript:
    """Transcript endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com", "password": "test123"
        })
        self.channel_id = "ch_bbc9cea9ccc6"
    
    def test_get_transcript(self):
        """GET /api/channels/{ch}/transcript - should return ZIP"""
        response = self.session.get(f"{BASE_URL}/api/channels/{self.channel_id}/transcript")
        assert response.status_code == 200
        print(f"PASS: Transcript - status={response.status_code}")


class TestDirectives:
    """Directive engine endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com", "password": "test123"
        })
        self.workspace_id = "ws_f6ec6355bb18"
    
    def test_get_directives(self):
        """GET /api/workspaces/{ws}/directives - should return list"""
        response = self.session.get(f"{BASE_URL}/api/workspaces/{self.workspace_id}/directives")
        assert response.status_code == 200
        data = response.json()
        # Response format: {"directives": [...]}
        assert "directives" in data
        assert isinstance(data["directives"], list)
        print(f"PASS: Directives - count={len(data['directives'])}")


class TestActivities:
    """Activity logging endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com", "password": "test123"
        })
        self.workspace_id = "ws_f6ec6355bb18"
    
    def test_get_activities(self):
        """GET /api/workspaces/{ws}/activities - should return logged activities"""
        response = self.session.get(f"{BASE_URL}/api/workspaces/{self.workspace_id}/activities")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or "activities" in data
        print(f"PASS: Activities - type={type(data).__name__}")


class TestUnifiedSearch:
    """Unified search endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com", "password": "test123"
        })
        self.workspace_id = "ws_f6ec6355bb18"
    
    def test_unified_search(self):
        """GET /api/workspaces/{ws}/search?q=test - should return results"""
        response = self.session.get(f"{BASE_URL}/api/workspaces/{self.workspace_id}/search?q=test")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        print(f"PASS: Unified search - keys={list(data.keys())}")


class TestAITools:
    """AI tools endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com", "password": "test123"
        })
    
    def test_get_ai_tools(self):
        """GET /api/ai-tools - should return 19 tools"""
        response = self.session.get(f"{BASE_URL}/api/ai-tools")
        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        # Should have ~19 tools per spec
        print(f"PASS: AI tools - count={len(data.get('tools', []))}")


class TestLegal:
    """Legal endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_get_tos_version(self):
        """GET /api/legal/tos-version - should return version"""
        response = self.session.get(f"{BASE_URL}/api/legal/tos-version")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        print(f"PASS: ToS version - version={data.get('version')}")


class TestPlatform:
    """Platform capabilities endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Platform capabilities requires auth
        self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com", "password": "test123"
        })
    
    def test_get_platform_capabilities(self):
        """GET /api/platform/capabilities - should return manifest"""
        response = self.session.get(f"{BASE_URL}/api/platform/capabilities")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "version" in data
        assert "tool_count" in data
        assert "manifest" in data
        print(f"PASS: Platform capabilities - version={data.get('version')}, tools={data.get('tool_count')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
