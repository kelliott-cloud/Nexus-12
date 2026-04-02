# Nexus Cloud — Product Requirements Document

## Current State — 2026-04-02

### Final Component Size Summary
| Component | Original | Current | Reduction |
|-----------|----------|---------|-----------|
| ChatPanel.js | 1,395 | 1,153 | -17% |
| AgentStudio.js | 797 | 339 | -57% |
| CodeRepoPanel.js | 1,210 | 699 | -42% |
| DeploymentPanel.js | 479 | 315 | -34% |
| server.py | 1,860 | 1,373 | -26% |

### Extracted Sub-Components
```
components/
├── chat/
│   ├── ChatHeader.js (wired)
│   └── ChatThreadPanel.js (wired)
├── repo/
│   ├── RepoEditor.js (wired) — 113 lines
│   ├── RepoToolbar.js (wired) — 124 lines
│   └── RepoDialogs.js (wired) — 251 lines
├── studio/
│   └── AgentWizard.js (wired)
├── DeploymentDetail.js (wired)
backend/
└── route_registry.py (wired)
```

### CI Test Suite: 49 tests, 100% pass rate

## Backlog
### P0 — Blocked: Generative Media (API keys)
