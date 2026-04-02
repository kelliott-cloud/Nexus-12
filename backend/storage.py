"""Storage Abstraction — File storage with local disk or S3-compatible backends.

Configure via STORAGE_BACKEND env var:
- 'local' (default): /app/uploads/{workspace_id}/{filename}
- 's3': S3/R2/MinIO via boto3
"""
import os
import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "local")
STORAGE_BUCKET = os.environ.get("STORAGE_BUCKET", "")
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/app/uploads"))

# Auto-fallback: if S3 configured but credentials missing, fall back to local
if STORAGE_BACKEND == "s3" and not (os.environ.get("S3_ACCESS_KEY_ID") and os.environ.get("S3_ENDPOINT_URL")):
    logger.warning("STORAGE_BACKEND=s3 but S3 credentials not set. Falling back to local storage.")
    STORAGE_BACKEND = "local"

# Production validation
if os.environ.get("ENVIRONMENT") == "production" and STORAGE_BACKEND == "local":
    logger.warning("STORAGE_BACKEND=local in production. File uploads will use ephemeral container storage. "
                    "Set S3_ENDPOINT_URL, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, STORAGE_BUCKET for persistent storage.")

_s3_client = None


def _get_s3():
    global _s3_client
    if _s3_client is None:
        import boto3
        kwargs = {}
        endpoint = os.environ.get("S3_ENDPOINT_URL")
        if endpoint:
            kwargs["endpoint_url"] = endpoint
        key_id = os.environ.get("S3_ACCESS_KEY_ID")
        secret = os.environ.get("S3_SECRET_ACCESS_KEY")
        if key_id and secret:
            kwargs["aws_access_key_id"] = key_id
            kwargs["aws_secret_access_key"] = secret
        _s3_client = boto3.client("s3", **kwargs)
    return _s3_client


async def save_file(workspace_id: str, filename: str, data: bytes) -> str:
    """Save file. Returns the storage key."""
    key = f"{workspace_id}/{filename}"
    if STORAGE_BACKEND == "s3" and STORAGE_BUCKET:
        await asyncio.to_thread(_get_s3().put_object, Bucket=STORAGE_BUCKET, Key=key, Body=data)
    else:
        path = UPLOAD_DIR / workspace_id
        path.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread((path / filename).write_bytes, data)
    return key


async def get_file(workspace_id: str, filename: str) -> bytes:
    """Retrieve file content. Returns bytes or None."""
    if STORAGE_BACKEND == "s3" and STORAGE_BUCKET:
        try:
            obj = await asyncio.to_thread(_get_s3().get_object, Bucket=STORAGE_BUCKET, Key=f"{workspace_id}/{filename}")
            return await asyncio.to_thread(obj["Body"].read)
        except Exception:
            return None
    path = UPLOAD_DIR / workspace_id / filename
    if path.exists():
        return await asyncio.to_thread(path.read_bytes)
    return None


async def get_file_url(workspace_id: str, filename: str, expires: int = 900) -> str:
    """Get a download URL. Local returns API path, S3 returns presigned URL."""
    if STORAGE_BACKEND == "s3" and STORAGE_BUCKET:
        return await asyncio.to_thread(
            _get_s3().generate_presigned_url,
            "get_object",
            Params={"Bucket": STORAGE_BUCKET, "Key": f"{workspace_id}/{filename}"},
            ExpiresIn=expires,
        )
    return f"/api/files/download/{filename}"


async def delete_file(workspace_id: str, filename: str) -> bool:
    """Delete file from storage."""
    if STORAGE_BACKEND == "s3" and STORAGE_BUCKET:
        try:
            await asyncio.to_thread(_get_s3().delete_object, Bucket=STORAGE_BUCKET, Key=f"{workspace_id}/{filename}")
            return True
        except Exception:
            return False
    path = UPLOAD_DIR / workspace_id / filename
    if path.exists():
        await asyncio.to_thread(path.unlink)
        return True
    return False
