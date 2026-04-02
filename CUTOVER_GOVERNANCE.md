# Nexus Cloud — Cutover Governance Plan

## Overview
This document defines the procedures for migrating Nexus Cloud to a new environment (production deploy, cloud migration, domain change). It covers backup/restore, migration dry-run, rollback, and soak window protocols.

---

## 1. Pre-Cutover Checklist

### Environment Validation
- [ ] All `.env` files configured (see `backend/.env.example`, `frontend/.env.example`)
- [ ] `python -m db_migrations --dry-run` shows no unexpected migrations
- [ ] `docker compose build` completes without errors
- [ ] Frontend `yarn build` succeeds
- [ ] Backend `python -m compileall -q .` succeeds
- [ ] Smoke test passes: `python smoke_test.py $TARGET_URL`

### Credentials Verified
- [ ] `MONGO_URL` points to production MongoDB
- [ ] `ENCRYPTION_KEY` is backed up securely (loss = all encrypted API keys unrecoverable)
- [ ] `SUPER_ADMIN_EMAIL` and `SUPER_ADMIN_INIT_PASSWORD` set
- [ ] DNS/domain configured and TLS certificates provisioned
- [ ] CORS_ORIGINS / CORS_ALLOWED_DOMAINS updated for new domain

---

## 2. Backup Procedures

### MongoDB Backup
```bash
# Full database dump
mongodump --uri="$MONGO_URL" --db="$DB_NAME" --out="/backups/$(date +%Y%m%d_%H%M%S)"

# Verify backup integrity
mongorestore --uri="$MONGO_URL" --db="nexus_backup_verify" --drop "/backups/LATEST/nexus_cloud/" --dryRun
```

### Critical Collections to Backup
| Collection | Priority | Contains |
|------------|----------|----------|
| `users` | P0 | All user accounts, roles, encrypted API keys |
| `user_sessions` | P1 | Active sessions (can be regenerated) |
| `workspaces` | P0 | All workspace configs, members |
| `channels` | P0 | Chat channels and agent assignments |
| `messages` | P0 | All conversation history |
| `code_repos` / `repo_files` | P0 | Code repository content |
| `platform_settings` | P0 | Platform managed keys, OAuth config |
| `migrations` | P1 | Migration tracking (auto-recreated) |
| `organizations` / `org_memberships` | P0 | Org structure |
| `scope_integration_budgets` | P1 | Budget configurations |

### Encryption Key Backup
```bash
# The ENCRYPTION_KEY in .env encrypts all stored API keys.
# LOSING THIS KEY = ALL ENCRYPTED KEYS UNRECOVERABLE.
# Store separately from database backup.
echo "$ENCRYPTION_KEY" > /secure-vault/encryption_key_$(date +%Y%m%d).txt
```

### File Uploads Backup
```bash
# If using local storage
tar -czf /backups/uploads_$(date +%Y%m%d).tar.gz /app/uploads/

# If using S3 — already durable, but snapshot for point-in-time
aws s3 sync s3://$S3_BUCKET /backups/s3_snapshot_$(date +%Y%m%d)/
```

---

## 3. Migration Dry-Run

### Step 1: Deploy to staging
```bash
# Clone production data to staging
mongodump --uri="$PROD_MONGO_URL" --db="nexus_cloud" --out="/tmp/staging_seed"
mongorestore --uri="$STAGING_MONGO_URL" --db="nexus_staging" --drop "/tmp/staging_seed/nexus_cloud/"

# Deploy to staging
docker compose -f docker-compose.staging.yml up --build -d
```

### Step 2: Run migration preview
```bash
MONGO_URL="$STAGING_MONGO_URL" DB_NAME="nexus_staging" python -m db_migrations --dry-run
```

### Step 3: Validate staging
```bash
# Run full smoke test against staging
python smoke_test.py https://staging.nexus.cloud

# Manual validation:
# - Login with admin account
# - Open a workspace, send a message in a channel
# - Verify AI agents respond
# - Check Settings > AI Keys loads
# - Check Admin dashboard loads
```

---

## 4. Cutover Execution

### Maintenance Window (Recommended: 30 minutes)

```
T-10m  Announce maintenance to users (banner or email)
T-5m   Set MAINTENANCE_MODE=true (if supported) or scale down frontend
T-0    Begin cutover:
       1. Final MongoDB backup: mongodump --uri="$PROD_MONGO_URL" --db="nexus_cloud"
       2. Update DNS / load balancer to point to new environment
       3. Deploy new containers: docker compose up --build -d
       4. Wait for health checks: curl http://new-host:8080/api/health
       5. Run smoke test: python smoke_test.py https://new-domain.com
T+5m   Verify login, workspace, and chat functionality manually
T+10m  Remove maintenance banner
T+15m  Monitor logs for errors: docker compose logs -f backend | grep ERROR
```

---

## 5. Rollback Plan

### Trigger Criteria
Rollback if ANY of these occur within the soak window:
- Login fails for >1 user
- AI agents fail to respond in channels
- 5xx error rate >5% in backend logs
- Database migration fails midway
- Data loss detected

### Rollback Procedure (< 5 minutes)
```bash
# 1. Revert DNS / load balancer to old environment
# 2. If old environment still running, simply redirect traffic back

# If old environment was shut down:
# 3. Restore MongoDB from pre-cutover backup
mongorestore --uri="$MONGO_URL" --db="nexus_cloud" --drop "/backups/LATEST/nexus_cloud/"

# 4. Restart old containers
docker compose -f docker-compose.old.yml up -d

# 5. Verify old environment
python smoke_test.py https://old-host.com
```

### Partial Rollback (Backend only)
```bash
# If only backend has issues, roll back backend image
docker compose up -d --no-deps --build backend
```

---

## 6. Soak Window

### Duration: 24 hours after cutover

### Monitoring Checklist
| Check | Frequency | Tool |
|-------|-----------|------|
| Error rate in logs | Every 30m for first 2h, then hourly | `docker compose logs backend \| grep ERROR \| tail -20` |
| Login success rate | Every 1h | Admin dashboard or manual test |
| AI agent response rate | Every 1h | Send test message in a channel |
| Database health | Every 2h | `GET /api/admin/system-health` |
| Memory/CPU usage | Every 1h | Docker stats or monitoring tool |
| WebSocket connections | Every 2h | Check active connections in admin |

### Graduation Criteria
The cutover is considered successful when ALL of:
- [ ] 24 hours have passed since cutover
- [ ] Zero P0/P1 incidents during soak window
- [ ] Login success rate >99%
- [ ] AI response rate matches pre-cutover baseline
- [ ] No data integrity issues found
- [ ] Old environment backup verified and archived

### Post-Soak Cleanup
```bash
# Archive final backup
tar -czf /archives/pre_cutover_$(date +%Y%m%d).tar.gz /backups/LATEST/

# Remove old environment (after 7-day cooling period)
# docker compose -f docker-compose.old.yml down -v

# Update documentation
# - DEPLOYMENT.md with new domain/environment details
# - Update DNS records documentation
# - Notify team of successful migration
```

---

## 7. Emergency Contacts

| Role | Responsibility | Escalation |
|------|---------------|------------|
| Platform Admin | First responder, runs rollback | Immediate |
| Database Admin | MongoDB restore, data integrity | Within 15m |
| DevOps | DNS, load balancer, infrastructure | Within 15m |
| Product Owner | Go/no-go decision on rollback | Within 30m |

---

## Appendix: Quick Reference Commands

```bash
# Backup
mongodump --uri="$MONGO_URL" --db="$DB_NAME" --out="/backups/$(date +%Y%m%d_%H%M%S)"

# Restore
mongorestore --uri="$MONGO_URL" --db="$DB_NAME" --drop "/backups/TIMESTAMP/nexus_cloud/"

# Migration preview
MONGO_URL="..." DB_NAME="..." python -m db_migrations --dry-run

# Smoke test
python smoke_test.py https://your-domain.com

# Health check
curl -f http://localhost:8080/api/health

# Log monitoring
docker compose logs -f backend 2>&1 | grep -E 'ERROR|FATAL|Exception'
```
