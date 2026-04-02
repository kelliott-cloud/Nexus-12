# Redis Degradation Guide

## Overview
Nexus Cloud operates in two modes regarding Redis:
- **With Redis**: Full distributed functionality
- **Without Redis** (fallback): Single-instance mode with in-memory fallbacks

The backend's `redis_client.py` automatically falls back to in-memory when Redis is unavailable, controlled by `REDIS_REQUIRED` env var.

## Feature Degradation Matrix

| Feature | With Redis | Without Redis | Impact |
|---------|-----------|---------------|--------|
| Rate Limiting | Distributed across instances | Per-process only | Each backend worker has independent limits. Total throughput = N × limit |
| WebSocket Pub/Sub | Cross-instance messaging | Local instance only | Users on different backend instances won't see each other's real-time updates |
| Collaboration State | Shared across instances | Single-instance only | Agent collaboration works within one worker but not across |
| Session Caching | Shared session cache | No cache (DB every time) | Slightly higher DB load for auth checks |
| Agent Scheduling | Distributed locks | No distributed locks | Possible duplicate schedule executions across workers |

## When to Use Redis

- **Required**: Multi-worker deployments (`WORKERS > 1`), horizontal scaling, load-balanced setups
- **Optional**: Single-worker dev/staging, small team deployments (< 10 concurrent users)
- **Not needed**: Local development, CI testing

## Configuration

```bash
# Require Redis (crash on startup if unavailable)
REDIS_REQUIRED=true
REDIS_URL=redis://your-redis-host:6379

# Optional Redis (fallback to in-memory if unavailable)
REDIS_REQUIRED=false
# REDIS_URL=redis://localhost:6379
```

## Monitoring

- Check Redis health: `GET /api/health/startup` includes Redis connectivity status
- Admin dashboard: System Health tab shows Redis connection state
- Logs: Search for `Redis startup` to see connection mode

## Migration Planning

When migrating from no-Redis to Redis:
1. Deploy Redis instance
2. Set `REDIS_URL` env var
3. Set `REDIS_REQUIRED=true`
4. Restart backend — verify via startup logs
5. No data migration needed — Redis state is ephemeral
