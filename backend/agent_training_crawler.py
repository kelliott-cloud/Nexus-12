"""Agent Training Crawler — Search the web, fetch pages, extract structured knowledge.

Pipeline: topic -> search queries -> web search -> page fetch -> content extraction -> chunking -> quality scoring
"""
import logging
import re
import uuid
import httpx
from datetime import datetime, timezone
from typing import List, Dict
from urllib.parse import urlparse

logger = logging.getLogger("agent_training_crawler")

HIGH_AUTHORITY_DOMAINS = {
    "docs.python.org", "developer.mozilla.org", "owasp.org", "cloud.google.com",
    "docs.aws.amazon.com", "learn.microsoft.com", "react.dev", "fastapi.tiangolo.com",
    "docs.github.com", "kubernetes.io", "redis.io", "www.mongodb.com",
    "arxiv.org", "en.wikipedia.org", "stackoverflow.com",
}
LOW_AUTHORITY_DOMAINS = {"medium.com", "dev.to", "reddit.com", "quora.com"}

STOP_WORDS = frozenset([
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "can", "shall", "this", "that",
    "these", "those", "i", "you", "he", "she", "it", "we", "they",
    "not", "no", "so", "if", "then", "than", "too", "very", "just",
])

SKIP_PATTERNS = [
    r"cookie.*consent", r"subscribe.*newsletter", r"sign up.*free",
    r"advertisement", r"sponsored content",
]

# Skill -> suggested training topics mapping
SKILL_TOPIC_SUGGESTIONS = {
    "code_review": ["Code review best practices", "SOLID principles", "Clean code patterns", "Code smells catalog"],
    "vulnerability_detection": ["OWASP Top 10 2025", "Common CVE patterns", "Security code review checklists", "SQL injection prevention"],
    "code_writing": ["Design patterns in Python", "TypeScript best practices", "Error handling patterns"],
    "debugging": ["Debugging distributed systems", "Root cause analysis techniques", "Performance profiling"],
    "testing": ["Test-driven development", "Property-based testing", "Integration testing strategies"],
    "architecture": ["Microservices architecture patterns", "Event-driven architecture", "System design fundamentals"],
    "devops": ["Kubernetes best practices", "CI/CD pipeline design", "Infrastructure as code"],
    "database": ["Database indexing strategies", "Query optimization techniques", "NoSQL schema design"],
    "api_design": ["RESTful API design guidelines", "GraphQL best practices", "API versioning strategies"],
    "performance": ["Web performance optimization", "Caching strategies", "Load testing methodologies"],
    "refactoring": ["Refactoring patterns", "Legacy code modernization", "Technical debt management"],
    "product_strategy": ["Product-market fit frameworks", "OKR methodology", "Competitive analysis frameworks"],
    "ux_review": ["WCAG accessibility guidelines", "Usability heuristics", "Mobile UX patterns"],
    "data_analysis": ["Statistical analysis methods", "Data visualization best practices", "A/B testing methodology"],
    "research": ["Research methodology", "Source evaluation criteria", "Literature review techniques"],
    "project_management": ["Agile project management", "Risk management frameworks", "Stakeholder communication"],
    "documentation": ["Technical writing style guide", "API documentation best practices", "README templates"],
    "compliance": ["GDPR compliance checklist", "SOC2 requirements", "Data privacy regulations"],
    "customer_support": ["Customer service best practices", "Escalation frameworks", "Knowledge base design"],
}

DEPTH_LIMITS = {"quick": 3, "standard": 8, "comprehensive": 15}


def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def classify_source_authority(domain: str) -> str:
    if domain in HIGH_AUTHORITY_DOMAINS or domain.endswith(".gov") or domain.endswith(".edu"):
        return "high"
    if domain in LOW_AUTHORITY_DOMAINS:
        return "low"
    return "medium"


def tokenize_for_retrieval(text: str) -> List[str]:
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    text = text.replace('_', ' ')
    tokens = re.findall(r'[a-z0-9]+', text.lower())
    return [t for t in tokens if t not in STOP_WORDS and len(t) > 1]


async def generate_search_queries(topic: str, agent_skills: list, num_queries: int = 5) -> List[str]:
    base_queries = [topic]
    skill_modifiers = {
        "code_review": ["code examples", "best practices", "anti-patterns"],
        "vulnerability_detection": ["security vulnerabilities", "CVE", "prevention"],
        "architecture": ["system design", "architecture patterns", "scalability"],
        "debugging": ["common errors", "debugging techniques", "troubleshooting"],
        "testing": ["test strategies", "test patterns", "coverage"],
        "devops": ["deployment", "CI/CD", "infrastructure"],
        "data_analysis": ["data patterns", "statistical methods", "visualization"],
        "research": ["latest research", "academic papers", "systematic review"],
    }
    active_skills = [s.get("skill_id", "") for s in agent_skills if s.get("priority", 99) <= 2]
    modifiers = []
    for skill in active_skills:
        modifiers.extend(skill_modifiers.get(skill, []))
    for mod in modifiers[:num_queries - 1]:
        base_queries.append(f"{topic} {mod}")
    return base_queries[:num_queries]


async def search_web(db, query: str, num_results: int = 8) -> List[Dict]:
    results = []
    try:
        # Try DuckDuckGo instant answer API (no key needed)
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1&skip_disambig=1")
            data = resp.json()
            if data.get("Abstract"):
                results.append({
                    "title": data.get("Heading", query),
                    "url": data.get("AbstractURL", ""),
                    "snippet": data["Abstract"],
                    "domain": _extract_domain(data.get("AbstractURL", "")),
                })
            for r in data.get("RelatedTopics", [])[:num_results]:
                if isinstance(r, dict) and r.get("FirstURL"):
                    results.append({
                        "title": r.get("Text", "")[:100],
                        "url": r["FirstURL"],
                        "snippet": r.get("Text", ""),
                        "domain": _extract_domain(r["FirstURL"]),
                    })
                elif isinstance(r, dict) and r.get("Topics"):
                    for sub in r["Topics"][:3]:
                        if sub.get("FirstURL"):
                            results.append({
                                "title": sub.get("Text", "")[:100],
                                "url": sub["FirstURL"],
                                "snippet": sub.get("Text", ""),
                                "domain": _extract_domain(sub["FirstURL"]),
                            })
    except Exception as e:
        logger.error(f"Web search failed for '{query}': {e}")
    return results[:num_results]


async def fetch_page_content(url: str) -> Dict:
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "NexusBot/1.0 (Knowledge Training)",
                "Accept": "text/html,application/xhtml+xml",
            })
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}", "url": url}
            html = resp.text
            text = _extract_text_from_html(html)
            title = _extract_title(html)
            return {"url": url, "title": title, "text": text, "length": len(text), "domain": _extract_domain(url)}
    except Exception as e:
        logger.error(f"Page fetch failed for {url}: {e}")
        return {"error": str(e), "url": url}


def _extract_text_from_html(html: str) -> str:
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<(nav|header|footer)[^>]*>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    for pattern in SKIP_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    return text[:50000]


def _extract_title(html: str) -> str:
    match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""


def chunk_content(text: str, title: str = "", max_chunk_size: int = 800, overlap: int = 100) -> List[Dict]:
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip() and len(p.strip()) > 30]
    if not paragraphs:
        paragraphs = [text[i:i + max_chunk_size] for i in range(0, len(text), max_chunk_size - overlap)]
    chunks = []
    current_chunk = ""
    for para in paragraphs:
        if len(current_chunk) + len(para) < max_chunk_size:
            current_chunk += ("\n\n" if current_chunk else "") + para
        else:
            if current_chunk:
                chunks.append(current_chunk)
            if len(para) > max_chunk_size:
                sentences = re.split(r'(?<=[.!?])\s+', para)
                sub_chunk = ""
                for sent in sentences:
                    if len(sub_chunk) + len(sent) < max_chunk_size:
                        sub_chunk += (" " if sub_chunk else "") + sent
                    else:
                        if sub_chunk:
                            chunks.append(sub_chunk)
                        sub_chunk = sent
                current_chunk = sub_chunk if sub_chunk else ""
            else:
                current_chunk = para
    if current_chunk:
        chunks.append(current_chunk)
    return [{"content": c, "index": i, "token_count": len(c.split())} for i, c in enumerate(chunks)]


async def score_chunk_quality(chunk_text: str, topic: str, agent_skills: list = None) -> float:
    score = 0.5
    text_lower = chunk_text.lower()
    topic_lower = topic.lower()
    topic_words = set(topic_lower.split())
    chunk_words = set(text_lower.split())
    overlap = len(topic_words & chunk_words) / max(len(topic_words), 1)
    score += overlap * 0.2
    length = len(chunk_text)
    if 200 < length < 1000:
        score += 0.1
    elif length < 50:
        score -= 0.2
    if "```" in chunk_text or "def " in chunk_text or "function " in chunk_text:
        score += 0.1
    if any(f"{i}." in chunk_text or f"{i})" in chunk_text for i in range(1, 6)):
        score += 0.05
    fluff_words = {"click here", "learn more", "sign up", "subscribe", "advertisement"}
    if any(f in text_lower for f in fluff_words):
        score -= 0.2
    return max(0.0, min(1.0, round(score, 2)))


def classify_category(text: str) -> str:
    lower = text.lower()
    if any(w in lower for w in ["step 1", "step 2", "first,", "then,", "finally,", "how to", "procedure"]):
        return "procedure"
    if any(w in lower for w in ["example", "```", "def ", "function ", "class ", "import "]):
        return "example"
    if any(w in lower for w in ["warning", "danger", "never", "avoid", "don't", "vulnerability", "attack"]):
        return "warning"
    if any(w in lower for w in ["http://", "https://", "api.", "endpoint", "documentation"]):
        return "reference"
    return "concept"


def extract_tags(text: str, topic: str) -> list:
    tokens = tokenize_for_retrieval(text)
    from collections import Counter
    freq = Counter(tokens)
    topic_tokens = tokenize_for_retrieval(topic)
    tags = [t for t, _ in freq.most_common(5) if len(t) > 3]
    tags.extend([t for t in topic_tokens if t not in tags and len(t) > 3][:3])
    return tags[:8]


def get_topic_suggestions(skill_ids: list) -> List[str]:
    """Get suggested training topics based on agent skills."""
    suggestions = []
    for sid in skill_ids:
        suggestions.extend(SKILL_TOPIC_SUGGESTIONS.get(sid, []))
    return list(dict.fromkeys(suggestions))[:15]
