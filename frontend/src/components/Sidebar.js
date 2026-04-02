import { useState, useEffect, useRef as useReactRef } from "react";
import { useConfirm } from "@/components/ConfirmDialog";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogTrigger } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Checkbox } from "@/components/ui/checkbox";
import { Hash, Plus, ArrowLeft, LogOut, Zap, CreditCard, Settings, Sparkles, Bot, MoreVertical, Pencil, Trash2, FolderKanban, ChevronDown, ChevronRight, Pin, PanelLeftClose, PanelLeftOpen, LayoutDashboard, KanbanSquare, Hammer, BarChart3, GripVertical, MessageSquare, Dumbbell } from "lucide-react";
import { useLanguage } from "@/contexts/LanguageContext";
import { useModules } from "@/contexts/ModuleContext";
import { useHelper } from "@/contexts/NexusHelperContext";
import { api } from "@/App";
import { toast } from "sonner";

const ALL_AI_AGENTS = [
  { key: "claude", name: "Claude", color: "#D97757" },
  { key: "chatgpt", name: "ChatGPT", color: "#10A37F" },
  { key: "gemini", name: "Gemini", color: "#4285F4" },
  { key: "perplexity", name: "Perplexity", color: "#20B2AA" },
  { key: "mistral", name: "Mistral", color: "#FF7000" },
  { key: "cohere", name: "Cohere", color: "#39594D" },
  { key: "groq", name: "Groq", color: "#F55036" },
  { key: "deepseek", name: "DeepSeek", color: "#4D6BFE" },
  { key: "grok", name: "Grok", color: "#F5F5F5" },
  { key: "mercury", name: "Mercury 2", color: "#00D4FF" },
  { key: "pi", name: "Pi", color: "#FF6B35" },
  { key: "manus", name: "Manus", color: "#6C5CE7" },
  { key: "qwen", name: "Qwen", color: "#615EFF" },
  { key: "kimi", name: "Kimi", color: "#000000" },
  { key: "llama", name: "Llama", color: "#0467DF" },
  { key: "glm", name: "GLM", color: "#3D5AFE" },
  { key: "cursor", name: "Cursor", color: "#00E5A0" },
  { key: "notebooklm", name: "NotebookLM", color: "#FBBC04" },
  { key: "copilot", name: "GitHub Copilot", color: "#171515" },
];

export const Sidebar = ({ workspace, channels, selectedChannel, onSelectChannel, onCreateChannel, onRefreshChannels, user, activeTab, onTabChange, projectRefreshKey, collapsed, onToggleCollapse, navMenus, openMenu, onMenuToggle, pinnedTabs, getTabLabel, onReorderPinned }) => {
  const navigate = useNavigate();
  const { confirm: confirmAction, ConfirmDialog: ConfirmDlg } = useConfirm();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [channelToEdit, setChannelToEdit] = useState(null);
  const [editChannelName, setEditChannelName] = useState("");
  const [editChannelAgents, setEditChannelAgents] = useState([]);
  const [channelName, setChannelName] = useState("");
  const { t } = useLanguage();
  const { enabledAIModels } = useModules();
  const helper = useHelper();
  // Filter agents by module config
  const AI_AGENTS = ALL_AI_AGENTS.filter(a => enabledAIModels.length === 0 || enabledAIModels.includes(a.key));
  const [channelDesc, setChannelDesc] = useState("");
  const [selectedAgents, setSelectedAgents] = useState(["claude", "chatgpt"]);
  const [nexusAgents, setNexusAgents] = useState([]);
  const [projects, setProjects] = useState([]);
  const [projectsExpanded, setProjectsExpanded] = useState(() => {
    return localStorage.getItem("nexus_projects_pinned") === "true";
  });
  const [projectsPinned, setProjectsPinned] = useState(() => {
    try { return localStorage.getItem("nexus_projects_pinned") === "true"; } catch (err) { return false; }
  });

  // Fetch custom Nexus Agents when workspace changes
  useEffect(() => {
    if (workspace?.workspace_id) {
      fetchNexusAgents();
    }
  }, [workspace?.workspace_id]);

  const fetchNexusAgents = async () => {
    try {
      const res = await api.get(`/workspaces/${workspace.workspace_id}/agents`);
      setNexusAgents(res.data.agents || []);
    } catch (err) { handleSilent(err, "Sidebar:op1"); }
  };

  const fetchProjects = async () => {
    try {
      const res = await api.get(`/workspaces/${workspace.workspace_id}/projects`);
      setProjects(res.data || []);
    } catch (err) { handleSilent(err, "Sidebar:op2"); }
  };

  useEffect(() => {
    if (workspace?.workspace_id) fetchProjects();
  }, [workspace?.workspace_id, projectRefreshKey]);

  const handleCreate = (e) => {
    if (e && e.preventDefault) e.preventDefault();
    if (!channelName.trim()) return;
    onCreateChannel(channelName, channelDesc, selectedAgents);
    setDialogOpen(false);
    setChannelName("");
    setChannelDesc("");
    setSelectedAgents(["claude", "chatgpt"]);
  };

  const toggleAgent = (key) => {
    setSelectedAgents((prev) =>
      prev.includes(key) ? prev.filter((a) => a !== key) : [...prev, key]
    );
  };

  const openEditChannelDialog = (channel, e) => {
    e.stopPropagation();
    setChannelToEdit(channel);
    setEditChannelName(channel.name);
    setEditChannelAgents(channel.ai_agents || []);
    setEditDialogOpen(true);
  };

  const updateChannel = async () => {
    if (!channelToEdit || !editChannelName.trim()) return;
    try {
      await api.put(`/channels/${channelToEdit.channel_id}`, {
        name: editChannelName,
        ai_agents: editChannelAgents,
      });
      setEditDialogOpen(false);
      setChannelToEdit(null);
      toast.success("Channel updated");
      if (onRefreshChannels) onRefreshChannels();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to rename channel");
    }
  };

  const deleteChannel = async (channel, e) => {
    e.stopPropagation();
    const _ok = await confirmAction("Delete Channel", `Delete "${channel.name}"? All messages will be permanently lost.`); if (!_ok) return;
    try {
      await api.delete(`/channels/${channel.channel_id}`);
      toast.success("Channel deleted");
      if (onRefreshChannels) onRefreshChannels();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to delete channel");
    }
  };

  const handleLogout = async () => {
    try {
      await api.post("/auth/logout");
    } catch (err) { handleSilent(err, "Sidebar:op3"); }
    sessionStorage.removeItem("nexus_user");
    navigate("/");
  };

  return (
    <nav className={`${collapsed ? "w-16" : "w-64"} flex-shrink-0 border-r border-zinc-800 bg-zinc-900/95 backdrop-blur flex flex-col h-screen transition-all duration-200`} data-testid="sidebar" role="navigation" aria-label="Workspace sidebar">
      {/* Collapse toggle + Workspace header */}
      <div className="p-2 border-b border-zinc-800/60">
        <div className="flex items-center justify-between mb-2">
          {!collapsed && (
            <button
              onClick={() => navigate("/dashboard")}
              className="flex items-center gap-1.5 text-zinc-400 hover:text-zinc-100 transition-colors text-xs px-2 py-1 rounded-md hover:bg-zinc-800/60"
              data-testid="back-to-dashboard" aria-label="Back to dashboard"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span className="font-medium">Dashboard</span>
            </button>
          )}
          <button
            onClick={onToggleCollapse}
            className="p-1.5 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/60 transition-colors"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            data-testid="sidebar-toggle"
          >
            {collapsed ? <PanelLeftOpen className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}
          </button>
        </div>
        {collapsed ? (
          <button onClick={() => navigate("/dashboard")} className="w-full flex justify-center py-1" title={workspace?.name} aria-label="Back to dashboard">
            <img src="/logo.png" alt="Nexus" className="w-7 h-7 rounded-md" />
          </button>
        ) : (
          <div className="flex items-center gap-2 px-2" title={workspace?.name}>
            <img src="/logo.png" alt="Nexus Cloud" className="w-7 h-7 rounded-md flex-shrink-0" />
            <div className="min-w-0">
              <span className="font-semibold text-sm text-zinc-200 truncate block" data-testid="workspace-name">{workspace?.name}</span>
              <span className="text-[9px] text-zinc-600">{workspace?.type === "org" ? workspace?.org_name : "Personal workspace"}</span>
            </div>
          </div>
        )}
      </div>

      {/* Pinned shortcuts with drag-to-reorder */}
      {pinnedTabs && pinnedTabs.length > 0 && (
        <div className={`${collapsed ? "px-1 py-1" : "px-2 py-1"} border-b border-zinc-800/60`} data-testid="sidebar-pinned-tabs">
          {!collapsed && <span className="text-[10px] uppercase tracking-wider text-zinc-600 font-semibold px-1 mb-0.5 block">Pinned</span>}
          {pinnedTabs.map((key, idx) => (
            <div
              key={key}
              draggable={!collapsed}
              onDragStart={(e) => { e.dataTransfer.setData("pin-idx", String(idx)); e.dataTransfer.effectAllowed = "move"; }}
              onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; }}
              onDrop={(e) => { e.preventDefault(); const from = parseInt(e.dataTransfer.getData("pin-idx"), 10); if (!isNaN(from) && from !== idx && onReorderPinned) onReorderPinned(from, idx); }}
              className="group"
            >
              <button
                onClick={() => onTabChange && onTabChange(key)}
                className={`w-full flex items-center ${collapsed ? "justify-center px-1 py-1" : "gap-1.5 px-2 py-1"} rounded-md text-xs transition-colors ${
                  activeTab === key
                    ? "text-cyan-400 bg-cyan-400/10 font-medium"
                    : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50"
                }`}
                title={collapsed ? (getTabLabel ? getTabLabel(key) : key) : undefined}
                data-testid={`pinned-${key}`}
              >
                {!collapsed && <GripVertical className="w-3 h-3 flex-shrink-0 opacity-0 group-hover:opacity-50 cursor-grab" />}
                <Pin className="w-3 h-3 flex-shrink-0" />
                {!collapsed && <span className="truncate">{getTabLabel ? getTabLabel(key) : key}</span>}
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Navigation module groups */}
      {navMenus && navMenus.length > 0 && (
        <div className={`${collapsed ? "px-1 py-1.5" : "px-2 py-1.5"} border-b border-zinc-800/60 space-y-0.5`} data-testid="sidebar-nav-menus">
          {navMenus.map((menu) => {
            const Icon = { LayoutDashboard, KanbanSquare, Bot, Hammer, BarChart3 }[menu.icon];
            const isActiveGroup = menu.items.some(i => i.key === activeTab);
            const isOpen = openMenu === menu.id;
            return (
              <button
                key={menu.id}
                onClick={() => onMenuToggle && onMenuToggle(menu.id)}
                className={`w-full flex items-center ${collapsed ? "justify-center px-1 py-1.5" : "gap-2 px-2.5 py-1.5"} rounded-md text-xs font-medium transition-all duration-150 ${
                  isOpen
                    ? "text-cyan-400 bg-cyan-400/10"
                    : isActiveGroup
                    ? "text-cyan-400/80 bg-cyan-400/5"
                    : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50"
                }`}
                title={collapsed ? menu.label : undefined}
                aria-label={menu.label}
                aria-expanded={isOpen}
                data-testid={`nav-menu-${menu.id}`}
              >
                {Icon && <Icon className="w-4 h-4 flex-shrink-0" />}
                {!collapsed && (
                  <>
                    <span className="flex-1 text-left">{menu.label}</span>
                    <ChevronRight className={`w-3 h-3 transition-transform duration-150 ${isOpen ? "rotate-90" : ""}`} />
                  </>
                )}
              </button>
            );
          })}
        </div>
      )}

      {/* Channels */}
      <div className="flex-1 overflow-hidden flex flex-col">
        <div className={`${collapsed ? "px-2 py-2 justify-center" : "px-4 py-3 justify-between"} flex items-center border-b border-zinc-800/30`}>
          {!collapsed && <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">Channels</span>}
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <button
                className="w-6 h-6 rounded flex items-center justify-center text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
                data-testid="create-channel-btn"
                title="New Channel"
                  aria-label="Create new channel"
              >
                <Plus className="w-4 h-4" />
              </button>
            </DialogTrigger>
            <DialogContent className="bg-zinc-900 border-zinc-800">
              <DialogHeader>
                <DialogTitle className="text-zinc-100" style={{ fontFamily: 'Syne, sans-serif' }}>New Channel</DialogTitle>
                <DialogDescription className="text-zinc-500 text-sm">Create a channel and select AI agents to collaborate with.</DialogDescription>
              </DialogHeader>
              <div className="space-y-4 mt-2">
                <Input
                  placeholder={t("workspace.channelName")}
                  value={channelName}
                  onChange={(e) => setChannelName(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && channelName.trim() && selectedAgents.length > 0) handleCreate(e); }}
                  className="bg-zinc-950 border-zinc-800 placeholder:text-zinc-600"
                  data-testid="channel-name-input"
                  autoFocus
                />
                <Input
                  placeholder="Description (optional)"
                  value={channelDesc}
                  onChange={(e) => setChannelDesc(e.target.value)}
                  className="bg-zinc-950 border-zinc-800 placeholder:text-zinc-600"
                  data-testid="channel-desc-input"
                />
                <div>
                  <label className="text-xs font-mono uppercase tracking-wider text-zinc-500 mb-2 block">
                    AI Agents
                  </label>
                  <div className="max-h-60 overflow-y-auto space-y-1 pr-1">
                    {/* Custom Nexus Agents */}
                    {nexusAgents.length > 0 && (
                      <>
                        <p className="text-[10px] text-amber-400 uppercase tracking-wider mb-1 mt-2 flex items-center gap-1">
                          <Sparkles className="w-3 h-3" /> Your Nexus Agents
                        </p>
                        {nexusAgents.map((agent) => (
                          <label
                            key={agent.agent_id}
                            className="flex items-center gap-3 p-2 rounded-lg hover:bg-zinc-800/50 cursor-pointer transition-colors"
                          >
                            <Checkbox
                              checked={selectedAgents.includes(agent.agent_id)}
                              onCheckedChange={() => toggleAgent(agent.agent_id)}
                              data-testid={`agent-checkbox-${agent.agent_id}`}
                            />
                            <div
                              className="w-5 h-5 rounded-lg flex items-center justify-center text-[9px] font-bold text-white"
                              style={{ backgroundColor: agent.color }}
                            >
                              {agent.avatar}
                            </div>
                            <span className="text-sm text-zinc-300">{agent.name}</span>
                          </label>
                        ))}
                        <div className="border-t border-zinc-800 my-2" />
                      </>
                    )}
                    
                    {/* Built-in AI Models */}
                    <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Built-in Models</p>
                    {AI_AGENTS.map((agent) => (
                      <label
                        key={agent.key}
                        className="flex items-center gap-3 p-2 rounded-lg hover:bg-zinc-800/50 cursor-pointer transition-colors"
                      >
                        <Checkbox
                          checked={selectedAgents.includes(agent.key)}
                          onCheckedChange={() => toggleAgent(agent.key)}
                          data-testid={`agent-checkbox-${agent.key}`}
                        />
                        <div
                          className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold"
                          style={{ backgroundColor: agent.color, color: ['#F5F5F5', '#FF7000', '#F55036'].includes(agent.color) ? '#09090b' : '#fff' }}
                        >
                          {agent.name[0]}
                        </div>
                        <span className="text-sm text-zinc-300">{agent.name}</span>
                      </label>
                    ))}
                  </div>
                </div>
                <Button
                  type="button"
                  onClick={() => {
                    if (!channelName.trim()) { toast.error("Channel name is required"); return; }
                    if (selectedAgents.length === 0) { toast.error("Select at least one AI agent"); return; }
                    handleCreate();
                  }}
                  disabled={false}
                  className="w-full bg-zinc-100 text-zinc-900 hover:bg-zinc-200 font-medium"
                  data-testid="channel-submit-btn"
                >
                  Create Channel
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        <ScrollArea className="flex-1 px-2">
          {channels.length === 0 ? (
            <div className="px-2 py-6 text-center">
              <p className="text-xs text-zinc-600">No channels yet</p>
            </div>
          ) : (
            <div className="space-y-0.5">
              {channels.map((ch) => (
                <div
                  key={ch.channel_id}
                  className={`group flex items-center gap-1 rounded-lg transition-colors ${
                    selectedChannel?.channel_id === ch.channel_id
                      ? "bg-zinc-800"
                      : "hover:bg-zinc-800/40"
                  }`}
                >
                  <button
                    onClick={() => onSelectChannel(ch)}
                    className={`flex-1 flex items-center ${collapsed ? "justify-center px-2 py-2" : "gap-2 px-3 py-2"} text-left text-sm ${
                      selectedChannel?.channel_id === ch.channel_id
                        ? "text-zinc-100"
                        : "text-zinc-400 hover:text-zinc-200"
                    }`}
                    data-testid={`channel-item-${ch.channel_id}`} aria-label={`Open channel ${ch.name}`}
                    title={collapsed ? ch.name : undefined}
                  >
                    <Hash className="w-3.5 h-3.5 flex-shrink-0" />
                    {!collapsed && <span className="truncate">{ch.name}</span>}
                    {!collapsed && ch.is_tpm_channel && <span className="ml-1 text-[8px] px-1 py-0.5 rounded bg-amber-500/15 text-amber-400 font-semibold">TPM</span>}
                  </button>
                  {!collapsed && (
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button
                        aria-label={`Options for ${ch.name}`}
                        className={`p-1 mr-1 rounded transition-colors opacity-0 group-hover:opacity-100 ${
                          selectedChannel?.channel_id === ch.channel_id
                            ? "opacity-100 text-zinc-400 hover:text-zinc-100"
                            : "text-zinc-500 hover:text-zinc-200"
                        }`}
                        onClick={(e) => e.stopPropagation()}
                        data-testid={`channel-menu-${ch.channel_id}`}
                      >
                        <MoreVertical className="w-3.5 h-3.5" />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent className="bg-zinc-900 border-zinc-800" align="end">
                      <DropdownMenuItem
                        onClick={(e) => openEditChannelDialog(ch, e)}
                        className="text-zinc-300 hover:bg-zinc-800 cursor-pointer text-xs"
                      >
                        <Pencil className="w-3.5 h-3.5 mr-2" />
                        Edit Channel
                      </DropdownMenuItem>
                      <DropdownMenuSeparator className="bg-zinc-800" />
                      <DropdownMenuItem
                        onClick={(e) => deleteChannel(ch, e)}
                        className="text-red-400 hover:bg-zinc-800 cursor-pointer text-xs"
                      >
                        <Trash2 className="w-3.5 h-3.5 mr-2" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Projects section in sidebar */}
          <div className="mt-3 pt-3 border-t border-zinc-800/40">
            {collapsed ? (
              <button onClick={() => onTabChange("projects")} className="w-full flex justify-center py-2 text-zinc-500 hover:text-zinc-300" title="Projects" aria-label="View projects">
                <FolderKanban className="w-4 h-4" />
              </button>
            ) : (
            <>
            <div className="w-full flex items-center justify-between px-2 py-1 mb-1">
              <button onClick={() => { if (!projectsPinned) setProjectsExpanded(!projectsExpanded); }} className="flex items-center gap-1" aria-label="Toggle projects">
                {projectsExpanded ? <ChevronDown className="w-3 h-3 text-zinc-600" /> : <ChevronRight className="w-3 h-3 text-zinc-600" />}
                <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">Projects</span>
              </button>
              <button onClick={() => { const next = !projectsPinned; setProjectsPinned(next); localStorage.setItem("nexus_projects_pinned", String(next)); if (next) setProjectsExpanded(true); }}
                className={`p-1 rounded transition-colors ${projectsPinned ? "text-cyan-400 bg-cyan-500/10" : "text-zinc-600 hover:text-zinc-400 hover:bg-zinc-800/50"}`}
                title={projectsPinned ? "Unpin" : "Pin open"} aria-label={projectsPinned ? "Unpin projects" : "Pin projects open"} data-testid="pin-projects-btn">
                <Pin className={`w-3 h-3 ${projectsPinned ? "rotate-0" : "rotate-45"}`} />
              </button>
            </div>
            {projectsExpanded && (
              <div className="space-y-0.5">
                {projects.length === 0 ? (
                  <p className="px-3 py-2 text-[11px] text-zinc-600">No projects</p>
                ) : projects.map((p) => (
                  <button key={p.project_id} onClick={() => onTabChange("projects")}
                    className="w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40 transition-colors text-left"
                    data-testid={`sidebar-project-${p.project_id}`} aria-label={`Open project ${p.name}`}>
                    <FolderKanban className="w-3.5 h-3.5 flex-shrink-0 text-zinc-500" />
                    <span className="truncate">{p.name}</span>
                    {p.task_count > 0 && <span className="ml-auto text-[10px] text-zinc-600" title={`${p.tasks_done} of ${p.task_count} tasks completed`}>{p.tasks_done}/{p.task_count}</span>}
                  </button>
                ))}
              </div>
            )}
            </>
            )}
          </div>

          {/* Workflows section in sidebar */}
          <div className="mt-3 pt-3 border-t border-zinc-800/50">
            <button
              onClick={() => onTabChange("workflows")}
              className={`w-full flex items-center ${collapsed ? "justify-center px-1 py-2" : "gap-2 px-2 py-1"} mb-1`}
              data-testid="sidebar-workflows-link" aria-label="View workflows"
              title="Workflows"
            >
              {collapsed ? <Sparkles className="w-4 h-4 text-zinc-500" /> : <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">Workflows</span>}
            </button>
          </div>
        </ScrollArea>

        {/* Edit channel dialog */}
        <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
          <DialogContent className="bg-zinc-900 border-zinc-800 max-w-sm">
            <DialogHeader>
              <DialogTitle className="text-zinc-100 flex items-center gap-2">
                <Pencil className="w-4 h-4 text-zinc-400" />
                Edit Channel
              </DialogTitle>
              <DialogDescription className="sr-only">Edit channel name and agents</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 mt-2">
              <Input
                value={editChannelName}
                onChange={(e) => setEditChannelName(e.target.value)}
                placeholder="Channel name"
                className="bg-zinc-950 border-zinc-800"
                onKeyDown={(e) => e.key === 'Enter' && updateChannel()}
                autoFocus
              />
              {/* Agent selection */}
              <div>
                <label className="text-xs font-mono uppercase tracking-wider text-zinc-500 mb-2 block">AI Agents</label>
                <div className="max-h-48 overflow-y-auto space-y-1 pr-1">
                  {AI_AGENTS.map((agent) => (
                    <label key={agent.key} className="flex items-center gap-3 p-1.5 rounded-lg hover:bg-zinc-800/50 cursor-pointer transition-colors">
                      <Checkbox
                        checked={editChannelAgents.includes(agent.key)}
                        onCheckedChange={() => {
                          setEditChannelAgents(prev => prev.includes(agent.key) ? prev.filter(a => a !== agent.key) : [...prev, agent.key]);
                        }}
                        data-testid={`edit-agent-${agent.key}`}
                      />
                      <div className="w-4 h-4 rounded-full flex items-center justify-center text-[8px] font-bold" style={{ backgroundColor: agent.color, color: ["grok", "notebooklm"].includes(agent.key) ? "#09090b" : "#fff" }}>
                        {agent.name[0]}
                      </div>
                      <span className="text-xs text-zinc-300">{agent.name}</span>
                    </label>
                  ))}
                </div>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={() => setEditDialogOpen(false)}
                  className="flex-1 border-zinc-700 text-zinc-400 text-xs"
                >
                  Cancel
                </Button>
                <Button
                  onClick={updateChannel}
                  disabled={!editChannelName.trim()}
                  className="flex-1 bg-zinc-100 text-zinc-900 hover:bg-zinc-200 text-xs"
                >
                  Save
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Helper button — above footer links */}
      {helper && !helper.open && (
        <div className={`${collapsed ? "px-2" : "px-3"} py-1`}>
          <button onClick={() => helper.restore ? helper.restore() : helper.toggle()}
            className={`w-full flex items-center ${collapsed ? "justify-center px-1 py-1.5" : "gap-2 px-3 py-1.5"} rounded-lg text-[11px] text-cyan-500 hover:text-cyan-400 hover:bg-cyan-500/10 transition-colors`}
            data-testid="helper-sidebar-btn" title="Nexus Helper AI">
            <MessageSquare className="w-3.5 h-3.5 flex-shrink-0" />
            {!collapsed && <span>Helper</span>}
            {!collapsed && helper.messages?.length > 0 && <span className="w-1.5 h-1.5 bg-cyan-400 rounded-full animate-pulse ml-auto" />}
          </button>
        </div>
      )}

      {/* User footer */}
      <div className={`${collapsed ? "p-2" : "p-3"} border-t border-zinc-800/60 space-y-1`}>
        <button onClick={() => navigate("/settings")}
          className={`w-full flex items-center ${collapsed ? "justify-center px-1 py-2" : "gap-2 px-3 py-1.5"} rounded-lg text-xs text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/40 transition-colors`}
          data-testid="settings-link" title="Settings" aria-label="AI Keys and Settings">
          <Settings className="w-3.5 h-3.5 flex-shrink-0" />
          {!collapsed && <span>{t("common.settings")}</span>}
        </button>
        <button onClick={() => navigate("/marketplace")}
          className={`w-full flex items-center ${collapsed ? "justify-center px-1 py-2" : "gap-2 px-3 py-1.5"} rounded-lg text-xs text-zinc-500 hover:text-cyan-400 hover:bg-cyan-500/10 transition-colors`}
          data-testid="marketplace-link" title="Agent Marketplace" aria-label="Agent Marketplace">
          <Sparkles className="w-3.5 h-3.5 flex-shrink-0" />
          {!collapsed && <span>Marketplace</span>}
        </button>
        <button onClick={() => { if (onTabChange) onTabChange("studio"); }}
          className={`w-full flex items-center ${collapsed ? "justify-center px-1 py-2" : "gap-2 px-3 py-1.5"} rounded-lg text-xs text-zinc-500 hover:text-violet-400 hover:bg-violet-500/10 transition-colors`}
          data-testid="studio-link" title="Agent Studio" aria-label="Agent Creator Studio">
          <Bot className="w-3.5 h-3.5 flex-shrink-0" />
          {!collapsed && <span>Agent Studio</span>}
        </button>
        <button onClick={() => { if (onTabChange) onTabChange("dojo"); }}
          className={`w-full flex items-center ${collapsed ? "justify-center px-1 py-2" : "gap-2 px-3 py-1.5"} rounded-lg text-xs text-zinc-500 hover:text-amber-400 hover:bg-amber-500/10 transition-colors`}
          data-testid="dojo-link" title="Agent Dojo" aria-label="Agent Dojo — AI Training Arena">
          <Dumbbell className="w-3.5 h-3.5 flex-shrink-0" />
          {!collapsed && <span>Agent Dojo</span>}
        </button>
        {(user?.platform_role === "super_admin" || user?.platform_role === "admin" || user?.org_role === "admin" || user?.org_role === "owner") ? (
          <button onClick={() => navigate("/billing")}
            className={`w-full flex items-center ${collapsed ? "justify-center px-1 py-2" : "gap-2 px-3 py-1.5"} rounded-lg text-xs text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/40 transition-colors`}
            data-testid="billing-link" title="Billing" aria-label="Billing and Plans">
            <CreditCard className="w-3.5 h-3.5 flex-shrink-0" />
            {!collapsed && <span>{t("common.billing")}</span>}
          </button>
        ) : null}
        {!collapsed && (
          <div className="flex items-center gap-2 px-3 mb-1">
            <a href="/terms" className="text-[9px] text-zinc-600 hover:text-zinc-400">Terms</a>
            <span className="text-zinc-800">|</span>
            <a href="/privacy" className="text-[9px] text-zinc-600 hover:text-zinc-400">Privacy</a>
            <span className="text-zinc-800">|</span>
            <a href="/acceptable-use" className="text-[9px] text-zinc-600 hover:text-zinc-400">AUP</a>
          </div>
        )}
        <div className={`flex items-center ${collapsed ? "justify-center" : "justify-between"}`}>
          <div className={`flex items-center ${collapsed ? "" : "gap-2"} min-w-0`}>
            {user?.picture ? (
              <img src={user.picture} alt="" className="w-6 h-6 rounded-full flex-shrink-0" title={user?.name} />
            ) : (
              <div className="w-6 h-6 rounded-full bg-zinc-800 flex items-center justify-center text-[10px] font-medium flex-shrink-0" title={user?.name}>
                {user?.name?.[0]}
              </div>
            )}
            {!collapsed && <span className="text-xs text-zinc-400 truncate">{user?.name}</span>}
            {!collapsed && user?.platform_role && (
              <span className={`text-[8px] px-1 py-0.5 rounded ${user.platform_role === "super_admin" ? "bg-red-500/20 text-red-400" : "bg-zinc-800 text-zinc-500"}`}>{user.platform_role === "super_admin" ? "Admin" : "Member"}</span>
            )}
          </div>
        </div>
      </div>
      <ConfirmDlg />
    </nav>
  );
};

export default Sidebar;
