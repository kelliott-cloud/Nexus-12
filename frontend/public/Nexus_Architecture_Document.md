# NEXUS PLATFORM — Complete Architecture Document
### Version 1.0 | March 2026

---

## TABLE OF CONTENTS

1. Platform Overview
2. System Architecture
3. Technology Stack
4. Frontend Architecture
5. Backend Architecture
6. Database Schema
7. Authentication & Authorization
8. AI Agent System
9. Code Repository
10. Wiki/Docs System
11. Project Lifecycle Management
12. Task Sessions & Automation
13. Content Creation Studio
14. Integrations & Plugins
15. Real-Time Communication
16. Mobile Architecture
17. Legal & Compliance
18. Billing & Pricing
19. API Reference Summary
20. Deployment Architecture
21. Security
22. Performance Optimizations

---

## 1. PLATFORM OVERVIEW

Nexus is a cloud-hosted, multi-tenant AI collaboration platform where multiple AI agents work together on projects with real-time human observation. It combines Slack-like messaging with 11 AI models, a full project lifecycle management suite, a code repository with Monaco editor, a wiki/docs system, content creation tools, and automation workflows.

### Key Metrics
- **639 API endpoints**
- **138 MongoDB collections**
- **20,934 lines of backend code** across 45 route files
- **19,574 lines of frontend code** across 44 components and 18 pages
- **125 Python dependencies, 53 JS dependencies**
- **17 AI agent tools**
- **11 AI models** (Claude, ChatGPT, Gemini, DeepSeek, Grok, Perplexity, Mistral, Cohere, Groq, Mercury 2, Pi)
- **10 languages** (English, Spanish, Chinese, Hindi, Arabic, French, Portuguese, Russian, Japanese, German)

---

## 2. SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────────┐
│                   CLIENT LAYER                    │
│  ┌──────────────┐  ┌──────────────┐              │
│  │ Desktop Web  │  │ Mobile Web   │              │
│  │ (React SPA)  │  │ (React SPA)  │              │
│  │ Port 3000    │  │ Auto-detect  │              │
│  └──────┬───────┘  └──────┬───────┘              │
│         │                  │                      │
│         └────────┬─────────┘                      │
│                  │ HTTPS                          │
│         ┌────────▼─────────┐                      │
│         │ Kubernetes Ingress│                      │
│         │ /api → 8001      │                      │
│         │ /* → 3000        │                      │
│         └────────┬─────────┘                      │
├──────────────────┼──────────────────────────────┤
│             API LAYER                             │
│  ┌───────────────▼──────────────────┐            │
│  │        FastAPI Server             │            │
│  │        Port 8001                  │            │
│  │  ┌──────────────────────────┐    │            │
│  │  │ server.py (2,600 lines)  │    │            │
│  │  │ - Auth, Channels, Msgs   │    │            │
│  │  │ - Collaboration Engine   │    │            │
│  │  │ - Health, Rate Limiter   │    │            │
│  │  └──────────────────────────┘    │            │
│  │  ┌──────────────────────────┐    │            │
│  │  │ 45 Route Modules         │    │            │
│  │  │ routes_*.py              │    │            │
│  │  └──────────────────────────┘    │            │
│  │  ┌──────────────────────────┐    │            │
│  │  │ ai_providers.py          │    │            │
│  │  │ Direct API calls to:     │    │            │
│  │  │ - Anthropic, OpenAI      │    │            │
│  │  │ - Google, DeepSeek, xAI  │    │            │
│  │  │ - Perplexity, Mistral    │    │            │
│  │  │ - Cohere, Groq           │    │            │
│  │  │ - Inception, Inflection  │    │            │
│  │  └──────────────────────────┘    │            │
│  └──────────────────────────────────┘            │
├──────────────────────────────────────────────────┤
│             DATA LAYER                            │
│  ┌──────────────────────────────────┐            │
│  │  MongoDB Atlas (Production)      │            │
│  │  MongoDB Local (Development)     │            │
│  │  138 Collections                 │            │
│  │  Motor Async Driver              │            │
│  └──────────────────────────────────┘            │
├──────────────────────────────────────────────────┤
│          EXTERNAL SERVICES                        │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐  │
│  │Emergent│ │ Stripe │ │ Resend │ │ GitHub   │  │
│  │  Auth  │ │Payments│ │ Email  │ │   API    │  │
│  └────────┘ └────────┘ └────────┘ └──────────┘  │
└──────────────────────────────────────────────────┘
```

---

## 3. TECHNOLOGY STACK

### Backend
| Component | Technology | Version |
|-----------|-----------|---------|
| Framework | FastAPI | Latest |
| Database | MongoDB (Motor async) | 7.x |
| Auth | JWT (HTTPOnly cookies) + Emergent Google OAuth | - |
| AI Calls | httpx (async HTTP client) | - |
| Encryption | cryptography (Fernet) | - |
| Email | Resend | - |
| Payments | Stripe | - |
| Language | Python 3.11+ | - |

### Frontend
| Component | Technology | Version |
|-----------|-----------|---------|
| Framework | React | 18.x |
| Build Tool | Craco (CRA override) | - |
| CSS | Tailwind CSS | 3.x |
| UI Library | Shadcn/UI | - |
| Code Editor | Monaco (@monaco-editor/react) | 4.7.0 |
| Workflow | React Flow | - |
| HTTP | Axios | - |
| Toasts | Sonner | - |
| Icons | Lucide React | - |

### Infrastructure
| Component | Technology |
|-----------|-----------|
| Container | Kubernetes (Emergent) |
| Process Manager | Supervisor |
| DB (Production) | MongoDB Atlas |
| DB (Development) | Local MongoDB |
| Auth Provider | Emergent Google OAuth |

---

## 4. FRONTEND ARCHITECTURE

### Directory Structure
```
frontend/src/
├── App.js                    # Root — routing, auth, device detection, theme
├── App.css                   # Global styles, light theme overrides
├── index.css                 # Tailwind base, CSS variables, animations
├── components/
│   ├── ChatPanel.js          # Chat messages, agent panel, input, persist toggle
│   ├── MessageBubble.js      # Individual message rendering, code blocks, tools
│   ├── Sidebar.js            # Workspace sidebar, channels, legal links
│   ├── CodeRepoPanel.js      # Monaco editor, file tree, branches, git
│   ├── WikiPanel.js          # Docs editor, page tree, templates
│   ├── TaskBoard.js          # Grouped + Kanban views, drag-drop, detail modal
│   ├── TaskPanel.js          # Task sessions, queue, scheduling
│   ├── ProjectPanel.js       # Project CRUD, milestones, task management
│   ├── GanttChart.js         # Timeline visualization
│   ├── RepoAnalytics.js      # Code repo stats, language breakdown
│   ├── LegalComponents.js    # Cookie banner, ToS modal, AI disclaimer
│   ├── LanguageToggle.js     # 10-language dropdown selector
│   ├── ui/                   # 40+ Shadcn/UI components
│   └── ... (44 total)
├── pages/
│   ├── LandingPage.js        # Public landing page
│   ├── AuthPage.js           # Login/Register/Company signup
│   ├── AuthCallback.js       # Google OAuth callback handler
│   ├── Dashboard.js          # Workspace list, onboarding
│   ├── WorkspacePage.js      # Main workspace — 20+ tabs
│   ├── SettingsPage.js       # Profile, AI keys, preferences, theme
│   ├── BillingPage.js        # Plans, invoices, usage
│   ├── AdminDashboard.js     # Super admin panel
│   ├── MobileApp.js          # Complete mobile UI (separate from desktop)
│   ├── LegalPage.js          # Terms, Privacy, AUP pages
│   └── ... (18 total)
├── contexts/
│   └── LanguageContext.js     # i18n provider, t() function
├── hooks/
│   └── useIsMobile.js        # Device detection (UA + screen width)
├── i18n/
│   ├── translations.js       # 10 language imports
│   ├── en.json, es.json, zh.json, hi.json, ar.json
│   ├── fr.json, pt.json, ru.json, ja.json, de.json
│   └── (145 keys × 10 languages = 1,450 translations)
└── lib/
    ├── api.js                # Axios instance, 401 interceptor, auth grace period
    ├── notifications.js      # Push notification helpers
    └── utils.js              # Shared utilities
```

### Device Detection & Routing
```javascript
// useIsMobile hook checks both UA and screen width
const isMobile = /iPhone|Android|Mobile/i.test(navigator.userAgent) || window.innerWidth < 768;

// AppRouter renders completely separate component trees
if (isMobile) {
  // MobileDashboard, MobileWorkspace, MobileAuth, MobileSettings, MobileWiki
} else {
  // Full desktop UI with sidebar, tabs, panels
}
```

### Theme System
```css
/* CSS Variables in :root (dark) and .light class */
:root { --background: 240 6% 4%; --foreground: 0 0% 98%; ... }
.light { --background: 0 0% 100%; --foreground: 240 10% 4%; ... }

/* Hardcoded class overrides for components using bg-zinc-* */
.light .bg-zinc-950 { background-color: #ffffff !important; }
.light .bg-zinc-900 { background-color: #f8f9fa !important; }
.light .text-zinc-100 { color: #1a1a2e !important; }
```

### Chat Layout (CSS Grid — bulletproof)
```
gridTemplateRows: "auto 1fr auto"
Row 1: Channel header (auto height)
Row 2: Messages area (1fr — takes remaining space)
Row 3: Input area (auto height)

Messages + Agent Panel use flex row inside Row 2:
[Messages (flex-1)] | [Agent Panel (w-64, optional)]
```

---

## 5. BACKEND ARCHITECTURE

### server.py (2,600 lines) — Core Application
```
Inline routes:
- /api/auth/* — Login, register, session, logout, OAuth callback
- /api/auth/me — Current user (with ToS status)
- /api/workspaces/* — CRUD, settings, search
- /api/channels/* — CRUD, messages, collaborate, status, auto-collab, persist
- /api/health — DB connectivity check

Key functions:
- get_current_user(request) — JWT cookie validation
- run_ai_collaboration(channel_id, user_id) — Parallel AI agent execution
- run_persist_collaboration(channel_id, user_id) — Indefinite collaboration loop
- run_auto_collaboration_loop(channel_id, user_id) — Round-limited auto-collab
- sanitize_html(text) — XSS prevention

Middleware:
- CORS (configurable origins)
- Rate limiter (120 req/min per IP)
- Structured JSON logging (optional)
```

### Route Modules (45 files)
| Module | Lines | Endpoints | Purpose |
|--------|-------|-----------|---------|
| routes_projects.py | 1,030 | 37 | Projects, milestones, relationships, templates, analytics |
| routes_media.py | 968 | 40 | Image/video/audio generation, library |
| routes_code_repo.py | 862 | 23 | File tree, branches, git push/pull, ZIP download |
| routes_ai_tools.py | 833 | 2 | 17 AI tools, multi-format parser, execution |
| routes_workflows.py | 747 | 27 | Visual workflow builder, execution, templates |
| routes_orgs.py | 675 | 25 | Multi-tenant organizations |
| routes_plm_advanced.py | 564 | 43 | Gantt, sprints, time tracking, custom fields |
| routes_walkthroughs_builder.py | 554 | 20 | Product tour builder |
| routes_admin.py | 535 | 16 | Super admin, user/org management |
| routes_marketplace.py | 531 | 18 | Workflow template marketplace |
| routes_code_dev.py | 529 | 20 | Code execution sandbox |
| routes_ai_skills.py | 512 | 5 | Per-workspace AI model configuration |
| routes_wiki.py | 360 | 12 | Wiki pages, templates, unified search |
| routes_legal.py | 275 | 12 | ToS, GDPR, data export, account deletion |
| routes_task_sessions.py | 315 | 10 | Task sessions, queue, scheduling |
| routes_billing_advanced.py | 384 | 18 | Plans, invoices, usage tracking |
| routes_plugins.py | 436 | 14 | Slack, Discord, Teams, etc. |
| routes_cloud_storage.py | 435 | 9 | Google Drive, Dropbox, Box, OneDrive |
| routes_support_desk.py | 422 | 19 | Ticketing system |
| routes_notifications.py | 200 | 8 | Bell notifications, push |
| routes_auth_email.py | 149 | 3 | Email/password auth |

### ai_providers.py — Direct AI API Calls
```python
PROVIDER_CONFIG = {
    "claude":     {"base_url": "api.anthropic.com",           "default_model": "claude-opus-4-20250514"},
    "chatgpt":    {"base_url": "api.openai.com",              "default_model": "gpt-5.2"},
    "gemini":     {"base_url": "generativelanguage.googleapis.com", "default_model": "gemini-3-pro"},
    "deepseek":   {"base_url": "api.deepseek.com",            "default_model": "deepseek-chat"},
    "grok":       {"base_url": "api.x.ai",                    "default_model": "grok-3"},
    "perplexity": {"base_url": "api.perplexity.ai",           "default_model": "sonar-pro"},
    "mistral":    {"base_url": "api.mistral.ai",              "default_model": "mistral-large-latest"},
    "cohere":     {"base_url": "api.cohere.com",              "default_model": "command-a-03-2025"},
    "groq":       {"base_url": "api.groq.com",                "default_model": "llama-3.3-70b-versatile"},
    "mercury":    {"base_url": "api.inceptionlabs.ai",        "default_model": "mercury-2"},
    "pi":         {"base_url": "api.inflection.ai",           "default_model": "inflection_3_pi"},
}

Features:
- Retry with exponential backoff + jitter (4 retries, max 30s)
- Prompt truncation (system: 12K chars, user: 8K chars)
- Claude 400 error retry with shorter prompt
- Per-channel model overrides via agent_models
```

---

## 6. DATABASE SCHEMA (138 Collections)

### Core Collections
| Collection | Purpose | Key Fields |
|-----------|---------|------------|
| users | User accounts | user_id, email, name, auth_type, plan, tos_version |
| workspaces | Workspace containers | workspace_id, name, owner_id |
| channels | Chat channels | channel_id, workspace_id, ai_agents[], agent_models{}, disabled_agents[] |
| messages | Chat messages | message_id, channel_id, sender_type, content, ai_generated, ai_model_id |
| organizations | Multi-tenant orgs | org_id, name, slug |

### AI & Collaboration
| Collection | Purpose |
|-----------|---------|
| ai_keys | Encrypted API keys per user/workspace |
| custom_agents | User-created Nexus agents |
| nexus_agents | Agent configurations |
| workspace_memory | Knowledge base entries |
| handoffs | Agent-to-agent handoffs |
| disagreements | AI agent disagreement tracking |

### Project Management
| Collection | Purpose |
|-----------|---------|
| projects | Project metadata |
| project_tasks | Rich task model (status, priority, assignee, labels) |
| tasks | Simple workspace-level tasks |
| milestones | Project milestones with progress |
| task_relationships | parent-child, blocks, depends_on, milestone links |
| sprints | Sprint planning |
| time_entries | Time tracking |
| task_sessions | AI agent task sessions with queue |

### Code Repository
| Collection | Purpose |
|-----------|---------|
| code_repos | Per-workspace repo metadata |
| repo_files | File tree with content |
| repo_commits | Version history |
| repo_branches | Branch management |
| repo_reviews | QA code reviews |
| repo_links | Links to channels/projects |

### Wiki/Docs
| Collection | Purpose |
|-----------|---------|
| wiki_pages | Wiki page content, hierarchy |
| wiki_versions | Page version history |

### Content & Media
| Collection | Purpose |
|-----------|---------|
| generated_images | AI-generated images |
| media_items | Video/audio items |
| artifacts | Code/document artifacts |
| drive_files | File repository |

---

## 7. AUTHENTICATION & AUTHORIZATION

### Auth Flow
```
1. Email/Password:
   POST /auth/register → bcrypt hash → JWT cookie
   POST /auth/login → verify hash → JWT cookie

2. Google OAuth:
   Click "Continue with Google" → GET /auth/google/login → Google consent → /api/auth/google/callback
   → Google consent → redirect back with #session_id=xxx
   → POST /auth/session → exchange for JWT cookie + sessionStorage

3. Cookie Config:
   httponly=True, secure=True, samesite="none", path="/", max_age=7 days
```

### Auth Grace Period
After login, a 10-second grace period prevents the 401 interceptor from clearing the session during cookie propagation (critical for mobile browsers).

### RBAC Roles
- **Super Admin** — Platform-wide access (SUPER_ADMIN_EMAIL env var)
- **Platform Support** — Same as super admin without delete
- **Org Admin** — Per-organization management
- **Workspace Owner** — Full workspace control
- **Member** — Standard access
- **Viewer** — Read-only

---

## 8. AI AGENT SYSTEM

### Agent Collaboration Flow
```
1. User sends message in channel
2. POST /channels/{id}/messages — saves message
3. POST /channels/{id}/collaborate — triggers collaboration
4. run_ai_collaboration():
   a. Fetch last 50 messages for context
   b. Parse @mentions to determine target agents
   c. Pre-fetch KB + repo context (shared, not per-agent)
   d. For each agent (STAGGERED parallel, 0.8s between):
      - Check if disabled
      - Check auto-collab rate limits
      - Get user's API key for this agent
      - Build system prompt + tools + KB + repo context
      - Truncate if too long (12K system, 8K user)
      - Call AI provider API (with model override if set)
      - Parse response for tool calls (5 formats)
      - Execute tool calls
      - Save response as message (with ai_generated metadata)
5. Frontend polls every 2 seconds, shows new messages
```

### 17 AI Tools
| Tool | Description |
|------|-------------|
| create_project | Create workspace project |
| create_task | Create task in project |
| update_task_status | Move task between statuses |
| list_projects | Browse projects |
| list_tasks | List project tasks |
| create_artifact | Save code/document artifact |
| save_to_memory | Store in knowledge base |
| read_memory | Read from knowledge base |
| handoff_to_agent | Pass context to another agent |
| execute_code | Run code in sandbox (Python, JS, Bash) |
| repo_list_files | Browse code repository |
| repo_read_file | Read any repo file |
| repo_write_file | Create/update repo file (QA review) |
| repo_approve_review | Approve/reject code review |
| wiki_list_pages | Browse wiki pages |
| wiki_read_page | Read wiki page content |
| wiki_write_page | Create/update wiki page |

### Tool Call Parsing (5 formats)
```
[TOOL_CALL]{"tool": "...", "params": {}}[/TOOL_CALL]
<tool_call>{"tool": "...", "params": {}}</tool_call>
[tool_call]{"tool": "...", "params": {}}[/tool_call]
```tool\n{"tool": "...", "params": {}}\n```
```json\n{"tool": "...", "params": {}}\n```
```

### Auto-Collaboration Modes
1. **Standard** — Limited rounds (5-50, configurable per workspace)
2. **Persist** — Runs indefinitely with adaptive throttling:
   - Starts at 3s delay, increases to 120s on rate limits
   - Reduces delay on success (speeds back up)
   - Pauses 5 min after 10 consecutive errors
   - Checks DB every 10 rounds if still enabled

### Per-Channel Model Overrides
```json
{
  "ai_agents": ["claude", "chatgpt", "gemini"],
  "agent_models": {
    "claude": "claude-opus-4-20250514",
    "chatgpt": "gpt-5.2",
    "gemini": "gemini-3-pro"
  }
}
```

---

## 9. CODE REPOSITORY

- **Per-workspace** repo with MongoDB storage
- **Monaco editor** in slide-out panel (syntax highlighting for 20+ languages)
- **File tree** with folders, search, create/rename/delete
- **Branch support** — create, merge, delete; branch selector in UI
- **Version history** — every edit tracked as a commit with before/after diff
- **Git integration** — push to / pull from GitHub via Contents API
- **ZIP download** — entire repo as compressed archive
- **QA reviews** — code flagged for review before commit
- **Repo analytics** — file count, language breakdown, contributors, recent commits
- **AI context injection** — file tree + small file contents injected into agent prompts

---

## 10. WIKI/DOCS SYSTEM

- **Per-workspace** wiki with parent-child page hierarchy
- **Monaco markdown editor** with live preview
- **Version history** — every edit tracked with author and timestamp
- **Search** — full-text search across title and content
- **Pin pages** — pinned pages appear at top of sidebar
- **4 templates** — Meeting Notes, Decision Log, Runbook, API Documentation
- **AI access** — agents can list, read, and write wiki pages via tools

---

## 11. PROJECT LIFECYCLE MANAGEMENT

- **Projects** — CRUD with linked channels
- **Tasks** — Rich model (status, priority, type, assignee, labels, story points, due date)
- **Task Board** — Grouped by Project + Kanban (4-column drag-and-drop)
- **Task Detail Modal** — Full details with relationships, milestone, activity
- **Milestones** — Per-project with progress tracking (% of linked tasks done)
- **Relationships** — parent-child, blocks, depends_on, milestone linking
- **3 Project Templates** — Web Application, AI Agent Project, Sprint Planning
- **Gantt Chart** — Timeline visualization with milestone diamonds
- **Sprints** — Sprint planning with velocity tracking
- **Time Tracking** — Time entries per task

---

## 12. TASK SESSIONS & AUTOMATION

- **Task Sessions** — AI agent work sessions with dedicated chat
- **Task Queue** — Queued/scheduled tasks with due dates
- **Scheduled tasks** — Set date/time, auto-run when due
- **Completion notifications** — Bell notification when AI finishes
- **Embedded panel** — Right side of Tasks tab (not floating)

---

## 13. CONTENT CREATION STUDIO

- **Image Generation** — Gemini Nano Banana via Emergent LLM Key
- **Video Generation** — Sora 2 via Emergent LLM Key
- **Audio/TTS** — OpenAI TTS (multiple voices)
- **Voice Input** — Whisper transcription
- **Documents** — AI-powered document creation

---

## 14. INTEGRATIONS & PLUGINS

### Built-in Connectors (30+)
| Category | Services |
|----------|----------|
| Messaging | Slack, Discord, MS Teams, Mattermost, WhatsApp, Signal, Telegram |
| Meetings | Zoom |
| Cloud Storage | Google Drive, OneDrive, Dropbox, Box |
| Development | GitHub (OAuth, repos, PRs, issues, CI/CD) |
| Email | SendGrid, Resend |
| Payments | Stripe |
| Voice/Music | ElevenLabs, Suno, Udio |

### Integration Keys
- Encrypted with Fernet symmetric encryption
- Stored in `platform_settings` (platform-level) or `ai_keys` (user-level)
- Admin panel for saving/testing keys

---

## 15. REAL-TIME COMMUNICATION

- **Polling** — Frontend polls every 2 seconds for messages and status
- **Push Notifications** — Service worker (sw.js) for background notifications
- **Local Notifications** — Shows when AI responds while tab is hidden
- **Agent Status** — Real-time thinking/idle indicators per agent

---

## 16. MOBILE ARCHITECTURE

- **Completely separate UI** — Not responsive CSS, separate React components
- **Device detection** — `useIsMobile` hook (UA regex + `innerWidth < 768`)
- **Bottom navigation** — Chat, Tasks, Docs, Settings
- **Hamburger menu** — Channel list, workspace navigation
- **Mobile chat** — Full-width message bubbles, horizontal channel pills
- **Mobile settings** — Theme, auto-collab rounds, links to AI Keys/Billing
- **iPhone safe areas** — `env(safe-area-inset-*)`, `viewport-fit=cover`
- **Google OAuth** — Same Emergent auth flow with sessionStorage fallback

---

## 17. LEGAL & COMPLIANCE

### Implemented
- **/terms** — Terms of Service (14 sections)
- **/privacy** — Privacy Policy (10 sections)
- **/acceptable-use** — Acceptable Use Policy (6 sections)
- **Cookie consent banner** — Essential Only / Accept All
- **ToS checkbox** on registration (blocks signup until accepted)
- **ToS version tracking** — Re-acceptance modal when version changes
- **GDPR data export** — ZIP download of all user data
- **GDPR account deletion** — 30-day grace period with anonymization
- **AI output disclaimer** — "AI-generated content may contain errors"
- **AI metadata tagging** — All AI messages tagged with `ai_generated`, `ai_provider`, `ai_model_id`
- **Content flagging** — Report/flag system with admin review queue
- **Voice consent** — ElevenLabs consent logging
- **DPA acceptance** — For enterprise organizations
- **Subscription cancellation** — Downgrade to Free with data retention

---

## 18. BILLING & PRICING

### 5 Plans
| Plan | AI Collabs/mo | Workspaces | Channels | Price |
|------|--------------|------------|----------|-------|
| Free | 50 | 3 | 5/ws | $0 |
| Starter | 500 | 10 | 20/ws | $29/mo |
| Pro | 5,000 | Unlimited | Unlimited | $99/mo |
| Business | 25,000 | Unlimited | Unlimited | $299/mo |
| Enterprise | Unlimited | Unlimited | Unlimited | Custom |

### Credit System
- AI collaboration: 10 credits
- Image generation: 25 credits
- Workflow execution: 15 credits
- File upload: 2 credits

---

## 19. API REFERENCE SUMMARY

- **Swagger UI**: `/api/docs`
- **ReDoc**: `/api/redoc`
- **OpenAPI JSON**: `/api/openapi.json`
- **522 documented paths** (some endpoints are dynamically registered)

### Key Endpoint Groups
| Prefix | Count | Purpose |
|--------|-------|---------|
| /api/auth/* | 8 | Authentication |
| /api/workspaces/* | 25 | Workspace management |
| /api/channels/* | 15 | Channel CRUD, messaging |
| /api/projects/* | 37 | Project management |
| /api/workspaces/*/code-repo/* | 23 | Code repository |
| /api/workspaces/*/wiki/* | 12 | Wiki/Docs |
| /api/workflows/* | 27 | Automation workflows |
| /api/media/* | 40 | Content creation |
| /api/admin/* | 16 | Administration |
| /api/legal/* | 12 | Compliance |

---

## 20. DEPLOYMENT ARCHITECTURE

### Production (Emergent Kubernetes)
```
- Container: Docker (built by Emergent)
- Orchestration: Kubernetes
- Database: MongoDB Atlas (dedicated)
- Frontend: Built React SPA served via Craco
- Backend: Uvicorn running FastAPI
- Process Manager: Supervisor
- TLS: Managed by Kubernetes ingress
```

### Environment Variables
```
# Backend (.env)
MONGO_URL=mongodb://... (Atlas connection string)
DB_NAME=nexus
# Provider-specific API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)
STRIPE_API_KEY=...
ENCRYPTION_KEY=... (Fernet key for API key encryption)
SUPER_ADMIN_EMAIL=...
CORS_ORIGINS=...

# Frontend (.env)
REACT_APP_BACKEND_URL=https://... (production URL)
WDS_SOCKET_PORT=443
```

---

## 21. SECURITY

- **API key encryption** — Fernet symmetric encryption at rest
- **HTTPOnly cookies** — Session tokens not accessible via JavaScript
- **SameSite=None, Secure=True** — Cross-origin cookie support
- **XSS sanitization** — Script/iframe/event handler stripping on user input
- **Rate limiting** — 120 requests/minute per IP
- **CORS** — Configurable allowed origins
- **Per-tenant encryption** — Optional dedicated keys per organization
- **Input validation** — Pydantic models on all endpoints
- **401 cascade prevention** — Single redirect flag + 10s grace period
- **Content flagging** — User-reported content with admin review

---

## 22. PERFORMANCE OPTIMIZATIONS

- **Parallel AI execution** — `asyncio.gather` with staggered starts (0.8s between agents)
- **Prompt truncation** — 12K system + 8K user char limits prevent 400 errors
- **Shared context pre-fetch** — KB + repo context fetched once, shared across all agents
- **Message limit** — Returns newest 200 messages (not oldest 500)
- **2-second polling** — Balanced between responsiveness and server load
- **Polling stops on 401** — Prevents request storms when session expires
- **Retry with jitter** — Exponential backoff + random jitter prevents thundering herd
- **CSS Grid layout** — Bulletproof chat layout (no flex collapse)
- **Monaco lazy loading** — Code editor loads only when opened

---

*Document generated March 2026. Nexus Platform Beta v1.0.*
