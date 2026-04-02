"""Code Repository - Per-workspace multi-repo with file tree, versioning, and linking"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import UploadFile, File
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request
from nexus_utils import now_iso

logger = logging.getLogger(__name__)



class CreateFileRequest(BaseModel):
    path: str = Field(..., min_length=1)
    content: str = ""
    language: str = ""


class UpdateFileRequest(BaseModel):
    content: str = ""
    message: str = "Update file"


class CreateFolderRequest(BaseModel):
    path: str = Field(..., min_length=1)


class LinkRepoRequest(BaseModel):
    target_type: str  # "channel", "project", "task"
    target_id: str


def register_code_repo_routes(api_router, db, get_current_user):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import now_iso, require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user

    # ---- helpers ----
    def detect_language(path: str) -> str:
        ext_map = {
            "py": "python", "js": "javascript", "jsx": "javascript",
            "ts": "typescript", "tsx": "typescript", "html": "html",
            "css": "css", "json": "json", "md": "markdown", "xml": "xml",
            "yaml": "yaml", "yml": "yaml", "sh": "shell", "bash": "shell",
            "sql": "sql", "go": "go", "rs": "rust", "rb": "ruby",
            "java": "java", "kt": "kotlin", "swift": "swift", "c": "c",
            "cpp": "cpp", "h": "c", "hpp": "cpp", "cs": "csharp",
            "php": "php", "r": "r", "toml": "toml", "ini": "ini",
            "dockerfile": "dockerfile", "tf": "hcl", "graphql": "graphql",
            "svg": "xml", "txt": "plaintext", "env": "plaintext",
            "gitignore": "plaintext", "lock": "plaintext",
        }
        ext = path.rsplit(".", 1)[-1].lower() if "." in path else path.lower()
        return ext_map.get(ext, "plaintext")

    async def ensure_repo(workspace_id: str, repo_id: str = None) -> dict:
        """Get or create a repo. Adopts orphan files on first creation."""
        if repo_id:
            repo = await db.code_repos.find_one({"repo_id": repo_id, "workspace_id": workspace_id}, {"_id": 0})
            if not repo:
                raise HTTPException(404, "Repository not found")
            return repo
        repo = await db.code_repos.find_one({"workspace_id": workspace_id}, {"_id": 0})
        if not repo:
            new_id = f"repo_{uuid.uuid4().hex[:12]}"
            repo = {
                "repo_id": new_id, "workspace_id": workspace_id,
                "name": "Default", "description": "", "default_branch": "main",
                "created_at": now_iso(), "updated_at": now_iso(), "file_count": 0,
            }
            await db.code_repos.insert_one(repo)
            repo.pop("_id", None)
            # Adopt orphan files
            await db.repo_files.update_many(
                {"workspace_id": workspace_id, "$or": [{"repo_id": {"$exists": False}}, {"repo_id": ""}, {"repo_id": None}]},
                {"$set": {"repo_id": new_id}})
            await db.repo_commits.update_many(
                {"workspace_id": workspace_id, "$or": [{"repo_id": {"$exists": False}}, {"repo_id": ""}, {"repo_id": None}]},
                {"$set": {"repo_id": new_id}})
        return repo

    def repo_scope(repo_id: str, include_legacy: bool = False) -> dict:
        if not repo_id:
            return {}
        if include_legacy:
            return {
                "$or": [
                    {"repo_id": repo_id},
                    {"repo_id": {"$exists": False}},
                    {"repo_id": ""},
                    {"repo_id": None},
                ]
            }
        return {"repo_id": repo_id}

    async def resolve_github_token(user_id: str, body: dict, allow_anonymous: bool = False):
        pat = (body.get("token") or "").strip()
        if pat:
            return pat, "request"

        conn = await db.github_connections.find_one(
            {"user_id": user_id, "status": "active"},
            {"_id": 0}
        )
        if conn and conn.get("access_token"):
            try:
                from encryption import get_fernet; fernet = get_fernet()
                return fernet.decrypt(conn["access_token"].encode()).decode(), "connection"
            except Exception:
                if not allow_anonymous:
                    raise HTTPException(400, "GitHub token decryption failed. Please reconnect GitHub or provide a PAT.")

        pat_setting = await db.platform_settings.find_one({"key": "GITHUB_PAT"}, {"_id": 0})
        if pat_setting and pat_setting.get("value"):
            return pat_setting["value"], "platform"

        if allow_anonymous:
            return None, "anonymous"
        raise HTTPException(400, "No GitHub token. Save a Personal Access Token in Integration Settings, or provide one directly.")

    # ---- Multi-repo management ----

    @api_router.get("/workspaces/{workspace_id}/code-repos")
    async def list_repos(workspace_id: str, request: Request):
        """List all code repositories in a workspace."""
        await _authed_user(request, workspace_id)
        repos = await db.code_repos.find(
            {"workspace_id": workspace_id}, {"_id": 0}
        ).sort("created_at", 1).to_list(50)
        # Get file counts
        for r in repos:
            r["file_count"] = await db.repo_files.count_documents(
                {"repo_id": r["repo_id"], "is_deleted": {"$ne": True}})
        return {"repos": repos}

    @api_router.post("/workspaces/{workspace_id}/code-repos")
    async def create_repo(workspace_id: str, request: Request):
        """Create a new code repository in the workspace. W5: rate limit + max repos."""
        user = await _authed_user(request, workspace_id)
        # W5: Max 20 repos per workspace
        count = await db.code_repos.count_documents({"workspace_id": workspace_id})
        if count >= 20:
            raise HTTPException(429, "Maximum 20 repositories per workspace")
        body = await request.json()
        name = body.get("name", "").strip()
        if not name:
            raise HTTPException(400, "Repository name required")
        # W6: Input validation — alphanumeric, spaces, hyphens, underscores only. Max 100 chars.
        import re
        if len(name) > 100:
            raise HTTPException(400, "Repository name must be 100 characters or less")
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9 _\-\.]{0,99}$', name):
            raise HTTPException(400, "Repository name must start with a letter/number and contain only letters, numbers, spaces, hyphens, underscores, or dots")
        # Check duplicate name
        existing = await db.code_repos.find_one(
            {"workspace_id": workspace_id, "name": name}, {"_id": 0})
        if existing:
            raise HTTPException(409, f"Repository '{name}' already exists")
        repo = {
            "repo_id": f"repo_{uuid.uuid4().hex[:12]}",
            "workspace_id": workspace_id,
            "name": name,
            "description": body.get("description", ""),
            "default_branch": "main",
            "created_by": user["user_id"],
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "file_count": 0,
        }
        await db.code_repos.insert_one(repo)
        repo.pop("_id", None)
        return repo

    @api_router.put("/workspaces/{workspace_id}/code-repos/{repo_id}")
    async def update_repo(workspace_id: str, repo_id: str, request: Request):
        """Rename or update a repository."""
        await _authed_user(request, workspace_id)
        body = await request.json()
        updates = {}
        if "name" in body and body["name"].strip():
            updates["name"] = body["name"].strip()
        if "description" in body:
            updates["description"] = body["description"]
        if updates:
            updates["updated_at"] = now_iso()
            await db.code_repos.update_one({"repo_id": repo_id, "workspace_id": workspace_id}, {"$set": updates})
        result = await db.code_repos.find_one({"repo_id": repo_id, "workspace_id": workspace_id}, {"_id": 0})
        if not result:
            raise HTTPException(404, "Repository not found")
        return result

    @api_router.delete("/workspaces/{workspace_id}/code-repos/{repo_id}")
    async def delete_repo(workspace_id: str, repo_id: str, request: Request):
        """Delete a repository and all its files. W1: verify repo belongs to workspace."""
        await _authed_user(request, workspace_id)
        repo = await db.code_repos.find_one({"repo_id": repo_id, "workspace_id": workspace_id})
        if not repo:
            raise HTTPException(404, "Repository not found in this workspace")
        await db.repo_files.delete_many({"repo_id": repo_id, "workspace_id": workspace_id})
        await db.repo_commits.delete_many({"repo_id": repo_id, "workspace_id": workspace_id})
        await db.channel_repo_links.delete_many({"repo_id": repo_id})
        await db.code_repos.delete_one({"repo_id": repo_id, "workspace_id": workspace_id})
        return {"message": "Repository deleted"}

    # ---- Channel-repo linking (multiple repos per channel) ----

    @api_router.get("/channels/{channel_id}/repos")
    async def get_channel_repos(channel_id: str, request: Request):
        """Get repos linked to a channel. W2: verify channel access via workspace."""
        user = await get_current_user(request)
        channel = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0, "workspace_id": 1})
        if not channel:
            raise HTTPException(404, "Channel not found")
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, channel["workspace_id"])
        links = await db.channel_repo_links.find({"channel_id": channel_id}, {"_id": 0}).to_list(20)
        repo_ids = [link["repo_id"] for link in links]
        repos = []
        for rid in repo_ids:
            r = await db.code_repos.find_one({"repo_id": rid}, {"_id": 0})
            if r:
                repos.append(r)
        return {"repos": repos}

    @api_router.post("/channels/{channel_id}/repos")
    async def link_channel_repo(channel_id: str, request: Request):
        """Link a repo to a channel. W2: verify channel + repo in same workspace."""
        user = await get_current_user(request)
        body = await request.json()
        repo_id = body.get("repo_id", "")
        if not repo_id:
            raise HTTPException(400, "repo_id required")
        channel = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0, "workspace_id": 1})
        if not channel:
            raise HTTPException(404, "Channel not found")
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, channel["workspace_id"])
        # Verify repo belongs to same workspace
        repo = await db.code_repos.find_one({"repo_id": repo_id, "workspace_id": channel["workspace_id"]})
        if not repo:
            raise HTTPException(404, "Repository not found in this workspace")
        existing = await db.channel_repo_links.find_one({"channel_id": channel_id, "repo_id": repo_id})
        if existing:
            return {"message": "Already linked"}
        await db.channel_repo_links.insert_one({
            "link_id": f"crl_{uuid.uuid4().hex[:12]}",
            "channel_id": channel_id,
            "repo_id": repo_id,
            "linked_at": now_iso(),
            "linked_by": user["user_id"],
        })
        return {"message": "Repo linked to channel"}

    @api_router.delete("/channels/{channel_id}/repos/{repo_id}")
    async def unlink_channel_repo(channel_id: str, repo_id: str, request: Request):
        """Unlink a repo from a channel. W2: verify channel access."""
        user = await get_current_user(request)
        channel = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0, "workspace_id": 1})
        if not channel:
            raise HTTPException(404, "Channel not found")
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, channel["workspace_id"])
        await db.channel_repo_links.delete_one({"channel_id": channel_id, "repo_id": repo_id})
        return {"message": "Repo unlinked"}

    # ---- repo meta (backward compat — uses first/default repo) ----
    @api_router.get("/workspaces/{workspace_id}/code-repo")
    async def get_repo(workspace_id: str, request: Request):
        await _authed_user(request, workspace_id)
        explicit_repo_id = request.query_params.get("repo_id")
        repo = await ensure_repo(workspace_id, explicit_repo_id)
        count_query = {"workspace_id": workspace_id, "is_deleted": {"$ne": True}}
        count_query.update(repo_scope(repo.get("repo_id"), include_legacy=not explicit_repo_id))
        count = await db.repo_files.count_documents(count_query)
        repo["file_count"] = count
        return repo

    # ---- file tree ----
    @api_router.get("/workspaces/{workspace_id}/code-repo/tree")
    async def get_file_tree(workspace_id: str, request: Request, repo_id: str = None):
        await _authed_user(request, workspace_id)
        repo = await ensure_repo(workspace_id, repo_id)
        query = {"workspace_id": workspace_id, "is_deleted": {"$ne": True}}
        query.update(repo_scope(repo.get("repo_id"), include_legacy=not repo_id))
        files = await db.repo_files.find(
            query,
            {"_id": 0, "file_id": 1, "path": 1, "name": 1, "is_folder": 1, "language": 1, "size": 1, "updated_at": 1, "updated_by": 1, "repo_id": 1}
        ).sort("path", 1).to_list(500)
        return {"files": files, "repo_id": repo.get("repo_id")}

    # ---- create file ----
    @api_router.post("/workspaces/{workspace_id}/code-repo/files")
    async def create_file(workspace_id: str, data: CreateFileRequest, request: Request):
        user = await _authed_user(request, workspace_id)
        repo_id = getattr(data, 'repo_id', None) or request.query_params.get('repo_id')
        repo = await ensure_repo(workspace_id, repo_id)

        # Check for duplicate path within repo
        dup_query = {"workspace_id": workspace_id, "path": data.path, "is_deleted": {"$ne": True}}
        dup_query.update(repo_scope(repo.get("repo_id"), include_legacy=not repo_id))
        existing = await db.repo_files.find_one(dup_query)
        if existing:
            raise HTTPException(409, f"File already exists: {data.path}")

        name = data.path.rsplit("/", 1)[-1] if "/" in data.path else data.path
        language = data.language or detect_language(data.path)
        now = now_iso()
        file_id = f"rf_{uuid.uuid4().hex[:12]}"

        file_doc = {
            "file_id": file_id,
            "repo_id": repo.get("repo_id", ""),
            "workspace_id": workspace_id,
            "path": data.path,
            "name": name,
            "is_folder": False,
            "language": language,
            "content": data.content,
            "size": len(data.content.encode("utf-8")),
            "version": 1,
            "created_by": user["user_id"],
            "updated_by": user["user_id"],
            "created_at": now,
            "updated_at": now,
            "is_deleted": False,
        }
        await db.repo_files.insert_one(file_doc)

        # Create initial commit
        commit_id = f"rc_{uuid.uuid4().hex[:12]}"
        await db.repo_commits.insert_one({
            "commit_id": commit_id,
            "repo_id": repo.get("repo_id", ""),
            "workspace_id": workspace_id,
            "file_id": file_id,
            "file_path": data.path,
            "action": "create",
            "message": f"Create {data.path}",
            "author_id": user["user_id"],
            "author_name": user.get("name", "Unknown"),
            "content_after": data.content,
            "content_before": "",
            "version": 1,
            "created_at": now,
        })

        await db.code_repos.update_one(
            {"workspace_id": workspace_id, "repo_id": repo.get("repo_id")},
            {"$set": {"updated_at": now}}
        )

        return {k: v for k, v in file_doc.items() if k != "_id"}

    # ---- create folder ----
    @api_router.post("/workspaces/{workspace_id}/code-repo/folders")
    async def create_folder(workspace_id: str, data: CreateFolderRequest, request: Request):
        user = await _authed_user(request, workspace_id)
        repo_id = request.query_params.get("repo_id")
        repo = await ensure_repo(workspace_id, repo_id)

        existing = await db.repo_files.find_one(
            {
                "workspace_id": workspace_id,
                "path": data.path,
                "is_folder": True,
                "is_deleted": {"$ne": True},
                **repo_scope(repo.get("repo_id"), include_legacy=not repo_id),
            }
        )
        if existing:
            raise HTTPException(409, f"Folder already exists: {data.path}")

        name = data.path.rsplit("/", 1)[-1] if "/" in data.path else data.path
        now = now_iso()
        file_id = f"rf_{uuid.uuid4().hex[:12]}"

        folder_doc = {
            "file_id": file_id,
            "repo_id": repo.get("repo_id", ""),
            "workspace_id": workspace_id,
            "path": data.path,
            "name": name,
            "is_folder": True,
            "language": "",
            "content": "",
            "size": 0,
            "version": 0,
            "created_by": user["user_id"],
            "updated_by": user["user_id"],
            "created_at": now,
            "updated_at": now,
            "is_deleted": False,
        }
        await db.repo_files.insert_one(folder_doc)
        return {k: v for k, v in folder_doc.items() if k != "_id"}

    # ---- get file content ----
    @api_router.get("/workspaces/{workspace_id}/code-repo/files/{file_id}")
    async def get_file(workspace_id: str, file_id: str, request: Request):
        await _authed_user(request, workspace_id)
        f = await db.repo_files.find_one(
            {"file_id": file_id, "workspace_id": workspace_id, "is_deleted": {"$ne": True}},
            {"_id": 0}
        )
        if not f:
            raise HTTPException(404, "File not found")
        return f

    # ---- update file ----
    @api_router.put("/workspaces/{workspace_id}/code-repo/files/{file_id}")
    async def update_file(workspace_id: str, file_id: str, data: UpdateFileRequest, request: Request):
        user = await _authed_user(request, workspace_id)
        f = await db.repo_files.find_one(
            {"file_id": file_id, "workspace_id": workspace_id, "is_deleted": {"$ne": True}}
        )
        if not f:
            raise HTTPException(404, "File not found")

        old_content = f.get("content", "")
        new_version = f.get("version", 0) + 1
        now = now_iso()

        await db.repo_files.update_one(
            {"file_id": file_id},
            {"$set": {
                "content": data.content,
                "size": len(data.content.encode("utf-8")),
                "version": new_version,
                "updated_by": user["user_id"],
                "updated_at": now,
            }}
        )

        # Create commit record
        commit_id = f"rc_{uuid.uuid4().hex[:12]}"
        await db.repo_commits.insert_one({
            "commit_id": commit_id,
            "repo_id": f.get("repo_id", ""),
            "workspace_id": workspace_id,
            "file_id": file_id,
            "file_path": f["path"],
            "action": "update",
            "message": data.message,
            "author_id": user["user_id"],
            "author_name": user.get("name", "Unknown"),
            "content_before": old_content[:50000],
            "content_after": data.content[:50000],
            "version": new_version,
            "created_at": now,
        })

        await db.code_repos.update_one(
            {"workspace_id": workspace_id, "repo_id": f.get("repo_id")},
            {"$set": {"updated_at": now}}
        )

        return {
            "file_id": file_id,
            "version": new_version,
            "updated_at": now,
            "commit_id": commit_id,
        }

    # ---- delete file ----
    @api_router.delete("/workspaces/{workspace_id}/code-repo/files/{file_id}")
    async def delete_file(workspace_id: str, file_id: str, request: Request):
        user = await _authed_user(request, workspace_id)
        f = await db.repo_files.find_one(
            {"file_id": file_id, "workspace_id": workspace_id, "is_deleted": {"$ne": True}},
            {"_id": 0, "path": 1, "is_folder": 1}
        )
        if not f:
            raise HTTPException(404, "File not found")

        now = now_iso()

        if f.get("is_folder"):
            import re as _re
            escaped_path = _re.escape(f['path'])
            await db.repo_files.update_many(
                {"workspace_id": workspace_id, "path": {"$regex": f"^{escaped_path}/"}, "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "updated_at": now, "updated_by": user["user_id"]}}
            )

        await db.repo_files.update_one(
            {"file_id": file_id},
            {"$set": {"is_deleted": True, "updated_at": now, "updated_by": user["user_id"]}}
        )

        commit_id = f"rc_{uuid.uuid4().hex[:12]}"
        await db.repo_commits.insert_one({
            "commit_id": commit_id,
            "repo_id": f.get("repo_id", ""),
            "workspace_id": workspace_id,
            "file_id": file_id,
            "file_path": f["path"],
            "action": "delete",
            "message": f"Delete {f['path']}",
            "author_id": user["user_id"],
            "author_name": user.get("name", "Unknown"),
            "content_before": "",
            "content_after": "",
            "version": 0,
            "created_at": now,
        })

        return {"deleted": True}

    # ---- rename/move file ----
    @api_router.patch("/workspaces/{workspace_id}/code-repo/files/{file_id}")
    async def rename_file(workspace_id: str, file_id: str, request: Request):
        user = await _authed_user(request, workspace_id)
        body = await request.json()
        new_path = body.get("path", "")
        if not new_path:
            raise HTTPException(400, "New path required")

        f = await db.repo_files.find_one(
            {"file_id": file_id, "workspace_id": workspace_id, "is_deleted": {"$ne": True}}
        )
        if not f:
            raise HTTPException(404, "File not found")

        new_name = new_path.rsplit("/", 1)[-1] if "/" in new_path else new_path
        now = now_iso()

        await db.repo_files.update_one(
            {"file_id": file_id},
            {"$set": {"path": new_path, "name": new_name, "updated_at": now, "updated_by": user["user_id"]}}
        )

        await db.repo_commits.insert_one({
            "commit_id": f"rc_{uuid.uuid4().hex[:12]}",
            "repo_id": f.get("repo_id", ""),
            "workspace_id": workspace_id,
            "file_id": file_id,
            "file_path": new_path,
            "action": "rename",
            "message": f"Rename {f['path']} → {new_path}",
            "author_id": user["user_id"],
            "author_name": user.get("name", "Unknown"),
            "content_before": f["path"],
            "content_after": new_path,
            "version": f.get("version", 0),
            "created_at": now,
        })

        return {"file_id": file_id, "path": new_path, "name": new_name}

    # ---- version history ----
    @api_router.get("/workspaces/{workspace_id}/code-repo/history")
    async def get_history(workspace_id: str, request: Request, file_id: Optional[str] = None, limit: int = 50):
        await _authed_user(request, workspace_id)
        query = {"workspace_id": workspace_id}
        if file_id:
            query["file_id"] = file_id
        commits = await db.repo_commits.find(
            query,
            {"_id": 0, "content_before": 0, "content_after": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        return {"commits": commits}

    # ---- get specific commit (with diff) ----
    @api_router.get("/workspaces/{workspace_id}/code-repo/commits/{commit_id}")
    async def get_commit(workspace_id: str, commit_id: str, request: Request):
        await _authed_user(request, workspace_id)
        commit = await db.repo_commits.find_one(
            {"commit_id": commit_id, "workspace_id": workspace_id},
            {"_id": 0}
        )
        if not commit:
            raise HTTPException(404, "Commit not found")
        return commit

    # ---- link repo to channel/project/task ----
    @api_router.post("/workspaces/{workspace_id}/code-repo/links")
    async def create_link(workspace_id: str, data: LinkRepoRequest, request: Request):
        user = await _authed_user(request, workspace_id)
        await ensure_repo(workspace_id, request.query_params.get("repo_id"))

        existing = await db.repo_links.find_one({
            "workspace_id": workspace_id,
            "target_type": data.target_type,
            "target_id": data.target_id,
        })
        if existing:
            raise HTTPException(409, "Link already exists")

        link_id = f"rl_{uuid.uuid4().hex[:12]}"
        now = now_iso()

        # Resolve target name
        target_name = ""
        if data.target_type == "channel":
            ch = await db.channels.find_one({"channel_id": data.target_id}, {"_id": 0, "name": 1})
            target_name = ch.get("name", "") if ch else ""
        elif data.target_type == "project":
            p = await db.projects.find_one({"project_id": data.target_id}, {"_id": 0, "name": 1})
            target_name = p.get("name", "") if p else ""
        elif data.target_type == "task":
            t = await db.project_tasks.find_one({"task_id": data.target_id}, {"_id": 0, "title": 1})
            target_name = t.get("title", "") if t else ""

        link = {
            "link_id": link_id,
            "workspace_id": workspace_id,
            "target_type": data.target_type,
            "target_id": data.target_id,
            "target_name": target_name,
            "created_by": user["user_id"],
            "created_at": now,
        }
        await db.repo_links.insert_one(link)
        return {k: v for k, v in link.items() if k != "_id"}

    @api_router.get("/workspaces/{workspace_id}/code-repo/links")
    async def get_links(workspace_id: str, request: Request):
        await _authed_user(request, workspace_id)
        links = await db.repo_links.find(
            {"workspace_id": workspace_id},
            {"_id": 0}
        ).to_list(100)
        return {"links": links}

    @api_router.delete("/workspaces/{workspace_id}/code-repo/links/{link_id}")
    async def delete_link(workspace_id: str, link_id: str, request: Request):
        await _authed_user(request, workspace_id)
        result = await db.repo_links.delete_one({"link_id": link_id, "workspace_id": workspace_id})
        if result.deleted_count == 0:
            raise HTTPException(404, "Link not found")
        return {"deleted": True}

    # ---- AI agent file update (used internally by collaboration engine) ----
    @api_router.post("/workspaces/{workspace_id}/code-repo/ai-update")
    async def ai_update_file(workspace_id: str, request: Request):
        """AI agents can create/update files in the repo during collaboration"""
        await _authed_user(request, workspace_id)
        body = await request.json()
        file_path = body.get("path", "")
        content = body.get("content", "")
        agent_name = body.get("agent_name", "AI Agent")
        message = body.get("message", f"Updated by {agent_name}")

        if not file_path:
            raise HTTPException(400, "path required")

        repo_id = request.query_params.get("repo_id")
        repo = await ensure_repo(workspace_id, repo_id)
        now = now_iso()

        existing_query = {"workspace_id": workspace_id, "path": file_path, "is_deleted": {"$ne": True}}
        existing_query.update(repo_scope(repo.get("repo_id"), include_legacy=not repo_id))
        existing = await db.repo_files.find_one(existing_query)

        if existing:
            old_content = existing.get("content", "")
            new_version = existing.get("version", 0) + 1
            await db.repo_files.update_one(
                {"file_id": existing["file_id"]},
                {"$set": {
                    "content": content,
                    "size": len(content.encode("utf-8")),
                    "version": new_version,
                    "updated_by": f"ai:{agent_name}",
                    "updated_at": now,
                }}
            )
            file_id = existing["file_id"]
            action = "update"
        else:
            file_id = f"rf_{uuid.uuid4().hex[:12]}"
            name = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path
            language = detect_language(file_path)
            old_content = ""
            new_version = 1
            action = "create"
            await db.repo_files.insert_one({
                "file_id": file_id,
                "repo_id": repo.get("repo_id", ""),
                "workspace_id": workspace_id,
                "path": file_path,
                "name": name,
                "is_folder": False,
                "language": language,
                "content": content,
                "size": len(content.encode("utf-8")),
                "version": 1,
                "created_by": f"ai:{agent_name}",
                "updated_by": f"ai:{agent_name}",
                "created_at": now,
                "updated_at": now,
                "is_deleted": False,
            })

        commit_id = f"rc_{uuid.uuid4().hex[:12]}"
        await db.repo_commits.insert_one({
            "commit_id": commit_id,
            "repo_id": existing.get("repo_id", repo.get("repo_id", "")) if existing else repo.get("repo_id", ""),
            "workspace_id": workspace_id,
            "file_id": file_id,
            "file_path": file_path,
            "action": action,
            "message": message,
            "author_id": f"ai:{agent_name}",
            "author_name": agent_name,
            "content_before": old_content[:50000],
            "content_after": content[:50000],
            "version": new_version,
            "created_at": now,
        })

        await db.code_repos.update_one(
            {"workspace_id": workspace_id, "repo_id": repo.get("repo_id")},
            {"$set": {"updated_at": now}}
        )

        return {
            "file_id": file_id,
            "path": file_path,
            "action": action,
            "version": new_version,
            "commit_id": commit_id,
        }


    # ======================================================
    # BRANCH SUPPORT
    # ======================================================

    @api_router.get("/workspaces/{workspace_id}/code-repo/branches")
    async def list_branches(workspace_id: str, request: Request):
        await _authed_user(request, workspace_id)
        await ensure_repo(workspace_id, request.query_params.get("repo_id"))
        branches = await db.repo_branches.find(
            {"workspace_id": workspace_id},
            {"_id": 0}
        ).sort("created_at", 1).to_list(50)
        # Ensure "main" always exists
        if not any(b["name"] == "main" for b in branches):
            main_branch = {
                "branch_id": f"rb_{uuid.uuid4().hex[:12]}",
                "workspace_id": workspace_id,
                "name": "main",
                "is_default": True,
                "created_by": "system",
                "created_at": now_iso(),
            }
            await db.repo_branches.insert_one(main_branch)
            main_branch.pop("_id", None)
            branches.insert(0, main_branch)
        return {"branches": branches}

    @api_router.post("/workspaces/{workspace_id}/code-repo/branches")
    async def create_branch(workspace_id: str, request: Request):
        user = await _authed_user(request, workspace_id)
        body = await request.json()
        name = body.get("name", "").strip()
        from_branch = body.get("from_branch", "main")
        if not name:
            raise HTTPException(400, "Branch name required")
        existing = await db.repo_branches.find_one(
            {"workspace_id": workspace_id, "name": name}
        )
        if existing:
            raise HTTPException(409, f"Branch '{name}' already exists")
        branch_id = f"rb_{uuid.uuid4().hex[:12]}"
        branch = {
            "branch_id": branch_id,
            "workspace_id": workspace_id,
            "name": name,
            "from_branch": from_branch,
            "is_default": False,
            "created_by": user["user_id"],
            "created_at": now_iso(),
        }
        await db.repo_branches.insert_one(branch)
        # Copy files from source branch to new branch
        source_files = await db.repo_files.find(
            {"workspace_id": workspace_id, "branch": from_branch, "is_deleted": {"$ne": True}},
            {"_id": 0}
        ).to_list(500)
        if not source_files:
            # Fallback: copy files without branch field (legacy main)
            source_files = await db.repo_files.find(
                {"workspace_id": workspace_id, "is_deleted": {"$ne": True}, "branch": {"$exists": False}},
                {"_id": 0}
            ).to_list(500)
        for sf in source_files:
            new_file = {**sf}
            new_file["file_id"] = f"rf_{uuid.uuid4().hex[:12]}"
            new_file["branch"] = name
            new_file.pop("_id", None)
            await db.repo_files.insert_one(new_file)
        return {k: v for k, v in branch.items() if k != "_id"}

    @api_router.delete("/workspaces/{workspace_id}/code-repo/branches/{branch_name}")
    async def delete_branch(workspace_id: str, branch_name: str, request: Request):
        await _authed_user(request, workspace_id)
        if branch_name == "main":
            raise HTTPException(400, "Cannot delete main branch")
        await db.repo_branches.delete_one({"workspace_id": workspace_id, "name": branch_name})
        await db.repo_files.delete_many({"workspace_id": workspace_id, "branch": branch_name})
        return {"deleted": True, "branch": branch_name}

    @api_router.post("/workspaces/{workspace_id}/code-repo/branches/{branch_name}/merge")
    async def merge_branch(workspace_id: str, branch_name: str, request: Request):
        """Merge a branch into main"""
        user = await _authed_user(request, workspace_id)
        body = await request.json()
        target = body.get("target", "main")
        branch_files = await db.repo_files.find(
            {"workspace_id": workspace_id, "branch": branch_name, "is_deleted": {"$ne": True}},
            {"_id": 0}
        ).to_list(500)
        now = now_iso()
        merged_count = 0
        for bf in branch_files:
            # Find target file by path
            target_file = await db.repo_files.find_one(
                {"workspace_id": workspace_id, "path": bf["path"],
                 "$or": [{"branch": target}, {"branch": {"$exists": False}}],
                 "is_deleted": {"$ne": True}}
            )
            if target_file:
                new_ver = target_file.get("version", 0) + 1
                await db.repo_files.update_one(
                    {"file_id": target_file["file_id"]},
                    {"$set": {"content": bf["content"], "size": bf.get("size", 0),
                              "version": new_ver, "updated_by": user["user_id"], "updated_at": now}}
                )
            else:
                new_file = {**bf}
                new_file["file_id"] = f"rf_{uuid.uuid4().hex[:12]}"
                new_file["branch"] = target
                new_file.pop("_id", None)
                await db.repo_files.insert_one(new_file)
            merged_count += 1
            await db.repo_commits.insert_one({
                "commit_id": f"rc_{uuid.uuid4().hex[:12]}",
                "workspace_id": workspace_id,
                "file_id": bf["file_id"],
                "file_path": bf["path"],
                "action": "merge",
                "message": f"Merge {branch_name} → {target}: {bf['path']}",
                "author_id": user["user_id"],
                "author_name": user.get("name", "Unknown"),
                "content_before": "",
                "content_after": bf.get("content", "")[:50000],
                "version": 0,
                "created_at": now,
            })
        return {"merged": True, "files_merged": merged_count, "source": branch_name, "target": target}

    # ======================================================
    # GIT PUSH/PULL (Export/Import to GitHub)
    # ======================================================

    @api_router.post("/workspaces/{workspace_id}/code-repo/git-export")
    async def git_export(workspace_id: str, request: Request):
        """Export repo as a downloadable archive (JSON bundle)"""
        await _authed_user(request, workspace_id)
        explicit_repo_id = request.query_params.get("repo_id")
        repo = await ensure_repo(workspace_id, explicit_repo_id)
        file_query = {"workspace_id": workspace_id, "is_deleted": {"$ne": True}}
        file_query.update(repo_scope(repo.get("repo_id"), include_legacy=not explicit_repo_id))
        files = await db.repo_files.find(
            file_query,
            {"_id": 0, "file_id": 1, "path": 1, "content": 1, "language": 1, "version": 1}
        ).to_list(500)
        commits = await db.repo_commits.find(
            {"workspace_id": workspace_id, "repo_id": repo.get("repo_id", "")},
            {"_id": 0, "commit_id": 1, "file_path": 1, "action": 1, "message": 1, "author_name": 1, "created_at": 1}
        ).sort("created_at", -1).limit(100).to_list(100)
        return {
            "workspace_id": workspace_id,
            "repo_id": repo.get("repo_id"),
            "repo_name": repo.get("name"),
            "exported_at": now_iso(),
            "file_count": len(files),
            "files": files,
            "recent_commits": commits,
        }

    @api_router.post("/workspaces/{workspace_id}/code-repo/git-import")
    async def git_import(workspace_id: str, request: Request):
        """Import files from a JSON bundle into the repo"""
        user = await _authed_user(request, workspace_id)
        body = await request.json()
        files = body.get("files") or []
        if not files:
            raise HTTPException(400, "No files to import")
        explicit_repo_id = request.query_params.get("repo_id")
        repo = await ensure_repo(workspace_id, explicit_repo_id)
        now = now_iso()
        imported = 0
        for f in files:
            path = f.get("path", "")
            content = f.get("content", "")
            if not path:
                continue
            existing_query = {"workspace_id": workspace_id, "path": path, "is_deleted": {"$ne": True}}
            existing_query.update(repo_scope(repo.get("repo_id"), include_legacy=not explicit_repo_id))
            existing = await db.repo_files.find_one(existing_query)
            if existing:
                await db.repo_files.update_one(
                    {"file_id": existing["file_id"]},
                    {"$set": {"content": content, "size": len(content.encode("utf-8")),
                              "version": existing.get("version", 0) + 1,
                              "updated_by": user["user_id"], "updated_at": now}}
                )
            else:
                name = path.rsplit("/", 1)[-1] if "/" in path else path
                await db.repo_files.insert_one({
                    "file_id": f"rf_{uuid.uuid4().hex[:12]}",
                    "repo_id": repo.get("repo_id", ""),
                    "workspace_id": workspace_id,
                    "path": path, "name": name, "is_folder": False,
                    "language": detect_language(path),
                    "content": content, "size": len(content.encode("utf-8")),
                    "version": 1, "created_by": user["user_id"],
                    "updated_by": user["user_id"],
                    "created_at": now, "updated_at": now, "is_deleted": False,
                })
            imported += 1
        return {"imported": imported, "workspace_id": workspace_id}

    @api_router.post("/workspaces/{workspace_id}/code-repo/github-push")
    async def github_push(workspace_id: str, request: Request):
        """Push repo files to a GitHub repository via API"""
        user = await _authed_user(request, workspace_id)
        body = await request.json()
        repo_full_name = body.get("repo", "")  # e.g., "owner/repo"
        branch = body.get("branch", "main")
        commit_message = body.get("message", "Push from Nexus")
        if not repo_full_name:
            raise HTTPException(400, "GitHub repo name required (owner/repo)")
        token, _token_source = await resolve_github_token(user["user_id"], body)
        explicit_repo_id = request.query_params.get("repo_id")
        repo = await ensure_repo(workspace_id, explicit_repo_id)
        workspace = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "org_id": 1})
        file_query = {"workspace_id": workspace_id, "is_deleted": {"$ne": True}, "is_folder": False}
        file_query.update(repo_scope(repo.get("repo_id"), include_legacy=not explicit_repo_id))
        files = await db.repo_files.find(
            file_query,
            {"_id": 0, "path": 1, "content": 1}
        ).to_list(500)
        if not files:
            raise HTTPException(400, "No files to push")
        budget_check = {}
        try:
            from managed_keys import check_usage_budget, estimate_integration_cost_usd, emit_budget_alert
            budget_check = await check_usage_budget("github", estimate_integration_cost_usd("github", max(len(files), 1)), workspace_id=workspace_id, org_id=(workspace or {}).get("org_id"), user_id=user["user_id"])
            if budget_check.get("blocked"):
                await emit_budget_alert("github", budget_check.get("scope_type") or "platform", budget_check.get("scope_id") or "platform", "blocked", budget_check.get("projected_spend_usd", 0), budget_check.get("hard_cap_usd"), user_id=user["user_id"], workspace_id=workspace_id, org_id=(workspace or {}).get("org_id"), message="Nexus AI budget reached for GitHub integration.")
                raise HTTPException(429, "Workspace/organization/platform Nexus AI budget reached for GitHub integration")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Budget check failed: {e}")
            budget_check = {}
        # Push each file via GitHub Contents API
        import httpx
        from urllib.parse import quote
        pushed = 0
        errors = []
        async with httpx.AsyncClient() as client:
            for f in files:
                import base64
                content_b64 = base64.b64encode(f["content"].encode()).decode()
                encoded_path = quote(f["path"], safe="/")
                # Check if file exists (to get sha for update)
                existing_resp = await client.get(
                    f"https://api.github.com/repos/{repo_full_name}/contents/{encoded_path}?ref={branch}",
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
                )
                payload = {
                    "message": f"{commit_message}: {f['path']}",
                    "content": content_b64,
                    "branch": branch,
                }
                if existing_resp.status_code == 200:
                    payload["sha"] = existing_resp.json().get("sha", "")
                resp = await client.put(
                    f"https://api.github.com/repos/{repo_full_name}/contents/{encoded_path}",
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                    json=payload
                )
                if resp.status_code in (200, 201):
                    pushed += 1
                else:
                    try:
                        detail = resp.json().get("message", "")
                    except Exception:
                        detail = resp.text[:120]
                    errors.append(f"{f['path']}: {resp.status_code} {detail}".strip())
        try:
            from managed_keys import record_usage_event, estimate_integration_cost_usd, emit_budget_alert
            cost = estimate_integration_cost_usd("github", max(pushed, 1))
            await record_usage_event("github", cost, user_id=user["user_id"], workspace_id=workspace_id, org_id=(workspace or {}).get("org_id"), usage_type="integration", key_source=_token_source, call_count=max(pushed, 1), metadata={"action": "github_push", "repo": repo_full_name, "branch": branch, "repo_id": repo.get("repo_id")})
            if budget_check.get("warn"):
                await emit_budget_alert("github", budget_check.get("scope_type") or "platform", budget_check.get("scope_id") or "platform", "warning", budget_check.get("projected_spend_usd", cost), budget_check.get("warn_threshold_usd"), user_id=user["user_id"], workspace_id=workspace_id, org_id=(workspace or {}).get("org_id"), message="Nexus AI budget warning for GitHub integration.")
        except Exception as e:
            logger.error(f"Budget usage tracking failed: {e}")
            budget_check = budget_check or {}
        return {"pushed": pushed, "errors": errors, "repo": repo_full_name, "branch": branch, "repo_id": repo.get("repo_id")}

    @api_router.post("/workspaces/{workspace_id}/code-repo/github-pull")
    async def github_pull(workspace_id: str, request: Request):
        """Pull files from a GitHub repository into the Nexus code repo"""
        user = await _authed_user(request, workspace_id)
        body = await request.json()
        repo_full_name = body.get("repo", "")
        branch = body.get("branch", "main")
        path_prefix = body.get("path", "")
        if not repo_full_name:
            raise HTTPException(400, "GitHub repo name required (owner/repo)")
        token, _token_source = await resolve_github_token(user["user_id"], body, allow_anonymous=True)
        explicit_repo_id = request.query_params.get("repo_id")
        repo = await ensure_repo(workspace_id, explicit_repo_id)
        workspace = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "org_id": 1})
        budget_check = {}
        try:
            from managed_keys import check_usage_budget, estimate_integration_cost_usd, emit_budget_alert
            budget_check = await check_usage_budget("github", estimate_integration_cost_usd("github", 1), workspace_id=workspace_id, org_id=(workspace or {}).get("org_id"), user_id=user["user_id"])
            if budget_check.get("blocked"):
                await emit_budget_alert("github", budget_check.get("scope_type") or "platform", budget_check.get("scope_id") or "platform", "blocked", budget_check.get("projected_spend_usd", 0), budget_check.get("hard_cap_usd"), user_id=user["user_id"], workspace_id=workspace_id, org_id=(workspace or {}).get("org_id"), message="Nexus AI budget reached for GitHub integration.")
                raise HTTPException(429, "Workspace/organization/platform Nexus AI budget reached for GitHub integration")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Budget check failed: {e}")
            budget_check = {}
        import httpx
        from urllib.parse import quote
        pulled = 0
        now = now_iso()

        async with httpx.AsyncClient() as client:
            async def github_get(url: str, accept: str = "application/vnd.github+json"):
                headers = {"Accept": accept}
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                resp = await client.get(url, headers=headers)
                if token and resp.status_code in (401, 403):
                    resp = await client.get(url, headers={"Accept": accept})
                return resp

            ref_resp = await github_get(f"https://api.github.com/repos/{repo_full_name}/git/ref/heads/{quote(branch, safe='')}")
            if ref_resp.status_code != 200:
                raise HTTPException(400, f"Failed to fetch branch '{branch}': {ref_resp.status_code}")
            commit_sha = ((ref_resp.json().get("object") or {}).get("sha"))
            if not commit_sha:
                raise HTTPException(400, f"Failed to resolve branch '{branch}' commit")

            commit_resp = await github_get(f"https://api.github.com/repos/{repo_full_name}/git/commits/{commit_sha}")
            if commit_resp.status_code != 200:
                raise HTTPException(400, f"Failed to fetch commit for '{branch}': {commit_resp.status_code}")
            tree_sha = ((commit_resp.json().get("tree") or {}).get("sha"))
            if not tree_sha:
                raise HTTPException(400, f"Failed to resolve tree for '{branch}'")

            tree_resp = await github_get(f"https://api.github.com/repos/{repo_full_name}/git/trees/{tree_sha}?recursive=1")
            if tree_resp.status_code != 200:
                raise HTTPException(400, f"Failed to fetch repo tree: {tree_resp.status_code}")

            tree = tree_resp.json().get("tree") or []
            for item in tree:
                if item["type"] != "blob":
                    continue
                file_path = item["path"]
                if path_prefix and not file_path.startswith(path_prefix):
                    continue
                # Get file content
                file_resp = await github_get(
                    f"https://api.github.com/repos/{repo_full_name}/contents/{quote(file_path, safe='/')}?ref={quote(branch, safe='')}",
                    accept="application/vnd.github.raw"
                )
                if file_resp.status_code != 200:
                    continue
                content = file_resp.text
                name = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path
                existing_query = {"workspace_id": workspace_id, "path": file_path, "is_deleted": {"$ne": True}}
                existing_query.update(repo_scope(repo.get("repo_id"), include_legacy=not explicit_repo_id))
                existing = await db.repo_files.find_one(existing_query)
                if existing:
                    await db.repo_files.update_one(
                        {"file_id": existing["file_id"]},
                        {"$set": {"content": content, "size": len(content.encode("utf-8")),
                                  "version": existing.get("version", 0) + 1,
                                  "updated_by": user["user_id"], "updated_at": now}}
                    )
                else:
                    await db.repo_files.insert_one({
                        "file_id": f"rf_{uuid.uuid4().hex[:12]}",
                        "repo_id": repo.get("repo_id", ""),
                        "workspace_id": workspace_id,
                        "path": file_path, "name": name, "is_folder": False,
                        "language": detect_language(file_path),
                        "content": content, "size": len(content.encode("utf-8")),
                        "version": 1, "created_by": user["user_id"],
                        "updated_by": user["user_id"],
                        "created_at": now, "updated_at": now, "is_deleted": False,
                    })
                pulled += 1
        try:
            from managed_keys import record_usage_event, estimate_integration_cost_usd, emit_budget_alert
            cost = estimate_integration_cost_usd("github", max(pulled, 1))
            await record_usage_event("github", cost, user_id=user["user_id"], workspace_id=workspace_id, org_id=(workspace or {}).get("org_id"), usage_type="integration", key_source=_token_source, call_count=max(pulled, 1), metadata={"action": "github_pull", "repo": repo_full_name, "branch": branch, "repo_id": repo.get("repo_id")})
            if budget_check.get("warn"):
                await emit_budget_alert("github", budget_check.get("scope_type") or "platform", budget_check.get("scope_id") or "platform", "warning", budget_check.get("projected_spend_usd", cost), budget_check.get("warn_threshold_usd"), user_id=user["user_id"], workspace_id=workspace_id, org_id=(workspace or {}).get("org_id"), message="Nexus AI budget warning for GitHub integration.")
        except Exception as e:
            logger.error(f"Budget usage tracking failed: {e}")
            budget_check = budget_check or {}
        return {"pulled": pulled, "repo": repo_full_name, "branch": branch, "repo_id": repo.get("repo_id")}


    # ======================================================
    # DOWNLOAD REPO AS ZIP
    # ======================================================

    @api_router.get("/workspaces/{workspace_id}/code-repo/download")
    async def download_repo_zip(workspace_id: str, request: Request):
        """Download entire repo as a ZIP file"""
        await _authed_user(request, workspace_id)
        import io
        import zipfile
        from fastapi.responses import StreamingResponse
        explicit_repo_id = request.query_params.get("repo_id")
        repo = await ensure_repo(workspace_id, explicit_repo_id)

        file_query = {"workspace_id": workspace_id, "is_deleted": {"$ne": True}, "is_folder": False}
        file_query.update(repo_scope(repo.get("repo_id"), include_legacy=not explicit_repo_id))
        files = await db.repo_files.find(
            file_query,
            {"_id": 0, "path": 1, "content": 1}
        ).to_list(500)

        if not files:
            raise HTTPException(404, "No files in repository")

        # Create ZIP in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                zf.writestr(f["path"], f.get("content", ""))

        zip_buffer.seek(0)

        # Get workspace name for filename
        ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "name": 1})
        from nexus_utils import sanitize_filename
        ws_name = sanitize_filename((ws.get("name", "repo") if ws else "repo"))
        repo_name = sanitize_filename(repo.get("name") or "repo")

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{ws_name}_{repo_name}.zip"'}
        )

    @api_router.post("/workspaces/{workspace_id}/code-repo/import-zip")
    async def import_repo_from_zip(workspace_id: str, request: Request, file: UploadFile = File(...)):
        """Import a repository from a ZIP file. Creates/updates files in the workspace repo."""
        user = await _authed_user(request, workspace_id)
        explicit_repo_id = request.query_params.get("repo_id")
        repo = await ensure_repo(workspace_id, explicit_repo_id)
        
        content = await file.read()
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(400, "ZIP file too large. Maximum: 50MB")
        
        import zipfile
        import io
        
        try:
            zf = zipfile.ZipFile(io.BytesIO(content))
        except zipfile.BadZipFile:
            raise HTTPException(400, "Invalid ZIP file")
        
        imported = 0
        skipped = 0
        errors = []
        now = datetime.now(timezone.utc).isoformat()
        
        # Skip common non-source directories
        SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".DS_Store", "venv", ".env", "dist", "build"}
        # Max single file size: 2MB
        MAX_FILE_SIZE = 2 * 1024 * 1024
        
        for zip_path in zf.namelist():
            # Skip directories
            if zip_path.endswith("/"):
                continue
            
            # Skip hidden/system files and large directories
            parts = zip_path.split("/")
            if any(p in SKIP_DIRS or p.startswith(".") for p in parts):
                skipped += 1
                continue
            
            # Strip top-level directory if all files share one (common in GitHub ZIPs)
            if len(parts) > 1:
                # Check if all entries share the same root
                all_roots = set(n.split("/")[0] for n in zf.namelist() if "/" in n)
                if len(all_roots) == 1:
                    clean_path = "/".join(parts[1:])
                else:
                    clean_path = zip_path
            else:
                clean_path = zip_path
            
            if not clean_path:
                continue
            
            try:
                file_data = zf.read(zip_path)
                if len(file_data) > MAX_FILE_SIZE:
                    skipped += 1
                    continue
                
                # Try to decode as text
                try:
                    file_content = file_data.decode("utf-8")
                except UnicodeDecodeError:
                    # Binary file — store as base64 placeholder
                    file_content = f"[Binary file: {clean_path} ({len(file_data)} bytes)]"
                
                # Check if file already exists
                ext = clean_path.split(".")[-1] if "." in clean_path else ""
                existing_query = {"workspace_id": workspace_id, "path": clean_path, "is_deleted": {"$ne": True}}
                existing_query.update(repo_scope(repo.get("repo_id"), include_legacy=not explicit_repo_id))
                existing = await db.repo_files.find_one(
                    existing_query,
                    {"_id": 0, "file_id": 1}
                )
                
                if existing:
                    # Update existing file
                    await db.repo_files.update_one(
                        {"file_id": existing["file_id"]},
                        {"$set": {"content": file_content, "updated_at": now, "updated_by": f"import:{user['user_id']}"}}
                    )
                else:
                    # Create new file
                    file_id = f"rf_{uuid.uuid4().hex[:12]}"
                    await db.repo_files.insert_one({
                        "file_id": file_id,
                        "repo_id": repo.get("repo_id", ""),
                        "workspace_id": workspace_id,
                        "path": clean_path,
                        "name": clean_path.split("/")[-1],
                        "extension": ext,
                        "content": file_content,
                        "language": detect_language(clean_path),
                        "is_folder": False,
                        "size": len(file_content.encode("utf-8")),
                        "version": 1,
                        "branch": "main",
                        "created_by": f"import:{user['user_id']}",
                        "updated_by": f"import:{user['user_id']}",
                        "is_deleted": False,
                        "created_at": now,
                        "updated_at": now,
                    })
                imported += 1
            except Exception as e:
                errors.append(f"{clean_path}: {str(e)[:50]}")
                if len(errors) > 20:
                    break
        
        # Update repo metadata
        await db.code_repos.update_one(
            {"workspace_id": workspace_id, "repo_id": repo.get("repo_id")},
            {"$set": {"updated_at": now, "last_import": {"filename": file.filename, "files_imported": imported, "at": now}}}
        )
        
        return {
            "imported": imported,
            "skipped": skipped,
            "errors": errors[:10],
            "total_in_zip": len([n for n in zf.namelist() if not n.endswith("/")]),
            "filename": file.filename,
        }

    def _detect_language(ext):
        lang_map = {
            "py": "python", "js": "javascript", "jsx": "javascript", "ts": "typescript", "tsx": "typescript",
            "html": "html", "css": "css", "json": "json", "md": "markdown", "yaml": "yaml", "yml": "yaml",
            "java": "java", "cpp": "cpp", "c": "c", "go": "go", "rs": "rust", "rb": "ruby", "php": "php",
            "swift": "swift", "kt": "kotlin", "sql": "sql", "sh": "shell", "bash": "shell", "xml": "xml",
        }
        return lang_map.get(ext.lower(), "text")
