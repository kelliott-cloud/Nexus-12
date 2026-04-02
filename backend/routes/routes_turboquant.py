"""NAVC (Nexus Adaptive Vector Compression) API Routes — Profiles, Runs, Promotions."""
import uuid
import logging
import numpy as np
from datetime import datetime, timezone
from fastapi import HTTPException, Request, BackgroundTasks
from nexus_utils import now_iso
from nexus_config import FEATURE_FLAGS

logger = logging.getLogger(__name__)


def register_turboquant_routes(api_router, db, get_current_user):
    from turboquant.profile_schema import ProfileCreate, RunCreate, PromotionCreate, DatasetUpload

    async def _authed(request, ws_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, ws_id)
        return user

    def _check_flag():
        if not FEATURE_FLAGS.get("turboquant", {}).get("enabled", True):
            raise HTTPException(501, FEATURE_FLAGS.get("turboquant", {}).get("reason", "NAVC not enabled"))

    # ============ Profile CRUD ============

    @api_router.post("/workspaces/{ws_id}/turboquant/profiles")
    async def create_profile(ws_id: str, data: ProfileCreate, request: Request):
        _check_flag()
        user = await _authed(request, ws_id)
        profile_id = f"tqp_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        profile = {
            "profile_id": profile_id, "workspace_id": ws_id,
            "name": data.name, "target_type": data.target_type.value,
            "optimization_target": data.optimization_target.value,
            "bit_width": data.bit_width, "rotation_seed": data.rotation_seed,
            "enable_residual": data.enable_residual,
            "kv_config": data.kv_config.dict() if data.kv_config else None,
            "thresholds": data.thresholds, "description": data.description,
            "version": 1, "created_by": user["user_id"],
            "created_at": now, "updated_at": now,
        }
        await db.turboquant_profiles.insert_one(profile)
        profile.pop("_id", None)
        return profile

    @api_router.get("/workspaces/{ws_id}/turboquant/profiles")
    async def list_profiles(ws_id: str, request: Request):
        _check_flag()
        await _authed(request, ws_id)
        profiles = await db.turboquant_profiles.find(
            {"workspace_id": ws_id}, {"_id": 0}
        ).sort("created_at", -1).to_list(100)
        return {"profiles": profiles}

    @api_router.get("/workspaces/{ws_id}/turboquant/profiles/{profile_id}")
    async def get_profile(ws_id: str, profile_id: str, request: Request):
        _check_flag()
        await _authed(request, ws_id)
        profile = await db.turboquant_profiles.find_one(
            {"profile_id": profile_id, "workspace_id": ws_id}, {"_id": 0})
        if not profile:
            raise HTTPException(404, "Profile not found")
        return profile

    @api_router.put("/workspaces/{ws_id}/turboquant/profiles/{profile_id}")
    async def update_profile(ws_id: str, profile_id: str, request: Request):
        _check_flag()
        user = await _authed(request, ws_id)
        body = await request.json()
        updates = {}
        for field in ["name", "description", "bit_width", "rotation_seed",
                     "enable_residual", "thresholds", "optimization_target", "kv_config"]:
            if field in body:
                updates[field] = body[field]
        if not updates:
            raise HTTPException(400, "No valid fields to update")
        updates["updated_at"] = now_iso()
        existing = await db.turboquant_profiles.find_one(
            {"profile_id": profile_id, "workspace_id": ws_id}, {"_id": 0, "version": 1})
        if not existing:
            raise HTTPException(404, "Profile not found")
        updates["version"] = (existing.get("version", 0) or 0) + 1
        await db.turboquant_profiles.update_one(
            {"profile_id": profile_id, "workspace_id": ws_id}, {"$set": updates})
        updated = await db.turboquant_profiles.find_one(
            {"profile_id": profile_id}, {"_id": 0})
        return updated

    @api_router.delete("/workspaces/{ws_id}/turboquant/profiles/{profile_id}")
    async def delete_profile(ws_id: str, profile_id: str, request: Request):
        _check_flag()
        await _authed(request, ws_id)
        result = await db.turboquant_profiles.delete_one(
            {"profile_id": profile_id, "workspace_id": ws_id})
        if result.deleted_count == 0:
            raise HTTPException(404, "Profile not found")
        return {"status": "deleted"}

    # ============ Run Execution ============

    @api_router.post("/workspaces/{ws_id}/turboquant/runs")
    async def start_run(ws_id: str, data: RunCreate, request: Request, bg: BackgroundTasks):
        _check_flag()
        user = await _authed(request, ws_id)
        profile = await db.turboquant_profiles.find_one(
            {"profile_id": data.profile_id, "workspace_id": ws_id}, {"_id": 0})
        if not profile:
            raise HTTPException(404, "Profile not found")

        run_id = f"tqr_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        run = {
            "run_id": run_id, "profile_id": data.profile_id,
            "workspace_id": ws_id, "dataset_id": data.dataset_id,
            "workload_ref": data.workload_ref,
            "run_baseline": data.run_baseline,
            "status": "queued", "progress": 0,
            "metrics": None, "baseline_metrics": None,
            "artifacts": [], "promotion_eval": None,
            "error": None,
            "created_by": user["user_id"], "created_at": now, "updated_at": now,
        }
        await db.turboquant_runs.insert_one(run)
        run.pop("_id", None)

        bg.add_task(_execute_run, db, run_id, profile, ws_id, data.run_baseline)
        return run

    @api_router.get("/workspaces/{ws_id}/turboquant/runs")
    async def list_runs(ws_id: str, request: Request):
        _check_flag()
        await _authed(request, ws_id)
        runs = await db.turboquant_runs.find(
            {"workspace_id": ws_id}, {"_id": 0}
        ).sort("created_at", -1).to_list(100)
        return {"runs": runs}

    @api_router.get("/workspaces/{ws_id}/turboquant/runs/{run_id}")
    async def get_run(ws_id: str, run_id: str, request: Request):
        _check_flag()
        await _authed(request, ws_id)
        run = await db.turboquant_runs.find_one(
            {"run_id": run_id, "workspace_id": ws_id}, {"_id": 0})
        if not run:
            raise HTTPException(404, "Run not found")
        return run

    @api_router.post("/workspaces/{ws_id}/turboquant/runs/{run_id}/cancel")
    async def cancel_run(ws_id: str, run_id: str, request: Request):
        _check_flag()
        await _authed(request, ws_id)
        result = await db.turboquant_runs.update_one(
            {"run_id": run_id, "workspace_id": ws_id, "status": {"$in": ["queued", "running"]}},
            {"$set": {"status": "cancelled", "updated_at": now_iso()}})
        if result.matched_count == 0:
            raise HTTPException(404, "Run not found or not cancellable")
        return {"status": "cancelled"}

    # ============ Datasets ============

    @api_router.post("/workspaces/{ws_id}/turboquant/datasets")
    async def create_dataset(ws_id: str, data: DatasetUpload, request: Request):
        _check_flag()
        user = await _authed(request, ws_id)
        dataset_id = f"tqd_{uuid.uuid4().hex[:12]}"
        now = now_iso()

        dataset = {
            "dataset_id": dataset_id, "workspace_id": ws_id,
            "name": data.name, "description": data.description,
            "dataset_type": data.dataset_type, "source": data.source,
            "model_name": data.model_name,
            "vector_count": 0, "dimensions": 0,
            "status": "ready" if data.source == "synthetic" else "pending",
            "created_by": user["user_id"], "created_at": now,
        }

        if data.source == "synthetic" and data.dataset_type == "kv_trace":
            from turboquant.kv_runner import MODEL_CONFIGS
            cfg = MODEL_CONFIGS.get(data.model_name or "custom", MODEL_CONFIGS["custom"])
            dataset["vector_count"] = cfg["layers"] * cfg["heads"] * cfg["seq_len"]
            dataset["dimensions"] = cfg["head_dim"]
            dataset["model_config"] = cfg
            dataset["status"] = "ready"

        if data.source == "workspace_memory":
            count = await db.workspace_memory.count_documents({"workspace_id": ws_id})
            dataset["vector_count"] = count
            dataset["status"] = "ready" if count >= 10 else "insufficient_data"

        await db.turboquant_datasets.insert_one(dataset)
        dataset.pop("_id", None)
        return dataset

    @api_router.get("/workspaces/{ws_id}/turboquant/datasets")
    async def list_datasets(ws_id: str, request: Request):
        _check_flag()
        await _authed(request, ws_id)
        datasets = await db.turboquant_datasets.find(
            {"workspace_id": ws_id}, {"_id": 0}
        ).sort("created_at", -1).to_list(50)
        return {"datasets": datasets}

    @api_router.delete("/workspaces/{ws_id}/turboquant/datasets/{dataset_id}")
    async def delete_dataset(ws_id: str, dataset_id: str, request: Request):
        _check_flag()
        await _authed(request, ws_id)
        result = await db.turboquant_datasets.delete_one(
            {"dataset_id": dataset_id, "workspace_id": ws_id})
        if result.deleted_count == 0:
            raise HTTPException(404, "Dataset not found")
        return {"status": "deleted"}

    # ============ KV Model Configs ============

    @api_router.get("/workspaces/{ws_id}/turboquant/kv-models")
    async def list_kv_models(ws_id: str, request: Request):
        _check_flag()
        await _authed(request, ws_id)
        from turboquant.kv_runner import MODEL_CONFIGS
        models = []
        for name, cfg in MODEL_CONFIGS.items():
            total_params = cfg["layers"] * cfg["heads"] * cfg["seq_len"] * cfg["head_dim"] * 2
            models.append({
                "name": name, **cfg,
                "total_kv_params": total_params,
                "memory_fp32_mb": round(total_params * 4 / (1024 * 1024), 1),
            })
        return {"models": models}

    # ============ Promotions ============

    @api_router.post("/workspaces/{ws_id}/turboquant/promotions")
    async def create_promotion(ws_id: str, data: PromotionCreate, request: Request):
        _check_flag()
        user = await _authed(request, ws_id)
        run = await db.turboquant_runs.find_one(
            {"run_id": data.run_id, "workspace_id": ws_id}, {"_id": 0})
        if not run:
            raise HTTPException(404, "Run not found")
        if run.get("status") != "completed":
            raise HTTPException(400, "Only completed runs can be promoted")
        promo_eval = run.get("promotion_eval", {})
        if not promo_eval.get("eligible"):
            raise HTTPException(400, f"Run not eligible for promotion: {promo_eval.get('reason', 'unknown')}")

        promo_id = f"tqpm_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        promotion = {
            "promotion_id": promo_id, "run_id": data.run_id,
            "workspace_id": ws_id, "target_binding": data.target_binding,
            "notes": data.notes, "profile_id": run.get("profile_id"),
            "metrics_snapshot": run.get("metrics"),
            "status": "active",
            "promoted_by": user["user_id"], "promoted_at": now,
        }
        await db.turboquant_promotions.insert_one(promotion)
        promotion.pop("_id", None)
        return promotion

    @api_router.get("/workspaces/{ws_id}/turboquant/promotions")
    async def list_promotions(ws_id: str, request: Request):
        _check_flag()
        await _authed(request, ws_id)
        promos = await db.turboquant_promotions.find(
            {"workspace_id": ws_id}, {"_id": 0}
        ).sort("promoted_at", -1).to_list(50)
        return {"promotions": promos}

    @api_router.post("/workspaces/{ws_id}/turboquant/promotions/{promo_id}/rollback")
    async def rollback_promotion(ws_id: str, promo_id: str, request: Request):
        """Rollback an active promotion — sets status to 'rolled_back'."""
        _check_flag()
        user = await _authed(request, ws_id)
        result = await db.turboquant_promotions.update_one(
            {"promotion_id": promo_id, "workspace_id": ws_id, "status": "active"},
            {"$set": {"status": "rolled_back", "rolled_back_by": user["user_id"], "rolled_back_at": now_iso()}})
        if result.matched_count == 0:
            raise HTTPException(404, "Promotion not found or not active")
        # Also unbind from workspace settings if bound
        await db.workspaces.update_one(
            {"workspace_id": ws_id, "turboquant_binding.promotion_id": promo_id},
            {"$unset": {"turboquant_binding": ""}})
        return {"status": "rolled_back"}

    # ============ Run Comparison ============

    @api_router.get("/workspaces/{ws_id}/turboquant/compare")
    async def compare_runs(ws_id: str, request: Request, run_ids: str = ""):
        """Compare 2+ runs side-by-side. Pass run_ids as comma-separated query param."""
        _check_flag()
        await _authed(request, ws_id)
        ids = [r.strip() for r in run_ids.split(",") if r.strip()]
        if len(ids) < 2:
            raise HTTPException(400, "Provide at least 2 run_ids (comma-separated)")
        if len(ids) > 6:
            raise HTTPException(400, "Maximum 6 runs for comparison")

        runs = []
        for rid in ids:
            run = await db.turboquant_runs.find_one(
                {"run_id": rid, "workspace_id": ws_id, "status": "completed"}, {"_id": 0})
            if run:
                profile = await db.turboquant_profiles.find_one(
                    {"profile_id": run.get("profile_id"), "workspace_id": ws_id}, {"_id": 0, "name": 1, "bit_width": 1, "target_type": 1})
                runs.append({
                    "run_id": rid,
                    "profile_name": (profile or {}).get("name", "Unknown"),
                    "target_type": (profile or {}).get("target_type", "unknown"),
                    "bit_width": (profile or {}).get("bit_width", 0),
                    "metrics": run.get("metrics"),
                    "promotion_eval": run.get("promotion_eval"),
                    "created_at": run.get("created_at"),
                })

        if len(runs) < 2:
            raise HTTPException(400, "Need at least 2 completed runs to compare")

        # Build comparison summary
        comparison = {
            "runs": runs,
            "chart_data": {
                "compression": [{"name": r["profile_name"], "value": r["metrics"]["memory"]["compression_ratio"]} for r in runs if r.get("metrics")],
                "memory_saved": [{"name": r["profile_name"], "value": r["metrics"]["memory"]["memory_reduction_pct"]} for r in runs if r.get("metrics")],
                "mse": [{"name": r["profile_name"], "value": round(r["metrics"]["distortion"]["mse"], 6)} for r in runs if r.get("metrics")],
                "snr": [{"name": r["profile_name"], "value": round(r["metrics"]["distortion"]["snr_db"], 2)} for r in runs if r.get("metrics")],
            },
            "best": {
                "compression": max(runs, key=lambda r: r["metrics"]["memory"]["compression_ratio"] if r.get("metrics") else 0).get("run_id"),
                "quality": min(runs, key=lambda r: r["metrics"]["distortion"]["mse"] if r.get("metrics") else 999).get("run_id"),
            },
        }
        return comparison

    # ============ Deployment Binding ============

    @api_router.post("/workspaces/{ws_id}/turboquant/bind")
    async def bind_promotion(ws_id: str, request: Request):
        """Bind an active promotion to workspace retrieval settings."""
        _check_flag()
        user = await _authed(request, ws_id)
        body = await request.json()
        promo_id = body.get("promotion_id", "")

        promo = await db.turboquant_promotions.find_one(
            {"promotion_id": promo_id, "workspace_id": ws_id, "status": "active"}, {"_id": 0})
        if not promo:
            raise HTTPException(404, "Active promotion not found")

        binding = {
            "promotion_id": promo_id,
            "profile_id": promo.get("profile_id"),
            "run_id": promo.get("run_id"),
            "target_binding": promo.get("target_binding"),
            "metrics_snapshot": promo.get("metrics_snapshot"),
            "bound_by": user["user_id"],
            "bound_at": now_iso(),
        }
        await db.workspaces.update_one(
            {"workspace_id": ws_id},
            {"$set": {"turboquant_binding": binding}})
        return {"status": "bound", "binding": binding}

    @api_router.get("/workspaces/{ws_id}/turboquant/binding")
    async def get_binding(ws_id: str, request: Request):
        """Get current NAVC deployment binding for this workspace."""
        _check_flag()
        await _authed(request, ws_id)
        ws = await db.workspaces.find_one({"workspace_id": ws_id}, {"_id": 0, "turboquant_binding": 1})
        return {"binding": (ws or {}).get("turboquant_binding")}

    @api_router.delete("/workspaces/{ws_id}/turboquant/binding")
    async def unbind_promotion(ws_id: str, request: Request):
        """Remove NAVC deployment binding."""
        _check_flag()
        await _authed(request, ws_id)
        await db.workspaces.update_one(
            {"workspace_id": ws_id}, {"$unset": {"turboquant_binding": ""}})
        return {"status": "unbound"}


async def _execute_run(db, run_id: str, profile: dict, ws_id: str, run_baseline: bool):
    """Background task: execute NAVC compression + benchmark."""
    try:
        from turboquant.scoring import evaluate_promotion

        await db.turboquant_runs.update_one(
            {"run_id": run_id}, {"$set": {"status": "running", "progress": 10}})

        target_type = profile.get("target_type", "vector_index")

        if target_type == "kv_cache":
            # KV-Cache compression path
            from turboquant.kv_runner import run_kv_benchmark
            kv_config = profile.get("kv_config") or {}
            model_name = kv_config.get("model_name", "custom")

            await db.turboquant_runs.update_one(
                {"run_id": run_id}, {"$set": {"progress": 20}})

            metrics = await run_kv_benchmark(db, profile, model_name=model_name)
            await db.turboquant_runs.update_one(
                {"run_id": run_id}, {"$set": {"progress": 70}})

            baseline_metrics = None
            if run_baseline:
                baseline_profile = {**profile, "bit_width": 32, "enable_residual": False}
                baseline_metrics = await run_kv_benchmark(db, baseline_profile, model_name=model_name)

        else:
            # Vector-index compression path
            from turboquant.vector_runner import run_vector_benchmark

            docs = await db.workspace_memory.find(
                {"workspace_id": ws_id}, {"_id": 0, "embedding": 1, "content": 1}
            ).to_list(500)

            if not docs or not docs[0].get("embedding"):
                texts = [d.get("content", "") for d in docs if d.get("content")]
                if len(texts) < 10:
                    await db.turboquant_runs.update_one(
                        {"run_id": run_id},
                        {"$set": {"status": "failed", "error": "Need 10+ knowledge docs in workspace memory", "updated_at": now_iso()}})
                    return

                # Generate real TF-IDF vectors from document content
                from semantic_memory import _compute_tfidf
                vectors_sparse, vocab = _compute_tfidf(texts)
                dim = min(len(vocab), 256)
                if dim < 8:
                    await db.turboquant_runs.update_one(
                        {"run_id": run_id},
                        {"$set": {"status": "failed", "error": "Vocabulary too small for meaningful compression benchmark", "updated_at": now_iso()}})
                    return
                vectors = np.zeros((len(texts), dim), dtype=np.float32)
                for i, sv in enumerate(vectors_sparse):
                    for k, v in sv.items():
                        if k < dim:
                            vectors[i, k] = v
            else:
                vectors = np.array([d["embedding"] for d in docs], dtype=np.float32)

            await db.turboquant_runs.update_one(
                {"run_id": run_id}, {"$set": {"progress": 30}})

            metrics = await run_vector_benchmark(db, profile, vectors)
            await db.turboquant_runs.update_one(
                {"run_id": run_id}, {"$set": {"progress": 70}})

            baseline_metrics = None
            if run_baseline:
                baseline_profile = {**profile, "bit_width": 32, "enable_residual": False}
                baseline_metrics = await run_vector_benchmark(db, baseline_profile, vectors)

        promo_eval = evaluate_promotion(metrics, profile.get("thresholds", {}))

        await db.turboquant_runs.update_one({"run_id": run_id}, {"$set": {
            "status": "completed", "progress": 100,
            "metrics": metrics, "baseline_metrics": baseline_metrics,
            "promotion_eval": promo_eval,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }})
        logger.info(f"NAVC run {run_id} completed: type={target_type} score={promo_eval.get('score', 0)}")

    except Exception as e:
        logger.error(f"NAVC run {run_id} failed: {e}")
        await db.turboquant_runs.update_one(
            {"run_id": run_id},
            {"$set": {"status": "failed", "error": str(e)[:500], "updated_at": now_iso()}})
