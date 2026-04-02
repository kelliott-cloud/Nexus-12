"""Shared encryption module — breaks circular import between key_resolver and routes_ai_keys."""
import os
import logging
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY', '')
if not ENCRYPTION_KEY:
    logger.warning("ENCRYPTION_KEY not set — generating ephemeral key")
    ENCRYPTION_KEY = Fernet.generate_key().decode()

_fernet = None

def get_fernet():
    global _fernet
    if _fernet is None:
        _fernet = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)
    return _fernet
