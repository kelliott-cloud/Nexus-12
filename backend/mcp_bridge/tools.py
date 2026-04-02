"""Bridge Tool Definitions v2 — Available tools when a desktop bridge is connected."""

BRIDGE_TOOLS = [
    # File Operations
    {"name": "desktop_read_file", "description": "Read a file from the user's local machine", "parameters": {"path": {"type": "string", "description": "Absolute file path", "required": True}}, "requires_approval": False, "category": "read"},
    {"name": "desktop_write_file", "description": "Write/create a file on the user's machine (approval required)", "parameters": {"path": {"type": "string", "description": "Absolute file path", "required": True}, "content": {"type": "string", "description": "File content", "required": True}}, "requires_approval": True, "category": "write"},
    {"name": "desktop_list_dir", "description": "List files and folders in a directory", "parameters": {"path": {"type": "string", "description": "Directory path", "required": True}}, "requires_approval": False, "category": "read"},
    {"name": "desktop_search_files", "description": "Search for files by name pattern", "parameters": {"pattern": {"type": "string", "description": "File name glob pattern", "required": True}, "directory": {"type": "string", "description": "Search directory", "required": True}}, "requires_approval": False, "category": "read"},
    # System
    {"name": "desktop_run_command", "description": "Run a terminal command (approval required)", "parameters": {"command": {"type": "string", "description": "Shell command", "required": True}, "cwd": {"type": "string", "description": "Working directory", "required": False}}, "requires_approval": True, "category": "execute"},
    {"name": "desktop_get_system_info", "description": "Get OS, CPU, RAM, disk info", "parameters": {}, "requires_approval": False, "category": "read"},
    {"name": "desktop_open_url", "description": "Open URL in user's browser (approval required)", "parameters": {"url": {"type": "string", "description": "URL to open", "required": True}}, "requires_approval": True, "category": "write"},
    {"name": "desktop_screenshot", "description": "Take a desktop screenshot (approval required)", "parameters": {}, "requires_approval": True, "category": "read"},
    # Clipboard
    {"name": "desktop_clipboard_read", "description": "Read the system clipboard contents", "parameters": {}, "requires_approval": False, "category": "read"},
    {"name": "desktop_clipboard_write", "description": "Write text to the system clipboard (approval required)", "parameters": {"content": {"type": "string", "description": "Text to copy", "required": True}}, "requires_approval": True, "category": "write"},
    # Process Management
    {"name": "desktop_list_processes", "description": "List running processes sorted by CPU usage", "parameters": {}, "requires_approval": False, "category": "read"},
    {"name": "desktop_kill_process", "description": "Kill a process by PID (approval required)", "parameters": {"pid": {"type": "integer", "description": "Process ID to kill", "required": True}}, "requires_approval": True, "category": "execute"},
    # Network
    {"name": "desktop_network_ping", "description": "Ping a host to check connectivity", "parameters": {"host": {"type": "string", "description": "Hostname or IP", "required": True}, "count": {"type": "integer", "description": "Number of pings (max 10)", "required": False}}, "requires_approval": False, "category": "network"},
    {"name": "desktop_network_dns", "description": "DNS lookup for a hostname", "parameters": {"host": {"type": "string", "description": "Hostname to resolve", "required": True}}, "requires_approval": False, "category": "network"},
    {"name": "desktop_network_ports", "description": "Scan ports on a host", "parameters": {"host": {"type": "string", "description": "Hostname or IP (default: localhost)", "required": False}, "ports": {"type": "string", "description": "Comma-separated ports to scan", "required": False}}, "requires_approval": False, "category": "network"},
    # Docker
    {"name": "desktop_docker_list", "description": "List all Docker containers", "parameters": {}, "requires_approval": False, "category": "docker"},
    {"name": "desktop_docker_control", "description": "Start/stop/restart a Docker container (approval required)", "parameters": {"action": {"type": "string", "description": "start, stop, restart, or logs", "required": True}, "container": {"type": "string", "description": "Container name or ID", "required": True}}, "requires_approval": True, "category": "docker"},
    # Git
    {"name": "desktop_git_status", "description": "Git status, diff stats, and recent commits", "parameters": {"path": {"type": "string", "description": "Repository path (default: current dir)", "required": False}}, "requires_approval": False, "category": "git"},
    {"name": "desktop_git_diff", "description": "Git diff for a repo or specific file", "parameters": {"path": {"type": "string", "description": "Repository path", "required": False}, "file": {"type": "string", "description": "Specific file to diff", "required": False}}, "requires_approval": False, "category": "git"},
    # Environment
    {"name": "desktop_read_env", "description": "Read environment variables (sensitive values auto-masked)", "parameters": {"prefix": {"type": "string", "description": "Filter by prefix (e.g. 'NODE_', 'PYTHON_')", "required": False}}, "requires_approval": False, "category": "read"},
]

BRIDGE_TOOL_PROMPT = """
=== DESKTOP BRIDGE TOOLS v2 ===
The user has a desktop bridge connected. You can interact with their local machine.

FILE OPERATIONS:
- desktop_read_file(path) — Read a file
- desktop_write_file(path, content) — Write/create a file [APPROVAL]
- desktop_list_dir(path) — List directory contents
- desktop_search_files(pattern, directory) — Search files by glob pattern

SYSTEM:
- desktop_run_command(command, cwd) — Run shell command [APPROVAL]
- desktop_get_system_info() — OS, CPU, RAM, disk info
- desktop_open_url(url) — Open URL in browser [APPROVAL]
- desktop_screenshot() — Take desktop screenshot [APPROVAL]

CLIPBOARD:
- desktop_clipboard_read() — Read clipboard contents
- desktop_clipboard_write(content) — Write to clipboard [APPROVAL]

PROCESS MANAGEMENT:
- desktop_list_processes() — List running processes by CPU
- desktop_kill_process(pid) — Kill a process [APPROVAL]

NETWORK:
- desktop_network_ping(host, count) — Ping a host
- desktop_network_dns(host) — DNS lookup
- desktop_network_ports(host, ports) — Port scan

DOCKER:
- desktop_docker_list() — List Docker containers
- desktop_docker_control(action, container) — Start/stop/restart/logs [APPROVAL]

GIT:
- desktop_git_status(path) — Status, diff stats, recent commits
- desktop_git_diff(path, file) — Git diff

ENVIRONMENT:
- desktop_read_env(prefix) — Read env vars (secrets auto-masked)

SECURITY:
- [APPROVAL] tools require user confirmation on their desktop
- File access is restricted by user's path allowlist/blocklist
- Dangerous commands (rm -rf /, format, etc.) are auto-blocked
- Rate limited to prevent abuse
- Sensitive env vars are auto-masked

To use: TOOL_CALL: desktop_tool_name | {"param": "value"}
=== END DESKTOP BRIDGE ===
"""
