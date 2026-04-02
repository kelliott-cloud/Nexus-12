"""Database Migration Framework — Simple numbered migration runner.

Tracks which migrations have run in a `migrations` collection.
Run pending migrations on startup.
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def _migration_2(db):
    """Create login_attempts collection index for account lockout."""
    await db.login_attempts.create_index("email", unique=True)


async def _migration_3(db):
    """Add thread_count default to messages missing it."""
    await db.messages.update_many(
        {"thread_count": {"$exists": False}},
        {"$set": {"thread_count": 0}}
    )


async def _migration_4(db):
    """Create TTL index on mfa_challenges for auto-expiry (5 minutes)."""
    await db.mfa_challenges.create_index("created_at", expireAfterSeconds=300)


async def _migration_5(db):
    """Persist super_admin platform_role. Password handled by migration 6."""
    import os
    super_email = os.environ.get("SUPER_ADMIN_EMAIL", "")
    if super_email:
        # Only set the role — password is handled by migration 6 via env var
        await db.users.update_one({"email": super_email}, {"$set": {"platform_role": "super_admin"}})
        await db.users.update_one({"email": super_email.lower()}, {"$set": {"platform_role": "super_admin"}})


async def _migration_6(db):
    """Ensure super admin has password login capability."""
    import os
    import bcrypt
    super_email = os.environ.get("SUPER_ADMIN_EMAIL", "")
    init_pw = os.environ.get("SUPER_ADMIN_INIT_PASSWORD", "")
    if not super_email or not init_pw:
        return
    user = await db.users.find_one(
        {"$or": [{"email": super_email}, {"email": super_email.lower()}]},
        {"_id": 0, "password_hash": 1, "email": 1}
    )
    if user and not user.get("password_hash"):
        pw_hash = bcrypt.hashpw(init_pw.encode(), bcrypt.gensalt()).decode()
        await db.users.update_one(
            {"email": user["email"]},
            {"$set": {"password_hash": pw_hash, "auth_type": "both", "platform_role": "super_admin"}}
        )
        logger.info(f"Migration 6: Set password for super admin {user['email']}")


MIGRATIONS = [
    {
        "version": 1,
        "name": "initial_indexes",
        "description": "Create core database indexes",
    },
    {
        "version": 2,
        "name": "add_login_attempts_collection",
        "description": "Create login_attempts collection and index for account lockout",
        "up": _migration_2,
    },
    {
        "version": 3,
        "name": "add_thread_count_field",
        "description": "Add thread_count default to messages",
        "up": _migration_3,
    },
    {
        "version": 4,
        "name": "mfa_challenge_ttl_index",
        "description": "TTL index on mfa_challenges for auto-expiry",
        "up": _migration_4,
    },
    {
        "version": 5,
        "name": "persist_super_admin_role",
        "description": "Persist super_admin platform_role in DB",
        "up": _migration_5,
    },
    {
        "version": 6,
        "name": "ensure_super_admin_password",
        "description": "Ensure super admin has local password login",
        "up": _migration_6,
    },
    {
        "version": 7,
        "name": "drop_unique_code_repos_workspace_index",
        "description": "Drop old unique workspace_id index on code_repos to allow multi-repo per workspace",
    },
    {
        "version": 8,
        "name": "backfill_repo_id_on_files",
        "description": "Assign repo_id to all orphan repo_files and repo_commits",
    },
]


async def _migration_8(db):
    """Backfill repo_id on repo_files and repo_commits for multi-repo."""
    import uuid as _uuid
    from nexus_utils import now_iso as _now
    orphan_ws = await db.repo_files.distinct('workspace_id', {'$or': [{'repo_id': {'$exists': False}}, {'repo_id': ''}, {'repo_id': None}]})
    for ws_id in orphan_ws:
        repo = await db.code_repos.find_one({'workspace_id': ws_id}, {'_id': 0})
        if not repo:
            repo_id = f'repo_{_uuid.uuid4().hex[:12]}'
            repo = {'repo_id': repo_id, 'workspace_id': ws_id, 'name': 'Default', 'description': '', 'default_branch': 'main', 'created_at': _now(), 'updated_at': _now()}
            await db.code_repos.insert_one(repo)
        else:
            repo_id = repo['repo_id']
        r = await db.repo_files.update_many({'workspace_id': ws_id, '$or': [{'repo_id': {'$exists': False}}, {'repo_id': ''}, {'repo_id': None}]}, {'$set': {'repo_id': repo_id}})
        logger.info(f'Migration 8: ws {ws_id}: assigned {r.modified_count} files to {repo_id}')
        await db.repo_commits.update_many({'workspace_id': ws_id, '$or': [{'repo_id': {'$exists': False}}, {'repo_id': ''}, {'repo_id': None}]}, {'$set': {'repo_id': repo_id}})


async def run_migrations(db, dry_run=False):
    """Run all pending migrations. If dry_run=True, show what would run without executing."""
    pending = []
    for migration in MIGRATIONS:
        version = migration["version"]
        existing = await db.migrations.find_one({"version": version})
        if existing:
            continue
        pending.append(migration)

    if dry_run:
        if not pending:
            print("No pending migrations.")
        else:
            print(f"{len(pending)} pending migration(s):")
            for m in pending:
                print(f"  v{m['version']}: {m['name']} — {m.get('description', '')}")
        return

    for migration in pending:
        version = migration["version"]
        logger.info(f"Running migration v{version}: {migration['name']}")
        try:
            if "up" in migration and callable(migration["up"]):
                await migration["up"](db)
            elif migration["version"] == 8:
                await _migration_8(db)

            await db.migrations.insert_one({
                "version": version,
                "name": migration["name"],
                "description": migration.get("description", ""),
                "applied_at": datetime.now(timezone.utc).isoformat(),
            })
            logger.info(f"Migration v{version} complete")
        except Exception as e:
            logger.error(f"Migration v{version} failed: {e}")
            break

    applied = await db.migrations.count_documents({})
    logger.info(f"Database migrations: {applied}/{len(MIGRATIONS)} applied")


# CLI: python -m db_migrations --dry-run
if __name__ == "__main__":
    import asyncio
    import sys
    from motor.motor_asyncio import AsyncIOMotorClient
    import os

    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "nexus_cloud")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    dry = "--dry-run" in sys.argv
    if dry:
        print("=== DRY RUN — No changes will be made ===\n")

    asyncio.run(run_migrations(db, dry_run=dry))
    if not dry:
        print("\nMigrations applied.")
    client.close()
