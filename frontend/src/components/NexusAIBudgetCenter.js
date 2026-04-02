import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Loader2, Save, Wallet, Building2, FolderKanban, ShieldAlert, History, ChevronDown, ChevronUp, Filter, CheckCircle, XCircle, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

const PROVIDERS = [
  ["chatgpt", "ChatGPT"], ["claude", "Claude"], ["gemini", "Gemini"], ["mistral", "Mistral"], ["deepseek", "DeepSeek"],
  ["perplexity", "Perplexity"], ["cohere", "Cohere"], ["groq", "Groq"], ["grok", "Grok"], ["mercury", "Mercury 2"],
  ["pi", "Pi"], ["manus", "Manus"], ["qwen", "Qwen"], ["kimi", "Kimi"], ["llama", "Llama"], ["glm", "GLM"],
  ["cursor", "Cursor"], ["notebooklm", "NotebookLM"], ["copilot", "GitHub Copilot"], ["google_drive", "Google Drive"],
  ["onedrive", "OneDrive"], ["dropbox", "Dropbox"], ["box", "Box"], ["telegram", "Telegram"], ["twitter", "Twitter/X"],
  ["linkedin", "LinkedIn"], ["youtube", "YouTube"], ["tiktok", "TikTok"], ["instagram", "Instagram"],
  ["slack", "Slack"], ["discord", "Discord"], ["msteams", "Microsoft Teams"], ["mattermost", "Mattermost"],
  ["whatsapp", "WhatsApp"], ["signal", "Signal"], ["zoom", "Zoom"], ["sendgrid", "SendGrid"], ["resend", "Resend"],
  ["meta", "Meta"], ["microsoft", "Microsoft OAuth"], ["cloudflare_r2", "Cloudflare R2"], ["cloudflare_kv", "Cloudflare KV"],
  ["cloudflare_ai_gateway", "CF AI Gateway"], ["github", "GitHub"], ["paypal", "PayPal"],
];

const ScopePanel = ({ title, icon: Icon, scopeType, scopeId, endpointBase, selectableOptions, selectedId, onSelectId, canEdit }) => {
  const [budgets, setBudgets] = useState({});
  const [dashboard, setDashboard] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [alertsExpanded, setAlertsExpanded] = useState(false);
  const [alertsLimit, setAlertsLimit] = useState(5);

  const load = async () => {
    if (!scopeId) return;
    setLoading(true);
    try {
      const [budgetRes, dashboardRes, alertsRes] = await Promise.all([
        api.get(`${endpointBase}/budgets`),
        api.get(`${endpointBase}/dashboard`),
        api.get(`${endpointBase}/alerts`).catch(() => ({ data: { alerts: [] } })),
      ]);
      setBudgets(budgetRes.data?.budgets || {});
      setDashboard(dashboardRes.data || null);
      setAlerts(alertsRes.data?.alerts || []);
    } catch (err) {
      toast.error(err?.response?.data?.detail || `Failed to load ${title.toLowerCase()}`);
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, [scopeId, endpointBase]);

  const updateBudget = (provider, patch) => {
    setBudgets(prev => ({ ...prev, [provider]: { ...(prev[provider] || {}), ...patch } }));
  };

  const save = async () => {
    if (!scopeId || !canEdit) return;
    setSaving(true);
    try {
      await api.put(`${endpointBase}/budgets`, { budgets });
      toast.success(`${title} budgets saved`);
      await load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || `Failed to save ${title.toLowerCase()}`);
    }
    setSaving(false);
  };

  return (
    <div className="p-5 rounded-xl bg-zinc-900/40 border border-zinc-800/60 space-y-4" data-testid={`${scopeType}-budget-panel`}>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-cyan-400" />
          <div>
            <h3 className="text-sm font-semibold text-zinc-200">{title} Budgets</h3>
            <p className="text-[11px] text-zinc-500">Per-provider monthly warning threshold and hard cap.</p>
          </div>
        </div>
        {selectableOptions?.length > 0 && (
          <select
            value={selectedId || ""}
            onChange={(e) => onSelectId?.(e.target.value)}
            className="bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-300"
            data-testid={`${scopeType}-budget-select`}
          >
            {selectableOptions.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
          </select>
        )}
      </div>

      {dashboard && (
        <div className="flex items-center gap-3 flex-wrap">
          <Badge className="bg-cyan-500/15 text-cyan-400 text-[10px]">Month: {dashboard.month_key}</Badge>
          <span className="text-xs text-zinc-400" data-testid={`${scopeType}-budget-total-cost`}>Total cost: ${Number(dashboard.total_cost_usd || 0).toFixed(4)}</span>
          <span className="text-xs text-zinc-500">Events: {dashboard.total_events || 0}</span>
          {!canEdit && <span className="text-[11px] text-amber-400">Read only</span>}
        </div>
      )}

      {loading ? (
        <div className="py-8 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-zinc-500" /></div>
      ) : (
        <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1">
          {PROVIDERS.map(([provider, label]) => {
            const cfg = budgets[provider] || {};
            const usage = dashboard?.providers?.[provider] || {};
            const status = usage.status || "ok";
            return (
              <div key={provider} className="grid grid-cols-1 lg:grid-cols-[1.2fr_100px_100px_90px_120px] gap-2 items-center p-3 rounded-lg bg-zinc-950/60 border border-zinc-800/40" data-testid={`${scopeType}-budget-row-${provider}`}>
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-medium text-zinc-200">{label}</span>
                    <Badge className={`text-[9px] ${status === "blocked" ? "bg-red-500/20 text-red-400" : status === "warning" ? "bg-amber-500/20 text-amber-400" : "bg-zinc-800 text-zinc-500"}`}>{status}</Badge>
                  </div>
                  <p className="text-[10px] text-zinc-500">Current: ${Number(usage.current_cost_usd || 0).toFixed(4)} · Calls: {usage.events || 0}</p>
                </div>
                <Input
                  value={cfg.warn_threshold_usd ?? ""}
                  onChange={(e) => updateBudget(provider, { warn_threshold_usd: e.target.value })}
                  placeholder="Warn $"
                  disabled={!canEdit}
                  className="bg-zinc-900 border-zinc-800 text-xs h-8"
                  data-testid={`${scopeType}-warn-${provider}`}
                />
                <Input
                  value={cfg.hard_cap_usd ?? ""}
                  onChange={(e) => updateBudget(provider, { hard_cap_usd: e.target.value })}
                  placeholder="Cap $"
                  disabled={!canEdit}
                  className="bg-zinc-900 border-zinc-800 text-xs h-8"
                  data-testid={`${scopeType}-hardcap-${provider}`}
                />
                <label className="flex items-center gap-2 text-xs text-zinc-400" data-testid={`${scopeType}-enabled-${provider}`}>
                  <input type="checkbox" checked={!!cfg.enabled} disabled={!canEdit} onChange={(e) => updateBudget(provider, { enabled: e.target.checked })} className="rounded border-zinc-700 bg-zinc-900" />
                  On
                </label>
                <div className="text-[10px] text-zinc-500 text-right lg:text-left">
                  Warn @ {cfg.warn_threshold_usd || "—"}<br />Cap @ {cfg.hard_cap_usd || "—"}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {alerts.length > 0 && (
        <div className="rounded-lg border border-zinc-800/60 bg-zinc-950/40 p-3" data-testid={`${scopeType}-budget-alerts`}>
          <button
            onClick={() => setAlertsExpanded(!alertsExpanded)}
            className="w-full flex items-center justify-between text-[10px] font-semibold uppercase tracking-wider text-zinc-500 mb-2 hover:text-zinc-300 transition-colors"
            data-testid={`${scopeType}-alerts-toggle`}
          >
            <span className="flex items-center gap-1.5">
              <AlertTriangle className="w-3 h-3" />
              Recent Alerts ({alerts.length})
            </span>
            {alertsExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
          {alertsExpanded && (
            <div className="space-y-2">
              {alerts.slice(0, alertsLimit).map(alert => (
                <div key={alert.alert_id || alert.alert_key} className={`flex items-start justify-between gap-3 text-xs p-2 rounded-lg ${alert.dismissed ? "opacity-50 bg-zinc-900/30" : "bg-zinc-900/60"}`} data-testid={`alert-${alert.alert_key}`}>
                  <div className="flex items-start gap-2 min-w-0">
                    {alert.alert_type === "blocked" ? <XCircle className="w-3.5 h-3.5 text-red-400 mt-0.5 shrink-0" /> : <AlertTriangle className="w-3.5 h-3.5 text-amber-400 mt-0.5 shrink-0" />}
                    <div className="min-w-0">
                      <p className={alert.alert_type === "blocked" ? "text-red-400 font-medium" : "text-amber-400 font-medium"}>{alert.provider} &middot; {alert.alert_type}</p>
                      {alert.message && <p className="text-zinc-400 mt-0.5 truncate">{alert.message}</p>}
                      <p className="text-zinc-500 mt-0.5">${Number(alert.current_spend_usd || 0).toFixed(4)} / {alert.threshold_usd != null ? `$${Number(alert.threshold_usd).toFixed(4)}` : "—"}</p>
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <span className="text-[10px] text-zinc-600">{new Date(alert.last_triggered_at).toLocaleString()}</span>
                    {alert.dismissed && <p className="text-[9px] text-zinc-600">Dismissed</p>}
                  </div>
                </div>
              ))}
              {alerts.length > alertsLimit && (
                <button onClick={() => setAlertsLimit(p => p + 10)} className="text-[10px] text-cyan-400 hover:text-cyan-300" data-testid={`${scopeType}-load-more-alerts`}>
                  Show more ({alerts.length - alertsLimit} remaining)
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {canEdit && (
        <Button onClick={save} disabled={saving || !scopeId} className="bg-cyan-600 hover:bg-cyan-500 text-white" data-testid={`${scopeType}-budget-save`}>
          {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
          Save {title} Budgets
        </Button>
      )}
    </div>
  );
};

const AlertHistoryPanel = () => {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [filterType, setFilterType] = useState("");
  const [filterProvider, setFilterProvider] = useState("");
  const limit = 15;

  const load = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit, offset });
      if (filterType) params.set("alert_type", filterType);
      if (filterProvider) params.set("provider", filterProvider);
      const res = await api.get(`/admin/managed-keys/alerts/history?${params}`);
      setAlerts(res.data?.alerts || []);
      setTotal(res.data?.total || 0);
    } catch (err) {
      toast.error("Failed to load alert history");
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, [offset, filterType, filterProvider]);

  const dismiss = async (alertKey) => {
    try {
      await api.put(`/admin/managed-keys/alerts/${encodeURIComponent(alertKey)}/dismiss`);
      setAlerts(prev => prev.map(a => a.alert_key === alertKey ? { ...a, dismissed: true } : a));
      toast.success("Alert dismissed");
    } catch {
      toast.error("Failed to dismiss alert");
    }
  };

  return (
    <div className="p-5 rounded-xl bg-zinc-900/40 border border-zinc-800/60 space-y-4" data-testid="alert-history-panel">
      <div className="flex items-center gap-2">
        <History className="w-4 h-4 text-cyan-400" />
        <div>
          <h3 className="text-sm font-semibold text-zinc-200">Alert History</h3>
          <p className="text-[11px] text-zinc-500">All budget alerts across scopes. {total} total alerts.</p>
        </div>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <Filter className="w-3.5 h-3.5 text-zinc-500" />
        <select value={filterType} onChange={e => { setFilterType(e.target.value); setOffset(0); }} className="bg-zinc-950 border border-zinc-800 rounded-lg px-2 py-1 text-xs text-zinc-300" data-testid="alert-history-filter-type">
          <option value="">All types</option>
          <option value="warning">Warning</option>
          <option value="blocked">Blocked</option>
        </select>
        <Input value={filterProvider} onChange={e => { setFilterProvider(e.target.value); setOffset(0); }} placeholder="Filter provider..." className="bg-zinc-900 border-zinc-800 text-xs h-7 w-40" data-testid="alert-history-filter-provider" />
      </div>

      {loading ? (
        <div className="py-6 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-zinc-500" /></div>
      ) : alerts.length === 0 ? (
        <p className="text-xs text-zinc-500 py-4 text-center">No alerts found.</p>
      ) : (
        <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
          {alerts.map(alert => (
            <div key={alert.alert_key} className={`flex items-start justify-between gap-3 text-xs p-3 rounded-lg border ${alert.dismissed ? "opacity-50 border-zinc-800/30 bg-zinc-950/30" : alert.alert_type === "blocked" ? "border-red-500/20 bg-red-500/5" : "border-amber-500/20 bg-amber-500/5"}`} data-testid={`history-alert-${alert.alert_key}`}>
              <div className="flex items-start gap-2 min-w-0 flex-1">
                {alert.alert_type === "blocked" ? <XCircle className="w-3.5 h-3.5 text-red-400 mt-0.5 shrink-0" /> : <AlertTriangle className="w-3.5 h-3.5 text-amber-400 mt-0.5 shrink-0" />}
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`font-medium ${alert.alert_type === "blocked" ? "text-red-400" : "text-amber-400"}`}>{alert.provider}</span>
                    <Badge className={`text-[9px] ${alert.alert_type === "blocked" ? "bg-red-500/20 text-red-400" : "bg-amber-500/20 text-amber-400"}`}>{alert.alert_type}</Badge>
                    <Badge className="bg-zinc-800 text-zinc-500 text-[9px]">{alert.scope_type}:{(alert.scope_id || "").substring(0, 12)}</Badge>
                  </div>
                  {alert.message && <p className="text-zinc-400 mt-1 break-words">{alert.message}</p>}
                  <p className="text-zinc-500 mt-0.5">${Number(alert.current_spend_usd || 0).toFixed(4)} spend &middot; Month: {alert.month_key}</p>
                </div>
              </div>
              <div className="text-right shrink-0 flex flex-col items-end gap-1">
                <span className="text-[10px] text-zinc-600">{new Date(alert.last_triggered_at).toLocaleString()}</span>
                {alert.dismissed ? (
                  <span className="text-[9px] text-zinc-600 flex items-center gap-0.5"><CheckCircle className="w-2.5 h-2.5" /> Dismissed</span>
                ) : (
                  <button onClick={() => dismiss(alert.alert_key)} className="text-[9px] text-zinc-500 hover:text-cyan-400 transition-colors" data-testid={`dismiss-${alert.alert_key}`}>Dismiss</button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {total > limit && (
        <div className="flex items-center justify-between text-xs text-zinc-500">
          <span>Showing {offset + 1}–{Math.min(offset + limit, total)} of {total}</span>
          <div className="flex gap-2">
            <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))} className="px-2 py-1 rounded bg-zinc-800 disabled:opacity-30 hover:bg-zinc-700 transition-colors" data-testid="alert-history-prev">Prev</button>
            <button disabled={offset + limit >= total} onClick={() => setOffset(offset + limit)} className="px-2 py-1 rounded bg-zinc-800 disabled:opacity-30 hover:bg-zinc-700 transition-colors" data-testid="alert-history-next">Next</button>
          </div>
        </div>
      )}
    </div>
  );
};

export const NexusAIBudgetCenter = () => {
  const [user, setUser] = useState(null);
  const [orgs, setOrgs] = useState([]);
  const [workspaces, setWorkspaces] = useState([]);
  const [selectedOrg, setSelectedOrg] = useState("");
  const [selectedWorkspace, setSelectedWorkspace] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [meRes, orgRes, wsRes] = await Promise.all([
          api.get("/auth/me"),
          api.get("/orgs/my-orgs").catch(() => ({ data: { organizations: [] } })),
          api.get("/workspaces").catch(() => ({ data: [] })),
        ]);
        const me = meRes.data || {};
        const orgOptions = (orgRes.data?.organizations || []).filter(org => ["org_owner", "org_admin"].includes(org.org_role));
        const workspaceOptions = (wsRes.data || []).map(ws => ({ ...ws, canEdit: me.platform_role === "super_admin" || ws.owner_id === me.user_id }));
        setUser(me);
        setOrgs(orgOptions);
        setWorkspaces(workspaceOptions);
        setSelectedOrg(orgOptions[0]?.org_id || "");
        setSelectedWorkspace(workspaceOptions[0]?.workspace_id || "");
      } catch {
        toast.error("Failed to load Nexus AI budget settings");
      }
      setLoading(false);
    };
    load();
  }, []);

  const orgOptions = useMemo(() => orgs.map(org => ({ value: org.org_id, label: org.name })), [orgs]);
  const workspaceOptions = useMemo(() => workspaces.map(ws => ({ value: ws.workspace_id, label: ws.name })), [workspaces]);
  const selectedWorkspaceMeta = workspaces.find(ws => ws.workspace_id === selectedWorkspace);

  if (loading) return <div className="p-6 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-zinc-500" /></div>;

  return (
    <div className="space-y-6" data-testid="nexus-ai-budget-center">
      <div className="p-5 rounded-xl bg-zinc-900/40 border border-zinc-800/60">
        <div className="flex items-center gap-2 mb-1">
          <Wallet className="w-4 h-4 text-cyan-400" />
          <h3 className="text-sm font-semibold text-zinc-200">Nexus AI Budget Controls</h3>
        </div>
        <p className="text-xs text-zinc-500">Workspace budgets override org budgets, and org budgets override platform budgets. Each provider/integration can have its own warning threshold and hard cap.</p>
        <div className="mt-3 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-[11px] text-emerald-300" data-testid="nexus-ai-budget-default-note">
          Default behavior: if a budget is not configured, Nexus does <span className="font-semibold">not</span> block usage. Budgets only apply when enabled. This is especially useful for Super Admin and Enterprise workflows. External provider/platform limits may still apply separately.
        </div>
      </div>

      {user?.platform_role === "super_admin" && (
        <ScopePanel title="Platform" icon={ShieldAlert} scopeType="platform" scopeId="platform" endpointBase="/admin/managed-keys" canEdit />
      )}

      {orgOptions.length > 0 && (
        <ScopePanel title="Organization" icon={Building2} scopeType="org" scopeId={selectedOrg} endpointBase={`/orgs/${selectedOrg}/nexus-ai`} selectableOptions={orgOptions} selectedId={selectedOrg} onSelectId={setSelectedOrg} canEdit />
      )}

      {workspaceOptions.length > 0 && (
        <ScopePanel title="Workspace" icon={FolderKanban} scopeType="workspace" scopeId={selectedWorkspace} endpointBase={`/workspaces/${selectedWorkspace}/nexus-ai`} selectableOptions={workspaceOptions} selectedId={selectedWorkspace} onSelectId={setSelectedWorkspace} canEdit={!!selectedWorkspaceMeta?.canEdit} />
      )}

      {user?.platform_role === "super_admin" && <AlertHistoryPanel />}
    </div>
  );
};

export default NexusAIBudgetCenter;