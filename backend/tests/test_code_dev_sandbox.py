"""
Test Suite for Code Execution Sandbox, GitHub Integration, Dev Templates, Project-Code Linking, Console, VS Code API
Iteration 41 - Testing code sandbox endpoints and related functionality

Endpoints tested:
- POST /api/code/execute - Code execution sandbox (Python, JavaScript, Bash, error handling)
- GET /api/code/runtimes - List supported languages
- GET /api/code/executions - Execution history
- GET /api/ai-tools - AI tools including execute_code
- POST /api/github/connect - GitHub OAuth (501 without keys)
- GET /api/github/connections - List connections
- POST /api/github/webhook - Public webhook endpoint
- POST /api/workflows/{id}/trigger/github - Create GitHub event trigger
- GET /api/workflow-templates/dev - Dev workflow templates
- POST /api/tasks/{id}/link-artifact - Link code artifact to task
- GET /api/tasks/{id}/linked-artifacts - Get linked artifacts
- DELETE /api/tasks/{id}/link-artifact/{art_id} - Unlink artifact
- GET /api/workspaces/{ws}/console/history - Console execution history
- POST /api/external/review - VS Code extension API
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testmention@test.com"
TEST_PASSWORD = "Test1234!"
TEST_WORKSPACE = "ws_bd1750012bfd"
TEST_TASK = "ptask_d0ae46fddc58"
LINKED_ARTIFACT = "art_3e289bcd225b"


@pytest.fixture(scope="module")
def auth_session():
    """Get authenticated session with cookies"""
    session = requests.Session()
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if resp.status_code == 200:
        return session
    pytest.skip(f"Authentication failed: {resp.status_code} - {resp.text[:200]}")


class TestCodeExecutionSandbox:
    """Test code execution sandbox endpoints"""

    def test_execute_python_code(self, auth_session):
        """POST /api/code/execute - Execute Python code and verify stdout/exit_code/success"""
        resp = auth_session.post(f"{BASE_URL}/api/code/execute", json={
            "code": "print('Hello from Python!')\nprint(2 + 3)",
            "language": "python",
            "timeout_ms": 5000
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Verify response structure
        assert "exec_id" in data
        assert "stdout" in data
        assert "exit_code" in data
        assert "success" in data
        
        # Verify execution success
        assert data["success"] == True
        assert data["exit_code"] == 0
        assert "Hello from Python!" in data["stdout"]
        assert "5" in data["stdout"]

    def test_execute_javascript_code(self, auth_session):
        """POST /api/code/execute - Execute Node.js code"""
        resp = auth_session.post(f"{BASE_URL}/api/code/execute", json={
            "code": "console.log('Hello from JavaScript!');\nconsole.log(10 * 5);",
            "language": "javascript",
            "timeout_ms": 5000
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert data["success"] == True
        assert data["exit_code"] == 0
        assert "Hello from JavaScript!" in data["stdout"]
        assert "50" in data["stdout"]

    def test_execute_bash_code(self, auth_session):
        """POST /api/code/execute - Execute Bash command"""
        resp = auth_session.post(f"{BASE_URL}/api/code/execute", json={
            "code": "echo 'Hello from Bash!'; echo 'Current directory:'; pwd",
            "language": "bash",
            "timeout_ms": 5000
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert data["success"] == True
        assert data["exit_code"] == 0
        assert "Hello from Bash!" in data["stdout"]

    def test_execute_code_with_error(self, auth_session):
        """POST /api/code/execute - Code with error returns non-zero exit code + stderr"""
        resp = auth_session.post(f"{BASE_URL}/api/code/execute", json={
            "code": "import sys; print('Before error'); sys.exit(1)",
            "language": "python",
            "timeout_ms": 5000
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert data["success"] == False
        assert data["exit_code"] != 0
        assert "Before error" in data["stdout"]

    def test_execute_code_syntax_error(self, auth_session):
        """POST /api/code/execute - Syntax error returns stderr"""
        resp = auth_session.post(f"{BASE_URL}/api/code/execute", json={
            "code": "print('unclosed string",
            "language": "python",
            "timeout_ms": 5000
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert data["success"] == False
        assert data["exit_code"] != 0
        assert len(data.get("stderr", "")) > 0, "Expected stderr for syntax error"

    def test_execute_unsupported_language(self, auth_session):
        """POST /api/code/execute - Unsupported language returns helpful error"""
        resp = auth_session.post(f"{BASE_URL}/api/code/execute", json={
            "code": "fn main() { println!(\"Hello\"); }",
            "language": "rust",
            "timeout_ms": 5000
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Rust is in SUPPORTED_LANGUAGES but requires external runtime
        assert "stderr" in data
        # Should indicate that local execution only supports python/javascript/bash
        assert "requires external runtime" in data.get("stderr", "") or data["exit_code"] == -1

    def test_execute_code_no_auth(self):
        """POST /api/code/execute - Without auth returns 401/403"""
        resp = requests.post(f"{BASE_URL}/api/code/execute", json={
            "code": "print('test')",
            "language": "python"
        })
        assert resp.status_code in [401, 403], f"Expected 401/403 without auth, got {resp.status_code}"


class TestCodeRuntimes:
    """Test code runtimes listing"""

    def test_list_runtimes(self, auth_session):
        """GET /api/code/runtimes - Returns 16 supported languages"""
        resp = auth_session.get(f"{BASE_URL}/api/code/runtimes")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert "languages" in data
        languages = data["languages"]
        assert len(languages) == 16, f"Expected 16 languages, got {len(languages)}"
        
        # Verify expected languages are present
        expected_langs = ["python", "javascript", "typescript", "go", "rust", "c", "cpp", 
                         "java", "ruby", "php", "bash", "sql", "r", "swift", "kotlin", "csharp"]
        for lang in expected_langs:
            assert lang in languages, f"Missing language: {lang}"

    def test_list_runtimes_no_auth(self):
        """GET /api/code/runtimes - Requires authentication"""
        resp = requests.get(f"{BASE_URL}/api/code/runtimes")
        assert resp.status_code in [401, 403], f"Expected 401/403 without auth, got {resp.status_code}"


class TestCodeExecutions:
    """Test execution history"""

    def test_list_executions(self, auth_session):
        """GET /api/code/executions - Lists recent execution history"""
        resp = auth_session.get(f"{BASE_URL}/api/code/executions")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert "executions" in data
        executions = data["executions"]
        assert isinstance(executions, list)
        
        # If we have executions, verify structure
        if len(executions) > 0:
            exec_item = executions[0]
            assert "exec_id" in exec_item
            assert "language" in exec_item
            assert "success" in exec_item


class TestAIToolsWithExecuteCode:
    """Test AI tools endpoint includes execute_code"""

    def test_get_ai_tools(self):
        """GET /api/ai-tools - Returns 10 tools including execute_code"""
        resp = requests.get(f"{BASE_URL}/api/ai-tools")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert "tools" in data
        tools = data["tools"]
        assert len(tools) == 10, f"Expected 10 tools, got {len(tools)}"
        
        # Verify execute_code tool is present
        tool_names = [t["name"] for t in tools]
        assert "execute_code" in tool_names, "execute_code tool not found"
        
        # Verify execute_code tool structure
        execute_code_tool = next((t for t in tools if t["name"] == "execute_code"), None)
        assert execute_code_tool is not None
        assert "description" in execute_code_tool
        assert "params" in execute_code_tool
        assert "code" in execute_code_tool["params"]
        assert "language" in execute_code_tool["params"]


class TestGitHubIntegration:
    """Test GitHub integration endpoints"""

    def test_github_connect_no_keys(self, auth_session):
        """POST /api/github/connect - Returns 501 when GITHUB_CLIENT_ID not configured"""
        resp = auth_session.post(f"{BASE_URL}/api/github/connect", json={
            "scope": "user"
        })
        # Without GITHUB_CLIENT_ID, should return 501
        assert resp.status_code == 501, f"Expected 501, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "detail" in data or "message" in data

    def test_github_connections_list(self, auth_session):
        """GET /api/github/connections - Lists connections"""
        resp = auth_session.get(f"{BASE_URL}/api/github/connections")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert "connections" in data
        assert isinstance(data["connections"], list)

    def test_github_webhook_public(self):
        """POST /api/github/webhook - Public endpoint for GitHub events"""
        # This is a public endpoint - no auth required
        resp = requests.post(f"{BASE_URL}/api/github/webhook", 
            headers={"X-GitHub-Event": "push", "Content-Type": "application/json"},
            json={
                "repository": {"full_name": "test/repo"},
                "ref": "refs/heads/main"
            })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert "processed" in data
        assert data["processed"] == True
        assert "event" in data
        assert data["event"] == "push"


class TestGitHubTriggers:
    """Test GitHub event triggers for workflows"""

    def test_create_github_trigger(self, auth_session):
        """POST /api/workflows/{id}/trigger/github - Creates GitHub event trigger"""
        test_workflow_id = "wf_test_github_trigger"
        resp = auth_session.post(f"{BASE_URL}/api/workflows/{test_workflow_id}/trigger/github", json={
            "repo": "test/example-repo",
            "events": ["push", "pull_request"]
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert "trigger_id" in data
        assert "webhook_url" in data
        assert "/api/github/webhook" in data["webhook_url"]
        assert "instructions" in data


class TestDevWorkflowTemplates:
    """Test dev workflow templates endpoint"""

    def test_get_dev_templates(self, auth_session):
        """GET /api/workflow-templates/dev - Returns 3 dev templates"""
        resp = auth_session.get(f"{BASE_URL}/api/workflow-templates/dev")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert "templates" in data
        templates = data["templates"]
        assert len(templates) == 3, f"Expected 3 templates, got {len(templates)}"
        
        # Verify template IDs
        template_ids = [t["template_id"] for t in templates]
        assert "wst_code_review_pipeline" in template_ids, "Code Review Pipeline template missing"
        assert "wst_feature_builder" in template_ids, "Feature Builder template missing"
        assert "wst_bug_diagnosis" in template_ids, "Bug Diagnosis template missing"
        
        # Verify Code Review Pipeline structure (6 nodes)
        code_review = next((t for t in templates if t["template_id"] == "wst_code_review_pipeline"), None)
        assert code_review is not None
        assert "nodes" in code_review
        assert len(code_review["nodes"]) == 6, f"Expected 6 nodes in Code Review, got {len(code_review['nodes'])}"
        
        # Verify Feature Builder structure (6 nodes)
        feature_builder = next((t for t in templates if t["template_id"] == "wst_feature_builder"), None)
        assert feature_builder is not None
        assert len(feature_builder["nodes"]) == 6
        
        # Verify Bug Diagnosis structure (6 nodes)
        bug_diagnosis = next((t for t in templates if t["template_id"] == "wst_bug_diagnosis"), None)
        assert bug_diagnosis is not None
        assert len(bug_diagnosis["nodes"]) == 6


class TestProjectCodeLinking:
    """Test project-code linking functionality"""

    def test_link_artifact_to_task(self, auth_session):
        """POST /api/tasks/{id}/link-artifact - Links code artifact to task"""
        test_artifact_id = f"art_TEST_{int(time.time())}"
        resp = auth_session.post(f"{BASE_URL}/api/tasks/{TEST_TASK}/link-artifact", json={
            "artifact_id": test_artifact_id
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert "task_id" in data
        assert data["task_id"] == TEST_TASK
        assert "linked" in data
        assert data["linked"] == test_artifact_id

    def test_get_linked_artifacts(self, auth_session):
        """GET /api/tasks/{id}/linked-artifacts - Returns linked artifacts"""
        resp = auth_session.get(f"{BASE_URL}/api/tasks/{TEST_TASK}/linked-artifacts")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert "artifacts" in data
        assert isinstance(data["artifacts"], list)

    def test_unlink_artifact_from_task(self, auth_session):
        """DELETE /api/tasks/{id}/link-artifact/{art_id} - Unlinks artifact"""
        # First link a test artifact
        test_artifact_id = f"art_TEST_unlink_{int(time.time())}"
        link_resp = auth_session.post(f"{BASE_URL}/api/tasks/{TEST_TASK}/link-artifact", json={
            "artifact_id": test_artifact_id
        })
        assert link_resp.status_code == 200
        
        # Now unlink it
        resp = auth_session.delete(f"{BASE_URL}/api/tasks/{TEST_TASK}/link-artifact/{test_artifact_id}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "message" in data
        assert "Unlinked" in data["message"]

    def test_link_artifact_missing_id(self, auth_session):
        """POST /api/tasks/{id}/link-artifact - Without artifact_id returns 400"""
        resp = auth_session.post(f"{BASE_URL}/api/tasks/{TEST_TASK}/link-artifact", json={})
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"


class TestConsoleHistory:
    """Test workspace console history"""

    def test_get_console_history(self, auth_session):
        """GET /api/workspaces/{ws}/console/history - Returns execution history"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/console/history")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert "executions" in data
        assert isinstance(data["executions"], list)

    def test_get_console_history_with_limit(self, auth_session):
        """GET /api/workspaces/{ws}/console/history?limit=5 - Respects limit"""
        resp = auth_session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE}/console/history?limit=5")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert "executions" in data
        assert len(data["executions"]) <= 5


class TestVSCodeExtensionAPI:
    """Test VS Code extension API endpoint"""

    def test_external_review_submit(self, auth_session):
        """POST /api/external/review - VS Code extension API for code review submission"""
        resp = auth_session.post(f"{BASE_URL}/api/external/review", json={
            "code": "def hello():\n    return 'Hello World!'",
            "language": "python",
            "workspace_id": TEST_WORKSPACE,
            "models": ["claude", "chatgpt"]
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert "artifact_id" in data
        assert "review_url" in data
        assert "message" in data
        assert TEST_WORKSPACE in data["review_url"]

    def test_external_review_missing_code(self, auth_session):
        """POST /api/external/review - Without code returns 400"""
        resp = auth_session.post(f"{BASE_URL}/api/external/review", json={
            "language": "python"
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"

    def test_external_review_no_auth(self):
        """POST /api/external/review - Without auth returns 401/403"""
        resp = requests.post(f"{BASE_URL}/api/external/review", json={
            "code": "print('test')",
            "language": "python"
        })
        assert resp.status_code in [401, 403], f"Expected 401/403 without auth, got {resp.status_code}"


class TestCodeExecutionIntegration:
    """Integration tests for code execution flow"""

    def test_execute_and_verify_history(self, auth_session):
        """Execute code and verify it appears in history"""
        unique_marker = f"TEST_MARKER_{int(time.time())}"
        
        # Execute code with unique marker
        exec_resp = auth_session.post(f"{BASE_URL}/api/code/execute", json={
            "code": f"print('{unique_marker}')",
            "language": "python"
        })
        assert exec_resp.status_code == 200
        exec_data = exec_resp.json()
        exec_id = exec_data["exec_id"]
        
        # Check execution history
        hist_resp = auth_session.get(f"{BASE_URL}/api/code/executions?limit=10")
        assert hist_resp.status_code == 200
        hist_data = hist_resp.json()
        
        # Find our execution
        found = any(e.get("exec_id") == exec_id for e in hist_data.get("executions", []))
        assert found, f"Execution {exec_id} not found in history"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
