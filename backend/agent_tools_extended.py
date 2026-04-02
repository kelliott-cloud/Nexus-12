from nexus_utils import now_iso, safe_regex
"""Extended Agent Tools — Web search, image gen, ask human, file read, decisions, cross-channel, alerts."""
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


# ============ Web Search ============

async def tool_web_search(db, workspace_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Search the web and return structured results."""
    query = params.get("query", "")
    if not query:
        return {"error": "Query required"}
    
    import httpx
    # Try Serper API first, fall back to DuckDuckGo HTML
    from key_resolver import get_integration_key
    serper_key = await get_integration_key(db, "SERPER_API_KEY")
    
    if serper_key:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post("https://google.serper.dev/search",
                headers={"X-API-KEY": serper_key},
                json={"q": query, "num": 5})
            data = resp.json()
            results = [{"title": r.get("title", ""), "url": r.get("link", ""), "snippet": r.get("snippet", "")[:200]}
                       for r in data.get("organic") or [][:5]]
            return {"results": results, "query": query, "source": "serper"}
    
    # Fallback: DuckDuckGo instant answer
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1")
        data = resp.json()
        results = []
        if data.get("Abstract"):
            results.append({"title": data.get("Heading", query), "url": data.get("AbstractURL", ""), "snippet": data["Abstract"][:200]})
        for r in data.get("RelatedTopics", [])[:4]:
            if isinstance(r, dict) and r.get("Text"):
                results.append({"title": r.get("Text", "")[:80], "url": r.get("FirstURL", ""), "snippet": r.get("Text", "")[:200]})
        return {"results": results, "query": query, "source": "duckduckgo"}


# ============ Image Generation ============

async def tool_generate_image(db, workspace_id, user_id, params):
    """Generate an image from a text prompt."""
    prompt = params.get("prompt", "")
    if not prompt:
        return {"error": "Prompt required"}
    
    from key_resolver import get_integration_key
    api_key = await get_integration_key(db, "GOOGLE_AI_KEY")
    if not api_key:
        api_key = await get_integration_key(db, "OPENAI_API_KEY")
    
    if not api_key:
        return {"error": "No image generation API key configured"}
    
    # Use Gemini for image gen
    import httpx
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent",
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            json={"contents": [{"parts": [{"text": f"Generate an image: {prompt}"}]}],
                  "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}})
        if resp.status_code != 200:
            return {"error": f"Image generation failed: {resp.status_code}"}
        
        data = resp.json()
        for candidate in data.get("candidates") or []:
            for part in (candidate.get("content") or {}).get("parts") or []:
                if "inlineData" in part:
                    return {"image_data": part["inlineData"]["data"][:100], "generated": True, "prompt": prompt}
    
    return {"error": "No image generated"}


# ============ Ask Human (Structured Query) ============

async def tool_ask_human(db, channel_id, agent_key, params):
    """Create a structured question for the human with options."""
    question = params.get("question", "")
    options = params.get("options") or []
    
    msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    msg = {
        "message_id": msg_id,
        "channel_id": channel_id,
        "sender_type": "system",
        "sender_id": agent_key,
        "sender_name": f"{agent_key} (Question)",
        "content": f"**Question from {agent_key}:**\n{question}",
        "message_type": "human_query",
        "query_options": options,
        "query_answered": False,
        "created_at": now_iso(),
    }
    await db.messages.insert_one(msg)
    msg.pop("_id", None)
    return {"question_id": msg_id, "question": question, "options": options, "awaiting_response": True}


# ============ File Read ============

async def tool_read_file(db, workspace_id, params):
    """Read the extracted text content of an uploaded file."""
    file_id = params.get("file_id", "")
    if not file_id:
        return {"error": "file_id required"}
    
    f = await db.file_storage.find_one(
        {"file_id": file_id}, {"_id": 0, "filename": 1, "extracted_text": 1, "mime_type": 1, "size": 1}
    )
    if not f:
        f = await db.files.find_one({"file_id": file_id}, {"_id": 0, "filename": 1, "extracted_text": 1, "content": 1})
    
    if not f:
        return {"error": f"File {file_id} not found"}
    
    text = f.get("extracted_text") or f.get("content", "")
    return {"file_id": file_id, "filename": f.get("filename", ""), "content": text[:10000], "truncated": len(text) > 10000}


# ============ Decision Log ============

async def tool_log_decision(db, workspace_id, channel_id, params):
    """Log a project decision to the structured decision log."""
    dec_id = f"dec_{uuid.uuid4().hex[:12]}"
    decision = {
        "decision_id": dec_id,
        "workspace_id": workspace_id,
        "channel_id": channel_id,
        "decision": params.get("decision", ""),
        "alternatives": params.get("alternatives") or [],
        "rationale": params.get("rationale", ""),
        "decided_by": params.get("decided_by", ""),
        "project_id": params.get("project_id", ""),
        "tags": params.get("tags") or [],
        "source_message_id": params.get("source_message_id", ""),
        "created_at": now_iso(),
    }
    await db.decision_log.insert_one(decision)
    decision.pop("_id", None)
    return decision


async def tool_query_decisions(db, workspace_id, params):
    """Search the decision log."""
    query = params.get("query", "")
    decisions = await db.decision_log.find(
        {"workspace_id": workspace_id, "decision": {"$regex": safe_regex(query), "$options": "i"}},
        {"_id": 0}
    ).sort("created_at", -1).limit(10).to_list(10)
    return {"decisions": decisions, "query": query}


# ============ Cross-Channel Query ============

async def tool_search_channels(db, workspace_id, params):
    """Search across all channels in the workspace."""
    query = params.get("query", "")
    if not query:
        return {"error": "Query required"}
    
    results = []
    # Search messages across all workspace channels
    channels = await db.channels.find({"workspace_id": workspace_id}, {"_id": 0, "channel_id": 1, "name": 1}).to_list(20)
    ch_map = {c["channel_id"]: c["name"] for c in channels}
    
    messages = await db.messages.find(
        {"channel_id": {"$in": list(ch_map.keys())}, "content": {"$regex": safe_regex(query), "$options": "i"}},
        {"_id": 0, "message_id": 1, "channel_id": 1, "sender_name": 1, "content": 1, "created_at": 1}
    ).sort("created_at", -1).limit(10).to_list(10)
    
    for m in messages:
        results.append({
            "channel": ch_map.get(m["channel_id"], ""),
            "sender": m.get("sender_name", ""),
            "content": m.get("content", "")[:500],
            "message_id": m.get("message_id", ""),
            "date": m.get("created_at", ""),
        })
    
    return {"results": results, "query": query, "channels_searched": len(ch_map)}


# ============ Send Alert ============

async def tool_send_alert(db, workspace_id, channel_id, params):
    """Send an alert/notification to the human."""
    message = params.get("message", "")
    severity = params.get("severity", "info")
    
    # Create notification
    notif_id = f"notif_{uuid.uuid4().hex[:12]}"
    notif = {
        "notification_id": notif_id,
        "workspace_id": workspace_id,
        "channel_id": channel_id,
        "type": "agent_alert",
        "severity": severity,
        "message": message,
        "read": False,
        "created_at": now_iso(),
    }
    await db.notifications.insert_one(notif)
    
    # Also post as system message in channel
    await db.messages.insert_one({
        "message_id": f"msg_{uuid.uuid4().hex[:12]}",
        "channel_id": channel_id,
        "sender_type": "system",
        "sender_id": "alert",
        "sender_name": f"Alert ({severity.upper()})",
        "content": f"**{severity.upper()} ALERT**\n{message}",
        "created_at": now_iso(),
    })
    
    return {"alert_id": notif_id, "severity": severity, "delivered": True}


# ============ Agent Skill Trees ============

async def update_agent_skill(db, workspace_id, agent_key, skill_category, success=True, complexity=1.0):
    """Track agent skill development from actual usage with XP, streaks, auto-leveling."""
    base_xp = 10
    xp_earned = int(base_xp * complexity * (1.5 if success else 0.3))

    # Fetch current skill record
    current = await db.agent_skills.find_one(
        {"workspace_id": workspace_id, "agent_key": agent_key, "skill": skill_category},
        {"_id": 0}
    )

    streak = 0
    best_streak = 0
    if current:
        prev_streak = current.get("streak", 0)
        best_streak = current.get("best_streak", 0)
        if success:
            streak = prev_streak + 1
            if streak > best_streak:
                best_streak = streak
        else:
            streak = 0

    await db.agent_skills.update_one(
        {"workspace_id": workspace_id, "agent_key": agent_key, "skill": skill_category},
        {
            "$inc": {"total_tasks": 1, "successful_tasks": 1 if success else 0, "xp": xp_earned},
            "$set": {
                "last_used": now_iso(),
                "streak": streak,
                "best_streak": best_streak,
            },
            "$setOnInsert": {"created_at": now_iso(), "level": "novice"},
        },
        upsert=True,
    )

    # Auto-level calculation based on XP thresholds
    updated = await db.agent_skills.find_one(
        {"workspace_id": workspace_id, "agent_key": agent_key, "skill": skill_category},
        {"_id": 0, "xp": 1, "total_tasks": 1, "successful_tasks": 1}
    )
    if updated:
        xp = updated.get("xp", 0)
        total = updated.get("total_tasks", 0)
        success_rate = updated.get("successful_tasks", 0) / max(total, 1)
        proficiency = round(success_rate * 100, 1)

        # Level thresholds: novice(0), intermediate(50xp+60%), advanced(200xp+70%), expert(500xp+80%), master(1000xp+90%)
        level = "novice"
        if xp >= 1000 and proficiency >= 90:
            level = "master"
        elif xp >= 500 and proficiency >= 80:
            level = "expert"
        elif xp >= 200 and proficiency >= 70:
            level = "advanced"
        elif xp >= 50 and proficiency >= 60:
            level = "intermediate"

        await db.agent_skills.update_one(
            {"workspace_id": workspace_id, "agent_key": agent_key, "skill": skill_category},
            {"$set": {"level": level, "proficiency": proficiency}}
        )


async def get_agent_skills(db, workspace_id, agent_key):
    """Get an agent's skill profile."""
    skills = await db.agent_skills.find(
        {"workspace_id": workspace_id, "agent_key": agent_key},
        {"_id": 0}
    ).sort("total_tasks", -1).to_list(20)
    
    for s in skills:
        total = s.get("total_tasks", 0)
        success = s.get("successful_tasks", 0)
        s["proficiency"] = round(success / max(total, 1) * 100, 1)
    
    return skills


# ============ Conversation Branching ============

async def tool_branch_conversation(db, channel_id, from_message_id, params):
    """Fork a conversation at a specific message to explore alternatives."""
    branch_name = params.get("branch_name", "Alternative path")
    
    # Get the parent channel
    parent_ch = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0})
    if not parent_ch:
        return {"error": "Channel not found"}
    
    # Create a branch channel
    branch_id = f"ch_{uuid.uuid4().hex[:12]}"
    branch = {
        "channel_id": branch_id,
        "workspace_id": parent_ch["workspace_id"],
        "name": f"{parent_ch.get('name', 'chat')}-branch-{branch_name[:20]}",
        "description": f"Branched from {channel_id} at message {from_message_id}",
        "ai_agents": parent_ch.get("ai_agents") or [],
        "is_branch": True,
        "branch_from_channel": channel_id,
        "branch_from_message": from_message_id,
        "created_at": now_iso(),
    }
    await db.channels.insert_one(branch)
    
    # Copy messages up to the branch point
    messages = await db.messages.find(
        {"channel_id": channel_id, "created_at": {"$lte": (await db.messages.find_one({"message_id": from_message_id}, {"_id": 0, "created_at": 1}) or {}).get("created_at", "")}},
        {"_id": 0}
    ).sort("created_at", 1).to_list(100)
    
    for msg in messages:
        msg["_original_id"] = msg["message_id"]
        msg["message_id"] = f"msg_{uuid.uuid4().hex[:12]}"
        msg["channel_id"] = branch_id
        await db.messages.insert_one(msg)
    
    return {"branch_channel_id": branch_id, "branch_name": branch_name, "messages_copied": len(messages)}
