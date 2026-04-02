from nexus_utils import now_iso
"""Image Understanding — Process images through vision models.

Sends images to multimodal AI models (Gemini, GPT-4o) for analysis,
description, OCR, diagram understanding, and code extraction from screenshots.
"""
import base64
import logging
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)



def register_image_understanding_routes(api_router, db, get_current_user):

    @api_router.post("/tools/analyze-image")
    async def analyze_image(request: Request):
        """Send an image to a vision model for analysis."""
        user = await get_current_user(request)
        body = await request.json()
        
        image_data = body.get("image_data", "")  # base64 encoded
        image_url = body.get("image_url", "")
        question = body.get("question", "Describe this image in detail.")
        model = body.get("model", "gemini")
        workspace_id = body.get("workspace_id", "")
        
        if not image_data and not image_url:
            raise HTTPException(400, "Provide image_data (base64) or image_url")
        
        # Budget pre-check
        provider = "gemini" if model != "chatgpt" else "chatgpt"
        org_id = None
        if workspace_id:
            ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "org_id": 1})
            org_id = (ws or {}).get("org_id")
        try:
            from managed_keys import check_usage_budget, estimate_ai_cost_usd, estimate_tokens, emit_budget_alert, record_usage_event
            estimated_cost = estimate_ai_cost_usd(provider, estimate_tokens(question), 500)
            budget = await check_usage_budget(provider, estimated_cost, workspace_id=workspace_id, org_id=org_id, user_id=user["user_id"])
            if budget.get("blocked"):
                scope_name = (budget.get("scope_type") or "Platform").capitalize()
                await emit_budget_alert(provider, budget.get("scope_type") or "platform", budget.get("scope_id") or "platform", "blocked", budget.get("projected_spend_usd", estimated_cost), budget.get("hard_cap_usd"), user_id=user["user_id"], workspace_id=workspace_id, org_id=org_id, message=f"{scope_name} Nexus AI budget reached for image analysis.")
                raise HTTPException(429, f"{scope_name} Nexus AI budget reached for image analysis.")
        except HTTPException:
            raise
        except Exception as _be:
            budget = {}
            logger.warning(f"Budget check skipped for image analysis: {_be}")
        
        from key_resolver import get_integration_key
        
        if model == "gemini":
            result = await _analyze_with_gemini(db, image_data, image_url, question)
        elif model == "chatgpt":
            result = await _analyze_with_openai(db, image_data, image_url, question)
        else:
            result = await _analyze_with_gemini(db, image_data, image_url, question)
        
        # Record budget usage
        try:
            actual_cost = estimate_ai_cost_usd(provider, len(question) // 4, len(result.get("analysis", "")) // 4)
            await record_usage_event(provider, actual_cost, user_id=user["user_id"], workspace_id=workspace_id, org_id=org_id, usage_type="ai", key_source="platform", tokens_in=len(question) // 4, tokens_out=len(result.get("analysis", "")) // 4, metadata={"action": "image_analysis"})
            if budget.get("warn"):
                scope_name = (budget.get("scope_type") or "Platform").capitalize()
                await emit_budget_alert(provider, budget.get("scope_type") or "platform", budget.get("scope_id") or "platform", "warning", budget.get("projected_spend_usd", actual_cost), budget.get("warn_threshold_usd"), user_id=user["user_id"], workspace_id=workspace_id, org_id=org_id, message=f"{scope_name} Nexus AI budget warning for image analysis.")
        except Exception as _be:
            logger.warning(f"Budget recording failed for image analysis: {_be}")
        
        return result

    @api_router.post("/channels/{ch_id}/analyze-attachment")
    async def analyze_channel_attachment(ch_id: str, request: Request):
        """Analyze an image attachment from a channel message."""
        user = await get_current_user(request)
        body = await request.json()
        file_id = body.get("file_id", "")
        question = body.get("question", "Describe this image and any text, code, or diagrams in it.")
        
        # Get file data
        f = await db.file_storage.find_one({"file_id": file_id}, {"_id": 0, "data": 1, "mime_type": 1, "filename": 1})
        if not f:
            raise HTTPException(404, "File not found")
        
        image_data = f.get("data", "")
        if isinstance(image_data, bytes):
            image_data = base64.b64encode(image_data).decode()
        
        result = await _analyze_with_gemini(db, image_data, "", question)
        
        # Post analysis as a message in the channel
        if result.get("analysis"):
            import uuid
            await db.messages.insert_one({
                "message_id": f"msg_{uuid.uuid4().hex[:12]}",
                "channel_id": ch_id,
                "sender_type": "system",
                "sender_id": "vision",
                "sender_name": "Image Analysis",
                "content": f"**Image: {f.get('filename', 'attachment')}**\n\n{result['analysis']}",
                "created_at": now_iso(),
            })
        
        return result


async def _analyze_with_gemini(db, image_data, image_url, question):
    """Analyze image using Gemini Vision."""
    from key_resolver import get_integration_key
    api_key = await get_integration_key(db, "GOOGLE_AI_KEY")
    if not api_key:
        return {"error": "GOOGLE_AI_KEY not configured", "analysis": ""}
    
    import httpx
    
    parts = [{"text": question}]
    if image_data:
        parts.append({"inline_data": {"mime_type": "image/png", "data": image_data[:500000]}})
    elif image_url:
        # Download image first
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(image_url)
            if resp.status_code == 200:
                b64 = base64.b64encode(resp.content).decode()
                parts.append({"inline_data": {"mime_type": "image/png", "data": b64[:500000]}})
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            json={"contents": [{"parts": parts}]}
        )
        if resp.status_code != 200:
            return {"error": f"Gemini API error: {resp.status_code}", "analysis": ""}
        
        data = resp.json()
        text = ""
        for candidate in data.get("candidates") or []:
            for part in (candidate.get("content") or {}).get("parts") or []:
                if "text" in part:
                    text += part["text"]
        
        return {"analysis": text, "model": "gemini-2.0-flash", "question": question}


async def _analyze_with_openai(db, image_data, image_url, question):
    """Analyze image using GPT-4o Vision."""
    from key_resolver import get_integration_key
    api_key = await get_integration_key(db, "OPENAI_API_KEY")
    if not api_key:
        return {"error": "OPENAI_API_KEY not configured", "analysis": ""}
    
    import httpx
    
    content = [{"type": "text", "text": question}]
    if image_data:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data[:500000]}"}})
    elif image_url:
        content.append({"type": "image_url", "image_url": {"url": image_url}})
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": content}],
                "max_tokens": 1000,
            }
        )
        if resp.status_code != 200:
            return {"error": f"OpenAI API error: {resp.status_code}", "analysis": ""}
        
        data = resp.json()
        text = data.get("choices", [{}])([0].get("message") or {}).get("content", "")
        return {"analysis": text, "model": "gpt-4o", "question": question}
