import { useState, useEffect, useRef } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogTrigger } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Zap, Plus, LogOut, Users, CreditCard, Settings, MoreVertical, Trash2, PauseCircle, PlayCircle, AlertTriangle, Pencil, Shield, Bug, FileText, Monitor, Building2, Search, Star, LayoutGrid, Workflow, BarChart3, HelpCircle, Pin, MousePointer, PanelLeftClose, PanelLeftOpen, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/App";
import NotificationBell from "@/components/NotificationBell";
import BugReportModal from "@/components/BugReportModal";
import { useHelper } from "@/contexts/NexusHelperContext";
import OnboardingChecklist from "@/components/OnboardingChecklist";
import { useLanguage } from "@/contexts/LanguageContext";
import { useSidebarCollapse } from "@/hooks/useSidebarCollapse";
import { useKeyboardShortcuts, ShortcutPalette } from "@/components/KeyboardShortcuts";
import OnboardingTour from "@/components/OnboardingTour";

const WS_COLORS = [
  { bg: "#10B981", text: "#fff" }, { bg: "#6366F1", text: "#fff" },
  { bg: "#F59E0B", text: "#1a1a1a" }, { bg: "#EC4899", text: "#fff" },
  { bg: "#3B82F6", text: "#fff" }, { bg: "#8B5CF6", text: "#fff" },
  { bg: "#14B8A6", text: "#fff" }, { bg: "#EF4444", text: "#fff" },
];

const MODEL_COLORS = {
  claude: "#D97757", chatgpt: "#10A37F", gemini: "#4285F4", perplexity: "#20B2AA",
  mistral: "#FF7000", cohere: "#39594D", groq: "#F55036", deepseek: "#4D6BFE", grok: "#E4E4E7", mercury: "#00D4FF", pi: "#FF6B35",
};

function getWsColor(name) {
  let hash = 0;
  for (let i = 0; i < (name || "").length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return WS_COLORS[Math.abs(hash) % WS_COLORS.length];
}

export default function Dashboard({ user }) {
  const navigate = useNavigate();
  const { t } = useLanguage();
  const { collapsed, toggle: toggleSidebar } = useSidebarCollapse();
  const helper = useHelper();
  const [workspaces, setWorkspaces] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [workspaceToDelete, setWorkspaceToDelete] = useState(null);
  const [workspaceToEdit, setWorkspaceToEdit] = useState(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [myOrgs, setMyOrgs] = useState([]);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [creating, setCreating] = useState(false);
  const [showDisabled, setShowDisabled] = useState(false);
  const [search, setSearch] = useState("");
  const [selectedForDelete, setSelectedForDelete] = useState(new Set());
  const [deletePreview, setDeletePreview] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [sortBy, setSortBy] = useState("recent");
  const [pinnedIds, setPinnedIds] = useState(() => {
    try { return JSON.parse(localStorage.getItem("nexus_pinned") || "[]"); } catch (err) { return []; }
  });
  const searchTimerRef = useRef(null);

  useEffect(() => { fetchWorkspaces(); checkAdminStatus(); loadMyOrgs(); }, [showDisabled]);

  const checkAdminStatus = async () => { try { const r = await api.get("/admin/check"); setIsAdmin(r.data.is_super_admin || r.data.is_platform_support || r.data.is_staff); } catch (err) { handleSilent(err, "Dashboard:op1"); } };
  const loadMyOrgs = async () => { try { const r = await api.get("/orgs/my-orgs"); setMyOrgs(r.data.organizations || []); } catch (err) { handleSilent(err, "Dashboard:op2"); } };
  const fetchWorkspaces = async (searchQuery = "") => {
    try {
      const params = new URLSearchParams({ include_disabled: showDisabled });
      if (searchQuery) params.set("search", searchQuery);
      const r = await api.get(`/workspaces?${params}`);
      setWorkspaces(r.data);
    }
    catch (err) { toast.error(`Failed to load workspaces: ${err?.response?.data?.detail || err?.message}`); }
    finally { setLoading(false); }
  };
  const createWorkspace = async (e) => {
    if (e?.preventDefault) e.preventDefault();
    if (!newName.trim() || creating) return;
    setCreating(true);
    try { await api.post("/workspaces", { name: newName, description: newDesc }); setDialogOpen(false); setNewName(""); setNewDesc(""); toast.success("Workspace created"); await fetchWorkspaces(); }
    catch (err) { toast.error(`Failed: ${err?.response?.data?.detail || err?.message}`); }
    finally { setCreating(false); }
  };
  const toggleDisable = async (ws) => { try { const r = await api.put(`/workspaces/${ws.workspace_id}/disable`); setWorkspaces(workspaces.map(w => w.workspace_id === ws.workspace_id ? r.data : w)); toast.success(r.data.disabled ? "Disabled" : "Enabled"); } catch (e) { toast.error(e.response?.data?.detail || "Failed"); } };
  const confirmDelete = (ws) => { setWorkspaceToDelete(ws); setDeleteDialogOpen(true); };
  const openEdit = (ws) => { setWorkspaceToEdit(ws); setEditName(ws.name); setEditDesc(ws.description || ""); setEditDialogOpen(true); };
  const updateWorkspace = async () => { if (!workspaceToEdit || !editName.trim()) return; try { const r = await api.put(`/workspaces/${workspaceToEdit.workspace_id}`, { name: editName, description: editDesc }); setWorkspaces(workspaces.map(w => w.workspace_id === workspaceToEdit.workspace_id ? { ...w, ...r.data } : w)); setEditDialogOpen(false); toast.success("Updated"); } catch (e) { toast.error(e.response?.data?.detail || "Failed"); } };
  const deleteWorkspace = async () => { if (!workspaceToDelete) return; try { await api.delete(`/workspaces/${workspaceToDelete.workspace_id}`); setWorkspaces(workspaces.filter(w => w.workspace_id !== workspaceToDelete.workspace_id)); setDeleteDialogOpen(false); toast.success("Deleted"); } catch (e) { toast.error(e.response?.data?.detail || "Failed"); } };
  const handleLogout = async () => { try { await api.post("/auth/logout"); } catch (err) { handleSilent(err, "Dashboard:op3"); } navigate("/"); };

  const toggleSelectForDelete = (wsId) => {
    setSelectedForDelete(prev => {
      const next = new Set(prev);
      if (next.has(wsId)) next.delete(wsId);
      else next.add(wsId);
      return next;
    });
  };

  const selectAllForDelete = () => {
    if (selectedForDelete.size === workspaces.length) setSelectedForDelete(new Set());
    else setSelectedForDelete(new Set(workspaces.map(w => w.workspace_id)));
  };

  const previewDelete = async () => {
    if (selectedForDelete.size === 0) return;
    if (selectedForDelete.size === 1) {
      const wsId = [...selectedForDelete][0];
      try {
        const res = await api.get(`/workspaces/${wsId}/delete-preview`);
        setDeletePreview(res.data);
      } catch (err) { toast.error(err.response?.data?.detail || "Cannot preview"); return; }
    } else {
      setDeletePreview({ bulk: true, count: selectedForDelete.size, workspace_ids: [...selectedForDelete] });
    }
    setDeleteDialogOpen(true);
  };

  const executeDelete = async () => {
    setDeleting(true);
    try {
      if (selectedForDelete.size === 1) {
        const wsId = [...selectedForDelete][0];
        const res = await api.delete(`/workspaces/${wsId}`);
        toast.success(res.data?.message || "Workspace deleted");
      } else {
        const res = await api.post("/workspaces/bulk-delete", { workspace_ids: [...selectedForDelete] });
        const deleted = res.data?.count || res.data?.deleted?.length || 0;
        toast.success(`${deleted} workspace(s) deleted`);
      }
      setSelectedForDelete(new Set());
      setDeleteDialogOpen(false);
      setDeletePreview(null);
      fetchWorkspaces();
    } catch (err) { toast.error(err.response?.data?.detail || "Delete failed"); }
    setDeleting(false);
  };
  const togglePin = (wsId) => {
    const next = pinnedIds.includes(wsId) ? pinnedIds.filter(id => id !== wsId) : [...pinnedIds, wsId];
    setPinnedIds(next);
    localStorage.setItem("nexus_pinned", JSON.stringify(next));
  };

  const { showPalette, setShowPalette } = useKeyboardShortcuts({
    settings: () => navigate("/settings"),
    billing: () => navigate("/billing"),
    new: () => setDialogOpen(true),
  });

  // Filter + sort
  const filtered = workspaces.filter(w => !search || w.name.toLowerCase().includes(search.toLowerCase()) || (w.description || "").toLowerCase().includes(search.toLowerCase()));
  const sorted = [...filtered].sort((a, b) => {
    if (sortBy === "name") return a.name.localeCompare(b.name);
    if (sortBy === "agents") return (b.total_agents || 0) - (a.total_agents || 0);
    return (b.created_at || "").localeCompare(a.created_at || "");
  });
  const pinned = sorted.filter(w => pinnedIds.includes(w.workspace_id));
  const unpinned = sorted.filter(w => !pinnedIds.includes(w.workspace_id));
  const totalAgents = workspaces.reduce((s, w) => s + (w.total_agents || 0), 0);

  const SidebarLink = ({ icon: Icon, label, active, onClick, badge, title }) => (
    <button onClick={onClick} className={`w-full flex items-center ${label ? "gap-2.5 px-3" : "justify-center px-1"} py-2 rounded-lg text-sm transition-colors ${active ? "bg-zinc-800 text-zinc-100 font-medium" : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50"}`} title={title || label}>
      <Icon className="w-4 h-4 flex-shrink-0" />
      {label && <span className="truncate">{label}</span>}
      {badge && <span className="ml-auto text-[10px] bg-emerald-500/15 text-emerald-400 px-1.5 py-0.5 rounded">{badge}</span>}
    </button>
  );

  const WsCard = ({ ws }) => {
    const c = getWsColor(ws.name);
    const isPinned = pinnedIds.includes(ws.workspace_id);
    return (
      <div className={`relative group rounded-xl border transition-all hover:-translate-y-0.5 hover:shadow-lg hover:shadow-black/30 ${selectedForDelete.has(ws.workspace_id) ? "border-red-500/40 bg-red-500/5" : "border-zinc-800/40"} ${ws.disabled ? "opacity-50" : "cursor-pointer"}`}
        onClick={() => !ws.disabled && navigate(`/workspace/${ws.workspace_id}`)}
        data-testid={`workspace-card-${ws.workspace_id}`}
      >
        {/* Selection checkbox */}
        <div className="absolute top-2.5 left-2.5 z-10">
          <input type="checkbox" checked={selectedForDelete.has(ws.workspace_id)}
            onChange={(e) => { e.stopPropagation(); toggleSelectForDelete(ws.workspace_id); }}
            onClick={(e) => e.stopPropagation()}
            className="w-4 h-4 rounded border-zinc-600 bg-zinc-800 text-red-500 opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
            style={selectedForDelete.has(ws.workspace_id) ? { opacity: 1 } : {}}
            data-testid={`select-ws-${ws.workspace_id}`} />
        </div>
        {/* Menu */}
        <div className="absolute top-2.5 right-2.5 z-10 flex items-center gap-0.5">
          <button onClick={(e) => { e.stopPropagation(); togglePin(ws.workspace_id); }} className={`p-1 rounded-md transition-colors ${isPinned ? "text-amber-400" : "text-zinc-700 opacity-0 group-hover:opacity-100 hover:text-amber-400"}`} data-testid={`pin-ws-${ws.workspace_id}`}>
            <Star className={`w-3.5 h-3.5 ${isPinned ? "fill-current" : ""}`} />
          </button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="p-1 rounded-md text-zinc-600 hover:text-zinc-300 hover:bg-zinc-800 transition-all" onClick={(e) => e.stopPropagation()} data-testid={`workspace-menu-${ws.workspace_id}`}>
                <MoreVertical className="w-3.5 h-3.5" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="bg-zinc-900 border-zinc-800" align="end">
              <DropdownMenuItem onClick={(e) => { e.stopPropagation(); openEdit(ws); }} className="text-zinc-300 hover:bg-zinc-800 cursor-pointer text-xs"><Pencil className="w-3.5 h-3.5 mr-2 text-zinc-400" />Rename</DropdownMenuItem>
              <DropdownMenuItem onClick={(e) => { e.stopPropagation(); toggleDisable(ws); }} className="text-zinc-300 hover:bg-zinc-800 cursor-pointer text-xs">
                {ws.disabled ? <><PlayCircle className="w-3.5 h-3.5 mr-2 text-emerald-400" />Enable</> : <><PauseCircle className="w-3.5 h-3.5 mr-2 text-amber-400" />Disable</>}
              </DropdownMenuItem>
              <DropdownMenuSeparator className="bg-zinc-800" />
              <DropdownMenuItem onClick={(e) => { e.stopPropagation(); confirmDelete(ws); }} className="text-red-400 hover:bg-zinc-800 cursor-pointer text-xs"><Trash2 className="w-3.5 h-3.5 mr-2" />Delete</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <div className="text-left w-full p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="relative">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center text-base font-bold flex-shrink-0" style={{ backgroundColor: c.bg, color: c.text }}>
                {ws.name?.[0]?.toUpperCase()}
              </div>
              {/* Persist status indicator */}
              {ws.persist_status && ws.persist_status !== "none" && (
                <div className={`absolute -top-1 -right-1 w-3.5 h-3.5 rounded-full border-2 border-zinc-950 ${
                  ws.persist_status === "active" ? "bg-emerald-500 animate-pulse" :
                  ws.persist_status === "warning" ? "bg-amber-500 animate-pulse" :
                  "bg-red-500"
                }`} title={
                  ws.persist_status === "active" ? "Persistent collaboration active" :
                  ws.persist_status === "warning" ? "Persistent collaboration — issues detected" :
                  "Persistent collaboration stopped — check status"
                } />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <h3 className="text-sm font-semibold text-zinc-200 group-hover:text-zinc-50 truncate">{ws.name}</h3>
              {ws.description && <p className="text-[11px] text-zinc-600 truncate">{ws.description}</p>}
              {ws.persist_status === "error" && (
                <p className="text-[10px] text-red-400 flex items-center gap-1 mt-0.5"><AlertTriangle className="w-3 h-3" />Check channel status</p>
              )}
              {ws.persist_status === "warning" && (
                <p className="text-[10px] text-amber-400 flex items-center gap-1 mt-0.5"><AlertTriangle className="w-3 h-3" />Agent issues detected</p>
              )}
            </div>
          </div>

          {/* Model dots */}
          <div className="flex items-center justify-between border-t border-zinc-800/40 pt-3 mt-1">
            <div className="flex items-center">
              {(ws.total_agents || 0) > 0 ? (
                <div className="flex -space-x-1.5">
                  {["claude", "chatgpt", "gemini", "perplexity", "mistral"].slice(0, Math.min(ws.total_agents || 0, 5)).map((m, i) => (
                    <div key={i} className="w-5 h-5 rounded-full border-2 border-zinc-950 flex items-center justify-center text-[7px] font-bold" style={{ backgroundColor: MODEL_COLORS[m] || "#555", color: m === "grok" ? "#000" : "#fff", zIndex: 5 - i }} />
                  ))}
                  {(ws.total_agents || 0) > 5 && <div className="w-5 h-5 rounded-full border-2 border-zinc-950 bg-zinc-800 flex items-center justify-center text-[8px] text-zinc-400 font-medium" style={{ zIndex: 0 }}>+{(ws.total_agents || 0) - 5}</div>}
                </div>
              ) : (
                <span className="text-[11px] text-zinc-600">No agents</span>
              )}
            </div>
            <div className="flex items-center gap-3 text-[11px] text-zinc-500">
              <span><span className="text-zinc-400">{ws.total_agents || 0}</span> agents</span>
              {ws.disabled && <span className="text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded text-[10px]">Disabled</span>}
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="h-screen flex bg-[#09090b]" data-testid="dashboard-page">
      <OnboardingTour />
      <ShortcutPalette open={showPalette} onClose={() => setShowPalette(false)} />
      {/* ─── SIDEBAR ─── */}
      <aside className={`${collapsed ? "w-16" : "w-56"} flex-shrink-0 bg-zinc-900/50 border-r border-zinc-800/40 flex flex-col transition-all duration-200`} data-testid="dashboard-sidebar">
        {/* Logo + Toggle */}
        <div className={`${collapsed ? "px-2" : "px-4"} py-4 border-b border-zinc-800/40`}>
          <div className="flex items-center justify-between">
            {collapsed ? (
              <img src="/logo.png" alt="Nexus" className="w-8 h-8 rounded-lg mx-auto" />
            ) : (
              <div className="flex items-center gap-2.5">
                <img src="/logo.png" alt="Nexus Cloud" className="w-8 h-8 rounded-lg" />
                <span className="font-bold text-sm tracking-tight text-zinc-100" style={{ fontFamily: 'Syne, sans-serif' }}>NEXUS <span className="text-cyan-400">CLOUD</span></span>
              </div>
            )}
            <button onClick={toggleSidebar} className="p-1 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/60 transition-colors" aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} data-testid="dashboard-sidebar-toggle">
              {collapsed ? <PanelLeftOpen className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* Nav */}
        <div className="flex-1 overflow-y-auto px-2 py-3 space-y-0.5">
          <SidebarLink icon={LayoutGrid} label={collapsed ? "" : "Workspaces"} active title="Workspaces" />
          <SidebarLink icon={Workflow} label={collapsed ? "" : "Workflows"} title="Workflows" onClick={() => { if (workspaces[0]) navigate(`/workspace/${workspaces[0].workspace_id}?tab=workflows`); else toast.info("Create a workspace first"); }} />
          <SidebarLink icon={BarChart3} label={collapsed ? "" : "Analytics"} title="Analytics" onClick={() => { if (workspaces[0]) navigate(`/workspace/${workspaces[0].workspace_id}?tab=analytics`); else toast.info("Create a workspace first"); }} />
          <SidebarLink icon={MousePointer} label={collapsed ? "" : "Walkthroughs"} title="Walkthroughs" onClick={() => navigate("/walkthrough-builder")} />
          {isAdmin && <SidebarLink icon={Shield} label={collapsed ? "" : "Admin Panel"} title="Admin Panel" onClick={() => navigate("/admin")} badge={collapsed ? "" : "Admin"} />}

          {!collapsed && myOrgs.length > 0 && (
            <div className="pt-4">
              <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-wider px-3 mb-1.5">Organizations</p>
              {myOrgs.map((org) => (
                <button key={org.org_id} onClick={() => navigate(`/org/${org.slug}/dashboard`)} className="w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50 transition-colors" data-testid={`org-card-${org.slug}`}>
                  <Building2 className="w-3.5 h-3.5 flex-shrink-0" />
                  <span className="truncate">{org.name}</span>
                </button>
              ))}
            </div>
          )}
          {collapsed && myOrgs.length > 0 && myOrgs.map((org) => (
            <button key={org.org_id} onClick={() => navigate(`/org/${org.slug}/dashboard`)} className="w-full flex justify-center py-1.5 text-zinc-500 hover:text-zinc-300 rounded-lg hover:bg-zinc-800/50" title={org.name}>
              <Building2 className="w-4 h-4" />
            </button>
          ))}
        </div>

        {/* Helper — above footer links */}
        {helper && !helper.open && (
          <div className="px-2 py-1">
            <SidebarLink icon={Sparkles} label={collapsed ? "" : "Helper"} title="Nexus Helper AI"
              onClick={() => helper.restore ? helper.restore() : helper.toggle()} />
          </div>
        )}

        {/* Bottom */}
        <div className="border-t border-zinc-800/40 px-2 py-2 space-y-0.5">
          <SidebarLink icon={Settings} label={collapsed ? "" : "Settings"} title="Settings" onClick={() => navigate("/settings")} />
          <SidebarLink icon={Zap} label={collapsed ? "" : "Nexus AI"} title="Nexus AI — Platform Keys" onClick={() => navigate("/settings?tab=nexus-keys")} badge={collapsed ? "" : ""} />
          <SidebarLink icon={CreditCard} label={collapsed ? "" : "Billing"} title="Billing" onClick={() => navigate("/billing")} />
        </div>

        {/* User */}
        <div className="border-t border-zinc-800/40 px-2 py-3">
          <div className={`flex items-center ${collapsed ? "justify-center" : "gap-2.5"}`}>
            {user?.picture ? (
              <img src={user.picture} alt="" className="w-8 h-8 rounded-full" title={user?.name} />
            ) : (
              <div className="w-8 h-8 rounded-full bg-indigo-500 flex items-center justify-center text-xs font-bold text-white" title={user?.name}>{user?.name?.[0] || "U"}</div>
            )}
            {!collapsed && (
              <>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-zinc-300 truncate" data-testid="user-name">{user?.name}</p>
                  <div className="flex items-center gap-1.5">
                    <span className={`text-[9px] px-1.5 py-0.5 rounded ${user?.platform_role === "super_admin" ? "bg-red-500/20 text-red-400" : user?.platform_role === "org_admin" ? "bg-amber-500/20 text-amber-400" : "bg-zinc-800 text-zinc-500"}`}>
                      {user?.platform_role === "super_admin" ? "Super Admin" : user?.platform_role === "org_admin" ? "Org Admin" : user?.platform_role || "Member"}
                    </span>
                    <span className="text-[9px] text-zinc-600">{(user?.plan || "free").charAt(0).toUpperCase() + (user?.plan || "free").slice(1)}</span>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </aside>

      {/* ─── MAIN ─── */}
      <main className="flex-1 overflow-y-auto">
        {/* Header bar */}
        <div className="sticky top-0 z-30 bg-[#09090b]/80 backdrop-blur-xl border-b border-zinc-800/30 px-8 py-3 flex items-center justify-end gap-3">
          <button onClick={handleLogout} className="flex items-center gap-2 px-5 py-2 rounded-xl text-sm font-semibold text-white bg-cyan-400 hover:bg-cyan-300 shadow-lg shadow-cyan-400/20 transition-all duration-200" data-testid="header-logout-btn" title="Logout">
            <span>{t("common.logout")}</span><LogOut className="w-4 h-4" />
          </button>
          <NotificationBell onNavigate={(path) => navigate(path)} />
          <BugReportModal />
          <button onClick={() => navigate("/my-bugs")} className="text-xs text-zinc-500 hover:text-zinc-300 flex items-center gap-1" data-testid="my-bugs-btn"><FileText className="w-3.5 h-3.5" /></button>
        </div>

        <div className="px-8 py-8 max-w-6xl">
          {/* Onboarding Checklist */}
          <OnboardingChecklist user={user} workspaceCount={workspaces.length} />
          
          {/* Page header */}
          <div className="flex items-start justify-between mb-2">
            <div>
              <h1 className="text-2xl font-bold text-zinc-100" style={{ fontFamily: 'Syne, sans-serif' }} data-testid="dashboard-title">{t("common.workspaces")}</h1>
              <p className="text-sm text-zinc-600 mt-1">
                <span className="text-zinc-400">{workspaces.length}</span> {workspaces.length === 1 ? 'workspace' : 'workspaces'}
                {" · "}<span className="text-zinc-400">{totalAgents}</span> {totalAgents === 1 ? 'AI agent' : 'AI agents'}
                {pinnedIds.length > 0 && <>{" · "}<span className="text-amber-400">{pinnedIds.length} pinned</span></>}
              </p>
            </div>
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
              <DialogTrigger asChild>
                <Button className="bg-emerald-500 hover:bg-emerald-400 text-white font-semibold gap-2" data-testid="create-workspace-btn">
                  <Plus className="w-4 h-4" /> New Workspace
                </Button>
              </DialogTrigger>
              <DialogContent className="bg-zinc-900 border-zinc-800 z-[60]">
                <DialogHeader>
                  <DialogTitle className="text-zinc-100" style={{ fontFamily: 'Syne, sans-serif' }}>{t("dashboard.createWorkspace")}</DialogTitle>
                  <DialogDescription className="text-zinc-500 text-sm">Create a workspace and start collaborating with AI.</DialogDescription>
                </DialogHeader>
                <div className="space-y-4 mt-2">
                  <Input placeholder={t("dashboard.workspaceName")} value={newName} onChange={(e) => setNewName(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && newName.trim()) createWorkspace(e); }} className="bg-zinc-950 border-zinc-800 placeholder:text-zinc-600" data-testid="workspace-name-input" autoFocus />
                  <Input placeholder={t("dashboard.workspaceDesc")} value={newDesc} onChange={(e) => setNewDesc(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && newName.trim()) createWorkspace(e); }} className="bg-zinc-950 border-zinc-800 placeholder:text-zinc-600" data-testid="workspace-desc-input" />
                  <Button type="button" onClick={(e) => { if (!newName.trim()) { toast.error("Workspace name is required"); return; } createWorkspace(e); }} disabled={creating} className="w-full bg-emerald-500 hover:bg-emerald-400 text-white font-medium" data-testid="workspace-submit-btn">{creating ? "Creating..." : "Create Workspace"}</Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>

          {/* Search & Filter */}
          <div className="flex items-center gap-3 mt-5 mb-6">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-600" />
              <input type="text" placeholder="Search workspaces..." value={search} onChange={(e) => {
                  const val = e.target.value;
                  setSearch(val);
                  // Debounced server-side typeahead
                  if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
                  searchTimerRef.current = setTimeout(() => fetchWorkspaces(val), 300);
                }}
                className="w-full bg-zinc-900/60 border border-zinc-800/60 rounded-lg pl-9 pr-3 py-2 text-sm text-zinc-300 placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-700" data-testid="workspace-search" />
            </div>
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}
              className="bg-zinc-900/60 border border-zinc-800/60 rounded-lg px-3 py-2 text-xs text-zinc-400 focus:outline-none" data-testid="workspace-sort">
              <option value="recent">Sort: Recent</option>
              <option value="name">Sort: Name</option>
              <option value="agents">Sort: Most Agents</option>
            </select>
            <label className="flex items-center gap-1.5 text-xs text-zinc-600 cursor-pointer">
              <input type="checkbox" checked={showDisabled} onChange={(e) => setShowDisabled(e.target.checked)} className="rounded border-zinc-700 bg-zinc-900" />
              Show disabled
            </label>
          </div>

          {/* Content */}
          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {[1, 2, 3].map((i) => <div key={i} className="h-36 rounded-xl bg-zinc-900/40 animate-pulse" />)}
            </div>
          ) : workspaces.length === 0 ? (
            <div className="text-center py-20" data-testid="empty-state">
              <div className="w-14 h-14 rounded-2xl bg-zinc-900 border border-zinc-800 flex items-center justify-center mx-auto mb-5"><LayoutGrid className="w-6 h-6 text-zinc-600" /></div>
              <h3 className="text-lg font-semibold text-zinc-300 mb-2" style={{ fontFamily: 'Syne, sans-serif' }}>{t("dashboard.noWorkspaces")}</h3>
              <p className="text-sm text-zinc-500 mb-5 max-w-sm mx-auto">{t("dashboard.noWorkspacesDesc")}</p>
              <Button onClick={() => setDialogOpen(true)} className="bg-emerald-500 hover:bg-emerald-400 text-white font-medium" data-testid="empty-create-btn"><Plus className="w-4 h-4 mr-2" />Create Workspace</Button>
            </div>
          ) : (
            <>
              {/* Pinned */}
              {pinned.length > 0 && (
                <div className="mb-6">
                  <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-widest mb-3 flex items-center gap-1.5"><Star className="w-3 h-3 text-amber-400 fill-amber-400" /> Pinned</p>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="pinned-grid">
                    {pinned.map((ws) => <WsCard key={ws.workspace_id} ws={ws} />)}
                  </div>
                </div>
              )}

              {/* All */}
              <div className="flex items-center justify-between mb-3">
                <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-widest">All Workspaces</p>
                {workspaces.length > 0 && (
                  <div className="flex items-center gap-2">
                    <button onClick={selectAllForDelete} className="text-[10px] text-zinc-600 hover:text-zinc-400 transition-colors" data-testid="select-all-btn">
                      {selectedForDelete.size === workspaces.length ? "Deselect All" : "Select All"}
                    </button>
                  </div>
                )}
              </div>
              {selectedForDelete.size > 0 && (
                <div className="flex items-center gap-3 mb-3 p-3 rounded-lg bg-red-500/5 border border-red-500/20">
                  <span className="text-sm text-zinc-300">{selectedForDelete.size} selected</span>
                  <div className="flex-1" />
                  <Button size="sm" variant="ghost" onClick={() => setSelectedForDelete(new Set())} className="text-zinc-400 text-xs h-7">Clear</Button>
                  <Button size="sm" onClick={previewDelete} className="bg-red-600 hover:bg-red-700 text-white text-xs gap-1 h-7" data-testid="bulk-delete-btn">
                    <Trash2 className="w-3 h-3" /> Delete {selectedForDelete.size > 1 ? `${selectedForDelete.size} Workspaces` : "Workspace"}
                  </Button>
                </div>
              )}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="workspace-grid">
                {unpinned.map((ws) => <WsCard key={ws.workspace_id} ws={ws} />)}
              </div>
            </>
          )}
        </div>
      </main>

      {/* Delete dialog — enhanced with preview and bulk support */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-md">
          <DialogHeader>
            <DialogTitle className="text-zinc-100 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-red-400" />
              {deletePreview?.bulk ? `Delete ${deletePreview.count} Workspaces` : "Delete Workspace"}
            </DialogTitle>
            <DialogDescription className="sr-only">Confirm deletion</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            {deletePreview?.bulk ? (
              <p className="text-sm text-zinc-400">Permanently delete <span className="text-zinc-200 font-medium">{deletePreview.count} workspaces</span> and all their data?</p>
            ) : deletePreview ? (
              <>
                <p className="text-sm text-zinc-400">Permanently delete <span className="text-zinc-200 font-medium">"{deletePreview.workspace_name}"</span>?</p>
                <div className="grid grid-cols-3 gap-2 text-center">
                  {Object.entries(deletePreview.data_counts || {}).filter(([,v]) => v > 0).map(([k, v]) => (
                    <div key={k} className="p-2 rounded bg-zinc-800/50 text-[10px]">
                      <div className="text-sm font-bold text-zinc-200">{v}</div>
                      <div className="text-zinc-500">{k}</div>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-zinc-500">{deletePreview.total_records} total records will be removed</p>
              </>
            ) : (
              <p className="text-sm text-zinc-400">Delete <span className="text-zinc-200 font-medium">"{workspaceToDelete?.name}"</span>?</p>
            )}
            <p className="text-xs text-red-400 bg-red-500/10 p-3 rounded-lg">This action is permanent and cannot be undone. All channels, messages, tasks, projects, files, and agent data will be deleted.</p>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => { setDeleteDialogOpen(false); setDeletePreview(null); }} className="flex-1 border-zinc-700 text-zinc-400">Cancel</Button>
              <Button onClick={deletePreview ? executeDelete : deleteWorkspace} disabled={deleting}
                className="flex-1 bg-red-600 hover:bg-red-700 text-white" data-testid="confirm-delete-workspace">
                {deleting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Trash2 className="w-4 h-4 mr-2" />}
                {deleting ? "Deleting..." : "Delete Permanently"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-md">
          <DialogHeader>
            <DialogTitle className="text-zinc-100 flex items-center gap-2"><Pencil className="w-5 h-5 text-zinc-400" />Rename Workspace</DialogTitle>
            <DialogDescription className="sr-only">Edit workspace</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <Input value={editName} onChange={(e) => setEditName(e.target.value)} placeholder="Name" className="bg-zinc-950 border-zinc-800" data-testid="edit-workspace-name" />
            <Input value={editDesc} onChange={(e) => setEditDesc(e.target.value)} placeholder="Description" className="bg-zinc-950 border-zinc-800" data-testid="edit-workspace-desc" />
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setEditDialogOpen(false)} className="flex-1 border-zinc-700 text-zinc-400">Cancel</Button>
              <Button onClick={updateWorkspace} disabled={!editName.trim()} className="flex-1 bg-zinc-100 text-zinc-900 hover:bg-zinc-200" data-testid="save-workspace-edit">Save</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
