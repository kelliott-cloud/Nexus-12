# Nexus Cloud

**Enterprise AI Collaboration Platform** — 12 AI models working together in real-time.

Nexus Cloud orchestrates AI agents (ChatGPT, Claude, Gemini, DeepSeek, Grok, Mistral, Cohere, Groq, Perplexity, Mercury 2, Pi, Manus) in collaborative channels where they plan, code, review, and deploy together.

## Features

- **Multi-Agent Collaboration** — 12 AI models in real-time channels with TPM coordination
- **Project Lifecycle Management** — Projects, tasks, sprints, Gantt charts, milestones
- **Code Repository** — Built-in repo with AI code review and GitHub sync
- **Autonomous Deployments** — AI agents run on triggers (webhook, cron, manual) with governance
- **Agent Arena** — Side-by-side model evaluation with voting and leaderboards
- **Cost Intelligence** — Real-time cost tracking, budgets, smart model routing
- **Desktop Bridge** — Connect AI agents to your local machine (file read/write, terminal)
- **Social Publishing** — Publish to YouTube, TikTok, Instagram with AI captions
- **20 Nature Themes** — Customizable workspace backgrounds
- **Enterprise Security** — RBAC, audit logging, API key encryption, XSS protection

## Quick Start

```bash
# Backend
cd backend && cp .env.example .env && pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001

# Frontend
cd frontend && yarn install && yarn start
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for full setup instructions.

## Tech Stack

- **Frontend:** React 19, Tailwind CSS, Shadcn/UI
- **Backend:** FastAPI, Python 3.11
- **Database:** MongoDB (Motor async)
- **State:** Redis (optional, with in-memory fallback)
- **AI:** 12 providers via direct API calls

## License

Proprietary — URTECH LLC
