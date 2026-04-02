"""Agent Performance Benchmarks — Automated test conversations to validate training.

Run test suites against agents, score accuracy/quality/knowledge utilization.
"""
import uuid
import logging
import asyncio
from datetime import datetime, timezone
from fastapi import HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional

logger = logging.getLogger(__name__)


class BenchmarkCase(BaseModel):
    question: str = Field(..., min_length=5)
    expected_keywords: List[str] = []
    expected_topic: str = ""
    category: str = "general"


class CreateBenchmarkSuite(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    cases: List[BenchmarkCase] = Field(..., min_length=1, max_length=50)


class RunBenchmarkRequest(BaseModel):
    suite_id: str


def register_benchmark_routes(api_router, db, get_current_user):

    async def _authed_user(request, ws_id):
        user = await get_current_user(request)
        from nexus_utils import require_workspace_access
        await require_workspace_access(db, user, ws_id)
        return user

    @api_router.post("/workspaces/{ws_id}/agents/{agent_id}/benchmarks/suites")
    async def create_benchmark_suite(ws_id: str, agent_id: str, data: CreateBenchmarkSuite, request: Request):
        """Create a reusable benchmark test suite."""
        user = await _authed_user(request, ws_id)
        suite_id = f"bsuite_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        suite = {
            "suite_id": suite_id, "agent_id": agent_id, "workspace_id": ws_id,
            "name": data.name, "created_by": user["user_id"],
            "cases": [c.dict() for c in data.cases],
            "case_count": len(data.cases),
            "created_at": now, "updated_at": now,
        }
        await db.benchmark_suites.insert_one(suite)
        suite.pop("_id", None)
        return suite

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/benchmarks/suites")
    async def list_benchmark_suites(ws_id: str, agent_id: str, request: Request):
        await _authed_user(request, ws_id)
        suites = await db.benchmark_suites.find(
            {"agent_id": agent_id, "workspace_id": ws_id},
            {"_id": 0, "suite_id": 1, "name": 1, "case_count": 1, "created_at": 1}
        ).sort("created_at", -1).limit(20).to_list(20)
        return {"suites": suites}

    @api_router.delete("/workspaces/{ws_id}/agents/{agent_id}/benchmarks/suites/{suite_id}")
    async def delete_benchmark_suite(ws_id: str, agent_id: str, suite_id: str, request: Request):
        await _authed_user(request, ws_id)
        await db.benchmark_suites.delete_one({"suite_id": suite_id, "agent_id": agent_id})
        return {"deleted": suite_id}

    @api_router.post("/workspaces/{ws_id}/agents/{agent_id}/benchmarks/run")
    async def run_benchmark(ws_id: str, agent_id: str, data: RunBenchmarkRequest, request: Request, background_tasks: BackgroundTasks):
        """Run a benchmark suite against the agent."""
        user = await _authed_user(request, ws_id)
        suite = await db.benchmark_suites.find_one({"suite_id": data.suite_id, "agent_id": agent_id}, {"_id": 0})
        if not suite:
            raise HTTPException(404, "Suite not found")

        run_id = f"brun_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        run = {
            "run_id": run_id, "suite_id": data.suite_id, "suite_name": suite["name"],
            "agent_id": agent_id, "workspace_id": ws_id,
            "started_by": user["user_id"], "status": "running",
            "results": [], "summary": {},
            "started_at": now, "completed_at": None,
        }
        await db.benchmark_runs.insert_one(run)
        run.pop("_id", None)

        background_tasks.add_task(_execute_benchmark, db, run_id, agent_id, ws_id, suite)
        return run

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/benchmarks/runs")
    async def list_benchmark_runs(ws_id: str, agent_id: str, request: Request):
        await _authed_user(request, ws_id)
        runs = await db.benchmark_runs.find(
            {"agent_id": agent_id, "workspace_id": ws_id},
            {"_id": 0, "run_id": 1, "suite_name": 1, "status": 1, "summary": 1, "started_at": 1, "completed_at": 1}
        ).sort("started_at", -1).limit(20).to_list(20)
        return {"runs": runs}

    @api_router.get("/workspaces/{ws_id}/agents/{agent_id}/benchmarks/runs/{run_id}")
    async def get_benchmark_run(ws_id: str, agent_id: str, run_id: str, request: Request):
        await _authed_user(request, ws_id)
        run = await db.benchmark_runs.find_one({"run_id": run_id, "agent_id": agent_id}, {"_id": 0})
        if not run:
            raise HTTPException(404, "Run not found")
        return run


async def _execute_benchmark(db, run_id, agent_id, ws_id, suite):
    """Background: run each test case against the agent's knowledge retrieval + scoring."""
    from agent_knowledge_retrieval import retrieve_training_knowledge
    results = []
    total_score = 0

    for i, case in enumerate(suite.get("cases") or []):
        question = case["question"]
        expected_kw = case.get("expected_keywords") or []
        expected_topic = case.get("expected_topic", "")

        try:
            # Retrieve knowledge for this question
            context = await retrieve_training_knowledge(db, agent_id, question, max_chunks=5, max_tokens=2000, min_relevance=0.1)

            # Score: knowledge retrieval quality
            retrieval_score = min(len(context) / 200, 1.0) if context else 0.0

            # Score: keyword coverage
            context_lower = context.lower() if context else ""
            kw_hits = sum(1 for kw in expected_kw if kw.lower() in context_lower)
            keyword_score = (kw_hits / max(len(expected_kw), 1)) if expected_kw else 0.5

            # Score: topic relevance
            topic_score = 0.8 if expected_topic and expected_topic.lower() in context_lower else 0.5 if context else 0.0

            # Combined score
            case_score = round((retrieval_score * 0.3 + keyword_score * 0.4 + topic_score * 0.3) * 100, 1)
            total_score += case_score

            results.append({
                "case_index": i, "question": question, "category": case.get("category", "general"),
                "retrieval_score": round(retrieval_score * 100, 1),
                "keyword_score": round(keyword_score * 100, 1),
                "topic_score": round(topic_score * 100, 1),
                "overall_score": case_score,
                "keywords_found": kw_hits, "keywords_total": len(expected_kw),
                "context_length": len(context) if context else 0,
                "passed": case_score >= 50,
            })
        except Exception as e:
            results.append({
                "case_index": i, "question": question, "category": case.get("category", "general"),
                "retrieval_score": 0, "keyword_score": 0, "topic_score": 0, "overall_score": 0,
                "error": str(e), "passed": False,
            })

    avg_score = round(total_score / max(len(results), 1), 1)
    passed = sum(1 for r in results if r.get("passed"))
    now = datetime.now(timezone.utc).isoformat()

    await db.benchmark_runs.update_one(
        {"run_id": run_id},
        {"$set": {
            "status": "completed", "results": results, "completed_at": now,
            "summary": {
                "total_cases": len(results), "passed": passed, "failed": len(results) - passed,
                "avg_score": avg_score, "pass_rate": round(passed / max(len(results), 1) * 100, 1),
            },
        }}
    )
    logger.info(f"Benchmark {run_id}: {passed}/{len(results)} passed, avg={avg_score}")
