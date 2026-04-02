import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Shield, Download, RefreshCw, Search, Loader2, Clock, User } from "lucide-react";
import { handleSilent } from "@/lib/errorHandler";
import { api } from "@/App";

const ACTION_COLORS = {
  create: "bg-emerald-500/20 text-emerald-400",
  delete: "bg-red-500/20 text-red-400",
  update: "bg-blue-500/20 text-blue-400",
  login: "bg-cyan-500/20 text-cyan-400",
  logout: "bg-zinc-700/20 text-zinc-400",
  export: "bg-purple-500/20 text-purple-400",
  admin: "bg-amber-500/20 text-amber-400",
};

export default function AuditLogViewer() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(0);
  const LIMIT = 50;

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: String(LIMIT), skip: String(page * LIMIT) });
      if (search) params.set("q", search);
      if (actionFilter) params.set("action", actionFilter);
      if (dateFrom) params.set("from", dateFrom);
      if (dateTo) params.set("to", dateTo);
      const res = await api.get("/admin/audit-logs?" + params.toString());
      setLogs(res.data?.logs || res.data || []);
    } catch (err) {
      handleSilent(err, "AuditLog:fetch");
    }
    setLoading(false);
  }, [search, actionFilter, dateFrom, dateTo, page]);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  const exportCsv = () => {
    if (!logs.length) return;
    const header = "Timestamp,User,Action,Resource,Details\n";
    const rows = logs.map(l => {
      const ts = l.created_at || "";
      const userName = l.user_name || l.user_id || "";
      const action = l.action || "";
      const resource = l.resource_type || "";
      const details = l.details ? JSON.stringify(l.details).replace(/"/g, "'").substring(0, 200) : "";
      return [ts, userName, action, resource, details].map(v => '"' + v + '"').join(",");
    }).join("\n");
    const blob = new Blob([header + rows], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "audit_log_" + new Date().toISOString().split("T")[0] + ".csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const getActionColor = (action) => {
    const key = Object.keys(ACTION_COLORS).find(k => (action || "").toLowerCase().includes(k));
    return ACTION_COLORS[key] || "bg-zinc-800 text-zinc-400";
  };

  return (
    <div className="flex-1 flex flex-col min-h-0" data-testid="audit-log-viewer">
      <div className="max-w-6xl mx-auto w-full space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-emerald-400" />
            <h2 className="text-lg font-semibold text-zinc-100" style={{ fontFamily: "Syne, sans-serif" }}>Audit Log</h2>
          </div>
          <div className="flex gap-2">
            <Button size="sm" variant="ghost" onClick={fetchLogs} className="h-7 text-zinc-400" data-testid="audit-refresh-btn">
              <RefreshCw className="w-3.5 h-3.5" />
            </Button>
            <Button size="sm" onClick={exportCsv} className="h-7 text-xs bg-zinc-800 text-zinc-300 gap-1" data-testid="audit-export-btn">
              <Download className="w-3 h-3" /> Export CSV
            </Button>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 items-center">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-zinc-500" />
            <Input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search by user, action, or resource..."
              className="pl-9 bg-zinc-950 border-zinc-800 h-9 text-xs"
              data-testid="audit-search-input"
            />
          </div>
          <select
            value={actionFilter}
            onChange={e => setActionFilter(e.target.value)}
            className="bg-zinc-950 border border-zinc-800 rounded-md px-3 py-1.5 text-xs text-zinc-300 h-9"
            data-testid="audit-action-filter"
          >
            <option value="">All Actions</option>
            <option value="create">Create</option>
            <option value="update">Update</option>
            <option value="delete">Delete</option>
            <option value="login">Login</option>
            <option value="export">Export</option>
          </select>
          <Input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className="bg-zinc-950 border-zinc-800 h-9 text-xs w-36" data-testid="audit-date-from" />
          <Input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className="bg-zinc-950 border-zinc-800 h-9 text-xs w-36" data-testid="audit-date-to" />
        </div>

        <div className="rounded-lg border border-zinc-800/40 overflow-hidden">
          <div className="grid grid-cols-[160px_120px_140px_1fr] gap-2 px-4 py-2 bg-zinc-900/50 text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">
            <span>Timestamp</span><span>User</span><span>Action</span><span>Details</span>
          </div>
          <ScrollArea className="max-h-[500px]">
            {loading ? (
              <div className="py-8 text-center"><Loader2 className="w-4 h-4 animate-spin text-zinc-500 mx-auto" /></div>
            ) : logs.length === 0 ? (
              <div className="py-8 text-center text-xs text-zinc-600">No audit logs found</div>
            ) : (
              logs.map((log, i) => (
                <div key={log.log_id || i} className="grid grid-cols-[160px_120px_140px_1fr] gap-2 px-4 py-2.5 border-t border-zinc-800/30 hover:bg-zinc-900/30 text-xs" data-testid={"audit-log-row-" + i}>
                  <span className="text-zinc-500 flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {log.created_at ? new Date(log.created_at).toLocaleString() : ""}
                  </span>
                  <span className="text-zinc-300 truncate flex items-center gap-1">
                    <User className="w-3 h-3 text-zinc-600" />
                    {log.user_name || log.user_id || "system"}
                  </span>
                  <Badge className={"text-[9px] w-fit " + getActionColor(log.action)}>{log.action}</Badge>
                  <span className="text-zinc-400 truncate">
                    {log.resource_type ? log.resource_type + ": " : ""}
                    {typeof log.details === "object" ? JSON.stringify(log.details).substring(0, 150) : String(log.details || "").substring(0, 150)}
                  </span>
                </div>
              ))
            )}
          </ScrollArea>
        </div>

        <div className="flex items-center justify-between text-xs text-zinc-500">
          <span>{logs.length} entries shown (page {page + 1})</span>
          <div className="flex gap-2">
            <Button size="sm" variant="ghost" disabled={page === 0} onClick={() => setPage(p => p - 1)} className="h-7 text-xs" data-testid="audit-prev-btn">Previous</Button>
            <Button size="sm" variant="ghost" disabled={logs.length < LIMIT} onClick={() => setPage(p => p + 1)} className="h-7 text-xs" data-testid="audit-next-btn">Next</Button>
          </div>
        </div>
      </div>
    </div>
  );
}
