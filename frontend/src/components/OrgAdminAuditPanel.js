import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Loader2, Download, History, Users, DollarSign, Filter, ChevronLeft, ChevronRight } from "lucide-react";
import { toast } from "sonner";

const OrgAuditLog = ({ orgId }) => {
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [actionFilter, setActionFilter] = useState("");
  const [userFilter, setUserFilter] = useState("");
  const [actions, setActions] = useState([]);
  const [loading, setLoading] = useState(false);
  const limit = 20;

  useEffect(() => {
    if (!orgId) return;
    api.get(`/orgs/${orgId}/admin/audit-log/actions`).then(r => setActions(r.data?.actions || [])).catch(() => {});
  }, [orgId]);

  useEffect(() => {
    if (!orgId) return;
    setLoading(true);
    const params = new URLSearchParams({ limit, offset });
    if (actionFilter) params.set("action", actionFilter);
    if (userFilter) params.set("user_filter", userFilter);
    api.get(`/orgs/${orgId}/admin/audit-log?${params}`)
      .then(r => { setLogs(r.data?.logs || []); setTotal(r.data?.total || 0); })
      .catch(() => toast.error("Failed to load audit log"))
      .finally(() => setLoading(false));
  }, [orgId, offset, actionFilter, userFilter]);

  return (
    <div className="space-y-3" data-testid="org-audit-log">
      <div className="flex items-center gap-2 flex-wrap">
        <Filter className="w-3.5 h-3.5 text-zinc-500" />
        <select value={actionFilter} onChange={e => { setActionFilter(e.target.value); setOffset(0); }} className="bg-zinc-950 border border-zinc-800 rounded-lg px-2 py-1 text-xs text-zinc-300" data-testid="audit-action-filter">
          <option value="">All actions</option>
          {actions.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
        <Input value={userFilter} onChange={e => { setUserFilter(e.target.value); setOffset(0); }} placeholder="Filter by user ID..." className="bg-zinc-900 border-zinc-800 text-xs h-7 w-44" data-testid="audit-user-filter" />
      </div>
      {loading ? (
        <div className="py-6 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-zinc-500" /></div>
      ) : logs.length === 0 ? (
        <p className="text-xs text-zinc-500 text-center py-4">No audit logs found.</p>
      ) : (
        <div className="space-y-1.5 max-h-[400px] overflow-y-auto pr-1">
          {logs.map((log, i) => (
            <div key={log.audit_id || i} className="flex items-start justify-between gap-3 p-2.5 rounded-lg bg-zinc-950/60 border border-zinc-800/40 text-xs">
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge className="bg-zinc-800 text-zinc-400 text-[9px]">{log.action || "unknown"}</Badge>
                  <span className="text-zinc-500">{log.resource_type}</span>
                </div>
                <p className="text-zinc-400 mt-0.5 truncate">{log.user_id} &middot; {log.workspace_id || "org-level"}</p>
              </div>
              <span className="text-[10px] text-zinc-600 shrink-0">{log.timestamp ? new Date(log.timestamp).toLocaleString() : ""}</span>
            </div>
          ))}
        </div>
      )}
      {total > limit && (
        <div className="flex items-center justify-between text-xs text-zinc-500">
          <span>{offset + 1}–{Math.min(offset + limit, total)} of {total}</span>
          <div className="flex gap-1">
            <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))} className="p-1 rounded bg-zinc-800 disabled:opacity-30 hover:bg-zinc-700"><ChevronLeft className="w-3.5 h-3.5" /></button>
            <button disabled={offset + limit >= total} onClick={() => setOffset(offset + limit)} className="p-1 rounded bg-zinc-800 disabled:opacity-30 hover:bg-zinc-700"><ChevronRight className="w-3.5 h-3.5" /></button>
          </div>
        </div>
      )}
    </div>
  );
};

const OrgBudgetAudit = ({ orgId }) => {
  const [events, setEvents] = useState([]);
  const [total, setTotal] = useState(0);
  const [spendByProvider, setSpendByProvider] = useState({});
  const [offset, setOffset] = useState(0);
  const [providerFilter, setProviderFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const limit = 20;

  useEffect(() => {
    if (!orgId) return;
    setLoading(true);
    const params = new URLSearchParams({ limit, offset });
    if (providerFilter) params.set("provider", providerFilter);
    api.get(`/orgs/${orgId}/admin/budget-audit?${params}`)
      .then(r => {
        setEvents(r.data?.events || []);
        setTotal(r.data?.total || 0);
        setSpendByProvider(r.data?.spend_by_provider || {});
      })
      .catch(() => toast.error("Failed to load budget audit"))
      .finally(() => setLoading(false));
  }, [orgId, offset, providerFilter]);

  const topProviders = Object.entries(spendByProvider).sort((a, b) => b[1].cost_usd - a[1].cost_usd).slice(0, 8);

  return (
    <div className="space-y-3" data-testid="org-budget-audit">
      {topProviders.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {topProviders.map(([provider, data]) => (
            <button
              key={provider}
              onClick={() => { setProviderFilter(providerFilter === provider ? "" : provider); setOffset(0); }}
              className={`px-2.5 py-1 rounded-lg text-[10px] border transition-colors ${providerFilter === provider ? "border-cyan-500/40 bg-cyan-500/10 text-cyan-400" : "border-zinc-800 bg-zinc-950/60 text-zinc-400 hover:border-zinc-700"}`}
              data-testid={`budget-provider-${provider}`}
            >
              {provider}: ${data.cost_usd.toFixed(4)} ({data.events} calls)
            </button>
          ))}
        </div>
      )}
      {loading ? (
        <div className="py-6 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-zinc-500" /></div>
      ) : events.length === 0 ? (
        <p className="text-xs text-zinc-500 text-center py-4">No budget events found.</p>
      ) : (
        <div className="space-y-1.5 max-h-[400px] overflow-y-auto pr-1">
          {events.map((evt, i) => (
            <div key={evt.event_id || i} className="flex items-start justify-between gap-3 p-2.5 rounded-lg bg-zinc-950/60 border border-zinc-800/40 text-xs">
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-zinc-200 font-medium">{evt.provider}</span>
                  <Badge className="bg-zinc-800 text-zinc-500 text-[9px]">{evt.usage_type}</Badge>
                  <span className="text-emerald-400 font-mono">${Number(evt.cost_usd || 0).toFixed(6)}</span>
                </div>
                <p className="text-zinc-500 mt-0.5">{evt.user_id} &middot; {evt.tokens_in || 0} in / {evt.tokens_out || 0} out</p>
              </div>
              <span className="text-[10px] text-zinc-600 shrink-0">{evt.timestamp ? new Date(evt.timestamp).toLocaleString() : ""}</span>
            </div>
          ))}
        </div>
      )}
      {total > limit && (
        <div className="flex items-center justify-between text-xs text-zinc-500">
          <span>{offset + 1}–{Math.min(offset + limit, total)} of {total}</span>
          <div className="flex gap-1">
            <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))} className="p-1 rounded bg-zinc-800 disabled:opacity-30 hover:bg-zinc-700"><ChevronLeft className="w-3.5 h-3.5" /></button>
            <button disabled={offset + limit >= total} onClick={() => setOffset(offset + limit)} className="p-1 rounded bg-zinc-800 disabled:opacity-30 hover:bg-zinc-700"><ChevronRight className="w-3.5 h-3.5" /></button>
          </div>
        </div>
      )}
    </div>
  );
};

const OrgMemberActivity = ({ orgId }) => {
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!orgId) return;
    setLoading(true);
    api.get(`/orgs/${orgId}/admin/member-activity`)
      .then(r => setMembers(r.data?.members || []))
      .catch(() => toast.error("Failed to load member activity"))
      .finally(() => setLoading(false));
  }, [orgId]);

  if (loading) return <div className="py-6 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-zinc-500" /></div>;

  return (
    <div className="space-y-1.5 max-h-[400px] overflow-y-auto pr-1" data-testid="org-member-activity">
      {members.length === 0 ? (
        <p className="text-xs text-zinc-500 text-center py-4">No members found.</p>
      ) : (
        members.map(m => (
          <div key={m.user_id} className="flex items-center justify-between gap-3 p-2.5 rounded-lg bg-zinc-950/60 border border-zinc-800/40 text-xs">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-zinc-200 font-medium truncate">{m.name || m.email || m.user_id}</span>
                <Badge className="bg-zinc-800 text-zinc-500 text-[9px]">{m.org_role}</Badge>
              </div>
              <p className="text-zinc-500 mt-0.5">{m.email}</p>
            </div>
            <div className="text-right shrink-0">
              <p className="text-zinc-400">{m.messages_sent} msgs &middot; ${m.total_spend_usd.toFixed(4)}</p>
              {m.last_active && <p className="text-[10px] text-zinc-600">Last: {new Date(m.last_active).toLocaleDateString()}</p>}
            </div>
          </div>
        ))
      )}
    </div>
  );
};

export const OrgAdminAuditPanel = ({ orgId }) => {
  const [activeTab, setActiveTab] = useState("audit");
  const [exporting, setExporting] = useState(false);

  const exportCsv = async (dataType) => {
    setExporting(true);
    try {
      const res = await api.get(`/orgs/${orgId}/admin/export/csv?data_type=${dataType}`, { responseType: "blob" });
      const url = URL.createObjectURL(new Blob([res.data], { type: "text/csv" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `org_${orgId}_${dataType}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`${dataType} export downloaded`);
    } catch {
      toast.error(`Failed to export ${dataType}`);
    }
    setExporting(false);
  };

  if (!orgId) return null;

  const tabs = [
    { key: "audit", label: "Audit Log", icon: History },
    { key: "budget", label: "Budget Audit", icon: DollarSign },
    { key: "members", label: "Member Activity", icon: Users },
  ];

  return (
    <div className="p-5 rounded-xl bg-zinc-900/40 border border-zinc-800/60 space-y-4" data-testid="org-admin-audit-panel">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <History className="w-4 h-4 text-cyan-400" />
          <div>
            <h3 className="text-sm font-semibold text-zinc-200">Org Audit & Export</h3>
            <p className="text-[11px] text-zinc-500">View audit trails, budget usage, and member activity across the organization.</p>
          </div>
        </div>
        <div className="flex gap-1.5" data-testid="org-export-buttons">
          <Button size="sm" variant="outline" disabled={exporting} onClick={() => exportCsv("audit")} className="text-xs h-7 border-zinc-700" data-testid="export-audit-csv">
            <Download className="w-3 h-3 mr-1" /> Audit CSV
          </Button>
          <Button size="sm" variant="outline" disabled={exporting} onClick={() => exportCsv("budget")} className="text-xs h-7 border-zinc-700" data-testid="export-budget-csv">
            <Download className="w-3 h-3 mr-1" /> Budget CSV
          </Button>
          <Button size="sm" variant="outline" disabled={exporting} onClick={() => exportCsv("members")} className="text-xs h-7 border-zinc-700" data-testid="export-members-csv">
            <Download className="w-3 h-3 mr-1" /> Members CSV
          </Button>
        </div>
      </div>

      <div className="flex gap-1 border-b border-zinc-800/40 pb-0.5">
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-t-lg text-xs transition-colors ${activeTab === t.key ? "bg-zinc-800/60 text-zinc-200 border-b-2 border-cyan-500" : "text-zinc-500 hover:text-zinc-300"}`}
            data-testid={`org-audit-tab-${t.key}`}
          >
            <t.icon className="w-3 h-3" /> {t.label}
          </button>
        ))}
      </div>

      {activeTab === "audit" && <OrgAuditLog orgId={orgId} />}
      {activeTab === "budget" && <OrgBudgetAudit orgId={orgId} />}
      {activeTab === "members" && <OrgMemberActivity orgId={orgId} />}
    </div>
  );
};

export default OrgAdminAuditPanel;
