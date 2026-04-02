import { useState, useEffect } from "react";
import { useConfirm } from "@/components/ConfirmDialog";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Monitor, Wifi, WifiOff, Plus, Trash2, Copy, Check, Terminal, FileText, FolderOpen, Globe, Camera, Cpu, RefreshCw, Loader2, Download, Shield } from "lucide-react";
import { api } from "@/App";
import { toast } from "sonner";

export default function DesktopBridgePanel() {
  const { confirm: confirmAction, ConfirmDialog: ConfirmDlg } = useConfirm();
  const [status, setStatus] = useState(null);
  const [tokens, setTokens] = useState([]);
  const [auditLog, setAuditLog] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState("My Desktop");
  const [newToken, setNewToken] = useState(null);
  const [copied, setCopied] = useState(false);
  const [showAudit, setShowAudit] = useState(false);
  const [availableAgents, setAvailableAgents] = useState([]);
  const [selectedAgents, setSelectedAgents] = useState([]);
  const [editingToken, setEditingToken] = useState(null);

  // Workspaces for selection
  const [workspaces, setWorkspaces] = useState([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState("");

  const load = async () => {
    try {
      const [sRes, tRes, wsRes] = await Promise.all([
        api.get("/bridge/status"),
        api.get("/bridge/tokens"),
        api.get("/workspaces"),
      ]);
      setStatus(sRes.data);
      setTokens(tRes.data || []);
      const wsList = Array.isArray(wsRes.data) ? wsRes.data : wsRes.data?.workspaces || [];
      setWorkspaces(wsList);
      // Load available AI models for agent selection
      try {
        const modelsRes = await api.get("/ai-models");
        const models = (modelsRes.data || []).filter(m => m.key && m.name);
        setAvailableAgents(models);
      } catch (_) {}
    } catch (err) { handleSilent(err, "DesktopBridgePanel:op1"); } finally { setLoading(false); }
  };

  const loadAudit = async () => {
    try {
      const res = await api.get("/bridge/audit-log?limit=30");
      setAuditLog(res.data || []);
    } catch (err) { handleSilent(err, "DesktopBridgePanel:op2"); }
  };

  useEffect(() => { load(); }, []);

  const createToken = async () => {
    if (!selectedWorkspace) return toast.error("Select a workspace first");
    try {
      const res = await api.post("/bridge/tokens", {
        name: newName,
        workspace_id: selectedWorkspace,
        allowed_agents: selectedAgents.length > 0 ? selectedAgents : [],
      });
      setNewToken(res.data);
      load();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  const updateTokenAgents = async (tokenId, agents) => {
    try {
      await api.put(`/bridge/tokens/${tokenId}`, { allowed_agents: agents });
      toast.success("Agent permissions updated");
      load();
      setEditingToken(null);
    } catch (err) { toast.error("Update failed"); }
  };

  const toggleAgent = (agentKey) => {
    setSelectedAgents(prev => prev.includes(agentKey) ? prev.filter(a => a !== agentKey) : [...prev, agentKey]);
  };

  const copyCommand = (t) => {
    const serverUrl = window.location.origin;
    const userId = sessionStorage.getItem("nexus_user") ? JSON.parse(sessionStorage.getItem("nexus_user")).user_id : "YOUR_USER_ID";
    const cmd = `python nexus_bridge.py --server ${serverUrl} --token ${t.token_preview || "YOUR_TOKEN"} --user ${userId}`;
    navigator.clipboard.writeText(cmd);
    toast.success("Run command copied to clipboard");
  };

  const revokeToken = async (tokenId) => {
    const _ok = await confirmAction("Revoke Token", "Revoke this desktop bridge token?"); if (!_ok) return;
    try {
      await api.delete(`/bridge/tokens/${tokenId}`);
      toast.success("Token revoked");
      load();
    } catch (err) { toast.error("Failed"); }
  };

  const TOOL_ICONS = {
    desktop_read_file: FileText, desktop_write_file: FileText, desktop_list_dir: FolderOpen,
    desktop_run_command: Terminal, desktop_search_files: FolderOpen, desktop_get_system_info: Cpu,
    desktop_open_url: Globe, desktop_screenshot: Camera,
  };

  if (loading) return <div className="p-4"><Loader2 className="w-4 h-4 animate-spin text-zinc-500" /></div>;

  return (
    <div className="space-y-4" data-testid="desktop-bridge-panel">
      {/* Connection Status */}
      <div className={`p-4 rounded-lg border ${status?.connected ? "border-emerald-500/30 bg-emerald-500/5" : "border-zinc-800/40 bg-zinc-900/30"}`}>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            {status?.connected ? <Wifi className="w-4 h-4 text-emerald-400" /> : <WifiOff className="w-4 h-4 text-zinc-600" />}
            <span className="text-sm font-medium text-zinc-200">Desktop Bridge</span>
            <Badge className={`text-[8px] ${status?.connected ? "bg-emerald-500/20 text-emerald-400" : "bg-zinc-800 text-zinc-500"}`}>
              {status?.connected ? "Connected" : "Disconnected"}
            </Badge>
          </div>
          <Button size="sm" variant="ghost" onClick={load} className="h-7 text-zinc-400"><RefreshCw className="w-3 h-3" /></Button>
          {status?.connected && (
            <Button size="sm" variant="ghost" onClick={async () => {
              try { await api.post("/bridge/kill-switch"); toast.success("Kill switch activated — bridge disconnected"); load(); } catch (err) { toast.error("Kill switch failed"); }
            }} className="h-7 text-red-400 hover:text-red-300 hover:bg-red-500/10" data-testid="bridge-kill-switch" title="Emergency Disconnect">
              <Shield className="w-3 h-3 mr-1" /> Kill
            </Button>
          )}
        </div>
        {status?.connected ? (
          <div className="text-[10px] text-zinc-400 space-y-1">
            <p><Monitor className="w-3 h-3 inline mr-1" />{status.machine_name} ({status.os})</p>
            <p>{status.capabilities?.length || 0} tools available</p>
            <div className="flex flex-wrap gap-1 mt-1">
              {(status.capabilities || []).map(t => {
                const Icon = TOOL_ICONS[t.name] || Terminal;
                return (
                  <Badge key={t.name} className="text-[8px] bg-zinc-800 text-zinc-400 gap-1">
                    <Icon className="w-2.5 h-2.5" />{t.name.replace("desktop_", "")}
                    {t.requires_approval && <Shield className="w-2.5 h-2.5 text-amber-400" />}
                  </Badge>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="text-[10px] text-zinc-500">
            <p>No desktop bridge connected. Generate a token below and run the bridge agent on your machine.</p>
          </div>
        )}
      </div>

      {/* Setup Instructions */}
      {!status?.connected && (
        <div className="p-3 rounded-lg bg-zinc-900/50 border border-zinc-800/30">
          <p className="text-xs font-semibold text-zinc-300 mb-2">Quick Setup</p>
          <div className="space-y-1.5 text-[10px] text-zinc-500">
            <p>1. Generate a bridge token below</p>
            <p>2. Download <code className="bg-zinc-800 px-1 rounded">nexus_bridge.py</code> from Settings</p>
            <p>3. Run: <code className="bg-zinc-800 px-1 rounded">pip install websockets</code></p>
            <p>4. Run: <code className="bg-zinc-800 px-1 rounded">python nexus_bridge.py --server URL --token TOKEN --user USER_ID</code></p>
          </div>
          <Button size="sm" onClick={async () => {
            try {
              const res = await api.get("/bridge/download-agent", { responseType: "blob" });
              const blobUrl = URL.createObjectURL(res.data);
              const a = document.createElement("a");
              a.href = blobUrl;
              a.download = "nexus_bridge.py";
              a.click();
              URL.revokeObjectURL(blobUrl);
            } catch (err) {
              toast.error("Download failed");
            }
          }} className="mt-2 h-7 text-[10px] bg-cyan-500 hover:bg-cyan-400 text-white gap-1">
            <Download className="w-3 h-3" /> Download Bridge Agent
          </Button>
        </div>
      )}

      {/* Tokens */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <p className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Bridge Tokens</p>
          <Button size="sm" onClick={() => { setCreateOpen(true); setNewToken(null); setNewName("My Desktop"); }}
            className="h-6 px-2 text-[10px] bg-cyan-500 hover:bg-cyan-400 text-white" data-testid="create-bridge-token">
            <Plus className="w-3 h-3 mr-1" /> New Token
          </Button>
        </div>
        {tokens.length === 0 ? (
          <p className="text-xs text-zinc-600 text-center py-2">No tokens created yet</p>
        ) : (
          <div className="space-y-1">
            {tokens.map(t => {
              const wsName = workspaces.find(w => w.workspace_id === t.workspace_id)?.name || t.workspace_id || "No workspace";
              return (
              <div key={t.token_id} className="p-3 rounded-lg bg-zinc-900/30 border border-zinc-800/30 space-y-2">
                {/* Header: name + workspace + status */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Monitor className="w-3.5 h-3.5 text-zinc-500" />
                    <span className="text-sm font-medium text-zinc-200">{t.name}</span>
                    <Badge className={`text-[8px] ${t.status === "connected" ? "bg-emerald-500/20 text-emerald-400" : "bg-zinc-800 text-zinc-500"}`}>{t.status}</Badge>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button size="sm" variant="ghost" onClick={() => copyCommand(t)} className="h-6 text-zinc-400" title="Copy run command"><Copy className="w-3 h-3" /></Button>
                    <Button size="sm" variant="ghost" onClick={() => revokeToken(t.token_id)} className="h-6 text-red-400 hover:text-red-300" title="Revoke"><Trash2 className="w-3 h-3" /></Button>
                  </div>
                </div>

                {/* Workspace binding */}
                <div className="flex items-center gap-1.5">
                  <span className="text-[9px] text-zinc-600 uppercase font-medium tracking-wider">Workspace:</span>
                  <Badge className="text-[9px] bg-indigo-500/15 text-indigo-400">{wsName}</Badge>
                </div>

                {/* Allowed agents — always visible */}
                <div>
                  <span className="text-[9px] text-zinc-600 uppercase font-medium tracking-wider">Allowed Agents:</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {t.allowed_agents && t.allowed_agents.length > 0 ? (
                      t.allowed_agents.map(a => (
                        <Badge key={a} className="text-[9px] bg-cyan-500/15 text-cyan-400">{a}</Badge>
                      ))
                    ) : (
                      <Badge className="text-[9px] bg-amber-500/15 text-amber-400">All agents (unrestricted)</Badge>
                    )}
                  </div>
                </div>

                {/* Edit agent permissions inline */}
                <div className="flex items-center gap-1 pt-1 border-t border-zinc-800/30">
                  <Button size="sm" variant="ghost" onClick={() => setEditingToken(editingToken === t.token_id ? null : t.token_id)} className="h-6 text-[9px] text-zinc-500 hover:text-zinc-300">
                    <Shield className="w-3 h-3 mr-1" /> {editingToken === t.token_id ? "Done editing" : "Edit permissions"}
                  </Button>
                </div>
                {editingToken === t.token_id && (
                  <div className="pt-1 space-y-1.5">
                    <p className="text-[10px] text-zinc-400">Click agents to toggle access:</p>
                    <div className="flex flex-wrap gap-1">
                      {availableAgents.map(agent => {
                        const isSelected = (t.allowed_agents || []).includes(agent.key);
                        return (
                          <button key={agent.key} onClick={() => {
                            const current = t.allowed_agents || [];
                            const updated = isSelected ? current.filter(a => a !== agent.key) : [...current, agent.key];
                            updateTokenAgents(t.token_id, updated);
                          }}
                          className={`px-2 py-0.5 text-[9px] rounded border transition-colors ${isSelected ? "bg-cyan-500/20 border-cyan-500/40 text-cyan-300" : "bg-zinc-800 border-zinc-700 text-zinc-500 hover:text-zinc-300"}`}>
                            {agent.name || agent.key}
                          </button>
                        );
                      })}
                    </div>
                    <p className="text-[9px] text-zinc-600">Empty = all agents allowed</p>
                  </div>
                )}
              </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ============ TOOL CONSOLE (shown when connected) ============ */}
      {status?.connected && (
        <BridgeToolConsole capabilities={status?.capabilities || []} />
      )}

      {/* Audit Log Toggle */}
      <Button size="sm" variant="outline" onClick={() => { setShowAudit(!showAudit); if (!showAudit) loadAudit(); }}
        className="w-full border-zinc-800 text-zinc-400 text-[10px]">
        {showAudit ? "Hide" : "Show"} Bridge Activity Log
      </Button>
      {showAudit && (
        <ScrollArea className="max-h-[200px]">
          {auditLog.length === 0 ? (
            <p className="text-xs text-zinc-600 text-center py-2">No bridge activity yet</p>
          ) : (
            <div className="space-y-1">
              {auditLog.map(log => (
                <div key={log.log_id} className="p-1.5 rounded bg-zinc-900/30 text-[10px]">
                  <div className="flex items-center justify-between">
                    <span className={`font-medium ${log.success ? "text-emerald-400" : "text-red-400"}`}>{log.tool}</span>
                    <span className="text-zinc-600">{log.created_at ? new Date(log.created_at).toLocaleString() : ""}</span>
                  </div>
                  <p className="text-zinc-500 truncate">{log.result_summary?.substring(0, 100)}</p>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      )}

      {/* Create Token Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-md">
          <DialogHeader>
            <DialogTitle className="text-zinc-100 flex items-center gap-2"><Monitor className="w-4 h-4 text-cyan-400" /> New Bridge Token</DialogTitle>
            <DialogDescription className="text-zinc-500">Generate a token for your desktop bridge agent</DialogDescription>
          </DialogHeader>
          {!newToken ? (
            <div className="space-y-3 mt-2">
              <Input value={newName} onChange={e => setNewName(e.target.value)} placeholder="Device name (e.g. My MacBook)" className="bg-zinc-950 border-zinc-800" />

              {/* Workspace Selector */}
              <div>
                <p className="text-xs text-zinc-400 mb-1.5 font-medium">Bind to Workspace:</p>
                <div className="grid grid-cols-2 gap-1.5 max-h-28 overflow-y-auto">
                  {workspaces.map(ws => (
                    <button key={ws.workspace_id} onClick={() => setSelectedWorkspace(ws.workspace_id)}
                      className={`px-2.5 py-1.5 text-xs rounded border text-left transition-colors ${selectedWorkspace === ws.workspace_id ? "bg-cyan-500/20 border-cyan-500/40 text-cyan-300" : "bg-zinc-900 border-zinc-800 text-zinc-500 hover:text-zinc-300"}`}>
                      {ws.name || ws.workspace_id}
                    </button>
                  ))}
                </div>
                {!selectedWorkspace && <p className="text-[9px] text-red-400 mt-1">Required — each bridge token is bound to one workspace</p>}
              </div>

              {/* Agent/Model Selector */}
              <div>
                <p className="text-xs text-zinc-400 mb-1.5 font-medium">Allowed AI Agents & Models:</p>
                <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
                  {availableAgents.map(agent => (
                    <button key={agent.key} onClick={() => toggleAgent(agent.key)}
                      className={`px-2.5 py-1 text-xs rounded border transition-colors ${selectedAgents.includes(agent.key) ? "bg-cyan-500/20 border-cyan-500/40 text-cyan-300" : "bg-zinc-900 border-zinc-800 text-zinc-500 hover:text-zinc-300"}`}>
                      {agent.name || agent.key}
                    </button>
                  ))}
                </div>
                <p className="text-[9px] text-zinc-600 mt-1">{selectedAgents.length === 0 ? "No agents selected = all agents allowed (less secure)" : `${selectedAgents.length} agent(s) selected — only these can use the bridge`}</p>
              </div>

              <Button onClick={createToken} disabled={!selectedWorkspace} className="w-full bg-cyan-500 hover:bg-cyan-400 text-white">Generate Token</Button>
            </div>
          ) : (
            <div className="space-y-3 mt-2">
              <p className="text-xs text-amber-400">Copy this token now — it won't be shown again!</p>
              <div className="p-2 rounded bg-zinc-950 border border-zinc-800 font-mono text-xs text-zinc-300 break-all">{newToken.token}</div>
              <Button onClick={() => { navigator.clipboard.writeText(newToken.token); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
                className="w-full bg-zinc-800 text-zinc-200 gap-2">
                {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                {copied ? "Copied!" : "Copy Token"}
              </Button>
              <div className="p-2 rounded bg-zinc-900 text-[10px] text-zinc-500">
                <p className="mb-1">Run on your machine:</p>
                <code className="text-cyan-400">python nexus_bridge.py --server {window.location.origin} --token {newToken.token} --user {newToken.user_id}</code>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    <ConfirmDlg />
    </div>
    );
}

// ============ Tool Console ============

function BridgeToolConsole({ capabilities }) {
  const [activeTab, setActiveTab] = useState("files");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  // File browser
  const [filePath, setFilePath] = useState("~");
  const [dirContents, setDirContents] = useState(null);
  const [fileContent, setFileContent] = useState(null);
  // Terminal
  const [command, setCommand] = useState("");
  const [cmdOutput, setCmdOutput] = useState(null);
  // System
  const [sysInfo, setSysInfo] = useState(null);
  const [processes, setProcesses] = useState(null);
  // Network
  const [pingHost, setPingHost] = useState("");
  const [pingResult, setPingResult] = useState(null);
  // Git
  const [gitPath, setGitPath] = useState(".");
  const [gitResult, setGitResult] = useState(null);

  const invoke = async (tool, params) => {
    setLoading(true);
    try {
      const res = await api.post("/bridge/invoke", { tool, params });
      setResult(res.data);
      return res.data;
    } catch (err) {
      const detail = err?.response?.data?.detail || "Bridge tool failed";
      toast.error(detail);
      return { success: false, error: detail };
    } finally {
      setLoading(false);
    }
  };

  const listDir = async (path) => {
    const res = await invoke("desktop_list_dir", { path });
    if (res?.success) { setDirContents(res.result); setFilePath(path); setFileContent(null); }
  };

  const readFile = async (path) => {
    const res = await invoke("desktop_read_file", { path });
    if (res?.success) setFileContent(res.result);
  };

  const runCommand = async () => {
    if (!command.trim()) return;
    const res = await invoke("desktop_run_command", { command });
    if (res?.success) setCmdOutput(res.result);
    else if (res?.error) setCmdOutput({ stdout: "", stderr: res.error, exit_code: -1 });
  };

  const getSystemInfo = async () => {
    const res = await invoke("desktop_get_system_info", {});
    if (res?.success) setSysInfo(res.result);
  };

  const getProcesses = async () => {
    const res = await invoke("desktop_list_processes", {});
    if (res?.success) setProcesses(res.result);
  };

  const pingHostFn = async () => {
    if (!pingHost.trim()) return;
    const res = await invoke("desktop_network_ping", { host: pingHost, count: 4 });
    if (res?.success) setPingResult(res.result);
  };

  const getGitStatus = async () => {
    const res = await invoke("desktop_git_status", { path: gitPath });
    if (res?.success) setGitResult(res.result);
  };

  const tabs = [
    { key: "files", label: "Files", icon: FolderOpen },
    { key: "terminal", label: "Terminal", icon: Terminal },
    { key: "system", label: "System", icon: Cpu },
    { key: "network", label: "Network", icon: Globe },
    { key: "git", label: "Git", icon: FileText },
  ];

  return (
    <div className="border border-zinc-800 rounded-lg overflow-hidden" data-testid="bridge-tool-console">
      <div className="flex border-b border-zinc-800 bg-zinc-900/50">
        {tabs.map(t => {
          const Icon = t.icon;
          return (
            <button key={t.key} onClick={() => setActiveTab(t.key)}
              className={`flex items-center gap-1 px-3 py-2 text-[10px] font-medium border-b-2 transition-colors ${activeTab === t.key ? "border-cyan-500 text-zinc-100 bg-zinc-800/50" : "border-transparent text-zinc-500 hover:text-zinc-300"}`}>
              <Icon className="w-3 h-3" /> {t.label}
            </button>
          );
        })}
        {loading && <Loader2 className="w-3 h-3 animate-spin text-cyan-400 ml-auto mr-2 my-auto" />}
      </div>

      <div className="p-3 min-h-[200px] max-h-[400px] overflow-y-auto bg-zinc-950/50">
        {/* Files Tab */}
        {activeTab === "files" && (
          <div className="space-y-2">
            <div className="flex gap-1">
              <Input value={filePath} onChange={e => setFilePath(e.target.value)} onKeyDown={e => e.key === "Enter" && listDir(filePath)} placeholder="Path (e.g. ~/projects)" className="bg-zinc-900 border-zinc-800 h-7 text-xs flex-1" />
              <Button size="sm" onClick={() => listDir(filePath)} disabled={loading} className="h-7 text-xs bg-zinc-800"><FolderOpen className="w-3 h-3 mr-1" /> Browse</Button>
            </div>
            {dirContents && (
              <div className="space-y-0.5">
                <button onClick={() => listDir(filePath.includes("/") ? filePath.rsplit("/", 1)[0] || "/" : "/")} className="text-[10px] text-cyan-400 hover:underline">.. (parent)</button>
                {(dirContents.entries || []).map(e => (
                  <div key={e.name} className="flex items-center justify-between py-0.5 text-[10px] hover:bg-zinc-800/30 px-1 rounded cursor-pointer"
                    onClick={() => e.is_dir ? listDir(`${filePath}/${e.name}`) : readFile(`${filePath}/${e.name}`)}>
                    <div className="flex items-center gap-1">
                      {e.is_dir ? <FolderOpen className="w-3 h-3 text-amber-400" /> : <FileText className="w-3 h-3 text-zinc-500" />}
                      <span className={e.is_dir ? "text-amber-300" : "text-zinc-300"}>{e.name}</span>
                    </div>
                    {!e.is_dir && <span className="text-zinc-600">{(e.size / 1024).toFixed(1)}KB</span>}
                  </div>
                ))}
                {dirContents.total > 200 && <p className="text-[9px] text-zinc-600">Showing 200 of {dirContents.total}</p>}
              </div>
            )}
            {fileContent && (
              <div className="mt-2">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] text-zinc-400 font-medium">{fileContent.path}</span>
                  <span className="text-[9px] text-zinc-600">{(fileContent.size / 1024).toFixed(1)}KB</span>
                </div>
                <pre className="bg-zinc-900 border border-zinc-800 rounded p-2 text-[10px] text-zinc-300 max-h-[200px] overflow-auto font-mono whitespace-pre-wrap">{fileContent.content}</pre>
              </div>
            )}
            {!dirContents && !fileContent && <p className="text-xs text-zinc-600 text-center py-6">Enter a path and click Browse to explore your files</p>}
          </div>
        )}

        {/* Terminal Tab */}
        {activeTab === "terminal" && (
          <div className="space-y-2">
            <div className="flex gap-1">
              <Input value={command} onChange={e => setCommand(e.target.value)} onKeyDown={e => e.key === "Enter" && runCommand()} placeholder="Enter command (e.g. ls -la, git status, docker ps)" className="bg-zinc-900 border-zinc-800 h-7 text-xs font-mono flex-1" />
              <Button size="sm" onClick={runCommand} disabled={loading} className="h-7 text-xs bg-zinc-800"><Terminal className="w-3 h-3 mr-1" /> Run</Button>
            </div>
            {cmdOutput && (
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <Badge className={`text-[8px] ${cmdOutput.exit_code === 0 ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"}`}>exit {cmdOutput.exit_code}</Badge>
                </div>
                {cmdOutput.stdout && <pre className="bg-zinc-900 border border-zinc-800 rounded p-2 text-[10px] text-zinc-300 max-h-[200px] overflow-auto font-mono whitespace-pre-wrap">{cmdOutput.stdout}</pre>}
                {cmdOutput.stderr && <pre className="bg-red-900/20 border border-red-800/30 rounded p-2 text-[10px] text-red-400 max-h-[100px] overflow-auto font-mono whitespace-pre-wrap">{cmdOutput.stderr}</pre>}
              </div>
            )}
            {!cmdOutput && <p className="text-xs text-zinc-600 text-center py-6">Commands require approval on your desktop</p>}
          </div>
        )}

        {/* System Tab */}
        {activeTab === "system" && (
          <div className="space-y-2">
            <div className="flex gap-2">
              <Button size="sm" onClick={getSystemInfo} disabled={loading} className="h-7 text-xs bg-zinc-800"><Cpu className="w-3 h-3 mr-1" /> System Info</Button>
              <Button size="sm" onClick={getProcesses} disabled={loading} className="h-7 text-xs bg-zinc-800"><Monitor className="w-3 h-3 mr-1" /> Processes</Button>
            </div>
            {sysInfo && (
              <div className="grid grid-cols-2 gap-2 text-[10px]">
                {Object.entries(sysInfo).map(([k, v]) => (
                  <div key={k} className="flex justify-between py-0.5 border-b border-zinc-800/30">
                    <span className="text-zinc-500">{k.replace(/_/g, " ")}</span>
                    <span className="text-zinc-300">{String(v)}</span>
                  </div>
                ))}
              </div>
            )}
            {processes && (
              <div className="text-[10px]">
                <div className="grid grid-cols-4 gap-1 text-zinc-500 font-medium mb-1"><span>PID</span><span>Name</span><span>CPU%</span><span>MEM%</span></div>
                {(processes.processes || []).slice(0, 20).map(p => (
                  <div key={p.pid} className="grid grid-cols-4 gap-1 text-zinc-400 py-0.5 border-b border-zinc-800/20">
                    <span className="text-zinc-500">{p.pid}</span><span className="text-zinc-300 truncate">{p.name}</span>
                    <span>{(p.cpu_percent || 0).toFixed(1)}</span><span>{(p.memory_percent || 0).toFixed(1)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Network Tab */}
        {activeTab === "network" && (
          <div className="space-y-2">
            <div className="flex gap-1">
              <Input value={pingHost} onChange={e => setPingHost(e.target.value)} onKeyDown={e => e.key === "Enter" && pingHostFn()} placeholder="Host to ping (e.g. google.com)" className="bg-zinc-900 border-zinc-800 h-7 text-xs flex-1" />
              <Button size="sm" onClick={pingHostFn} disabled={loading} className="h-7 text-xs bg-zinc-800"><Globe className="w-3 h-3 mr-1" /> Ping</Button>
            </div>
            {pingResult && (
              <pre className="bg-zinc-900 border border-zinc-800 rounded p-2 text-[10px] text-zinc-300 max-h-[200px] overflow-auto font-mono whitespace-pre-wrap">{pingResult.output || JSON.stringify(pingResult, null, 2)}</pre>
            )}
          </div>
        )}

        {/* Git Tab */}
        {activeTab === "git" && (
          <div className="space-y-2">
            <div className="flex gap-1">
              <Input value={gitPath} onChange={e => setGitPath(e.target.value)} placeholder="Repo path (e.g. ~/projects/myrepo)" className="bg-zinc-900 border-zinc-800 h-7 text-xs flex-1" />
              <Button size="sm" onClick={getGitStatus} disabled={loading} className="h-7 text-xs bg-zinc-800"><FileText className="w-3 h-3 mr-1" /> Status</Button>
            </div>
            {gitResult && (
              <div className="space-y-2">
                <div className="text-[10px]"><span className="text-zinc-500">Branch:</span> <span className="text-cyan-400">{gitResult.branch}</span></div>
                {gitResult.status && <pre className="bg-zinc-900 border border-zinc-800 rounded p-2 text-[10px] text-zinc-300 max-h-[100px] overflow-auto font-mono whitespace-pre-wrap">{gitResult.status}</pre>}
                {gitResult.recent_commits && (
                  <div><span className="text-[10px] text-zinc-500">Recent commits:</span><pre className="bg-zinc-900 border border-zinc-800 rounded p-2 text-[10px] text-zinc-300 max-h-[80px] overflow-auto font-mono whitespace-pre-wrap">{gitResult.recent_commits}</pre></div>
                )}
                {gitResult.diff_stat && (
                  <div><span className="text-[10px] text-zinc-500">Uncommitted changes:</span><pre className="bg-zinc-900 border border-zinc-800 rounded p-2 text-[10px] text-amber-400 max-h-[80px] overflow-auto font-mono whitespace-pre-wrap">{gitResult.diff_stat}</pre></div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
