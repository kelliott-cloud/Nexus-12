import { useState, useEffect, useCallback } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { AlertTriangle, CheckCircle2, Clock, Users, MessageSquare, Gavel, RefreshCw, Loader2, ChevronDown, Download } from "lucide-react";
import { api } from "@/App";
import { toast } from "sonner";

const STATUS_BADGE = {
  detected: { color: "bg-amber-500/20 text-amber-400", label: "Detected" },
  open: { color: "bg-blue-500/20 text-blue-400", label: "Open" },
  voting: { color: "bg-purple-500/20 text-purple-400", label: "Voting" },
  resolved: { color: "bg-emerald-500/20 text-emerald-400", label: "Resolved" },
};

export default function DisagreementAuditLog({ workspaceId, onClose }) {
  const [audit, setAudit] = useState({ items: [], stats: {} });
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [selectedItem, setSelectedItem] = useState(null);
  const [resolveOpen, setResolveOpen] = useState(false);
  const [resolveText, setResolveText] = useState("");
  const [resolveNotes, setResolveNotes] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = filter !== "all" ? `?status=${filter}` : "";
      const res = await api.get(`/workspaces/${workspaceId}/disagreement-audit${params}`);
      setAudit(res.data || { items: [], stats: {} });
    } catch (err) { toast.error("Failed to load audit log"); }
    setLoading(false);
  }, [workspaceId, filter]);

  useEffect(() => { load(); }, [load]);

  const manualResolve = async () => {
    if (!selectedItem || !resolveText.trim()) return;
    try {
      await api.post(`/disagreements/${selectedItem.disagreement_id}/manual-resolve`, {
        resolution: resolveText, notes: resolveNotes,
      });
      toast.success("Disagreement resolved");
      setResolveOpen(false);
      setResolveText(""); setResolveNotes("");
      load();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed to resolve"); }
  };

  const exportCsv = () => {
    const items = audit.items || [];
    if (items.length === 0) { toast.info("No data to export"); return; }
    const header = "ID,Channel,Status,Topic,Agents,Resolution,Date\n";
    const rows = items.map(d => {
      const agents = (d.agents_involved || []).map(a => a.model || "").join(";");
      const resolution = d.resolution?.winning_position || "";
      return `${d.disagreement_id},"${d.channel_name || ""}",${d.status},"${(d.topic || "").replace(/"/g, "'').substring(0, 100)}","${agents}","${resolution.replace(/"/g, "'").substring(0, 100)}",${d.created_at || ""}`;
    }).join("\n");
    const blob = new Blob([header + rows], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = `disagreement_audit_${workspaceId}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  const stats = audit.stats || {};

  return (
    <div className="flex flex-col h-full" data-testid="disagreement-audit-log">
      {/* Header */}
      <div className="px-4 py-3 border-b border-zinc-800/40 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
          <span className="text-sm font-semibold text-zinc-200">Disagreement Audit Log</span>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="ghost" onClick={exportCsv} className="h-7 px-2 text-zinc-500 text-[10px]"><Download className="w-3 h-3 mr-1" /> Export</Button>
          <Button size="sm" variant="ghost" onClick={load} className="h-7 px-2 text-zinc-400"><RefreshCw className="w-3 h-3" /></Button>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="px-4 py-2 border-b border-zinc-800/30 flex items-center gap-4 text-[10px]">
        <span className="text-zinc-400">{stats.total || 0} total</span>
        <span className="text-amber-400">{stats.open || 0} open</span>
        <span className="text-emerald-400">{stats.resolved || 0} resolved</span>
        <span className="text-zinc-500">{stats.resolution_rate || 0}% resolution rate</span>
        <div className="flex-1" />
        <select value={filter} onChange={e => setFilter(e.target.value)} className="bg-zinc-900 border border-zinc-800 rounded px-2 py-0.5 text-[10px] text-zinc-400">
          <option value="all">All</option>
          <option value="detected">Detected</option>
          <option value="open">Open</option>
          <option value="voting">Voting</option>
          <option value="resolved">Resolved</option>
        </select>
      </div>

      {/* List */}
      <ScrollArea className="flex-1">
        {loading ? (
          <div className="p-8 text-center"><Loader2 className="w-4 h-4 animate-spin text-zinc-500 mx-auto" /></div>
        ) : (audit.items || []).length === 0 ? (
          <div className="p-8 text-center">
            <CheckCircle2 className="w-8 h-8 text-zinc-700 mx-auto mb-2" />
            <p className="text-xs text-zinc-500">No disagreements found</p>
            <p className="text-[10px] text-zinc-600 mt-1">Agents are in agreement or no conflicts detected yet</p>
          </div>
        ) : (
          <div className="p-3 space-y-2">
            {(audit.items || []).map(item => (
              <button key={item.disagreement_id} onClick={() => setSelectedItem(selectedItem?.disagreement_id === item.disagreement_id ? null : item)}
                className={`w-full text-left p-3 rounded-lg border transition-all ${
                  selectedItem?.disagreement_id === item.disagreement_id
                    ? "border-amber-500/40 bg-amber-500/5"
                    : "border-zinc-800/40 bg-zinc-900/30 hover:border-zinc-700"
                }`} data-testid={`dis-${item.disagreement_id}`}>
                {/* Header Row */}
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className={`w-3.5 h-3.5 ${item.status === "resolved" ? "text-emerald-400" : "text-amber-400"}`} />
                    <span className="text-xs font-medium text-zinc-300 truncate max-w-[250px]">{item.topic || "Auto-detected disagreement"}</span>
                  </div>
                  <Badge className={`text-[8px] ${(STATUS_BADGE[item.status] || STATUS_BADGE.detected).color}`}>
                    {(STATUS_BADGE[item.status] || STATUS_BADGE.detected).label}
                  </Badge>
                </div>

                {/* Channel + Date */}
                <div className="flex items-center gap-3 text-[10px] text-zinc-500 mb-1.5">
                  {item.channel_name && <span className="flex items-center gap-1"><MessageSquare className="w-3 h-3" /> #{item.channel_name}</span>}
                  <span><Clock className="w-3 h-3 inline mr-0.5" />{item.created_at ? new Date(item.created_at).toLocaleString() : ""}</span>
                  {item.conflict_score && <span>Score: {item.conflict_score}</span>}
                </div>

                {/* Agents Involved */}
                <div className="flex items-center gap-1 flex-wrap mb-1">
                  <Users className="w-3 h-3 text-zinc-600" />
                  {(item.agents_involved || []).map((agent, i) => (
                    <Badge key={i} className="text-[8px] bg-zinc-800 text-zinc-400">{agent.model || agent.agent_key || "Unknown"}</Badge>
                  ))}
                </div>

                {/* Expanded Detail */}
                {selectedItem?.disagreement_id === item.disagreement_id && (
                  <div className="mt-2 pt-2 border-t border-zinc-800/30">
                    {/* Agent Positions */}
                    <p className="text-[10px] font-semibold text-zinc-400 mb-1">Agent Positions:</p>
                    {(item.agents_involved || []).map((agent, i) => (
                      <div key={i} className="p-2 rounded bg-zinc-950/50 mb-1">
                        <span className="text-[10px] text-cyan-400 font-medium">{agent.model || "Agent"}</span>
                        <p className="text-[10px] text-zinc-400 mt-0.5 whitespace-pre-wrap">{agent.position_summary || "No position recorded"}</p>
                      </div>
                    ))}

                    {/* Votes */}
                    {item.votes && Object.keys(item.votes).length > 0 && (
                      <div className="mt-2">
                        <p className="text-[10px] font-semibold text-zinc-400 mb-1">Votes:</p>
                        {Object.entries(item.votes).map(([agent, vote]) => (
                          <div key={agent} className="flex items-center gap-2 text-[10px] text-zinc-400 p-1">
                            <span className="text-cyan-400">{agent}</span>
                            <span className="text-zinc-300">"{vote.position}"</span>
                            <Badge className="text-[8px] bg-zinc-800">{Math.round((vote.confidence || 0) * 100)}% conf</Badge>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Resolution */}
                    {item.resolution && (
                      <div className="mt-2 p-2 rounded bg-emerald-500/5 border border-emerald-500/20">
                        <p className="text-[10px] font-semibold text-emerald-400 mb-1 flex items-center gap-1"><Gavel className="w-3 h-3" /> Resolution</p>
                        <p className="text-[10px] text-zinc-300">{item.resolution.winning_position}</p>
                        {item.resolution.resolution_notes && <p className="text-[10px] text-zinc-500 mt-0.5">Notes: {item.resolution.resolution_notes}</p>}
                        {item.resolution.resolved_by && <p className="text-[9px] text-zinc-600 mt-0.5">By: {item.resolution.resolved_by} ({item.resolution.resolution_type})</p>}
                      </div>
                    )}

                    {/* Resolve Button */}
                    {item.status !== "resolved" && (
                      <Button size="sm" onClick={(e) => { e.stopPropagation(); setResolveOpen(true); }}
                        className="mt-2 h-7 text-[10px] bg-amber-500 hover:bg-amber-400 text-white gap-1">
                        <Gavel className="w-3 h-3" /> Resolve Manually
                      </Button>
                    )}
                  </div>
                )}
              </button>
            ))}
          </div>
        )}
      </ScrollArea>

      {/* Manual Resolve Dialog */}
      <Dialog open={resolveOpen} onOpenChange={setResolveOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-md">
          <DialogHeader>
            <DialogTitle className="text-zinc-100 flex items-center gap-2"><Gavel className="w-4 h-4 text-amber-400" /> Resolve Disagreement</DialogTitle>
            <DialogDescription className="text-zinc-500">Provide your decision to resolve this conflict</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 mt-2">
            <textarea value={resolveText} onChange={e => setResolveText(e.target.value)} placeholder="Your resolution / winning position..."
              className="w-full bg-zinc-950 border border-zinc-800 rounded-md px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 min-h-[80px]" data-testid="resolve-text" />
            <textarea value={resolveNotes} onChange={e => setResolveNotes(e.target.value)} placeholder="Notes (optional)"
              className="w-full bg-zinc-950 border border-zinc-800 rounded-md px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 min-h-[40px]" />
            <Button onClick={manualResolve} disabled={!resolveText.trim()} className="w-full bg-amber-500 hover:bg-amber-400 text-white" data-testid="resolve-submit">Resolve</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
