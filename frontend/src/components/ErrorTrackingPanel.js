import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Bug, CheckCircle2, Trash2, RefreshCw, Loader2, ChevronDown, ChevronRight, Monitor, Server } from "lucide-react";
import { toast } from "sonner";
import { handleSilent } from "@/lib/errorHandler";
import { api } from "@/App";

export default function ErrorTrackingPanel() {
  const [errors, setErrors] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showResolved, setShowResolved] = useState(false);
  const [expanded, setExpanded] = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [errRes, statRes] = await Promise.all([
        api.get(`/admin/errors?resolved=${showResolved}&limit=50`),
        api.get("/admin/errors/stats"),
      ]);
      setErrors(errRes.data?.errors || []);
      setStats(statRes.data);
    } catch (err) { handleSilent(err, "ErrorTracking:fetch"); }
    setLoading(false);
  }, [showResolved]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const resolve = async (errorId) => {
    try {
      await api.put(`/admin/errors/${errorId}/resolve`);
      toast.success("Marked as resolved");
      fetchData();
    } catch (err) { handleSilent(err, "ErrorTracking:resolve"); }
  };

  const deleteError = async (errorId) => {
    try {
      await api.delete(`/admin/errors/${errorId}`);
      toast.success("Deleted");
      fetchData();
    } catch (err) { handleSilent(err, "ErrorTracking:delete"); }
  };

  return (
    <div className="space-y-4" data-testid="error-tracking-panel">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bug className="w-5 h-5 text-red-400" />
          <h2 className="text-lg font-semibold text-zinc-100" style={{ fontFamily: "Syne, sans-serif" }}>Error Tracking</h2>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant={showResolved ? "default" : "ghost"} onClick={() => setShowResolved(!showResolved)} className="h-7 text-[10px]" data-testid="error-toggle-resolved">
            {showResolved ? "Show Unresolved" : "Show Resolved"}
          </Button>
          <Button size="sm" variant="ghost" onClick={fetchData} className="h-7 text-zinc-400"><RefreshCw className="w-3.5 h-3.5" /></Button>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-4 gap-2">
          {[
            { label: "Total", value: stats.total, color: "text-zinc-300" },
            { label: "Unresolved", value: stats.unresolved, color: stats.unresolved > 0 ? "text-red-400" : "text-emerald-400" },
            { label: "Frontend", value: stats.frontend, color: "text-blue-400" },
            { label: "Backend", value: stats.backend, color: "text-amber-400" },
          ].map(s => (
            <div key={s.label} className="bg-zinc-900/50 border border-zinc-800/40 rounded-lg p-2.5 text-center">
              <div className={`text-lg font-bold ${s.color}`}>{s.value}</div>
              <div className="text-[9px] text-zinc-500 uppercase">{s.label}</div>
            </div>
          ))}
        </div>
      )}

      <ScrollArea className="max-h-[500px]">
        {loading ? (
          <div className="py-8 text-center"><Loader2 className="w-4 h-4 animate-spin text-zinc-500 mx-auto" /></div>
        ) : errors.length === 0 ? (
          <div className="py-8 text-center text-xs text-zinc-600">
            {showResolved ? "No resolved errors" : "No unresolved errors"}
          </div>
        ) : (
          <div className="space-y-1.5">
            {errors.map(err => (
              <div key={err.error_id} className="rounded-lg border border-zinc-800/40 bg-zinc-900/30 overflow-hidden" data-testid={`error-${err.error_id}`}>
                <div className="flex items-center gap-3 px-3 py-2.5 cursor-pointer hover:bg-zinc-800/30" onClick={() => setExpanded(expanded === err.error_id ? null : err.error_id)}>
                  {expanded === err.error_id ? <ChevronDown className="w-3.5 h-3.5 text-zinc-600" /> : <ChevronRight className="w-3.5 h-3.5 text-zinc-600" />}
                  {err.source === "frontend" ? <Monitor className="w-3.5 h-3.5 text-blue-400" /> : <Server className="w-3.5 h-3.5 text-amber-400" />}
                  <span className="text-xs text-zinc-300 truncate flex-1">{err.message}</span>
                  <Badge className="text-[8px] bg-zinc-800 text-zinc-500">{err.count}x</Badge>
                  <span className="text-[9px] text-zinc-600">{err.last_seen ? new Date(err.last_seen).toLocaleString() : ""}</span>
                  <div className="flex gap-1" onClick={e => e.stopPropagation()}>
                    {!err.resolved && (
                      <button onClick={() => resolve(err.error_id)} className="text-zinc-600 hover:text-emerald-400 p-1" data-testid={`error-resolve-${err.error_id}`}>
                        <CheckCircle2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                    <button onClick={() => deleteError(err.error_id)} className="text-zinc-600 hover:text-red-400 p-1" data-testid={`error-delete-${err.error_id}`}>
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
                {expanded === err.error_id && (
                  <div className="px-3 pb-3 space-y-2 border-t border-zinc-800/30 pt-2">
                    <div className="grid grid-cols-2 gap-2 text-[10px]">
                      <div><span className="text-zinc-600">Source:</span> <span className="text-zinc-400">{err.source}</span></div>
                      <div><span className="text-zinc-600">Component:</span> <span className="text-zinc-400">{err.component || "—"}</span></div>
                      <div><span className="text-zinc-600">First seen:</span> <span className="text-zinc-400">{err.first_seen ? new Date(err.first_seen).toLocaleString() : ""}</span></div>
                      <div><span className="text-zinc-600">Occurrences:</span> <span className="text-zinc-400">{err.count}</span></div>
                      {err.url && <div className="col-span-2"><span className="text-zinc-600">URL:</span> <span className="text-zinc-400 break-all">{err.url}</span></div>}
                    </div>
                    {err.stack && (
                      <pre className="text-[9px] text-zinc-500 bg-zinc-950 rounded p-2 overflow-x-auto max-h-40 whitespace-pre-wrap font-mono">{err.stack}</pre>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
