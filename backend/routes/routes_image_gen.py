"""Image Generation — Gemini Nano Banana (default) + user-provided API key support"""
import os
import uuid
import base64
import logging
import time
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


class ImageGenRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    provider: str = "gemini"  # gemini, imagen4, openai, or nano_banana
    use_own_key: bool = False


class ImageGenStats(BaseModel):
    pass


def register_image_gen_routes(api_router, db, get_current_user):

    async def _authed_user(request, workspace_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, workspace_id)
        return user

    @api_router.post("/workspaces/{workspace_id}/generate-image")
    async def generate_image(workspace_id: str, data: ImageGenRequest, request: Request):
        """Generate an image from a text prompt"""
        user = await _authed_user(request, workspace_id)
        start_time = time.time()

        # Budget pre-check
        workspace = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "org_id": 1})
        org_id = (workspace or {}).get("org_id")
        budget = {}
        try:
            from managed_keys import check_usage_budget, estimate_ai_cost_usd, estimate_tokens, emit_budget_alert
            estimated_cost = estimate_ai_cost_usd("gemini", estimate_tokens(data.prompt), 500)
            budget = await check_usage_budget("gemini", estimated_cost, workspace_id=workspace_id, org_id=org_id, user_id=user["user_id"])
            if budget.get("blocked"):
                scope_name = (budget.get("scope_type") or "Platform").capitalize()
                await emit_budget_alert("gemini", budget.get("scope_type") or "platform", budget.get("scope_id") or "platform", "blocked", budget.get("projected_spend_usd", estimated_cost), budget.get("hard_cap_usd"), user_id=user["user_id"], workspace_id=workspace_id, org_id=org_id, message=f"{scope_name} Nexus AI budget reached for image generation.")
                raise HTTPException(429, f"{scope_name} Nexus AI budget reached for image generation. Contact your admin to increase the limit.")
        except HTTPException:
            raise
        except Exception as _be:
            logger.debug(f"Budget check skipped for image gen: {_be}")

        api_key = None
        key_source = "user"

        if data.use_own_key:
            from routes_ai_keys import decrypt_key
            user_doc = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "ai_keys": 1})
            user_keys = user_doc.get("ai_keys") or {} if user_doc else {}
            if data.provider == "openai":
                encrypted = user_keys.get("openai") or user_keys.get("chatgpt")
            else:
                encrypted = user_keys.get(data.provider) or user_keys.get("gemini") or user_keys.get("google")
            if encrypted:
                try:
                    api_key = decrypt_key(encrypted)
                    key_source = "user"
                except Exception as _e:
                    logger.warning(f"Caught exception: {_e}")
            if not api_key:
                raise HTTPException(400, f"No {data.provider} API key configured. Add one in Settings.")
        else:
            from key_resolver import get_integration_key
            if data.provider == "openai":
                api_key = await get_integration_key(db, "OPENAI_API_KEY")
                if not api_key:
                    raise HTTPException(500, "OpenAI image generation not configured. Set OPENAI_API_KEY.")
            else:
                api_key = await get_integration_key(db, "GOOGLE_AI_KEY")
                if not api_key:
                    raise HTTPException(500, "Image generation service not configured. Set GOOGLE_AI_KEY environment variable.")
            key_source = "platform"

        try:
            import httpx
            import base64 as b64

            image_data = None
            text_response = ""
            mime_type = "image/png"

            if data.provider == "openai":
                async with httpx.AsyncClient(timeout=90.0) as client:
                    resp = await client.post(
                        "https://api.openai.com/v1/images/generations",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json={"model": "gpt-image-1", "prompt": data.prompt, "n": 1, "size": "1024x1024", "output_format": "b64_json"}
                    )
                    resp.raise_for_status()
                    result = resp.json()
                    if result.get("data") and len(result["data"]) > 0:
                        image_data = result["data"][0].get("b64_json", "")
                        text_response = result["data"][0].get("revised_prompt", "")

            elif data.provider == "imagen4":
                async with httpx.AsyncClient(timeout=90.0) as client:
                    resp = await client.post(
                        "https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:generateImages",
                        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
                        json={"prompt": data.prompt, "config": {"numberOfImages": 1, "aspectRatio": "1:1", "outputOptions": {"addWatermark": True}}}
                    )
                    resp.raise_for_status()
                    result = resp.json()
                    generated = result.get("generatedImages", result.get("predictions", []))
                    if generated:
                        img = generated[0]
                        image_data = img.get("image", {}).get("imageBytes", "") or img.get("bytesBase64Encoded", "")
                        mime_type = img.get("image", {}).get("mimeType", "image/png") or img.get("mimeType", "image/png")

            elif data.provider == "nano_banana":
                from ai_providers import call_nano_banana
                result = await call_nano_banana(api_key, data.prompt, workspace_id=workspace_id)
                if result.get("images"):
                    image_data = result["images"][0].get("base64", "")
                    mime_type = result["images"][0].get("mime_type", "image/png")
                text_response = result.get("text", "")

            else:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent",
                        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
                        json={
                            "contents": [{"parts": [{"text": f"Generate an image: {data.prompt}"}]}],
                            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}
                        }
                    )
                    resp.raise_for_status()
                    result = resp.json()
                    for candidate in result.get("candidates") or []:
                        for part in (candidate.get("content") or {}).get("parts") or []:
                            if "inlineData" in part:
                                image_data = part["inlineData"].get("data", "")
                                mime_type = part["inlineData"].get("mimeType", "image/png")
                            if "text" in part:
                                text_response = part["text"]

            duration_ms = int((time.time() - start_time) * 1000)

            if not image_data:
                raise HTTPException(422, f"No image generated. Model response: {text_response[:200]}")

            image_id = f"img_{uuid.uuid4().hex[:12]}"
            now = datetime.now(timezone.utc).isoformat()

            image_record = {
                "image_id": image_id,
                "workspace_id": workspace_id,
                "prompt": data.prompt,
                "provider": data.provider,
                "key_source": key_source,
                "mime_type": mime_type,
                "text_response": text_response[:500] if text_response else None,
                "duration_ms": duration_ms,
                "created_by": user["user_id"],
                "created_at": now,
            }
            await db.generated_images.insert_one(image_record)

            await db.image_data.insert_one({
                "image_id": image_id,
                "data": image_data,
                "created_at": now,
            })

            await db.image_gen_metrics.insert_one({
                "metric_id": f"igm_{uuid.uuid4().hex[:8]}",
                "workspace_id": workspace_id,
                "provider": data.provider,
                "key_source": key_source,
                "duration_ms": duration_ms,
                "success": True,
                "prompt_length": len(data.prompt),
                "created_at": now,
            })

            # Record budget usage
            try:
                from managed_keys import record_usage_event, estimate_ai_cost_usd, emit_budget_alert
                actual_cost = estimate_ai_cost_usd("gemini", len(data.prompt) // 4, 500)
                await record_usage_event("gemini", actual_cost, user_id=user["user_id"], workspace_id=workspace_id, org_id=org_id, usage_type="ai", key_source=key_source, tokens_in=len(data.prompt) // 4, tokens_out=500, metadata={"action": "image_generation", "image_id": image_id})
                if budget.get("warn"):
                    scope_name = (budget.get("scope_type") or "Platform").capitalize()
                    await emit_budget_alert("gemini", budget.get("scope_type") or "platform", budget.get("scope_id") or "platform", "warning", budget.get("projected_spend_usd", actual_cost), budget.get("warn_threshold_usd"), user_id=user["user_id"], workspace_id=workspace_id, org_id=org_id, message=f"{scope_name} Nexus AI budget warning for image generation.")
            except Exception as _be:
                logger.debug(f"Budget record skipped for image gen: {_be}")

            return {
                "image_id": image_id,
                "mime_type": mime_type,
                "data_preview": image_data[:50] + "...",
                "text_response": text_response[:200] if text_response else None,
                "duration_ms": duration_ms,
                "key_source": key_source,
            }

        except HTTPException:
            raise
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Image generation failed: {e}")

            # Log failure metric
            await db.image_gen_metrics.insert_one({
                "metric_id": f"igm_{uuid.uuid4().hex[:8]}",
                "workspace_id": workspace_id,
                "provider": data.provider,
                "key_source": key_source,
                "duration_ms": duration_ms,
                "success": False,
                "error": str(e)[:200],
                "prompt_length": len(data.prompt),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            raise HTTPException(500, f"Image generation failed: {str(e)[:200]}")

    @api_router.get("/images/{image_id}")
    async def get_image(image_id: str, request: Request):
        """Get image metadata"""
        await get_current_user(request)
        record = await db.generated_images.find_one({"image_id": image_id}, {"_id": 0})
        if not record:
            raise HTTPException(404, "Image not found")
        return record

    @api_router.get("/images/{image_id}/data")
    async def get_image_data(image_id: str, request: Request):
        """Get image base64 data"""
        await get_current_user(request)
        data = await db.image_data.find_one({"image_id": image_id}, {"_id": 0})
        if not data:
            raise HTTPException(404, "Image data not found")
        return {"image_id": image_id, "data": data["data"]}

    @api_router.get("/workspaces/{workspace_id}/images")
    async def list_workspace_images(workspace_id: str, request: Request, limit: int = 20, offset: int = 0):
        """List generated images for a workspace"""
        await _authed_user(request, workspace_id)
        images = await db.generated_images.find(
            {"workspace_id": workspace_id}, {"_id": 0}
        ).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
        total = await db.generated_images.count_documents({"workspace_id": workspace_id})
        return {"images": images, "total": total}

    @api_router.delete("/images/{image_id}")
    async def delete_image(image_id: str, request: Request):
        """Delete a generated image"""
        await get_current_user(request)
        await db.generated_images.delete_one({"image_id": image_id})
        await db.image_data.delete_one({"image_id": image_id})
        return {"message": "Image deleted"}

    # ============ Monitoring ============

    @api_router.get("/workspaces/{workspace_id}/image-gen/metrics")
    async def get_image_gen_metrics(workspace_id: str, request: Request):
        """Get image generation metrics for monitoring"""
        await _authed_user(request, workspace_id)
        pipeline = [
            {"$match": {"workspace_id": workspace_id}},
            {"$group": {
                "_id": None,
                "total_requests": {"$sum": 1},
                "successful": {"$sum": {"$cond": ["$success", 1, 0]}},
                "failed": {"$sum": {"$cond": ["$success", 0, 1]}},
                "avg_duration_ms": {"$avg": "$duration_ms"},
                "total_duration_ms": {"$sum": "$duration_ms"},
            }}
        ]
        result = await db.image_gen_metrics.aggregate(pipeline).to_list(1)
        if result:
            r = result[0]
            return {
                "total_requests": r["total_requests"],
                "successful": r["successful"],
                "failed": r["failed"],
                "success_rate": round(r["successful"] / max(r["total_requests"], 1) * 100, 1),
                "avg_duration_ms": round(r["avg_duration_ms"] or 0),
            }
        return {"total_requests": 0, "successful": 0, "failed": 0, "success_rate": 0, "avg_duration_ms": 0}
