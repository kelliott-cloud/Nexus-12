# NEXUS PLATFORM — Complete Feature List & Functionality Guide

---

## 1. AUTHENTICATION & USER MANAGEMENT

### 1.1 Email/Password Authentication
- Register with email, name, password (bcrypt hashed)
- Login returns HTTPOnly session cookie (samesite=none, secure=true)
- Session tokens stored in MongoDB with expiry

### 1.2 Google OAuth
- One-click Google sign-in via Emergent-managed OAuth
- Auto-creates user account on first login
- Merges with existing email account if same email

### 1.3 Organization Login
- Branded login pages at `/org/{slug}` (e.g., `/org/urtech`)
- Custom domain support (configurable via API)
- Members must be invited to access org workspaces

### 1.4 Profile Management
- Editable display name (auto-saves on blur)
- View email, auth method, member since date
- Plan and role badges visible

### 1.5 Platform Roles (5 levels)
- **Super Admin**: Full access including delete
- **Platform Support**: Full access EXCEPT delete
- **Admin**: Admin panel access, manage users
- **Moderator**: View admin panel, moderate content
- **User**: Standard access

### 1.6 Organization Roles (4 levels)
- **Owner**: Full org control
- **Admin**: Manage members, settings, workspaces
- **Member**: Use workspaces, create content
- **Viewer**: Read-only access

---

## 2. WORKSPACES & CHANNELS

### 2.1 Workspaces
- Create/edit/delete workspaces with name and description
- Disable/enable workspaces (soft disable, not delete)
- Pin workspaces to dashboard (persisted in localStorage)
- Search and sort workspaces (by name, recency, agent count)
- Workspace cards show colored initial, agent dots, agent count

### 2.2 Channels
- Create channels within workspaces
- Assign AI agents (up to 9 models) per channel
- Channel-level AI collaboration
- Branch conversations (fork channel with copied history)

---

## 3. AI COLLABORATION ENGINE

### 3.1 Multi-Agent Chat
- 9 AI models: Claude, ChatGPT, Gemini, Perplexity, Mistral, Cohere, Groq, DeepSeek, Grok
- User-provided API keys per model (Fernet encrypted at rest)
- Real-time sequential agent responses
- Retry with exponential backoff for rate limits (429 errors)

### 3.2 @Mentions
- Type `@` to trigger autocomplete dropdown
- `@agentname` targets specific agent to respond
- `@everyone` triggers all agents in channel
- Mention chips rendered with agent-specific colors in messages

### 3.3 Chat Input
- Multi-line textarea (Enter = new line, Ctrl+Enter = send)
- Voice input via microphone button (Whisper transcription)
- File upload with auto-artifact creation
- @mention autocomplete integration

### 3.4 Message Rendering
- Code blocks with language label + copy button
- @mention chips with agent colors
- Handoff messages in indigo-styled cards
- Tool execution results as compact activity cards
- System message consolidation (duplicate API key errors collapsed)

### 3.5 Message Actions (hover to reveal on AI messages)
- Save as Artifact (bookmark icon)
- Thumbs up / Thumbs down rating
- Audio playback (TTS with Nova voice)

### 3.6 AI Agent Tools (10 tools)
Agents can autonomously execute during collaboration:
1. **create_project** — Create project in workspace
2. **create_task** — Create task in project
3. **update_task_status** — Change task status
4. **list_projects** — List workspace projects
5. **list_tasks** — List project tasks
6. **create_artifact** — Save output as artifact
7. **save_to_memory** — Write to knowledge base
8. **read_memory** — Read from knowledge base
9. **handoff_to_agent** — Pass context to another agent
10. **execute_code** — Run Python/JavaScript/Bash in sandbox

### 3.7 Auto-Features (during collaboration)
- **Auto Handoff Extraction**: Confidence, open questions, assumptions extracted per AI response
- **Auto Disagreement Detection**: Conflicting AI responses flagged (score >= 3)
- **Auto Artifact Creation**: Code blocks in AI responses saved as code artifacts
- **Knowledge Base Injection**: Top 10 KB entries injected into AI system prompts

### 3.8 Structured Handoffs
- Agent-to-agent context passing
- 5 context types: general, findings, code, recommendation, analysis
- Acknowledge endpoint for receiving agent

### 3.9 Disagreement Resolution
- Manual + auto-detected disagreements
- Weighted confidence voting per agent
- Resolution with winning position

### 3.10 Smart Summarization
- One-click channel summary
- Extracts: key decisions, action items, open questions
- Agent involvement summary

---

## 4. WORKFLOW ENGINE

### 4.1 Visual Canvas (React Flow)
- Drag-and-drop DAG editor
- Solid edges with animated flow direction + arrow markers
- Undo/Redo (Ctrl+Z / Ctrl+Shift+Z, 20-step history)
- Node duplication (Ctrl+D)
- Right-click context menu (node: Configure/Duplicate/Delete, canvas: Add node)
- Validation before activation (checks Input/Output, orphans, required fields)

### 4.2 Node Types (15+)
- **Input**: Receives initial data
- **Output**: Collects final output
- **AI Agent**: Calls AI model with configurable prompt/temp/tokens
- **Condition**: True/False branching (green right handle, red bottom handle)
- **Merge**: Combines outputs (3 strategies: Concatenate, First Response, Summarize)
- **Human Review**: 5 checkpoint types (approve_reject, review_edit, select_option, provide_input, confirm_proceed)
- **Trigger**: Webhook/Cron/Event/Manual triggers
- **Code Execute**: Run code in sandbox
- **Text to Video**: Sora 2 video generation
- **Text to Speech**: OpenAI TTS
- **Text to Music**: Music generation (stub)
- **Transcribe**: Whisper STT
- **Video Compose**: Clip composition
- **Audio Compose**: Audio mixing
- **Media Publish**: Publish to external platform

### 4.3 Variable System
- `{{source.field}}` syntax for data mapping
- Auto-detected variables from all nodes
- "Insert Variable" picker with autocomplete in node config

### 4.4 Workflow Triggers
- **Webhook**: Public URL with token
- **Cron**: Scheduled expression (e.g., `0 9 * * *`)
- **Event**: message.created, task.completed, etc.
- **GitHub**: Push/PR events trigger workflows
- **Manual**: Run on demand

### 4.5 Workflow RBAC
- 5 permission levels: Owner, Admin, Moderator, User, Viewer
- Per-action permissions: view, edit, activate, run, delete

### 4.6 Execution Engine
- Topological sort for DAG traversal
- Parallel branch support with merge wait
- SSE streaming for real-time progress
- Per-node execution tracking (status, duration, tokens, cost)
- Execution history with per-node inspection

### 4.7 Version Control
- Auto-version on publish
- Version history with snapshots
- Rollback to any previous version

### 4.8 Workflow Templates (15 total)
- **Seeded (4)**: Research Synthesis, Content Production, Code Review, Competitive Analysis
- **Dev (3)**: Multi-Model Code Review Pipeline, Feature Builder, Bug Diagnosis
- **Extended (8)**: Competitive Analysis, Pitch Deck Creator, Blog Generator, Meeting Notes, Market Research, Social Media Campaign, Feedback Analyzer, Enhanced Code Review

---

## 5. PROJECT LIFECYCLE MANAGEMENT (PLM)

### 5.1 Projects
- Create/edit/delete projects within workspaces
- Link projects to channels
- Project status: active, on_hold, completed, archived

### 5.2 Work Items (Tasks)
- **5 types**: Task, Story, Bug, Epic, Subtask
- **4 statuses**: Todo, In Progress, Review, Done
- **4 priorities**: Low, Medium, High, Critical
- Due dates with overdue tracking
- Labels and story points
- Parent-child subtask linking
- Assignee (human or AI agent)

### 5.3 Task Views
- **List view**: With checkboxes for bulk selection
- **Kanban board**: Drag-and-drop between columns
- **Gantt chart**: Horizontal bar timeline with dependency arrows and milestone diamonds
- **Planner/Calendar**: Month/week view with task cards on due dates

### 5.4 Task Features
- **Comments**: Threaded per task with author info
- **File attachments**: Upload files to tasks
- **Activity log**: All changes tracked (actor, action, timestamp, details)
- **Subtasks**: Nested with progress tracking
- **Dependencies**: 4 types (finish-to-start, start-to-start, finish-to-finish, start-to-finish)
- **Code linking**: Link code artifacts to tasks
- **Custom fields**: 6 types (text, number, date, dropdown, checkbox, URL)

### 5.5 Bulk Operations
- Multi-select tasks
- Bulk status change
- Bulk priority change
- Bulk delete
- Select all / deselect all

### 5.6 Search & Filter
- Text search across title and description
- Filter by status, priority, assignee
- Sort by due date, updated, priority
- Workspace-wide task search

### 5.7 Sprints (Agile)
- Create/edit/close sprints with goal and dates
- Assign tasks to sprints
- Sprint board (Kanban filtered by sprint)
- Burndown data (total/done/remaining points + tasks)
- Velocity tracking across completed sprints

### 5.8 Milestones
- Target dates with status tracking
- Task counts per milestone
- Gantt visualization

### 5.9 Programs & Portfolios
- **Programs**: Group related projects
- **Portfolios**: Group programs
- **Portfolio health**: Completion rate, overdue count, health color (green/yellow/red)

### 5.10 Time Tracking
- Log hours per task with description and date
- Task-level time totals
- Timesheets with date range filtering and by-day breakdown

### 5.11 Automation Rules
- 7 trigger events: task.status_changed, task.assigned, task.due_soon, task.overdue, task.created, sprint.completed, milestone.reached
- 6 action types: set_field, assign_to, add_label, send_notification, move_to_sprint, change_priority

### 5.12 Recurring Tasks
- Template-based with configurable interval

### 5.13 My Tasks
- Consolidated view of all tasks assigned to current user across all projects
- Enriched with project name and workspace

---

## 6. ARTIFACTS & KNOWLEDGE BASE

### 6.1 Artifacts
- Content types: text, JSON, code, markdown, image
- **Versioning**: Auto-increment on update, change summaries (chars added/removed)
- **Restore**: Revert to any previous version
- **Diff**: Unified diff between any two versions
- **Tags and pinning**: Organize and prioritize
- **File attachments**: Upload files per artifact (base64 storage)
- **Comments**: Threaded discussion per artifact
- **Auto-creation**: Code blocks in AI chat auto-saved as artifacts
- **"Save as Artifact"**: Button on AI messages (hover to reveal)

### 6.2 Knowledge Base
- Workspace-scoped persistent memory
- **5 categories**: General, Insight, Decision, Reference, Context
- **Rich text editor**: Markdown toolbar (Bold, Italic, Code, List, Link, Attachment)
- **Search**: Text + semantic word-overlap scoring
- **File upload**: PDF/DOCX/TXT/MD/CSV with auto-chunking (500 words, 50 overlap)
- AI agents can read/write via tools
- Context injection into AI prompts (top 10 entries)

---

## 7. MULTIMEDIA CONTENT STUDIO

### 7.1 Image Generation
- Gemini Nano Banana model via Emergent LLM key
- User API key option
- Gallery with metrics tracking

### 7.2 Video Generation
- Sora 2 text-to-video
- 4 sizes: HD 720p, Widescreen, Portrait, Square
- 3 durations: 4/8/12 seconds
- 6 style presets: Natural, Cinematic, Animated, Documentary, Slow Motion, Timelapse
- Negative prompts
- Image-to-video endpoint
- Multi-agent storyboarding (scene generation + batch video creation)

### 7.3 Audio / Text-to-Speech
- OpenAI TTS with 9 voices: Alloy, Ash, Coral, Echo, Fable, Nova, Onyx, Sage, Shimmer
- Standard + HD quality models
- Speed control (0.5x - 2x)
- TTS preview (instant, no save)
- Streaming TTS (chunked for long text)
- Podcast generation (multi-agent segments by topic)

### 7.4 Speech-to-Text
- OpenAI Whisper transcription
- Voice input button in chat (microphone icon)
- Supports webm, mp3, wav, etc.

### 7.5 Media Library
- Unified library for all media (video, audio, image)
- Smart folders: Recent, Starred, Videos, Audio, Images
- Storage usage overview with limit bar
- Grid + List view toggle
- Drag-and-drop upload dropzone
- Bulk operations: tag, move, delete
- Share links with expiry
- Asset detail dialog with preview
- Media version history + restore
- Media scheduling (recurring generation)
- Full analytics dashboard (summary, cost, performance, timeseries)

### 7.6 Voice Notes
- Record audio memos
- Attach to tasks or artifacts
- Workspace-scoped

---

## 8. CONTENT GENERATION SUITE

### 8.1 Documents
- AI-generated documents from prompts or templates
- Chat-to-document export
- Version history
- Markdown export

### 8.2 Slides
- AI-generated slide decks from prompts
- 6 templates: Project Brief, Tech Spec, Pitch Deck, Quarterly Review, Budget Tracker, Project Plan

### 8.3 Spreadsheets
- AI-generated sheets with structured data

### 8.4 Export as Deliverables
- Chat → Document
- Chat → Report (summary + actions + transcript)
- Combine artifacts → Document

---

## 9. CODE DEVELOPMENT

### 9.1 Code Execution Sandbox
- Execute Python, JavaScript, Bash in sandboxed subprocess
- 15-second timeout
- Returns stdout, stderr, exit code, duration
- Execution history

### 9.2 GitHub Integration
- OAuth connection (user + org level)
- List repositories
- Browse file tree
- Read file content
- Create pull requests
- Create issues
- GitHub webhook for CI/CD (push/PR events trigger workflows)

### 9.3 Project-Code Linking
- Link code artifacts to tasks
- View linked code from task detail

### 9.4 Console/Terminal
- Execution history per workspace

### 9.5 VS Code Extension API
- Submit code for multi-model review
- Returns artifact URL

---

## 10. DEEP RESEARCH & FACT CHECKING

### 10.1 Deep Research Agent
- 3 depth levels: Quick (3 sub-queries), Standard (5), Deep (10)
- Sub-query decomposition
- Structured reports with citations and confidence scores
- Follow-up refinement
- Export as markdown

### 10.2 AI Fact Checking
- Claim verification with verdict
- Confidence score (0-1)
- Supporting + contradicting evidence
- History tracking

---

## 11. SCHEDULED AGENT ACTIONS

- **4 action types**: Project Review, Task Triage, Standup Summary, Custom
- **8 interval options**: 15 min to daily
- Multi-worker safe (MongoDB atomic claims)
- Manual trigger
- Execution history with status tracking
- Pause/Resume per schedule

---

## 12. WALKTHROUGH BUILDER

### 12.1 Walkthrough Management
- Create/edit/delete/publish/archive walkthroughs
- Version snapshots on publish
- Rollback to any version

### 12.2 Step Types (6)
- **Tooltip**: Anchored to element
- **Modal**: Centered overlay
- **Spotlight**: Highlight element with overlay
- **Action**: Wait for user interaction
- **Beacon**: Pulsing dot indicator
- **Checklist**: Multi-item with walkthrough links

### 12.3 Configuration
- Branching rules (condition → then/else step)
- 5 trigger types: Page Load, First Visit, Event, Manual, Scheduled
- 4 frequency rules: Once, Until Completed, Every N Days, Always
- Theme customization (colors, border radius, overlay blur)
- Target selectors (data-testid or CSS)

### 12.4 SDK Endpoints
- Active walkthroughs for current URL
- Batch event ingestion
- User progress tracking
- Resource Center (categorized progress)

### 12.5 Analytics
- Starts, completions, dismissals, completion rate
- Step-level funnel with drop-off rates

### 12.6 Validation
- Check for missing steps, broken branch references, empty selectors

### 12.7 Permissions (5 roles)
- Super Admin: Full access
- Admin: Full except delete
- Moderator: Create/edit own
- User: Consumer only
- Viewer: Consumer only

---

## 13. BILLING & PRICING

### 13.1 Pricing Plans (5 tiers)
| Plan | Price | Credits | AI Models | Storage |
|------|-------|---------|-----------|---------|
| Free | $0 | 100 | 3 | 500MB |
| Starter | $19/mo | 1,000 | 5 | 5GB |
| Pro | $49/mo | 5,000 | 9 | 10GB |
| Team | $29/user/mo | 5,000 | 9 | 10GB |
| Enterprise | Custom | 50,000 | 9 | 100GB |

### 13.2 Credits System
- 7 action costs: AI collaboration (10), image gen (25), video gen (50), workflow run (15), audio gen (5), file upload (2), export (1)
- Monthly allocation by plan
- Overage billing for paid plans
- Overage estimation (projected from daily rate)

### 13.3 Free Tier Limits
- 6 daily limits: workspaces, channels, collaborations, images, workflows, KB entries
- Real-time limit checking

### 13.4 Invoices & Statements
- Monthly invoice generation with line items
- Plan cost + overage charges
- CSV export
- Payment history with receipts

### 13.5 Organization Billing
- Separate org billing accounts
- Billing contacts
- Spending limits with alert thresholds
- Cost allocation by workspace

### 13.6 Subscription Management
- Plan upgrade/downgrade with history
- Feature gating by plan
- Billing notifications (approaching limit, overage, unpaid)

---

## 14. SUPPORT DESK

### 14.1 Ticket Management
- **8 ticket types**: Bug, Enhancement, Question, Billing, General Support, Incident, Feature Request, Access Request
- **6 statuses**: Open, In Progress, Waiting on Customer, Waiting on Support, Resolved, Closed
- **4 priorities**: Low, Medium, High, Urgent

### 14.2 Features
- Threaded replies (customer-visible + internal notes)
- File attachments on tickets
- SLA tracking: 3 policies (Standard 24h/72h, Priority 4h/24h, Enterprise 1h/8h)
- First response + resolution breach detection
- Auto-status updates on reply
- Agent dashboard with queue counts
- Per-type ticket queues
- KB article suggestions

---

## 15. EXPORT & AUDIT

### 15.1 Export
- Channel export: JSON, Markdown, CSV
- Workspace export: Full data dump
- Workflow export: Nodes, edges, run history
- Invoice export: JSON, CSV

### 15.2 Audit Trail
- 14 action types tracked
- Per-workspace audit log
- User name enrichment

---

## 16. WEBHOOKS

### 16.1 Outbound
- 15 event types (message.created, task.completed, workflow.run.completed, etc.)
- HMAC signatures
- Delivery tracking
- Auto-disable after 10 consecutive failures

### 16.2 Inbound
- Public trigger URLs for workflows
- Input mapping (dot-notation JSONPath)
- GitHub webhook adapter

---

## 17. ORGANIZATION MANAGEMENT

### 17.1 Multi-Tenancy
- Logical data isolation by org_id
- Custom login URLs
- Per-org integration key overrides (encrypted)
- Per-tenant encryption keys (optional dedicated Fernet)

### 17.2 Org-Level Rollup
- Cross-workspace Projects (with workspace attribution)
- Cross-workspace Tasks with Kanban
- Cross-workspace Workflows
- Cross-workspace Analytics
- Gantt chart at org level
- Planner at org level

### 17.3 Org Repository
- File upload with auto-indexing
- Full-text search across filename, description, tags, content
- Folder organization
- File preview (image, PDF, video, audio, text)
- Cloud storage connectors: Google Drive, OneDrive, Dropbox

### 17.4 Org Settings
- Integration key management (13 integrations)
- Encryption settings
- Cloud storage connections
- Billing contacts and spending limits

---

## 18. REPORTS & ANALYTICS

### 18.1 Workspace Reports
- Status/priority/type distributions
- Assignee workload
- Project completion rates
- Overdue tasks
- Hours logged

### 18.2 Org Reports
- Cross-workspace rollup
- Per-workspace breakdown
- Team utilization

### 18.3 Velocity Report
- Sprint velocity across completed sprints

### 18.4 Usage Analytics
- Messages by type
- Model usage with avg response times
- Daily activity trends
- Artifact and workflow counts

### 18.5 Media Analytics
- Generation stats per type/provider
- Cost breakdown
- Performance (avg generation time)
- Daily timeseries

### 18.6 Model Performance
- Per-model stats
- Task-type recommendations with scoring
- Auto-routing (classify task → select best model)

---

## 19. PLATFORM PLUGINS (8 platforms)

### 19.1 Messaging (7)
| Platform | Auth | Features |
|----------|------|----------|
| Slack | OAuth | Send/receive, channel sync, slash commands |
| Discord | Bot Token | Channel mapping, message relay |
| MS Teams | OAuth | Channel sync, adaptive cards |
| Mattermost | Webhook | Channel bridge, message relay |
| WhatsApp | API Key | Message templates, send/receive |
| Signal | API Key | Secure message relay |
| Telegram | Bot Token | Group mapping, inline commands |

### 19.2 Meetings
| Zoom | OAuth | Create meetings, join URLs, recording webhooks, transcripts |

### 19.3 Shared Features
- OAuth/token connection (user + org level)
- Channel mapping (link external ↔ Nexus channel)
- Bidirectional sync (to_nexus / from_nexus / bidirectional)
- Public webhook endpoints for incoming messages
- Message history across platforms

---

## 20. INTEGRATIONS & SETTINGS

### 20.1 AI Model Keys
- 9 AI providers with encrypted key storage
- Test/validate endpoint per provider
- "Get key" links to provider dashboards
- Encryption health check

### 20.2 Integration Settings (Admin + Org)
- 13 integration keys configurable
- Platform-level defaults
- Per-org overrides (encrypted)
- Status dashboard

### 20.3 Cloud Storage
- Google Drive, OneDrive, Dropbox connectors
- OAuth connection (user + org level)
- File browsing and import to repository

---

## 21. UI/UX FEATURES

### 21.1 Dashboard
- Sidebar navigation (Workspaces, Workflows, Analytics, Walkthroughs, Admin)
- Workspace cards with colored initials, agent dots, kebab menu
- Pinned workspaces section
- Search and sort
- Onboarding tour (4-step guided walkthrough)
- Keyboard shortcuts (Ctrl+K search, Ctrl+N new, Ctrl+/ palette)

### 21.2 Workspace Tabs (consolidated)
- **COLLABORATE**: Chat, Members
- **BUILD**: Workflows, Agents, Schedules, Media ▾ (Images/Video/Audio/Library)
- **MANAGE**: Projects, Tasks, Artifacts, Knowledge, More ▾ (Gantt/Planner/Skills/Marketplace/Reports/Analytics)

### 21.3 Settings
- Sidebar layout (Dashboard/Settings/Billing)
- Profile tab (editable name, account details)
- AI Keys tab (9 providers with test/save/delete)
- Preferences tab (language, theme, notifications, keyboard shortcuts, AI defaults)

### 21.4 Landing Page
- Clean hero with outcome-focused headline
- Primary + secondary CTAs
- Model marquee with brand colors
- Hand-crafted product mockup (4 AI agents discussing pitch deck)
- Feature cards (emerald/blue/amber icons)
- How it works (3-step)
- Pricing section ($0 beta)
- Footer with support link

### 21.5 Internationalization
- 10 languages: English, Spanish, French, German, Portuguese, Japanese, Chinese, Korean, Arabic (RTL), Hindi

---

## 22. DESKTOP APPLICATION

- Downloadable Windows .exe (64-bit + 32-bit)
- Electron-based wrapper
- Online mode (connects to deployed Nexus server)
- Offline mode (local Express server)
- Auto-detects server URL
- Download endpoint: `GET /api/download/desktop/{arch}`

---

## 23. CUSTOM AGENTS

### 23.1 Agent Personas (4 built-in)
- Senior Code Reviewer, Technical Writer, Data Analyst, Business Strategist

### 23.2 Custom Agent Builder
- Name, avatar emoji, base model
- Custom system prompt
- Enabled tools selection
- Knowledge base scope
- Trigger keywords
- Auto-respond toggle
- Handoff targets
- Response style (concise/detailed/structured)
- Public/private visibility
- Test endpoint

### 23.3 AI Team Roles (8)
- Strategist, Coder, Researcher, Critic, Writer, Designer, Analyst, QA Engineer
- Assignable per workspace per model

---

## 24. WORKSPACE TEMPLATES (4 pre-built)

- **Product Launch**: market-research, messaging-copy, gtm-strategy channels
- **Code Review Team**: code-review, refactoring, testing channels
- **Research Lab**: source-gathering, analysis, synthesis channels
- **Content Studio**: ideation, drafting, editing-review channels

One-click deploy creates workspace + pre-configured channels with agents.

---

## 25. REAL-TIME COLLABORATION

- Presence heartbeat (online users per workspace)
- Typing indicators per channel
- Notification polling (30s with visibility-based pause)

---

## 26. BUILT-IN DRIVE

- Workspace + personal file storage
- Chunked upload (4MB chunks, 100MB max)
- Folder creation and organization
- Trash and restore
- Share links with expiry and permissions
- Search across filenames
- Storage usage tracking with plan-based limits

---

## 27. SUPPORT REQUEST MODAL

- Replaces old "Report Bug" button
- 5 ticket type cards: Bug, Enhancement, Question, Billing, General Support
- Priority selector (Low/Medium/High/Urgent)
- Subject + description fields
- File attachment support
- Creates support ticket via `/support/tickets` API
