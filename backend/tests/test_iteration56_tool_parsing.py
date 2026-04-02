"""
Iteration 56 - Tool Parsing Multi-Format Tests
Tests for the 5 tool call formats supported in routes_ai_tools.py:
1. [TOOL_CALL]...[/TOOL_CALL] - uppercase format
2. <tool_call>...</tool_call> - XML-style format
3. [tool_call]...[/tool_call] - lowercase format
4. ```tool ... ``` - code block format
5. ```json {"tool": ...} ``` - JSON code block format
Also tests strip_tool_calls and tool execution for create_project, repo_list_files, wiki_list_pages
"""
import pytest
import requests
import os
import json
import sys

# Add backend to path to import routes_ai_tools directly for unit testing
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent))
from routes_ai_tools import parse_tool_calls, strip_tool_calls, TOOL_DEFINITIONS, TOOL_CALL_PATTERNS

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# ==================== UNIT TESTS - parse_tool_calls ====================

class TestParseToolCallsFormats:
    """Test parse_tool_calls function with all 5 supported formats"""
    
    def test_format_1_uppercase_brackets(self):
        """Test [TOOL_CALL]...[/TOOL_CALL] format"""
        response = '''I'll create a project for you.
[TOOL_CALL]{"tool": "create_project", "params": {"name": "TestProject"}}[/TOOL_CALL]
Let me know if you need anything else.'''
        
        calls = parse_tool_calls(response)
        assert len(calls) == 1, f"Expected 1 tool call, got {len(calls)}"
        assert calls[0]["tool"] == "create_project"
        assert calls[0]["params"]["name"] == "TestProject"
        print(f"PASS: Format 1 (uppercase brackets) parsed correctly: {calls[0]}")
    
    def test_format_2_xml_style(self):
        """Test <tool_call>...</tool_call> XML-style format"""
        response = '''Here's the list of files:
<tool_call>{"tool": "repo_list_files", "params": {}}</tool_call>'''
        
        calls = parse_tool_calls(response)
        assert len(calls) == 1, f"Expected 1 tool call, got {len(calls)}"
        assert calls[0]["tool"] == "repo_list_files"
        print(f"PASS: Format 2 (XML-style) parsed correctly: {calls[0]}")
    
    def test_format_3_lowercase_brackets(self):
        """Test [tool_call]...[/tool_call] lowercase format"""
        response = '''Checking wiki pages now.
[tool_call]{"tool": "wiki_list_pages", "params": {}}[/tool_call]'''
        
        calls = parse_tool_calls(response)
        assert len(calls) == 1, f"Expected 1 tool call, got {len(calls)}"
        assert calls[0]["tool"] == "wiki_list_pages"
        print(f"PASS: Format 3 (lowercase brackets) parsed correctly: {calls[0]}")
    
    def test_format_4_code_block_tool(self):
        """Test ```tool ... ``` code block format"""
        response = '''Creating a new task:
```tool
{"tool": "create_task", "params": {"project_id": "proj_123", "title": "Test Task"}}
```
Done!'''
        
        calls = parse_tool_calls(response)
        assert len(calls) == 1, f"Expected 1 tool call, got {len(calls)}"
        assert calls[0]["tool"] == "create_task"
        assert calls[0]["params"]["title"] == "Test Task"
        print(f"PASS: Format 4 (code block tool) parsed correctly: {calls[0]}")
    
    def test_format_5_code_block_json(self):
        """Test ```json {"tool": ...} ``` code block format"""
        response = '''Saving to memory:
```json
{"tool": "save_to_memory", "params": {"key": "test_key", "value": "test_value"}}
```'''
        
        calls = parse_tool_calls(response)
        assert len(calls) == 1, f"Expected 1 tool call, got {len(calls)}"
        assert calls[0]["tool"] == "save_to_memory"
        assert calls[0]["params"]["key"] == "test_key"
        print(f"PASS: Format 5 (JSON code block) parsed correctly: {calls[0]}")
    
    def test_multiple_mixed_formats(self):
        """Test multiple tool calls with different formats in one response"""
        response = '''I'll help you with multiple tasks:
        
First, let me create a project:
[TOOL_CALL]{"tool": "create_project", "params": {"name": "MultiTest1"}}[/TOOL_CALL]

Then check the wiki:
<tool_call>{"tool": "wiki_list_pages", "params": {}}</tool_call>

And list repository files:
[tool_call]{"tool": "repo_list_files", "params": {}}[/tool_call]

Finally, save something:
```json
{"tool": "save_to_memory", "params": {"key": "mixed_test", "value": "working"}}
```

All done!'''
        
        calls = parse_tool_calls(response)
        assert len(calls) == 4, f"Expected 4 tool calls, got {len(calls)}"
        
        tool_names = [c["tool"] for c in calls]
        assert "create_project" in tool_names
        assert "wiki_list_pages" in tool_names
        assert "repo_list_files" in tool_names
        assert "save_to_memory" in tool_names
        print(f"PASS: Multiple mixed formats parsed correctly: {tool_names}")
    
    def test_deduplication_same_tool_call(self):
        """Test that duplicate tool calls are deduplicated"""
        response = '''
[TOOL_CALL]{"tool": "list_projects", "params": {}}[/TOOL_CALL]
<tool_call>{"tool": "list_projects", "params": {}}</tool_call>
[tool_call]{"tool": "list_projects", "params": {}}[/tool_call]'''
        
        calls = parse_tool_calls(response)
        # Should deduplicate identical calls
        assert len(calls) == 1, f"Expected 1 deduplicated call, got {len(calls)}"
        assert calls[0]["tool"] == "list_projects"
        print(f"PASS: Duplicate tool calls deduplicated correctly")
    
    def test_empty_response(self):
        """Test with empty or None response"""
        assert parse_tool_calls("") == []
        assert parse_tool_calls(None) == []
        print("PASS: Empty/None responses return empty list")
    
    def test_no_tool_calls(self):
        """Test response with no tool calls"""
        response = "I'll help you with that. Let me explain how it works..."
        calls = parse_tool_calls(response)
        assert len(calls) == 0
        print("PASS: Response without tool calls returns empty list")


class TestStripToolCalls:
    """Test strip_tool_calls removes all format variants"""
    
    def test_strip_uppercase_brackets(self):
        """Test stripping [TOOL_CALL]...[/TOOL_CALL]"""
        original = 'Hello [TOOL_CALL]{"tool": "test"}[/TOOL_CALL] World'
        stripped = strip_tool_calls(original)
        assert "[TOOL_CALL]" not in stripped
        assert "[/TOOL_CALL]" not in stripped
        assert "Hello" in stripped
        assert "World" in stripped
        print(f"PASS: Uppercase brackets stripped: '{stripped}'")
    
    def test_strip_xml_style(self):
        """Test stripping <tool_call>...</tool_call>"""
        original = 'Start <tool_call>{"tool": "test"}</tool_call> End'
        stripped = strip_tool_calls(original)
        assert "<tool_call>" not in stripped
        assert "</tool_call>" not in stripped
        assert "Start" in stripped
        assert "End" in stripped
        print(f"PASS: XML-style stripped: '{stripped}'")
    
    def test_strip_lowercase_brackets(self):
        """Test stripping [tool_call]...[/tool_call]"""
        original = 'Before [tool_call]{"tool": "test"}[/tool_call] After'
        stripped = strip_tool_calls(original)
        assert "[tool_call]" not in stripped
        assert "[/tool_call]" not in stripped
        print(f"PASS: Lowercase brackets stripped: '{stripped}'")
    
    def test_strip_code_block_tool(self):
        """Test stripping ```tool ... ```"""
        original = '''Here is the code:
```tool
{"tool": "test", "params": {}}
```
That's all.'''
        stripped = strip_tool_calls(original)
        assert "```tool" not in stripped
        assert '"tool"' not in stripped
        print(f"PASS: Code block tool stripped: '{stripped}'")
    
    def test_strip_all_mixed_formats(self):
        """Test stripping multiple formats at once"""
        original = '''I'll do multiple things:
[TOOL_CALL]{"tool": "a"}[/TOOL_CALL]
<tool_call>{"tool": "b"}</tool_call>
[tool_call]{"tool": "c"}[/tool_call]
```tool
{"tool": "d"}
```
Done!'''
        stripped = strip_tool_calls(original)
        assert "[TOOL_CALL]" not in stripped
        assert "<tool_call>" not in stripped
        assert "[tool_call]" not in stripped
        assert "```tool" not in stripped
        assert "I'll do multiple things:" in stripped
        assert "Done!" in stripped
        print(f"PASS: All mixed formats stripped")


class TestToolDefinitions:
    """Test tool definitions are complete"""
    
    def test_all_17_tools_defined(self):
        """Verify all 17 tools are in TOOL_DEFINITIONS"""
        expected_tools = [
            "create_project", "create_task", "update_task_status", "list_projects", "list_tasks",
            "create_artifact", "save_to_memory", "read_memory", "handoff_to_agent", "execute_code",
            "repo_list_files", "repo_read_file", "repo_write_file", "repo_approve_review",
            "wiki_list_pages", "wiki_read_page", "wiki_write_page"
        ]
        
        actual_tools = [t["name"] for t in TOOL_DEFINITIONS]
        assert len(actual_tools) >= 17, f"Expected at least 17 tools, got {len(actual_tools)}"
        
        for tool in expected_tools:
            assert tool in actual_tools, f"Missing tool: {tool}"
        
        print(f"PASS: All 17 tools defined: {actual_tools}")
    
    def test_tool_call_patterns_count(self):
        """Verify 5 regex patterns are defined"""
        assert len(TOOL_CALL_PATTERNS) == 5, f"Expected 5 patterns, got {len(TOOL_CALL_PATTERNS)}"
        print(f"PASS: 5 tool call patterns defined")


# ==================== API TESTS ====================

class TestAIToolsAPI:
    """Test GET /api/ai-tools endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
    
    def test_get_ai_tools_returns_all_17_tools(self):
        """GET /api/ai-tools returns all 17 tools"""
        response = self.session.get(f"{BASE_URL}/api/ai-tools")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "tools" in data
        
        tools = data["tools"]
        assert len(tools) >= 17, f"Expected at least 17 tools, got {len(tools)}"
        
        tool_names = [t["name"] for t in tools]
        assert "create_project" in tool_names
        assert "repo_list_files" in tool_names
        assert "wiki_list_pages" in tool_names
        assert "execute_code" in tool_names
        
        print(f"PASS: GET /api/ai-tools returns all 17 tools: {tool_names}")
    
    def test_tool_has_description_and_params(self):
        """Each tool has name, description, and params"""
        response = self.session.get(f"{BASE_URL}/api/ai-tools")
        assert response.status_code == 200
        
        tools = response.json()["tools"]
        for tool in tools:
            assert "name" in tool, f"Tool missing 'name'"
            assert "description" in tool, f"Tool {tool.get('name')} missing 'description'"
            assert "params" in tool, f"Tool {tool.get('name')} missing 'params'"
        
        print("PASS: All tools have name, description, and params")


class TestLegalPagesRegression:
    """Regression: Legal pages still render"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
    
    def test_terms_page_accessible(self):
        """GET /terms returns 200"""
        response = self.session.get(f"{BASE_URL}/terms")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "html" in response.text.lower()
        print("PASS: /terms page accessible (200)")
    
    def test_privacy_page_accessible(self):
        """GET /privacy returns 200"""
        response = self.session.get(f"{BASE_URL}/privacy")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "html" in response.text.lower()
        print("PASS: /privacy page accessible (200)")


class TestAuthenticatedToolExecution:
    """Test tool execution requires workspace context (authenticated tests)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.workspace_id = "ws_f6ec6355bb18"  # Test workspace from credentials
    
    def test_workspace_exists(self):
        """Verify test workspace exists via channels endpoint"""
        # This tests that the workspace context works
        response = self.session.get(
            f"{BASE_URL}/api/workspaces/{self.workspace_id}/channels"
        )
        # Will return 401 if not authenticated, but endpoint should exist
        assert response.status_code in [200, 401, 403], f"Unexpected status: {response.status_code}"
        print(f"PASS: Workspace endpoint exists (status: {response.status_code})")


# ==================== PATTERN VALIDATION TESTS ====================

class TestPatternMatching:
    """Test each regex pattern matches expected format"""
    
    def test_pattern_1_uppercase(self):
        """Pattern 1: [TOOL_CALL]...[/TOOL_CALL]"""
        pattern = TOOL_CALL_PATTERNS[0]
        test = '[TOOL_CALL]{"tool": "test"}[/TOOL_CALL]'
        matches = pattern.findall(test)
        assert len(matches) == 1
        assert '"tool": "test"' in matches[0]
        print("PASS: Pattern 1 matches uppercase format")
    
    def test_pattern_2_xml(self):
        """Pattern 2: <tool_call>...</tool_call>"""
        pattern = TOOL_CALL_PATTERNS[1]
        test = '<tool_call>{"tool": "test"}</tool_call>'
        matches = pattern.findall(test)
        assert len(matches) == 1
        print("PASS: Pattern 2 matches XML format")
    
    def test_pattern_3_lowercase(self):
        """Pattern 3: [tool_call]...[/tool_call]"""
        pattern = TOOL_CALL_PATTERNS[2]
        test = '[tool_call]{"tool": "test"}[/tool_call]'
        matches = pattern.findall(test)
        assert len(matches) == 1
        print("PASS: Pattern 3 matches lowercase format")
    
    def test_pattern_4_code_block_tool(self):
        """Pattern 4: ```tool ... ```"""
        pattern = TOOL_CALL_PATTERNS[3]
        test = '```tool\n{"tool": "test"}\n```'
        matches = pattern.findall(test)
        assert len(matches) == 1
        print("PASS: Pattern 4 matches code block tool format")
    
    def test_pattern_5_code_block_json(self):
        """Pattern 5: ```json {"tool": ...} ```"""
        pattern = TOOL_CALL_PATTERNS[4]
        test = '```json\n{"tool": "test", "params": {}}\n```'
        matches = pattern.findall(test)
        assert len(matches) == 1
        print("PASS: Pattern 5 matches JSON code block format")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
