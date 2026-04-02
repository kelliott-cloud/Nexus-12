"""Mail rules — if/then automation conditions for email triage."""
import uuid
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from typing import List, Optional
from nexus_utils import now_iso
from nexus_config import FEATURE_FLAGS


class RuleCondition(BaseModel):
    field: str = Field(..., description="sender, subject, labels, folder, has_attachment")
    operator: str = Field(..., description="contains, equals, starts_with, ends_with, regex, not_contains")
    value: str


class RuleAction(BaseModel):
    action_type: str = Field(..., description="archive, label, move, flag, mark_read, priority, category")
    payload: dict = Field(default_factory=dict)


class RuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    connection_id: Optional[str] = None
    conditions: List[RuleCondition] = Field(default_factory=list)
    actions: List[RuleAction] = Field(default_factory=list)
    match_mode: str = Field(default="all", description="all (AND) or any (OR)")
    enabled: bool = True


def register_mail_rule_routes(api_router, db, get_current_user):
    def _check_flag():
        if not FEATURE_FLAGS.get("smart_inbox", {}).get("enabled", False):
            raise HTTPException(501, FEATURE_FLAGS.get("smart_inbox", {}).get("reason", "Smart Inbox not enabled"))

    async def _authed(request, ws_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, ws_id)
        return user

    @api_router.get("/workspaces/{ws_id}/mail/rules")
    async def list_rules(ws_id: str, request: Request):
        _check_flag()
        await _authed(request, ws_id)
        rules = await db.mail_rules.find({"workspace_id": ws_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
        return {"rules": rules}

    @api_router.post("/workspaces/{ws_id}/mail/rules")
    async def create_rule(ws_id: str, data: RuleCreate, request: Request):
        _check_flag()
        user = await _authed(request, ws_id)
        rule_id = f"mrule_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        rule = {
            "rule_id": rule_id, "workspace_id": ws_id,
            "name": data.name, "connection_id": data.connection_id,
            "conditions": [c.dict() for c in data.conditions],
            "actions": [a.dict() for a in data.actions],
            "match_mode": data.match_mode, "enabled": data.enabled,
            "execution_count": 0,
            "created_by": user["user_id"], "created_at": now,
        }
        await db.mail_rules.insert_one(rule)
        rule.pop("_id", None)
        return rule

    @api_router.put("/workspaces/{ws_id}/mail/rules/{rule_id}")
    async def update_rule(ws_id: str, rule_id: str, request: Request):
        _check_flag()
        await _authed(request, ws_id)
        body = await request.json()
        updates = {}
        for field in ["name", "conditions", "actions", "match_mode", "enabled"]:
            if field in body:
                updates[field] = body[field]
        if not updates:
            raise HTTPException(400, "No fields to update")
        updates["updated_at"] = now_iso()
        result = await db.mail_rules.update_one(
            {"rule_id": rule_id, "workspace_id": ws_id}, {"$set": updates})
        if result.matched_count == 0:
            raise HTTPException(404, "Rule not found")
        return {"status": "updated"}

    @api_router.delete("/workspaces/{ws_id}/mail/rules/{rule_id}")
    async def delete_rule(ws_id: str, rule_id: str, request: Request):
        _check_flag()
        await _authed(request, ws_id)
        result = await db.mail_rules.delete_one({"rule_id": rule_id, "workspace_id": ws_id})
        if result.deleted_count == 0:
            raise HTTPException(404, "Rule not found")
        return {"status": "deleted"}
