"""Shared HTTP client pool — reuse connections across AI provider calls."""
import httpx
import logging

logger = logging.getLogger(__name__)

_client = None


def get_http_client(timeout=90.0):
    """Get the shared httpx.AsyncClient. Creates one on first call."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=timeout,
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=30,
            ),
            follow_redirects=True,
        )
    return _client


async def close_http_client():
    """Close the shared client. Call on app shutdown."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
