import { useState, useEffect, useCallback } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import {
  Plus, ArrowRight, LogOut, Users, Settings, Building2, Shield, BarChart3,
  Loader2, Zap, LayoutGrid, Workflow, FolderKanban, ListTodo, Search,
  ChevronRight, Circle, Clock, CheckCircle2, AlertTriangle, Pause,
  ArrowUp, ArrowDown, Minus, Bot, User, CreditCard
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { api } from "@/App";
import { toast } from "sonner";
import GanttChart from "@/components/GanttChart";
import PlannerCalendar from "@/components/PlannerCalendar";
import RepositoryPanel from "@/components/RepositoryPanel";
import { OrgIntegrations, EncryptionSettings, CloudStorageConnections } from "@/components/IntegrationSettings";
import OrgMembersPanel from "@/components/OrgMembersPanel";
import ManagedKeysUser from "@/components/ManagedKeysUser";

const TASK_STATUS = {
  todo: { label: "To Do", color: "bg-zinc-500/20 text-zinc-400", icon: Circle },
  in_progress: { label: "In Progress", color: "bg-blue-500/20 text-blue-400", icon: Clock },
  review: { label: "Review", color: "bg-amber-500/20 text-amber-400", icon: AlertTriangle },
  done: { label: "Done", color: "bg-emerald-500/20 text-emerald-400", icon: CheckCircle2 },
};
const PRIORITY_CONFIG = {
  low: { label: "Low", color: "text-zinc-400", icon: ArrowDown },
  medium: { label: "Medium", color: "text-blue-400", icon: Minus },
  high: { label: "High", color: "text-amber-400", icon: ArrowUp },
  critical: { label: "Critical", color: "text-red-400", icon: AlertTriangle },
};

export default function OrgDashboard() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [user, setUser] = useState(location.state?.user || null);
  const [org, setOrg] = useState(location.state?.org || null);
  const [orgRole, setOrgRole] = useState(null);
  const [workspaces, setWorkspaces] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("workspaces");
  const [wsName, setWsName] = useState("");
  const [wsDesc, setWsDesc] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  // Rollup data
  const [orgProjects, setOrgProjects] = useState([]);
  const [orgTasks, setOrgTasks] = useState([]);
  const [orgWorkflows, setOrgWorkflows] = useState([]);
  const [orgAnalytics, setOrgAnalytics] = useState(null);
  const [taskSearch, setTaskSearch] = useState("");
  const [taskStatus, setTaskStatus] = useState("");

  useEffect(() => { loadData(); }, [slug]);

  const loadData = async () => {
    try {
      let currentUser = user;
      if (!currentUser) { const r = await api.get("/auth/me"); currentUser = r.data; setUser(currentUser); }
      const orgRes = await api.get(`/orgs/by-slug/${slug}`);
      setOrg(orgRes.data);
      const myOrgs = await api.get("/orgs/my-orgs");
      const myOrg = myOrgs.data.organizations?.find(o => o.slug === slug);
      if (!myOrg) { toast.error("Not a member"); navigate("/dashboard"); return; }
      setOrgRole(myOrg.org_role);
      const wsRes = await api.get(`/orgs/${orgRes.data.org_id}/workspaces`);
      setWorkspaces(wsRes.data.workspaces || []);
    } catch (err) {
      if (err.response?.status === 401) navigate(`/org/${slug}`);
      else toast.error("Failed to load organization");
    } finally { setLoading(false); }
  };

  const loadTabData = useCallback(async () => {
    if (!org) return;
    try {
      if (activeTab === "projects") {
        const r = await api.get(`/orgs/${org.org_id}/projects`);
        setOrgProjects(r.data.projects || []);
      } else if (activeTab === "tasks") {
        const params = new URLSearchParams();
        if (taskSearch) params.append("search", taskSearch);
        if (taskStatus) params.append("status", taskStatus);
        const r = await api.get(`/orgs/${org.org_id}/tasks?${params}`);
        setOrgTasks(r.data.tasks || []);
      } else if (activeTab === "workflows") {
        const r = await api.get(`/orgs/${org.org_id}/workflows`);
        setOrgWorkflows(r.data.workflows || []);
      } else if (activeTab === "analytics") {
        const r = await api.get(`/orgs/${org.org_id}/analytics/summary`);
        setOrgAnalytics(r.data);
      }
    } catch (err) { handleSilent(err, "OrgDashboard:op1"); }
  }, [org, activeTab, taskSearch, taskStatus]);

  useEffect(() => { loadTabData(); }, [loadTabData]);

  const createWorkspace = async () => {
    if (!wsName.trim() || !org) return;
    try {
      await api.post(`/orgs/${org.org_id}/workspaces`, { name: wsName, description: wsDesc });
      setShowCreate(false); setWsName(""); setWsDesc(""); loadData();
      toast.success("Workspace created");
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  const isOrgAdmin = orgRole === "org_owner" || orgRole === "org_admin";

  if (loading) return <div className="min-h-screen bg-[#09090b] flex items-center justify-center"><Loader2 className="w-8 h-8 animate-spin text-zinc-500" /></div>;

  const SideLink = ({ icon: Icon, label, tab, badge }) => (
    <button onClick={() => setActiveTab(tab)} className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${activeTab === tab ? "bg-zinc-800 text-zinc-100 font-medium" : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50"}`} data-testid={`org-tab-${tab}`}>
      <Icon className="w-4 h-4 flex-shrink-0" /><span className="truncate">{label}</span>
      {badge && <span className="ml-auto text-[10px] bg-emerald-500/15 text-emerald-400 px-1.5 py-0.5 rounded">{badge}</span>}
    </button>
  );

  return (
    <div className="h-screen flex bg-[#09090b]" data-testid="org-dashboard">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 bg-zinc-900/50 border-r border-zinc-800/40 flex flex-col">
        <div className="px-4 py-4 border-b border-zinc-800/40">
          <div className="flex items-center gap-2.5">
            <img src="/logo.png" alt="Nexus Cloud" className="w-7 h-7 rounded-lg" />
            <div className="min-w-0">
              <p className="text-sm font-bold text-zinc-100 truncate" style={{ fontFamily: 'Syne, sans-serif' }}>{org?.name}</p>
              <div className="flex items-center gap-1.5">
                <p className="text-[10px] text-zinc-600">/{slug}</p>
                <span className={`text-[8px] px-1.5 py-0.5 rounded-full font-semibold uppercase ${
                  org?.plan === 'enterprise' ? 'bg-red-500/20 text-red-400' :
                  org?.plan === 'team' ? 'bg-purple-500/20 text-purple-400' :
                  org?.plan === 'pro' ? 'bg-amber-500/20 text-amber-400' :
                  org?.plan === 'starter' ? 'bg-blue-500/20 text-blue-400' :
                  'bg-zinc-800 text-zinc-500'
                }`}>{org?.plan || 'free'}</span>
              </div>
            </div>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto px-3 py-3 space-y-0.5">
          <SideLink icon={LayoutGrid} label="Workspaces" tab="workspaces" badge={String(workspaces.length)} />
          <SideLink icon={Workflow} label="Workflows" tab="workflows" />
          <SideLink icon={FolderKanban} label="Projects" tab="projects" />
          <SideLink icon={ListTodo} label="Tasks" tab="tasks" />
          <SideLink icon={BarChart3} label="Analytics" tab="analytics" />
          <SideLink icon={FolderKanban} label="Gantt" tab="gantt" />
          <SideLink icon={ListTodo} label="Planner" tab="planner" />
          <SideLink icon={LayoutGrid} label="Repository" tab="repository" />
          <SideLink icon={Settings} label="Settings" tab="settings" />
          <SideLink icon={ListTodo} label="Integrations" tab="integrations" />
          <SideLink icon={Zap} label="Nexus AI" tab="nexus-ai" />
          <SideLink icon={CreditCard} label="Billing" tab="billing" />
          {isOrgAdmin && <SideLink icon={Shield} label="Admin" tab="admin" />}
          {isOrgAdmin && <SideLink icon={Users} label="Members" tab="members" />}
        </div>
        <div className="border-t border-zinc-800/40 px-3 py-2 space-y-0.5">
          <button onClick={() => navigate("/dashboard")} className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50"><ArrowRight className="w-4 h-4" />Personal Dashboard</button>
        </div>
        <div className="border-t border-zinc-800/40 px-3 py-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-indigo-500 flex items-center justify-center text-xs font-bold text-white">{user?.name?.[0]}</div>
            <div className="min-w-0 flex-1"><p className="text-xs font-medium text-zinc-300 truncate">{user?.name}</p><p className="text-[10px] text-zinc-600">{orgRole?.replace("org_", "")}</p></div>
            <button onClick={() => { api.post("/auth/logout"); navigate("/"); }} className="p-1.5 rounded-md text-zinc-600 hover:text-zinc-300" data-testid="org-logout-btn"><LogOut className="w-3.5 h-3.5" /></button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto">
        <div className="px-8 py-8 max-w-6xl">
          {/* ─── Workspaces Tab ─── */}
          {activeTab === "workspaces" && (
            <>
              <div className="flex items-start justify-between mb-6">
                <div><h2 className="text-2xl font-bold text-zinc-100" style={{ fontFamily: 'Syne, sans-serif' }}>Workspaces</h2><p className="text-sm text-zinc-500 mt-1">{workspaces.length} workspace{workspaces.length !== 1 ? "s" : ""} in {org?.name}</p></div>
                {orgRole !== "org_viewer" && (
                  <Dialog open={showCreate} onOpenChange={setShowCreate}>
                    <DialogTrigger asChild><Button className="bg-emerald-500 hover:bg-emerald-400 text-white font-semibold gap-2" data-testid="org-create-workspace-btn"><Plus className="w-4 h-4" />New Workspace</Button></DialogTrigger>
                    <DialogContent className="bg-zinc-900 border-zinc-800 text-zinc-100">
                      <DialogHeader><DialogTitle>Create Workspace</DialogTitle></DialogHeader>
                      <Input placeholder="Workspace name" value={wsName} onChange={(e) => setWsName(e.target.value)} className="bg-zinc-800/50 border-zinc-700" data-testid="org-ws-name-input" />
                      <Textarea placeholder="Description (optional)" value={wsDesc} onChange={(e) => setWsDesc(e.target.value)} className="bg-zinc-800/50 border-zinc-700" data-testid="org-ws-desc-input" />
                      <DialogFooter><Button onClick={createWorkspace} className="bg-emerald-500 hover:bg-emerald-400 text-white" data-testid="org-ws-submit-btn">Create</Button></DialogFooter>
                    </DialogContent>
                  </Dialog>
                )}
              </div>
              {workspaces.length === 0 ? (
                <div className="text-center py-16"><LayoutGrid className="w-10 h-10 text-zinc-700 mx-auto mb-3" /><p className="text-zinc-400">No workspaces yet</p></div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {workspaces.map((ws) => (
                    <div key={ws.workspace_id} className="p-5 rounded-xl bg-zinc-900/50 border border-zinc-800 hover:border-zinc-700 transition-colors cursor-pointer group" onClick={() => navigate(`/workspace/${ws.workspace_id}`)} data-testid={`org-ws-card-${ws.workspace_id}`}>
                      <h3 className="text-sm font-semibold text-zinc-200 group-hover:text-zinc-100 mb-1">{ws.name}</h3>
                      <p className="text-xs text-zinc-500 line-clamp-2 mb-3">{ws.description || "No description"}</p>
                      <div className="flex items-center gap-3 text-[10px] text-zinc-600"><Users className="w-3 h-3" /> {ws.members?.length || 1} members</div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {/* ─── Projects Roll-up ─── */}
          {activeTab === "projects" && (
            <>
              <h2 className="text-2xl font-bold text-zinc-100 mb-1" style={{ fontFamily: 'Syne, sans-serif' }}>All Projects</h2>
              <p className="text-sm text-zinc-500 mb-6">{orgProjects.length} projects across all workspaces</p>
              {orgProjects.length === 0 ? (
                <div className="text-center py-16"><FolderKanban className="w-10 h-10 text-zinc-700 mx-auto mb-3" /><p className="text-zinc-400">No projects yet</p></div>
              ) : (
                <div className="space-y-2" data-testid="org-projects-list">
                  {orgProjects.map((p) => (
                    <div key={p.project_id} className="flex items-center gap-4 p-4 rounded-xl bg-zinc-900/50 border border-zinc-800 hover:border-zinc-700 transition-colors group" data-testid={`org-project-${p.project_id}`}>
                      <FolderKanban className="w-5 h-5 text-zinc-500 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2"><span className="text-sm font-medium text-zinc-200">{p.name}</span><Badge className="text-[9px] bg-zinc-800 text-zinc-400">{p.status}</Badge></div>
                        <div className="flex items-center gap-3 mt-1 text-[11px] text-zinc-500">
                          <button onClick={() => navigate(`/workspace/${p.workspace_id}`)} className="text-emerald-400 hover:text-emerald-300 hover:underline" data-testid={`project-ws-link-${p.project_id}`}>{p.workspace_name}</button>
                          <span>{p.tasks_done}/{p.task_count} tasks done</span>
                        </div>
                      </div>
                      <ChevronRight className="w-4 h-4 text-zinc-700 group-hover:text-zinc-500" />
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {/* ─── Tasks Roll-up with Kanban ─── */}
          {activeTab === "tasks" && (
            <>
              <h2 className="text-2xl font-bold text-zinc-100 mb-1" style={{ fontFamily: 'Syne, sans-serif' }}>All Tasks</h2>
              <p className="text-sm text-zinc-500 mb-4">{orgTasks.length} tasks across all workspaces</p>
              <div className="flex items-center gap-3 mb-6">
                <div className="relative flex-1 max-w-sm">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-600" />
                  <input type="text" placeholder="Search tasks..." value={taskSearch} onChange={(e) => setTaskSearch(e.target.value)} className="w-full bg-zinc-900/60 border border-zinc-800/60 rounded-lg pl-9 pr-3 py-2 text-sm text-zinc-300 placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-700" data-testid="org-task-search" />
                </div>
                <select value={taskStatus} onChange={(e) => setTaskStatus(e.target.value)} className="bg-zinc-900/60 border border-zinc-800/60 rounded-lg px-3 py-2 text-xs text-zinc-400" data-testid="org-task-status-filter">
                  <option value="">All Status</option>
                  {Object.entries(TASK_STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
                </select>
              </div>
              {/* Kanban Board */}
              <div className="flex gap-3 overflow-x-auto pb-4" data-testid="org-kanban-board">
                {Object.entries(TASK_STATUS).map(([status, cfg]) => {
                  const Icon = cfg.icon;
                  const colTasks = orgTasks.filter(t => t.status === status);
                  return (
                    <div key={status} className="w-72 flex-shrink-0 flex flex-col rounded-xl border border-zinc-800/50 bg-zinc-900/30">
                      <div className="px-3 py-2.5 border-b border-zinc-800/40 flex items-center gap-2">
                        <Icon className={`w-3.5 h-3.5 ${cfg.color.split(' ')[1]}`} />
                        <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">{cfg.label}</span>
                        <span className="ml-auto text-[10px] text-zinc-600 bg-zinc-800/60 px-1.5 py-0.5 rounded-full">{colTasks.length}</span>
                      </div>
                      <div className="flex-1 p-2 space-y-2 min-h-[120px] max-h-[60vh] overflow-y-auto">
                        {colTasks.length === 0 && <div className="rounded-lg border-2 border-dashed border-zinc-800/30 py-6 text-center"><p className="text-[11px] text-zinc-600">No tasks</p></div>}
                        {colTasks.map((t) => {
                          const pc = PRIORITY_CONFIG[t.priority] || PRIORITY_CONFIG.medium;
                          const PIcon = pc.icon;
                          return (
                            <div key={t.task_id} className="p-3 rounded-lg bg-zinc-900/80 border border-zinc-800/50 hover:border-zinc-700 group" data-testid={`org-task-${t.task_id}`}>
                              <div className="flex items-start justify-between gap-2 mb-1"><span className="text-sm font-medium text-zinc-200 leading-tight">{t.title}</span><PIcon className={`w-3 h-3 ${pc.color} flex-shrink-0 mt-0.5`} /></div>
                              <div className="space-y-1 mt-2">
                                <div className="flex items-center gap-1 text-[10px] text-zinc-500"><FolderKanban className="w-3 h-3" /><span>{t.project_name}</span></div>
                                <button onClick={() => navigate(`/workspace/${t.workspace_id}`)} className="flex items-center gap-1 text-[10px] text-emerald-500 hover:text-emerald-400"><LayoutGrid className="w-3 h-3" /><span>{t.workspace_name}</span></button>
                              </div>
                              {t.assignee_name && <div className="flex items-center gap-1 mt-1.5 text-[10px] text-zinc-500">{t.assignee_type === "ai" ? <Bot className="w-3 h-3" /> : <User className="w-3 h-3" />}{t.assignee_name}</div>}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}

          {/* ─── Workflows ─── */}
          {activeTab === "workflows" && (
            <>
              <h2 className="text-2xl font-bold text-zinc-100 mb-1" style={{ fontFamily: 'Syne, sans-serif' }}>All Workflows</h2>
              <p className="text-sm text-zinc-500 mb-6">{orgWorkflows.length} workflows across all workspaces</p>
              {orgWorkflows.length === 0 ? (
                <div className="text-center py-16"><Workflow className="w-10 h-10 text-zinc-700 mx-auto mb-3" /><p className="text-zinc-400">No workflows yet</p></div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="org-workflows-list">
                  {orgWorkflows.map((wf) => (
                    <div key={wf.workflow_id} className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800 hover:border-zinc-700 transition-colors group" data-testid={`org-wf-${wf.workflow_id}`}>
                      <div className="flex items-center gap-2 mb-2"><Workflow className="w-4 h-4 text-blue-400" /><span className="text-sm font-medium text-zinc-200">{wf.name}</span></div>
                      <p className="text-xs text-zinc-500 line-clamp-2 mb-3">{wf.description || "No description"}</p>
                      <div className="flex items-center justify-between text-[10px] text-zinc-600">
                        <Badge className={`text-[9px] ${wf.status === "active" ? "bg-emerald-500/20 text-emerald-400" : "bg-zinc-800 text-zinc-500"}`}>{wf.status}</Badge>
                        <button onClick={() => navigate(`/workspace/${wf.workspace_id}`)} className="text-emerald-400 hover:text-emerald-300">{wf.workspace_name}</button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {/* ─── Analytics ─── */}
          {activeTab === "analytics" && (
            <>
              <h2 className="text-2xl font-bold text-zinc-100 mb-6" style={{ fontFamily: 'Syne, sans-serif' }}>Organization Analytics</h2>
              {orgAnalytics ? (
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4" data-testid="org-analytics">
                  {[
                    { label: "Workspaces", value: orgAnalytics.workspaces, color: "text-emerald-400" },
                    { label: "Projects", value: orgAnalytics.total_projects, color: "text-blue-400" },
                    { label: "Tasks", value: orgAnalytics.total_tasks, color: "text-amber-400" },
                    { label: "Workflows", value: orgAnalytics.total_workflows, color: "text-purple-400" },
                    { label: "Messages", value: orgAnalytics.total_messages, color: "text-zinc-300" },
                  ].map((s) => (
                    <div key={s.label} className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800 text-center">
                      <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
                      <p className="text-xs text-zinc-500 mt-1">{s.label}</p>
                    </div>
                  ))}
                </div>
              ) : <Loader2 className="w-6 h-6 animate-spin text-zinc-500 mx-auto" />}
            </>
          )}

          {/* ─── Gantt ─── */}
          {activeTab === "gantt" && (
            <>
              <h2 className="text-2xl font-bold text-zinc-100 mb-4" style={{ fontFamily: 'Syne, sans-serif' }}>Gantt Chart</h2>
              <GanttChart orgId={org?.org_id} />
            </>
          )}

          {/* ─── Planner ─── */}
          {activeTab === "planner" && (
            <>
              <h2 className="text-2xl font-bold text-zinc-100 mb-4" style={{ fontFamily: 'Syne, sans-serif' }}>Planner</h2>
              <PlannerCalendar orgId={org?.org_id} />
            </>
          )}

          {/* ─── Repository ─── */}
          {activeTab === "repository" && org && (
            <RepositoryPanel orgId={org.org_id} />
          )}

          {/* ─── Settings (Integrations + Encryption) ─── */}
          {activeTab === "settings" && org && (
            <div className="space-y-6">
              <h2 className="text-2xl font-bold text-zinc-100" style={{ fontFamily: 'Syne, sans-serif' }}>Organization Settings</h2>
              <EncryptionSettings orgId={org.org_id} />
              <CloudStorageConnections scope="org" orgId={org.org_id} />
              <OrgIntegrations orgId={org.org_id} />
            </div>
          )}

          {/* ─── Integrations (dedicated view) ─── */}
          {activeTab === "integrations" && org && (
            <div className="space-y-6">
              <h2 className="text-2xl font-bold text-zinc-100" style={{ fontFamily: 'Syne, sans-serif' }}>Integrations</h2>
              <p className="text-sm text-zinc-500">Configure API keys for messaging, storage, development, and media services. These override platform defaults for this organization.</p>
              <OrgIntegrations orgId={org.org_id} />
              <CloudStorageConnections scope="org" orgId={org.org_id} />
            </div>
          )}

          {/* ─── Nexus AI (Managed Keys) ─── */}
          {activeTab === "nexus-ai" && (
            <div className="space-y-6">
              <h2 className="text-2xl font-bold text-zinc-100" style={{ fontFamily: 'Syne, sans-serif' }}>Nexus AI</h2>
              {org?.nexus_ai_enabled ? (
                <>
                  <div className="p-4 rounded-xl bg-cyan-500/10 border border-cyan-500/20">
                    <div className="flex items-center gap-2">
                      <Zap className="w-4 h-4 text-cyan-400" />
                      <span className="text-sm font-medium text-cyan-300">Nexus AI is enabled for {org.name}</span>
                    </div>
                    <p className="text-xs text-zinc-500 mt-1">All organization members can use platform-provided AI keys. Usage is deducted from your credit balance.</p>
                  </div>
                  <ManagedKeysUser />
                </>
              ) : (
                <div className="p-6 rounded-xl bg-zinc-900/40 border border-zinc-800/60 text-center">
                  <Zap className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
                  <h3 className="text-lg font-semibold text-zinc-300 mb-2">Nexus AI Not Enabled</h3>
                  <p className="text-sm text-zinc-500 mb-4">Nexus AI platform keys have not been enabled for this organization. Contact your Nexus Cloud administrator to enable this feature.</p>
                  <p className="text-xs text-zinc-600">When enabled, you can use AI models without providing your own API keys. Credits are managed by your organization's plan.</p>
                </div>
              )}
            </div>
          )}

          {/* ─── Billing ─── */}
          {activeTab === "billing" && org && (
            <div className="space-y-6">
              <h2 className="text-2xl font-bold text-zinc-100" style={{ fontFamily: 'Syne, sans-serif' }}>Organization Billing</h2>
              <div className="p-6 rounded-xl bg-zinc-900/40 border border-zinc-800/60">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <p className="text-sm text-zinc-500">Current Plan</p>
                    <p className="text-3xl font-bold text-zinc-100 mt-1">{(org.plan || "free").charAt(0).toUpperCase() + (org.plan || "free").slice(1)}</p>
                  </div>
                  <span className={`text-sm px-4 py-2 rounded-full font-semibold uppercase ${
                    org.plan === 'enterprise' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                    org.plan === 'team' ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30' :
                    org.plan === 'pro' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                    org.plan === 'starter' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' :
                    'bg-zinc-800 text-zinc-400 border border-zinc-700'
                  }`}>{org.plan || 'free'}</span>
                </div>
                <p className="text-xs text-zinc-600">
                  {org.plan === 'enterprise' ? 'Custom enterprise plan managed by Nexus Cloud.' :
                   org.plan === 'free' ? 'Free plan. Contact your admin or Nexus Cloud to upgrade.' :
                   `${(org.plan || '').charAt(0).toUpperCase() + (org.plan || '').slice(1)} plan. Contact admin to change.`}
                </p>
              </div>
              <div className="p-4 rounded-xl bg-zinc-900/30 border border-zinc-800/40">
                <p className="text-xs text-zinc-500">
                  Plan changes are managed by platform administrators. If you need an upgrade, contact your Nexus Cloud admin or reach out to <a href="mailto:support@nexuscloud.ai" className="text-cyan-400 hover:underline">support@nexuscloud.ai</a>.
                </p>
              </div>
            </div>
          )}

          {/* ─── Admin ─── */}
          {activeTab === "admin" && isOrgAdmin && (
            <>
              <h2 className="text-2xl font-bold text-zinc-100 mb-4" style={{ fontFamily: 'Syne, sans-serif' }}>Admin Panel</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800 text-center"><p className="text-2xl font-bold text-blue-400">{workspaces.length}</p><p className="text-xs text-zinc-500">Workspaces</p></div>
                <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800 text-center"><p className="text-2xl font-bold text-emerald-400">{orgProjects.length}</p><p className="text-xs text-zinc-500">Projects</p></div>
                <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800 text-center"><p className="text-2xl font-bold text-amber-400">{orgTasks.length}</p><p className="text-xs text-zinc-500">Tasks</p></div>
                <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800 text-center"><p className="text-2xl font-bold text-purple-400">{orgWorkflows.length}</p><p className="text-xs text-zinc-500">Workflows</p></div>
              </div>
              <div className="flex gap-3">
                <Button onClick={() => navigate(`/org/${slug}/admin`)} className="bg-zinc-800 hover:bg-zinc-700 text-zinc-200 gap-2"><Shield className="w-4 h-4" />Full Admin Dashboard</Button>
                <Button variant="outline" onClick={() => navigate(`/org/${slug}/analytics`)} className="border-zinc-700 text-zinc-400 gap-2"><BarChart3 className="w-4 h-4" />Detailed Analytics</Button>
              </div>
            </>
          )}

          {/* ─── Members ─── */}
          {activeTab === "members" && isOrgAdmin && <OrgMembersPanel orgId={org?.org_id} slug={slug} />}
        </div>
      </main>
    </div>
  );
}
