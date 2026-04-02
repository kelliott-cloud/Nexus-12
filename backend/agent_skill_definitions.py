"""Skill taxonomy and builtin definitions for the Agent Skills Matrix."""

SKILL_CATEGORIES = {
    "engineering": {"label": "Engineering", "color": "#3B82F6", "icon": "code"},
    "product": {"label": "Product & Design", "color": "#8B5CF6", "icon": "palette"},
    "data": {"label": "Data & Research", "color": "#10B981", "icon": "bar-chart-3"},
    "operations": {"label": "Operations", "color": "#F59E0B", "icon": "settings"},
    "marketing": {"label": "Marketing & Growth", "color": "#EC4899", "icon": "megaphone"},
    "finance": {"label": "Finance & Legal", "color": "#F97316", "icon": "landmark"},
}

BUILTIN_SKILLS = {
    # === Engineering ===
    "code_review": {
        "skill_id": "code_review", "category": "engineering", "name": "Code Review",
        "description": "Analyze code for bugs, patterns, performance, and best practices",
        "icon": "search-code", "color": "#3B82F6",
        "recommended_tools": ["repo_read_file", "repo_list_files", "create_task", "log_decision"],
        "prompt_injection": {
            "novice": "Check code for basic syntax errors and unused variables.",
            "intermediate": "Analyze code for DRY violations, error handling gaps, edge cases, and suggest refactoring.",
            "advanced": "Deep code review: architecture decisions, concurrency issues, algorithm complexity, security patterns, design pattern improvements.",
            "expert": "Elite code review: SOLID violations, OWASP Top 10, performance bottlenecks, race conditions, memory leaks, API design flaws, test coverage gaps, dependency risks. Provide severity-ranked findings with exact line references and fix code.",
            "master": "Comprehensive security-aware code audit at staff engineer level. Identify systemic issues, architectural debt, supply chain risks. Cross-reference CVE databases.",
        },
        "assessment_prompts": [
            {"prompt": "Review this function:\n```python\ndef transfer(from_acc, to_acc, amount):\n  from_acc.balance -= amount\n  to_acc.balance += amount\n  db.save(from_acc)\n  db.save(to_acc)\n```", "expected_findings": ["no transaction/atomicity", "no balance validation", "no error handling", "race condition"], "difficulty": "intermediate", "max_score": 4},
            {"prompt": "Review this authentication code:\n```python\ndef login(email, password):\n  user = db.users.find_one({'email': email})\n  if user and user['password'] == password:\n    return create_session(user)\n  return None\n```", "expected_findings": ["plain text password comparison", "no rate limiting", "timing attack", "no input sanitization"], "difficulty": "advanced", "max_score": 4},
        ],
        "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}},
    },
    "code_writing": {
        "skill_id": "code_writing", "category": "engineering", "name": "Code Writing",
        "description": "Write production-quality, well-tested code",
        "icon": "code", "color": "#2563EB",
        "recommended_tools": ["repo_write_file", "repo_read_file", "execute_code", "create_task"],
        "prompt_injection": {
            "novice": "Write simple, readable code with basic comments.",
            "intermediate": "Write well-structured code with error handling, input validation, and meaningful names.",
            "advanced": "Write production code with comprehensive error handling, logging, tests, type hints, and documentation.",
            "expert": "Write enterprise-grade code: design patterns, SOLID principles, comprehensive tests, performance-conscious, security-aware, fully documented.",
            "master": "Write architecture-defining code: extensible, backward-compatible, framework-quality with benchmarks, property-based tests, and security hardening.",
        },
        "assessment_prompts": [],
        "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}},
    },
    "debugging": {
        "skill_id": "debugging", "category": "engineering", "name": "Debugging",
        "description": "Identify and fix bugs from logs and code",
        "icon": "bug", "color": "#DC2626",
        "recommended_tools": ["repo_read_file", "execute_code", "search_channels", "log_decision"],
        "prompt_injection": {
            "novice": "Look for obvious errors in logs and stack traces.",
            "intermediate": "Trace bugs through call stacks, check edge cases and data flow.",
            "advanced": "Deep debugging: reproduce issues, analyze race conditions, memory leaks, and subtle logic errors.",
            "expert": "Expert debugging: root cause analysis across distributed systems, analyze core dumps, performance profiling, and intermittent failure patterns.",
            "master": "Master debugger: diagnose production incidents, post-mortem analysis, identify systemic failure patterns, and design prevention strategies.",
        },
        "assessment_prompts": [],
        "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}},
    },
    "testing": {
        "skill_id": "testing", "category": "engineering", "name": "Test Writing",
        "description": "Write unit, integration, and E2E tests",
        "icon": "test-tube", "color": "#16A34A",
        "recommended_tools": ["repo_write_file", "repo_read_file", "execute_code", "create_task"],
        "prompt_injection": {
            "novice": "Write basic unit tests for happy path scenarios.",
            "intermediate": "Write tests covering edge cases, error paths, and boundary conditions.",
            "advanced": "Write comprehensive test suites: unit, integration, mocking, fixtures, and parameterized tests.",
            "expert": "Expert testing: property-based tests, mutation testing, performance benchmarks, security tests, and CI pipeline integration.",
            "master": "Master testing: design testing strategies, define coverage standards, create test frameworks, and establish organization-wide testing culture.",
        },
        "assessment_prompts": [],
        "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}},
    },
    "architecture": {
        "skill_id": "architecture", "category": "engineering", "name": "System Design",
        "description": "Design system architecture and patterns",
        "icon": "layout", "color": "#7C3AED",
        "recommended_tools": ["wiki_write_page", "create_task", "log_decision", "create_project_plan"],
        "prompt_injection": {
            "novice": "Suggest basic architecture patterns for simple applications.",
            "intermediate": "Design modular systems with clear separation of concerns and standard patterns.",
            "advanced": "Architect distributed systems: microservices, event-driven, CQRS, considering scalability and fault tolerance.",
            "expert": "Expert architect: design for scale (millions of users), multi-region deployment, zero-downtime migration, cost optimization, and security-first architecture.",
            "master": "Principal architect: define technical vision, evaluate build-vs-buy, design platform foundations, and mentor architecture decisions across the organization.",
        },
        "assessment_prompts": [],
        "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}},
    },
    "devops": {
        "skill_id": "devops", "category": "engineering", "name": "DevOps & CI/CD",
        "description": "Infrastructure, deployment, pipelines",
        "icon": "server", "color": "#0891B2",
        "recommended_tools": ["execute_code", "repo_write_file", "repo_read_file", "create_task"],
        "prompt_injection": {
            "expert": "Expert DevOps: design CI/CD pipelines, Kubernetes deployments, infrastructure-as-code (Terraform/Pulumi), monitoring/alerting (Prometheus/Grafana), security scanning, and zero-downtime deployment strategies.",
        },
        "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}},
    },
    "database": {
        "skill_id": "database", "category": "engineering", "name": "Database Design",
        "description": "Schema design, queries, optimization",
        "icon": "database", "color": "#0D9488",
        "recommended_tools": ["execute_code", "repo_write_file", "log_decision", "create_task"],
        "prompt_injection": {
            "expert": "Expert DBA: design normalized schemas, write optimized queries, plan indexes, handle migrations, implement sharding strategies, and design for high-throughput read/write patterns.",
        },
        "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}},
    },
    "api_design": {
        "skill_id": "api_design", "category": "engineering", "name": "API Design",
        "description": "RESTful/GraphQL API design",
        "icon": "globe", "color": "#4F46E5",
        "recommended_tools": ["repo_write_file", "repo_read_file", "wiki_write_page", "log_decision"],
        "prompt_injection": {
            "expert": "Expert API designer: design RESTful APIs with proper resource naming, pagination, versioning, rate limiting, authentication, error handling, and comprehensive OpenAPI documentation.",
        },
        "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}},
    },
    "vulnerability_detection": {
        "skill_id": "vulnerability_detection", "category": "engineering", "name": "Security Analysis",
        "description": "Find security vulnerabilities in code and infrastructure",
        "icon": "shield-alert", "color": "#EF4444",
        "recommended_tools": ["repo_read_file", "repo_list_files", "web_search", "send_alert", "log_decision"],
        "prompt_injection": {
            "expert": "Security specialist: analyze for injection attacks (SQL, XSS, command), authentication bypasses, authorization flaws, cryptographic weaknesses, SSRF, path traversal, deserialization attacks, race conditions, and supply chain vulnerabilities. Rate findings by CVSS score with PoC exploit steps and remediation code.",
        },
        "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}},
    },
    "performance": {
        "skill_id": "performance", "category": "engineering", "name": "Performance Optimization",
        "description": "Profiling, optimization, caching",
        "icon": "gauge", "color": "#EA580C",
        "recommended_tools": ["repo_read_file", "execute_code", "log_decision", "create_task"],
        "prompt_injection": {
            "expert": "Performance expert: profile applications, identify bottlenecks, optimize algorithms, implement caching strategies, reduce memory usage, and design for high-throughput low-latency systems.",
        },
        "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}},
    },
    "refactoring": {
        "skill_id": "refactoring", "category": "engineering", "name": "Refactoring",
        "description": "Code improvement without changing behavior",
        "icon": "git-branch", "color": "#A855F7",
        "recommended_tools": ["repo_read_file", "repo_write_file", "execute_code", "create_task"],
        "prompt_injection": {
            "expert": "Refactoring expert: identify code smells, extract methods/classes, apply design patterns, reduce complexity, improve naming, and ensure behavioral preservation through comprehensive tests.",
        },
        "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}},
    },
    # === Product & Design ===
    "product_strategy": {
        "skill_id": "product_strategy", "category": "product", "name": "Product Strategy",
        "description": "Market analysis, roadmapping, prioritization",
        "icon": "target", "color": "#8B5CF6",
        "recommended_tools": ["wiki_write_page", "create_task", "create_project_plan", "log_decision"],
        "prompt_injection": {
            "expert": "Senior PM: analyze market positioning, prioritize features using RICE/ICE frameworks, define OKRs, create roadmaps, and balance technical debt with feature delivery.",
        },
        "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}},
    },
    "ux_review": {
        "skill_id": "ux_review", "category": "product", "name": "UX Review",
        "description": "Usability analysis, accessibility audit",
        "icon": "layout-template", "color": "#A78BFA",
        "recommended_tools": ["web_search", "wiki_write_page", "create_task", "log_decision"],
        "prompt_injection": {
            "expert": "UX expert: evaluate interfaces for usability heuristics, WCAG accessibility compliance, cognitive load, information architecture, and interaction design patterns.",
        },
        "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}},
    },
    "copywriting": {
        "skill_id": "copywriting", "category": "product", "name": "Copywriting",
        "description": "Marketing copy, microcopy, CTAs",
        "icon": "pencil-line", "color": "#C084FC",
        "recommended_tools": ["wiki_write_page", "web_search", "log_decision"],
        "prompt_injection": {
            "expert": "Expert copywriter: craft compelling headlines, persuasive CTAs, clear microcopy, brand-consistent messaging, and A/B test variations. Optimize for conversion and clarity.",
        },
        "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}},
    },
    "wireframing": {
        "skill_id": "wireframing", "category": "product", "name": "Wireframing",
        "description": "UI layouts, user flows, mockups",
        "icon": "frame", "color": "#D946EF",
        "recommended_tools": ["wiki_write_page", "repo_write_file", "log_decision"],
        "prompt_injection": {
            "expert": "Expert wireframer: design UI layouts with clear visual hierarchy, responsive breakpoints, component reuse, and user flow optimization. Describe layouts in structured detail.",
        },
        "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}},
    },
    "user_research": {
        "skill_id": "user_research", "category": "product", "name": "User Research",
        "description": "Persona creation, interview guides, surveys",
        "icon": "users", "color": "#EC4899",
        "recommended_tools": ["wiki_write_page", "web_search", "create_task", "log_decision"],
        "prompt_injection": {
            "expert": "Expert researcher: design user interviews, create personas, analyze qualitative data, build empathy maps, and translate findings into actionable product requirements.",
        },
        "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}},
    },
    # === Data & Research ===
    "data_analysis": {
        "skill_id": "data_analysis", "category": "data", "name": "Data Analysis",
        "description": "Statistical analysis, trends, insights",
        "icon": "bar-chart-3", "color": "#10B981",
        "recommended_tools": ["execute_code", "repo_read_file", "wiki_write_page", "log_decision"],
        "prompt_injection": {
            "expert": "Expert data analyst: perform statistical analysis, identify trends, create visualizations, build dashboards, and translate data into actionable business insights.",
        },
        "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}},
    },
    "research": {
        "skill_id": "research", "category": "data", "name": "Research & Synthesis",
        "description": "Deep research with source evaluation and synthesis",
        "icon": "book-open", "color": "#059669",
        "recommended_tools": ["web_search", "search_channels", "wiki_write_page", "log_decision"],
        "prompt_injection": {
            "expert": "Senior research analyst: evaluate source credibility, cross-reference claims, identify consensus vs controversy, provide confidence levels, and synthesize into actionable recommendations with citations.",
        },
        "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}},
    },
    "web_search": {
        "skill_id": "web_search", "category": "data", "name": "Web Intelligence",
        "description": "Find and synthesize web information",
        "icon": "search", "color": "#14B8A6",
        "recommended_tools": ["web_search", "wiki_write_page", "log_decision"],
        "prompt_injection": {
            "expert": "Web intelligence expert: formulate precise search queries, evaluate source reliability, synthesize information from multiple sources, and present structured findings with proper attribution.",
        },
        "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}},
    },
    "report_writing": {
        "skill_id": "report_writing", "category": "data", "name": "Report Writing",
        "description": "Structured reports, executive summaries",
        "icon": "file-text", "color": "#0D9488",
        "recommended_tools": ["wiki_write_page", "repo_write_file", "log_decision"],
        "prompt_injection": {
            "expert": "Expert report writer: create structured reports with executive summaries, data visualization recommendations, clear methodology sections, and actionable conclusions.",
        },
        "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}},
    },
    "competitive_analysis": {
        "skill_id": "competitive_analysis", "category": "data", "name": "Competitive Analysis",
        "description": "Market positioning, feature comparison",
        "icon": "swords", "color": "#047857",
        "recommended_tools": ["web_search", "wiki_write_page", "create_task", "log_decision"],
        "prompt_injection": {
            "expert": "Competitive intelligence expert: analyze competitor products, identify market gaps, compare feature matrices, evaluate pricing strategies, and recommend differentiation opportunities.",
        },
        "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}},
    },
    # === Operations ===
    "project_management": {
        "skill_id": "project_management", "category": "operations", "name": "Project Management",
        "description": "Task breakdown, timeline, coordination",
        "icon": "kanban", "color": "#F59E0B",
        "recommended_tools": ["create_task", "list_tasks", "create_project_plan", "create_milestone", "handoff_to_agent"],
        "prompt_injection": {
            "expert": "Senior TPM: break work into atomic tasks with acceptance criteria, estimate effort, identify dependencies, assign to best-suited agents, and track progress. Use Gantt-aware scheduling. Escalate blockers immediately.",
        },
        "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}},
    },
    "documentation": {
        "skill_id": "documentation", "category": "operations", "name": "Documentation",
        "description": "Technical writing, guides, runbooks",
        "icon": "book", "color": "#D97706",
        "recommended_tools": ["wiki_write_page", "wiki_read_page", "repo_read_file", "log_decision"],
        "prompt_injection": {
            "expert": "Expert technical writer: create comprehensive documentation with clear structure, code examples, diagrams, troubleshooting guides, and API references. Optimize for searchability and developer experience.",
        },
        "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}},
    },
    "translation": {
        "skill_id": "translation", "category": "operations", "name": "Translation",
        "description": "Multi-language translation and localization",
        "icon": "languages", "color": "#CA8A04",
        "recommended_tools": ["wiki_write_page", "repo_write_file"],
        "prompt_injection": {
            "expert": "Expert translator: provide culturally-aware translations, adapt idioms, maintain technical accuracy, handle RTL languages, and ensure UI string constraints are met.",
        },
        "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}},
    },
    "customer_support": {
        "skill_id": "customer_support", "category": "operations", "name": "Customer Support",
        "description": "Issue resolution, FAQs, escalation",
        "icon": "headphones", "color": "#EA580C",
        "recommended_tools": ["search_channels", "wiki_read_page", "create_task", "send_alert"],
        "prompt_injection": {
            "expert": "Expert support agent: diagnose issues quickly, provide step-by-step solutions, know when to escalate, maintain empathetic tone, and document resolutions for knowledge base.",
        },
        "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}},
    },
    "compliance": {
        "skill_id": "compliance", "category": "operations", "name": "Compliance & Legal",
        "description": "Regulatory review, policy drafting",
        "icon": "scale", "color": "#B45309",
        "recommended_tools": ["web_search", "wiki_write_page", "log_decision", "send_alert"],
        "prompt_injection": {
            "expert": "Compliance expert: review for GDPR, SOC2, HIPAA, PCI-DSS requirements, draft privacy policies, evaluate data handling practices, and identify regulatory risks with remediation recommendations.",
        },
        "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}},
    },
    # ============ NEW: Engineering Skills ============
    "frontend_development": {"skill_id": "frontend_development", "category": "engineering", "name": "Frontend Development", "description": "Build responsive, accessible, performant web interfaces", "icon": "monitor", "color": "#6366F1", "recommended_tools": ["repo_write_file", "repo_read_file", "execute_code", "create_task"], "prompt_injection": {"expert": "Expert frontend dev: React/Vue/Svelte component architecture, state management, responsive design, accessibility (WCAG 2.1 AA), performance optimization (Core Web Vitals), SSR/SSG, design system implementation, and cross-browser testing."}, "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}}},
    "mobile_development": {"skill_id": "mobile_development", "category": "engineering", "name": "Mobile Development", "description": "iOS, Android, and cross-platform mobile apps", "icon": "smartphone", "color": "#A855F7", "recommended_tools": ["repo_write_file", "repo_read_file", "execute_code", "create_task"], "prompt_injection": {"expert": "Expert mobile dev: React Native/Flutter/Swift/Kotlin, offline-first architecture, push notifications, deep linking, app store optimization, mobile-specific security (certificate pinning, biometrics), and responsive tablet layouts."}, "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}}},
    "data_engineering": {"skill_id": "data_engineering", "category": "engineering", "name": "Data Engineering", "description": "ETL pipelines, data warehousing, streaming", "icon": "database", "color": "#0EA5E9", "recommended_tools": ["execute_code", "repo_write_file", "repo_read_file", "wiki_write_page"], "prompt_injection": {"expert": "Expert data engineer: design ETL/ELT pipelines, data warehouse schemas (star/snowflake), stream processing (Kafka/Kinesis), data quality frameworks, partitioning strategies, and cost-optimized storage tiers."}, "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}}},
    "ml_engineering": {"skill_id": "ml_engineering", "category": "engineering", "name": "ML Engineering", "description": "Model training, deployment, MLOps pipelines", "icon": "brain", "color": "#8B5CF6", "recommended_tools": ["execute_code", "repo_write_file", "repo_read_file", "wiki_write_page", "create_task"], "prompt_injection": {"expert": "Expert ML engineer: model selection, feature engineering, hyperparameter tuning, model serving (TFServing/Triton), A/B testing, drift detection, experiment tracking (MLflow/W&B), and responsible AI practices."}, "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}}},
    "accessibility": {"skill_id": "accessibility", "category": "engineering", "name": "Accessibility", "description": "WCAG compliance, screen reader testing, inclusive design", "icon": "eye", "color": "#14B8A6", "recommended_tools": ["repo_read_file", "create_task", "wiki_write_page", "log_decision"], "prompt_injection": {"expert": "Expert a11y specialist: WCAG 2.1 AA/AAA compliance, ARIA patterns, screen reader behavior, keyboard navigation, color contrast analysis, cognitive accessibility, and automated testing with axe-core/Lighthouse."}, "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}}},
    # ============ NEW: Marketing & Growth Skills ============
    "seo_optimization": {"skill_id": "seo_optimization", "category": "marketing", "name": "SEO Optimization", "description": "Search engine optimization, keyword research, technical SEO", "icon": "search", "color": "#EC4899", "recommended_tools": ["web_search", "wiki_write_page", "create_task", "log_decision"], "prompt_injection": {"expert": "Expert SEO: keyword research and clustering, on-page optimization, technical SEO (Core Web Vitals, structured data, crawl budget), link building strategy, content gap analysis, and search intent mapping."}, "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}}},
    "email_marketing": {"skill_id": "email_marketing", "category": "marketing", "name": "Email Marketing", "description": "Campaign design, segmentation, automation flows", "icon": "mail", "color": "#F43F5E", "recommended_tools": ["web_search", "wiki_write_page", "create_task", "log_decision"], "prompt_injection": {"expert": "Expert email marketer: design high-converting email campaigns, segment audiences by behavior and lifecycle stage, build automation flows (welcome series, abandoned cart, re-engagement), A/B test subject lines, optimize send times, and ensure deliverability (SPF/DKIM/DMARC)."}, "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}}},
    "growth_hacking": {"skill_id": "growth_hacking", "category": "marketing", "name": "Growth Hacking", "description": "Acquisition funnels, viral loops, experiment design", "icon": "trending-up", "color": "#D946EF", "recommended_tools": ["web_search", "wiki_write_page", "create_task", "log_decision"], "prompt_injection": {"expert": "Expert growth hacker: design acquisition funnels, identify viral coefficients, build referral programs, run rapid A/B experiments, optimize conversion rates, implement product-led growth mechanics, and model LTV:CAC ratios."}, "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}}},
    "social_media_strategy": {"skill_id": "social_media_strategy", "category": "marketing", "name": "Social Media Strategy", "description": "Platform strategy, content calendar, engagement", "icon": "share-2", "color": "#FB7185", "recommended_tools": ["web_search", "wiki_write_page", "create_task", "log_decision"], "prompt_injection": {"expert": "Expert social strategist: platform-specific content strategies (LinkedIn thought leadership, Twitter/X threads, Instagram Reels, TikTok trends), content calendar planning, community management, influencer outreach, and social listening for brand sentiment."}, "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}}},
    "brand_strategy": {"skill_id": "brand_strategy", "category": "marketing", "name": "Brand Strategy", "description": "Positioning, messaging, voice & tone guidelines", "icon": "palette", "color": "#A855F7", "recommended_tools": ["web_search", "wiki_write_page", "create_task", "log_decision"], "prompt_injection": {"expert": "Expert brand strategist: define brand positioning and value propositions, create messaging frameworks, establish voice and tone guidelines, develop brand architecture, design naming conventions, and ensure brand consistency across all touchpoints."}, "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}}},
    # ============ NEW: Finance & Legal Skills ============
    "financial_modeling": {"skill_id": "financial_modeling", "category": "finance", "name": "Financial Modeling", "description": "Revenue models, forecasting, unit economics", "icon": "calculator", "color": "#F97316", "recommended_tools": ["execute_code", "wiki_write_page", "web_search", "log_decision"], "prompt_injection": {"expert": "Expert financial modeler: build revenue forecast models, calculate unit economics (LTV, CAC, payback period), create pro forma financial statements, model scenario analysis (bull/base/bear), and design pricing strategies backed by data."}, "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}}},
    "contract_review": {"skill_id": "contract_review", "category": "finance", "name": "Contract Review", "description": "Legal document analysis, risk identification, clause drafting", "icon": "file-check", "color": "#EA580C", "recommended_tools": ["execute_code", "wiki_write_page", "web_search", "log_decision"], "prompt_injection": {"expert": "Expert contract reviewer: identify high-risk clauses (indemnification, limitation of liability, IP assignment, non-compete), flag ambiguous language, compare against standard market terms, suggest protective amendments, and draft counter-proposals."}, "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}}},
    "investor_relations": {"skill_id": "investor_relations", "category": "finance", "name": "Investor Relations", "description": "Pitch decks, due diligence, investor updates", "icon": "presentation", "color": "#D97706", "recommended_tools": ["execute_code", "wiki_write_page", "web_search", "log_decision"], "prompt_injection": {"expert": "Expert IR: craft compelling investor narratives, prepare due diligence data rooms, write monthly investor updates with KPI dashboards, design pitch decks with market sizing and competitive positioning, and model valuation scenarios."}, "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}}},
    "tax_analysis": {"skill_id": "tax_analysis", "category": "finance", "name": "Tax & Accounting", "description": "Tax implications, expense categorization, audit preparation", "icon": "receipt", "color": "#B45309", "recommended_tools": ["execute_code", "wiki_write_page", "web_search", "log_decision"], "prompt_injection": {"expert": "Expert tax analyst: categorize business expenses, identify tax-deductible opportunities, analyze R&D tax credit eligibility, prepare documentation for audits, and model tax implications of business decisions across jurisdictions."}, "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}}},
    "risk_assessment": {"skill_id": "risk_assessment", "category": "finance", "name": "Risk Assessment", "description": "Risk identification, mitigation planning, impact analysis", "icon": "alert-triangle", "color": "#DC2626", "recommended_tools": ["execute_code", "wiki_write_page", "web_search", "log_decision"], "prompt_injection": {"expert": "Expert risk assessor: identify operational, financial, and strategic risks, create risk matrices (likelihood x impact), design mitigation plans, model Monte Carlo scenarios, and establish early warning indicators with escalation procedures."}, "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}}},
    # ============ NEW: Product & Data Skills ============
    "ab_testing": {"skill_id": "ab_testing", "category": "product", "name": "A/B Testing", "description": "Experiment design, statistical significance, result analysis", "icon": "flask-conical", "color": "#D946EF", "recommended_tools": ["execute_code", "wiki_write_page", "web_search", "log_decision"], "prompt_injection": {"expert": "Expert experimenter: design statistically valid A/B tests, calculate required sample sizes, analyze results with proper confidence intervals, identify Simpson's paradox, design multi-armed bandit experiments, and build experimentation culture."}, "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}}},
    "product_analytics": {"skill_id": "product_analytics", "category": "product", "name": "Product Analytics", "description": "Funnels, retention, engagement metrics", "icon": "activity", "color": "#8B5CF6", "recommended_tools": ["execute_code", "wiki_write_page", "web_search", "log_decision"], "prompt_injection": {"expert": "Expert product analyst: define and track North Star metrics, build conversion funnels, analyze retention curves (D1/D7/D30), segment user behavior, identify power users vs churning cohorts, and design instrumentation plans for new features."}, "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}}},
    "data_visualization": {"skill_id": "data_visualization", "category": "data", "name": "Data Visualization", "description": "Charts, dashboards, storytelling with data", "icon": "file-text", "color": "#0D9488", "recommended_tools": ["execute_code", "wiki_write_page", "web_search", "log_decision"], "prompt_injection": {"expert": "Expert data visualizer: choose the right chart type for the data story, design clear dashboards with proper hierarchy, apply Tufte's principles (data-ink ratio), create interactive explorations, and translate complex datasets into executive-friendly visualizations."}, "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}}},
    "market_research": {"skill_id": "market_research", "category": "data", "name": "Market Research", "description": "TAM/SAM/SOM sizing, trend analysis, industry mapping", "icon": "globe", "color": "#059669", "recommended_tools": ["execute_code", "wiki_write_page", "web_search", "log_decision"], "prompt_injection": {"expert": "Expert market researcher: calculate Total Addressable Market using top-down and bottom-up approaches, map industry value chains, identify emerging trends, conduct PESTEL analysis, and synthesize findings into investment-grade market reports with confidence ranges."}, "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}}},
    "content_strategy": {"skill_id": "content_strategy", "category": "data", "name": "Content Strategy", "description": "Editorial planning, content audits, topic clusters", "icon": "file-text", "color": "#0D9488", "recommended_tools": ["execute_code", "wiki_write_page", "web_search", "log_decision"], "prompt_injection": {"expert": "Expert content strategist: audit existing content for gaps and cannibalization, design topic cluster architectures, create editorial calendars aligned with buyer journey stages, measure content ROI, and develop distribution strategies across owned, earned, and paid channels."}, "assessment_prompts": [], "levels": {"novice": {"min_score": 0, "min_tasks": 0}, "intermediate": {"min_score": 50, "min_tasks": 10}, "advanced": {"min_score": 70, "min_tasks": 50}, "expert": {"min_score": 85, "min_tasks": 100}, "master": {"min_score": 95, "min_tasks": 250}}},
}


def get_skill(skill_id: str) -> dict:
    return BUILTIN_SKILLS.get(skill_id, {})

def get_skills_by_category(category: str) -> list:
    return [s for s in BUILTIN_SKILLS.values() if s.get("category") == category]

def get_all_skill_ids() -> list:
    return list(BUILTIN_SKILLS.keys())

def build_skill_prompt_fragment(skills: list) -> str:
    """Build prompt injection from an agent's skill configuration."""
    fragments = []
    for skill_config in skills:
        skill_def = BUILTIN_SKILLS.get(skill_config.get("skill_id", ""))
        if not skill_def:
            continue
        level = skill_config.get("level", "intermediate")
        injections = skill_def.get("prompt_injection") or {}
        injection = injections.get(level) or injections.get("expert", "") or injections.get("intermediate", "")
        custom = skill_config.get("custom_instructions", "")
        if injection or custom:
            fragments.append(f"[SKILL: {skill_def['name']} — {level.upper()}]")
            if injection:
                fragments.append(injection)
            if custom:
                fragments.append(f"Additional instructions: {custom}")
    if not fragments:
        return ""
    return "\n\n=== YOUR SPECIALIZED SKILLS ===\n" + "\n".join(fragments) + "\n=== END SKILLS ===\n"
