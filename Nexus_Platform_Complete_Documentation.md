# NEXUS PLATFORM — Complete Technical & Feature Documentation

## Document Version: 1.0
## Date: March 5, 2026
## Platform Version: Production Release

---

# TABLE OF CONTENTS

1. Executive Summary
2. Platform Architecture
3. Technology Stack
4. Frontend Architecture
5. Backend Architecture
6. Database Architecture
7. Authentication & Security
8. Complete Feature Catalog
9. API Reference
10. Third-Party Integrations
11. Testing & Quality Assurance
12. Deployment Architecture
13. Appendix

---

# 1. EXECUTIVE SUMMARY

Nexus is a cloud-hosted, multi-tenant AI collaboration platform that enables multiple AI models to work together on projects with real-time human observation and control. The platform supports 9 AI models, visual workflow automation, multimedia content generation, project lifecycle management, and enterprise-grade organization management.

**Key Metrics:**
- 40 test iterations, all passing
- 200+ API endpoints
- 50+ frontend components
- 30+ database collections
- 9 AI model integrations
- 3 cloud storage provider integrations

---

# 2. PLATFORM ARCHITECTURE

## 2.1 High-Level Architecture

```
[Browser/Desktop Client]
        |
    [HTTPS/WSS]
        |
[Kubernetes Ingress (Emergent)]
    /           \
[Frontend]   [Backend API]
(React)      (FastAPI)
   |              |
   |         [MongoDB Atlas]
   |              |
   |         [External APIs]
   |         - OpenAI (GPT, Sora 2, TTS, Whisper)
   |         - Anthropic (Claude)
   |         - Google (Gemini Nano Banana)
   |         - DeepSeek, Grok, Perplexity, Mistral, Cohere, Groq
   |         - Stripe (Payments)
   |         - Cloud Storage (Google Drive, OneDrive, Dropbox)
```

## 2.2 Service Architecture

- **Frontend**: Port 3000 (React dev server / Craco build)
- **Backend**: Port 8001 (FastAPI via Uvicorn)
- **Database**: MongoDB (local in dev, Atlas in production)
- **Routing**: Kubernetes ingress routes `/api/*` to backend, all other paths to frontend
- **Process Management**: Supervisor manages both frontend and backend processes

## 2.3 Communication Patterns

- **REST API**: All CRUD operations via JSON over HTTPS
- **Server-Sent Events (SSE)**: Real-time workflow execution streaming
- **Polling**: Notification polling (30s interval with visibility-based pause)
- **Background Tasks**: asyncio tasks for AI collaboration, scheduled actions, webhook delivery

---

# 3. TECHNOLOGY STACK

## 3.1 Frontend Stack

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Framework | React | 18.x | UI rendering |
| Build Tool | Craco | 7.x | CRA configuration override |
| Styling | Tailwind CSS | 3.x | Utility-first CSS |
| UI Components | Shadcn/UI | Latest | Accessible component library |
| Visual Workflow Editor | React Flow | 11.x | DAG canvas for workflows |
| Icons | Lucide React | Latest | Icon library |
| HTTP Client | Axios | Latest | API communication |
| Routing | React Router | 6.x | Client-side routing |
| Toast Notifications | Sonner | Latest | Notification toasts |
| Font | Syne (headings), Manrope (body) | - | Typography |
| State Management | React useState/useEffect/useCallback | Built-in | Local state |
| Internationalization | Custom i18n (en.json + es.json) | Custom | English + Spanish |

### Frontend File Structure
```
/app/frontend/src/
├── components/
│   ├── ui/                          # Shadcn UI primitives (30+ components)
│   ├── ChatPanel.js                 # Chat interface with @mentions, voice input
│   ├── MessageBubble.js             # Message rendering (code blocks, handoffs, tools)
│   ├── MentionDropdown.js           # @mention autocomplete
│   ├── Sidebar.js                   # Workspace sidebar navigation
│   ├── ProjectPanel.js              # Projects with Kanban, search, bulk ops
│   ├── WorkflowCanvas.js            # React Flow visual editor
│   ├── FlowNode.js                  # Custom workflow node component
│   ├── NodeConfigPanel.js           # Node configuration sidebar
│   ├── RunMonitor.js                # Workflow execution monitor
│   ├── WorkflowPanel.js             # Workflow list with search/filter
│   ├── ArtifactPanel.js             # Artifacts with versioning, attachments
│   ├── KnowledgeBasePanel.js        # Knowledge base with rich editor
│   ├── SchedulePanel.js             # Agent schedule management
│   ├── ImageGenPanel.js             # Image generation (Gemini)
│   ├── VideoPanel.js                # Video generation (Sora 2)
│   ├── AudioPanel.js                # Audio/TTS generation
│   ├── MediaLibraryPanel.js         # Centralized media library
│   ├── GanttChart.js                # Gantt chart visualization
│   ├── PlannerCalendar.js           # Calendar/planner view
│   ├── RepositoryPanel.js           # Org file repository
│   ├── IntegrationSettings.js       # Integration + encryption + cloud storage settings
│   ├── WalkthroughBuilder.js        # Walkthrough/tour builder
│   ├── NotificationBell.js          # Notification dropdown
│   ├── BugReportModal.js            # Support request modal (5 ticket types)
│   ├── FileUpload.js                # File upload with chunking
│   ├── KeyboardShortcuts.js         # Global keyboard shortcuts + palette
│   ├── OnboardingTour.js            # 4-step guided tour
│   └── AIKeySetup.js                # AI key configuration per workspace
├── pages/
│   ├── LandingPage.js               # Marketing landing page
│   ├── AuthPage.js                  # Login/Register/Org signup
│   ├── Dashboard.js                 # Main dashboard with sidebar
│   ├── WorkspacePage.js             # Workspace with grouped tabs
│   ├── OrgDashboard.js              # Organization dashboard
│   ├── OrgLoginPage.js              # Org-specific login
│   ├── OrgAdminDashboard.js         # Org admin panel
│   ├── OrgAnalytics.js              # Org analytics
│   ├── SettingsPage.js              # Settings with sidebar
│   ├── BillingPage.js               # Billing & plans
│   ├── AdminDashboard.js            # Platform admin
│   ├── DownloadPage.js              # Desktop app downloads
│   ├── BugListPage.js               # Support ticket list
│   └── MarketplacePage.js           # Workflow marketplace
├── contexts/
│   └── LanguageContext.js            # i18n provider
├── i18n/
│   ├── translations.js              # Loader
│   ├── en.json                      # English translations
│   └── es.json                      # Spanish translations
└── lib/
    └── api.js                       # Axios instance with cookie auth
```

## 3.2 Backend Stack

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Framework | FastAPI | 0.100+ | Async REST API |
| Server | Uvicorn | Latest | ASGI server |
| Database Driver | Motor | Latest | Async MongoDB driver |
| Validation | Pydantic | 2.x | Request/response models |
| Encryption | Cryptography (Fernet) | Latest | API key + token encryption |
| HTTP Client | HTTPX | Latest | Async external API calls |
| AI Integration | Direct Provider APIs | Custom | LLM, TTS, image, video APIs |
| Payments | Stripe | Latest | Subscription billing |
| Auth | JWT via HTTPOnly cookies | Custom | Session management |

### Backend File Structure
```
/app/backend/
├── server.py                        # Main app, core routes, AI collaboration engine
├── ai_providers.py                  # Direct AI API calls with retry logic
├── workflow_engine.py               # Workflow orchestrator, DAG execution, SSE
├── routes_auth_email.py             # Email/password authentication
├── routes_orgs.py                   # Organization CRUD, org-level rollup
├── routes_admin.py                  # Platform admin, RBAC, role management
├── routes_rbac.py                   # Role-based access control
├── routes_billing.py                # Stripe checkout, plan management
├── routes_billing_advanced.py       # Invoices, statements, org billing, cost allocation
├── routes_pricing.py                # Credits engine, free tier, overage
├── routes_projects.py               # Projects, tasks, comments, attachments, subtasks
├── routes_plm_advanced.py           # Sprints, dependencies, milestones, portfolios, automation, custom fields
├── routes_workflows.py              # Workflow CRUD, nodes, edges, triggers, variables, RBAC
├── routes_marketplace.py            # Marketplace templates, artifacts, versioning
├── routes_ai_keys.py                # API key encryption, storage, validation
├── routes_ai_tools.py               # 9 AI tools for autonomous agent actions
├── routes_agent_schedules.py        # Scheduled agent actions with background checker
├── routes_handoffs_memory.py        # Handoffs, knowledge base, semantic search, file upload
├── routes_export_audit.py           # Export (JSON/Markdown/CSV), audit trail
├── routes_webhooks.py               # Outbound + inbound webhooks
├── routes_model_perf.py             # Model performance, auto-routing, disagreements, checkpoints
├── routes_image_gen.py              # Image generation (Gemini Nano Banana)
├── routes_media.py                  # Video (Sora 2), TTS, STT, media library, storyboard, podcast
├── routes_enhancements.py           # Usage analytics, summarization, personas, templates, branching
├── routes_walkthroughs_builder.py   # Walkthrough builder, SDK endpoints, analytics
├── routes_reports.py                # Gantt, planner, project/task reports
├── routes_support_desk.py           # Support tickets, queues, SLA, replies
├── routes_repository.py             # Org repository, integration settings, per-tenant encryption
├── routes_cloud_storage.py          # Google Drive, OneDrive, Dropbox connectors
├── routes_integrations.py           # External integration status stubs
├── routes_nexus_agents.py           # Custom AI agent personas
├── routes_notifications.py          # Notification system
├── routes_tasks.py                  # Standalone task sessions
├── seed_workflow_templates.py       # 4 seeded workflow templates
└── .env                             # Environment variables
```

## 3.3 Database Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Database | MongoDB | Document storage |
| Production | MongoDB Atlas | Managed cloud database |
| Driver | Motor (async) | Non-blocking queries |
| Indexes | 60+ indexes | Query performance |

---

# 4. AUTHENTICATION & SECURITY

## 4.1 Authentication Methods
- **Email/Password**: BCrypt hashed passwords, session tokens
- **Google OAuth**: Emergent-managed Google social login
- **Organization Login**: Branded login pages per org (`/org/{slug}`)

## 4.2 Session Management
- HTTPOnly cookies with `samesite=none`, `secure=true`
- Session tokens stored in `user_sessions` collection
- Token expiry with automatic cleanup

## 4.3 Role-Based Access Control (RBAC)

### Platform Roles (5 levels)
| Role | Admin Panel | Edit All | Delete | Support Tools |
|------|------------|----------|--------|--------------|
| Super Admin | Yes | Yes | Yes | Yes |
| Platform Support | Yes | Yes | **No** | Yes |
| Admin | Yes | Yes | Yes | No |
| Moderator | View only | Own only | No | No |
| User | No | No | No | No |

### Organization Roles (4 levels)
- **Owner**: Full org control
- **Admin**: Manage members, settings
- **Member**: Use workspaces
- **Viewer**: Read-only access

## 4.4 Encryption
- **API Keys**: Fernet symmetric encryption at rest
- **Per-Tenant Encryption**: Optional dedicated Fernet key per organization
- **Cloud Storage Tokens**: OAuth tokens encrypted before storage
- **Org Integration Keys**: Encrypted with org-level or platform-level Fernet

---

# 5. COMPLETE FEATURE CATALOG

## 5.1 AI Collaboration Engine

### Multi-Agent Chat
- 9 AI models collaborate in real-time channels: Claude, ChatGPT, Gemini, Perplexity, Mistral, Cohere, Groq, DeepSeek, Grok
- User-provided API keys per model (encrypted storage)
- @mentions to target specific agents (`@claude`, `@everyone`)
- Mention autocomplete dropdown in chat input
- Multi-line textarea input (Enter = newline, Ctrl+Enter = send)
- Voice input via microphone button (Whisper transcription)
- Audio playback of AI responses (TTS with Nova voice)
- Auto-retry with exponential backoff for rate limits
- System message consolidation (duplicate API key errors collapsed)

### AI Agent Tools (9 tools)
AI agents can autonomously execute actions during collaboration:
1. `create_project` — Create a new project in the workspace
2. `create_task` — Create a task within a project
3. `update_task_status` — Update task status
4. `list_projects` — List workspace projects
5. `list_tasks` — List project tasks
6. `create_artifact` — Save output as artifact
7. `save_to_memory` — Write to knowledge base
8. `read_memory` — Read from knowledge base
9. `handoff_to_agent` — Hand off context to another agent

### Auto-Features (during collaboration)
- **Auto Handoff Extraction**: Confidence, open questions, assumptions extracted from each AI response
- **Auto Disagreement Detection**: Conflicting AI responses auto-flagged (conflict score >= 3)
- **Auto Artifact Creation**: Code blocks in AI responses auto-saved as code artifacts
- **Knowledge Base Injection**: Top 10 KB entries injected into AI system prompts

### Structured Handoffs
- Agent-to-agent context passing with 5 context types: general, findings, code, recommendation, analysis
- Handoff messages render as indigo-styled cards in chat
- Acknowledge endpoint for receiving agent

### Disagreement Resolution
- Manual + auto-detected disagreements
- Weighted confidence voting
- Resolution with winning position and vote counts

## 5.2 Workflow Engine

### Visual Canvas (React Flow)
- Drag-and-drop DAG editor with 12+ node types
- Solid edges with animated flow direction + arrow markers
- Condition nodes with True (green, right) and False (red, bottom) output handles
- Merge nodes with strategy selector (Concatenate / First Response / Summarize)
- Undo/Redo (Ctrl+Z / Ctrl+Shift+Z, 20-step history)
- Node duplication (Ctrl+D)
- Right-click context menu (node: Configure/Duplicate/Delete, canvas: Add node)
- Validation before activation (checks Input/Output, orphans, required fields)

### Node Types
| Type | Purpose |
|------|---------|
| Input | Receives initial data |
| Output | Collects final output |
| AI Agent | Calls an AI model with prompt |
| Condition | Branches on true/false logic |
| Merge | Combines multiple upstream outputs |
| Human Review | Pauses for approval (5 checkpoint types) |
| Trigger | Webhook/Cron/Event trigger |
| Text to Video | Sora 2 video generation |
| Text to Speech | OpenAI TTS |
| Text to Music | Music generation (stub) |
| Transcribe | Whisper STT |
| Video Compose | Clip composition |
| Media Publish | Publish to external platform |

### Execution Engine
- Topological sort for DAG traversal
- Parallel branch support
- SSE streaming for real-time progress
- Per-node execution tracking (status, duration, tokens, cost)
- Execution history with per-node inspection

### Workflow Triggers
- Webhook (public URL with token)
- Cron (scheduled expression)
- Event (message.created, task.completed, etc.)
- Manual

### Workflow RBAC
- Owner: full access
- Admin: full access
- Moderator: edit + run, no activate/delete
- User: view only
- Viewer: view only

### Variable System
- `{{source.field}}` syntax for data mapping between nodes
- Auto-detected variables from all nodes
- "Insert Variable" picker with autocomplete in node config

### Version Control
- Auto-version on publish
- Version history with snapshots
- Rollback to any previous version

## 5.3 Project Lifecycle Management (PLM)

### Phase 1 — Foundation
- **Work Item Types**: Task, Story, Bug, Epic, Subtask
- **Due Dates**: Date picker with overdue highlighting
- **Subtasks**: Parent-child linking, subtask count tracking
- **Comments**: Threaded comments per task with author info
- **File Attachments**: Upload files to tasks
- **Labels**: Tag-based categorization
- **Story Points**: Agile estimation
- **Activity Log**: All changes tracked (actor, action, timestamp, details)
- **My Tasks**: Consolidated view of all assigned tasks across projects

### Phase 2 — Agile & Waterfall
- **Sprints**: CRUD, assign tasks, sprint board (Kanban filtered by sprint), burndown data
- **Dependencies**: 4 types (finish-to-start, start-to-start, finish-to-finish, start-to-finish)
- **Milestones**: Target dates, task counts, status tracking
- **Gantt Chart**: Horizontal bar timeline with dependency arrows, milestone diamonds
- **Planner Calendar**: Month/week view with task cards on due dates

### Phase 3 — Portfolio & Program
- **Programs**: Group related projects
- **Portfolios**: Group programs, health dashboard (green/yellow/red)

### Phase 4 — Time & Automation
- **Time Tracking**: Log hours per task, timesheets with date filtering
- **Automation Rules**: 7 trigger events, 6 action types
- **Recurring Tasks**: Template-based with interval

### Phase 5 — Custom Fields
- **6 Field Types**: Text, number, date, dropdown, checkbox, URL
- **Field Templates**: Save and apply across projects
- **Per-Task Custom Values**: Stored as nested object

## 5.4 Multimedia Content Studio

### Image Generation
- Gemini Nano Banana model via Emergent LLM key
- User API key option
- Gallery with metrics tracking
- Auto-save as artifact from chat

### Video Generation
- Sora 2 text-to-video
- 4 sizes (HD 720p, Widescreen, Portrait, Square)
- 3 durations (4/8/12 seconds)
- 6 style presets (natural, cinematic, animated, documentary, slow motion, timelapse)
- Negative prompts
- Image-to-video endpoint
- Multi-agent storyboarding (scene generation + batch video creation)

### Audio Generation
- OpenAI TTS with 9 voices (Alloy, Ash, Coral, Echo, Fable, Nova, Onyx, Sage, Shimmer)
- Standard + HD quality models
- Speed control (0.5x - 2x)
- TTS preview (instant, no save)
- Streaming TTS (chunked for long text)
- Podcast generation (multi-agent segments)

### Speech-to-Text
- OpenAI Whisper transcription
- Voice input button in chat (microphone icon)
- Supports webm, mp3, wav, etc.

### Media Library
- Unified library (video, audio, image)
- Smart folders (Recent, Starred, Videos, Audio, Images)
- Storage usage overview with limit bar
- Grid + List view toggle
- Drag-and-drop upload dropzone
- Bulk operations (tag, move, delete)
- Share links with expiry
- Asset detail dialog with preview (video/audio/image)
- Media version history + restore
- Media scheduling (recurring generation)
- Full analytics dashboard (summary, cost, performance, timeseries)

## 5.5 Marketplace & Artifacts

### Workflow Marketplace
- Publish workflows as templates (global or org-scoped)
- Browse/search/filter by category
- One-click import into workspace
- 5-star rating system
- Usage count tracking

### Artifact Management
- Content types: text, JSON, code, markdown, image
- Versioning with restore and unified diff
- Change summaries (chars added/removed)
- File attachments on artifacts
- Comments (threaded with author)
- Tags and pinning
- Auto-creation from AI code blocks in chat
- "Save as Artifact" button on AI messages

## 5.6 Knowledge Base
- Workspace-scoped persistent memory
- 5 categories: General, Insight, Decision, Reference, Context
- Search (text + semantic word-overlap scoring)
- File upload (PDF/DOCX/TXT/MD/CSV) with auto-chunking (500 words, 50 overlap)
- Rich text editor with Markdown toolbar (Bold, Italic, Code, List, Link, Attachment)
- AI agents can read/write via tools
- Context injection into AI prompts (top 10 entries)

## 5.7 Scheduled Agent Actions
- 4 action types: Project Review, Task Triage, Standup Summary, Custom
- 8 interval options (15 min to daily)
- Multi-worker safe (MongoDB atomic claims)
- Execution history with status tracking
- Manual trigger

## 5.8 Export & Audit Trail
- Channel export (JSON + Markdown + CSV)
- Workspace export (full data dump)
- Workflow export (nodes, edges, run history)
- Invoice export (JSON + CSV)
- 14 audit action types
- Per-workspace audit log with user enrichment

## 5.9 Webhooks
- **Outbound**: 15 event types, HMAC signatures, delivery tracking, auto-disable after 10 failures
- **Inbound**: Public trigger URLs for workflows, input mapping (dot-notation JSONPath)

## 5.10 Walkthrough Builder
- Walkthrough CRUD with versioning
- 6 step types: Tooltip, Modal, Spotlight, Action, Beacon, Checklist
- Branching rules (condition → then/else step)
- 5 trigger types: Page Load, First Visit, Event, Manual, Scheduled
- 4 frequency rules: Once, Until Completed, Every N Days, Always
- Theme customization (colors, border radius, overlay blur)
- SDK endpoints (active walkthroughs, event ingestion, progress tracking)
- Resource Center (categorized progress)
- Analytics (starts, completions, dismissals, step funnel with drop-off rates)
- Validation (missing steps, broken branch refs, empty selectors)
- Full permissions matrix (5 roles)

## 5.11 Pricing Engine
- Credits-based billing: 7 action types with costs
- 3 plans: Free (100 credits), Pro (5000, $0.01 overage), Enterprise (50000, $0.005 overage)
- Free tier manager: 6 daily limits
- Overage estimation (projected from daily rate)
- Credit transactions log
- Real-time limit checking

## 5.12 Advanced Billing
- **User Billing**: Account, address, tax ID, invoices, payment history, receipts
- **Invoice Generation**: Monthly with line items, plan cost, overage, exportable
- **Org Billing**: Separate accounts, billing contacts, spending limits, cost allocation by workspace
- **Subscription Management**: Plan upgrade/downgrade with history
- **Notifications**: Approaching limit, overage, unpaid invoices

## 5.13 Support Desk (Light JSD)
- 8 ticket types: Bug, Enhancement, Question, Billing, General Support, Incident, Feature Request, Access Request
- 6 statuses: Open, In Progress, Waiting on Customer, Waiting on Support, Resolved, Closed
- 4 priorities: Low, Medium, High, Urgent
- Threaded replies (customer-visible + internal notes)
- File attachments on tickets
- SLA tracking: 3 policies (Standard 24h/72h, Priority 4h/24h, Enterprise 1h/8h)
- First response + resolution breach detection
- Auto-status updates on reply
- Agent dashboard with queue counts, priority/type breakdown
- Per-type ticket queues
- KB article suggestions

## 5.14 Organization Management
- Multi-tenant with logical data isolation
- Custom login URLs (`/org/{slug}`)
- Org-level rollup: Projects, Tasks (Kanban), Workflows, Analytics
- Gantt chart + Planner at org level
- Per-org integration key overrides (encrypted)
- Per-tenant encryption keys
- Billing contacts and spending limits

## 5.15 Repository (Org File Store)
- File upload with auto-indexing (content extraction for search)
- Preview type detection (image, PDF, video, audio, text, document)
- Folder organization
- Full-text search across filename, description, tags, content
- File preview dialog (renders images, PDFs, video, audio, text)
- Cloud storage connectors: Google Drive, OneDrive, Dropbox
- OAuth connection management (user-level + org-level)
- File import from cloud to repository

## 5.16 Model Performance & Auto-Routing
- Per-model stats: message count, avg response time, content length, code quality
- Task-type recommendations with scoring (speed, quality, volume factors)
- Auto-routing: Classifies task from prompt → selects best model
- Quick Rate widget (thumbs up/down on AI messages)
- Strength analysis per model

## 5.17 Reports
- **Workspace Reports**: Completion rate, status/priority/type distributions, assignee workload, overdue tasks, project summaries, hours logged
- **Org Reports**: Cross-workspace rollup, per-workspace breakdown, team utilization
- **Velocity Report**: Sprint velocity across completed sprints
- **Gantt Data**: Tasks + milestones + dependencies
- **Planner Data**: Tasks grouped by date with overdue highlighting

## 5.18 Enhancement Features
- **Usage Analytics Dashboard**: Messages by type, model usage, daily activity, artifact/workflow counts
- **Smart Summarization**: One-click channel summary (key decisions, action items, open questions)
- **Conversation Branching**: Fork channels with copied message history
- **Agent Personas Library**: 4 built-in (Senior Code Reviewer, Technical Writer, Data Analyst, Business Strategist) + custom
- **Workspace Templates**: 4 pre-built (Product Launch, Code Review Team, Research Lab, Content Studio) with one-click deploy
- **Comments on Artifacts**: Threaded discussion per artifact
- **@channel Notifications**: Targeted workspace member notifications
- **Workspace Activity Timeline**: Combined audit + workflow run timeline
- **Keyboard Shortcuts**: Ctrl+K search, Ctrl+N new, Ctrl+/ palette
- **Onboarding Tour**: 4-step guided walkthrough (localStorage persistence)

## 5.19 Desktop Application
- Downloadable Windows .exe (32-bit + 64-bit)
- Online mode (connects to deployed server)
- Offline mode (local instance)

## 5.20 Internationalization
- English (en.json) + Spanish (es.json)
- Per-user language preference
- AI responses respect language setting

---

# 6. DATABASE COLLECTIONS

| Collection | Purpose | Key Indexes |
|------------|---------|-------------|
| users | User accounts | user_id (unique), email (unique) |
| user_sessions | Auth sessions | session_token (unique) |
| workspaces | Workspaces | workspace_id (unique), owner_id |
| channels | Chat channels | channel_id (unique), workspace_id |
| messages | Chat messages | message_id (unique), channel_id |
| organizations | Orgs/tenants | org_id (unique), slug (unique) |
| org_memberships | Org member roles | (org_id, user_id) unique |
| projects | Projects | project_id (unique), workspace_id |
| project_tasks | Tasks/work items | task_id (unique), project_id |
| task_comments | Task comments | comment_id, task_id |
| task_attachments | Task files | attachment_id, task_id |
| task_activity | Task change log | task_id |
| task_dependencies | Task links | dependency_id |
| sprints | Agile sprints | sprint_id, project_id |
| milestones | Project milestones | milestone_id, project_id |
| programs | Program groups | program_id |
| portfolios | Portfolio groups | portfolio_id |
| time_entries | Time tracking | entry_id, task_id, user_id |
| automation_rules | Automation | rule_id |
| recurring_tasks | Recurring tasks | recurring_id |
| custom_fields | Custom field defs | field_id, project_id |
| workflows | Workflows | workflow_id (unique), workspace_id |
| workflow_nodes | Workflow nodes | node_id (unique), workflow_id |
| workflow_edges | Workflow edges | edge_id (unique), workflow_id |
| workflow_runs | Execution runs | run_id (unique), workflow_id |
| node_executions | Per-node execution | exec_id (unique), run_id |
| workflow_templates | Built-in templates | template_id (unique) |
| workflow_triggers | Webhook/cron triggers | trigger_id |
| marketplace_templates | Published templates | marketplace_id (unique) |
| marketplace_ratings | Template ratings | (marketplace_id, user_id) |
| artifacts | Saved outputs | artifact_id (unique), workspace_id |
| artifact_versions | Version history | (artifact_id, version) |
| artifact_comments | Artifact discussion | artifact_id |
| artifact_attachments | Artifact files | artifact_id |
| workspace_memory | Knowledge base | memory_id (unique), (workspace_id, key) |
| handoffs | Agent handoffs | handoff_id (unique), channel_id |
| handoff_extractions | Auto-extracted handoffs | task_id |
| disagreements | Agent disagreements | disagreement_id (unique), channel_id |
| agent_schedules | Scheduled actions | schedule_id (unique), workspace_id |
| schedule_runs | Schedule execution log | run_id, schedule_id |
| analytics | AI usage analytics | workspace_id |
| notifications | User notifications | user_id |
| bug_reports | Legacy bug reports | reporter_id |
| support_tickets | Support tickets | ticket_id (unique), requester_id, assigned_to |
| ticket_replies | Ticket replies | ticket_id |
| ticket_activity | Ticket change log | ticket_id |
| ticket_attachments | Ticket files | ticket_id |
| nexus_agents | Custom AI agents | agent_id (unique) |
| webhooks | Outbound webhooks | webhook_id (unique), workspace_id |
| webhook_deliveries | Delivery log | webhook_id |
| inbound_webhooks | Inbound triggers | inbound_hook_id |
| walkthroughs | Product tours | walkthrough_id (unique) |
| walkthrough_versions | Tour versions | (walkthrough_id, version_number) |
| walkthrough_progress | User tour progress | (user_id, walkthrough_id) |
| walkthrough_events | Tour event log | walkthrough_id |
| generated_images | Image gen records | image_id (unique), workspace_id |
| image_data | Image binary data | image_id (unique) |
| image_gen_metrics | Image gen metrics | workspace_id |
| media_items | All media records | media_id (unique), (workspace_id, type) |
| media_data | Media binary data | media_id (unique) |
| media_metrics | Media gen metrics | workspace_id |
| media_jobs | Generation job queue | job_id |
| media_shares | Share links | token |
| media_schedules | Recurring media gen | schedule_id |
| storyboards | Video storyboards | storyboard_id |
| podcasts | Podcast records | podcast_id |
| personas | Agent personas | persona_id (unique) |
| workspace_templates | WS template defs | - |
| credit_balances | Monthly credits | (user_id, month) unique |
| credit_transactions | Credit usage log | user_id |
| daily_usage | Free tier daily tracking | key (unique) |
| billing_accounts | User billing | user_id (unique) |
| org_billing | Org billing | org_id (unique) |
| invoices | Monthly invoices | invoice_id (unique), (user_id, period) |
| payments | Payment history | user_id |
| plan_changes | Plan change log | user_id |
| platform_settings | Global config | key |
| org_integrations | Org API key overrides | (org_id, key) unique |
| org_encryption_keys | Per-tenant keys | org_id |
| org_repository | Org file store | file_id (unique), (org_id, folder) |
| repo_file_data | File binary data | file_id (unique) |
| cloud_connections | Cloud storage OAuth | connection_id (unique), (user_id, provider) |
| audit_log | Audit trail | audit_id, (workspace_id, timestamp) |
| field_templates | Custom field templates | - |

---

# 7. TESTING & QUALITY ASSURANCE

## Test Iterations Summary

| Iteration | Focus | Results |
|-----------|-------|---------|
| 18 | Workspace features | 22/22 passed |
| 19 | Workflow Engine | 22/22 backend, 100% frontend |
| 20 | Marketplace & Artifacts | 31/31 passed |
| 21 | AI Tools & @Mentions | 16/16 passed |
| 22 | Scheduled Agent Actions | 21/21 passed |
| 23 | Artifact versioning + Bulk ops | 28/28 passed |
| 24 | P1 features (Handoffs, Memory, Logs) | 21/23 (2 skipped) |
| 25 | Export, Webhooks, Model Perf | 22/24 (2 skipped) |
| 26 | Spec gap filling | 20/20 passed |
| 27 | Org-level features | 13/13 passed |
| 28 | Final spec gaps | 22/22 passed |
| 29 | 12 Enhancements | 16/16 + 6/6 frontend |
| 30 | Full QA regression | 73/78 (4 skipped, 1 setup) |
| 31 | Walkthrough + Pricing | 22/22 passed |
| 32 | Multimedia suite | 32/32 passed |
| 33 | PLM Phase 1 | 28/28 passed |
| 34 | PLM Phases 2-5 | 37/37 passed |
| 35 | Gantt, Planner, Reports, Support | 28/28 passed |
| 36 | Repository, Integrations, Encryption | 30/30 passed |
| 37 | Frontend components (6) | 11/11 + 6/6 frontend |
| 38 | Cloud Storage connectors | 18/18 passed |
| 39 | UX improvements (21 items) | 8/8 + all verified |
| 40 | Advanced Billing | 26/26 passed |

---

# 8. DEPLOYMENT

- **Platform**: Emergent native Kubernetes deployment
- **Container**: Single pod with supervisor managing frontend + backend
- **Scaling**: Async FastAPI handles concurrent requests; MongoDB Atlas scales independently
- **Cost**: 50 credits/month deployment slot
- **SSL**: Automatic HTTPS via Kubernetes ingress
- **Monitoring**: Backend logs via supervisor, error tracking via logging module

---

*Document generated from the Nexus codebase. For API reference, see the FastAPI auto-generated docs at `/api/docs`.*
