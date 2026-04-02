# Nexus Cloud Platform — Deployment Guide

## Prerequisites
- MongoDB Atlas cluster (or any MongoDB 5.0+)
- At least 1 AI provider API key (OpenAI, Anthropic, or Google)
- Node.js 18+ (for frontend build)
- Python 3.11+ (for backend)

## Quick Deploy (Docker Compose)
1. Copy env files: `cp backend/.env.example backend/.env && cp frontend/.env.example frontend/.env`
2. Fill in required values in both `.env` files
3. Run: `docker compose up --build -d`
4. First login creates the super admin from `SUPER_ADMIN_EMAIL`

## Environment Variables
Copy `backend/.env.example` to `backend/.env` and fill in your values.

### Required:
- `MONGO_URL` — MongoDB connection string
- `DB_NAME` — Database name
- `SUPER_ADMIN_EMAIL` — Super admin email
- `ENCRYPTION_KEY` — Fernet key for API key encryption (generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
- `CORS_ORIGINS` — Allowed origins
- `APP_URL` — Public URL

### Recommended:
- `STORAGE_BACKEND=s3` — Use S3/R2 for file storage (local storage is ephemeral in containers)
- `REDIS_URL` — Redis for rate limiting and session state
- At least one AI API key

## Architecture
- **Backend**: FastAPI (Python 3.11) on port 8080
- **Frontend**: React (Vite) on port 3000
- **Database**: MongoDB Atlas
- **Storage**: S3-compatible (Cloudflare R2, AWS S3, MinIO)
- **Cache**: Redis (optional, in-memory fallback)

## Post-Deploy Checklist
1. Login with super admin credentials
2. Configure AI provider keys in Settings → AI Keys
3. Create first workspace
4. Verify Google OAuth (if configured)
5. Test AI collaboration in a chat channel
