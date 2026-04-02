import { useState, useEffect } from "react";
import { api } from "@/App";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Loader2, Mail, Plus, Trash2, Check, X, Search, RefreshCw, Shield, ChevronRight, Filter, Eye, Archive, Tag } from "lucide-react";
import { toast } from "sonner";

const PROVIDERS = [
  { id: "gmail", name: "Gmail", color: "#EA4335" },
  { id: "microsoft", name: "Microsoft 365", color: "#0078D4" },
  { id: "icloud", name: "iCloud Mail", color: "#A2AAAD" },
  { id: "imap", name: "Generic IMAP", color: "#6B7280" },
];

const PRIORITY_COLORS = { high: "text-red-400 bg-red-500/10", normal: "text-zinc-300 bg-zinc-800", low: "text-zinc-500 bg-zinc-900" };
const STATUS_COLORS = { pending_review: "bg-amber-500/15 text-amber-400", approved: "bg-cyan-500/15 text-cyan-400", executed: "bg-emerald-500/15 text-emerald-400", dismissed: "bg-zinc-800 text-zinc-500", failed: "bg-red-500/15 text-red-400" };

export default function SmartInboxPanel({ workspaceId }) {
  const [tab, setTab] = useState("inbox");
  const [stats, setStats] = useState({});
  const [threads, setThreads] = useState([]);
  const [connections, setConnections] = useState([]);
  const [rules, setRules] = useState([]);
  const [reviewQueue, setReviewQueue] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => { loadData(); }, [workspaceId, tab]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [statsRes] = await Promise.all([
        api.get(`/workspaces/${workspaceId}/mail/stats`).catch(() => ({ data: {} })),
      ]);
      setStats(statsRes.data || {});
      if (tab === "inbox") {
        const r = await api.get(`/workspaces/${workspaceId}/mail/threads?limit=50`);
        setThreads(r.data?.threads || []);
      } else if (tab === "mail-accounts") {
        const r = await api.get(`/workspaces/${workspaceId}/mail/connections`);
        setConnections(r.data?.connections || []);
      } else if (tab === "mail-rules") {
        const r = await api.get(`/workspaces/${workspaceId}/mail/rules`);
        setRules(r.data?.rules || []);
      } else if (tab === "mail-review") {
        const r = await api.get(`/workspaces/${workspaceId}/mail/review`);
        setReviewQueue(r.data?.actions || []);
      } else if (tab === "mail-audit") {
        const r = await api.get(`/workspaces/${workspaceId}/mail/audit?limit=50`);
        setAuditLogs(r.data?.logs || []);
      }
    } catch { /* feature may be disabled */ }
    setLoading(false);
  };

  const approveAction = async (id) => {
    try { await api.post(`/workspaces/${workspaceId}/mail/review/${id}/approve`); toast.success("Approved"); loadData(); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const dismissAction = async (id) => {
    try { await api.post(`/workspaces/${workspaceId}/mail/review/${id}/dismiss`); toast.success("Dismissed"); loadData(); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const tabs = [
    { key: "inbox", label: "Inbox", count: stats.unread },
    { key: "mail-accounts", label: "Accounts", count: stats.connections },
    { key: "mail-rules", label: "Rules" },
    { key: "mail-review", label: "Review", count: stats.pending_review },
    { key: "mail-audit", label: "Audit" },
  ];

  return (
    <div className="p-6 space-y-6" data-testid="smart-inbox-panel">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center">
            <Mail className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-zinc-100" style={{ fontFamily: 'Syne, sans-serif' }}>Smart Inbox</h2>
            <p className="text-xs text-zinc-500">AI-managed email with governed delegation and audit trail</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={loadData} className="border-zinc-700 text-zinc-400">
          <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Refresh
        </Button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-zinc-800">
        {tabs.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`flex items-center gap-1.5 px-4 py-2 text-xs font-medium border-b-2 transition-colors ${
              tab === t.key ? "text-zinc-100 border-cyan-500" : "text-zinc-500 border-transparent hover:text-zinc-300"
            }`}>
            {t.label}
            {t.count > 0 && <Badge className="text-[9px] bg-cyan-500/15 text-cyan-400 ml-1">{t.count}</Badge>}
          </button>
        ))}
      </div>

      {loading ? <div className="py-12 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-zinc-500" /></div> : (
        <>
          {/* Inbox Tab */}
          {tab === "inbox" && (
            <div className="space-y-3">
              <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search threads..."
                className="bg-zinc-900 border-zinc-800 text-sm" data-testid="mail-search" />
              {threads.length === 0 ? (
                <div className="text-center py-12 text-zinc-500 text-sm">No email threads yet. Connect a mail account to get started.</div>
              ) : (
                threads.filter(t => !search || t.subject?.toLowerCase().includes(search.toLowerCase())).map(t => (
                  <div key={t.thread_id} className="p-3 rounded-xl bg-zinc-950/50 border border-zinc-800/40 hover:border-zinc-700 transition-colors cursor-pointer" data-testid={`thread-${t.thread_id}`}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          {!t.is_read && <div className="w-2 h-2 rounded-full bg-cyan-400 shrink-0" />}
                          <span className={`text-sm truncate ${t.is_read ? "text-zinc-400" : "text-zinc-100 font-medium"}`}>{t.subject || "(no subject)"}</span>
                        </div>
                        <p className="text-xs text-zinc-500 mt-0.5 truncate">{t.sender} &middot; {t.snippet?.substring(0, 80)}</p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {t.priority && <Badge className={`text-[9px] ${PRIORITY_COLORS[t.priority] || PRIORITY_COLORS.normal}`}>{t.priority}</Badge>}
                        {t.category && <Badge className="text-[9px] bg-zinc-800 text-zinc-500">{t.category}</Badge>}
                        <ChevronRight className="w-3.5 h-3.5 text-zinc-700" />
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* Accounts Tab */}
          {tab === "mail-accounts" && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {PROVIDERS.map(p => (
                  <button key={p.id} className="p-3 rounded-xl bg-zinc-950/50 border border-zinc-800/40 hover:border-zinc-700 transition-colors text-left" data-testid={`connect-${p.id}`}>
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold" style={{ backgroundColor: p.color, color: "#fff" }}>{p.name[0]}</div>
                      <div><p className="text-xs text-zinc-200">{p.name}</p><p className="text-[9px] text-zinc-600">Connect</p></div>
                    </div>
                  </button>
                ))}
              </div>
              {connections.length > 0 && (
                <div className="space-y-2 mt-4">
                  <p className="text-[10px] font-semibold text-zinc-500 uppercase">Connected Accounts</p>
                  {connections.map(c => (
                    <div key={c.connection_id} className="flex items-center justify-between p-3 rounded-xl bg-zinc-950/50 border border-zinc-800/40">
                      <div className="flex items-center gap-3">
                        <Badge className="text-[9px] bg-emerald-500/15 text-emerald-400">{c.status}</Badge>
                        <span className="text-sm text-zinc-200">{c.display_name || c.email}</span>
                        <Badge className="text-[9px] bg-zinc-800 text-zinc-500">{c.provider}</Badge>
                        <Badge className="text-[9px] bg-violet-500/15 text-violet-400">{c.delegation_mode}</Badge>
                      </div>
                      <span className="text-[10px] text-zinc-600">{c.sync_status}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Rules Tab */}
          {tab === "mail-rules" && (
            <div className="space-y-3">
              {rules.length === 0 ? (
                <div className="text-center py-12 text-zinc-500 text-sm">No rules configured. Rules automate triage and actions on incoming mail.</div>
              ) : (
                rules.map(r => (
                  <div key={r.rule_id} className="p-3 rounded-xl bg-zinc-950/50 border border-zinc-800/40">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-zinc-200">{r.name}</span>
                      <div className="flex items-center gap-2">
                        <Badge className={`text-[9px] ${r.enabled ? "bg-emerald-500/15 text-emerald-400" : "bg-zinc-800 text-zinc-600"}`}>{r.enabled ? "Active" : "Disabled"}</Badge>
                        <span className="text-[10px] text-zinc-600">{r.execution_count} runs</span>
                      </div>
                    </div>
                    <p className="text-[10px] text-zinc-500 mt-1">{r.conditions?.length || 0} conditions &middot; {r.actions?.length || 0} actions &middot; {r.match_mode}</p>
                  </div>
                ))
              )}
            </div>
          )}

          {/* Review Queue Tab */}
          {tab === "mail-review" && (
            <div className="space-y-3">
              {reviewQueue.length === 0 ? (
                <div className="text-center py-12 text-zinc-500 text-sm">No actions pending review. AI-recommended actions will appear here for approval.</div>
              ) : (
                reviewQueue.map(a => (
                  <div key={a.action_id} className="flex items-center justify-between p-3 rounded-xl bg-zinc-950/50 border border-zinc-800/40">
                    <div className="flex items-center gap-3">
                      <Badge className={`text-[9px] ${STATUS_COLORS[a.status] || STATUS_COLORS.pending_review}`}>{a.status}</Badge>
                      <span className="text-sm text-zinc-200">{a.action_type}</span>
                      <span className="text-xs text-zinc-500">{a.thread_id}</span>
                    </div>
                    <div className="flex gap-1">
                      <Button size="sm" onClick={() => approveAction(a.action_id)} className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs h-7"><Check className="w-3 h-3 mr-1" /> Approve</Button>
                      <Button size="sm" variant="outline" onClick={() => dismissAction(a.action_id)} className="border-zinc-700 text-zinc-400 text-xs h-7"><X className="w-3 h-3 mr-1" /> Dismiss</Button>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* Audit Tab */}
          {tab === "mail-audit" && (
            <div className="space-y-2">
              {auditLogs.length === 0 ? (
                <div className="text-center py-12 text-zinc-500 text-sm">No audit entries yet. All mail actions are logged here for compliance.</div>
              ) : (
                auditLogs.map((l, i) => (
                  <div key={l.audit_id || i} className="flex items-start justify-between p-2.5 rounded-lg bg-zinc-950/50 border border-zinc-800/30 text-xs">
                    <div className="flex items-center gap-2">
                      <Badge className="text-[9px] bg-zinc-800 text-zinc-400">{l.event_type}</Badge>
                      <span className="text-zinc-400">{l.action_type || l.resource_id}</span>
                    </div>
                    <span className="text-[10px] text-zinc-600">{l.timestamp ? new Date(l.timestamp).toLocaleString() : ""}</span>
                  </div>
                ))
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
