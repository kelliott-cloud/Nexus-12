import { useState, useEffect, useCallback, useRef } from "react";
import { useConfirm } from "@/components/ConfirmDialog";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { useNavigate } from "react-router-dom";
import { api } from "@/App";
import { markRecentAuth } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import {
  MessageSquare, FolderKanban, FileCode, BookOpen, Settings,
  Plus, Hash, Send, Loader2, ArrowLeft, Zap, LogOut, ChevronRight,
  CheckCircle2, Circle, Clock, AlertCircle, Bot, User, Power,
  RotateCw, Menu, X, Home, Bell, Search, RefreshCw, Trash2, Paperclip,
} from "lucide-react";

// ===== Mobile Dashboard =====
export function MobileDashboard({ user }) {
  const navigate = useNavigate();
  const [workspaces, setWorkspaces] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [wsName, setWsName] = useState("");

  useEffect(() => {
    api.get("/workspaces").then(r => setWorkspaces(r.data || [])).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const createWorkspace = async () => {
    if (!wsName.trim()) return;
    try {
      const res = await api.post("/workspaces", { name: wsName });
      navigate(`/workspace/${res.data.workspace_id}`);
    } catch (err) { toast.error("Failed"); }
  };

  const handleLogout = async () => {
    try { await api.post("/auth/logout"); } catch (err) { handleSilent(err, "MobileApp:op1"); }
    sessionStorage.removeItem("nexus_user");
    navigate("/");
  };

  return (
    <div className="min-h-screen bg-zinc-950 flex flex-col" style={{ paddingTop: "env(safe-area-inset-top)", paddingBottom: "env(safe-area-inset-bottom)" }} data-testid="mobile-dashboard">
      {/* Header */}
      <div className="flex-shrink-0 px-4 py-3 border-b border-zinc-800/60 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <img src="/logo.png" alt="Nexus Cloud" className="w-7 h-7 rounded-lg" />
          <span className="font-bold text-sm text-zinc-100" style={{ fontFamily: "Syne, sans-serif" }}>NEXUS <span className="text-cyan-400">CLOUD</span></span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => navigate("/settings")} className="p-2 text-zinc-500"><Settings className="w-5 h-5" /></button>
          <button onClick={handleLogout} className="p-2 text-zinc-500"><LogOut className="w-5 h-5" /></button>
        </div>
      </div>

      {/* Welcome */}
      <div className="px-4 py-4">
        <h1 className="text-xl font-bold text-zinc-100" style={{ fontFamily: "Syne, sans-serif" }}>Welcome, {user?.name?.split(" ")[0]}</h1>
        <p className="text-sm text-zinc-500 mt-1">Your workspaces</p>
      </div>

      {/* Workspaces */}
      <ScrollArea className="flex-1 px-4">
        {loading ? (
          <div className="flex justify-center py-8"><Loader2 className="w-5 h-5 text-zinc-500 animate-spin" /></div>
        ) : workspaces.length === 0 ? (
          <div className="text-center py-12">
            <Zap className="w-10 h-10 text-zinc-800 mx-auto mb-3" />
            <p className="text-sm text-zinc-500">No workspaces yet</p>
          </div>
        ) : (
          <div className="space-y-2 pb-20">
            {workspaces.map(ws => (
              <button key={ws.workspace_id} onClick={() => navigate(`/workspace/${ws.workspace_id}`)}
                className="w-full p-4 rounded-xl bg-zinc-900/60 border border-zinc-800/40 text-left active:scale-[0.98] transition-transform"
                data-testid={`mobile-ws-${ws.workspace_id}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-zinc-800 flex items-center justify-center">
                      <Zap className="w-5 h-5 text-zinc-400" />
                    </div>
                    <div>
                      <span className="text-sm font-semibold text-zinc-200">{ws.name}</span>
                      <p className="text-[11px] text-zinc-600 mt-0.5">{ws.channel_count || 0} channels</p>
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-zinc-600" />
                </div>
              </button>
            ))}
          </div>
        )}
      </ScrollArea>

      {/* FAB */}
      <button onClick={() => setCreateOpen(true)}
        className="fixed bottom-6 right-4 w-14 h-14 rounded-full bg-emerald-500 flex items-center justify-center shadow-lg active:scale-95 transition-transform z-50"
        style={{ bottom: "calc(env(safe-area-inset-bottom, 0px) + 24px)" }}
        data-testid="mobile-create-ws">
        <Plus className="w-6 h-6 text-white" />
      </button>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 mx-4">
          <DialogHeader><DialogTitle className="text-zinc-100">New Workspace</DialogTitle><DialogDescription className="sr-only">Create workspace</DialogDescription></DialogHeader>
          <div className="space-y-3 mt-2">
            <Input value={wsName} onChange={(e) => setWsName(e.target.value)} placeholder="Workspace name" className="bg-zinc-950 border-zinc-800" autoFocus data-testid="mobile-ws-name" />
            <Button onClick={createWorkspace} disabled={!wsName.trim()} className="w-full bg-zinc-100 text-zinc-900">Create</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ===== Mobile Workspace =====
export function MobileWorkspace({ user }) {
  const { confirm: confirmAction, ConfirmDialog: ConfirmDlg } = useConfirm();
  const navigate = useNavigate();
  const workspaceId = window.location.pathname.split("/workspace/")[1]?.split("/")[0];
  const [workspace, setWorkspace] = useState(null);
  const [channels, setChannels] = useState([]);
  const [selectedChannel, setSelectedChannel] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [pendingFile, setPendingFile] = useState(null);
  const [isCollaborating, setIsCollaborating] = useState(false);
  const [activeView, setActiveView] = useState("chat"); // chat, projects, code, docs
  const [menuOpen, setMenuOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [projects, setProjects] = useState([]);
  const [tasks, setTasks] = useState([]);
  const touchStart = useRef(null);

  // Haptic feedback helper
  const haptic = (style = "light") => {
    if (navigator.vibrate) navigator.vibrate(style === "heavy" ? 50 : 10);
  };

  // Swipe gesture handler
  const handleTouchStart = (e) => { touchStart.current = { x: e.touches[0].clientX, y: e.touches[0].clientY }; };
  const handleTouchEnd = (e) => {
    if (!touchStart.current) return;
    const dx = e.changedTouches[0].clientX - touchStart.current.x;
    const dy = e.changedTouches[0].clientY - touchStart.current.y;
    if (Math.abs(dx) > 80 && Math.abs(dx) > Math.abs(dy) * 2) {
      const views = ["chat", "projects", "docs", "settings"];
      const idx = views.indexOf(activeView);
      if (dx > 0 && idx > 0) { setActiveView(views[idx - 1]); haptic(); } // swipe right = back
      else if (dx < 0 && idx < views.length - 1) { setActiveView(views[idx + 1]); haptic(); } // swipe left = forward
    }
    touchStart.current = null;
  };
  const [disabledAgents, setDisabledAgents] = useState([]);
  const [createChannelOpen, setCreateChannelOpen] = useState(false);
  const [newChannelName, setNewChannelName] = useState("");
  const [selectedAgents, setSelectedAgents] = useState(["claude", "chatgpt"]);
  const [refreshing, setRefreshing] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);

  const AI_COLORS = { claude: "#D97757", chatgpt: "#10A37F", gemini: "#4285F4", deepseek: "#4D6BFE", grok: "#F5F5F5", groq: "#F55036", perplexity: "#20B2AA", mistral: "#FF7000", cohere: "#39594D", mercury: "#00D4FF", pi: "#FF6B35", manus: "#6C5CE7", qwen: "#615EFF", kimi: "#000000", llama: "#0467DF", glm: "#3D5AFE", cursor: "#00E5A0", notebooklm: "#FBBC04", copilot: "#171515" };
  const AI_NAMES = { claude: "Claude", chatgpt: "ChatGPT", gemini: "Gemini", deepseek: "DeepSeek", grok: "Grok", groq: "Groq", perplexity: "Perplexity", mistral: "Mistral", cohere: "Cohere", mercury: "Mercury", pi: "Pi", manus: "Manus", qwen: "Qwen", kimi: "Kimi", llama: "Llama", glm: "GLM", cursor: "Cursor", notebooklm: "NotebookLM", copilot: "GitHub Copilot" };

  useEffect(() => {
    const load = async () => {
      try {
        const [wsRes, chRes] = await Promise.all([
          api.get(`/workspaces/${workspaceId}`),
          api.get(`/workspaces/${workspaceId}/channels`),
        ]);
        setWorkspace(wsRes.data);
        setChannels(chRes.data);
        if (chRes.data.length > 0) setSelectedChannel(chRes.data[0]);
      } catch (err) { navigate("/dashboard"); }
      setLoading(false);
    };
    load();
  }, [workspaceId, navigate]);

  // Fetch messages
  const fetchMessages = useCallback(async () => {
    if (!selectedChannel) return;
    try {
      const [msgRes, statusRes] = await Promise.all([
        api.get(`/channels/${selectedChannel.channel_id}/messages`),
        api.get(`/channels/${selectedChannel.channel_id}/status`),
      ]);
      setMessages(msgRes.data);
      setIsCollaborating(statusRes.data.is_running || false);
    } catch (err) { handleSilent(err, "MobileApp:op2"); }
  }, [selectedChannel]);

  useEffect(() => { fetchMessages(); }, [fetchMessages]);
  useEffect(() => {
    if (!selectedChannel) return;
    const i = setInterval(fetchMessages, 3000);
    return () => clearInterval(i);
  }, [selectedChannel, fetchMessages]);

  // Fetch disabled agents
  useEffect(() => {
    if (selectedChannel?.channel_id) {
      api.get(`/channels/${selectedChannel.channel_id}/disabled-agents`)
        .then(r => setDisabledAgents(r.data?.disabled_agents || []))
        .catch(() => {});
    }
  }, [selectedChannel?.channel_id]);

  // Fetch projects/tasks
  useEffect(() => {
    if (activeView === "projects") {
      api.get(`/workspaces/${workspaceId}/all-tasks`).then(r => {
        setProjects(r.data?.groups || []);
        setTasks(r.data?.groups?.flatMap(g => g.tasks || []) || []);
      }).catch(() => {});
    }
  }, [activeView, workspaceId]);

  const sendMessage = async () => {
    if ((!input.trim() && !pendingFile) || !selectedChannel || sending) return;
    setSending(true);
    const msg = input;
    setInput("");
    try {
      if (pendingFile) {
        const formData = new FormData();
        formData.append("file", pendingFile);
        formData.append("message", msg);
        await api.post(`/channels/${selectedChannel.channel_id}/files`, formData, { headers: { "Content-Type": "multipart/form-data" } });
        setPendingFile(null);
      } else {
        await api.post(`/channels/${selectedChannel.channel_id}/messages`, { content: msg });
      }
      await fetchMessages();
      const res = await api.post(`/channels/${selectedChannel.channel_id}/collaborate`);
      if (res.data.status === "limit_reached") toast.error(res.data.message);
    } catch (err) { toast.error("Failed"); }
    setSending(false);
  };

  const toggleAgent = async (agentKey) => {
    if (!selectedChannel) return;
    const isDisabled = disabledAgents.includes(agentKey);
    try {
      await api.put(`/channels/${selectedChannel.channel_id}/agent-toggle`, { agent_key: agentKey, enabled: isDisabled });
      setDisabledAgents(prev => isDisabled ? prev.filter(a => a !== agentKey) : [...prev, agentKey]);
      toast.success(`${AI_NAMES[agentKey] || agentKey} ${isDisabled ? "enabled" : "disabled"}`);
    } catch (err) { handleSilent(err, "MobileApp:op3"); }
  };

  const createChannel = async () => {
    if (!newChannelName.trim()) return;
    try {
      const res = await api.post(`/workspaces/${workspaceId}/channels`, {
        name: newChannelName, description: "", ai_agents: selectedAgents,
      });
      setChannels(prev => [...prev, res.data]);
      setSelectedChannel(res.data);
      setCreateChannelOpen(false);
      setNewChannelName("");
      toast.success("Channel created");
    } catch (err) { toast.error("Failed"); }
  };

  const handlePullRefresh = async () => {
    setRefreshing(true);
    await fetchMessages();
    setRefreshing(false);
  };

  const handleSearch = async (q) => {
    setSearchQuery(q);
    if (!q.trim()) { setSearchResults([]); return; }
    try {
      const res = await api.get(`/workspaces/${workspaceId}/search?q=${encodeURIComponent(q)}`);
      setSearchResults(res.data.results || []);
    } catch (err) { handleSilent(err, "MobileApp:op4"); }
  };

  if (loading) return <div className="min-h-screen bg-zinc-950 flex items-center justify-center"><Loader2 className="w-6 h-6 text-zinc-500 animate-spin" /></div>;

  return (
    <div className="h-[100dvh] bg-zinc-950 flex flex-col" style={{ paddingTop: "env(safe-area-inset-top)" }} data-testid="mobile-workspace">
      {/* Header */}
      <div className="flex-shrink-0 px-3 py-2 border-b border-zinc-800/60 flex items-center gap-2">
        <button onClick={() => navigate("/dashboard")} className="p-1.5 text-zinc-400"><ArrowLeft className="w-5 h-5" /></button>
        <span className="text-sm font-semibold text-zinc-200 truncate flex-1">{workspace?.name}</span>
        <button onClick={() => setSearchOpen(!searchOpen)} className="p-1.5 text-zinc-400" data-testid="mobile-search-btn"><Search className="w-5 h-5" /></button>
        <button onClick={() => setMenuOpen(true)} className="p-1.5 text-zinc-400" data-testid="mobile-menu-btn"><Menu className="w-5 h-5" /></button>
      </div>

      {/* Channel selector (horizontal scroll) */}
      {activeView === "chat" && (
        <div className="flex-shrink-0 border-b border-zinc-800/40 overflow-x-auto">
          <div className="flex gap-1 px-3 py-2">
            {channels.map(ch => (
              <button key={ch.channel_id} onClick={() => setSelectedChannel(ch)}
                className={`flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                  selectedChannel?.channel_id === ch.channel_id ? "bg-zinc-800 text-zinc-100" : "text-zinc-500"
                }`} data-testid={`mobile-channel-${ch.channel_id}`}>
                <Hash className="w-3 h-3 inline mr-1" />{ch.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Agent bar for chat */}
      {activeView === "chat" && selectedChannel && (
        <div className="flex-shrink-0 border-b border-zinc-800/30 overflow-x-auto">
          <div className="flex gap-1.5 px-3 py-1.5">
            {(selectedChannel.ai_agents || []).map(agentKey => {
              const isDisabled = disabledAgents.includes(agentKey);
              return (
                <button key={agentKey} onClick={() => toggleAgent(agentKey)}
                  className={`flex-shrink-0 flex items-center gap-1 px-2 py-1 rounded-full text-[10px] font-medium transition-all ${
                    isDisabled ? "bg-red-500/5 border border-red-500/20 text-zinc-600" : "bg-zinc-800/60 text-zinc-400"
                  }`} data-testid={`mobile-agent-${agentKey}`}>
                  <div className="w-2 h-2 rounded-full" style={{ backgroundColor: isDisabled ? "#71717a" : AI_COLORS[agentKey] }} />
                  <span className={isDisabled ? "line-through" : ""}>{AI_NAMES[agentKey] || agentKey}</span>
                  <Power className={`w-2.5 h-2.5 ${isDisabled ? "text-red-400" : "text-zinc-600"}`} />
                </button>
              );
            })}
            {isCollaborating && <span className="flex items-center gap-1 text-[10px] text-amber-400"><Loader2 className="w-3 h-3 animate-spin" />Thinking</span>}
          </div>
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 min-h-0 flex flex-col" onTouchStart={handleTouchStart} onTouchEnd={handleTouchEnd}>
        {activeView === "chat" && selectedChannel ? (
          <>
            {/* Messages */}
            <ScrollArea className="flex-1">
              <div className="px-3 py-3 space-y-2">
                {messages.length === 0 ? (
                  <div className="text-center py-12">
                    <Hash className="w-8 h-8 text-zinc-800 mx-auto mb-2" />
                    <p className="text-sm text-zinc-500">Send a message to start</p>
                  </div>
                ) : messages.filter((m, i, arr) => {
                  if (m.sender_type === "system" && m.content?.includes("requires an API key")) {
                    return !arr.slice(0, i).some(p => p.sender_type === "system" && p.content?.includes("requires an API key"));
                  }
                  return true;
                }).map(msg => (
                  <div key={msg.message_id} className={`flex ${msg.sender_type === "human" ? "justify-end" : "justify-start"}`} data-testid={`mobile-msg-${msg.message_id}`}>
                    <div className={`max-w-[85%] rounded-2xl px-3 py-2 ${
                      msg.sender_type === "human" ? "bg-emerald-500/20 text-zinc-200" :
                      msg.sender_type === "system" ? "bg-zinc-800/30 text-zinc-500 italic text-xs" :
                      "bg-zinc-800/60 text-zinc-300"
                    }`}>
                      {msg.sender_type === "ai" && (
                        <div className="flex items-center gap-1.5 mb-1">
                          <div className="w-4 h-4 rounded-full flex items-center justify-center text-[8px] font-bold text-white" style={{ backgroundColor: AI_COLORS[msg.ai_model] || "#666" }}>
                            {(AI_NAMES[msg.ai_model] || "?")[0]}
                          </div>
                          <span className="text-[10px] font-semibold text-zinc-400">{msg.sender_name}</span>
                        </div>
                      )}
                      <p className="text-sm whitespace-pre-wrap break-words">{msg.content}</p>
                      {msg.file_attachment && (
                        <div className="mt-1 flex items-center gap-1.5 text-[10px] px-2 py-1 rounded bg-zinc-700/50">
                          <span className="text-zinc-400">{msg.file_attachment.name}</span>
                          {msg.file_attachment.has_extracted_text && <span className="text-emerald-400/70">AI readable</span>}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
            {/* Input */}
            <div className="flex-shrink-0 px-3 py-2 border-t border-zinc-800/60" style={{ paddingBottom: "env(safe-area-inset-bottom, 8px)" }}>
              {/* Pending file */}
              {pendingFile && (
                <div className="flex items-center gap-2 px-3 py-1.5 mb-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                  <span className="text-[11px] text-emerald-400 truncate flex-1">{pendingFile.name}</span>
                  <button onClick={() => setPendingFile(null)} className="text-zinc-500 text-xs">✕</button>
                </div>
              )}
              <div className="flex items-end gap-2">
                {/* File attach button */}
                <button
                  onClick={() => {
                    const inp = document.createElement("input");
                    inp.type = "file";
                    inp.onchange = async (ev) => {
                      const f = ev.target.files[0];
                      if (f) {
                        if (f.size > 25*1024*1024) { toast.error("File too large"); return; }
                        setPendingFile(f);
                      }
                    };
                    inp.click();
                  }}
                  className={`p-2 rounded-xl ${pendingFile ? "text-emerald-400 bg-emerald-500/10" : "text-zinc-600"}`}
                  data-testid="mobile-attach-btn"
                >
                  <Paperclip className="w-4 h-4" />
                </button>
                <textarea value={input} onChange={(e) => setInput(e.target.value)}
                  placeholder="Message..." rows={1}
                  className="flex-1 bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2.5 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-700 resize-none"
                  style={{ maxHeight: 100 }}
                  onInput={(e) => { e.target.style.height = "auto"; e.target.style.height = Math.min(e.target.scrollHeight, 100) + "px"; }}
                  data-testid="mobile-message-input"
                />
                <Button onClick={sendMessage} disabled={(!input.trim() && !pendingFile) || sending}
                  className="bg-emerald-500 hover:bg-emerald-400 text-white rounded-xl h-10 w-10 p-0 flex-shrink-0"
                  data-testid="mobile-send-btn">
                  {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                </Button>
              </div>
            </div>
          </>
        ) : activeView === "chat" && !selectedChannel ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center px-6">
              <Hash className="w-10 h-10 text-zinc-800 mx-auto mb-3" />
              <p className="text-sm text-zinc-500">No channels yet</p>
              <p className="text-xs text-zinc-600 mt-1">Create a channel from the menu</p>
            </div>
          </div>
        ) : activeView === "projects" ? (
          <ScrollArea className="flex-1 px-3 py-3">
            <div className="space-y-3">
              {projects.length === 0 ? (
                <div className="text-center py-12"><FolderKanban className="w-10 h-10 text-zinc-800 mx-auto mb-3" /><p className="text-sm text-zinc-500">No tasks yet</p></div>
              ) : projects.map(group => (
                <div key={group.project_id || "_ws"} className="rounded-xl border border-zinc-800/60 overflow-hidden">
                  <div className="px-3 py-2 bg-zinc-900/60 flex items-center gap-2">
                    <FolderKanban className="w-4 h-4 text-purple-400" />
                    <span className="text-xs font-semibold text-zinc-200">{group.project_name}</span>
                    <Badge className="bg-zinc-800 text-zinc-500 text-[9px] ml-auto">{(group.tasks || []).length}</Badge>
                  </div>
                  <div className="divide-y divide-zinc-800/30">
                    {(group.tasks || []).map(task => {
                      const s = task.status || "todo";
                      return (
                        <div key={task.task_id} className="px-3 py-2.5 flex items-center gap-2" data-testid={`mobile-task-${task.task_id}`}>
                          {s === "done" ? <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" /> :
                           s === "in_progress" ? <Clock className="w-4 h-4 text-amber-400 flex-shrink-0" /> :
                           <Circle className="w-4 h-4 text-zinc-500 flex-shrink-0" />}
                          <div className="flex-1 min-w-0">
                            <span className={`text-sm ${s === "done" ? "text-zinc-500 line-through" : "text-zinc-200"}`}>{task.title}</span>
                            {(task.assignee_name || task.assigned_to) && (
                              <p className="text-[10px] text-zinc-600 flex items-center gap-1 mt-0.5">
                                <Bot className="w-3 h-3" />{task.assignee_name || task.assigned_to}
                              </p>
                            )}
                          </div>
                          <Badge className={`text-[8px] ${
                            task.priority === "critical" ? "bg-red-500/15 text-red-400" :
                            task.priority === "high" ? "bg-amber-500/15 text-amber-400" :
                            "bg-zinc-800 text-zinc-500"
                          }`}>{task.priority || "medium"}</Badge>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        ) : activeView === "code" ? (
          <MobileCodeViewer workspaceId={workspaceId} />
        ) : activeView === "docs" ? (
          <MobileWiki workspaceId={workspaceId} />
        ) : activeView === "settings" ? (
          <MobileSettings workspaceId={workspaceId} navigate={navigate} />
        ) : null}
      </div>

      {/* Bottom Navigation */}
      <div className="flex-shrink-0 border-t border-zinc-800/60 bg-zinc-950" style={{ paddingBottom: "env(safe-area-inset-bottom)" }}>
        <div className="flex items-center justify-around py-1.5">
          {[
            { key: "chat", icon: MessageSquare, label: "Chat" },
            { key: "projects", icon: FolderKanban, label: "Tasks" },
            { key: "docs", icon: BookOpen, label: "Docs" },
            { key: "settings", icon: Settings, label: "Settings" },
          ].map(tab => {
            const Icon = tab.icon;
            const active = activeView === tab.key;
            return (
              <button key={tab.key} onClick={() => { setActiveView(tab.key); haptic(); }}
                className={`flex flex-col items-center gap-0.5 px-3 py-1 rounded-lg transition-colors ${active ? "text-emerald-400" : "text-zinc-600"}`}
                data-testid={`mobile-tab-${tab.key}`}>
                <Icon className="w-5 h-5" />
                <span className="text-[9px] font-medium">{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Side Menu */}
      {menuOpen && (
        <div className="fixed inset-0 z-50 flex" data-testid="mobile-side-menu">
          <div className="absolute inset-0 bg-black/60" onClick={() => setMenuOpen(false)} />
          <div className="relative w-72 bg-zinc-900 h-full flex flex-col border-r border-zinc-800 animate-in slide-in-from-left">
            <div className="px-4 py-3 border-b border-zinc-800 flex items-center justify-between">
              <span className="text-sm font-semibold text-zinc-200">{workspace?.name}</span>
              <button onClick={() => setMenuOpen(false)} className="p-1 text-zinc-400"><X className="w-5 h-5" /></button>
            </div>
            <ScrollArea className="flex-1 px-3 py-3">
              <div className="flex items-center justify-between mb-2 px-2">
                <p className="text-[10px] text-zinc-600 uppercase tracking-wider font-semibold">Channels</p>
                <button onClick={() => { setMenuOpen(false); setCreateChannelOpen(true); }} className="p-1 text-zinc-500" data-testid="mobile-create-channel-btn"><Plus className="w-4 h-4" /></button>
              </div>
              {channels.map(ch => (
                <div key={ch.channel_id} className="flex items-center gap-1 mb-0.5">
                  <button
                    onClick={() => { setSelectedChannel(ch); setActiveView("chat"); setMenuOpen(false); }}
                    className={`flex-1 text-left px-3 py-2 rounded-lg text-sm ${selectedChannel?.channel_id === ch.channel_id ? "bg-zinc-800 text-zinc-100" : "text-zinc-400"}`}
                    data-testid={`mobile-drawer-channel-${ch.channel_id}`}>
                    <Hash className="w-3.5 h-3.5 inline mr-1.5" />{ch.name}
                  </button>
                  <button
                    onClick={async (e) => {
                      e.stopPropagation();
                      const ok = await confirmAction("Delete Channel", `Delete "${ch.name}"? All messages will be lost.`); if (!ok) return;
                      try {
                        await api.delete(`/channels/${ch.channel_id}`);
                        toast.success("Channel deleted");
                        setChannels(prev => prev.filter(c => c.channel_id !== ch.channel_id));
                        if (selectedChannel?.channel_id === ch.channel_id) setSelectedChannel(null);
                      } catch (err) { toast.error("Failed to delete channel"); }
                    }}
                    className="p-1.5 rounded text-zinc-600 hover:text-red-400 transition-colors"
                    data-testid={`mobile-delete-channel-${ch.channel_id}`}>
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
              <div className="border-t border-zinc-800 my-3" />
              <button onClick={() => { setActiveView("projects"); setMenuOpen(false); }} className="w-full text-left px-3 py-2 rounded-lg text-sm text-zinc-400 hover:bg-zinc-800">
                <FolderKanban className="w-3.5 h-3.5 inline mr-1.5" />Tasks & Projects
              </button>
              <button onClick={() => { setActiveView("docs"); setMenuOpen(false); }} className="w-full text-left px-3 py-2 rounded-lg text-sm text-zinc-400 hover:bg-zinc-800">
                <BookOpen className="w-3.5 h-3.5 inline mr-1.5" />Docs
              </button>
            </ScrollArea>
            <div className="px-4 py-3 border-t border-zinc-800 flex items-center gap-2">
              {user?.picture ? <img src={user.picture} alt="" className="w-8 h-8 rounded-full" /> : <div className="w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center text-xs">{user?.name?.[0]}</div>}
              <span className="text-xs text-zinc-400 truncate">{user?.name}</span>
            </div>
          </div>
        </div>
      )}

      {/* Search Overlay */}
      {searchOpen && (
        <div className="fixed inset-0 z-50 bg-zinc-950/95 flex flex-col" style={{ paddingTop: "env(safe-area-inset-top)" }}>
          <div className="flex items-center gap-2 px-3 py-2 border-b border-zinc-800">
            <Search className="w-4 h-4 text-zinc-500 flex-shrink-0" />
            <input type="text" value={searchQuery} onChange={(e) => handleSearch(e.target.value)}
              placeholder="Search messages, tasks, docs, code..."
              className="flex-1 bg-transparent text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none" autoFocus data-testid="mobile-search-input" />
            <button onClick={() => { setSearchOpen(false); setSearchQuery(""); setSearchResults([]); }} className="p-1 text-zinc-400"><X className="w-5 h-5" /></button>
          </div>
          <ScrollArea className="flex-1 px-3 py-2">
            {searchResults.length === 0 && searchQuery && <p className="text-center text-sm text-zinc-600 py-8">No results</p>}
            {searchResults.map((r, i) => (
              <button key={`${r.type}-${r.id}-${i}`} onClick={() => { setSearchOpen(false); setSearchQuery(""); }}
                className="w-full text-left px-3 py-2.5 rounded-lg hover:bg-zinc-800/40 mb-0.5">
                <div className="flex items-center gap-2">
                  <span className={`text-[9px] px-1.5 py-0.5 rounded font-mono uppercase ${r.type === "message" ? "bg-blue-500/15 text-blue-400" : r.type === "task" ? "bg-amber-500/15 text-amber-400" : r.type === "wiki" ? "bg-purple-500/15 text-purple-400" : "bg-emerald-500/15 text-emerald-400"}`}>{r.type}</span>
                  <span className="text-sm text-zinc-200 truncate">{r.title}</span>
                </div>
                {r.snippet && <p className="text-xs text-zinc-500 mt-0.5 line-clamp-1">{r.snippet}</p>}
              </button>
            ))}
          </ScrollArea>
        </div>
      )}

      {/* Create Channel Dialog */}
      <Dialog open={createChannelOpen} onOpenChange={setCreateChannelOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 mx-4">
          <DialogHeader><DialogTitle className="text-zinc-100">New Channel</DialogTitle><DialogDescription className="sr-only">Create channel</DialogDescription></DialogHeader>
          <div className="space-y-3 mt-2">
            <Input value={newChannelName} onChange={(e) => setNewChannelName(e.target.value)} placeholder="Channel name"
              className="bg-zinc-950 border-zinc-800" autoFocus data-testid="mobile-channel-name" />
            <div>
              <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-2">AI Agents</p>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(AI_NAMES).map(([key, name]) => (
                  <button key={key} onClick={() => setSelectedAgents(prev => prev.includes(key) ? prev.filter(a => a !== key) : [...prev, key])}
                    className={`px-2.5 py-1.5 rounded-lg text-xs flex items-center gap-1 ${selectedAgents.includes(key) ? "bg-zinc-700 text-zinc-200" : "bg-zinc-800/40 text-zinc-500"}`}
                    data-testid={`mobile-agent-select-${key}`}>
                    <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: AI_COLORS[key] }} />
                    {name}
                  </button>
                ))}
              </div>
            </div>
            <Button onClick={createChannel} disabled={!newChannelName.trim() || selectedAgents.length === 0}
              className="w-full bg-zinc-100 text-zinc-900" data-testid="mobile-create-channel-submit">Create Channel</Button>
          </div>
        </DialogContent>
      </Dialog>
      <ConfirmDlg />
    </div>
  );
}

// ===== Mobile Settings =====

// ===== Mobile Code Viewer =====
function MobileCodeViewer({ workspaceId }) {
  const [files, setFiles] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/workspaces/${workspaceId}/code-repo/tree`)
      .then(r => { setFiles(r.data?.files || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, [workspaceId]);

  const selectFile = async (fileId) => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/code-repo/files/${fileId}`);
      setSelectedFile(res.data);
    } catch (err) { toast.error("Failed to load file"); }
  };

  if (selectedFile) {
    return (
      <div className="flex-1 flex flex-col">
        <div className="flex-shrink-0 px-3 py-2 border-b border-zinc-800/40 flex items-center gap-2">
          <button onClick={() => setSelectedFile(null)} className="p-1 text-zinc-400"><ArrowLeft className="w-4 h-4" /></button>
          <span className="text-xs font-mono text-zinc-300 truncate">{selectedFile.path}</span>
          <span className="text-[9px] text-zinc-600 ml-auto">v{selectedFile.version} {selectedFile.language}</span>
        </div>
        <ScrollArea className="flex-1 px-3 py-2">
          <pre className="text-xs text-zinc-300 font-mono whitespace-pre-wrap bg-zinc-900/50 rounded-lg p-3 border border-zinc-800/40">
            {selectedFile.content || "Empty file"}
          </pre>
        </ScrollArea>
      </div>
    );
  }

  return (
    <ScrollArea className="flex-1 px-3 py-3">
      {loading ? (
        <div className="flex justify-center py-8"><Loader2 className="w-5 h-5 text-zinc-500 animate-spin" /></div>
      ) : files.length === 0 ? (
        <div className="text-center py-12"><FileCode className="w-10 h-10 text-zinc-800 mx-auto mb-3" /><p className="text-sm text-zinc-500">No files in repo</p></div>
      ) : (
        <div className="space-y-1">
          {files.filter(f => !f.is_folder).map(f => (
            <button key={f.file_id} onClick={() => selectFile(f.file_id)}
              className="w-full text-left px-3 py-2.5 rounded-xl bg-zinc-900/40 border border-zinc-800/40 active:scale-[0.98] transition-transform flex items-center gap-2">
              <FileCode className="w-4 h-4 text-emerald-400/60 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-zinc-200 truncate">{f.path}</p>
                <p className="text-[10px] text-zinc-600">{f.language} • {f.size}B</p>
              </div>
              <ChevronRight className="w-4 h-4 text-zinc-700" />
            </button>
          ))}
        </div>
      )}
    </ScrollArea>
  );
}


function MobileSettings({ workspaceId, navigate }) {
  const [settings, setSettings] = useState(null);
  const [maxRounds, setMaxRounds] = useState(10);
  const [theme, setTheme] = useState(() => localStorage.getItem("nexus_theme") || "dark");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (workspaceId) {
      api.get(`/workspaces/${workspaceId}/settings`).then(r => {
        setSettings(r.data);
        setMaxRounds(r.data?.auto_collab_max_rounds || 10);
      }).catch(() => {});
    }
  }, [workspaceId]);

  const saveSettings = async () => {
    setSaving(true);
    try {
      await api.put(`/workspaces/${workspaceId}/settings`, { auto_collab_max_rounds: maxRounds });
      toast.success(`Settings saved`);
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
    setSaving(false);
  };

  const applyTheme = (t) => {
    setTheme(t);
    localStorage.setItem("nexus_theme", t);
    api.put("/user/preferences", { theme: t }).catch(() => {});
    toast.success(`Theme: ${t}`);
  };

  return (
    <ScrollArea className="flex-1 px-4 py-4">
      <div className="space-y-4" data-testid="mobile-settings">
        {/* Theme */}
        <div className="p-4 rounded-xl bg-zinc-900/40 border border-zinc-800/40">
          <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">Theme</p>
          <div className="flex gap-2">
            {["dark", "light", "system"].map(t => (
              <button key={t} onClick={() => applyTheme(t)}
                className={`flex-1 py-2 rounded-lg text-xs font-medium ${theme === t ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30" : "bg-zinc-800/40 text-zinc-500 border border-zinc-800"}`}
                data-testid={`mobile-theme-${t}`}>
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
        </div>
        {/* Auto-collab rounds */}
        <div className="p-4 rounded-xl bg-zinc-900/40 border border-zinc-800/40">
          <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">Auto-Collab Rounds</p>
          <div className="flex items-center gap-3">
            <input type="range" min={5} max={50} value={maxRounds} onChange={(e) => setMaxRounds(Number(e.target.value))}
              className="flex-1 accent-emerald-500" data-testid="mobile-rounds-slider" />
            <span className="text-lg font-bold text-zinc-200 w-8 text-center">{maxRounds}</span>
          </div>
          <Button onClick={saveSettings} disabled={saving} size="sm" className="mt-3 w-full bg-zinc-100 text-zinc-900" data-testid="mobile-save-settings">
            {saving ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : null}Save
          </Button>
        </div>
        {/* Navigation links */}
        <div className="p-4 rounded-xl bg-zinc-900/40 border border-zinc-800/40 space-y-2">
          <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">Account</p>
          <button onClick={() => navigate("/settings")} className="w-full text-left px-3 py-2.5 rounded-lg bg-zinc-800/30 text-sm text-zinc-300 active:scale-[0.98]">AI Keys & Settings</button>
          <button onClick={() => navigate("/billing")} className="w-full text-left px-3 py-2.5 rounded-lg bg-zinc-800/30 text-sm text-zinc-300 active:scale-[0.98]">Billing & Plans</button>
        </div>
      </div>
    </ScrollArea>
  );
}


function MobileWiki({ workspaceId }) {
  const [pages, setPages] = useState([]);
  const [selectedPage, setSelectedPage] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/workspaces/${workspaceId}/wiki`)
      .then(r => { setPages(r.data.pages || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, [workspaceId]);

  const selectPage = async (pageId) => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/wiki/${pageId}`);
      setSelectedPage(res.data);
    } catch (err) { toast.error("Failed to load"); }
  };

  if (selectedPage) {
    return (
      <div className="flex-1 flex flex-col">
        <div className="flex-shrink-0 px-3 py-2 border-b border-zinc-800/40 flex items-center gap-2">
          <button onClick={() => setSelectedPage(null)} className="p-1 text-zinc-400"><ArrowLeft className="w-4 h-4" /></button>
          <span className="text-sm font-semibold text-zinc-200 truncate">{selectedPage.title}</span>
          <span className="text-[10px] text-zinc-600 ml-auto">v{selectedPage.version}</span>
        </div>
        <ScrollArea className="flex-1 px-4 py-4">
          <div className="text-sm text-zinc-300 leading-relaxed whitespace-pre-wrap">{selectedPage.content || "Empty page"}</div>
        </ScrollArea>
      </div>
    );
  }

  return (
    <ScrollArea className="flex-1 px-3 py-3">
      {loading ? (
        <div className="flex justify-center py-8"><Loader2 className="w-5 h-5 text-zinc-500 animate-spin" /></div>
      ) : pages.length === 0 ? (
        <div className="text-center py-12"><BookOpen className="w-10 h-10 text-zinc-800 mx-auto mb-3" /><p className="text-sm text-zinc-500">No docs yet</p></div>
      ) : (
        <div className="space-y-1">
          {pages.map(p => (
            <button key={p.page_id} onClick={() => selectPage(p.page_id)}
              className="w-full text-left px-3 py-3 rounded-xl bg-zinc-900/40 border border-zinc-800/40 active:scale-[0.98] transition-transform"
              data-testid={`mobile-wiki-${p.page_id}`}>
              <div className="flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-blue-400/60 flex-shrink-0" />
                <span className="text-sm text-zinc-200">{p.title}</span>
                <ChevronRight className="w-4 h-4 text-zinc-700 ml-auto" />
              </div>
            </button>
          ))}
        </div>
      )}
    </ScrollArea>
  );
}

// ===== Mobile Auth =====
export function MobileAuth() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [isRegister, setIsRegister] = useState(false);
  const [name, setName] = useState("");

  const handleSubmit = async () => {
    if (!email || !password) return;
    setLoading(true);
    try {
      if (isRegister) {
        await api.post("/auth/register", { email, password, name: name || email.split("@")[0] });
      } else {
        const res = await api.post("/auth/login", { email, password });
        if (res.data) {
          sessionStorage.setItem("nexus_user", JSON.stringify({ user_id: res.data.user_id, name: res.data.name, platform_role: res.data.platform_role }));
          if (res.data.session_token) sessionStorage.setItem("nexus_session_token", res.data.session_token);
        }
      }
      markRecentAuth();
      navigate("/dashboard");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center px-6" style={{ paddingTop: "env(safe-area-inset-top)", paddingBottom: "env(safe-area-inset-bottom)" }} data-testid="mobile-auth">
      <div className="w-full max-w-sm">
        <div className="flex items-center justify-center gap-2 mb-8">
          <img src="/logo.png" alt="Nexus Cloud" className="w-10 h-10 rounded-xl" />
          <span className="text-xl font-bold text-zinc-100" style={{ fontFamily: "Syne, sans-serif" }}>NEXUS <span className="text-cyan-400">CLOUD</span></span>
        </div>

        <div className="space-y-3">
          {isRegister && <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" className="bg-zinc-900 border-zinc-800 h-12 text-base" />}
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" className="bg-zinc-900 border-zinc-800 h-12 text-base" data-testid="mobile-email" />
          <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" className="bg-zinc-900 border-zinc-800 h-12 text-base"
            onKeyDown={(e) => e.key === "Enter" && handleSubmit()} data-testid="mobile-password" />
          <Button onClick={handleSubmit} disabled={loading} className="w-full bg-emerald-500 hover:bg-emerald-400 text-white h-12 text-base" data-testid="mobile-submit">
            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : isRegister ? "Create Account" : "Sign In"}
          </Button>
        </div>

        <div className="mt-4 text-center">
          <button onClick={() => setIsRegister(!isRegister)} className="text-sm text-zinc-500">{isRegister ? "Already have an account? Sign In" : "Need an account? Sign Up"}</button>
        </div>

        <div className="mt-6 flex items-center gap-3"><div className="flex-1 h-px bg-zinc-800" /><span className="text-xs text-zinc-600">or</span><div className="flex-1 h-px bg-zinc-800" /></div>
        <button onClick={async () => {
          try {
            const res = await api.get("/auth/google/login");
            if (res.data?.url) { window.location.href = res.data.url; return; }
            if (res.data?.use_emergent_bridge) {
              const redirectUrl = window.location.origin + '/dashboard';
              window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
              return;
            }
            toast.error("Google login not available. Use email/password.");
          } catch (err) {
            const redirectUrl = window.location.origin + '/dashboard';
            window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
          }
        }} className="mt-4 w-full flex items-center justify-center gap-2 h-12 rounded-lg border border-zinc-800 text-sm text-zinc-300 bg-zinc-900 active:scale-[0.98] transition-transform" data-testid="mobile-google-btn">
          <svg className="w-5 h-5" viewBox="0 0 24 24"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>
          Continue with Google
        </button>
      </div>
    </div>
  );
}
