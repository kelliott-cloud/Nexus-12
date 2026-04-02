"""Code Execution Sandbox + GitHub/GitLab Integration + CI/CD Triggers"""
import uuid
import os
import logging
import time
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request
from nexus_utils import now_iso

logger = logging.getLogger(__name__)

PISTON_API = "https://emkc.org/api/v2/piston"
SUPPORTED_LANGUAGES = ["python", "javascript", "typescript", "go", "rust", "c", "cpp", "java", "ruby", "php", "bash", "sql", "r", "swift", "kotlin", "csharp"]

GITHUB_API = "https://api.github.com"


class CodeExecuteRequest(BaseModel):
    code: str = Field(..., min_length=1)
    language: str = "python"
    stdin: str = ""
    timeout_ms: int = 10000



def register_code_dev_routes(api_router, db, get_current_user):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import validate_external_url, now_iso, require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user

    # ======================================================
    # CODE EXECUTION SANDBOX (#1 + #4)
    # ======================================================

    @api_router.post("/code/execute")
    async def execute_code(data: CodeExecuteRequest, request: Request):
        """Execute code via Piston API (sandboxed)"""
        user = await get_current_user(request)
        if data.language not in SUPPORTED_LANGUAGES:
            raise HTTPException(400, f"Unsupported language. Use: {SUPPORTED_LANGUAGES}")

        start_time = time.time()
        exec_id = f"cex_{uuid.uuid4().hex[:12]}"

        try:
            import httpx
            PISTON_URL = os.environ.get("PISTON_URL", "https://emkc.org/api/v2/piston")
            LANG_MAP = {"python": "python", "javascript": "javascript", "typescript": "typescript", "bash": "bash", "java": "java", "cpp": "c++", "go": "go", "rust": "rust", "ruby": "ruby", "php": "php"}
            piston_lang = LANG_MAP.get(data.language, data.language)

            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(f"{PISTON_URL}/execute", json={
                    "language": piston_lang, "version": "*",
                    "files": [{"content": data.code}],
                    "stdin": data.stdin or "",
                    "run_timeout": min(data.timeout_ms, 15000),
                })
                result = resp.json()
                run = result.get("run") or {}

            stdout_text = (run.get("stdout", "") or "")[:5000]
            stderr_text = (run.get("stderr", "") or "")[:2000]
            exit_code = run.get("code", -1)
            duration_ms = int((time.time() - start_time) * 1000)

            execution = {
                "exec_id": exec_id,
                "language": data.language,
                "code_length": len(data.code),
                "stdout": stdout_text,
                "stderr": stderr_text,
                "exit_code": exit_code,
                "duration_ms": duration_ms,
                "success": exit_code == 0,
                "executed_by": user["user_id"],
                "executed_at": now_iso(),
            }

            # Log execution
            await db.code_executions.insert_one(execution)

            return {k: v for k, v in execution.items() if k != "_id"}

        except httpx.TimeoutException:
            return {"exec_id": exec_id, "success": False, "stdout": "", "stderr": "Execution timed out", "exit_code": -1, "duration_ms": int((time.time() - start_time) * 1000)}
        except Exception as e:
            logger.error(f"Code execution failed: {e}")
            raise HTTPException(500, f"Execution failed: {str(e)[:200]}")

    @api_router.get("/code/runtimes")
    async def list_runtimes(request: Request):
        """List available code execution runtimes"""
        await get_current_user(request)
        return {"languages": SUPPORTED_LANGUAGES, "provider": "piston", "max_timeout_ms": 30000}

    @api_router.get("/code/executions")
    async def list_executions(request: Request, limit: int = 20):
        """List recent code executions"""
        user = await get_current_user(request)
        execs = await db.code_executions.find({"executed_by": user["user_id"]}, {"_id": 0}).sort("executed_at", -1).limit(limit).to_list(limit)
        return {"executions": execs}

    # ======================================================
    # GITHUB INTEGRATION (#2)
    # ======================================================

    @api_router.post("/github/connect")
    async def connect_github(request: Request):
        """Initiate GitHub OAuth connection"""
        user = await get_current_user(request)
        body = await request.json()
        scope = body.get("scope", "user")
        org_id = body.get("org_id")

        from key_resolver import get_integration_key
        client_id = await get_integration_key(db, "GITHUB_CLIENT_ID", org_id)

        if not client_id:
            raise HTTPException(501, "GitHub not configured. Add GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET to integration settings.")

        import secrets
        state = secrets.token_urlsafe(24)
        conn_id = f"ghc_{uuid.uuid4().hex[:12]}"

        await db.github_connections.insert_one({
            "connection_id": conn_id, "user_id": user["user_id"],
            "scope": scope, "org_id": org_id,
            "status": "pending", "oauth_state": state,
            "access_token": None, "github_username": None,
            "created_at": now_iso(),
        })

        from nexus_utils import now_iso, validate_redirect_uri
        redirect_uri = validate_redirect_uri(
            body.get("redirect_uri", f"{os.environ.get('APP_URL', '')}/api/github/callback"),
            os.environ.get("APP_URL", "")
        )
        auth_url = f"https://github.com/login/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&state={state}&scope=repo,read:org,write:discussion"

        return {"connection_id": conn_id, "auth_url": auth_url, "state": state}

    @api_router.post("/github/callback")
    async def github_callback(request: Request):
        """Handle GitHub OAuth callback"""
        body = await request.json()
        code = body.get("code", "")
        state = body.get("state", "")

        conn = await db.github_connections.find_one({"oauth_state": state, "status": "pending"})
        if not conn:
            raise HTTPException(404, "Connection not found")

        from key_resolver import get_integration_key
        org_id = conn.get("org_id")
        client_id = await get_integration_key(db, "GITHUB_CLIENT_ID", org_id)
        client_secret = await get_integration_key(db, "GITHUB_CLIENT_SECRET", org_id)

        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.post("https://github.com/login/oauth/access_token",
                    headers={"Accept": "application/json"},
                    json={"client_id": client_id, "client_secret": client_secret, "code": code})
                tokens = resp.json()

            if "access_token" not in tokens:
                raise HTTPException(400, f"Auth failed: {tokens.get('error_description', 'unknown')}")

            # Get user info
            async with httpx.AsyncClient() as client:
                user_resp = await client.get(f"{GITHUB_API}/user", headers={"Authorization": f"Bearer {tokens['access_token']}"})
                gh_user = user_resp.json()

            from encryption import get_fernet; fernet = get_fernet()
            enc_token = fernet.encrypt(tokens["access_token"].encode()).decode()

            await db.github_connections.update_one(
                {"connection_id": conn["connection_id"]},
                {"$set": {"status": "active", "access_token": enc_token,
                          "github_username": gh_user.get("login", ""), "github_name": gh_user.get("name", ""),
                          "avatar_url": gh_user.get("avatar_url", "")}}
            )
            return {"connection_id": conn["connection_id"], "status": "active", "username": gh_user.get("login", "")}
        except HTTPException: raise
        except Exception as e:
            raise HTTPException(500, f"GitHub auth failed: {str(e)[:200]}")

    @api_router.get("/github/connections")
    async def list_github_connections(request: Request, scope: str = "user", org_id: Optional[str] = None):
        user = await get_current_user(request)
        query = {"status": "active"}
        if scope == "org" and org_id:
            query["org_id"] = org_id
        else:
            query["user_id"] = user["user_id"]
        conns = await db.github_connections.find(query, {"_id": 0, "access_token": 0, "oauth_state": 0}).to_list(5)
        return {"connections": conns}

    @api_router.delete("/github/connections/{conn_id}")
    async def disconnect_github(conn_id: str, request: Request):
        await get_current_user(request)
        await db.github_connections.update_one({"connection_id": conn_id}, {"$set": {"status": "revoked"}})
        return {"message": "Disconnected"}

    # --- GitHub File Operations ---

    @api_router.get("/github/connections/{conn_id}/repos")
    async def list_repos(conn_id: str, request: Request):
        """List GitHub repositories"""
        await get_current_user(request)
        conn = await db.github_connections.find_one({"connection_id": conn_id, "status": "active"})
        if not conn: raise HTTPException(404, "Connection not found")
        from encryption import get_fernet; fernet = get_fernet()
        token = fernet.decrypt(conn["access_token"].encode()).decode()
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{GITHUB_API}/user/repos?per_page=50&sort=updated", headers={"Authorization": f"Bearer {token}"})
            repos = resp.json()
        return {"repos": [{"id": r["id"], "name": r["full_name"], "private": r["private"], "url": r["html_url"], "default_branch": r.get("default_branch", "main"), "language": r.get("language")} for r in repos if isinstance(r, dict)]}

    @api_router.get("/github/connections/{conn_id}/repos/{owner}/{repo}/tree")
    async def get_repo_tree(conn_id: str, owner: str, repo: str, request: Request, ref: str = "main", path: str = ""):
        """Browse repository file tree"""
        await get_current_user(request)
        conn = await db.github_connections.find_one({"connection_id": conn_id, "status": "active"})
        if not conn: raise HTTPException(404, "Connection not found")
        from encryption import get_fernet; fernet = get_fernet()
        token = fernet.decrypt(conn["access_token"].encode()).decode()
        import httpx
        url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}?ref={ref}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
            items = resp.json()
        if isinstance(items, list):
            return {"items": [{"name": i["name"], "path": i["path"], "type": i["type"], "size": i.get("size", 0), "sha": i.get("sha", "")} for i in items]}
        return {"items": []}

    @api_router.get("/github/connections/{conn_id}/repos/{owner}/{repo}/file")
    async def get_file_content(conn_id: str, owner: str, repo: str, request: Request, path: str = "", ref: str = "main"):
        """Get file content from repository"""
        await get_current_user(request)
        conn = await db.github_connections.find_one({"connection_id": conn_id, "status": "active"})
        if not conn: raise HTTPException(404, "Connection not found")
        from encryption import get_fernet; fernet = get_fernet()
        token = fernet.decrypt(conn["access_token"].encode()).decode()
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}?ref={ref}", headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3.raw"})
            content = resp.text
        return {"path": path, "content": content, "ref": ref}

    # --- GitHub Write Operations ---

    @api_router.post("/github/connections/{conn_id}/repos/{owner}/{repo}/pr")
    async def create_pull_request(conn_id: str, owner: str, repo: str, request: Request):
        """Create a pull request"""
        await get_current_user(request)
        body = await request.json()
        conn = await db.github_connections.find_one({"connection_id": conn_id, "status": "active"})
        if not conn: raise HTTPException(404, "Connection not found")
        from encryption import get_fernet; fernet = get_fernet()
        token = fernet.decrypt(conn["access_token"].encode()).decode()
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{GITHUB_API}/repos/{owner}/{repo}/pulls",
                headers={"Authorization": f"Bearer {token}"},
                json={"title": body.get("title", ""), "body": body.get("body", ""), "head": body.get("head", ""), "base": body.get("base", "main")})
            pr = resp.json()
        return {"pr_number": pr.get("number"), "url": pr.get("html_url"), "state": pr.get("state")}

    @api_router.post("/github/connections/{conn_id}/repos/{owner}/{repo}/issues")
    async def create_issue(conn_id: str, owner: str, repo: str, request: Request):
        """Create a GitHub issue"""
        await get_current_user(request)
        body = await request.json()
        conn = await db.github_connections.find_one({"connection_id": conn_id, "status": "active"})
        if not conn: raise HTTPException(404, "Connection not found")
        from encryption import get_fernet; fernet = get_fernet()
        token = fernet.decrypt(conn["access_token"].encode()).decode()
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{GITHUB_API}/repos/{owner}/{repo}/issues",
                headers={"Authorization": f"Bearer {token}"},
                json={"title": body.get("title", ""), "body": body.get("body", ""), "labels": body.get("labels") or []})
            issue = resp.json()
        return {"issue_number": issue.get("number"), "url": issue.get("html_url")}

    # --- CI/CD Event Triggers (#9) ---

    @api_router.post("/github/webhook")
    async def github_webhook_handler(request: Request):
        """Public endpoint — receives GitHub webhook events and triggers workflows"""
        body = await request.json()
        event_type = request.headers.get("X-GitHub-Event", "")
        repo_name = (body.get("repository") or {}).get("full_name", "")

        # Find matching workflow triggers
        triggers = await db.workflow_triggers.find(
            {"type": "github_event", "enabled": True}, {"_id": 0}
        ).to_list(10)

        triggered_runs = []
        for trigger in triggers:
            config = trigger.get("github_config") or {}
            if config.get("repo") and config["repo"] != repo_name:
                continue
            if config.get("events") and event_type not in config["events"]:
                continue

            # Trigger the workflow
            import asyncio
            from workflow_engine import WorkflowOrchestrator, SSEManager
            run_id = f"wrun_{uuid.uuid4().hex[:12]}"
            now = now_iso()
            input_data = {"event": event_type, "repo": repo_name, "payload": body}

            await db.workflow_runs.insert_one({
                "run_id": run_id, "workflow_id": trigger["workflow_id"],
                "status": "queued", "triggered_by": f"github:{event_type}",
                "run_by": trigger.get("created_by", "github"),
                "initial_input": input_data, "created_at": now,
            })
            sse = SSEManager()
            orchestrator = WorkflowOrchestrator(db, sse)
            asyncio.create_task(orchestrator.execute_workflow(run_id))
            triggered_runs.append(run_id)

        return {"processed": True, "event": event_type, "triggered_runs": triggered_runs}

    @api_router.post("/workflows/{workflow_id}/trigger/github")
    async def create_github_trigger(workflow_id: str, request: Request):
        """Create a GitHub event trigger for a workflow"""
        user = await get_current_user(request)
        body = await request.json()
        trigger_id = f"wft_{uuid.uuid4().hex[:12]}"
        await db.workflow_triggers.insert_one({
            "trigger_id": trigger_id, "workflow_id": workflow_id,
            "type": "github_event", "enabled": True,
            "github_config": {
                "repo": body.get("repo", ""),
                "events": body.get("events", ["push", "pull_request"]),
            },
            "created_by": user["user_id"], "created_at": now_iso(),
        })
        webhook_url = "/api/github/webhook"
        return {"trigger_id": trigger_id, "webhook_url": webhook_url,
                "instructions": f"Add {webhook_url} as a webhook in your GitHub repo settings. Select events: {body.get('events', ['push', 'pull_request'])}"}

    # ======================================================
    # DEV WORKFLOW TEMPLATES (#5)
    # ======================================================

    @api_router.get("/workflow-templates/dev")
    async def get_dev_templates(request: Request):
        """Get code-focused workflow templates"""
        await get_current_user(request)
        return {"templates": [
            {
                "template_id": "wst_code_review_pipeline", "name": "Multi-Model Code Review Pipeline",
                "description": "Paste code → Claude reviews security → ChatGPT reviews style → DeepSeek reviews performance → merged report artifact",
                "category": "development",
                "nodes": [
                    {"type": "input", "label": "Code Input"},
                    {"type": "ai_agent", "label": "Security Review", "ai_model": "claude", "system_prompt": "You are a security expert. Review the code for vulnerabilities, injection risks, and security best practices."},
                    {"type": "ai_agent", "label": "Style Review", "ai_model": "chatgpt", "system_prompt": "You are a code style expert. Review for readability, naming conventions, and clean code principles."},
                    {"type": "ai_agent", "label": "Performance Review", "ai_model": "deepseek", "system_prompt": "You are a performance engineer. Review for algorithmic efficiency, memory usage, and optimization opportunities."},
                    {"type": "merge", "label": "Merge Reviews", "merge_strategy": "concatenate"},
                    {"type": "output", "label": "Review Report"},
                ],
            },
            {
                "template_id": "wst_feature_builder", "name": "Feature Builder",
                "description": "Describe feature → research best practices → generate implementation → execute tests → human review → create PR",
                "category": "development",
                "nodes": [
                    {"type": "input", "label": "Feature Description"},
                    {"type": "ai_agent", "label": "Research", "ai_model": "perplexity", "system_prompt": "Research best practices and existing solutions for implementing this feature."},
                    {"type": "ai_agent", "label": "Implement", "ai_model": "claude", "system_prompt": "Generate a complete implementation based on the research. Include tests."},
                    {"type": "code_execute", "label": "Run Tests"},
                    {"type": "human_review", "label": "Code Review"},
                    {"type": "output", "label": "Approved Code"},
                ],
            },
            {
                "template_id": "wst_bug_diagnosis", "name": "Bug Diagnosis",
                "description": "Paste error → one agent reproduces → another root-causes → third generates fix → sandbox validates",
                "category": "development",
                "nodes": [
                    {"type": "input", "label": "Error + Stack Trace"},
                    {"type": "ai_agent", "label": "Reproduce", "ai_model": "chatgpt", "system_prompt": "Analyze this error and create a minimal reproduction case."},
                    {"type": "ai_agent", "label": "Root Cause", "ai_model": "claude", "system_prompt": "Analyze the reproduction and identify the root cause of this bug."},
                    {"type": "ai_agent", "label": "Generate Fix", "ai_model": "deepseek", "system_prompt": "Generate a fix for this bug based on the root cause analysis. Include the fixed code."},
                    {"type": "code_execute", "label": "Validate Fix"},
                    {"type": "output", "label": "Verified Fix"},
                ],
            },
        ]}

    # ======================================================
    # PROJECT-CODE LINKING (#6)
    # ======================================================

    @api_router.post("/tasks/{task_id}/link-artifact")
    async def link_code_artifact(task_id: str, request: Request):
        """Link a code artifact to a task"""
        await get_current_user(request)
        body = await request.json()
        artifact_id = body.get("artifact_id", "")
        if not artifact_id:
            raise HTTPException(400, "artifact_id required")
        await db.project_tasks.update_one(
            {"task_id": task_id},
            {"$addToSet": {"code_artifact_ids": artifact_id}, "$set": {"updated_at": now_iso()}}
        )
        return {"task_id": task_id, "linked": artifact_id}

    @api_router.get("/tasks/{task_id}/linked-artifacts")
    async def get_linked_artifacts(task_id: str, request: Request):
        await get_current_user(request)
        task = await db.project_tasks.find_one({"task_id": task_id}, {"_id": 0, "code_artifact_ids": 1})
        ids = task.get("code_artifact_ids") or [] if task else []
        artifacts = await db.artifacts.find({"artifact_id": {"$in": ids}}, {"_id": 0}).to_list(20) if ids else []
        return {"artifacts": artifacts}

    @api_router.delete("/tasks/{task_id}/link-artifact/{artifact_id}")
    async def unlink_artifact(task_id: str, artifact_id: str, request: Request):
        await get_current_user(request)
        await db.project_tasks.update_one({"task_id": task_id}, {"$pull": {"code_artifact_ids": artifact_id}})
        return {"message": "Unlinked"}

    # ======================================================
    # TERMINAL / CONSOLE PANEL (#7)
    # ======================================================

    @api_router.get("/workspaces/{workspace_id}/console/history")
    async def get_console_history(workspace_id: str, request: Request, limit: int = 50):
        """Get recent execution history for workspace console"""
        user = await _authed_user(request, workspace_id)
        execs = await db.code_executions.find(
            {"executed_by": user["user_id"]}, {"_id": 0}
        ).sort("executed_at", -1).limit(limit).to_list(limit)
        return {"executions": execs}

    # ======================================================
    # VS CODE EXTENSION API (#8)
    # ======================================================

    @api_router.post("/external/review")
    async def external_code_review(request: Request):
        """API endpoint for VS Code extension — submit code for multi-model review"""
        user = await get_current_user(request)
        body = await request.json()
        code = body.get("code", "")
        language = body.get("language", "python")
        workspace_id = body.get("workspace_id", "")
        models = body.get("models", ["claude", "chatgpt"])

        if not code:
            raise HTTPException(400, "Code required")

        # Create review as artifact
        artifact_id = f"art_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        await db.artifacts.insert_one({
            "artifact_id": artifact_id, "workspace_id": workspace_id,
            "name": f"External Review — {language}", "content": code,
            "content_type": "code", "tags": ["external-review", language],
            "pinned": False, "version": 1, "attachments": [],
            "created_by": user["user_id"], "created_at": now, "updated_at": now,
        })

        return {
            "artifact_id": artifact_id,
            "review_url": f"/workspace/{workspace_id}?tab=artifacts&artifact={artifact_id}",
            "message": f"Code submitted for review by {', '.join(models)}",
        }


def _get_ext(language):
    ext_map = {"python": "py", "javascript": "js", "typescript": "ts", "go": "go", "rust": "rs",
               "c": "c", "cpp": "cpp", "java": "java", "ruby": "rb", "php": "php", "bash": "sh",
               "csharp": "cs", "kotlin": "kt", "swift": "swift", "r": "r", "sql": "sql"}
    return ext_map.get(language, "txt")
