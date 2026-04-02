"""Test Suite — Agent Dojo module.

Tests cover:
  - DojoEngine: session lifecycle, termination detection, stall detection
  - DojoPrompts: inception prompt building, task specification
  - DojoDataExtractor: Q&A extraction, quality scoring, ingestion
  - DojoScenarios: built-in scenario registry
  - Routes: API endpoint contracts

Uses pytest + pytest-asyncio with a mock MongoDB (mongomock or in-memory dict).
"""
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


# ================================================================
# Fixtures
# ================================================================

class FakeCursor:
    """Minimal async cursor for mocking MongoDB find()."""
    def __init__(self, items):
        self._items = items
    def sort(self, *a, **kw): return self
    def limit(self, *a, **kw): return self
    async def to_list(self, *a): return self._items


class FakeCollection:
    """In-memory MongoDB collection mock."""
    def __init__(self):
        self._docs = []

    async def insert_one(self, doc):
        self._docs.append({**doc})

    async def find_one(self, query, projection=None):
        for d in self._docs:
            if all(d.get(k) == v for k, v in query.items() if not isinstance(v, dict)):
                if projection and "_id" in projection and projection["_id"] == 0:
                    return {k: v for k, v in d.items() if k != "_id"}
                return d
        return None

    def find(self, query=None, projection=None):
        results = []
        for d in self._docs:
            if query is None or all(d.get(k) == v for k, v in query.items() if not isinstance(v, dict)):
                if projection and "_id" in projection and projection["_id"] == 0:
                    results.append({k: v for k, v in d.items() if k != "_id"})
                else:
                    results.append(d)
        return FakeCursor(results)

    async def update_one(self, query, update):
        doc = await self.find_one(query)
        if doc and "$set" in update:
            doc.update(update["$set"])
        if doc and "$push" in update:
            for k, v in update["$push"].items():
                doc.setdefault(k, []).append(v)
        if doc and "$inc" in update:
            for k, v in update["$inc"].items():
                parts = k.split(".")
                target = doc
                for p in parts[:-1]:
                    target = target.setdefault(p, {})
                target[parts[-1]] = target.get(parts[-1], 0) + v

    async def count_documents(self, query):
        count = 0
        for d in self._docs:
            if all(d.get(k) == v for k, v in query.items() if not isinstance(v, dict)):
                count += 1
        return count

    async def aggregate(self, pipeline):
        return FakeCursor([])


class FakeDB:
    """Fake database with all Dojo-relevant collections."""
    def __init__(self):
        self.dojo_sessions = FakeCollection()
        self.dojo_scenarios = FakeCollection()
        self.dojo_extracted_data = FakeCollection()
        self.agent_knowledge = FakeCollection()
        self.nexus_agents = FakeCollection()
        self.workspaces = FakeCollection()
        self.users = FakeCollection()
        self.messages = FakeCollection()
        self.workspace_members = FakeCollection()
        self.workspace_budgets = FakeCollection()
        self.projects = FakeCollection()
        self.work_queue = FakeCollection()
        self.reporting_events = FakeCollection()
        self.agent_skills = FakeCollection()


@pytest.fixture
def db():
    return FakeDB()


@pytest.fixture
def sample_session():
    return {
        "session_id": "dojo_ses_test123",
        "workspace_id": "ws_test1",
        "scenario_id": "dojo_sc_code_review",
        "status": "draft",
        "agents": [
            {"agent_id": "agent_dev", "role": "Senior Developer",
             "is_driver": True, "base_model": "claude",
             "domain": "software engineering", "methodology": "clean code"},
            {"agent_id": "agent_reviewer", "role": "Code Reviewer",
             "is_driver": False, "base_model": "chatgpt",
             "domain": "security", "methodology": "threat modeling"},
        ],
        "task": {
            "description": "Review a user auth module for security issues.",
            "success_criteria": "All OWASP Top 10 risks identified.",
            "domain": "security",
        },
        "config": {
            "max_turns": 10,
            "cost_cap_usd": 1.0,
            "turn_timeout_sec": 30,
            "session_timeout_sec": 120,
        },
        "turns": [],
        "turn_count": 0,
        "termination": None,
        "synthetic_data": None,
        "cost_tracking": {"total_cost_usd": 0, "per_agent": {}},
        "created_by": "user_test1",
        "created_at": "2026-03-30T12:00:00Z",
        "updated_at": "2026-03-30T12:00:00Z",
    }


@pytest.fixture
def completed_session_with_turns():
    """A completed session with realistic turn data for extraction tests."""
    return {
        "session_id": "dojo_ses_completed1",
        "workspace_id": "ws_test1",
        "scenario_id": "dojo_sc_code_review",
        "status": "completed",
        "agents": [
            {"agent_id": "agent_dev", "role": "Developer", "is_driver": True, "base_model": "claude"},
            {"agent_id": "agent_rev", "role": "Reviewer", "is_driver": False, "base_model": "chatgpt"},
        ],
        "task": {"description": "Review auth module", "success_criteria": "Security issues fixed", "domain": "security"},
        "config": {"max_turns": 50, "cost_cap_usd": 5.0},
        "turns": [
            {
                "turn_number": 0, "agent_id": "agent_dev", "role": "Developer",
                "content": "[ROLE: Developer] Here is the login function that needs review:\n```python\ndef login(email, password):\n    user = db.users.find_one({'email': email})\n    if user and user['password'] == password:\n        return create_session(user)\n    return None\n```\nPlease identify any security issues. [STATUS: in_progress]",
                "confidence": {"score": 0.8, "level": "high", "signals": []},
                "cost_usd": 0.01, "tokens_in": 200, "tokens_out": 150,
            },
            {
                "turn_number": 1, "agent_id": "agent_rev", "role": "Reviewer",
                "content": "[ROLE: Reviewer] [CONFIDENCE: 95%] I found several critical security issues:\n1. **Plain text password comparison** — passwords must be hashed with bcrypt\n2. **No rate limiting** — vulnerable to brute force attacks\n3. **Timing attack** — string comparison leaks password length\n4. **No input sanitization** — potential NoSQL injection via email field\n\nHere is the fixed implementation:\n```python\nimport bcrypt\nfrom datetime import datetime, timedelta\n\nLOGIN_ATTEMPTS = {}  # In production, use Redis\n\ndef login(email, password):\n    # Rate limiting\n    key = email.lower().strip()\n    attempts = LOGIN_ATTEMPTS.get(key, {'count': 0, 'last': datetime.min})\n    if attempts['count'] >= 5 and (datetime.utcnow() - attempts['last']) < timedelta(minutes=15):\n        raise RateLimitError('Too many attempts')\n    \n    # Input validation\n    if not isinstance(email, str) or not isinstance(password, str):\n        return None\n    \n    user = db.users.find_one({'email': key})\n    if user and bcrypt.checkpw(password.encode(), user['password_hash']):\n        LOGIN_ATTEMPTS.pop(key, None)\n        return create_session(user)\n    \n    # Track failed attempt\n    LOGIN_ATTEMPTS[key] = {'count': attempts['count'] + 1, 'last': datetime.utcnow()}\n    return None\n```\n[STATUS: in_progress]",
                "confidence": {"score": 0.95, "level": "high", "signals": ["explicit: 95%"]},
                "cost_usd": 0.03, "tokens_in": 400, "tokens_out": 500,
            },
            {
                "turn_number": 2, "agent_id": "agent_dev", "role": "Developer",
                "content": "[ROLE: Developer] Excellent review. All four issues are valid. I accept the fixes and have one addition — we should also add:\n5. **Constant-time comparison** for the bcrypt check (bcrypt.checkpw already does this)\n6. **Logging** for failed login attempts for security monitoring\n\nAll OWASP Top 10 risks in this function have been addressed. [CONFIDENCE: 90%] [STATUS: task_complete]",
                "confidence": {"score": 0.9, "level": "high", "signals": ["explicit: 90%"]},
                "cost_usd": 0.02, "tokens_in": 600, "tokens_out": 200,
            },
        ],
        "turn_count": 3,
        "termination": {"reason": "task_complete", "detected_at": "2026-03-30T12:05:00Z"},
        "synthetic_data": None,
        "cost_tracking": {"total_cost_usd": 0.06, "per_agent": {"agent_dev": 0.03, "agent_rev": 0.03}},
        "created_by": "user_test1",
    }


# ================================================================
# DojoEngine Tests
# ================================================================

class TestDojoEngine:

    @pytest.mark.asyncio
    async def test_session_not_found_returns_early(self, db):
        from dojo_engine import DojoEngine
        engine = DojoEngine(db)
        await engine.run_session("nonexistent_session")
        # Should not raise, just return silently

    @pytest.mark.asyncio
    async def test_session_starts_and_updates_status(self, db, sample_session):
        await db.dojo_sessions.insert_one(sample_session)

        from dojo_engine import DojoEngine
        engine = DojoEngine(db)

        # Mock the AI call to return a completion marker immediately
        with patch("dojo_engine.DojoEngine._execute_turn") as mock_turn:
            mock_turn.return_value = {
                "turn_number": 0, "agent_id": "agent_dev",
                "role": "Developer", "base_model": "claude",
                "content": "[ROLE: Developer] Done. [STATUS: task_complete]",
                "confidence": {"score": 0.9, "level": "high", "signals": []},
                "tool_calls": [], "tokens_in": 100, "tokens_out": 50,
                "cost_usd": 0.01, "duration_ms": 500, "timestamp": "2026-03-30T12:00:00Z",
            }
            with patch("dojo_engine.DojoEngine._emit", new_callable=AsyncMock):
                with patch("dojo_data_extractor.extract_training_data", new_callable=AsyncMock, return_value=None):
                    await engine.run_session("dojo_ses_test123")

        session = await db.dojo_sessions.find_one({"session_id": "dojo_ses_test123"})
        assert session["status"] == "completed"
        assert session["termination"]["reason"] == "task_complete"

    @pytest.mark.asyncio
    async def test_cost_cap_terminates_session(self, db, sample_session):
        sample_session["config"]["cost_cap_usd"] = 0.001  # Very low cap
        sample_session["cost_tracking"]["total_cost_usd"] = 0.01  # Already over
        sample_session["status"] = "running"
        await db.dojo_sessions.insert_one(sample_session)

        from dojo_engine import DojoEngine
        engine = DojoEngine(db)
        with patch("dojo_engine.DojoEngine._emit", new_callable=AsyncMock):
            with patch("dojo_data_extractor.extract_training_data", new_callable=AsyncMock, return_value=None):
                await engine.run_session("dojo_ses_test123")

        session = await db.dojo_sessions.find_one({"session_id": "dojo_ses_test123"})
        assert session["status"] == "completed"
        assert "cost_cap" in session["termination"]["reason"]


# ================================================================
# DojoPrompts Tests
# ================================================================

class TestDojoPrompts:

    @pytest.mark.asyncio
    async def test_inception_prompt_contains_role(self, db):
        from dojo_prompts import build_inception_prompt

        agent_def = {
            "agent_id": "agent_1", "role": "Security Reviewer",
            "is_driver": False, "base_model": "claude",
            "domain": "application security", "methodology": "threat modeling",
        }
        all_agents = [
            agent_def,
            {"agent_id": "agent_2", "role": "Developer", "is_driver": True, "base_model": "chatgpt"},
        ]
        task = {"description": "Review auth code", "success_criteria": "All issues found"}

        with patch("dojo_prompts.build_agent_context_block", new_callable=AsyncMock, return_value="[CTX]"):
            prompt = await build_inception_prompt(db, agent_def, all_agents, task, "ws_test")

        assert "Security Reviewer" in prompt
        assert "Developer" in prompt
        assert "Never flip roles" in prompt
        assert "[STATUS: task_complete]" in prompt
        assert "Review auth code" in prompt

    @pytest.mark.asyncio
    async def test_driver_agent_gets_user_inception(self, db):
        from dojo_prompts import build_inception_prompt

        driver = {
            "agent_id": "agent_drv", "role": "PM", "is_driver": True,
            "base_model": "claude", "domain": "product", "methodology": "agile",
        }
        other = {"agent_id": "agent_eng", "role": "Engineer", "is_driver": False, "base_model": "chatgpt"}

        with patch("dojo_prompts.build_agent_context_block", new_callable=AsyncMock, return_value=""):
            prompt = await build_inception_prompt(
                db, driver, [driver, other],
                {"description": "Define PRD", "success_criteria": "PRD complete"}, "ws_test"
            )

        # Driver should get USER_INCEPTION which contains "You drive the task forward"
        assert "drive the task forward" in prompt

    @pytest.mark.asyncio
    async def test_non_driver_gets_assistant_inception(self, db):
        from dojo_prompts import build_inception_prompt

        executor = {
            "agent_id": "agent_ex", "role": "Engineer", "is_driver": False,
            "base_model": "claude", "domain": "coding", "methodology": "TDD",
        }
        driver = {"agent_id": "agent_drv", "role": "PM", "is_driver": True, "base_model": "chatgpt"}

        with patch("dojo_prompts.build_agent_context_block", new_callable=AsyncMock, return_value=""):
            prompt = await build_inception_prompt(
                db, executor, [driver, executor],
                {"description": "Build API", "success_criteria": "API works"}, "ws_test"
            )

        # Non-driver should get ASSISTANT_INCEPTION with "YOUR role's contribution"
        assert "YOUR role" in prompt


# ================================================================
# DojoDataExtractor Tests
# ================================================================

class TestDojoDataExtractor:

    @pytest.mark.asyncio
    async def test_extracts_qa_pairs_from_completed_session(self, db, completed_session_with_turns):
        await db.dojo_sessions.insert_one(completed_session_with_turns)

        from dojo_data_extractor import extract_training_data
        with patch("dojo_data_extractor.ingest_extracted_data", new_callable=AsyncMock):
            ext_id = await extract_training_data(db, "dojo_ses_completed1")

        assert ext_id is not None
        assert ext_id.startswith("dojo_ext_")

        ext = await db.dojo_extracted_data.find_one({"extraction_id": ext_id})
        assert ext is not None
        assert ext["pair_count"] >= 1
        assert ext["avg_quality"] > 0

    @pytest.mark.asyncio
    async def test_skips_incomplete_session(self, db, sample_session):
        sample_session["status"] = "running"
        await db.dojo_sessions.insert_one(sample_session)

        from dojo_data_extractor import extract_training_data
        result = await extract_training_data(db, "dojo_ses_test123")
        assert result is None

    @pytest.mark.asyncio
    async def test_extracts_code_blocks(self, db, completed_session_with_turns):
        await db.dojo_sessions.insert_one(completed_session_with_turns)

        from dojo_data_extractor import extract_training_data
        with patch("dojo_data_extractor.ingest_extracted_data", new_callable=AsyncMock):
            ext_id = await extract_training_data(db, "dojo_ses_completed1")

        ext = await db.dojo_extracted_data.find_one({"extraction_id": ext_id})
        # Should find code blocks in the turns
        code_pairs = [p for p in ext["pairs"] if p["topic"].startswith("code_")]
        assert len(code_pairs) >= 1

    def test_quality_scoring(self):
        from dojo_data_extractor import _score_pair_quality

        # High quality: long answer with code and high confidence
        score = _score_pair_quality(
            "How do I implement rate limiting?",
            "Here is the implementation:\n```python\ndef rate_limit(key):\n    # Check Redis for request count\n    count = redis.incr(key)\n    if count > 100:\n        raise RateLimitError()\n    redis.expire(key, 60)\n```\nThis uses a sliding window approach with Redis for distributed rate limiting.",
            {"confidence": {"score": 0.9, "level": "high", "signals": []}},
        )
        assert score >= 0.5

        # Low quality: very short answer
        score_low = _score_pair_quality(
            "What?",
            "Yes.",
            {"confidence": {"score": 0.3}},
        )
        assert score_low < 0.3

    def test_clean_markers(self):
        from dojo_data_extractor import _clean_markers

        text = "[ROLE: Developer] Here is my code [CONFIDENCE: 85%] [STATUS: in_progress]"
        cleaned = _clean_markers(text)
        assert "[ROLE:" not in cleaned
        assert "[CONFIDENCE:" not in cleaned
        assert "[STATUS:" not in cleaned
        assert "Here is my code" in cleaned


# ================================================================
# DojoScenarios Tests
# ================================================================

class TestDojoScenarios:

    def test_all_12_scenarios_exist(self):
        from dojo_scenarios import get_all_scenarios
        scenarios = get_all_scenarios()
        assert len(scenarios) == 12

    def test_each_scenario_has_required_fields(self):
        from dojo_scenarios import get_all_scenarios
        required = ["scenario_id", "name", "description", "category",
                     "roles", "default_task", "config_defaults",
                     "skill_alignment", "is_builtin"]
        for s in get_all_scenarios():
            for field in required:
                assert field in s, f"Scenario {s.get('name', '?')} missing {field}"
            assert len(s["roles"]) >= 2, f"Scenario {s['name']} needs 2+ roles"
            assert s["is_builtin"] is True

    def test_get_scenario_by_id(self):
        from dojo_scenarios import get_scenario
        s = get_scenario("dojo_sc_code_review")
        assert s is not None
        assert s["name"] == "Adversarial Code Review"

    def test_get_scenario_not_found(self):
        from dojo_scenarios import get_scenario
        assert get_scenario("nonexistent") is None

    def test_all_scenarios_have_driver_and_executor(self):
        from dojo_scenarios import get_all_scenarios
        for s in get_all_scenarios():
            drivers = [r for r in s["roles"] if r.get("is_driver")]
            executors = [r for r in s["roles"] if not r.get("is_driver")]
            assert len(drivers) >= 1, f"Scenario {s['name']} has no driver"
            assert len(executors) >= 1, f"Scenario {s['name']} has no executor"

    def test_skill_alignments_are_valid(self):
        """All skill_alignment IDs should exist in BUILTIN_SKILLS."""
        from dojo_scenarios import get_all_scenarios
        from agent_skill_definitions import BUILTIN_SKILLS
        for s in get_all_scenarios():
            for skill_id in s["skill_alignment"]:
                assert skill_id in BUILTIN_SKILLS, (
                    f"Scenario {s['name']}: skill '{skill_id}' not in BUILTIN_SKILLS"
                )

    def test_categories_are_valid(self):
        from dojo_scenarios import get_all_scenarios
        valid = {"engineering", "product", "data", "operations"}
        for s in get_all_scenarios():
            assert s["category"] in valid, f"Scenario {s['name']}: invalid category {s['category']}"


# ================================================================
# Confidence Scoring Integration Tests
# ================================================================

class TestConfidenceIntegration:

    def test_dojo_confidence_markers_parsed(self):
        from confidence_scoring import estimate_confidence

        response = "[ROLE: Reviewer] [CONFIDENCE: 85%] The code has a SQL injection vulnerability."
        result = estimate_confidence(response)
        assert result["score"] == 0.85
        assert "explicit" in str(result["signals"])

    def test_low_confidence_detected(self):
        from confidence_scoring import estimate_confidence

        response = "I'm not sure about this, but it might be a problem. I'd guess it could cause issues."
        result = estimate_confidence(response)
        assert result["score"] < 0.6


# ================================================================
# Stall Detection Tests
# ================================================================

class TestStallDetection:

    @pytest.mark.asyncio
    async def test_detects_repetitive_turns(self, db):
        session = {
            "session_id": "stall_test",
            "turns": [
                {"content": "Let me review the authentication module for security issues."},
                {"content": "I will now review the authentication module for security issues."},
                {"content": "Reviewing the authentication module for security issues now."},
                {"content": "Let me review the authentication module for security issues."},
            ],
        }
        await db.dojo_sessions.insert_one(session)

        from dojo_engine import DojoEngine
        engine = DojoEngine(db)
        is_stalled = await engine._detect_stall("stall_test", 3)
        assert is_stalled is True

    @pytest.mark.asyncio
    async def test_no_stall_with_diverse_content(self, db):
        session = {
            "session_id": "diverse_test",
            "turns": [
                {"content": "Here is the authentication code with bcrypt hashing."},
                {"content": "I found SQL injection in the email parameter. Fix it."},
                {"content": "Added input sanitization and parameterized queries."},
                {"content": "Good. Now let's add rate limiting to prevent brute force."},
            ],
        }
        await db.dojo_sessions.insert_one(session)

        from dojo_engine import DojoEngine
        engine = DojoEngine(db)
        is_stalled = await engine._detect_stall("diverse_test", 3)
        assert is_stalled is False
