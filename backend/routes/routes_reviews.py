"""Marketplace Reviews & Ratings — User feedback on marketplace agents/templates."""
import uuid
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional

logger = logging.getLogger(__name__)


class CreateReview(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    title: str = Field("", max_length=200)
    content: str = Field("", max_length=2000)


class FlagReview(BaseModel):
    reason: str = Field("inappropriate", max_length=200)


def register_review_routes(api_router, db, get_current_user):

    @api_router.post("/marketplace/{template_id}/reviews")
    async def create_review(template_id: str, data: CreateReview, request: Request):
        user = await get_current_user(request)
        tpl = await db.marketplace_templates.find_one({"marketplace_id": template_id}, {"_id": 0, "publisher_id": 1})
        if not tpl:
            raise HTTPException(404, "Template not found")
        if tpl.get("publisher_id") == user["user_id"]:
            raise HTTPException(400, "Cannot review your own template")

        existing = await db.marketplace_reviews.find_one(
            {"template_id": template_id, "user_id": user["user_id"]})
        if existing:
            raise HTTPException(400, "You already reviewed this template")

        review_id = f"rev_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        review = {
            "review_id": review_id, "template_id": template_id,
            "user_id": user["user_id"],
            "user_name": user.get("name", user.get("email", "Anonymous")),
            "rating": data.rating, "title": data.title, "content": data.content,
            "flagged": False, "flag_reason": "",
            "helpful_count": 0, "created_at": now, "updated_at": now,
        }
        await db.marketplace_reviews.insert_one(review)
        review.pop("_id", None)

        # Update template aggregate rating
        await _update_template_rating(db, template_id)
        return review

    @api_router.get("/marketplace/{template_id}/reviews")
    async def list_reviews(template_id: str, request: Request, sort: str = "recent"):
        await get_current_user(request)
        sort_field = "created_at" if sort == "recent" else "rating" if sort == "rating" else "helpful_count"
        reviews = await db.marketplace_reviews.find(
            {"template_id": template_id, "flagged": {"$ne": True}},
            {"_id": 0}
        ).sort(sort_field, -1).limit(50).to_list(50)

        # Rating breakdown
        pipeline = [
            {"$match": {"template_id": template_id, "flagged": {"$ne": True}}},
            {"$group": {"_id": "$rating", "count": {"$sum": 1}}},
        ]
        breakdown = {str(i): 0 for i in range(1, 6)}
        async for doc in db.marketplace_reviews.aggregate(pipeline):
            breakdown[str(doc["_id"])] = doc["count"]

        return {"reviews": reviews, "rating_breakdown": breakdown}

    @api_router.put("/marketplace/{template_id}/reviews/{review_id}")
    async def update_review(template_id: str, review_id: str, data: CreateReview, request: Request):
        user = await get_current_user(request)
        result = await db.marketplace_reviews.update_one(
            {"review_id": review_id, "user_id": user["user_id"]},
            {"$set": {"rating": data.rating, "title": data.title, "content": data.content, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        if result.matched_count == 0:
            raise HTTPException(404, "Review not found or not yours")
        await _update_template_rating(db, template_id)
        return {"updated": review_id}

    @api_router.delete("/marketplace/{template_id}/reviews/{review_id}")
    async def delete_review(template_id: str, review_id: str, request: Request):
        user = await get_current_user(request)
        result = await db.marketplace_reviews.delete_one(
            {"review_id": review_id, "user_id": user["user_id"]}
        )
        if result.deleted_count == 0:
            raise HTTPException(404, "Review not found or not yours")
        await _update_template_rating(db, template_id)
        return {"deleted": review_id}

    @api_router.post("/marketplace/{template_id}/reviews/{review_id}/flag")
    async def flag_review(template_id: str, review_id: str, data: FlagReview, request: Request):
        user = await get_current_user(request)
        review = await db.marketplace_reviews.find_one({"review_id": review_id}, {"_id": 0, "user_id": 1, "flag_count": 1})
        if not review:
            raise HTTPException(404, "Review not found")
        if review.get("user_id") == user["user_id"]:
            raise HTTPException(400, "Cannot flag your own review")
        existing_flag = await db.review_flags.find_one({"review_id": review_id, "user_id": user["user_id"]})
        if existing_flag:
            raise HTTPException(400, "You already flagged this review")
        await db.review_flags.insert_one({
            "review_id": review_id, "user_id": user["user_id"],
            "reason": data.reason, "created_at": datetime.now(timezone.utc).isoformat()
        })
        flag_count = (review.get("flag_count", 0) or 0) + 1
        update = {"$set": {"flag_count": flag_count}}
        if flag_count >= 3:
            update["$set"]["flagged"] = True
            update["$set"]["flag_reason"] = data.reason
        await db.marketplace_reviews.update_one({"review_id": review_id}, update)
        return {"flagged": review_id, "flag_count": flag_count}

    @api_router.post("/marketplace/{template_id}/reviews/{review_id}/helpful")
    async def mark_helpful(template_id: str, review_id: str, request: Request):
        user = await get_current_user(request)
        review = await db.marketplace_reviews.find_one({"review_id": review_id}, {"_id": 0, "review_id": 1})
        if not review:
            raise HTTPException(404, "Review not found")
        existing = await db.review_helpful_votes.find_one({"review_id": review_id, "user_id": user["user_id"]})
        if existing:
            raise HTTPException(400, "Already marked as helpful")
        await db.review_helpful_votes.insert_one({
            "review_id": review_id, "user_id": user["user_id"],
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        await db.marketplace_reviews.update_one(
            {"review_id": review_id}, {"$inc": {"helpful_count": 1}}
        )
        return {"marked_helpful": review_id}


async def _update_template_rating(db, template_id):
    """Recalculate template's aggregate rating from reviews."""
    pipeline = [
        {"$match": {"template_id": template_id, "flagged": {"$ne": True}}},
        {"$group": {"_id": None, "avg": {"$avg": "$rating"}, "count": {"$sum": 1}, "total": {"$sum": "$rating"}}},
    ]
    async for doc in db.marketplace_reviews.aggregate(pipeline):
        await db.marketplace_templates.update_one(
            {"marketplace_id": template_id},
            {"$set": {
                "avg_rating": round(doc["avg"], 1),
                "rating_count": doc["count"],
                "ratings_sum": doc["total"],
            }}
        )
        return
    await db.marketplace_templates.update_one(
        {"marketplace_id": template_id},
        {"$set": {"avg_rating": 0, "rating_count": 0, "ratings_sum": 0}}
    )
