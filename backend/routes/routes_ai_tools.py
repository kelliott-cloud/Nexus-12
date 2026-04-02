"""AI Agent Tools - allows AI agents to autonomously interact with Nexus workspace resources"""
import os
import uuid
import re
import json
import logging
from nexus_config import AI_MODELS
from nexus_utils import safe_regex
import re as _re
from datetime import datetime, timezone
from fastapi import Request

logger = logging.getLogger(__name__)

# Tool definitions that get injected into AI system prompts
TOOL_DEFINITIONS = [
    {
        "name": "create_project",
        "description": "Create a new project in the current workspace",
        "params": {
            "name": {"type": "string", "required": True, "description": "Project name"},
            "description": {"type": "string", "required": False, "description": "Project description"},
        },
    },
    {
        "name": "create_task",
        "description": "Create a new task in a project",
        "params": {
            "project_id": {"type": "string", "required": True, "description": "The project ID to add the task to"},
            "title": {"type": "string", "required": True, "description": "Task title"},
            "description": {"type": "string", "required": False, "description": "Task description"},
            "priority": {"type": "string", "required": False, "description": "Priority: low, medium, high, critical"},
            "status": {"type": "string", "required": False, "description": "Status: todo, in_progress, review, done"},
        },
    },
    {
        "name": "update_task_status",
        "description": "Update an existing task's status",
        "params": {
            "task_id": {"type": "string", "required": True, "description": "The task ID to update"},
            "status": {"type": "string", "required": True, "description": "New status: todo, in_progress, review, done"},
        },
    },
    {
        "name": "list_projects",
        "description": "List all projects in the current workspace",
        "params": {},
    },
    {
        "name": "list_tasks",
        "description": "List tasks in a specific project",
        "params": {
            "project_id": {"type": "string", "required": True, "description": "The project ID"},
        },
    },
    {
        "name": "create_artifact",
        "description": "Save content as a named artifact. Use artifact_type 'wireframe' for UI wireframes (SVG), 'html' for interactive prototypes, 'svg' for vector graphics.",
        "params": {
            "name": {"type": "string", "required": True, "description": "Artifact name"},
            "content": {"type": "string", "required": True, "description": "Content. For wireframes use SVG markup. For prototypes use full HTML."},
            "artifact_type": {"type": "string", "required": False, "description": "Type: text, code, json, markdown, wireframe, html, svg. Default: text"},
        },
    },
    {
        "name": "save_to_memory",
        "description": "Save a key piece of information to the workspace knowledge base for future reference",
        "params": {
            "key": {"type": "string", "required": True, "description": "A short descriptive key (e.g., 'api_architecture', 'user_preferences')"},
            "value": {"type": "string", "required": True, "description": "The information to store"},
            "category": {"type": "string", "required": False, "description": "Category: general, insight, decision, reference, context"},
        },
    },
    {
        "name": "read_memory",
        "description": "Read stored knowledge from the workspace memory/knowledge base",
        "params": {
            "search": {"type": "string", "required": False, "description": "Search query to find relevant entries"},
            "category": {"type": "string", "required": False, "description": "Filter by category"},
        },
    },
    {
        "name": "handoff_to_agent",
        "description": "Hand off context and findings to another AI agent for continued work",
        "params": {
            "to_agent": {"type": "string", "required": True, "description": "The agent to hand off to (e.g., 'claude', 'chatgpt')"},
            "title": {"type": "string", "required": True, "description": "Brief title of what's being handed off"},
            "content": {"type": "string", "required": True, "description": "The context, findings, or work to hand off"},
            "context_type": {"type": "string", "required": False, "description": "Type: general, findings, code, recommendation, analysis"},
        },
    },
    {
        "name": "execute_code",
        "description": "Execute code in a sandboxed environment and get the output (stdout, stderr, exit code)",
        "params": {
            "code": {"type": "string", "required": True, "description": "The code to execute"},
            "language": {"type": "string", "required": True, "description": "Programming language: python, javascript, go, rust, c, cpp, java, ruby, bash"},
        },
    },
    {
        "name": "repo_list_files",
        "description": "List all files in the workspace code repository. Returns the file tree with paths, languages, and sizes.",
        "params": {},
    },
    {
        "name": "repo_read_file",
        "description": "Read the contents of a specific file from the workspace code repository",
        "params": {
            "path": {"type": "string", "required": True, "description": "File path in the repo (e.g., 'src/main.py')"},
        },
    },
    {
        "name": "repo_write_file",
        "description": "Create or update a file in the workspace code repository. A QA review will be requested from other agents.",
        "params": {
            "path": {"type": "string", "required": True, "description": "File path to create/update (e.g., 'src/utils.py')"},
            "content": {"type": "string", "required": True, "description": "The full file content to write"},
            "message": {"type": "string", "required": False, "description": "Commit message describing the change"},
        },
    },
    {
        "name": "repo_approve_review",
        "description": "Approve or reject a pending QA review for a file commit. Use after reading a file with repo_read_file.",
        "params": {
            "file_path": {"type": "string", "required": True, "description": "The file path to approve/reject"},
            "approved": {"type": "boolean", "required": True, "description": "true to approve, false to reject"},
            "comment": {"type": "string", "required": False, "description": "Review comment or reason"},
        },
    },
    {
        "name": "wiki_list_pages",
        "description": "List all wiki/docs pages in the workspace",
        "params": {},
    },
    {
        "name": "wiki_read_page",
        "description": "Read the content of a wiki page by title",
        "params": {
            "title": {"type": "string", "required": True, "description": "Page title to read"},
        },
    },
    {
        "name": "wiki_write_page",
        "description": "Create or update a wiki page. If a page with this title exists, it will be updated.",
        "params": {
            "title": {"type": "string", "required": True, "description": "Page title"},
            "content": {"type": "string", "required": True, "description": "Page content in markdown"},
        },
    },
    {
        "name": "create_milestone",
        "description": "Create a milestone in a project with a due date. Use after creating a project.",
        "params": {
            "project_id": {"type": "string", "required": True, "description": "Project ID to add milestone to"},
            "name": {"type": "string", "required": True, "description": "Milestone name"},
            "due_date": {"type": "string", "required": False, "description": "Due date (YYYY-MM-DD format)"},
        },
    },
    {
        "name": "create_project_plan",
        "description": "Create a complete project with milestones and tasks in one call. Use this to build out a full project plan.",
        "params": {
            "name": {"type": "string", "required": True, "description": "Project name"},
            "description": {"type": "string", "required": False, "description": "Project description"},
            "milestones": {"type": "array", "required": True, "description": "Array of {name, due_date, tasks: [{title, priority, description}]}"},
        },
    },
    {
        "name": "save_context",
        "description": "Save your current work context before switching to a different topic. Use this when you're interrupted by a human or another agent and need to remember what you were working on so you can resume later.",
        "params": {
            "prior_work": {"type": "string", "required": True, "description": "Brief summary of what you were working on before the interruption"},
            "resume_note": {"type": "string", "required": False, "description": "Note to yourself about what to do next when you resume"},
        },
    },
    {
        "name": "browser_navigate",
        "description": "Navigate the Nexus Browser to a URL. Only the designated Browser Operator agent should use browser tools. The browser must be open first.",
        "params": {
            "url": {"type": "string", "required": True, "description": "The URL to navigate to"},
        },
    },
    {
        "name": "browser_click",
        "description": "Click an element in the Nexus Browser using a CSS selector.",
        "params": {
            "selector": {"type": "string", "required": True, "description": "CSS selector of the element to click (e.g., 'button.submit', '#login-btn', 'a[href=\"/signup\"]')"},
        },
    },
    {
        "name": "browser_type",
        "description": "Type text into an input field in the Nexus Browser.",
        "params": {
            "selector": {"type": "string", "required": True, "description": "CSS selector of the input field"},
            "text": {"type": "string", "required": True, "description": "Text to type into the field"},
        },
    },
    {
        "name": "browser_read",
        "description": "Read the visible text content of the current page in the Nexus Browser.",
        "params": {},
    },
    {
        "name": "browser_request_help",
        "description": "Request human assistance with the browser. Use when you encounter CAPTCHAs, login screens, or anything you can't handle. Specify exactly what help you need.",
        "params": {
            "help_needed": {"type": "string", "required": True, "description": "Specific description of what you need the human to do (e.g., 'Please solve the CAPTCHA on the page', 'Please log in with your credentials')"},
        },
    },
    {
        "name": "browser_get_elements",
        "description": "Get a list of all interactive elements on the current page (links, buttons, input fields). Use this AFTER navigating to understand what you can click or interact with.",
        "params": {},
    },
    {
        "name": "delete_project",
        "description": "Delete a project (moves to recycle bin, recoverable by admin).",
        "params": {
            "project_id": {"type": "string", "required": True, "description": "The project ID to delete"},
        },
    },
    {
        "name": "delete_task",
        "description": "Delete a task from a project (moves to recycle bin).",
        "params": {
            "task_id": {"type": "string", "required": True, "description": "The task ID to delete"},
        },
    },
    {
        "name": "delete_artifact",
        "description": "Delete an artifact (moves to recycle bin).",
        "params": {
            "artifact_id": {"type": "string", "required": True, "description": "The artifact ID to delete"},
        },
    },
    # TPM Tools
    {
        "name": "ask_tpm",
        "description": "Request direction from the TPM when you're unsure what to do next. The TPM will respond with guidance.",
        "params": {
            "question": {"type": "string", "required": True, "description": "Your question or what you need direction on"},
        },
    },
    {
        "name": "create_work_item",
        "description": "Create a work item and assign it to a specific agent. Only TPMs should use this to delegate work.",
        "params": {
            "title": {"type": "string", "required": True, "description": "Work item title"},
            "description": {"type": "string", "required": False, "description": "Detailed description"},
            "assigned_to": {"type": "string", "required": True, "description": "Agent key to assign to (e.g., 'claude', 'chatgpt')"},
            "priority": {"type": "integer", "required": False, "description": "Priority 1-5 (1=highest)"},
        },
    },
    {
        "name": "post_tpm_directive",
        "description": "TPM posts a directive that all agents must follow. Only TPMs should use this.",
        "params": {
            "directive": {"type": "string", "required": True, "description": "The directive/instruction for agents"},
            "target_agent": {"type": "string", "required": False, "description": "Specific agent key, or 'all' for everyone"},
            "priority": {"type": "string", "required": False, "description": "critical, high, normal, or low"},
        },
    },
]


def build_tool_prompt():
    """Build the tool documentation string for AI system prompts"""
    lines = [
        "\n\n--- AVAILABLE TOOLS ---",
        "You can perform actions in Nexus by including a tool call block in your response.",
        "Format: [TOOL_CALL]{\"tool\": \"tool_name\", \"params\": {\"key\": \"value\"}}[/TOOL_CALL]",
        "Alternative formats also work: <tool_call>...</tool_call> or ```tool ... ```",
        "You may include multiple tool calls. Place them at the END of your response after your text.",
        "Tools execute immediately and results appear in the conversation.",
        "Only use tools when the conversation context clearly calls for it.\n",
    ]
    for t in TOOL_DEFINITIONS:
        params_desc = ""
        if t["params"]:
            param_parts = []
            for pname, pinfo in t["params"].items():
                req = " (required)" if pinfo.get("required") else " (optional)"
                param_parts.append(f"    - {pname}: {pinfo['description']}{req}")
            params_desc = "\n".join(param_parts)
        lines.append(f"  {t['name']}: {t['description']}")
        if params_desc:
            lines.append(params_desc)
    lines.append("--- END TOOLS ---")
    return "\n".join(lines)


TOOL_PROMPT = build_tool_prompt()

# Regex patterns to find tool calls in AI responses (multiple formats)
TOOL_CALL_PATTERNS = [
    re.compile(r'\[TOOL_CALL\](.*?)\[/TOOL_CALL\]', re.DOTALL),
    re.compile(r'<tool_call>(.*?)</tool_call>', re.DOTALL),
    re.compile(r'\[tool_call\](.*?)\[/tool_call\]', re.DOTALL),
    re.compile(r'```tool\s*\n(.*?)```', re.DOTALL),
    re.compile(r'```json\s*\n(\{.*?"tool".*?\})\s*```', re.DOTALL),
]

TOOL_STRIP_PATTERNS = [
    re.compile(r'\[TOOL_CALL\].*?\[/TOOL_CALL\]', re.DOTALL),
    re.compile(r'<tool_call>.*?</tool_call>', re.DOTALL),
    re.compile(r'\[tool_call\].*?\[/tool_call\]', re.DOTALL),
    re.compile(r'```tool\s*\n.*?```', re.DOTALL),
]


def parse_tool_calls(response_text):
    """Extract tool call JSON blocks from AI response text (handles multiple formats)"""
    if not response_text:
        return []
    calls = []
    for pattern in TOOL_CALL_PATTERNS:
        matches = pattern.findall(response_text)
        for raw in matches:
            try:
                parsed = json.loads(raw.strip())
                if "tool" in parsed and parsed not in calls:
                    calls.append(parsed)
            except json.JSONDecodeError:
                # Try to find JSON within the match
                try:
                    json_match = re.search(r'\{.*"tool".*\}', raw, re.DOTALL)
                    if json_match:
                        parsed = json.loads(json_match.group())
                        if "tool" in parsed and parsed not in calls:
                            calls.append(parsed)
                except (json.JSONDecodeError, AttributeError):
                    logger.warning(f"Failed to parse tool call: {raw[:100]}")
    return calls


def strip_tool_calls(response_text):
    """Remove tool call blocks from the visible message text"""
    result = response_text
    for pattern in TOOL_STRIP_PATTERNS:
        result = pattern.sub('', result)
    return result.strip()


async def execute_tool(db, tool_call, workspace_id, agent_name, channel_id):
    """Execute a single tool call and return a result message"""
    tool_name = tool_call.get("tool")
    params = tool_call.get("params") or {}
    now = datetime.now(timezone.utc).isoformat()

    # Blocked modules check
    BLOCKED_TOOLS = set()  # Members, Directives, Reports have no tools
    if tool_name in BLOCKED_TOOLS:
        return _tool_error(f"Tool {tool_name} is not available to AI agents")

    result = await _execute_tool_inner(db, tool_call, workspace_id, agent_name, channel_id)
    
    # Log workspace activity for ALL tool executions (success and failure)
    MODULE_MAP = {
        "create_project": "projects", "list_projects": "projects",
        "create_task": "tasks", "list_tasks": "tasks", "update_task_status": "tasks",
        "create_artifact": "artifacts",
        "save_to_memory": "knowledge", "read_memory": "knowledge",
        "execute_code": "code",
        "repo_list_files": "code_repo", "repo_read_file": "code_repo",
        "repo_write_file": "code_repo", "repo_approve_review": "code_repo",
        "wiki_list_pages": "wiki", "wiki_read_page": "wiki", "wiki_write_page": "wiki",
        "handoff_to_agent": "collaboration",
        "save_context": "context", "create_milestone": "projects",
        "create_project_plan": "projects",
    }
    module = MODULE_MAP.get(tool_name, "other")
    status = result.get("status", "unknown") if result else "error"
    try:
        await db.workspace_activities.insert_one({
            "activity_id": f"act_{uuid.uuid4().hex[:12]}",
            "workspace_id": workspace_id,
            "channel_id": channel_id,
            "agent": agent_name,
            "action_type": "tool_call",
            "tool": tool_name,
            "module": module,
            "status": status,
            "summary": (result.get("message", "") if result else "Tool execution failed")[:300],
            "params": {k: str(v)[:100] for k, v in params.items()} if params else {},
            "timestamp": now,
        })
    except Exception as e:
        logger.warning(f"Non-critical error at line 358: {e}")
    
    return result


async def _execute_tool_inner(db, tool_call, workspace_id, agent_name, channel_id):
    """Inner tool execution — returns result dict"""
    tool_name = tool_call.get("tool")
    params = tool_call.get("params") or {}
    now = datetime.now(timezone.utc).isoformat()

    # === TOOL ACCESS GATING ===
    if agent_name:
        try:
            nxa_doc = await db.nexus_agents.find_one(
                {"workspace_id": workspace_id, "$or": [
                    {"name": agent_name},
                    {"agent_id": agent_name},
                ]},
                {"_id": 0, "allowed_tools": 1, "denied_tools": 1}
            )
            if nxa_doc:
                denied = nxa_doc.get("denied_tools") or []
                allowed = nxa_doc.get("allowed_tools") or []
                if denied and tool_name in denied:
                    return _tool_error(f"Tool '{tool_name}' is not permitted for this agent. This restriction was configured in the Agent Studio.")
                if allowed and tool_name not in allowed:
                    return _tool_error(f"Tool '{tool_name}' is not in this agent's authorized tool list. Authorized tools: {', '.join(allowed[:10])}")
        except Exception as _e:
            import logging; logging.getLogger("routes/routes_ai_tools").warning(f"Suppressed: {_e}")  # Don't block tool execution on gating lookup failure

    try:
        if tool_name == "create_project":
            name = params.get("name", "").strip()
            if not name:
                return _tool_error("create_project requires a 'name' parameter")
            
            # Deduplication check
            from dedup_engine import check_duplicate_project, build_duplicate_block_message, log_duplicate_override
            dup = await check_duplicate_project(db, workspace_id, name, params.get("description", ""))
            if dup["is_duplicate"]:
                override_reason = params.get("override_reason", "").strip()
                if not override_reason:
                    return _tool_error(build_duplicate_block_message(dup, "create_project"))
                await log_duplicate_override(db, workspace_id, channel_id, agent_name,
                    "project", name, dup["existing_id"], dup["existing_name"], override_reason, dup["similarity"])
            
            project_id = f"proj_{uuid.uuid4().hex[:12]}"
            project = {
                "project_id": project_id,
                "workspace_id": workspace_id,
                "name": name,
                "description": params.get("description", "").strip(),
                "status": "active",
                "linked_channels": [channel_id],
                "created_by": f"ai:{agent_name}",
                "created_at": now,
                "updated_at": now,
            }
            await db.projects.insert_one(project)
            return _tool_success(f"Project **{name}** created (ID: `{project_id}`)", "create_project", agent_name)

        elif tool_name == "create_task":
            project_id = params.get("project_id", "").strip()
            title = params.get("title", "").strip()
            if not project_id or not title:
                return _tool_error("create_task requires 'project_id' and 'title'")
            project = await db.projects.find_one({"project_id": project_id, "workspace_id": workspace_id})
            if not project:
                return _tool_error(f"Project `{project_id}` not found in this workspace")
            
            # Deduplication check
            from dedup_engine import check_duplicate_task, build_duplicate_block_message, log_duplicate_override
            dup = await check_duplicate_task(db, project_id, title, params.get("description", ""))
            if dup["is_duplicate"]:
                override_reason = params.get("override_reason", "").strip()
                if not override_reason:
                    return _tool_error(build_duplicate_block_message(dup, "create_task"))
                await log_duplicate_override(db, workspace_id, channel_id, agent_name,
                    "task", title, dup["existing_id"], dup["existing_name"], override_reason, dup["similarity"])
            
            priority = params.get("priority", "medium")
            if priority not in ("low", "medium", "high", "critical"):
                priority = "medium"
            status = params.get("status", "todo")
            if status not in ("todo", "in_progress", "review", "done"):
                status = "todo"
            task_id = f"ptask_{uuid.uuid4().hex[:12]}"
            task = {
                "task_id": task_id,
                "project_id": project_id,
                "title": title,
                "description": params.get("description", ""),
                "status": status,
                "priority": priority,
                "assignee_type": "ai",
                "assignee_id": agent_name,
                "assignee_name": agent_name,
                "created_by": f"ai:{agent_name}",
                "created_at": now,
                "updated_at": now,
            }
            await db.project_tasks.insert_one(task)
            return _tool_success(f"Task **{title}** created in project **{project['name']}** [{priority}]", "create_task", agent_name)

        elif tool_name == "update_task_status":
            task_id = params.get("task_id", "").strip()
            status = params.get("status", "").strip()
            if not task_id or not status:
                return _tool_error("update_task_status requires 'task_id' and 'status'")
            if status not in ("todo", "in_progress", "review", "done"):
                return _tool_error(f"Invalid status: {status}. Use: todo, in_progress, review, done")
            task = await db.project_tasks.find_one({"task_id": task_id})
            if not task:
                return _tool_error(f"Task `{task_id}` not found")
            old_status = task.get("status", "unknown")
            updates = {"status": status, "updated_at": now}
            if status == "done":
                updates["completed_at"] = now
                updates["completed_by"] = f"ai:{agent_name}"
            await db.project_tasks.update_one(
                {"task_id": task_id},
                {"$set": updates}
            )
            # Log activity and send notification on completion
            if status == "done":
                await db.task_activity.insert_one({
                    "activity_id": f"ta_{uuid.uuid4().hex[:12]}",
                    "task_id": task_id,
                    "action": "completed",
                    "actor_name": agent_name,
                    "details": {"old_status": old_status, "new_status": status},
                    "timestamp": now,
                })
                # Notify workspace owner
                if task.get("project_id"):
                    proj = await db.projects.find_one({"project_id": task["project_id"]}, {"_id": 0, "workspace_id": 1})
                    if proj:
                        ws = await db.workspaces.find_one({"workspace_id": proj.get("workspace_id", "")}, {"_id": 0, "owner_id": 1})
                        if ws:
                            await db.notifications.insert_one({
                                "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
                                "user_id": ws["owner_id"],
                                "type": "task_completed",
                                "title": f"Task completed: {task.get('title', '')}",
                                "message": f"{agent_name} marked '{task.get('title', '')}' as done",
                                "read": False,
                                "created_at": now,
                            })
            return _tool_success(f"Task **{task['title']}** status: `{old_status}` → `{status}`", "update_task_status", agent_name)

        elif tool_name == "list_projects":
            projects = await db.projects.find(
                {"workspace_id": workspace_id, "is_deleted": {"$ne": True}}, {"_id": 0, "project_id": 1, "name": 1, "status": 1}
            ).to_list(20)
            if not projects:
                return _tool_success("No projects found in this workspace.", "list_projects", agent_name)
            lines = [f"- **{p['name']}** (`{p['project_id']}`) [{p.get('status','active')}]" for p in projects]
            return _tool_success("Projects:\n" + "\n".join(lines), "list_projects", agent_name)

        elif tool_name == "list_tasks":
            project_id = params.get("project_id", "").strip()
            if not project_id:
                return _tool_error("list_tasks requires 'project_id'")
            tasks = await db.project_tasks.find(
                {"project_id": project_id, "is_deleted": {"$ne": True}}, {"_id": 0, "task_id": 1, "title": 1, "status": 1, "priority": 1}
            ).to_list(50)
            if not tasks:
                return _tool_success("No tasks found in this project.", "list_tasks", agent_name)
            lines = [f"- **{t['title']}** (`{t['task_id']}`) [{t.get('status','todo')}] {t.get('priority','medium')}" for t in tasks]
            return _tool_success("Tasks:\n" + "\n".join(lines), "list_tasks", agent_name)

        elif tool_name == "create_artifact":
            name = params.get("name", "").strip()
            content = params.get("content", "").strip()
            if not name or not content:
                return _tool_error("create_artifact requires 'name' and 'content'")
            
            # Deduplication check
            from dedup_engine import check_duplicate_artifact, build_duplicate_block_message, log_duplicate_override
            dup = await check_duplicate_artifact(db, workspace_id, name, content)
            if dup["is_duplicate"]:
                override_reason = params.get("override_reason", "").strip()
                if not override_reason:
                    return _tool_error(build_duplicate_block_message(dup, "create_artifact"))
                await log_duplicate_override(db, workspace_id, channel_id, agent_name,
                    "artifact", name, dup["existing_id"], dup["existing_name"], override_reason, dup["similarity"])
            
            artifact_type = params.get("artifact_type", "text")
            if artifact_type not in ("text", "code", "json", "markdown", "wireframe", "html", "svg"):
                artifact_type = "text"
            artifact_id = f"art_{uuid.uuid4().hex[:12]}"
            artifact = {
                "artifact_id": artifact_id,
                "workspace_id": workspace_id,
                "workflow_id": None,
                "name": name,
                "type": artifact_type,
                "content": content,
                "tags": ["ai-generated"],
                "pinned": False,
                "version": 1,
                "created_by": f"ai:{agent_name}",
                "created_at": now,
                "updated_at": now,
            }
            await db.artifacts.insert_one(artifact)
            # Also save version
            await db.artifact_versions.insert_one({
                "version_id": f"av_{uuid.uuid4().hex[:12]}",
                "artifact_id": artifact_id,
                "version": 1,
                "content": content,
                "created_by": f"ai:{agent_name}",
                "created_at": now,
            })
            return _tool_success(f"Artifact **{name}** saved ({artifact_type})", "create_artifact", agent_name)

        elif tool_name == "save_to_memory":
            key = params.get("key", "").strip()
            value = params.get("value", "").strip()
            if not key or not value:
                return _tool_error("save_to_memory requires 'key' and 'value'")
            category = params.get("category", "general")
            if category not in ("general", "insight", "decision", "reference", "context"):
                category = "general"
            now = datetime.now(timezone.utc).isoformat()
            existing = await db.workspace_memory.find_one({"workspace_id": workspace_id, "key": key})
            if existing:
                await db.workspace_memory.update_one(
                    {"workspace_id": workspace_id, "key": key},
                    {"$set": {"value": value, "category": category, "updated_by": f"ai:{agent_name}", "updated_at": now, "version": existing.get("version", 1) + 1}}
                )
                return _tool_success(f"Memory **{key}** updated (v{existing.get('version', 1) + 1})", "save_to_memory", agent_name)
            memory_id = f"mem_{uuid.uuid4().hex[:12]}"
            await db.workspace_memory.insert_one({
                "memory_id": memory_id, "workspace_id": workspace_id, "key": key, "value": value,
                "category": category, "tags": ["ai-generated"], "version": 1,
                "created_by": f"ai:{agent_name}", "updated_by": f"ai:{agent_name}", "created_at": now, "updated_at": now,
            })
            return _tool_success(f"Saved to memory: **{key}**", "save_to_memory", agent_name)

        elif tool_name == "read_memory":
            search = params.get("search", "")
            category = params.get("category", "")
            query = {"workspace_id": workspace_id}
            if search:
                query["$or"] = [
                    {"key": {"$regex": safe_regex(search), "$options": "i"}},
                    {"value": {"$regex": safe_regex(search), "$options": "i"}},
                ]
            if category:
                query["category"] = category
            entries = await db.workspace_memory.find(query, {"_id": 0, "memory_id": 0}).sort("updated_at", -1).to_list(10)
            if not entries:
                return _tool_success("No memory entries found.", "read_memory", agent_name)
            lines = [f"- **{e['key']}** [{e.get('category','general')}]: {e['value'][:200]}" for e in entries]
            return _tool_success("Memory:\n" + "\n".join(lines), "read_memory", agent_name)

        elif tool_name == "handoff_to_agent":
            to_agent = params.get("to_agent", "").strip()
            title = params.get("title", "").strip()
            content = params.get("content", "").strip()
            if not to_agent or not title or not content:
                return _tool_error("handoff_to_agent requires 'to_agent', 'title', and 'content'")
            context_type = params.get("context_type", "general")
            handoff_id = f"ho_{uuid.uuid4().hex[:12]}"
            now = datetime.now(timezone.utc).isoformat()
            await db.handoffs.insert_one({
                "handoff_id": handoff_id, "channel_id": channel_id, "workspace_id": workspace_id,
                "from_agent": agent_name, "to_agent": to_agent, "context_type": context_type,
                "title": title, "content": content, "metadata": {}, "status": "pending",
                "created_by": f"ai:{agent_name}", "created_at": now,
            })
            # Post handoff message
            await db.messages.insert_one({
                "message_id": f"msg_{uuid.uuid4().hex[:12]}", "channel_id": channel_id,
                "sender_type": "handoff", "sender_id": agent_name, "sender_name": agent_name,
                "content": f"**Handoff to {to_agent}**: {title}\n\n{content[:500]}",
                "handoff": {"handoff_id": handoff_id, "from_agent": agent_name, "to_agent": to_agent, "context_type": context_type, "title": title},
                "created_at": now,
            })
            return _tool_success(f"Handed off **{title}** to {to_agent}", "handoff_to_agent", agent_name)

        elif tool_name == "execute_code":
            code = params.get("code", "").strip()
            language = params.get("language", "python").strip().lower()
            if not code:
                return _tool_error("execute_code requires 'code' parameter")

            LANG_MAP = {
                "python": "python3", "javascript": "javascript", "typescript": "typescript",
                "go": "go", "rust": "rust", "c": "c", "cpp": "c++",
                "java": "java", "ruby": "ruby", "bash": "bash",
            }
            runtime = LANG_MAP.get(language)
            if not runtime:
                return _tool_error(f"Unsupported language: {language}. Use: {', '.join(LANG_MAP.keys())}")

            try:
                import httpx
                PISTON_URL = os.environ.get("PISTON_URL", "https://emkc.org/api/v2/piston")
                async with httpx.AsyncClient(timeout=30.0) as http_client:
                    resp = await http_client.post(f"{PISTON_URL}/execute", json={
                        "language": runtime,
                        "version": "*",
                        "files": [{"content": code}],
                        "run_timeout": 10000,
                        "compile_timeout": 10000,
                        "run_memory_limit": 128_000_000,
                    })
                    result = resp.json()

                run = result.get("run") or {}
                stdout_text = (run.get("stdout") or "")[:2000]
                stderr_text = (run.get("stderr") or "")[:1000]
                exit_code = run.get("code", -1)

                output = f"**Exit code:** `{exit_code}`\n"
                if stdout_text:
                    output += f"**stdout:**\n```\n{stdout_text}\n```\n"
                if stderr_text:
                    output += f"**stderr:**\n```\n{stderr_text}\n```"
                return _tool_success(output.strip(), "execute_code", agent_name)
            except Exception as exec_err:
                return _tool_error(f"Code execution failed: {str(exec_err)[:200]}")

        elif tool_name == "repo_list_files":
            files = await db.repo_files.find(
                {"workspace_id": workspace_id, "is_deleted": {"$ne": True}},
                {"_id": 0, "file_id": 1, "path": 1, "is_folder": 1, "language": 1, "size": 1, "version": 1}
            ).sort("path", 1).to_list(200)
            if not files:
                return _tool_success("The code repository is empty. Use `repo_write_file` to create files.", "repo_list_files", agent_name)
            lines = []
            for f in files:
                if f.get("is_folder"):
                    lines.append(f"  {f['path']}/ (folder)")
                else:
                    sz = f.get("size", 0)
                    sz_str = f"{sz}B" if sz < 1024 else f"{sz//1024}KB"
                    lines.append(f"  {f['path']} [{f.get('language','')}] {sz_str} v{f.get('version',1)}")
            return _tool_success(f"**Repository files ({len(files)}):**\n```\n" + "\n".join(lines) + "\n```", "repo_list_files", agent_name)

        elif tool_name == "repo_read_file":
            file_path = params.get("path", "").strip()
            if not file_path:
                return _tool_error("repo_read_file requires 'path' parameter")
            f = await db.repo_files.find_one(
                {"workspace_id": workspace_id, "path": file_path, "is_deleted": {"$ne": True}, "is_folder": False},
                {"_id": 0}
            )
            if not f:
                return _tool_error(f"File not found: {file_path}")
            content = f.get("content", "")
            lang = f.get("language", "")
            return _tool_success(f"**{file_path}** (v{f.get('version',1)}, {lang}):\n```{lang}\n{content}\n```", "repo_read_file", agent_name)

        elif tool_name == "repo_write_file":
            file_path = params.get("path", "").strip()
            content = params.get("content", "")
            commit_msg = params.get("message", f"Update {file_path}")
            if not file_path:
                return _tool_error("repo_write_file requires 'path' parameter")
            if not content:
                return _tool_error("repo_write_file requires 'content' parameter")

            # Role-based write restriction: QA and Security agents cannot write production code
            channel_doc = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0, "channel_roles": 1})
            if channel_doc:
                roles = channel_doc.get("channel_roles") or {}
                qa_agents = roles.get("qa") or []
                # Map agent_name back to agent_key
                agent_key_map = {v.get("name", ""): k for k, v in AI_MODELS.items()} if "AI_MODELS" in dir() else {}
                current_key = agent_key_map.get(agent_name, agent_name)
                if current_key in qa_agents:
                    return _tool_error("QA agents cannot write production code. Your role is to review and file bugs, not write files. Use create_task to file a bug instead.")
                if current_key == roles.get("security"):
                    return _tool_error("Security agents cannot write production code. Your role is to review for vulnerabilities. Use create_task to file security issues.")
                if current_key == roles.get("tpm"):
                    return _tool_error("TPM agents should not write code. Use project management tools (create_task, update_task_status) instead.")

            # File lock check — prevent overwrite conflicts
            existing_file = await db.repo_files.find_one(
                {"workspace_id": workspace_id, "path": file_path, "is_deleted": {"$ne": True}}
            )
            if existing_file:
                last_updated = existing_file.get("updated_at", "")
                last_author = existing_file.get("updated_by", existing_file.get("created_by", ""))
                # If another agent updated in the last 30 seconds, block
                if last_author and last_author != f"ai:{agent_name}" and last_updated:
                    try:
                        updated_dt = datetime.fromisoformat(last_updated)
                        if updated_dt.tzinfo is None:
                            updated_dt = updated_dt.replace(tzinfo=timezone.utc)
                        elapsed = (datetime.now(timezone.utc) - updated_dt).total_seconds()
                        if elapsed < 30:
                            return _tool_error(f"File '{file_path}' was just modified by {last_author.replace('ai:', '')} ({int(elapsed)}s ago). Wait before overwriting to avoid conflicts.")
                    except Exception as e:
                        logger.warning(f"Non-critical error at line 757: {e}")
            else:
                # Deduplication check for new files
                from dedup_engine import check_duplicate_repo_file, build_duplicate_block_message, log_duplicate_override
                dup = await check_duplicate_repo_file(db, workspace_id, file_path, content)
                if dup["is_duplicate"]:
                    override_reason = params.get("override_reason", "").strip()
                    if not override_reason:
                        return _tool_error(build_duplicate_block_message(dup, "repo_write_file"))
                    await log_duplicate_override(db, workspace_id, channel_id, agent_name,
                        "repo_file", file_path, dup["existing_id"], dup["existing_name"], override_reason, dup["similarity"])

            now_ts = datetime.now(timezone.utc).isoformat()
            # Ensure repo exists
            repo = await db.code_repos.find_one({"workspace_id": workspace_id})
            if not repo:
                await db.code_repos.insert_one({
                    "repo_id": f"repo_{uuid.uuid4().hex[:12]}",
                    "workspace_id": workspace_id,
                    "created_at": now_ts, "updated_at": now_ts, "file_count": 0,
                })

            existing = await db.repo_files.find_one(
                {"workspace_id": workspace_id, "path": file_path, "is_deleted": {"$ne": True}}
            )
            if existing:
                old_content = existing.get("content", "")
                new_ver = existing.get("version", 0) + 1
                await db.repo_files.update_one(
                    {"file_id": existing["file_id"]},
                    {"$set": {"content": content, "size": len(content.encode("utf-8")),
                              "version": new_ver, "updated_by": f"ai:{agent_name}", "updated_at": now_ts}}
                )
                file_id = existing["file_id"]
                action = "update"
            else:
                file_id = f"rf_{uuid.uuid4().hex[:12]}"
                fname = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path
                ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
                lang_map = {"py": "python", "js": "javascript", "jsx": "javascript", "ts": "typescript", "tsx": "typescript",
                            "html": "html", "css": "css", "json": "json", "md": "markdown", "yaml": "yaml", "yml": "yaml",
                            "sh": "shell", "go": "go", "rs": "rust", "rb": "ruby", "java": "java", "sql": "sql"}
                new_ver = 1
                old_content = ""
                action = "create"
                await db.repo_files.insert_one({
                    "file_id": file_id, "workspace_id": workspace_id,
                    "path": file_path, "name": fname, "is_folder": False,
                    "language": lang_map.get(ext, "plaintext"),
                    "content": content, "size": len(content.encode("utf-8")),
                    "version": 1, "created_by": f"ai:{agent_name}",
                    "updated_by": f"ai:{agent_name}",
                    "created_at": now_ts, "updated_at": now_ts, "is_deleted": False,
                })

            # Create commit
            await db.repo_commits.insert_one({
                "commit_id": f"rc_{uuid.uuid4().hex[:12]}",
                "workspace_id": workspace_id, "file_id": file_id,
                "file_path": file_path, "action": action,
                "message": f"{agent_name}: {commit_msg}",
                "author_id": f"ai:{agent_name}", "author_name": agent_name,
                "content_before": old_content[:50000] if action == "update" else "",
                "content_after": content[:50000],
                "version": new_ver, "created_at": now_ts,
            })

            await db.code_repos.update_one(
                {"workspace_id": workspace_id}, {"$set": {"updated_at": now_ts}}
            )

            # Post confirmation in channel
            await db.messages.insert_one({
                "message_id": f"msg_{uuid.uuid4().hex[:12]}",
                "channel_id": channel_id,
                "sender_type": "system",
                "sender_id": "system",
                "sender_name": "System",
                "content": f"**saving to repo** — `{file_path}` {action}d by {agent_name}",
                "created_at": now_ts,
            })

            # Queue for QA review by another agent
            review_id = f"rr_{uuid.uuid4().hex[:12]}"
            await db.repo_reviews.insert_one({
                "review_id": review_id,
                "workspace_id": workspace_id,
                "channel_id": channel_id,
                "file_id": file_id,
                "file_path": file_path,
                "content": content[:50000],
                "author": agent_name,
                "status": "pending",
                "created_at": now_ts,
            })

            # Post QA request in channel
            await db.messages.insert_one({
                "message_id": f"msg_{uuid.uuid4().hex[:12]}",
                "channel_id": channel_id,
                "sender_type": "system",
                "sender_id": "system",
                "sender_name": "System",
                "content": f"**QA Review requested** — `{file_path}` by {agent_name} needs review. Other agents can use `repo_read_file` to review.",
                "created_at": now_ts,
            })

            return _tool_success(f"**saving to repo** — `{file_path}` {action}d (v{new_ver}). QA review requested.", "repo_write_file", agent_name)

        elif tool_name == "repo_approve_review":
            file_path = params.get("file_path", "").strip()
            approved = params.get("approved", True)
            comment = params.get("comment", "")
            if not file_path:
                return _tool_error("repo_approve_review requires 'file_path'")
            review = await db.repo_reviews.find_one(
                {"workspace_id": workspace_id, "file_path": file_path, "status": "pending"},
                {"_id": 0}
            )
            if not review:
                return _tool_error(f"No pending review found for {file_path}")
            now_ts = datetime.now(timezone.utc).isoformat()
            status = "approved" if approved else "rejected"
            await db.repo_reviews.update_one(
                {"review_id": review["review_id"]},
                {"$set": {"status": status, "reviewer": agent_name, "review_comment": comment, "reviewed_at": now_ts}}
            )
            # Post review result
            await db.messages.insert_one({
                "message_id": f"msg_{uuid.uuid4().hex[:12]}",
                "channel_id": channel_id,
                "sender_type": "system",
                "sender_id": "system",
                "sender_name": "System",
                "content": f"**QA {status.upper()}** — `{file_path}` reviewed by {agent_name}" + (f": {comment}" if comment else ""),
                "created_at": now_ts,
            })
            return _tool_success(f"QA review **{status}** for `{file_path}`" + (f" — {comment}" if comment else ""), "repo_approve_review", agent_name)

        elif tool_name == "wiki_list_pages":
            pages = await db.wiki_pages.find(
                {"workspace_id": workspace_id, "is_deleted": {"$ne": True}},
                {"_id": 0, "page_id": 1, "title": 1, "parent_id": 1, "word_count": 1, "updated_at": 1}
            ).sort("title", 1).to_list(100)
            if not pages:
                return _tool_success("No wiki pages yet. Use `wiki_write_page` to create one.", "wiki_list_pages", agent_name)
            lines = [f"  {p['title']} ({p.get('word_count', 0)} words)" for p in pages]
            return _tool_success(f"**Wiki pages ({len(pages)}):**\n" + "\n".join(lines), "wiki_list_pages", agent_name)

        elif tool_name == "wiki_read_page":
            title = params.get("title", "").strip()
            if not title:
                return _tool_error("wiki_read_page requires 'title'")
            page = await db.wiki_pages.find_one(
                {"workspace_id": workspace_id, "title": {"$regex": f"^{safe_regex(title)}$", "$options": "i"}, "is_deleted": {"$ne": True}},
                {"_id": 0}
            )
            if not page:
                return _tool_error(f"Wiki page not found: {title}")
            return _tool_success(f"**{page['title']}** (v{page.get('version', 1)}):\n\n{page.get('content', '')}", "wiki_read_page", agent_name)

        elif tool_name == "wiki_write_page":
            title = params.get("title", "").strip()
            content = params.get("content", "")
            if not title:
                return _tool_error("wiki_write_page requires 'title'")
            now_ts = datetime.now(timezone.utc).isoformat()
            existing = await db.wiki_pages.find_one(
                {"workspace_id": workspace_id, "title": {"$regex": f"^{safe_regex(title)}$", "$options": "i"}, "is_deleted": {"$ne": True}}
            )
            if existing:
                new_ver = existing.get("version", 0) + 1
                await db.wiki_pages.update_one(
                    {"page_id": existing["page_id"]},
                    {"$set": {"content": content, "version": new_ver, "word_count": len(content.split()),
                              "updated_by": f"ai:{agent_name}", "updated_by_name": agent_name, "updated_at": now_ts}}
                )
                await db.wiki_versions.insert_one({
                    "version_id": f"wv_{uuid.uuid4().hex[:12]}", "page_id": existing["page_id"],
                    "version": new_ver, "title": title, "content": content,
                    "author_id": f"ai:{agent_name}", "author_name": agent_name, "created_at": now_ts,
                })
                return _tool_success(f"Wiki page **{title}** updated (v{new_ver})", "wiki_write_page", agent_name)
            else:
                page_id = f"wp_{uuid.uuid4().hex[:12]}"
                await db.wiki_pages.insert_one({
                    "page_id": page_id, "workspace_id": workspace_id, "title": title,
                    "content": content, "parent_id": None, "icon": "", "pinned": False,
                    "word_count": len(content.split()), "version": 1,
                    "created_by": f"ai:{agent_name}", "created_by_name": agent_name,
                    "updated_by": f"ai:{agent_name}", "updated_by_name": agent_name,
                    "created_at": now_ts, "updated_at": now_ts, "is_deleted": False,
                })
                await db.wiki_versions.insert_one({
                    "version_id": f"wv_{uuid.uuid4().hex[:12]}", "page_id": page_id,
                    "version": 1, "title": title, "content": content,
                    "author_id": f"ai:{agent_name}", "author_name": agent_name, "created_at": now_ts,
                })
                return _tool_success(f"Wiki page **{title}** created", "wiki_write_page", agent_name)

        elif tool_name == "create_milestone":
            project_id = params.get("project_id", "").strip()
            ms_name = params.get("name", "").strip()
            due_date = params.get("due_date", "")
            if not project_id or not ms_name:
                return _tool_error("create_milestone requires 'project_id' and 'name'")
            
            # Deduplication check
            from dedup_engine import check_duplicate_milestone, build_duplicate_block_message, log_duplicate_override
            dup = await check_duplicate_milestone(db, project_id, ms_name)
            if dup["is_duplicate"]:
                override_reason = params.get("override_reason", "").strip()
                if not override_reason:
                    return _tool_error(build_duplicate_block_message(dup, "create_milestone"))
                await log_duplicate_override(db, workspace_id, channel_id, agent_name,
                    "milestone", ms_name, dup["existing_id"], dup["existing_name"], override_reason, dup["similarity"])
            
            ms_id = f"ms_{uuid.uuid4().hex[:12]}"
            await db.milestones.insert_one({
                "milestone_id": ms_id, "project_id": project_id,
                "name": ms_name, "description": "", "due_date": due_date or None,
                "status": "open", "created_by": f"ai:{agent_name}",
                "created_at": now, "updated_at": now,
            })
            return _tool_success(f"Milestone **{ms_name}** created in project `{project_id}` (due: {due_date or 'unset'})", "create_milestone", agent_name)

        elif tool_name == "create_project_plan":
            proj_name = params.get("name", "").strip()
            proj_desc = params.get("description", "")
            milestones = params.get("milestones") or []
            if not proj_name:
                return _tool_error("create_project_plan requires 'name'")
            
            # Create project
            project_id = f"proj_{uuid.uuid4().hex[:12]}"
            await db.projects.insert_one({
                "project_id": project_id, "workspace_id": workspace_id,
                "name": proj_name, "description": proj_desc,
                "status": "active", "linked_channels": [channel_id] if channel_id else [],
                "created_by": f"ai:{agent_name}", "created_at": now, "updated_at": now,
            })
            
            ms_count = 0
            task_count = 0
            for ms_def in (milestones if isinstance(milestones, list) else []):
                ms_name = ms_def.get("name", f"Milestone {ms_count + 1}") if isinstance(ms_def, dict) else str(ms_def)
                due_date = ms_def.get("due_date", "") if isinstance(ms_def, dict) else ""
                ms_id = f"ms_{uuid.uuid4().hex[:12]}"
                await db.milestones.insert_one({
                    "milestone_id": ms_id, "project_id": project_id,
                    "name": ms_name, "description": "", "due_date": due_date or None,
                    "status": "open", "created_by": f"ai:{agent_name}",
                    "created_at": now, "updated_at": now,
                })
                ms_count += 1
                
                tasks = ms_def.get("tasks") or [] if isinstance(ms_def, dict) else []
                for task_def in (tasks if isinstance(tasks, list) else []):
                    t_title = task_def.get("title", f"Task {task_count + 1}") if isinstance(task_def, dict) else str(task_def)
                    t_priority = task_def.get("priority", "medium") if isinstance(task_def, dict) else "medium"
                    t_desc = task_def.get("description", "") if isinstance(task_def, dict) else ""
                    task_id = f"ptask_{uuid.uuid4().hex[:12]}"
                    await db.project_tasks.insert_one({
                        "task_id": task_id, "project_id": project_id, "workspace_id": workspace_id,
                        "title": t_title, "description": t_desc, "status": "todo",
                        "priority": t_priority, "item_type": "task",
                        "assignee_type": "ai", "assignee_id": agent_name, "assignee_name": agent_name,
                        "parent_task_id": None, "labels": [], "story_points": None,
                        "created_by": f"ai:{agent_name}", "created_at": now, "updated_at": now,
                    })
                    # Link task to milestone
                    await db.task_relationships.insert_one({
                        "relationship_id": f"trel_{uuid.uuid4().hex[:12]}",
                        "task_id": task_id, "target_task_id": "",
                        "milestone_id": ms_id, "relationship_type": "milestone",
                        "created_by": f"ai:{agent_name}", "created_at": now,
                    })
                    task_count += 1
            
            return _tool_success(
                f"Project plan **{proj_name}** created with {ms_count} milestones and {task_count} tasks. Project ID: `{project_id}`",
                "create_project_plan", agent_name
            )

        elif tool_name == "save_context":
            prior_work = params.get("prior_work", "")
            resume_note = params.get("resume_note", "")
            if not prior_work:
                return _tool_error("save_context requires 'prior_work'")
            from routes_context_ledger import save_context_entry
            await save_context_entry(
                db, channel_id, workspace_id, agent_name, agent_name,
                "context_save", prior_work, resume_note, f"self:{agent_name}",
                response_summary=resume_note
            )
            return _tool_success(
                f"Context saved. You can resume this work later: \"{prior_work[:100]}\"",
                "save_context", agent_name
            )

        # --- Nexus Browser Tools ---
        elif tool_name == "browser_navigate":
            url = params.get("url", "")
            if not url:
                return _tool_error("browser_navigate requires 'url'")
            from routes_nexus_browser import navigate, get_session_info, create_session
            if not get_session_info(channel_id):
                await create_session(channel_id, url)
                return _tool_success(f"Nexus Browser opened and navigated to {url}", "browser_navigate", agent_name)
            result = await navigate(channel_id, url)
            if "error" in result:
                return _tool_error(result["error"])
            return _tool_success(f"Navigated to **{result.get('title', url)}** ({result['url']})", "browser_navigate", agent_name)

        elif tool_name == "browser_click":
            selector = params.get("selector", "")
            if not selector:
                return _tool_error("browser_click requires 'selector'")
            from routes_nexus_browser import click_element
            result = await click_element(channel_id, selector)
            if "error" in result:
                return _tool_error(result["error"])
            return _tool_success(f"Clicked `{selector}` — now at {result.get('url', '?')}", "browser_click", agent_name)

        elif tool_name == "browser_type":
            selector = params.get("selector", "")
            text = params.get("text", "")
            if not selector or not text:
                return _tool_error("browser_type requires 'selector' and 'text'")
            from routes_nexus_browser import type_text
            result = await type_text(channel_id, selector, text)
            if "error" in result:
                return _tool_error(result["error"])
            return _tool_success(f"Typed into `{selector}`", "browser_type", agent_name)

        elif tool_name == "browser_read":
            from routes_nexus_browser import get_page_text
            result = await get_page_text(channel_id)
            if "error" in result:
                return _tool_error(result["error"])
            return _tool_success(
                f"**Page: {result.get('title', '?')}** ({result['url']})\n\n{result['text']}",
                "browser_read", agent_name
            )

        elif tool_name == "browser_request_help":
            help_needed = params.get("help_needed", "")
            if not help_needed:
                return _tool_error("browser_request_help requires 'help_needed'")
            from routes_nexus_browser import request_human_help
            await request_human_help(channel_id, help_needed)
            # Post a visible help request message in the channel
            await db.messages.insert_one({
                "message_id": f"msg_{uuid.uuid4().hex[:12]}",
                "channel_id": channel_id,
                "sender_type": "system",
                "sender_id": "browser",
                "sender_name": "Nexus Browser",
                "content": f"**Human Help Needed** — {agent_name} needs your assistance:\n\n_{help_needed}_\n\nPlease interact with the browser panel and click **Resolve** when done.",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            return _tool_success(f"Help request posted. Waiting for human to assist with: {help_needed}", "browser_request_help", agent_name)

        elif tool_name == "browser_get_elements":
            from routes_nexus_browser import get_page_elements
            result = await get_page_elements(channel_id)
            if "error" in result:
                return _tool_error(result["error"])
            lines = [f"**Page: {result.get('title', '?')}** ({result['url']}) — {result['count']} interactive elements:\n"]
            for el in result.get("elements") or []:
                if el["type"] == "link":
                    lines.append(f"  [link] \"{el['text']}\" → selector: `{el['selector']}`")
                elif el["type"] == "button":
                    lines.append(f"  [button] \"{el['text']}\" → selector: `{el['selector']}`")
                elif el["type"] == "input":
                    lines.append(f"  [input:{el.get('inputType','text')}] label=\"{el['label']}\" → selector: `{el['selector']}`")
            return _tool_success("\n".join(lines), "browser_get_elements", agent_name)

        # --- Delete Tools (Soft Delete → Recycle Bin) ---
        elif tool_name == "delete_project":
            project_id = params.get("project_id", "").strip()
            if not project_id:
                return _tool_error("delete_project requires 'project_id'")
            project = await db.projects.find_one({"project_id": project_id, "workspace_id": workspace_id, "is_deleted": {"$ne": True}})
            if not project:
                return _tool_error(f"Project `{project_id}` not found")
            from recycle_bin import soft_delete
            await soft_delete(db, "projects", "project_id", project_id, workspace_id, f"ai:{agent_name}", agent_name)
            tasks_cursor = await db.project_tasks.find({"project_id": project_id, "is_deleted": {"$ne": True}}, {"_id": 0, "task_id": 1}).to_list(500)
            for t in tasks_cursor:
                await soft_delete(db, "project_tasks", "task_id", t["task_id"], workspace_id, f"ai:{agent_name}", agent_name)
            return _tool_success(f"Project **{project.get('name')}** and {len(tasks_cursor)} tasks moved to recycle bin", "delete_project", agent_name)

        elif tool_name == "delete_task":
            task_id = params.get("task_id", "").strip()
            if not task_id:
                return _tool_error("delete_task requires 'task_id'")
            task = await db.project_tasks.find_one({"task_id": task_id, "is_deleted": {"$ne": True}})
            if not task:
                return _tool_error(f"Task `{task_id}` not found")
            from recycle_bin import soft_delete
            await soft_delete(db, "project_tasks", "task_id", task_id, workspace_id, f"ai:{agent_name}", agent_name)
            return _tool_success(f"Task **{task.get('title')}** moved to recycle bin", "delete_task", agent_name)

        elif tool_name == "delete_artifact":
            artifact_id = params.get("artifact_id", "").strip()
            if not artifact_id:
                return _tool_error("delete_artifact requires 'artifact_id'")
            artifact = await db.artifacts.find_one({"artifact_id": artifact_id, "workspace_id": workspace_id, "is_deleted": {"$ne": True}})
            if not artifact:
                return _tool_error(f"Artifact `{artifact_id}` not found")
            from recycle_bin import soft_delete
            await soft_delete(db, "artifacts", "artifact_id", artifact_id, workspace_id, f"ai:{agent_name}", agent_name)
            return _tool_success(f"Artifact **{artifact.get('name')}** moved to recycle bin", "delete_artifact", agent_name)

        # === EXTENDED TOOLS (from agent_tools_extended.py) ===
        elif tool_name == "web_search":
            from agent_tools_extended import tool_web_search
            return await tool_web_search(db, workspace_id, params)
        elif tool_name == "generate_image":
            from agent_tools_extended import tool_generate_image
            ws_doc = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "owner_id": 1})
            user_id = ws_doc.get("owner_id", "") if ws_doc else ""
            return await tool_generate_image(db, workspace_id, user_id, params)
        elif tool_name == "ask_human":
            from agent_tools_extended import tool_ask_human
            return await tool_ask_human(db, channel_id, agent_name.lower().replace(" ", ""), params)
        elif tool_name == "read_file":
            from agent_tools_extended import tool_read_file
            return await tool_read_file(db, workspace_id, params)
        elif tool_name == "log_decision":
            from agent_tools_extended import tool_log_decision
            return await tool_log_decision(db, workspace_id, channel_id, params)
        elif tool_name == "query_decisions":
            from agent_tools_extended import tool_query_decisions
            return await tool_query_decisions(db, workspace_id, params)
        elif tool_name == "search_channels":
            from agent_tools_extended import tool_search_channels
            return await tool_search_channels(db, workspace_id, params)
        elif tool_name == "send_alert":
            from agent_tools_extended import tool_send_alert
            return await tool_send_alert(db, workspace_id, channel_id, params)
        elif tool_name == "branch_conversation":
            from agent_tools_extended import tool_branch_conversation
            return await tool_branch_conversation(db, channel_id, params.get("from_message_id", ""), params)

        elif tool_name == "ask_tpm":
            question = params.get("question", "")
            if not question:
                return _tool_error("Question is required")
            ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "tpm_agent_id": 1})
            tpm_id = (ws or {}).get("tpm_agent_id")
            if not tpm_id:
                return {"result": "No TPM designated in this workspace. Proceed with your best judgment."}
            tpm_agent = await db.nexus_agents.find_one({"agent_id": tpm_id}, {"_id": 0, "name": 1, "base_model": 1})
            await db.work_queue.insert_one({
                "item_id": f"wq_{uuid.uuid4().hex[:12]}", "workspace_id": workspace_id,
                "title": f"Question from agent: {question[:100]}", "description": question,
                "assigned_to": (tpm_agent or {}).get("base_model", ""), "priority": 1,
                "status": "pending", "item_type": "tpm_question", "from_agent": params.get("_agent_key", ""),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            return {"result": f"Question sent to TPM ({(tpm_agent or {}).get('name', 'TPM')}). They will respond with direction."}

        elif tool_name == "create_work_item":
            title = params.get("title", "")
            if not title:
                return _tool_error("Title is required")
            await db.work_queue.insert_one({
                "item_id": f"wq_{uuid.uuid4().hex[:12]}", "workspace_id": workspace_id,
                "title": title, "description": params.get("description", ""),
                "assigned_to": params.get("assigned_to", ""), "priority": params.get("priority", 3),
                "status": "pending", "item_type": "task",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            return {"result": f"Work item '{title}' assigned to {params.get('assigned_to', 'unassigned')}"}

        elif tool_name == "post_tpm_directive":
            directive = params.get("directive", "")
            if not directive:
                return _tool_error("Directive text is required")
            await db.tpm_queue.insert_one({
                "directive_id": f"tpmd_{uuid.uuid4().hex[:12]}", "workspace_id": workspace_id,
                "directive": directive[:1000], "target_agent": params.get("target_agent", "all"),
                "priority": params.get("priority", "normal"), "status": "active",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            return {"result": f"Directive posted to TPM queue for {params.get('target_agent', 'all agents')}"}

        else:
            return _tool_error(f"Unknown tool: {tool_name}")

    except Exception as e:
        logger.error(f"Tool execution error ({tool_name}): {e}")
        return _tool_error(f"Tool execution failed: {str(e)}")


def _tool_success(message, tool_name, agent_name):
    return {"status": "success", "tool": tool_name, "agent": agent_name, "message": message}


def _tool_error(message):
    return {"status": "error", "message": message}


# --- Mention Parsing ---

# Match @word patterns — agent keys, 'everyone', or custom agent names (supports underscores, dots, hyphens)
MENTION_PATTERN = re.compile(r'@([\w._-]+)')

# Built-in agent keys
BUILTIN_AGENT_KEYS = {"claude", "chatgpt", "gemini", "perplexity", "mistral", "cohere", "groq", "deepseek", "grok", "mercury", "pi"}

# Alternative name mappings for built-in agents
AGENT_ALIASES = {
    "gpt": "chatgpt", "gpt4": "chatgpt", "gpt-4": "chatgpt", "openai": "chatgpt",
    "anthropic": "claude", "sonnet": "claude",
    "google": "gemini", "bard": "gemini",
    "llama": "groq", "meta": "groq",
    "mercury2": "mercury", "mercury-2": "mercury",
}


def parse_mentions(content, channel_agents=None, nexus_agents=None):
    """Parse @mentions from message content.
    Returns a dict with:
      - mentioned_agents: list of agent keys that were specifically mentioned
      - mention_everyone: bool if @everyone was used
      - has_mentions: bool if any valid mentions were found
    """
    raw_mentions = [m.lower() for m in MENTION_PATTERN.findall(content)]
    if not raw_mentions:
        return {"mentioned_agents": [], "mention_everyone": False, "has_mentions": False}

    mention_everyone = "everyone" in raw_mentions
    mentioned_agents = []

    # Build lookup of valid agents in this channel
    valid_agents = set(channel_agents or [])

    # Also build a name→key mapping for Nexus agents and add their IDs to valid set
    nexus_name_map = {}
    if nexus_agents:
        for agent in nexus_agents:
            agent_id = agent.get("agent_id", "")
            valid_agents.add(agent_id)
            # Map lowercase name (spaces removed) to agent_id
            clean_name = agent.get("name", "").lower().replace(" ", "")
            nexus_name_map[clean_name] = agent_id

    for mention in raw_mentions:
        if mention == "everyone":
            continue
        # Check built-in agents (exact match)
        if mention in BUILTIN_AGENT_KEYS and mention in valid_agents:
            mentioned_agents.append(mention)
        # Check aliases
        elif mention in AGENT_ALIASES and AGENT_ALIASES[mention] in valid_agents:
            mentioned_agents.append(AGENT_ALIASES[mention])
        # Check nexus agent name match (exact, lowercase, no spaces)
        elif mention in nexus_name_map and nexus_name_map[mention] in valid_agents:
            mentioned_agents.append(nexus_name_map[mention])
        # Check partial nexus agent name match (prefix)
        else:
            for clean_name, agent_id in nexus_name_map.items():
                if clean_name.startswith(mention) and agent_id in valid_agents:
                    mentioned_agents.append(agent_id)
                    break
            else:
                # Check direct agent_id match
                if mention in valid_agents:
                    mentioned_agents.append(mention)

    return {
        "mentioned_agents": list(set(mentioned_agents)),
        "mention_everyone": mention_everyone,
        "has_mentions": bool(mentioned_agents) or mention_everyone,
    }


def register_ai_tools_routes(api_router, db, get_current_user):
    """Register API routes for AI tool management"""

    @api_router.get("/ai-tools")
    async def get_available_tools():
        """Get list of available AI tools"""
        return {"tools": TOOL_DEFINITIONS}

    @api_router.get("/workspaces/{workspace_id}/tools")
    async def get_workspace_available_tools(workspace_id: str, request: Request):
        """Workspace-scoped alias for available AI tools used by Agent Studio."""
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return {"tools": TOOL_DEFINITIONS}

    @api_router.get("/channels/{channel_id}/mentionable")
    async def get_mentionable_agents(channel_id: str, request: Request):
        """Get list of agents that can be @mentioned in a channel"""
        await get_current_user(request)
        channel = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0})
        if not channel:
            return {"agents": []}

        workspace_id = channel.get("workspace_id", "")  # noqa: F841
        agents = []

        # Add built-in agents
        for agent_key in channel.get("ai_agents") or []:
            if agent_key in BUILTIN_AGENT_KEYS:
                agents.append({
                    "key": agent_key,
                    "name": agent_key.capitalize() if agent_key != "chatgpt" else "ChatGPT",
                    "type": "builtin",
                })
            elif agent_key.startswith("nxa_"):
                # Nexus agent
                nxa = await db.nexus_agents.find_one({"agent_id": agent_key}, {"_id": 0, "agent_id": 1, "name": 1, "color": 1})
                if nxa:
                    agents.append({
                        "key": nxa["agent_id"],
                        "name": nxa["name"],
                        "type": "nexus",
                        "color": nxa.get("color"),
                    })

        # Always add @everyone
        agents.append({"key": "everyone", "name": "everyone", "type": "special"})
        return {"agents": agents}
