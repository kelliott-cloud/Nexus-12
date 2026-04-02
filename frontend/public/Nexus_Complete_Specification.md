# NEXUS PLATFORM — Complete System Specification & Architecture
### Version 2.0 | March 2026

---

## TABLE OF CONTENTS

1. Executive Summary
2. System Architecture Flow Diagrams
3. Authentication & Session Flow
4. AI Collaboration Engine
5. Human Priority Queue System
6. Auto-Collaborate & Persist Mode
7. Data Guard & Tenant Isolation
8. Directive Engine
9. Code Repository
10. Wiki/Docs System
11. Project Lifecycle Management
12. Task Board & Kanban
13. Guide Me Module
14. Platform Agent Update System
15. Mobile Architecture
16. Notification System
17. Legal & Compliance
18. API Reference (650+ endpoints)
19. Database Schema (140+ collections)
20. Security Architecture
21. Deployment Architecture

---

## 1. EXECUTIVE SUMMARY

Nexus is a cloud-hosted, multi-tenant AI collaboration platform where up to 11 AI models work together on projects with real-time human observation and control. The platform provides a complete development environment with code repository, wiki, project management, and automation — all accessible to both humans and AI agents.

### Key Metrics
- **651 API endpoints** across 51 backend files
- **140+ MongoDB collections**
- **19 AI agent tools** for workspace interaction
- **11 AI models** (Claude Opus 4.6, GPT-5.2, Gemini 2.5 Pro, + 8 more)
- **10 languages**, dark/light/system themes
- **Complete mobile app** (iPhone priority)

---

## 2. SYSTEM ARCHITECTURE FLOW DIAGRAMS

### 2.1 High-Level System Architecture
```
┌──────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                               │
│                                                                   │
│  ┌────────────────┐     ┌─────────────────┐                     │
│  │  Desktop Web   │     │   Mobile Web    │                     │
│  │  (React SPA)   │     │  (Separate UI)  │                     │
│  │  Port 3000     │     │  Auto-detected  │                     │
│  └───────┬────────┘     └───────┬─────────┘                     │
│          │                       │                                │
│          └───────────┬───────────┘                                │
│                      │ HTTPS                                      │
│          ┌───────────▼───────────┐                                │
│          │  Kubernetes Ingress   │                                │
│          │  /api/* → Port 8001   │                                │
│          │  /* → Port 3000       │                                │
│          └───────────┬───────────┘                                │
├──────────────────────┼────────────────────────────────────────────┤
│                 API LAYER                                         │
│          ┌───────────▼───────────┐                                │
│          │     FastAPI Server    │                                │
│          │     Port 8001         │                                │
│          │                       │                                │
│          │  ┌─────────────────┐  │                                │
│          │  │  Rate Limiter   │  │  120 req/min per IP           │
│          │  │  (Middleware)   │  │                                │
│          │  └────────┬────────┘  │                                │
│          │  ┌────────▼────────┐  │                                │
│          │  │  Auth Layer     │  │  JWT Cookies + Google OAuth   │
│          │  │  (get_current   │  │                                │
│          │  │   _user)        │  │                                │
│          │  └────────┬────────┘  │                                │
│          │  ┌────────▼────────┐  │                                │
│          │  │  51 Route       │  │  651 endpoints                │
│          │  │  Modules        │  │                                │
│          │  └────────┬────────┘  │                                │
│          │  ┌────────▼────────┐  │                                │
│          │  │  DATA GUARD     │──┼── Sanitizes before AI calls   │
│          │  │  (Abstraction)  │  │   No-train headers            │
│          │  └────────┬────────┘  │   Audit logging               │
│          │  ┌────────▼────────┐  │                                │
│          │  │  TENANT         │──┼── Workspace isolation          │
│          │  │  ISOLATION      │  │   Cross-tenant prevention      │
│          │  └─────────────────┘  │                                │
│          └───────────────────────┘                                │
├───────────────────────────────────────────────────────────────────┤
│                 DATA LAYER                                        │
│          ┌───────────────────────┐                                │
│          │  MongoDB Atlas (Prod) │  140+ collections              │
│          │  MongoDB Local (Dev)  │  Encrypted at rest             │
│          └───────────────────────┘                                │
├───────────────────────────────────────────────────────────────────┤
│              EXTERNAL AI PROVIDERS                                │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  │Anthropic│ │ OpenAI  │ │ Google  │ │DeepSeek │ │  xAI    │  │
│  │(Claude) │ │(GPT-5.2)│ │(Gemini) │ │         │ │ (Grok)  │  │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘  │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  │Perplxty │ │ Mistral │ │ Cohere  │ │  Groq   │ │OpenRoutr│  │
│  │(Sonar)  │ │ (Large) │ │(Cmd A)  │ │(Llama)  │ │  (Pi)   │  │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘  │
│              + Inception (Mercury 2)                              │
└───────────────────────────────────────────────────────────────────┘
```

### 2.2 AI Collaboration Flow
```
Human sends message
        │
        ▼
┌──────────────────┐
│ POST /messages   │──→ Sanitize (XSS) ──→ Store in DB
└────────┬─────────┘
         │
         ▼
┌──────────────────┐     ┌─────────────────────┐
│ POST /collaborate │──→  │ Human Priority Check │
└────────┬─────────┘     │ Is persist running?  │
         │               └──────────┬────────────┘
         │                          │
         ▼                    YES   ▼   NO
┌──────────────────┐   ┌────────────────┐  ┌──────────────┐
│ Set pause flag   │   │ Pause agents   │  │ Start normal │
│ (human_priority) │   │ Process human  │  │ collaboration│
└────────┬─────────┘   │ msg first      │  └──────┬───────┘
         │             └────────────────┘         │
         ▼                                        ▼
┌──────────────────────────────────────────────────────────┐
│                run_ai_collaboration()                      │
│                                                           │
│  1. Fetch last 50 messages for context                    │
│  2. Parse @mentions → determine target agents             │
│  3. Pre-fetch KB + Repo context (shared, once)            │
│  4. Check disabled_agents → skip disabled                 │
│  5. Build system prompt:                                  │
│     - Model prompt + Language + Tools + Code Repo         │
│     - Platform Capabilities + Directive Rules             │
│     - KB context + Repo file tree                         │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐  │
│  │     STAGGERED PARALLEL DISPATCH (0.8s apart)        │  │
│  │                                                      │  │
│  │  Agent 1 ──→ DATA GUARD ──→ AI Provider API         │  │
│  │     (0.0s)    sanitize      no-train headers         │  │
│  │               redact PII    audit log                │  │
│  │                                                      │  │
│  │  Agent 2 ──→ DATA GUARD ──→ AI Provider API         │  │
│  │     (0.8s)                                           │  │
│  │                                                      │  │
│  │  Agent N ──→ DATA GUARD ──→ AI Provider API         │  │
│  │     (N*0.8s)                                         │  │
│  │                                                      │  │
│  │  Each agent CHECKS human_priority before API call    │  │
│  │  If pause_requested → yield immediately              │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  6. Parse tool calls (5 formats supported)                │
│  7. Execute tools → log workspace_activities              │
│  8. Save AI message with metadata:                        │
│     {ai_generated: true, ai_provider, ai_model_id}       │
│  9. Post tool results as system messages                  │
└──────────────────────────────────────────────────────────┘
```

### 2.3 Data Guard Flow
```
AI Agent Request
        │
        ▼
┌──────────────────────────────────────────┐
│            DATA GUARD LAYER               │
│                                           │
│  1. SANITIZE content:                     │
│     - Emails → [EMAIL_REDACTED]           │
│     - API keys → [API_KEY_REDACTED]       │
│     - Phone numbers → [PHONE_REDACTED]    │
│     - SSNs → [SSN_REDACTED]              │
│     - Credentials → [CREDENTIAL_REDACTED] │
│                                           │
│  2. ADD NO-TRAIN HEADERS:                 │
│     - X-No-Train: true (OpenAI)           │
│     - X-Nexus-DataGuard: active           │
│     - X-Nexus-Workspace: sha256(ws_id)    │
│                                           │
│  3. AUDIT LOG:                            │
│     → data_transmissions collection       │
│     {workspace_id, agent, provider,       │
│      chars_sent, timestamp}               │
│                                           │
│  4. TRUNCATE:                             │
│     - System prompt: max 12K chars        │
│     - User message: max 8K chars          │
└──────────────────┬───────────────────────┘
                   │
                   ▼
         External AI Provider
         (sanitized data only)
```

### 2.4 Tenant Isolation Flow
```
Every API Request
        │
        ▼
┌──────────────────────────────────────────┐
│          TENANT ISOLATION                 │
│                                           │
│  verify_workspace_access(user, ws):       │
│    1. Is user the workspace owner? ──→ ✓  │
│    2. Is user in members list? ──→ ✓      │
│    3. Is user in workspace_members? ──→ ✓ │
│    4. Is user in org that owns ws? ──→ ✓  │
│    5. Is user super_admin? ──→ ✓          │
│    6. None of above? ──→ ✗ DENIED         │
│                                           │
│  enforce_workspace_filter(query, ws_id):  │
│    Every DB query MUST include            │
│    workspace_id to prevent cross-tenant   │
│    data leakage                           │
└──────────────────────────────────────────┘
```

### 2.5 Persistent Collaboration Flow
```
User enables Persist Mode
        │
        ▼
┌─────────────────────────────────────────────┐
│     run_persist_collaboration()              │
│     (infinite loop)                          │
│                                              │
│  while True:                                 │
│    │                                         │
│    ├─ Check: still enabled in DB?            │
│    │  NO → break                             │
│    │                                         │
│    ├─ Check: human_priority?                 │
│    │  YES → pause up to 30s, then continue   │
│    │                                         │
│    ├─ Check: agent health (every 5 rounds)   │
│    │  3+ errors → auto-disable agent         │
│    │  50%+ agents failed → STOP + notify     │
│    │                                         │
│    ├─ Run collaboration round                │
│    │  SUCCESS → reduce delay (speed up)      │
│    │  RATE LIMIT → increase delay x2.5       │
│    │  ERROR → increase delay x1.5            │
│    │                                         │
│    └─ Sleep (delay + jitter)                 │
│       delay range: 3s → 120s (adaptive)      │
│                                              │
│  On stop: post system message, clear flags   │
│  On server restart: auto-resume from DB      │
└─────────────────────────────────────────────┘
```

### 2.6 Directive Engine Flow
```
User creates Directive (4-step wizard)
        │
        ▼
┌─────────────────────────────────┐
│  Step 1: Project name, goal    │
│  Step 2: Agent roles/rules     │
│  Step 3: Universal rules       │
│  Step 4: Phases with tasks     │
│  + Optional: Upload reference  │
│    doc (.txt/.pdf/.docx)       │
└────────────┬────────────────────┘
             │ Activate
             ▼
┌─────────────────────────────────┐
│  Auto-generate:                 │
│  - Tasks from phases            │
│  - File ownership records       │
│  - Audit events                 │
│                                 │
│  Inject rules into AI prompts:  │
│  - Additive only (no deletion)  │
│  - Full file context            │
│  - Prohibited patterns          │
│  - Agent role constraints       │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  Validation Pipeline:           │
│  Task output checked against    │
│  acceptance criteria            │
│                                 │
│  PASS → move to review          │
│  FAIL → retry (up to max)       │
│  MAX RETRIES → escalate to      │
│    human + notification          │
│                                 │
│  Phase Gates:                   │
│  All tasks merged → unlock      │
│  next phase                     │
│                                 │
│  Cost Tracking:                 │
│  Token usage per task/agent     │
│  Budget alerts at threshold     │
└─────────────────────────────────┘
```

---

## 3-21: DETAILED SPECIFICATIONS

### 3. Authentication & Session Flow

**Email/Password**: bcrypt hash → JWT cookie (HttpOnly, Secure, SameSite=None, 7-day expiry)
**Google OAuth**: Emergent Auth → session_id hash → POST /auth/session → JWT cookie
**Mobile Resilience**: sessionStorage fallback + 10-second grace period for 401 interceptor
**RBAC Roles**: super_admin, platform_support, workspace_admin, admin, user, observer

### 4. AI Agent System — 19 Tools

| # | Tool | Module | Description |
|---|------|--------|-------------|
| 1 | create_project | Projects | Create workspace project |
| 2 | create_project_plan | Projects | Full project + milestones + tasks |
| 3 | create_task | Tasks | Create task in project |
| 4 | update_task_status | Tasks | Move status (auto-marks done) |
| 5 | create_milestone | Milestones | Add milestone with due date |
| 6 | list_projects | Projects | Browse projects |
| 7 | list_tasks | Tasks | List project tasks |
| 8 | create_artifact | Artifacts | Save code/documents |
| 9 | save_to_memory | Knowledge | Store knowledge |
| 10 | read_memory | Knowledge | Read knowledge |
| 11 | handoff_to_agent | Collab | Pass to another agent |
| 12 | execute_code | Code | Run Python/JS/Bash |
| 13 | repo_list_files | Code Repo | Browse file tree |
| 14 | repo_read_file | Code Repo | Read file content |
| 15 | repo_write_file | Code Repo | Create/update files |
| 16 | repo_approve_review | Code Repo | Approve QA reviews |
| 17 | wiki_list_pages | Wiki | Browse wiki pages |
| 18 | wiki_read_page | Wiki | Read wiki page |
| 19 | wiki_write_page | Wiki | Create/update wiki |

### Tool Call Parsing (5 formats)
```
[TOOL_CALL]{"tool": "...", "params": {}}[/TOOL_CALL]
<tool_call>{"tool": "...", "params": {}}</tool_call>
[tool_call]{"tool": "...", "params": {}}[/tool_call]
```tool\n{...}\n```
```json\n{...}\n```
```

### 5. Available AI Models Per Agent

| Agent | Default Model | Available Models |
|-------|--------------|-----------------|
| Claude | claude-opus-4-20250514 | Opus 4.6, Sonnet 4.6, Opus 4.5, Sonnet 4.5, 3.5 Sonnet, 3 Haiku |
| ChatGPT | gpt-5.2 | GPT-5.2, GPT-5, GPT-4.1, GPT-4o, GPT-4o Mini, o3, o3-mini |
| Gemini | gemini-2.5-pro | 2.5 Pro, 2.5 Flash, 2.0 Flash |
| DeepSeek | deepseek-chat | Chat, Reasoner |
| Grok | grok-3 | Grok 3, Grok 3 Mini |
| Groq | llama-3.3-70b | Llama 3.3 70B, 3.1 8B, Mixtral 8x7B |
| Mistral | mistral-large | Large, Medium, Small |
| Cohere | command-a-03-2025 | Command A, R+, R |
| Perplexity | sonar-pro | Sonar Pro, Sonar |
| Mercury 2 | mercury-2 | Mercury 2 |
| Pi | inflection-3-pi | Pi (via OpenRouter) |

### 6. Frontend Module Map

| Module | Tab Location | Component | Access |
|--------|-------------|-----------|--------|
| Chat | Primary | ChatPanel.js | All |
| Projects | Primary | ProjectPanel.js | All |
| Tasks | Primary | TaskBoard.js | All |
| Docs | Primary | WikiPanel.js | All |
| Code Repo | Build dropdown | CodeRepoPanel.js | All |
| Guide Me | Build dropdown | GuideMe.js | All |
| Workflows | Build dropdown | WorkflowBuilder.js | All |
| Agents | Build dropdown | AgentPanel | All |
| Gantt | More dropdown | GanttChart.js | All |
| Directives | More dropdown | DirectiveDashboard.js | All |
| Knowledge | More dropdown | KnowledgeBasePanel.js | All |
| Analytics | More dropdown | Analytics.js | All |
| Members | More dropdown | MembersPanel | Human only |
| Reports | More dropdown | Reports | Human only |

### 7. Security Architecture

```
┌─────────────────────────────────────────────────────┐
│                 SECURITY LAYERS                      │
│                                                      │
│  Layer 1: RATE LIMITER (120 req/min/IP)             │
│  Layer 2: AUTH (JWT HTTPOnly cookies)                │
│  Layer 3: TENANT ISOLATION (workspace_id filter)     │
│  Layer 4: XSS SANITIZATION (input validation)        │
│  Layer 5: DATA GUARD (AI provider abstraction)       │
│  Layer 6: ENCRYPTION (Fernet for API keys)           │
│  Layer 7: AUDIT LOGGING (all data transmissions)     │
│  Layer 8: RBAC (role-based permissions)              │
│  Layer 9: NO-TRAIN HEADERS (all AI calls)            │
│  Layer 10: CORS (configurable origins)               │
└─────────────────────────────────────────────────────┘
```

---

*Document generated March 2026. Nexus Platform v2.0.*
*Total codebase: ~25,000 lines backend, ~20,000 lines frontend.*
*51 backend files, 48 frontend components/pages.*
