import { useState, useEffect } from "react";
import { useConfirm } from "@/components/ConfirmDialog";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { useNavigate } from "react-router-dom";
import {
  Shield, Bug, Users, MessageSquare, BarChart3, Activity, TrendingUp,
  ChevronRight, Loader2, CheckCircle, AlertTriangle, Clock,
  XCircle, FileText, Folder, Zap, ArrowLeft, RefreshCw, Building2, Trash2, GitBranch,
  Copy, Download, RotateCw, Archive, Globe, Key
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import AuditLogViewer from "@/components/AuditLogViewer";
import SSOConfigPanel from "@/components/SSOConfigPanel";
import ErrorTrackingPanel from "@/components/ErrorTrackingPanel";
import ManagedKeysAdmin from "@/components/ManagedKeysAdmin";
import { api } from "@/App";

const STATUS_CONFIG = {
  open: { label: "Open", color: "bg-blue-500/20 text-blue-400", icon: AlertTriangle },
  in_progress: { label: "In Progress", color: "bg-amber-500/20 text-amber-400", icon: Clock },
  resolved: { label: "Resolved", color: "bg-emerald-500/20 text-emerald-400", icon: CheckCircle },
  closed: { label: "Closed", color: "bg-zinc-500/20 text-zinc-400", icon: XCircle },
  wont_fix: { label: "Won't Fix", color: "bg-red-500/20 text-red-400", icon: XCircle },
};

const PRIORITY_CONFIG = {
  low: { label: "Low", color: "text-zinc-400" },
  medium: { label: "Medium", color: "text-blue-400" },
  high: { label: "High", color: "text-amber-400" },
  critical: { label: "Critical", color: "text-red-400" },
};


function PlatformAnalytics() {
  const [data, setData] = useState(null);
  const [reportData, setReportData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [statsRes, healthRes, bizRes] = await Promise.all([
          api.get("/admin/stats"),
          api.get("/reports/platform/health").catch(() => ({ data: null })),
          api.get("/reports/platform/business").catch(() => ({ data: null })),
        ]);
        setData(statsRes.data);
        setReportData({ health: healthRes.data, business: bizRes.data });
      } catch (err) {
        console.error("Analytics load error:", err);
      }
      setLoading(false);
    };
    load();
  }, []);

  if (loading) return <div className="text-center py-8 text-zinc-500">Loading analytics...</div>;
  if (!data) return <div className="text-center py-8 text-zinc-500">Failed to load analytics. Ensure you have admin access.</div>;

  return (
    <div className="space-y-6" data-testid="platform-analytics">
      {/* Overview stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: "Total Users", value: data.users?.total || 0, sub: `+${data.users?.this_week || 0} this week`, color: "text-emerald-400" },
          { label: "Workspaces", value: data.workspaces?.total || 0, sub: `${data.workspaces?.active || 0} active`, color: "text-blue-400" },
          { label: "Total Messages", value: data.messages?.total || 0, sub: `${data.messages?.today || 0} today`, color: "text-amber-400" },
          { label: "AI Collaborations", value: data.collaborations?.total || 0, sub: `${data.collaborations?.today || 0} today`, color: "text-purple-400" },
        ].map((s, i) => (
          <div key={i} className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/60 text-center">
            <p className="text-2xl font-bold text-zinc-200">{s.value.toLocaleString()}</p>
            <p className="text-xs text-zinc-500">{s.label}</p>
            <p className={`text-[10px] ${s.color}`}>{s.sub}</p>
          </div>
        ))}
      </div>

      {/* Secondary stats */}
      <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
        {[
          { label: "Channels", value: data.channels?.total || 0 },
          { label: "Projects", value: data.projects?.total || 0 },
          { label: "Project Tasks", value: data.projects?.tasks || 0 },
          { label: "Wiki Pages", value: data.wiki?.pages || 0 },
          { label: "Repo Files", value: data.code_repo?.files || 0 },
          { label: "Commits", value: data.code_repo?.commits || 0 },
          { label: "Organizations", value: data.orgs?.total || 0 },
          { label: "Task Sessions", value: data.tasks?.total || 0 },
          { label: "Bug Reports", value: `${data.bugs?.open || 0}/${data.bugs?.total || 0}` },
          { label: "AI Messages", value: data.messages?.ai || 0 },
          { label: "Human Messages", value: data.messages?.human || 0 },
          { label: "Files", value: data.files?.total || 0 },
        ].map((s, i) => (
          <div key={i} className="p-3 rounded-lg bg-zinc-800/30 border border-zinc-800/40 text-center">
            <p className="text-lg font-bold text-zinc-300">{typeof s.value === "number" ? s.value.toLocaleString() : s.value}</p>
            <p className="text-[10px] text-zinc-500">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Message breakdown */}
      {(data.messages?.ai > 0 || data.messages?.human > 0) && (
        <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/60">
          <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">Message Breakdown</h3>
          <div className="flex items-center gap-2 mb-2">
            <div className="flex-1 h-4 bg-zinc-800 rounded-full overflow-hidden flex">
              {(() => {
                const total = (data.messages?.ai || 0) + (data.messages?.human || 0);
                const aiPct = total > 0 ? Math.round((data.messages.ai / total) * 100) : 0;
                return (
                  <>
                    <div className="h-full bg-purple-500 transition-all" style={{ width: `${aiPct}%` }} />
                    <div className="h-full bg-emerald-500 transition-all" style={{ width: `${100 - aiPct}%` }} />
                  </>
                );
              })()}
            </div>
          </div>
          <div className="flex items-center gap-4 text-xs">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-purple-500" /> AI: {(data.messages?.ai || 0).toLocaleString()}</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500" /> Human: {(data.messages?.human || 0).toLocaleString()}</span>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Top workspaces */}
        {data.top_workspaces?.length > 0 && (
          <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/60">
            <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-1"><TrendingUp className="w-3 h-3" /> Top Workspaces</h3>
            <div className="space-y-2">
              {data.top_workspaces.map((ws, i) => (
                <div key={ws.workspace_id || i} className="flex items-center gap-2">
                  <span className="text-[10px] text-zinc-600 w-4">{i + 1}.</span>
                  <span className="text-xs text-zinc-300 flex-1 truncate">{ws.name}</span>
                  <Badge className="bg-zinc-800 text-zinc-400 text-[9px]">{ws.message_count?.toLocaleString()} msgs</Badge>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Agent usage */}
        {data.agent_usage?.length > 0 && (
          <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/60">
            <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">AI Agent Usage</h3>
            <div className="space-y-2">
              {data.agent_usage.map((a, i) => {
                const maxCount = data.agent_usage[0]?.messages || 1;
                return (
                  <div key={a.agent || i} className="flex items-center gap-2">
                    <span className="text-xs text-zinc-300 w-20 truncate">{a.agent || "Unknown"}</span>
                    <div className="flex-1 h-3 bg-zinc-800 rounded-full overflow-hidden">
                      <div className="h-full bg-blue-500/60 rounded-full" style={{ width: `${(a.messages / maxCount) * 100}%` }} />
                    </div>
                    <span className="text-[10px] text-zinc-500 w-12 text-right">{a.messages?.toLocaleString()}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Project completion */}
      {data.projects?.tasks > 0 && (
        <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/60">
          <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">Project Task Completion</h3>
          <div className="flex items-center gap-3">
            <div className="flex-1 h-4 bg-zinc-800 rounded-full overflow-hidden">
              <div className="h-full bg-emerald-500 rounded-full transition-all" style={{ width: `${Math.round((data.projects.tasks_done / data.projects.tasks) * 100)}%` }} />
            </div>
            <span className="text-sm font-medium text-zinc-300">
              {Math.round((data.projects.tasks_done / data.projects.tasks) * 100)}%
            </span>
            <span className="text-[10px] text-zinc-500">{data.projects.tasks_done}/{data.projects.tasks}</span>
          </div>
        </div>
      )}

      {/* Reporting Engine Metrics */}
      {reportData?.health && (
        <div className="space-y-4">
          <h3 className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">Platform Health (Real-Time)</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/20 text-center">
              <p className="text-xl font-bold text-emerald-400">{reportData.health.dau}</p><p className="text-[10px] text-zinc-500">DAU</p>
            </div>
            <div className="p-3 rounded-lg bg-blue-500/5 border border-blue-500/20 text-center">
              <p className="text-xl font-bold text-blue-400">{reportData.health.wau}</p><p className="text-[10px] text-zinc-500">WAU</p>
            </div>
            <div className="p-3 rounded-lg bg-purple-500/5 border border-purple-500/20 text-center">
              <p className="text-xl font-bold text-purple-400">{reportData.health.mau}</p><p className="text-[10px] text-zinc-500">MAU</p>
            </div>
            <div className="p-3 rounded-lg bg-amber-500/5 border border-amber-500/20 text-center">
              <p className="text-xl font-bold text-amber-400">{reportData.health.events_today}</p><p className="text-[10px] text-zinc-500">Events Today</p>
            </div>
          </div>
          {reportData.health.latency && (
            <div className="grid grid-cols-3 gap-3">
              <div className="p-3 rounded-lg bg-zinc-800/30 text-center">
                <p className="text-lg font-bold text-zinc-300">{reportData.health.latency.avg_ms}ms</p><p className="text-[10px] text-zinc-500">Avg Latency</p>
              </div>
              <div className="p-3 rounded-lg bg-zinc-800/30 text-center">
                <p className="text-lg font-bold text-zinc-300">{reportData.health.latency.p95_ms}ms</p><p className="text-[10px] text-zinc-500">p95 Latency</p>
              </div>
              <div className="p-3 rounded-lg bg-zinc-800/30 text-center">
                <p className="text-lg font-bold text-zinc-300">{reportData.health.latency.p99_ms}ms</p><p className="text-[10px] text-zinc-500">p99 Latency</p>
              </div>
            </div>
          )}
          {reportData.health.token_consumption && Object.keys(reportData.health.token_consumption).length > 0 && (
            <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/60">
              <h4 className="text-xs font-semibold text-zinc-400 mb-2">Token Usage by Provider</h4>
              {Object.entries(reportData.health.token_consumption).map(([provider, d]) => (
                <div key={provider} className="flex items-center justify-between py-1">
                  <span className="text-xs text-zinc-300 capitalize">{provider}</span>
                  <span className="text-xs text-zinc-500">{(d.tokens || 0).toLocaleString()} tokens (${(d.cost_usd || 0).toFixed(4)})</span>
                </div>
              ))}
            </div>
          )}
          {reportData.health.error_rates && Object.keys(reportData.health.error_rates).length > 0 && (
            <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/60">
              <h4 className="text-xs font-semibold text-zinc-400 mb-2">Error Rates by Provider</h4>
              {Object.entries(reportData.health.error_rates).map(([provider, d]) => (
                <div key={provider} className="flex items-center justify-between py-1">
                  <span className="text-xs text-zinc-300 capitalize">{provider}</span>
                  <span className={`text-xs ${d.rate > 5 ? "text-red-400" : "text-zinc-500"}`}>{d.rate}% ({d.errors}/{d.total})</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {reportData?.business && (
        <div className="space-y-4">
          <h3 className="text-xs font-semibold text-purple-400 uppercase tracking-wider">Business Intelligence</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/60">
              <h4 className="text-xs font-semibold text-zinc-400 mb-2">Feature Adoption</h4>
              {reportData.business.feature_adoption && Object.entries(reportData.business.feature_adoption).map(([feature, count]) => (
                <div key={feature} className="flex items-center justify-between py-0.5">
                  <span className="text-[11px] text-zinc-400 capitalize">{feature.replace("_", " ")}</span>
                  <span className="text-[11px] text-zinc-300">{count}</span>
                </div>
              ))}
            </div>
            <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/60">
              <h4 className="text-xs font-semibold text-zinc-400 mb-2">Churn Risk</h4>
              <p className="text-2xl font-bold text-amber-400">{reportData.business.churn_risk_users || 0}</p>
              <p className="text-[10px] text-zinc-500">Users at risk (low activity, 30 days)</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


export default function AdminDashboard({ user }) {
  const navigate = useNavigate();
  const { confirm: confirmAction, ConfirmDialog: ConfirmDlg } = useConfirm();
  const [loading, setLoading] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);
  const [activeTab, setActiveTab] = useState("overview");
  const [stats, setStats] = useState(null);
  const [bugs, setBugs] = useState([]);
  const [bugStats, setBugStats] = useState({});
  const [logs, setLogs] = useState([]);
  const [users, setUsers] = useState([]);
  const [selectedBug, setSelectedBug] = useState(null);
  const [bugFilter, setBugFilter] = useState({ status: "all", priority: "all" });
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);
  const [updatingRole, setUpdatingRole] = useState(null);
  const [organizations, setOrganizations] = useState([]);
  const [contextLedger, setContextLedger] = useState([]);
  const [contextStats, setContextStats] = useState(null);
  const [contextFilter, setContextFilter] = useState({ event_type: "" });
  const [recycleBin, setRecycleBin] = useState([]);
  const [recycleBinTotal, setRecycleBinTotal] = useState(0);
  const [duplicateOverrides, setDuplicateOverrides] = useState([]);
  const [duplicateStats, setDuplicateStats] = useState(null);
  const [diagnostics, setDiagnostics] = useState(null);
  const [systemHealth, setSystemHealth] = useState(null);

  useEffect(() => {
    checkAdminAndLoad();
  }, []);

  const checkAdminAndLoad = async () => {
    try {
      const res = await api.get("/admin/check");
      if (!res.data.is_super_admin && !res.data.is_staff) {
        toast.error("Access denied. Staff access required.");
        navigate("/dashboard");
        return;
      }
      setIsAdmin(true);
      setIsSuperAdmin(res.data.is_super_admin);
      await loadData();
    } catch (err) {
      toast.error("Failed to verify admin access");
      navigate("/dashboard");
    } finally {
      setLoading(false);
    }
  };

  const loadData = async () => {
    try {
      const [statsRes, bugsRes, logsRes, usersRes, orgsRes, ctxRes, ctxStatsRes, rbRes, dupRes, dupStatsRes, diagRes, systemHealthRes] = await Promise.all([
        api.get("/admin/stats"),
        api.get("/admin/bugs"),
        api.get("/admin/logs?limit=50"),
        api.get("/admin/users?limit=50"),
        api.get("/admin/organizations").catch(() => ({ data: { organizations: [] } })),
        api.get("/admin/context-ledger?limit=50").catch(() => ({ data: { entries: [] } })),
        api.get("/admin/context-ledger/stats").catch(() => ({ data: null })),
        api.get("/admin/recycle-bin?limit=50").catch(() => ({ data: { items: [], total: 0 } })),
        api.get("/admin/duplicate-overrides?limit=50").catch(() => ({ data: { overrides: [], total: 0 } })),
        api.get("/admin/duplicate-overrides/stats").catch(() => ({ data: null })),
        api.get("/admin/startup-diagnostics").catch(() => ({ data: null })),
        api.get("/admin/system-health").catch(() => ({ data: null })),
      ]);
      setStats(statsRes.data);
      setBugs(bugsRes.data.bugs || []);
      setBugStats(bugsRes.data.stats || {});
      setLogs(logsRes.data.logs || []);
      setUsers(usersRes.data.users || []);
      setOrganizations(orgsRes.data.organizations || []);
      setContextLedger(ctxRes.data.entries || []);
      setContextStats(ctxStatsRes.data);
      setRecycleBin(rbRes.data.items || []);
      setRecycleBinTotal(rbRes.data.total || 0);
      setDuplicateOverrides(dupRes.data.overrides || []);
      setDuplicateStats(dupStatsRes.data);
      setDiagnostics(diagRes.data);
      setSystemHealth(systemHealthRes.data);
    } catch (err) { handleSilent(err, "AdminDashboard:op1"); }
  };

  const updateBug = async (bugId, updates) => {
    try {
      await api.put(`/admin/bugs/${bugId}`, updates);
      toast.success("Bug updated");
      // Refresh bugs
      const res = await api.get("/admin/bugs");
      setBugs(res.data.bugs || []);
      setBugStats(res.data.stats || {});
      if (selectedBug?.bug_id === bugId) {
        setSelectedBug({ ...selectedBug, ...updates });
      }
    } catch (err) {
      toast.error("Failed to update bug");
    }
  };

  const formatDate = (iso) => {
    if (!iso) return "";
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit"
    });
  };

  const updateUserRole = async (userId, newRole) => {
    setUpdatingRole(userId);
    try {
      await api.put(`/admin/users/${userId}/role`, { platform_role: newRole });
      setUsers(users.map(u => u.user_id === userId ? { ...u, platform_role: newRole } : u));
      toast.success("Role updated");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to update role");
    } finally {
      setUpdatingRole(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-zinc-400" />
      </div>
    );
  }

  if (!isAdmin) return null;

  const filteredBugs = bugs.filter(bug => {
    if (bugFilter.status !== "all" && bug.status !== bugFilter.status) return false;
    if (bugFilter.priority !== "all" && bug.priority !== bugFilter.priority) return false;
    return true;
  });

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex" data-testid="admin-dashboard">
      {/* Left Sidebar */}
      <aside className="w-56 flex-shrink-0 border-r border-zinc-800 flex flex-col h-screen sticky top-0 bg-zinc-950">
        {/* Logo */}
        <div className="px-4 py-4 flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => navigate("/dashboard")} className="text-zinc-400 hover:text-zinc-100 p-1">
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <Shield className="w-5 h-5 text-amber-400" />
          <span className="text-sm font-semibold text-zinc-200">Admin</span>
        </div>

        {/* Nav items */}
        <nav className="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
          {[
            { key: "overview", label: "Overview", icon: BarChart3 },
            { key: "analytics", label: "Analytics", icon: TrendingUp },
            { key: "bugs", label: "Bug Reports", icon: Bug, badge: bugStats.open > 0 ? bugStats.open : null },
            { key: "users", label: "Users", icon: Users },
            { key: "orgs", label: "Organizations", icon: Building2 },
            { key: "context", label: "Context Ledger", icon: GitBranch },
            { key: "recycle", label: "Recycle Bin", icon: Archive },
            { key: "duplicates", label: "Duplicates", icon: Copy },
            { key: "diagnostics", label: "Diagnostics", icon: RefreshCw },
            { key: "system-health", label: "System Health", icon: Activity },
            { key: "logs", label: "Activity Logs", icon: Activity },
            { key: "audit", label: "Audit Log", icon: Shield },
            { key: "sso", label: "SSO / SAML", icon: Globe },
            { key: "errors", label: "Error Tracking", icon: Bug },
            { key: "managed-keys", label: "Platform Keys", icon: Key },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                activeTab === tab.key
                  ? "bg-zinc-800 text-zinc-100 font-medium"
                  : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50"
              }`}
              data-testid={`admin-tab-${tab.key}`}
            >
              <tab.icon className="w-4 h-4 flex-shrink-0" />
              <span className="truncate">{tab.label}</span>
              {tab.badge && (
                <Badge className="ml-auto bg-red-500/20 text-red-400 text-[10px]">{tab.badge}</Badge>
              )}
            </button>
          ))}
        </nav>

        {/* Refresh at bottom */}
        <div className="px-3 py-3 border-t border-zinc-800">
          <Button variant="ghost" size="sm" onClick={loadData} className="w-full justify-start text-zinc-500 hover:text-zinc-300 text-xs">
            <RefreshCw className="w-3.5 h-3.5 mr-2" /> Refresh Data
          </Button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto h-screen">
        <div className="px-6 py-6">

        {/* Overview Tab */}
        {activeTab === "overview" && stats && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard icon={Users} label="Total Users" value={stats.users.total} sub={`+${stats.users.this_week} this week`} />
            <StatCard icon={Folder} label="Workspaces" value={stats.workspaces.total} sub={`${stats.workspaces.active} active`} />
            <StatCard icon={MessageSquare} label="Messages" value={stats.messages.total} sub={`${stats.messages.today} today`} />
            <StatCard icon={Bug} label="Open Bugs" value={bugStats.open || 0} sub={`${bugStats.total || 0} total`} color="text-red-400" />
            <StatCard icon={Zap} label="AI Messages" value={stats.messages.ai} sub={`${stats.messages.human} human`} />
            <StatCard icon={FileText} label="Files" value={stats.files.total} />
            <StatCard icon={Activity} label="Task Sessions" value={stats.tasks.total} sub={`${stats.tasks.active} active`} />
            <StatCard icon={CheckCircle} label="Resolved Bugs" value={bugStats.resolved || 0} />
          </div>
        )}


        {/* Analytics Tab */}
        {activeTab === "analytics" && (
          <PlatformAnalytics />
        )}


        {/* Bugs Tab */}
        {activeTab === "bugs" && (
          <div className="flex gap-6">
            {/* Bug List */}
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-4">
                <Select value={bugFilter.status} onValueChange={(v) => setBugFilter({ ...bugFilter, status: v })}>
                  <SelectTrigger className="w-40 bg-zinc-900 border-zinc-800">
                    <SelectValue placeholder="All Status" />
                  </SelectTrigger>
                  <SelectContent className="bg-zinc-900 border-zinc-800">
                    <SelectItem value="all">All Status</SelectItem>
                    {Object.entries(STATUS_CONFIG).map(([k, v]) => (
                      <SelectItem key={k} value={k}>{v.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select value={bugFilter.priority} onValueChange={(v) => setBugFilter({ ...bugFilter, priority: v })}>
                  <SelectTrigger className="w-40 bg-zinc-900 border-zinc-800">
                    <SelectValue placeholder="All Priority" />
                  </SelectTrigger>
                  <SelectContent className="bg-zinc-900 border-zinc-800">
                    <SelectItem value="all">All Priority</SelectItem>
                    {Object.entries(PRIORITY_CONFIG).map(([k, v]) => (
                      <SelectItem key={k} value={k}>{v.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <span className="text-sm text-zinc-500">{filteredBugs.length} bugs</span>
              </div>

              <div className="space-y-2">
                {filteredBugs.map((bug) => {
                  const statusConf = STATUS_CONFIG[bug.status] || STATUS_CONFIG.open;
                  const priorityConf = PRIORITY_CONFIG[bug.priority] || PRIORITY_CONFIG.medium;
                  return (
                    <div
                      key={bug.bug_id}
                      onClick={() => setSelectedBug(bug)}
                      className={`p-4 rounded-lg border cursor-pointer transition-colors ${
                        selectedBug?.bug_id === bug.bug_id
                          ? "bg-zinc-800 border-zinc-700"
                          : "bg-zinc-900/50 border-zinc-800 hover:bg-zinc-900"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <h4 className="text-sm font-medium text-zinc-200 truncate">{bug.title}</h4>
                          <p className="text-xs text-zinc-500 mt-1">
                            {bug.submitter_name} · {formatDate(bug.created_at)}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge className={statusConf.color}>{statusConf.label}</Badge>
                          <span className={`text-xs ${priorityConf.color}`}>{priorityConf.label}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
                {filteredBugs.length === 0 && (
                  <div className="text-center py-8 text-zinc-500">No bugs found</div>
                )}
              </div>
            </div>

            {/* Bug Detail */}
            {selectedBug && (
              <div className="w-96 bg-zinc-900 border border-zinc-800 rounded-xl p-4">
                <h3 className="text-lg font-medium text-zinc-100 mb-4">{selectedBug.title}</h3>
                
                <div className="space-y-4">
                  <div>
                    <label className="text-xs text-zinc-500">Status</label>
                    <Select 
                      value={selectedBug.status} 
                      onValueChange={(v) => updateBug(selectedBug.bug_id, { status: v })}
                    >
                      <SelectTrigger className="mt-1 bg-zinc-950 border-zinc-800">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-zinc-900 border-zinc-800">
                        {Object.entries(STATUS_CONFIG).map(([k, v]) => (
                          <SelectItem key={k} value={k}>{v.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <label className="text-xs text-zinc-500">Priority</label>
                    <Select 
                      value={selectedBug.priority} 
                      onValueChange={(v) => updateBug(selectedBug.bug_id, { priority: v })}
                    >
                      <SelectTrigger className="mt-1 bg-zinc-950 border-zinc-800">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-zinc-900 border-zinc-800">
                        {Object.entries(PRIORITY_CONFIG).map(([k, v]) => (
                          <SelectItem key={k} value={k}>{v.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <label className="text-xs text-zinc-500">Description</label>
                    <p className="mt-1 text-sm text-zinc-300 bg-zinc-950 p-3 rounded-lg">
                      {selectedBug.description}
                    </p>
                  </div>

                  {selectedBug.steps_to_reproduce && (
                    <div>
                      <label className="text-xs text-zinc-500">Steps to Reproduce</label>
                      <p className="mt-1 text-sm text-zinc-400 bg-zinc-950 p-3 rounded-lg whitespace-pre-wrap">
                        {selectedBug.steps_to_reproduce}
                      </p>
                    </div>
                  )}

                  <div>
                    <label className="text-xs text-zinc-500">Admin Notes</label>
                    <Textarea
                      value={selectedBug.admin_notes || ""}
                      onChange={(e) => setSelectedBug({ ...selectedBug, admin_notes: e.target.value })}
                      onBlur={() => updateBug(selectedBug.bug_id, { admin_notes: selectedBug.admin_notes })}
                      placeholder="Internal notes..."
                      className="mt-1 bg-zinc-950 border-zinc-800 min-h-[80px]"
                    />
                  </div>

                  <div className="pt-2 border-t border-zinc-800 text-xs text-zinc-500">
                    <p>Reporter: {selectedBug.submitter_email}</p>
                    <p>Category: {selectedBug.category}</p>
                    <p>Browser: {selectedBug.browser?.slice(0, 50)}...</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Users Tab */}
        {activeTab === "users" && (
          <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
            <table className="w-full">
              <thead className="bg-zinc-900">
                <tr>
                  <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">User</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Email</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Role</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Provider</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Plan</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Joined</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800">
                {users.map((u) => {
                  const role = u.platform_role || "user";
                  const roleColors = {
                    super_admin: "bg-red-500/20 text-red-400",
                    admin: "bg-amber-500/20 text-amber-400",
                    platform_support: "bg-purple-500/20 text-purple-400",
                    moderator: "bg-blue-500/20 text-blue-400",
                    user: "bg-zinc-800 text-zinc-400",
                  };
                  const roleLabel = {
                    super_admin: "Super Admin",
                    admin: "Admin",
                    platform_support: "Platform Support",
                    moderator: "Moderator",
                    user: "User",
                  };
                  return (
                    <tr key={u.user_id} className="hover:bg-zinc-900/50" data-testid={`user-row-${u.user_id}`}>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          {u.picture ? (
                            <img src={u.picture} alt="" className="w-8 h-8 rounded-full" />
                          ) : (
                            <div className="w-8 h-8 rounded-full bg-zinc-700 flex items-center justify-center">
                              <Users className="w-4 h-4 text-zinc-400" />
                            </div>
                          )}
                          <span className="text-sm text-zinc-200">{u.name || "Unknown"}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm text-zinc-400">{u.email}</td>
                      <td className="px-4 py-3">
                        {isSuperAdmin ? (
                          <Select
                            value={role}
                            onValueChange={(v) => updateUserRole(u.user_id, v)}
                            disabled={updatingRole === u.user_id}
                          >
                            <SelectTrigger className={`w-36 h-7 text-xs border-0 ${roleColors[role]}`} data-testid={`role-select-${u.user_id}`}>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="bg-zinc-900 border-zinc-800">
                              <SelectItem value="super_admin">Super Admin</SelectItem>
                              <SelectItem value="admin">Admin</SelectItem>
                              <SelectItem value="platform_support">Platform Support</SelectItem>
                              <SelectItem value="moderator">Moderator</SelectItem>
                              <SelectItem value="user">User</SelectItem>
                            </SelectContent>
                          </Select>
                        ) : (
                          <Badge className={roleColors[role]} data-testid={`role-badge-${u.user_id}`}>
                            {roleLabel[role]}
                          </Badge>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <Badge className="bg-zinc-800 text-zinc-400">{u.auth_provider || u.auth_type || "email"}</Badge>
                      </td>
                      <td className="px-4 py-3">
                        {isSuperAdmin ? (
                          <select value={u.plan || "free"} onChange={async (e) => {
                            try { await api.put(`/admin/users/${u.user_id}/plan`, { plan: e.target.value }); toast.success(`Plan updated to ${e.target.value}`); loadData(); } catch (err) { handleError(err, "Admin:action"); }
                          }} className="bg-zinc-800 border border-zinc-700 rounded text-[10px] text-zinc-300 px-1.5 py-0.5" data-testid={`plan-select-${u.user_id}`}>
                            <option value="free">Free</option><option value="starter">Starter</option><option value="pro">Pro</option><option value="team">Team</option><option value="enterprise">Enterprise</option>
                          </select>
                        ) : (
                          <Badge className={u.plan === "enterprise" ? "bg-red-500/20 text-red-400" : u.plan === "pro" ? "bg-amber-500/20 text-amber-400" : "bg-zinc-800 text-zinc-400"}>{u.plan || "free"}</Badge>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-zinc-500">{formatDate(u.created_at)}</td>
                      <td className="px-4 py-3">
                        {isSuperAdmin && role !== "super_admin" && (
                          <button onClick={async () => { const ok = await confirmAction("Delete User", `Delete ${u.name || u.email}? This is permanent.`); if (!ok) return; try { await api.delete(`/admin/users/${u.user_id}`); toast.success("User deleted"); loadData(); } catch (err) { toast.error(err.response?.data?.detail || "Failed"); } }} className="p-1 rounded hover:bg-zinc-800 text-zinc-600 hover:text-red-400" data-testid={`delete-user-${u.user_id}`}>
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Organizations Tab */}
        {activeTab === "orgs" && (
          <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
            {organizations.length === 0 ? (
              <div className="text-center py-12 text-zinc-500">
                <Building2 className="w-10 h-10 mx-auto mb-3 text-zinc-700" />
                <p>No organizations registered yet</p>
              </div>
            ) : (
              <table className="w-full">
                <thead className="bg-zinc-900">
                  <tr>
                    <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Organization</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">URL</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Members</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Workspaces</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Plan</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Created</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Nexus AI</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800">
                  {organizations.map((org) => (
                    <tr key={org.org_id} className="hover:bg-zinc-900/50" data-testid={`org-row-${org.org_id}`}>
                      <td className="px-4 py-3 cursor-pointer" onClick={() => navigate(`/org/${org.slug}/dashboard`)}>
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-lg bg-zinc-800 flex items-center justify-center">
                            <Building2 className="w-4 h-4 text-zinc-400" />
                          </div>
                          <span className="text-sm text-zinc-200 font-medium hover:text-emerald-400">{org.name}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm text-zinc-400 font-mono">/org/{org.slug}</td>
                      <td className="px-4 py-3 text-sm text-zinc-400">{org.member_count || 0}</td>
                      <td className="px-4 py-3 text-sm text-zinc-400">{org.workspace_count || 0}</td>
                      <td className="px-4 py-3">
                        {isSuperAdmin ? (
                          <select value={org.plan || "free"} onChange={async (e) => {
                            try { await api.put(`/admin/organizations/${org.org_id}/plan`, { plan: e.target.value }); toast.success("Plan updated"); loadData(); } catch (err) { handleError(err, "Admin:action"); }
                          }} onClick={(e) => e.stopPropagation()} className="bg-zinc-800 border border-zinc-700 rounded text-[10px] text-zinc-300 px-1.5 py-0.5" data-testid={`org-plan-${org.org_id}`}>
                            <option value="free">Free</option><option value="starter">Starter</option><option value="pro">Pro</option><option value="team">Team</option><option value="enterprise">Enterprise</option>
                          </select>
                        ) : (
                          <Badge className={org.plan === "enterprise" ? "bg-red-500/20 text-red-400" : org.plan === "pro" ? "bg-amber-500/20 text-amber-400" : "bg-zinc-800 text-zinc-400"}>{org.plan || "free"}</Badge>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-zinc-500">{formatDate(org.created_at)}</td>
                      <td className="px-4 py-3">
                        {isSuperAdmin && (
                          <button
                            onClick={async (e) => {
                              e.stopPropagation();
                              const newVal = !org.nexus_ai_enabled;
                              try {
                                await api.put(`/admin/organizations/${org.org_id}/nexus-ai`, { enabled: newVal });
                                toast.success(`Nexus AI ${newVal ? 'enabled' : 'disabled'} for ${org.name}`);
                                loadData();
                              } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
                            }}
                            className={`px-2 py-1 rounded text-[10px] font-medium transition-colors ${org.nexus_ai_enabled ? 'bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30' : 'bg-zinc-800 text-zinc-600 hover:bg-zinc-700'}`}
                            data-testid={`nexus-ai-toggle-${org.org_id}`}
                          >
                            {org.nexus_ai_enabled ? 'Enabled' : 'Disabled'}
                          </button>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {isSuperAdmin && (
                          <button onClick={async (e) => { e.stopPropagation(); const ok = await confirmAction("Delete Organization", `Delete "${org.name}" and ALL its data?`); if (!ok) return; try { await api.delete(`/admin/organizations/${org.org_id}`); toast.success("Organization deleted"); loadData(); } catch (err) { toast.error(err.response?.data?.detail || "Failed"); } }} className="p-1 rounded hover:bg-zinc-800 text-zinc-600 hover:text-red-400" data-testid={`delete-org-${org.org_id}`}>
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {/* Context Ledger Tab */}
        {activeTab === "context" && (
          <div className="space-y-4" data-testid="context-ledger-panel">
            {/* Stats summary */}
            {contextStats && (
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
                {Object.entries(contextStats.by_type || {}).map(([key, count]) => (
                  <div key={key} className="p-3 rounded-lg bg-zinc-900/60 border border-zinc-800/40">
                    <p className="text-[10px] text-zinc-500 uppercase tracking-wider">{key.replace("_", " ")}</p>
                    <p className="text-lg font-bold text-zinc-200">{count}</p>
                  </div>
                ))}
              </div>
            )}

            {/* Filter */}
            <div className="flex items-center gap-2 mb-3">
              <select
                value={contextFilter.event_type}
                onChange={(e) => setContextFilter({ ...contextFilter, event_type: e.target.value })}
                className="bg-zinc-900 border border-zinc-800 rounded-md px-3 py-1.5 text-xs text-zinc-300"
                data-testid="context-filter-type"
              >
                <option value="">All Types</option>
                <option value="human_interrupt">Human Interrupt</option>
                <option value="context_switch">Context Switch</option>
                <option value="context_save">Context Save</option>
                <option value="context_resume">Context Resume</option>
                <option value="disagreement">Disagreement</option>
              </select>
              <span className="text-xs text-zinc-500">{contextLedger.length} entries</span>
              <button onClick={() => setContextFilter(f => ({ ...f, viewMode: f.viewMode === "timeline" ? "list" : "timeline" }))}
                className={`text-[10px] px-2 py-1 rounded ${contextFilter.viewMode === "timeline" ? "bg-indigo-500/20 text-indigo-400" : "text-zinc-500 hover:text-zinc-300 bg-zinc-800/40"}`}
                data-testid="context-timeline-toggle">
                {contextFilter.viewMode === "timeline" ? "List View" : "Timeline View"}
              </button>
            </div>

            {/* Timeline View */}
            {contextFilter.viewMode === "timeline" && contextLedger.length > 0 && (
              <div className="relative pl-6 border-l-2 border-zinc-800 space-y-3 mb-4" data-testid="context-timeline">
                {contextLedger
                  .filter(e => !contextFilter.event_type || e.event_type === contextFilter.event_type)
                  .map((entry, idx) => {
                  const dotColors = {
                    human_interrupt: "bg-amber-400",
                    context_switch: "bg-blue-400",
                    context_save: "bg-emerald-400",
                    context_resume: "bg-purple-400",
                    disagreement: "bg-red-400",
                  };
                  return (
                    <div key={entry.ledger_id} className="relative" data-testid={`timeline-entry-${entry.ledger_id}`}>
                      <div className={`absolute -left-[25px] top-1 w-3 h-3 rounded-full border-2 border-zinc-900 ${dotColors[entry.event_type] || "bg-zinc-500"}`} />
                      <div className="text-[9px] text-zinc-600 mb-0.5">{formatDate(entry.created_at)}</div>
                      <div className="flex items-center gap-1.5 mb-0.5">
                        <span className="text-xs font-medium text-zinc-300">{entry.agent_name}</span>
                        <span className="text-[9px] text-zinc-600">{(entry.event_type || "").replace("_", " ")}</span>
                        {entry.channel_name && <span className="text-[9px] text-zinc-700">in #{entry.channel_name}</span>}
                      </div>
                      {entry.trigger && <p className="text-[10px] text-zinc-500">"{entry.trigger.substring(0, 120)}"</p>}
                      {entry.prior_work && <p className="text-[10px] text-zinc-600 italic">Was: {entry.prior_work.substring(0, 100)}</p>}
                    </div>
                  );
                })}
              </div>
            )}

            {/* Entries list */}
            <div className="space-y-2">
              {contextLedger
                .filter(e => !contextFilter.event_type || e.event_type === contextFilter.event_type)
                .map((entry) => {
                const typeColors = {
                  human_interrupt: "border-amber-500/30 bg-amber-500/5",
                  context_switch: "border-blue-500/30 bg-blue-500/5",
                  context_save: "border-emerald-500/30 bg-emerald-500/5",
                  context_resume: "border-purple-500/30 bg-purple-500/5",
                  disagreement: "border-red-500/30 bg-red-500/5",
                };
                const typeBadgeColors = {
                  human_interrupt: "bg-amber-500/20 text-amber-400",
                  context_switch: "bg-blue-500/20 text-blue-400",
                  context_save: "bg-emerald-500/20 text-emerald-400",
                  context_resume: "bg-purple-500/20 text-purple-400",
                  disagreement: "bg-red-500/20 text-red-400",
                };
                return (
                  <div key={entry.ledger_id} className={`p-3 rounded-lg border ${typeColors[entry.event_type] || "border-zinc-800 bg-zinc-900/30"}`} data-testid={`context-entry-${entry.ledger_id}`}>
                    <div className="flex items-center gap-2 mb-1.5">
                      <Badge className={`text-[9px] ${typeBadgeColors[entry.event_type] || "bg-zinc-700 text-zinc-400"}`}>
                        {(entry.event_type || "").replace("_", " ")}
                      </Badge>
                      <span className="text-xs font-medium text-zinc-300">{entry.agent_name}</span>
                      <span className="text-[10px] text-zinc-600">in #{entry.channel_name || entry.channel_id}</span>
                      {entry.project_name && <span className="text-[10px] text-zinc-600">/ {entry.project_name}</span>}
                      <span className="text-[10px] text-zinc-600 ml-auto">{formatDate(entry.created_at)}</span>
                    </div>
                    {entry.trigger && (
                      <p className="text-xs text-zinc-400 mb-1">
                        <span className="text-zinc-600">Trigger ({entry.trigger_source}):</span> {entry.trigger.substring(0, 200)}
                      </p>
                    )}
                    {entry.prior_work && (
                      <p className="text-xs text-zinc-500">
                        <span className="text-zinc-600">Prior work:</span> {entry.prior_work.substring(0, 200)}
                      </p>
                    )}
                    {entry.response_summary && (
                      <p className="text-xs text-zinc-500 mt-1">
                        <span className="text-zinc-600">Response:</span> {entry.response_summary.substring(0, 200)}
                      </p>
                    )}
                  </div>
                );
              })}
              {contextLedger.length === 0 && (
                <div className="text-center py-8">
                  <GitBranch className="w-8 h-8 text-zinc-800 mx-auto mb-2" />
                  <p className="text-sm text-zinc-600">No context switches recorded yet</p>
                  <p className="text-xs text-zinc-700 mt-1">Context entries appear when agents switch between tasks, respond to human input, or disagree with each other</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Recycle Bin Tab */}
        {activeTab === "recycle" && <RecycleBinTab recycleBin={recycleBin} recycleBinTotal={recycleBinTotal} loadData={loadData} confirmAction={confirmAction} />}

        {/* Duplicates Tab */}
        {activeTab === "duplicates" && (
          <div className="space-y-3" data-testid="duplicates-panel">
            {duplicateStats && (
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-3">
                {Object.entries(duplicateStats.by_type || {}).map(([key, count]) => (
                  <div key={key} className="p-3 rounded-lg bg-zinc-900/60 border border-zinc-800/40">
                    <p className="text-[10px] text-zinc-500 uppercase tracking-wider">{key}</p>
                    <p className="text-lg font-bold text-zinc-200">{count}</p>
                  </div>
                ))}
              </div>
            )}
            {duplicateOverrides.length === 0 ? (
              <div className="text-center py-8"><Copy className="w-8 h-8 text-zinc-800 mx-auto mb-2" /><p className="text-sm text-zinc-600">No duplicate overrides yet</p></div>
            ) : duplicateOverrides.map(ov => (
              <div key={ov.override_id} className="p-3 rounded-lg bg-amber-500/5 border border-amber-500/20" data-testid={`dup-${ov.override_id}`}>
                <div className="flex items-center gap-2 mb-1">
                  <Badge className="bg-amber-500/20 text-amber-400 text-[9px]">{ov.entity_type}</Badge>
                  <span className="text-xs font-medium text-zinc-300">"{ov.entity_name}"</span>
                  <span className="text-[10px] text-zinc-600">duplicates "{ov.existing_name}" ({Math.round(ov.similarity_score * 100)}%)</span>
                </div>
                <p className="text-[10px] text-zinc-400 mb-1"><span className="text-zinc-600">Agent:</span> {ov.agent_name}</p>
                <p className="text-[10px] text-emerald-400/80"><span className="text-zinc-600">Justification:</span> {ov.justification}</p>
                <p className="text-[10px] text-zinc-600 mt-1">{formatDate(ov.created_at)}</p>
              </div>
            ))}
          </div>
        )}

        {activeTab === "diagnostics" && diagnostics && (
          <div className="space-y-4" data-testid="startup-diagnostics-panel">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <StatCard icon={RefreshCw} label="Startup Ready" value={diagnostics.startup_probe?.ready ? 1 : 0} sub={diagnostics.startup_probe?.ready ? "Ready" : "Not ready"} color={diagnostics.startup_probe?.ready ? "text-emerald-400" : "text-amber-400"} />
              <StatCard icon={Shield} label="Duplicate Routes" value={diagnostics.routes?.duplicates?.length || 0} sub="Should be 0" color={(diagnostics.routes?.duplicates?.length || 0) === 0 ? "text-emerald-400" : "text-red-400"} />
              <StatCard icon={Activity} label="Media Routes" value={diagnostics.routes?.media_route_count || 0} sub="Registered" />
              <StatCard icon={Key} label="Workspace Tools" value={diagnostics.routes?.workspace_tools_endpoint ? 1 : 0} sub={diagnostics.routes?.workspace_tools_endpoint ? "Present" : "Missing"} color={diagnostics.routes?.workspace_tools_endpoint ? "text-emerald-400" : "text-red-400"} />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/60">
                <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">Core Checks</h3>
                <div className="space-y-2 text-xs">
                  <div className="flex items-center justify-between"><span className="text-zinc-400">Database</span><span className={diagnostics.database?.status === "ok" ? "text-emerald-400" : "text-red-400"}>{diagnostics.database?.status || "unknown"}</span></div>
                  <div className="flex items-center justify-between"><span className="text-zinc-400">Redis</span><span className={diagnostics.redis?.status === "operational" || diagnostics.redis?.status === "disabled" ? "text-emerald-400" : "text-amber-400"}>{diagnostics.redis?.status || "unknown"}</span></div>
                  <div className="flex items-center justify-between"><span className="text-zinc-400">routes_media wildcard import</span><span className={diagnostics.registration?.routes_media_wildcard_present ? "text-red-400" : "text-emerald-400"}>{diagnostics.registration?.routes_media_wildcard_present ? "present" : "removed"}</span></div>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/60">
                <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">Duplicate Routes</h3>
                {(diagnostics.routes?.duplicates || []).length === 0 ? (
                  <p className="text-xs text-emerald-400">No duplicate route registrations detected.</p>
                ) : (
                  <div className="space-y-2">
                    {(diagnostics.routes?.duplicates || []).map((item) => (
                      <div key={item.route} className="text-xs text-zinc-400 flex items-center justify-between">
                        <span className="font-mono truncate mr-3">{item.route}</span>
                        <span className="text-red-400">x{item.count}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === "system-health" && systemHealth && (
          <div className="space-y-4" data-testid="system-health-panel">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <StatCard icon={Activity} label="DB Ping" value={systemHealth.database?.ping_ms || 0} sub="ms" color="text-cyan-400" />
              <StatCard icon={BarChart3} label="Collections" value={systemHealth.database?.collections || 0} sub={`${systemHealth.database?.objects || 0} objects`} />
              <StatCard icon={Folder} label="Storage" value={systemHealth.database?.storage_size_mb || 0} sub="MB" color="text-amber-400" />
              <StatCard icon={Key} label="Indexes" value={systemHealth.database?.index_size_mb || 0} sub="MB" color="text-emerald-400" />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/60">
                <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">System Load</h3>
                <div className="space-y-2 text-xs">
                  <div className="flex items-center justify-between"><span className="text-zinc-400">CPU</span><span className="text-zinc-200">{systemHealth.system?.cpu_percent ?? 0}%</span></div>
                  <div className="flex items-center justify-between"><span className="text-zinc-400">Memory Used</span><span className="text-zinc-200">{systemHealth.system?.memory_used_pct ?? 0}%</span></div>
                  <div className="flex items-center justify-between"><span className="text-zinc-400">Memory Available</span><span className="text-zinc-200">{systemHealth.system?.memory_available_mb ?? 0} MB</span></div>
                  <div className="flex items-center justify-between"><span className="text-zinc-400">Disk Used</span><span className="text-zinc-200">{systemHealth.system?.disk_used_pct ?? 0}%</span></div>
                  <div className="flex items-center justify-between"><span className="text-zinc-400">Disk Free</span><span className="text-zinc-200">{systemHealth.system?.disk_free_gb ?? 0} GB</span></div>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/60">
                <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">Query Health</h3>
                <div className="space-y-2">
                  {(systemHealth.query_probes || []).map((probe) => (
                    <div key={probe.name} className="flex items-center justify-between text-xs">
                      <span className="text-zinc-400">{probe.name}</span>
                      <span className={probe.status === "healthy" ? "text-emerald-400" : probe.status === "warning" ? "text-amber-400" : probe.status === "slow" ? "text-red-400" : "text-red-400"}>
                        {probe.latency_ms != null ? `${probe.latency_ms} ms` : probe.status}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/60">
                <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">Largest Collections</h3>
                <div className="space-y-2">
                  {(systemHealth.collections || []).slice(0, 8).map((item) => (
                    <div key={item.name} className="grid grid-cols-[1fr_auto_auto] gap-3 text-xs">
                      <span className="text-zinc-300 truncate">{item.name}</span>
                      <span className="text-zinc-500">{item.count} docs</span>
                      <span className="text-zinc-400">{item.storage_mb} MB</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/60">
                <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">Index Coverage</h3>
                <div className="space-y-2">
                  {(systemHealth.index_overview || []).map((item) => (
                    <div key={item.name} className="grid grid-cols-[1fr_auto_auto] gap-3 text-xs">
                      <span className="text-zinc-300 truncate">{item.name}</span>
                      <span className="text-zinc-500">{item.indexes} idx</span>
                      <span className={item.coverage === "strong" ? "text-emerald-400" : item.coverage === "moderate" ? "text-amber-400" : "text-red-400"}>{item.coverage}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === "logs" && (
          <div className="space-y-2">
            {logs.map((log) => {
              // Format log data into human-readable text
              const formatLogData = (data, eventType) => {
                if (!data || Object.keys(data).length === 0) return null;
                const parts = [];
                if (data.target_user_id) parts.push(`User: ${data.target_user_name || data.target_user_id}`);
                if (data.new_role) parts.push(`Role → ${data.new_role}`);
                if (data.old_role) parts.push(`(was ${data.old_role})`);
                if (data.workspace_name) parts.push(`Workspace: ${data.workspace_name}`);
                if (data.org_name) parts.push(`Org: ${data.org_name}`);
                if (data.plan) parts.push(`Plan: ${data.plan}`);
                if (data.action) parts.push(data.action);
                if (data.reason) parts.push(`Reason: ${data.reason}`);
                if (parts.length === 0) {
                  // Fallback: format key-value pairs
                  Object.entries(data).forEach(([k, v]) => {
                    if (typeof v === "string" && v.length < 50) parts.push(`${k.replace(/_/g, " ")}: ${v}`);
                  });
                }
                return parts.join(" · ");
              };

              const eventLabels = {
                role_changed: "Role Changed", user_created: "User Created", workspace_created: "Workspace Created",
                login: "Login", logout: "Logout", plan_changed: "Plan Changed", org_created: "Org Created",
                settings_updated: "Settings Updated",
              };

              return (
                <div key={log.log_id} className="flex items-start gap-3 p-3 bg-zinc-900/50 border border-zinc-800 rounded-lg">
                  <Activity className="w-4 h-4 text-zinc-500 mt-0.5 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-zinc-300">{eventLabels[log.event_type] || log.event_type?.replace(/_/g, " ")}</span>
                      {log.user_name && <span className="text-xs text-zinc-500">by {log.user_name}</span>}
                    </div>
                    {log.data && Object.keys(log.data).length > 0 && (
                      <p className="text-xs text-zinc-500 mt-0.5">{formatLogData(log.data, log.event_type)}</p>
                    )}
                  </div>
                  <span className="text-[10px] text-zinc-600 flex-shrink-0">{formatDate(log.timestamp)}</span>
                </div>
              );
            })}
            {logs.length === 0 && (
              <div className="text-center py-8 text-zinc-500">No logs found</div>
            )}
          </div>
        )}

        {activeTab === "audit" && (
          <AuditLogViewer />
        )}

        {activeTab === "sso" && (
          <SSOConfigPanel />
        )}

        {activeTab === "errors" && (
          <ErrorTrackingPanel />
        )}
        {activeTab === "managed-keys" && (
          <ManagedKeysAdmin />
        )}
        </div>
      </main>
      <ConfirmDlg />
    </div>
  );
}

function StatCard({ icon: Icon, label, value, sub, color = "text-zinc-100" }) {
  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4">
      <div className="flex items-center gap-3 mb-3">
        <Icon className="w-5 h-5 text-zinc-500" />
        <span className="text-sm text-zinc-400">{label}</span>
      </div>
      <div className={`text-2xl font-bold ${color}`}>{value?.toLocaleString() || 0}</div>
      {sub && <p className="text-xs text-zinc-500 mt-1">{sub}</p>}
    </div>
  );
}


function RecycleBinTab({ recycleBin: initialItems, recycleBinTotal, loadData, confirmAction }) {
  const [items, setItems] = useState(initialItems);
  const [types, setTypes] = useState([]);
  const [filterType, setFilterType] = useState("");
  const [selected, setSelected] = useState(new Set());
  const [bulkAction, setBulkAction] = useState(false);

  useEffect(() => { setItems(initialItems); }, [initialItems]);

  useEffect(() => {
    api.get("/admin/recycle-bin/types").then(r => setTypes(r.data.types || [])).catch(() => {});
  }, [initialItems]);

  useEffect(() => {
    if (filterType) {
      api.get(`/admin/recycle-bin?collection=${filterType}&limit=100`).then(r => setItems(r.data.items || [])).catch(() => {});
    } else {
      setItems(initialItems);
    }
    setSelected(new Set());
  }, [filterType, initialItems]);

  const toggleSelect = (binId) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(binId)) next.delete(binId);
      else next.add(binId);
      return next;
    });
  };

  const selectAll = () => {
    if (selected.size === items.length) setSelected(new Set());
    else setSelected(new Set(items.map(i => i.bin_id)));
  };

  const bulkRestore = async () => {
    if (selected.size === 0) return;
    setBulkAction(true);
    try {
      const res = await api.post("/admin/recycle-bin/bulk-restore", { bin_ids: [...selected] });
      toast.success(`${res.data.restored} item(s) restored`);
      setSelected(new Set());
      loadData();
    } catch (err) { toast.error("Bulk restore failed"); }
    setBulkAction(false);
  };

  const bulkPurge = async () => {
    if (selected.size === 0) return;
    const ok = await confirmAction("Bulk Purge", `Permanently delete ${selected.size} item(s)?`);
    if (!ok) return;
    setBulkAction(true);
    try {
      const res = await api.post("/admin/recycle-bin/bulk-purge", { bin_ids: [...selected] });
      toast.success(`${res.data.purged} item(s) purged`);
      setSelected(new Set());
      loadData();
    } catch (err) { toast.error("Bulk purge failed"); }
    setBulkAction(false);
  };

  const typeColors = {
    projects: "bg-blue-500/20 text-blue-400",
    project_tasks: "bg-purple-500/20 text-purple-400",
    milestones: "bg-amber-500/20 text-amber-400",
    artifacts: "bg-emerald-500/20 text-emerald-400",
    wiki_pages: "bg-cyan-500/20 text-cyan-400",
    repo_files: "bg-orange-500/20 text-orange-400",
    channels: "bg-pink-500/20 text-pink-400",
    workspaces: "bg-red-500/20 text-red-400",
    messages: "bg-zinc-500/20 text-zinc-400",
  };

  return (
    <div className="space-y-3" data-testid="recycle-bin-panel">
      {/* Filter bar + bulk actions */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <p className="text-xs text-zinc-500">{recycleBinTotal} deleted items</p>
          {/* Type filter */}
          <div className="flex items-center gap-1">
            <button onClick={() => setFilterType("")} className={`px-2 py-1 text-[10px] rounded border transition-colors ${!filterType ? "bg-zinc-700 border-zinc-600 text-zinc-200" : "bg-zinc-900 border-zinc-800 text-zinc-500 hover:text-zinc-300"}`}>All</button>
            {types.map(t => (
              <button key={t.type} onClick={() => setFilterType(t.type)} className={`px-2 py-1 text-[10px] rounded border transition-colors ${filterType === t.type ? "bg-zinc-700 border-zinc-600 text-zinc-200" : "bg-zinc-900 border-zinc-800 text-zinc-500 hover:text-zinc-300"}`}>
                {t.type} ({t.count})
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {items.length > 0 && (
            <button onClick={selectAll} className="text-[10px] text-zinc-400 hover:text-zinc-200 underline" data-testid="select-all-btn">
              {selected.size === items.length ? "Deselect All" : "Select All"}
            </button>
          )}
          {recycleBinTotal > 0 && (
            <Button size="sm" variant="outline" className="border-red-500/30 text-red-400 hover:bg-red-500/10 text-xs" data-testid="purge-all-btn"
              onClick={async () => {
                const ok = await confirmAction("Purge All", `Permanently delete ALL ${filterType || "items"}?`);
                if (!ok) return;
                try { await api.delete(`/admin/recycle-bin${filterType ? `?collection=${filterType}` : ""}`); toast.success("Purged"); loadData(); } catch (err) { toast.error("Purge failed"); }
              }}>
              <Trash2 className="w-3 h-3 mr-1" /> Purge {filterType || "All"}
            </Button>
          )}
        </div>
      </div>

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div className="flex items-center gap-2 p-2 bg-zinc-800/80 rounded-lg border border-zinc-700/50" data-testid="bulk-actions">
          <span className="text-xs text-zinc-300 font-medium">{selected.size} selected</span>
          <Button size="sm" onClick={bulkRestore} disabled={bulkAction} className="bg-emerald-600 hover:bg-emerald-700 h-7 text-xs" data-testid="bulk-restore-btn">
            <RotateCw className="w-3 h-3 mr-1" /> Restore Selected
          </Button>
          <Button size="sm" onClick={bulkPurge} disabled={bulkAction} variant="outline" className="border-red-500/30 text-red-400 hover:bg-red-500/10 h-7 text-xs" data-testid="bulk-purge-btn">
            <Trash2 className="w-3 h-3 mr-1" /> Purge Selected
          </Button>
          <button onClick={() => setSelected(new Set())} className="text-[10px] text-zinc-500 hover:text-zinc-300 ml-auto">Clear</button>
        </div>
      )}

      {/* Items list */}
      {items.length === 0 ? (
        <div className="text-center py-8"><Archive className="w-8 h-8 text-zinc-800 mx-auto mb-2" /><p className="text-sm text-zinc-600">{filterType ? `No ${filterType} items in recycle bin` : "Recycle bin is empty"}</p></div>
      ) : items.map(item => (
        <div key={item.bin_id} className={`p-3 rounded-lg border transition-colors ${selected.has(item.bin_id) ? "bg-zinc-800/60 border-cyan-500/30" : "bg-zinc-900/50 border-zinc-800/40"}`} data-testid={`bin-item-${item.bin_id}`}>
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-2">
              <input type="checkbox" checked={selected.has(item.bin_id)} onChange={() => toggleSelect(item.bin_id)}
                className="w-3.5 h-3.5 rounded border-zinc-600 bg-zinc-800 text-cyan-500 focus:ring-cyan-500 cursor-pointer" data-testid={`bin-check-${item.bin_id}`} />
              <Badge className={`text-[9px] ${typeColors[item.collection] || "bg-zinc-700 text-zinc-400"}`}>{item.collection}</Badge>
              <span className="text-xs font-medium text-zinc-300">{item.original_data?.name || item.original_data?.title || item.id_value}</span>
            </div>
            <div className="flex items-center gap-1">
              <Button size="sm" variant="ghost" className="h-6 text-[10px] text-emerald-400 hover:bg-emerald-500/10" data-testid={`restore-${item.bin_id}`}
                onClick={async () => { try { await api.post(`/admin/recycle-bin/${item.bin_id}/restore`); toast.success("Restored"); loadData(); } catch (err) { toast.error("Restore failed"); } }}>
                <RotateCw className="w-3 h-3 mr-1" /> Restore
              </Button>
              <Button size="sm" variant="ghost" className="h-6 text-[10px] text-red-400 hover:bg-red-500/10" data-testid={`purge-${item.bin_id}`}
                onClick={async () => { const ok = await confirmAction("Purge Item", "Permanently delete this item?"); if (!ok) return; try { await api.delete(`/admin/recycle-bin/${item.bin_id}`); toast.success("Purged"); loadData(); } catch (err) { toast.error("Purge failed"); } }}>
                <Trash2 className="w-3 h-3 mr-1" /> Purge
              </Button>
            </div>
          </div>
          <div className="flex items-center gap-3 text-[10px] text-zinc-500 ml-6">
            <span>Deleted by {item.deleted_by_name}</span>
            <span>{new Date(item.deleted_at).toLocaleString()}</span>
            {item.workspace_id && <span className="text-zinc-600">{item.workspace_id}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}
