"""
Test Suite: Nexus 14 Features
Tests all new endpoints across Content Gen Suite, Drive, Research, Fact Check, Pricing, 
Custom Agents, Workflow Templates, Presence, Export, Multilingual, AI Roles, Voice Notes, Push Notifications
"""
import pytest
import requests
import os
import uuid
import base64
import io

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

@pytest.fixture(scope="module")
def auth_session():
    """Create authenticated session using cookie-based auth"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    # Login
    login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "testmention@test.com",
        "password": "Test1234!"
    })
    if login_resp.status_code != 200:
        pytest.skip(f"Auth failed: {login_resp.status_code} - {login_resp.text[:200]}")
    return session


# =============================================================================
# CONTENT GENERATION SUITE (#1)
# =============================================================================

class TestContentGeneration:
    """Content Generation Suite - documents, slides, templates"""
    
    workspace_id = "ws_bd1750012bfd"
    channel_id = "ch_9988b6543849"
    created_doc_id = None
    created_slides_id = None
    
    def test_get_content_templates(self, auth_session):
        """GET /api/content/templates - returns 6 system templates"""
        resp = auth_session.get(f"{BASE_URL}/api/content/templates")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "templates" in data
        templates = data["templates"]
        # Should have at least 6 system templates
        assert len(templates) >= 6, f"Expected at least 6 templates, got {len(templates)}"
        # Verify expected templates
        template_ids = [t["template_id"] for t in templates]
        expected_templates = ["ct_project_brief", "ct_tech_spec", "ct_pitch_deck", 
                            "ct_quarterly_review", "ct_budget_tracker", "ct_project_plan"]
        for exp in expected_templates:
            assert exp in template_ids, f"Missing template: {exp}"
        print(f"PASS: GET /api/content/templates - returns {len(templates)} templates")
    
    def test_create_document_from_template(self, auth_session):
        """POST /api/content/documents/create - creates doc from template with structure"""
        resp = auth_session.post(f"{BASE_URL}/api/content/documents/create", json={
            "workspace_id": self.workspace_id,
            "content_type": "document",
            "title": "TEST_Project Brief",
            "template_id": "ct_project_brief",
            "prompt": "Create a project brief for testing",
            "model": "claude"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "content_id" in data
        assert data["content_type"] == "document"
        assert data["title"] == "TEST_Project Brief"
        # Verify structure from template
        assert "structure" in data
        assert "sections" in data["structure"]
        expected_sections = ["Executive Summary", "Objectives", "Scope", "Timeline", "Budget", "Team"]
        actual_sections = data["structure"]["sections"]
        for sec in expected_sections:
            assert sec in actual_sections, f"Missing section: {sec}"
        TestContentGeneration.created_doc_id = data["content_id"]
        print(f"PASS: POST /api/content/documents/create - created {data['content_id']} with structure")
    
    def test_create_document_from_chat(self, auth_session):
        """POST /api/content/from-chat - converts chat to document"""
        resp = auth_session.post(f"{BASE_URL}/api/content/from-chat", json={
            "workspace_id": self.workspace_id,
            "channel_id": self.channel_id,
            "title": "TEST_Chat Export",
            "output_type": "document"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "content_id" in data
        assert data["content_type"] == "document"
        assert "structure" in data
        assert "sections" in data["structure"]
        print(f"PASS: POST /api/content/from-chat - created {data['content_id']}")
    
    def test_create_slides(self, auth_session):
        """POST /api/content/slides/create - creates slides"""
        resp = auth_session.post(f"{BASE_URL}/api/content/slides/create", json={
            "workspace_id": self.workspace_id,
            "title": "TEST_Pitch Deck",
            "template_id": "ct_pitch_deck",
            "prompt": "Create a pitch deck for testing",
            "model": "claude"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "content_id" in data
        assert data["content_type"] == "slides"
        assert "structure" in data
        # Pitch deck template should have slides
        assert "slides" in data["structure"]
        expected_slides = ["Title", "Problem", "Solution", "Market Size", "Business Model", "Traction", "Team", "Ask"]
        actual_slides = data["structure"]["slides"]
        for slide in expected_slides:
            assert slide in actual_slides, f"Missing slide: {slide}"
        TestContentGeneration.created_slides_id = data["content_id"]
        print(f"PASS: POST /api/content/slides/create - created {data['content_id']} with {len(actual_slides)} slides")


# =============================================================================
# DRIVE (#2)
# =============================================================================

class TestDrive:
    """Built-in File Storage / Drive"""
    
    workspace_id = "ws_bd1750012bfd"
    created_file_id = None
    created_folder_id = None
    
    def test_create_folder(self, auth_session):
        """POST /api/drive/folder - creates folder"""
        resp = auth_session.post(f"{BASE_URL}/api/drive/folder", json={
            "workspace_id": self.workspace_id,
            "name": "TEST_Folder",
            "path": "/"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "file_id" in data
        assert data["type"] == "folder"
        assert data["name"] == "TEST_Folder"
        TestDrive.created_folder_id = data["file_id"]
        print(f"PASS: POST /api/drive/folder - created {data['file_id']}")
    
    def test_upload_file(self, auth_session):
        """POST /api/drive/upload - uploads file with chunked storage"""
        # Create a test file
        file_content = b"Test file content for Nexus drive testing - " + bytes(str(uuid.uuid4()), "utf-8")
        files = {
            "file": ("TEST_file.txt", io.BytesIO(file_content), "text/plain")
        }
        data = {
            "workspace_id": self.workspace_id,
            "path": "/"
        }
        # Note: for multipart, remove Content-Type header (let requests set it)
        headers = {k: v for k, v in auth_session.headers.items() if k.lower() != "content-type"}
        resp = requests.post(
            f"{BASE_URL}/api/drive/upload",
            files=files,
            data=data,
            cookies=auth_session.cookies,
            headers=headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "file_id" in data
        assert data["type"] == "file"
        assert data["name"] == "TEST_file.txt"
        assert data["size"] == len(file_content)
        TestDrive.created_file_id = data["file_id"]
        print(f"PASS: POST /api/drive/upload - uploaded {data['file_id']} ({data['size']} bytes)")
    
    def test_list_files(self, auth_session):
        """GET /api/drive/list - lists files in path"""
        resp = auth_session.get(f"{BASE_URL}/api/drive/list", params={
            "workspace_id": self.workspace_id,
            "path": "/"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "files" in data
        assert "path" in data
        assert data["path"] == "/"
        # Should contain our created items
        file_ids = [f["file_id"] for f in data["files"]]
        if TestDrive.created_file_id:
            assert TestDrive.created_file_id in file_ids, "Uploaded file not in list"
        print(f"PASS: GET /api/drive/list - found {len(data['files'])} files")
    
    def test_get_storage_usage(self, auth_session):
        """GET /api/drive/storage-usage - returns used/limit/pct"""
        resp = auth_session.get(f"{BASE_URL}/api/drive/storage-usage", params={
            "workspace_id": self.workspace_id
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        # Verify all expected fields
        assert "used_bytes" in data
        assert "used_mb" in data
        assert "limit_bytes" in data
        assert "limit_gb" in data
        assert "usage_pct" in data
        assert "file_count" in data
        # Verify types
        assert isinstance(data["used_bytes"], int)
        assert isinstance(data["usage_pct"], (int, float))
        print(f"PASS: GET /api/drive/storage-usage - {data['used_mb']}MB / {data['limit_gb']}GB ({data['usage_pct']}%)")
    
    def test_share_file(self, auth_session):
        """POST /api/drive/file/{id}/share - creates share link"""
        if not TestDrive.created_file_id:
            pytest.skip("No file created to share")
        resp = auth_session.post(f"{BASE_URL}/api/drive/file/{TestDrive.created_file_id}/share", json={
            "permissions": "view",
            "expires_hours": 24
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "share_url" in data
        assert "token" in data
        assert "expires_at" in data
        assert data["share_url"].startswith("/api/drive/shared/")
        print(f"PASS: POST /api/drive/file/{TestDrive.created_file_id}/share - created share link")


# =============================================================================
# DEEP RESEARCH (#4)
# =============================================================================

class TestResearch:
    """Deep Research Agent"""
    
    workspace_id = "ws_bd1750012bfd"
    created_session_id = None
    
    def test_start_research(self, auth_session):
        """POST /api/research/start - starts research session"""
        resp = auth_session.post(f"{BASE_URL}/api/research/start", json={
            "workspace_id": self.workspace_id,
            "query": "What are the best practices for API testing?",
            "depth": "quick",
            "model": "claude",
            "output_format": "report",
            "include_citations": True
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "session_id" in data
        assert data["status"] == "running"
        assert "sub_queries" in data
        assert len(data["sub_queries"]) >= 3, "Quick depth should have at least 3 sub-queries"
        assert "credits_cost" in data
        TestResearch.created_session_id = data["session_id"]
        print(f"PASS: POST /api/research/start - started {data['session_id']} with {len(data['sub_queries'])} sub-queries")
    
    def test_get_research_report(self, auth_session):
        """GET /api/research/{id}/report - returns structured report"""
        if not TestResearch.created_session_id:
            pytest.skip("No research session created")
        resp = auth_session.get(f"{BASE_URL}/api/research/{TestResearch.created_session_id}/report")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        # Verify report structure
        assert "report_id" in data
        assert "session_id" in data
        assert "structure" in data
        assert "title" in data["structure"]
        assert "sections" in data["structure"]
        # Verify expected sections
        section_titles = [s["title"] for s in data["structure"]["sections"]]
        assert "Executive Summary" in section_titles or any("summary" in t.lower() for t in section_titles)
        # Verify confidence scores
        assert "confidence_scores" in data
        print(f"PASS: GET /api/research/{TestResearch.created_session_id}/report - got report with {len(data['structure']['sections'])} sections")


# =============================================================================
# FACT CHECKING (#6)
# =============================================================================

class TestFactCheck:
    """AI Fact Checking"""
    
    workspace_id = "ws_bd1750012bfd"
    
    def test_verify_claim(self, auth_session):
        """POST /api/fact-check/verify - verifies claim with verdict"""
        resp = auth_session.post(f"{BASE_URL}/api/fact-check/verify", json={
            "claim": "The Earth orbits the Sun in approximately 365 days",
            "workspace_id": self.workspace_id
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "check_id" in data
        assert "claim" in data
        assert "verdict" in data
        assert data["verdict"] is not None, "Verdict should be returned"
        assert "confidence_score" in data
        assert "status" in data
        assert data["status"] == "verified"
        # Verify evidence fields
        assert "supporting_evidence" in data
        assert "contradicting_evidence" in data
        print(f"PASS: POST /api/fact-check/verify - verdict: {data['verdict']} (confidence: {data['confidence_score']})")
    
    def test_verify_claim_empty_rejected(self, auth_session):
        """POST /api/fact-check/verify - rejects empty claim"""
        resp = auth_session.post(f"{BASE_URL}/api/fact-check/verify", json={
            "claim": "",
            "workspace_id": self.workspace_id
        })
        assert resp.status_code == 400, f"Expected 400 for empty claim, got {resp.status_code}"
        print("PASS: POST /api/fact-check/verify - rejects empty claim")


# =============================================================================
# PRICING (#5)
# =============================================================================

class TestPricing:
    """Pricing Engine - Plans & Feature Gates"""
    
    def test_get_plans_v2(self, auth_session):
        """GET /api/billing/plans-v2 - returns 5 plans with features"""
        resp = auth_session.get(f"{BASE_URL}/api/billing/plans-v2")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "plans" in data
        plans = data["plans"]
        assert len(plans) == 5, f"Expected 5 plans, got {len(plans)}"
        # Verify plan names
        plan_names = [p["plan"] for p in plans]
        expected_plans = ["free", "starter", "pro", "team", "enterprise"]
        for exp in expected_plans:
            assert exp in plan_names, f"Missing plan: {exp}"
        # Verify each plan has required fields
        for plan in plans:
            assert "price" in plan
            assert "price_label" in plan
            assert "credits" in plan
            assert "features" in plan
            # Verify features structure
            features = plan["features"]
            assert "ai_messages" in features
            assert "workspaces" in features
            assert "storage_gb" in features
        print(f"PASS: GET /api/billing/plans-v2 - returns {len(plans)} plans")
    
    def test_check_feature_gate(self, auth_session):
        """POST /api/billing/check-feature - checks feature gate"""
        resp = auth_session.post(f"{BASE_URL}/api/billing/check-feature", json={
            "feature": "ai_messages"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "allowed" in data
        assert "feature" in data
        assert data["feature"] == "ai_messages"
        print(f"PASS: POST /api/billing/check-feature - allowed: {data['allowed']}")
    
    def test_check_sso_feature(self, auth_session):
        """POST /api/billing/check-feature - checks SSO (boolean feature)"""
        resp = auth_session.post(f"{BASE_URL}/api/billing/check-feature", json={
            "feature": "sso"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "allowed" in data
        assert "feature" in data
        print(f"PASS: POST /api/billing/check-feature (sso) - allowed: {data['allowed']}")


# =============================================================================
# CUSTOM AGENT BUILDER (#7)
# =============================================================================

class TestCustomAgents:
    """Enhanced Agent Builder"""
    
    created_agent_id = None
    
    def test_create_custom_agent(self, auth_session):
        """POST /api/agents/custom - creates custom agent with tools"""
        resp = auth_session.post(f"{BASE_URL}/api/agents/custom", json={
            "name": "TEST_Research Agent",
            "avatar_emoji": "🔬",
            "model": "claude",
            "system_prompt": "You are a research assistant",
            "tools_enabled": ["web_search", "file_read", "code_execute"],
            "knowledge_scope": ["research", "analysis"],
            "temperature": 0.7,
            "max_tokens": 4096,
            "trigger_keywords": ["research", "analyze"],
            "auto_respond": False,
            "response_style": "detailed",
            "is_public": False
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "agent_id" in data
        assert data["name"] == "TEST_Research Agent"
        assert data["avatar_emoji"] == "🔬"
        assert "tools_enabled" in data
        assert "web_search" in data["tools_enabled"]
        assert "file_read" in data["tools_enabled"]
        assert "code_execute" in data["tools_enabled"]
        TestCustomAgents.created_agent_id = data["agent_id"]
        print(f"PASS: POST /api/agents/custom - created {data['agent_id']} with {len(data['tools_enabled'])} tools")
    
    def test_list_custom_agents(self, auth_session):
        """GET /api/agents/custom - lists agents"""
        resp = auth_session.get(f"{BASE_URL}/api/agents/custom")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "agents" in data
        if TestCustomAgents.created_agent_id:
            agent_ids = [a["agent_id"] for a in data["agents"]]
            assert TestCustomAgents.created_agent_id in agent_ids, "Created agent not in list"
        print(f"PASS: GET /api/agents/custom - found {len(data['agents'])} agents")


# =============================================================================
# WORKFLOW TEMPLATES (#13)
# =============================================================================

class TestWorkflowTemplates:
    """Extended Workflow Templates"""
    
    def test_get_extended_templates(self, auth_session):
        """GET /api/workflow-templates/extended - returns 8 templates"""
        resp = auth_session.get(f"{BASE_URL}/api/workflow-templates/extended")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "templates" in data
        templates = data["templates"]
        assert len(templates) == 8, f"Expected 8 templates, got {len(templates)}"
        # Verify expected templates
        template_ids = [t["template_id"] for t in templates]
        expected = ["wst_competitive_analysis", "wst_pitch_deck_creator", "wst_blog_generator",
                   "wst_meeting_notes", "wst_market_research", "wst_social_media",
                   "wst_feedback_analyzer", "wst_code_review_enhanced"]
        for exp in expected:
            assert exp in template_ids, f"Missing template: {exp}"
        # Verify each template has nodes
        for tpl in templates:
            assert "nodes" in tpl
            assert len(tpl["nodes"]) >= 3, f"Template {tpl['template_id']} should have at least 3 nodes"
        print(f"PASS: GET /api/workflow-templates/extended - returns {len(templates)} templates")


# =============================================================================
# REAL-TIME PRESENCE (#8)
# =============================================================================

class TestPresence:
    """Real-Time Collaboration Presence"""
    
    workspace_id = "ws_bd1750012bfd"
    
    def test_presence_heartbeat(self, auth_session):
        """POST /api/presence/heartbeat - registers presence"""
        resp = auth_session.post(f"{BASE_URL}/api/presence/heartbeat", json={
            "workspace_id": self.workspace_id,
            "current_tab": "chat"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert data.get("status") == "ok"
        print("PASS: POST /api/presence/heartbeat - registered presence")
    
    def test_get_workspace_presence(self, auth_session):
        """GET /api/workspaces/{ws}/presence - returns online users"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/{self.workspace_id}/presence")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "online_users" in data
        assert "count" in data
        assert isinstance(data["online_users"], list)
        # Should have at least 1 user (our test user)
        assert data["count"] >= 1, "Expected at least 1 online user after heartbeat"
        print(f"PASS: GET /api/workspaces/{self.workspace_id}/presence - {data['count']} online users")


# =============================================================================
# EXPORT (#9)
# =============================================================================

class TestExport:
    """Export as Deliverables"""
    
    workspace_id = "ws_bd1750012bfd"
    channel_id = "ch_9988b6543849"
    
    def test_export_chat_to_document(self, auth_session):
        """POST /api/export/chat-to-document - exports chat as document"""
        resp = auth_session.post(f"{BASE_URL}/api/export/chat-to-document", json={
            "workspace_id": self.workspace_id,
            "channel_id": self.channel_id,
            "title": "TEST_Chat Export Document"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "content_id" in data
        assert data["format"] == "document"
        print(f"PASS: POST /api/export/chat-to-document - created {data['content_id']}")
    
    def test_export_chat_to_report(self, auth_session):
        """POST /api/export/chat-to-report - exports chat as report"""
        resp = auth_session.post(f"{BASE_URL}/api/export/chat-to-report", json={
            "workspace_id": self.workspace_id,
            "channel_id": self.channel_id,
            "title": "TEST_Collaboration Report"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "content_id" in data
        assert data["format"] == "report"
        print(f"PASS: POST /api/export/chat-to-report - created {data['content_id']}")


# =============================================================================
# MULTILINGUAL (#11)
# =============================================================================

class TestMultilingual:
    """Multilingual Support"""
    
    def test_get_languages(self, auth_session):
        """GET /api/i18n/languages - returns 10 languages"""
        resp = auth_session.get(f"{BASE_URL}/api/i18n/languages")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "languages" in data
        languages = data["languages"]
        assert len(languages) == 10, f"Expected 10 languages, got {len(languages)}"
        # Verify expected language codes
        codes = [l["code"] for l in languages]
        expected_codes = ["en", "es", "fr", "de", "pt", "ja", "zh", "ko", "ar", "hi"]
        for code in expected_codes:
            assert code in codes, f"Missing language: {code}"
        # Verify RTL support for Arabic
        ar = next((l for l in languages if l["code"] == "ar"), None)
        assert ar is not None
        assert ar.get("rtl") == True, "Arabic should have rtl=True"
        print(f"PASS: GET /api/i18n/languages - returns {len(languages)} languages")


# =============================================================================
# AI ROLES (#12)
# =============================================================================

class TestAIRoles:
    """AI Team Roles"""
    
    workspace_id = "ws_bd1750012bfd"
    created_role_id = None
    
    def test_assign_ai_role(self, auth_session):
        """POST /api/workspaces/{ws}/ai-roles - assigns AI role"""
        resp = auth_session.post(f"{BASE_URL}/api/workspaces/{self.workspace_id}/ai-roles", json={
            "role": "researcher",
            "agent_model": "claude",
            "custom_prompt": "Focus on technical research"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "role_id" in data
        assert data["role_key"] == "researcher"
        assert data["agent_model"] == "claude"
        TestAIRoles.created_role_id = data["role_id"]
        print(f"PASS: POST /api/workspaces/{self.workspace_id}/ai-roles - assigned role {data['role_id']}")
    
    def test_list_workspace_roles(self, auth_session):
        """GET /api/workspaces/{ws}/ai-roles - lists roles and available options"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/{self.workspace_id}/ai-roles")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "roles" in data
        assert "available_roles" in data
        # Should have 8 available roles
        assert len(data["available_roles"]) == 8, f"Expected 8 available roles, got {len(data['available_roles'])}"
        role_keys = [r["key"] for r in data["available_roles"]]
        expected_roles = ["strategist", "coder", "researcher", "critic", "writer", "designer", "analyst", "qa"]
        for exp in expected_roles:
            assert exp in role_keys, f"Missing available role: {exp}"
        print(f"PASS: GET /api/workspaces/{self.workspace_id}/ai-roles - {len(data['available_roles'])} available roles")


# =============================================================================
# VOICE NOTES (#14)
# =============================================================================

class TestVoiceNotes:
    """Voice Notes"""
    
    workspace_id = "ws_bd1750012bfd"
    
    def test_create_voice_note(self, auth_session):
        """POST /api/voice-notes - creates voice note"""
        # Create a fake audio file (just for testing the endpoint)
        audio_content = b"RIFF" + b"\x00" * 100 + b"WAVEfmt " + b"\x00" * 100  # Fake WAV header
        files = {
            "audio": ("TEST_voice_note.webm", io.BytesIO(audio_content), "audio/webm")
        }
        data = {
            "workspace_id": self.workspace_id,
            "title": "TEST_Voice Note"
        }
        # Note: for multipart, remove Content-Type header
        headers = {k: v for k, v in auth_session.headers.items() if k.lower() != "content-type"}
        resp = requests.post(
            f"{BASE_URL}/api/voice-notes",
            files=files,
            data=data,
            cookies=auth_session.cookies,
            headers=headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "note_id" in data
        assert data["title"] == "TEST_Voice Note"
        assert data["mime_type"] == "audio/webm"
        print(f"PASS: POST /api/voice-notes - created {data['note_id']}")


# =============================================================================
# PUSH NOTIFICATIONS (#10)
# =============================================================================

class TestPushNotifications:
    """Mobile Push Notifications"""
    
    def test_register_push_token(self, auth_session):
        """POST /api/notifications/push-token - registers push token"""
        resp = auth_session.post(f"{BASE_URL}/api/notifications/push-token", json={
            "device_token": f"TEST_token_{uuid.uuid4().hex[:16]}",
            "device_type": "ios"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert data.get("message") == "Push token registered"
        print("PASS: POST /api/notifications/push-token - registered token")


# =============================================================================
# AUTH / UNAUTHORIZED TESTS
# =============================================================================

class TestUnauthorized:
    """Test endpoints require authentication"""
    
    def test_content_templates_unauthorized(self):
        """GET /api/content/templates - requires auth"""
        resp = requests.get(f"{BASE_URL}/api/content/templates")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: GET /api/content/templates - returns 401 without auth")
    
    def test_drive_list_unauthorized(self):
        """GET /api/drive/list - requires auth"""
        resp = requests.get(f"{BASE_URL}/api/drive/list")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: GET /api/drive/list - returns 401 without auth")
    
    def test_research_start_unauthorized(self):
        """POST /api/research/start - requires auth"""
        resp = requests.post(f"{BASE_URL}/api/research/start", json={
            "query": "test query for auth check",  # Min 5 chars required
            "workspace_id": "ws_test"
        })
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: POST /api/research/start - returns 401 without auth")
    
    def test_billing_plans_unauthorized(self):
        """GET /api/billing/plans-v2 - requires auth"""
        resp = requests.get(f"{BASE_URL}/api/billing/plans-v2")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: GET /api/billing/plans-v2 - returns 401 without auth")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
