"""Shared utilities used across route modules."""
import nh3
import uuid
from datetime import datetime, timezone


def now_iso():
    """UTC ISO timestamp — single source for all modules."""
    return datetime.now(timezone.utc).isoformat()


def gen_id(prefix="id"):
    """Generate a unique ID with prefix: gen_id("msg") → "msg_a1b2c3d4e5f6" """
    return f"{prefix}_{uuid.uuid4().hex[:12]}"




def sanitize_html(text):
    """Strip all HTML tags from user input using nh3."""
    if not text or not isinstance(text, str):
        return text
    return nh3.clean(text, tags=set(), attributes={}, strip_comments=True)


def validate_password(password):
    """Shared password validation — used by both registration and reset."""
    if len(password) < 10:
        return "Password must be at least 10 characters"
    if not any(c.isupper() for c in password):
        return "Password must contain at least one uppercase letter"
    if not any(c.isdigit() for c in password):
        return "Password must contain at least one number"
    COMMON_PASSWORDS = {"password", "12345678", "qwerty123", "abc12345", "letmein1", "welcome1",
                        "admin123", "iloveyou", "monkey123", "dragon12", "master12", "shadow12",
                        "sunshine", "trustno1", "princess", "football", "charlie1", "passw0rd",
                        "password1", "123456789", "1234567890", "qwertyui"}
    if password.lower() in COMMON_PASSWORDS:
        return "Password is too common. Choose a stronger password."
    return None


def safe_regex(user_input, max_len=200):
    """Escape user input for safe use in MongoDB $regex queries."""
    import re
    return re.escape(str(user_input)[:max_len])


def sanitize_filename(name):
    """Sanitize filename for Content-Disposition header."""
    import re
    safe = re.sub(r'["\\\r\n\x00-\x1f]', '_', str(name))
    return safe[:255]


def normalize_email(email):
    """Normalize email to lowercase and strip whitespace."""
    return email.strip().lower() if email else ""


def validate_redirect_uri(redirect_uri, app_url=None):
    """Validate that redirect_uri belongs to our domain. Returns safe URI or raises."""
    import os
    from urllib.parse import urlparse
    from fastapi import HTTPException

    base = app_url or os.environ.get("APP_URL", "")
    if not redirect_uri:
        raise HTTPException(400, "redirect_uri is required")
    parsed_redirect = urlparse(redirect_uri)
    if parsed_redirect.netloc:
        if not base:
            raise HTTPException(500, "APP_URL not configured")
        parsed_base = urlparse(base)
        if parsed_redirect.netloc != parsed_base.netloc:
            raise HTTPException(400, "Invalid redirect_uri: must match application domain")
    return redirect_uri


async def require_workspace_access(db, user, ws_id):
    """Verify the authenticated user has access to this workspace. Raises 403 if not.
    Super admins bypass all workspace access checks."""
    from fastapi import HTTPException
    # Super admin bypass
    if user.get("platform_role") == "super_admin":
        return
    from data_guard import TenantIsolation
    has_access = await TenantIsolation.verify_workspace_access(db, user["user_id"], ws_id)
    if not has_access:
        raise HTTPException(403, "You do not have access to this workspace")


async def require_deployment_access(db, user, dep_id):
    """Resolve deployment to workspace, then verify access."""
    from fastapi import HTTPException
    dep = await db.deployments.find_one({"deployment_id": dep_id}, {"_id": 0, "workspace_id": 1})
    if not dep:
        raise HTTPException(404, "Deployment not found")
    await require_workspace_access(db, user, dep["workspace_id"])
    return dep


async def require_directive_access(db, user, directive_id):
    """Resolve directive to workspace, then verify access."""
    from fastapi import HTTPException
    directive = await db.directives.find_one({"directive_id": directive_id}, {"_id": 0, "workspace_id": 1})
    if not directive:
        raise HTTPException(404, "Directive not found")
    await require_workspace_access(db, user, directive["workspace_id"])
    return directive


async def require_channel_access(db, user, channel_id):
    """Resolve channel to workspace, then verify access."""
    from data_guard import TenantIsolation
    from fastapi import HTTPException
    has_access = await TenantIsolation.verify_channel_access(db, user["user_id"], channel_id)
    if not has_access:
        raise HTTPException(403, "Access denied")


# ============================================================
# SSRF Protection (N7-007 / FG-002)
# ============================================================
import ipaddress
from urllib.parse import urlparse

BLOCKED_HOSTS = {"169.254.169.254", "metadata.google.internal", "metadata.internal"}

def validate_external_url(url: str) -> str:
    """Validate URL is not targeting internal/private networks. Returns cleaned URL or raises ValueError."""
    parsed = urlparse(url)
    if not parsed.scheme or parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme: {parsed.scheme}")
    if not parsed.hostname:
        raise ValueError("URL has no hostname")
    hostname = parsed.hostname.lower()
    if hostname in BLOCKED_HOSTS:
        raise ValueError(f"Blocked host: {hostname}")
    if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
        raise ValueError("Cannot access localhost")
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError(f"Blocked private/reserved IP: {ip}")
    except ValueError as ve:
        if "Blocked" in str(ve):
            raise
        # DNS rebinding protection (NX8-017): resolve hostname and check resolved IPs
        import socket
        try:
            resolved = socket.getaddrinfo(hostname, None)
            for family, _, _, _, sockaddr in resolved:
                resolved_ip = ipaddress.ip_address(sockaddr[0])
                if resolved_ip.is_private or resolved_ip.is_loopback or resolved_ip.is_link_local:
                    raise ValueError(f"DNS resolved to private IP: {resolved_ip}")
        except socket.gaierror:
            pass  # DNS resolution failure — will fail at request time
    return url


# ============================================================
# File Upload Validation (FG-005)
# ============================================================
ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".xml", ".yaml", ".yml",
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".scss",
    ".java", ".go", ".rs", ".c", ".cpp", ".h", ".rb", ".php", ".sh",
    ".sql", ".graphql", ".proto", ".toml", ".ini", ".cfg", ".env",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
    ".mp3", ".wav", ".mp4", ".webm", ".ogg",
    ".zip", ".tar", ".gz", ".7z",
}

MIME_MAGIC = {
    b"\x89PNG": ".png",
    b"\xff\xd8\xff": ".jpg",
    b"GIF87a": ".gif",
    b"GIF89a": ".gif",
    b"PK\x03\x04": ".zip",
    b"%PDF": ".pdf",
}

MAX_FILE_SIZES = {
    "default": 50 * 1024 * 1024,       # 50MB
    "image": 10 * 1024 * 1024,          # 10MB
    "document": 25 * 1024 * 1024,       # 25MB
    "archive": 100 * 1024 * 1024,       # 100MB
    "code": 5 * 1024 * 1024,            # 5MB
}

def validate_file_upload(filename: str, content: bytes, max_size: int = None) -> str:
    """Validate file upload. Returns error string or empty string if valid."""
    import os
    ext = os.path.splitext(filename)[1].lower()
    if ext and ext not in ALLOWED_EXTENSIONS:
        return f"File type '{ext}' not allowed"
    
    size = len(content)
    limit = max_size or MAX_FILE_SIZES["default"]
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"):
        limit = max_size or MAX_FILE_SIZES["image"]
    elif ext in (".zip", ".tar", ".gz", ".7z"):
        limit = max_size or MAX_FILE_SIZES["archive"]
    elif ext in (".py", ".js", ".ts", ".go", ".rs", ".java"):
        limit = max_size or MAX_FILE_SIZES["code"]
    
    if size > limit:
        return f"File too large ({size // 1024 // 1024}MB). Max: {limit // 1024 // 1024}MB"
    
    # Magic byte check for binary files
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".zip", ".pdf"):
        matched = False
        for magic, magic_ext in MIME_MAGIC.items():
            if content[:len(magic)] == magic:
                if magic_ext != ext and not (magic_ext == ".jpg" and ext == ".jpeg"):
                    return f"File content doesn't match extension '{ext}'"
                matched = True
                break
        if not matched and ext in (".png", ".jpg", ".jpeg", ".gif"):
            return f"Invalid {ext} file (magic bytes don't match)"
    
    # Archive bomb check (zip files)
    if ext == ".zip" and size > 1024:
        import zipfile, io
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                total_uncompressed = sum(f.file_size for f in zf.infolist())
                if total_uncompressed > 500 * 1024 * 1024:  # 500MB uncompressed limit
                    return f"Archive too large when extracted ({total_uncompressed // 1024 // 1024}MB)"
                if len(zf.infolist()) > 10000:
                    return f"Archive contains too many files ({len(zf.infolist())})"
        except zipfile.BadZipFile:
            return "Invalid zip file"
    
    return ""
