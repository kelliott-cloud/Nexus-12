"""Dojo Scenarios — Built-in scenario definitions for Agent Dojo.

12 pre-built scenarios mapped to BUILTIN_SKILLS taxonomy from
agent_skill_definitions.py. Each scenario defines:
  - Two complementary roles with domain expertise
  - Default inception prompt parameters
  - Recommended configuration (turns, temp, cost cap)
  - Skill alignment for XP progression
"""

BUILTIN_SCENARIOS = {
    "adversarial_code_review": {
        "scenario_id": "dojo_sc_code_review",
        "name": "Adversarial Code Review",
        "description": "A security-focused reviewer critiques code written by a senior developer.",
        "category": "engineering",
        "roles": [
            {"role": "Senior Developer", "is_driver": True,
             "domain": "software engineering, clean code, design patterns",
             "methodology": "writing production-quality code with tests and documentation"},
            {"role": "Security-Focused Code Reviewer", "is_driver": False,
             "domain": "application security, OWASP Top 10, code auditing",
             "methodology": "systematic threat modeling and line-by-line security analysis"},
        ],
        "default_task": {
            "description": "Review and improve the security of a user authentication module.",
            "success_criteria": "All OWASP Top 10 risks identified, mitigations proposed, code revised.",
            "domain": "security",
        },
        "config_defaults": {"max_turns": 30, "cost_cap_usd": 2.0, "temperature": 0.7},
        "skill_alignment": ["code_review", "vulnerability_detection"],
        "is_builtin": True,
    },
    "architecture_debate": {
        "scenario_id": "dojo_sc_architecture",
        "name": "Architecture Debate",
        "description": "Two architects debate microservices vs monolith for a given system.",
        "category": "engineering",
        "roles": [
            {"role": "Microservices Advocate", "is_driver": True,
             "domain": "distributed systems, container orchestration, event-driven design",
             "methodology": "arguing for decomposition, scalability, and team autonomy"},
            {"role": "Monolith Defender", "is_driver": False,
             "domain": "system simplicity, operational cost, data consistency",
             "methodology": "arguing for simplicity, lower ops overhead, and faster iteration"},
        ],
        "default_task": {
            "description": "Design architecture for an e-commerce platform handling 10K orders/day.",
            "success_criteria": "Both sides present tradeoffs, agree on hybrid approach with justification.",
            "domain": "architecture",
        },
        "config_defaults": {"max_turns": 40, "cost_cap_usd": 3.0, "temperature": 0.8},
        "skill_alignment": ["architecture", "devops"],
        "is_builtin": True,
    },
    "tdd_pair_programming": {
        "scenario_id": "dojo_sc_tdd",
        "name": "Test-Driven Pair Programming",
        "description": "Test writer creates tests first, developer writes implementation to pass them.",
        "category": "engineering",
        "roles": [
            {"role": "Test Writer", "is_driver": True,
             "domain": "TDD, pytest, property-based testing",
             "methodology": "writing failing tests first, then verifying implementations"},
            {"role": "Implementation Developer", "is_driver": False,
             "domain": "Python development, algorithm design, clean code",
             "methodology": "writing minimal code to pass tests, then refactoring"},
        ],
        "default_task": {
            "description": "Build a rate limiter with sliding window algorithm using TDD.",
            "success_criteria": "Tests cover edge cases, implementation passes all, code is production-ready.",
            "domain": "testing",
        },
        "config_defaults": {"max_turns": 30, "cost_cap_usd": 2.0, "temperature": 0.5},
        "skill_alignment": ["testing", "code_writing"],
        "is_builtin": True,
    },
    "bug_hunt": {
        "scenario_id": "dojo_sc_debug",
        "name": "Bug Hunt",
        "description": "Bug reporter provides symptoms, debugger diagnoses and fixes.",
        "category": "engineering",
        "roles": [
            {"role": "Bug Reporter", "is_driver": True,
             "domain": "QA, user experience, edge cases",
             "methodology": "providing detailed reproduction steps and system context"},
            {"role": "Debugger", "is_driver": False,
             "domain": "debugging, root cause analysis, performance profiling",
             "methodology": "systematic hypothesis testing and log analysis"},
        ],
        "default_task": {
            "description": "Diagnose intermittent 500 errors in a REST API during peak traffic.",
            "success_criteria": "Root cause identified, fix implemented, prevention strategy documented.",
            "domain": "debugging",
        },
        "config_defaults": {"max_turns": 25, "cost_cap_usd": 1.5, "temperature": 0.6},
        "skill_alignment": ["debugging", "testing"],
        "is_builtin": True,
    },
    "product_requirements": {
        "scenario_id": "dojo_sc_product",
        "name": "Product Requirements Refinement",
        "description": "PM and engineering lead collaborate to refine product requirements.",
        "category": "product",
        "roles": [
            {"role": "Product Manager", "is_driver": True,
             "domain": "user research, market analysis, requirements gathering",
             "methodology": "JTBD framework, user story mapping, MoSCoW prioritization"},
            {"role": "Engineering Lead", "is_driver": False,
             "domain": "technical feasibility, system design, estimation",
             "methodology": "technical spike analysis, complexity estimation, risk assessment"},
        ],
        "default_task": {
            "description": "Define requirements for a real-time collaborative document editor.",
            "success_criteria": "User stories written, constraints identified, MVP scope agreed, effort estimated.",
            "domain": "product_strategy",
        },
        "config_defaults": {"max_turns": 35, "cost_cap_usd": 2.5, "temperature": 0.7},
        "skill_alignment": ["product_strategy", "project_management"],
        "is_builtin": True,
    },
    "research_synthesis": {
        "scenario_id": "dojo_sc_research",
        "name": "Research Synthesis",
        "description": "Researcher presents findings, peer reviewer challenges methodology.",
        "category": "data",
        "roles": [
            {"role": "Primary Researcher", "is_driver": True,
             "domain": "research methodology, literature review, data collection",
             "methodology": "systematic evidence gathering and synthesis"},
            {"role": "Critical Peer Reviewer", "is_driver": False,
             "domain": "statistical rigor, methodology evaluation, bias detection",
             "methodology": "adversarial questioning and constructive critique"},
        ],
        "default_task": {
            "description": "Analyze effectiveness of RAG vs fine-tuning for domain-specific AI assistants.",
            "success_criteria": "Both approaches compared on cost, quality, latency, maintainability with citations.",
            "domain": "research",
        },
        "config_defaults": {"max_turns": 40, "cost_cap_usd": 3.0, "temperature": 0.7},
        "skill_alignment": ["research", "data_analysis"],
        "is_builtin": True,
    },

    # ─── Engineering (continued) ────────────────────────
    "api_design_review": {
        "scenario_id": "dojo_sc_api_design",
        "name": "API Design Review",
        "description": "An API consumer challenges the designer on usability, consistency, and edge cases.",
        "category": "engineering",
        "roles": [
            {"role": "API Consumer (Developer)", "is_driver": True,
             "domain": "frontend/mobile development, developer experience, SDK integration",
             "methodology": "evaluating APIs from the caller's perspective — ergonomics, error handling, discoverability"},
            {"role": "API Designer", "is_driver": False,
             "domain": "REST/GraphQL design, versioning, backward compatibility",
             "methodology": "applying RESTful constraints, OpenAPI spec, and resource modeling"},
        ],
        "default_task": {
            "description": "Design a REST API for a multi-tenant SaaS billing system with subscriptions, invoices, and usage metering.",
            "success_criteria": "Endpoint inventory defined, error contract agreed, pagination/filtering specified, versioning strategy chosen, example payloads provided.",
            "domain": "api_design",
        },
        "config_defaults": {"max_turns": 30, "cost_cap_usd": 2.0, "temperature": 0.6},
        "skill_alignment": ["api_design", "documentation"],
        "is_builtin": True,
    },
    "performance_optimization": {
        "scenario_id": "dojo_sc_performance",
        "name": "Performance Optimization",
        "description": "Performance engineer profiles and optimizes while the app developer provides context.",
        "category": "engineering",
        "roles": [
            {"role": "Application Developer", "is_driver": True,
             "domain": "full-stack development, business logic, feature requirements",
             "methodology": "explaining system behavior, data volumes, and usage patterns"},
            {"role": "Performance Engineer", "is_driver": False,
             "domain": "profiling, caching strategies, query optimization, load testing",
             "methodology": "systematic bottleneck identification using metrics and benchmarks"},
        ],
        "default_task": {
            "description": "Optimize a dashboard page that takes 8 seconds to load with 50K rows of analytics data.",
            "success_criteria": "Root causes identified with evidence, optimizations proposed with expected impact, implementation plan with priority order.",
            "domain": "performance",
        },
        "config_defaults": {"max_turns": 25, "cost_cap_usd": 2.0, "temperature": 0.6},
        "skill_alignment": ["performance", "database"],
        "is_builtin": True,
    },
    "refactoring_workshop": {
        "scenario_id": "dojo_sc_refactor",
        "name": "Refactoring Workshop",
        "description": "Refactoring lead proposes improvements while legacy code defender argues for stability.",
        "category": "engineering",
        "roles": [
            {"role": "Refactoring Lead", "is_driver": True,
             "domain": "code modernization, design patterns, technical debt reduction",
             "methodology": "identifying code smells, proposing incremental refactors with safety nets"},
            {"role": "Legacy Code Defender", "is_driver": False,
             "domain": "production stability, risk assessment, regression prevention",
             "methodology": "challenging each change with risk/reward analysis and backward compatibility concerns"},
        ],
        "default_task": {
            "description": "Refactor a 2000-line monolithic request handler into modular, testable components.",
            "success_criteria": "Refactoring plan with phases, risk assessment per change, test strategy, rollback approach, and estimated effort.",
            "domain": "refactoring",
        },
        "config_defaults": {"max_turns": 35, "cost_cap_usd": 2.5, "temperature": 0.7},
        "skill_alignment": ["refactoring", "architecture"],
        "is_builtin": True,
    },

    # ─── Operations ─────────────────────────────────────
    "compliance_audit": {
        "scenario_id": "dojo_sc_compliance",
        "name": "Compliance Audit",
        "description": "Compliance officer audits while the sysadmin explains current controls.",
        "category": "operations",
        "roles": [
            {"role": "Compliance Officer", "is_driver": True,
             "domain": "GDPR, SOC2, HIPAA, data privacy regulations",
             "methodology": "checklist-driven audit with evidence collection and gap analysis"},
            {"role": "System Administrator", "is_driver": False,
             "domain": "infrastructure security, access controls, logging, encryption",
             "methodology": "explaining implemented controls, providing evidence, proposing remediations"},
        ],
        "default_task": {
            "description": "Conduct a SOC2 Type II readiness audit for a SaaS platform handling PII.",
            "success_criteria": "All trust service criteria reviewed, gaps identified with severity, remediation plan with timelines, evidence requirements documented.",
            "domain": "compliance",
        },
        "config_defaults": {"max_turns": 40, "cost_cap_usd": 3.0, "temperature": 0.5},
        "skill_alignment": ["compliance", "devops"],
        "is_builtin": True,
    },

    # ─── Product & Design (continued) ───────────────────
    "ux_accessibility_review": {
        "scenario_id": "dojo_sc_ux",
        "name": "UX Accessibility Review",
        "description": "Accessibility specialist audits UI while the developer implements fixes.",
        "category": "product",
        "roles": [
            {"role": "Accessibility Specialist", "is_driver": True,
             "domain": "WCAG 2.1 AA/AAA, screen readers, keyboard navigation, color contrast",
             "methodology": "systematic audit against WCAG success criteria with severity ratings"},
            {"role": "UI Developer", "is_driver": False,
             "domain": "React/HTML/CSS, ARIA attributes, semantic HTML, responsive design",
             "methodology": "implementing accessible patterns with progressive enhancement"},
        ],
        "default_task": {
            "description": "Audit and fix accessibility issues in a dashboard with data tables, charts, and modal dialogs.",
            "success_criteria": "WCAG 2.1 AA violations identified, fixes implemented with code, screen reader testing notes, keyboard navigation verified.",
            "domain": "ux_review",
        },
        "config_defaults": {"max_turns": 30, "cost_cap_usd": 2.0, "temperature": 0.6},
        "skill_alignment": ["ux_review", "code_writing"],
        "is_builtin": True,
    },

    # ─── Data & Research (continued) ────────────────────
    "data_analysis_challenge": {
        "scenario_id": "dojo_sc_data",
        "name": "Data Analysis Challenge",
        "description": "Data analyst proposes insights while the statistical reviewer validates methodology.",
        "category": "data",
        "roles": [
            {"role": "Data Analyst", "is_driver": True,
             "domain": "exploratory data analysis, visualization, business metrics",
             "methodology": "hypothesis-driven analysis with clear visualizations and actionable insights"},
            {"role": "Statistical Reviewer", "is_driver": False,
             "domain": "statistical significance, sampling bias, correlation vs causation",
             "methodology": "challenging assumptions, verifying statistical validity, suggesting controls"},
        ],
        "default_task": {
            "description": "Analyze user churn data to identify top 3 predictive factors and propose retention interventions.",
            "success_criteria": "Analysis methodology documented, statistical significance verified, confounders addressed, actionable recommendations with expected impact.",
            "domain": "data_analysis",
        },
        "config_defaults": {"max_turns": 30, "cost_cap_usd": 2.5, "temperature": 0.7},
        "skill_alignment": ["data_analysis", "research"],
        "is_builtin": True,
    },
}


def get_all_scenarios():
    """Return all built-in scenarios."""
    return list(BUILTIN_SCENARIOS.values())


def get_scenario(scenario_id):
    """Look up a scenario by ID."""
    for s in BUILTIN_SCENARIOS.values():
        if s["scenario_id"] == scenario_id:
            return s
    return None
