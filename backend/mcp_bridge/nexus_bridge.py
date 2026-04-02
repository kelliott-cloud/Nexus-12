#!/usr/bin/env python3
"""Nexus Cloud Desktop Bridge Agent v2 — Connects your local machine to Nexus AI agents.

Usage:
    python nexus_bridge.py --server https://your-nexus.com --token YOUR_BRIDGE_TOKEN --user YOUR_USER_ID

Options:
    --allowed-paths ~/projects,~/Documents    Restrict file access to these directories
    --blocked-paths ~/.ssh,~/.aws,/etc        Block access to these directories
    --no-commands                              Disable command execution entirely
    --no-writes                                Disable all write operations
    --auto-approve-reads                       Auto-approve read-only operations
    --rate-limit 30                            Max tool invocations per minute (default: 30)
    --idle-timeout 3600                        Disconnect after N seconds idle (default: 1 hour)
    --allowed-ips 192.168.1.0/24              Only accept from these IPs (server-side)
"""
import os
import sys
import json
import asyncio
import platform
import subprocess
import glob
import argparse
import signal
import time
import hashlib
import re
from pathlib import Path
from datetime import datetime
from collections import deque

try:
    import websockets
except ImportError:
    print("Installing websockets...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
    import websockets


# ============ Security Configuration ============

class SecurityConfig:
    def __init__(self, args):
        self.allowed_paths = self._expand_paths(args.allowed_paths) if args.allowed_paths else []
        self.blocked_paths = self._expand_paths(args.blocked_paths or "~/.ssh,~/.aws,~/.gnupg,/etc/shadow,/etc/passwd")
        self.allow_commands = not args.no_commands
        self.allow_writes = not args.no_writes
        self.auto_approve_reads = args.auto_approve_reads
        self.rate_limit = args.rate_limit
        self.idle_timeout = args.idle_timeout
        self.invocation_times = deque()
        self.last_activity = time.time()

        # Dangerous command patterns
        self.blocked_commands = [
            r"rm\s+-rf\s+/", r"mkfs\.", r"dd\s+if=", r"format\s+[a-z]:", r"shutdown", r"reboot",
            r":(){ :\|:& };:", r"chmod\s+-R\s+777\s+/", r"chown\s+-R.*\s+/",
            r">\s*/dev/sd", r"curl.*\|\s*bash", r"wget.*\|\s*sh", r"eval\s*\(",
            r"python.*-c.*import\s+os.*system", r"nc\s+-e", r"ncat.*-e",
        ]

    def _expand_paths(self, paths_str):
        if not paths_str:
            return []
        return [os.path.expanduser(p.strip()) for p in paths_str.split(",") if p.strip()]

    def check_path_allowed(self, path):
        abs_path = os.path.abspath(os.path.expanduser(path))
        for blocked in self.blocked_paths:
            blocked_abs = os.path.abspath(blocked)
            if abs_path.startswith(blocked_abs):
                return False, f"Path blocked by security policy: {blocked}"
        if self.allowed_paths:
            for allowed in self.allowed_paths:
                allowed_abs = os.path.abspath(allowed)
                if abs_path.startswith(allowed_abs):
                    return True, ""
            return False, f"Path not in allowed list. Allowed: {', '.join(self.allowed_paths)}"
        return True, ""

    def check_command_safe(self, command):
        if not self.allow_commands:
            return False, "Command execution is disabled"
        for pattern in self.blocked_commands:
            if re.search(pattern, command, re.IGNORECASE):
                return False, f"Command blocked by security policy"
        return True, ""

    def check_rate_limit(self):
        now = time.time()
        while self.invocation_times and self.invocation_times[0] < now - 60:
            self.invocation_times.popleft()
        if len(self.invocation_times) >= self.rate_limit:
            return False, f"Rate limit exceeded ({self.rate_limit}/min)"
        self.invocation_times.append(now)
        return True, ""

    def check_idle_timeout(self):
        if time.time() - self.last_activity > self.idle_timeout:
            return False, "Idle timeout exceeded"
        return True, ""

    def touch_activity(self):
        self.last_activity = time.time()


# ============ Tool Implementations ============

def read_file(params, security):
    path = params.get("path", "")
    if not path:
        return {"error": "No path provided"}
    ok, reason = security.check_path_allowed(path)
    if not ok:
        return {"error": reason}
    if not os.path.exists(path):
        return {"error": f"File not found: {path}"}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        if len(content) > 100000:
            content = content[:100000] + f"\n... [truncated, file is {len(content)} chars]"
        return {"path": path, "content": content, "size": os.path.getsize(path)}
    except Exception as e:
        return {"error": str(e)}


def write_file(params, security):
    if not security.allow_writes:
        return {"error": "Write operations are disabled"}
    path = params.get("path", "")
    content = params.get("content", "")
    ok, reason = security.check_path_allowed(path)
    if not ok:
        return {"error": reason}
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"path": path, "written": len(content), "success": True}
    except Exception as e:
        return {"error": str(e)}


def list_dir(params, security):
    path = params.get("path", ".")
    ok, reason = security.check_path_allowed(path)
    if not ok:
        return {"error": reason}
    try:
        entries = []
        for entry in sorted(os.listdir(path)):
            full = os.path.join(path, entry)
            entries.append({
                "name": entry,
                "is_dir": os.path.isdir(full),
                "size": os.path.getsize(full) if os.path.isfile(full) else 0,
            })
        return {"path": path, "entries": entries[:200], "total": len(entries)}
    except Exception as e:
        return {"error": str(e)}


def run_command(params, security):
    command = params.get("command", "")
    cwd = params.get("cwd", None)
    ok, reason = security.check_command_safe(command)
    if not ok:
        return {"error": reason}
    try:
        import shlex
        try:
            cmd_list = shlex.split(command)
        except ValueError as e:
            return {"error": f"Invalid command syntax: {e}"}
        result = subprocess.run(cmd_list, shell=False, capture_output=True, text=True, timeout=30, cwd=cwd)
        return {"stdout": result.stdout[:50000], "stderr": result.stderr[:10000], "exit_code": result.returncode}
    except subprocess.TimeoutExpired:
        return {"error": "Command timed out (30s limit)"}
    except Exception as e:
        return {"error": str(e)}


def search_files(params, security):
    pattern = params.get("pattern", "*")
    directory = params.get("directory", ".")
    ok, reason = security.check_path_allowed(directory)
    if not ok:
        return {"error": reason}
    try:
        matches = glob.glob(os.path.join(directory, "**", pattern), recursive=True)
        # Filter by security
        safe = [m for m in matches if security.check_path_allowed(m)[0]]
        return {"matches": safe[:100], "total": len(safe), "pattern": pattern}
    except Exception as e:
        return {"error": str(e)}


def get_system_info(params, security):
    import shutil
    total, used, free = shutil.disk_usage("/")
    try:
        import psutil
        mem = psutil.virtual_memory()
        mem_total = round(mem.total / (1024**3), 1)
        mem_used = round(mem.used / (1024**3), 1)
        cpu_percent = psutil.cpu_percent(interval=0.5)
    except ImportError:
        mem_total = mem_used = cpu_percent = "N/A (install psutil)"
    return {
        "os": platform.system(), "os_version": platform.version(),
        "machine": platform.machine(), "hostname": platform.node(),
        "python": platform.python_version(), "cpu_count": os.cpu_count(),
        "cpu_percent": cpu_percent, "memory_total_gb": mem_total, "memory_used_gb": mem_used,
        "disk_total_gb": round(total / (1024**3), 1), "disk_free_gb": round(free / (1024**3), 1),
        "home_dir": str(Path.home()), "cwd": os.getcwd(),
    }


def open_url(params, security):
    import webbrowser
    url = params.get("url", "")
    if not url.startswith(("http://", "https://")):
        return {"error": "URL must start with http:// or https://"}
    try:
        webbrowser.open(url)
        return {"opened": url, "success": True}
    except Exception as e:
        return {"error": str(e)}


def take_screenshot(params, security):
    try:
        import mss
        import base64
        from io import BytesIO
        with mss.mss() as sct:
            img = sct.grab(sct.monitors[1])
            from PIL import Image
            pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
            buffer = BytesIO()
            pil_img.save(buffer, format="JPEG", quality=60)
            b64 = base64.b64encode(buffer.getvalue()).decode()
            return {"screenshot_base64": b64[:200000], "width": img.size[0], "height": img.size[1]}
    except ImportError:
        return {"error": "Screenshot requires 'mss' and 'Pillow'. Install: pip install mss Pillow"}
    except Exception as e:
        return {"error": str(e)}


# ============ NEW: Clipboard ============

def clipboard_read(params, security):
    try:
        import subprocess as sp
        if platform.system() == "Darwin":
            result = sp.run(["pbpaste"], capture_output=True, text=True, timeout=5)
        elif platform.system() == "Linux":
            result = sp.run(["xclip", "-selection", "clipboard", "-o"], capture_output=True, text=True, timeout=5)
        else:
            result = sp.run(["powershell", "-command", "Get-Clipboard"], capture_output=True, text=True, timeout=5)
        return {"content": result.stdout[:10000]}
    except Exception as e:
        return {"error": f"Clipboard read failed: {e}"}


def clipboard_write(params, security):
    if not security.allow_writes:
        return {"error": "Write operations are disabled"}
    content = params.get("content", "")
    try:
        import subprocess as sp
        if platform.system() == "Darwin":
            sp.run(["pbcopy"], input=content, text=True, timeout=5)
        elif platform.system() == "Linux":
            sp.run(["xclip", "-selection", "clipboard"], input=content, text=True, timeout=5)
        else:
            sp.run(["powershell", "-command", f"Set-Clipboard -Value '{content[:5000]}'"], timeout=5)
        return {"written": len(content), "success": True}
    except Exception as e:
        return {"error": f"Clipboard write failed: {e}"}


# ============ NEW: Process Management ============

def list_processes(params, security):
    try:
        import psutil
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
            try:
                info = p.info
                procs.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        procs.sort(key=lambda x: x.get("cpu_percent", 0) or 0, reverse=True)
        return {"processes": procs[:50], "total": len(procs)}
    except ImportError:
        # Fallback without psutil
        if platform.system() != "Windows":
            result = subprocess.run(["ps", "aux", "--sort=-pcpu"], capture_output=True, text=True, timeout=10)
            lines = result.stdout.strip().split("\n")[:51]
            return {"raw": "\n".join(lines), "total": len(lines) - 1}
        return {"error": "Process listing requires 'psutil'. Install: pip install psutil"}


def kill_process(params, security):
    pid = params.get("pid")
    if not pid:
        return {"error": "pid required"}
    try:
        import psutil
        p = psutil.Process(int(pid))
        name = p.name()
        p.terminate()
        return {"killed": int(pid), "name": name, "success": True}
    except ImportError:
        os.kill(int(pid), signal.SIGTERM)
        return {"killed": int(pid), "success": True}
    except Exception as e:
        return {"error": str(e)}


# ============ NEW: Network Diagnostics ============

def network_ping(params, security):
    host = params.get("host", "")
    if not host:
        return {"error": "host required"}
    count = min(params.get("count", 4), 10)
    try:
        flag = "-c" if platform.system() != "Windows" else "-n"
        result = subprocess.run(["ping", flag, str(count), host], capture_output=True, text=True, timeout=30)
        return {"host": host, "output": result.stdout[:5000], "success": result.returncode == 0}
    except Exception as e:
        return {"error": str(e)}


def network_dns(params, security):
    host = params.get("host", "")
    if not host:
        return {"error": "host required"}
    try:
        import socket
        ips = socket.getaddrinfo(host, None)
        unique = list(set(ip[4][0] for ip in ips))
        return {"host": host, "addresses": unique}
    except Exception as e:
        return {"error": str(e)}


def network_ports(params, security):
    host = params.get("host", "localhost")
    ports = params.get("ports", [80, 443, 8080, 3000, 5432, 27017, 6379])
    if isinstance(ports, str):
        ports = [int(p.strip()) for p in ports.split(",")]
    import socket
    results = {}
    for port in ports[:20]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, int(port)))
            results[str(port)] = "open" if result == 0 else "closed"
            sock.close()
        except Exception:
            results[str(port)] = "error"
    return {"host": host, "ports": results}


# ============ NEW: Docker Control ============

def docker_list(params, security):
    try:
        result = subprocess.run(["docker", "ps", "-a", "--format", "{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Ports}}"],
                                capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return {"error": result.stderr[:500] or "Docker not available"}
        containers = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            containers.append({"id": parts[0], "name": parts[1] if len(parts) > 1 else "",
                               "status": parts[2] if len(parts) > 2 else "", "image": parts[3] if len(parts) > 3 else "",
                               "ports": parts[4] if len(parts) > 4 else ""})
        return {"containers": containers}
    except FileNotFoundError:
        return {"error": "Docker not installed"}
    except Exception as e:
        return {"error": str(e)}


def docker_control(params, security):
    action = params.get("action", "")
    container = params.get("container", "")
    if action not in ("start", "stop", "restart", "logs"):
        return {"error": "action must be start, stop, restart, or logs"}
    if not container:
        return {"error": "container name or ID required"}
    try:
        if action == "logs":
            result = subprocess.run(["docker", "logs", "--tail", "50", container], capture_output=True, text=True, timeout=10)
            return {"logs": result.stdout[:20000] + result.stderr[:5000]}
        else:
            result = subprocess.run(["docker", action, container], capture_output=True, text=True, timeout=30)
            return {"action": action, "container": container, "success": result.returncode == 0, "output": result.stdout[:2000]}
    except Exception as e:
        return {"error": str(e)}


# ============ NEW: Git Operations ============

def git_status(params, security):
    repo_path = params.get("path", ".")
    ok, reason = security.check_path_allowed(repo_path)
    if not ok:
        return {"error": reason}
    try:
        result = subprocess.run(["git", "status", "--porcelain", "-b"], capture_output=True, text=True, cwd=repo_path, timeout=10)
        diff_stat = subprocess.run(["git", "diff", "--stat"], capture_output=True, text=True, cwd=repo_path, timeout=10)
        log = subprocess.run(["git", "log", "--oneline", "-5"], capture_output=True, text=True, cwd=repo_path, timeout=10)
        return {"status": result.stdout[:5000], "diff_stat": diff_stat.stdout[:5000], "recent_commits": log.stdout[:2000], "branch": result.stdout.split("\n")[0].replace("## ", "") if result.stdout else "unknown"}
    except Exception as e:
        return {"error": str(e)}


def git_diff(params, security):
    repo_path = params.get("path", ".")
    file_path = params.get("file", "")
    ok, reason = security.check_path_allowed(repo_path)
    if not ok:
        return {"error": reason}
    try:
        cmd = ["git", "diff"]
        if file_path:
            cmd.append(file_path)
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_path, timeout=10)
        return {"diff": result.stdout[:50000]}
    except Exception as e:
        return {"error": str(e)}


# ============ NEW: Environment Variables ============

def read_env_vars(params, security):
    filter_prefix = params.get("prefix", "")
    sensitive_patterns = ["KEY", "SECRET", "PASSWORD", "TOKEN", "CREDENTIAL", "AUTH"]
    env_vars = {}
    for key, value in os.environ.items():
        if filter_prefix and not key.startswith(filter_prefix):
            continue
        is_sensitive = any(pat in key.upper() for pat in sensitive_patterns)
        env_vars[key] = f"{value[:4]}{'*' * min(len(value) - 4, 20)}" if is_sensitive and len(value) > 4 else value
    return {"variables": env_vars, "count": len(env_vars)}


# ============ Tool Registry ============

TOOLS = {
    # Original tools
    "desktop_read_file": {"fn": read_file, "requires_approval": False, "category": "read", "description": "Read a file from the local machine"},
    "desktop_write_file": {"fn": write_file, "requires_approval": True, "category": "write", "description": "Write/create a file (approval required)"},
    "desktop_list_dir": {"fn": list_dir, "requires_approval": False, "category": "read", "description": "List directory contents"},
    "desktop_run_command": {"fn": run_command, "requires_approval": True, "category": "execute", "description": "Run shell command (approval required)"},
    "desktop_search_files": {"fn": search_files, "requires_approval": False, "category": "read", "description": "Search files by pattern"},
    "desktop_get_system_info": {"fn": get_system_info, "requires_approval": False, "category": "read", "description": "Get system info (OS, CPU, RAM, disk)"},
    "desktop_open_url": {"fn": open_url, "requires_approval": True, "category": "write", "description": "Open URL in browser (approval required)"},
    "desktop_screenshot": {"fn": take_screenshot, "requires_approval": True, "category": "read", "description": "Take desktop screenshot (approval required)"},
    # New: Clipboard
    "desktop_clipboard_read": {"fn": clipboard_read, "requires_approval": False, "category": "read", "description": "Read system clipboard contents"},
    "desktop_clipboard_write": {"fn": clipboard_write, "requires_approval": True, "category": "write", "description": "Write to system clipboard (approval required)"},
    # New: Process Management
    "desktop_list_processes": {"fn": list_processes, "requires_approval": False, "category": "read", "description": "List running processes sorted by CPU"},
    "desktop_kill_process": {"fn": kill_process, "requires_approval": True, "category": "execute", "description": "Kill a process by PID (approval required)"},
    # New: Network
    "desktop_network_ping": {"fn": network_ping, "requires_approval": False, "category": "network", "description": "Ping a host"},
    "desktop_network_dns": {"fn": network_dns, "requires_approval": False, "category": "network", "description": "DNS lookup for a hostname"},
    "desktop_network_ports": {"fn": network_ports, "requires_approval": False, "category": "network", "description": "Scan ports on a host"},
    # New: Docker
    "desktop_docker_list": {"fn": docker_list, "requires_approval": False, "category": "docker", "description": "List Docker containers"},
    "desktop_docker_control": {"fn": docker_control, "requires_approval": True, "category": "docker", "description": "Start/stop/restart Docker container (approval required)"},
    # New: Git
    "desktop_git_status": {"fn": git_status, "requires_approval": False, "category": "git", "description": "Git status, diff stats, and recent commits"},
    "desktop_git_diff": {"fn": git_diff, "requires_approval": False, "category": "git", "description": "Git diff for a repo or specific file"},
    # New: Environment
    "desktop_read_env": {"fn": read_env_vars, "requires_approval": False, "category": "read", "description": "Read environment variables (sensitive values masked)"},
}


# ============ Approval Logic ============

_approval_memory = {}  # tool_name -> "always" or "never"

def prompt_approval(tool_name, params, security):
    if security.auto_approve_reads and TOOLS.get(tool_name, {}).get("category") == "read":
        return True
    if tool_name in _approval_memory:
        return _approval_memory[tool_name] == "always"

    print(f"\n{'='*60}")
    print(f"  ACTION APPROVAL REQUIRED")
    print(f"{'='*60}")
    print(f"  Tool: {tool_name}")
    for k, v in params.items():
        val_str = str(v)
        if len(val_str) > 200:
            val_str = val_str[:200] + "..."
        print(f"  {k}: {val_str}")
    print(f"{'='*60}")

    while True:
        answer = input("  Approve? [y/n/always/never]: ").strip().lower()
        if answer in ("y", "yes"):
            return True
        elif answer in ("n", "no"):
            return False
        elif answer == "always":
            _approval_memory[tool_name] = "always"
            print(f"  [AUTO-APPROVE] {tool_name} will be auto-approved for this session")
            return True
        elif answer == "never":
            _approval_memory[tool_name] = "never"
            print(f"  [AUTO-DENY] {tool_name} will be auto-denied for this session")
            return False
        print("  Enter: y, n, always, never")


# ============ Kill Switch ============

_kill_switch = False

def emergency_disconnect():
    global _kill_switch
    _kill_switch = True
    print("\n  [KILL SWITCH] Emergency disconnect activated!")


# ============ WebSocket Client ============

async def run_bridge(server_url, token, user_id, security):
    global _kill_switch
    ws_url = server_url.replace("https://", "wss://").replace("http://", "ws://")
    ws_url = f"{ws_url}/api/ws/bridge/{user_id}/{token}"

    print(f"\n  Nexus Cloud Desktop Bridge v2")
    print(f"  {'='*40}")
    print(f"  Server:     {server_url}")
    print(f"  User:       {user_id}")
    print(f"  Machine:    {platform.node()} ({platform.system()})")
    print(f"  Tools:      {len(TOOLS)} available")
    print(f"  Rate limit: {security.rate_limit}/min")
    print(f"  Idle timeout: {security.idle_timeout}s")
    if security.allowed_paths:
        print(f"  Allowed paths: {', '.join(security.allowed_paths)}")
    if security.blocked_paths:
        print(f"  Blocked paths: {', '.join(security.blocked_paths)}")
    if not security.allow_commands:
        print(f"  Commands: DISABLED")
    if not security.allow_writes:
        print(f"  Writes: DISABLED")
    print(f"  {'='*40}")
    print(f"  Press Ctrl+C for kill switch\n")

    while not _kill_switch:
        try:
            ok, reason = security.check_idle_timeout()
            if not ok:
                print(f"  [TIMEOUT] {reason}")
                break

            async with websockets.connect(ws_url, ping_interval=30, ping_timeout=10) as ws:
                print(f"  [CONNECTED] {datetime.now().strftime('%H:%M:%S')}")
                security.touch_activity()

                caps = [{"name": name, "description": t["description"], "requires_approval": t["requires_approval"], "category": t.get("category", "other")}
                        for name, t in TOOLS.items()]
                await ws.send(json.dumps({
                    "type": "capabilities", "tools": caps,
                    "machine_name": platform.node(), "os": f"{platform.system()} {platform.release()}",
                    "version": "2.0", "security": {
                        "rate_limit": security.rate_limit, "idle_timeout": security.idle_timeout,
                        "commands_enabled": security.allow_commands, "writes_enabled": security.allow_writes,
                        "path_restrictions": bool(security.allowed_paths),
                    },
                }))

                async def heartbeat():
                    while not _kill_switch:
                        await asyncio.sleep(25)
                        ok, _ = security.check_idle_timeout()
                        if not ok or _kill_switch:
                            break
                        try:
                            await ws.send(json.dumps({"type": "heartbeat"}))
                        except Exception:
                            break

                hb_task = asyncio.create_task(heartbeat())

                try:
                    async for raw in ws:
                        if _kill_switch:
                            break
                        security.touch_activity()
                        msg = json.loads(raw)

                        if msg.get("type") == "tool_call":
                            call_id = msg["call_id"]
                            tool_name = msg["tool"]
                            params = msg.get("params") or {}

                            # Rate limit check
                            ok, reason = security.check_rate_limit()
                            if not ok:
                                await ws.send(json.dumps({"type": "tool_error", "call_id": call_id, "error": reason}))
                                print(f"  [RATE LIMITED] {tool_name}")
                                continue

                            tool = TOOLS.get(tool_name)
                            if not tool:
                                await ws.send(json.dumps({"type": "tool_error", "call_id": call_id, "error": f"Unknown tool: {tool_name}"}))
                                continue

                            if tool["requires_approval"]:
                                approved = prompt_approval(tool_name, params, security)
                                if not approved:
                                    await ws.send(json.dumps({"type": "tool_error", "call_id": call_id, "error": "User denied the action"}))
                                    print(f"  [DENIED] {tool_name}")
                                    continue

                            print(f"  [EXEC] {tool_name}", end="", flush=True)
                            start = time.time()
                            try:
                                result = tool["fn"](params, security)
                                ms = int((time.time() - start) * 1000)
                                print(f" -> OK ({ms}ms)")
                                await ws.send(json.dumps({"type": "tool_result", "call_id": call_id, "result": result}))
                            except Exception as e:
                                print(f" -> ERROR: {e}")
                                await ws.send(json.dumps({"type": "tool_error", "call_id": call_id, "error": str(e)}))

                        elif msg.get("type") == "kill_switch":
                            print(f"  [KILL SWITCH] Remote disconnect received")
                            _kill_switch = True
                            break
                        elif msg.get("type") == "heartbeat_ack":
                            pass
                finally:
                    hb_task.cancel()

        except websockets.exceptions.ConnectionClosed:
            if _kill_switch:
                break
            print(f"  [DISCONNECTED] Reconnecting in 5s...")
        except ConnectionRefusedError:
            print(f"  [ERROR] Connection refused")
        except Exception as e:
            print(f"  [ERROR] {e}")

        if _kill_switch:
            break
        await asyncio.sleep(5)

    print(f"\n  Bridge stopped at {datetime.now().strftime('%H:%M:%S')}")


def main():
    parser = argparse.ArgumentParser(description="Nexus Cloud Desktop Bridge Agent v2")
    parser.add_argument("--server", required=True, help="Nexus server URL")
    parser.add_argument("--token", required=True, help="Bridge connection token")
    parser.add_argument("--user", required=True, help="Your Nexus user ID")
    parser.add_argument("--allowed-paths", default="", help="Comma-separated allowed paths (e.g. ~/projects,~/Documents)")
    parser.add_argument("--blocked-paths", default="~/.ssh,~/.aws,~/.gnupg,/etc/shadow", help="Comma-separated blocked paths")
    parser.add_argument("--no-commands", action="store_true", help="Disable command execution")
    parser.add_argument("--no-writes", action="store_true", help="Disable all write operations")
    parser.add_argument("--auto-approve-reads", action="store_true", help="Auto-approve read-only operations")
    parser.add_argument("--rate-limit", type=int, default=30, help="Max invocations per minute (default: 30)")
    parser.add_argument("--idle-timeout", type=int, default=3600, help="Idle timeout in seconds (default: 3600)")
    args = parser.parse_args()

    security = SecurityConfig(args)

    def signal_handler(sig, frame):
        emergency_disconnect()
    signal.signal(signal.SIGINT, signal_handler)

    asyncio.run(run_bridge(args.server, args.token, args.user, security))


if __name__ == "__main__":
    main()
