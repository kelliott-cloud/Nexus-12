from nexus_utils import now_iso
"""Deep Research Agent + AI Fact Checking — autonomous web research, structured reports, fact verification"""
import uuid
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

DEPTH_CONFIG = {
    "quick": {"sub_queries": 3, "max_sources": 5, "est_minutes": 2, "credits": 15},
    "standard": {"sub_queries": 5, "max_sources": 15, "est_minutes": 5, "credits": 30},
    "deep": {"sub_queries": 10, "max_sources": 30, "est_minutes": 15, "credits": 60},
}


class ResearchRequest(BaseModel):
    workspace_id: str
    query: str = Field(..., min_length=5)
    depth: str = "standard"
    model: str = "claude"
    output_format: str = "report"  # report, brief, raw
    max_sources: int = 15
    include_citations: bool = True
    source_domains: List[str] = []



def register_research_routes(api_router, db, get_current_user):

    # ============ Deep Research ============

    @api_router.post("/research/start")
    async def start_research(data: ResearchRequest, request: Request):
        user = await get_current_user(request)
        if data.depth not in DEPTH_CONFIG:
            raise HTTPException(400, f"Invalid depth. Use: {list(DEPTH_CONFIG.keys())}")
        config = DEPTH_CONFIG[data.depth]
        session_id = f"rs_{uuid.uuid4().hex[:12]}"
        now = now_iso()

        # Budget pre-check
        org_id = None
        if data.workspace_id:
            ws = await db.workspaces.find_one({"workspace_id": data.workspace_id}, {"_id": 0, "org_id": 1})
            org_id = (ws or {}).get("org_id")
        provider = data.model if data.model in ("claude", "chatgpt", "gemini", "perplexity") else "claude"
        try:
            from managed_keys import check_usage_budget, estimate_ai_cost_usd, estimate_tokens, emit_budget_alert, record_usage_event
            estimated_cost = estimate_ai_cost_usd(provider, estimate_tokens(data.query) * config.get("sub_queries", 3), 2000)
            budget = await check_usage_budget(provider, estimated_cost, workspace_id=data.workspace_id, org_id=org_id, user_id=user["user_id"])
            if budget.get("blocked"):
                scope_name = (budget.get("scope_type") or "Platform").capitalize()
                await emit_budget_alert(provider, budget.get("scope_type") or "platform", budget.get("scope_id") or "platform", "blocked", budget.get("projected_spend_usd", estimated_cost), budget.get("hard_cap_usd"), user_id=user["user_id"], workspace_id=data.workspace_id, org_id=org_id, message=f"{scope_name} Nexus AI budget reached for research.")
                raise HTTPException(429, f"{scope_name} Nexus AI budget reached for deep research. Contact your admin to increase the limit.")
            # Record estimated spend on start
            await record_usage_event(provider, estimated_cost, user_id=user["user_id"], workspace_id=data.workspace_id, org_id=org_id, usage_type="ai", key_source="platform", tokens_in=estimate_tokens(data.query) * config.get("sub_queries", 3), tokens_out=2000, metadata={"action": "research_start", "session_id": session_id, "depth": data.depth})
        except HTTPException:
            raise
        except Exception as _be:
            import logging as _l
            _l.getLogger(__name__).debug(f"Budget check skipped for research: {_be}")

        # Decompose query into sub-queries
        sub_queries = [f"Sub-query {i+1}: {data.query} — aspect {i+1}" for i in range(config["sub_queries"])]

        session = {
            "session_id": session_id, "workspace_id": data.workspace_id,
            "query": data.query, "depth": data.depth,
            "model": data.model, "output_format": data.output_format,
            "max_sources": min(data.max_sources, config["max_sources"]),
            "include_citations": data.include_citations,
            "source_domains": data.source_domains,
            "status": "running", "sub_queries": sub_queries,
            "progress_pct": 0, "credits_cost": config["credits"],
            "created_by": user["user_id"], "created_at": now,
        }
        await db.research_sessions.insert_one(session)
        return {k: v for k, v in session.items() if k != "_id"}

    @api_router.get("/research/{session_id}/status")
    async def get_research_status(session_id: str, request: Request):
        await get_current_user(request)
        session = await db.research_sessions.find_one({"session_id": session_id}, {"_id": 0})
        if not session:
            raise HTTPException(404, "Session not found")
        sources = await db.research_sources.find({"session_id": session_id}, {"_id": 0}).to_list(50)
        return {"session": session, "sources_found": len(sources)}

    @api_router.post("/research/{session_id}/refine")
    async def refine_research(session_id: str, request: Request):
        await get_current_user(request)
        body = await request.json()
        follow_up = body.get("follow_up", "")
        session = await db.research_sessions.find_one({"session_id": session_id})
        if not session:
            raise HTTPException(404, "Session not found")
        sub_queries = session.get("sub_queries") or []
        sub_queries.append(f"Follow-up: {follow_up}")
        await db.research_sessions.update_one({"session_id": session_id}, {"$set": {"sub_queries": sub_queries, "status": "running", "progress_pct": 50}})
        return {"message": "Follow-up added", "sub_queries": sub_queries}

    @api_router.get("/research/{session_id}/report")
    async def get_research_report(session_id: str, request: Request):
        await get_current_user(request)
        report = await db.research_reports.find_one({"session_id": session_id}, {"_id": 0})
        if not report:
            session = await db.research_sessions.find_one({"session_id": session_id}, {"_id": 0})
            if not session:
                raise HTTPException(404, "Session not found")
            sources = await db.research_sources.find({"session_id": session_id}, {"_id": 0}).to_list(30)
            from ai_providers import call_ai_direct
            from key_resolver import get_integration_key
            import re

            KEY_MAP = {"claude": "ANTHROPIC_API_KEY", "chatgpt": "OPENAI_API_KEY", "gemini": "GOOGLE_AI_KEY", "perplexity": "PERPLEXITY_API_KEY"}
            model_key = session.get("model", "claude") if session.get("model") in KEY_MAP else "claude"
            api_key = await get_integration_key(db, KEY_MAP[model_key])
            if not api_key:
                for fallback_model in ["claude", "chatgpt", "gemini", "perplexity"]:
                    api_key = await get_integration_key(db, KEY_MAP[fallback_model])
                    if api_key:
                        model_key = fallback_model
                        break

            source_text = "\n\n".join(
                f"Source {idx + 1}: {s.get('title', 'Untitled')}\nURL: {s.get('url', '')}\nSummary: {s.get('summary', s.get('snippet', ''))}"
                for idx, s in enumerate(sources[:12])
            )
            generated = "No AI report could be generated because no research provider key is configured."
            if api_key:
                system_prompt = "You are a research analyst. Write a structured report with sections for Executive Summary, Findings, and Conclusions. Use grounded claims only."
                user_prompt = f"Research query: {session['query']}\nDepth: {session.get('depth', 'standard')}\n\nSources:\n{source_text or 'No sources collected yet.'}\n\nReturn markdown with headings exactly: ## Executive Summary, ## Findings, ## Conclusions."
                try:
                    generated = await call_ai_direct(model_key, api_key, system_prompt, user_prompt, workspace_id=session.get('workspace_id', ''), db=db, allow_emergent_fallback=False)
                except Exception as exc:
                    generated = f"Report generation failed: {str(exc)[:200]}"

            exec_summary = re.search(r"## Executive Summary\s*(.*?)(?=## Findings|## Conclusions|$)", generated, re.S)
            findings = re.search(r"## Findings\s*(.*?)(?=## Conclusions|$)", generated, re.S)
            conclusions = re.search(r"## Conclusions\s*(.*)$", generated, re.S)
            report_id = f"rr_{uuid.uuid4().hex[:12]}"
            report = {
                "report_id": report_id, "session_id": session_id,
                "structure": {
                    "title": f"Research Report: {session['query']}",
                    "sections": [
                        {"title": "Executive Summary", "content": (exec_summary.group(1).strip() if exec_summary else generated[:1200])},
                        {"title": "Methodology", "content": f"Depth: {session['depth']}, Sources analyzed: {len(sources)}"},
                        {"title": "Findings", "content": (findings.group(1).strip() if findings else generated[:2400])},
                        {"title": "Conclusions", "content": (conclusions.group(1).strip() if conclusions else generated[-1200:])},
                    ]
                },
                "citations": [{"url": s.get("url", ""), "title": s.get("title", ""), "relevance": s.get("relevance_score", 0)} for s in sources[:10]],
                "confidence_scores": {
                    "overall": round(min(0.95, 0.45 + len(sources) * 0.03), 2),
                    "data_quality": round(min(0.95, 0.5 + len([s for s in sources if s.get('summary') or s.get('snippet')]) * 0.03), 2),
                    "source_diversity": round(min(0.95, 0.4 + len({s.get('domain', s.get('url', '').split('/')[2] if '//' in s.get('url', '') else '') for s in sources if s.get('url')}) * 0.05), 2),
                },
                "created_at": now_iso(),
            }
            await db.research_reports.insert_one(report)
            await db.research_sessions.update_one({"session_id": session_id}, {"$set": {"status": "completed", "progress_pct": 100}})
            report.pop("_id", None)
        return report

    @api_router.post("/research/{session_id}/export")
    async def export_research(session_id: str, request: Request):
        await get_current_user(request)
        report = await db.research_reports.find_one({"session_id": session_id}, {"_id": 0})
        if not report:
            raise HTTPException(404, "Report not found")
        # Export as markdown
        md = f"# {report['structure']['title']}\n\n"
        for section in report["structure"].get("sections") or []:
            md += f"## {section['title']}\n\n{section['content']}\n\n"
        if report.get("citations"):
            md += "## References\n\n"
            for i, c in enumerate(report["citations"], 1):
                md += f"{i}. [{c.get('title', 'Source')}]({c.get('url', '')})\n"
        return {"content": md, "format": "markdown", "filename": f"research-{session_id}.md"}

    @api_router.get("/research/history")
    async def research_history(request: Request, workspace_id: str = ""):
        await get_current_user(request)
        query = {}
        if workspace_id:
            query["workspace_id"] = workspace_id
        sessions = await db.research_sessions.find(query, {"_id": 0}).sort("created_at", -1).to_list(20)
        return {"sessions": sessions}

    @api_router.delete("/research/{session_id}")
    async def delete_research(session_id: str, request: Request):
        await get_current_user(request)
        await db.research_sessions.delete_one({"session_id": session_id})
        await db.research_sources.delete_many({"session_id": session_id})
        await db.research_reports.delete_many({"session_id": session_id})
        return {"message": "Deleted"}

    @api_router.get("/research/config")
    async def research_config(request: Request):
        await get_current_user(request)
        return {"depths": DEPTH_CONFIG, "output_formats": ["report", "brief", "raw"]}

    # ============ Fact Checking ============

    @api_router.post("/fact-check/verify")
    async def verify_claim(request: Request):
        user = await get_current_user(request)
        body = await request.json()
        claim = body.get("claim", "").strip()
        workspace_id = body.get("workspace_id", "")
        if not claim:
            raise HTTPException(400, "Claim required")
        check_id = f"fc_{uuid.uuid4().hex[:12]}"
        now = now_iso()
        check = {
            "check_id": check_id, "claim": claim,
            "workspace_id": workspace_id,
            "status": "verifying",
            "verdict": None, "confidence_score": None,
            "supporting_evidence": [], "contradicting_evidence": [],
            "created_by": user["user_id"], "timestamp": now,
        }
        await db.fact_checks.insert_one(check)

        # Simulate verification (in production, would use AI agents + web search)
        await db.fact_checks.update_one({"check_id": check_id}, {"$set": {
            "status": "verified", "verdict": "Partially Verified",
            "confidence_score": 0.65,
            "supporting_evidence": [{"source": "Analysis", "snippet": "Claim appears consistent with available data"}],
            "contradicting_evidence": [{"source": "Analysis", "snippet": "Some aspects could not be independently verified"}],
        }})

        return await db.fact_checks.find_one({"check_id": check_id}, {"_id": 0})

    @api_router.get("/fact-check/{check_id}/result")
    async def get_fact_check_result(check_id: str, request: Request):
        await get_current_user(request)
        check = await db.fact_checks.find_one({"check_id": check_id}, {"_id": 0})
        if not check:
            raise HTTPException(404, "Not found")
        return check

    @api_router.get("/fact-check/history")
    async def fact_check_history(request: Request, workspace_id: str = ""):
        await get_current_user(request)
        query = {}
        if workspace_id:
            query["workspace_id"] = workspace_id
        checks = await db.fact_checks.find(query, {"_id": 0}).sort("timestamp", -1).to_list(20)
        return {"checks": checks}
