import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { handleSilent } from "@/lib/errorHandler";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import {
  Copy, Trash2, RefreshCw, Search, Loader2, CheckCircle, AlertTriangle, Sparkles, ChevronDown
} from "lucide-react";

export default function KnowledgeDedupPanel({ workspaceId }) {
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [duplicates, setDuplicates] = useState([]);
  const [scanning, setScanning] = useState(false);
  const [rescoring, setRescoring] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchAgents = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/agents`);
      setAgents(res.data.agents || []);
    } catch (err) { handleSilent(err, "Dedup:fetchAgents"); }
    setLoading(false);
  }, [workspaceId]);

  useEffect(() => { fetchAgents(); }, [fetchAgents]);

  const scanDuplicates = async () => {
    if (!selectedAgent) return;
    setScanning(true);
    setDuplicates([]);
    try {
      const res = await api.post(
        `/workspaces/${workspaceId}/agents/${selectedAgent.agent_id}/knowledge/deduplicate?threshold=0.7`
      );
      setDuplicates(res.data.duplicates || []);
      setStats({ total_checked: res.data.total_checked, duplicate_count: res.data.duplicate_count });
      if (res.data.duplicate_count === 0) {
        toast.success("No duplicates found — knowledge base is clean!");
      } else {
        toast.info(`Found ${res.data.duplicate_count} duplicate pairs`);
      }
    } catch (err) {
      toast.error("Scan failed");
      handleSilent(err, "Dedup:scan");
    }
    setScanning(false);
  };

  const rescoreKnowledge = async () => {
    if (!selectedAgent) return;
    setRescoring(true);
    try {
      const res = await api.post(
        `/workspaces/${workspaceId}/agents/${selectedAgent.agent_id}/knowledge/rescore`
      );
      toast.success(`Rescored ${res.data.rescored} chunks`);
    } catch (err) {
      toast.error("Rescore failed");
      handleSilent(err, "Dedup:rescore");
    }
    setRescoring(false);
  };

  const applyRemoval = async () => {
    if (!selectedAgent || duplicates.length === 0) return;
    setRemoving(true);
    try {
      const chunkIds = duplicates.map(d => d.remove);
      await api.post(
        `/workspaces/${workspaceId}/agents/${selectedAgent.agent_id}/knowledge/deduplicate/apply`,
        { chunk_ids: chunkIds }
      );
      toast.success(`Removed ${chunkIds.length} duplicate chunks`);
      setDuplicates([]);
      setStats(null);
    } catch (err) {
      toast.error("Removal failed");
      handleSilent(err, "Dedup:apply");
    }
    setRemoving(false);
  };

  if (loading) {
    return <div className="flex-1 flex items-center justify-center"><Loader2 className="w-5 h-5 animate-spin text-zinc-500" /></div>;
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden" data-testid="knowledge-dedup-panel">
      <div className="flex-shrink-0 px-6 py-4 border-b border-zinc-800/60">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100 flex items-center gap-2" style={{ fontFamily: "Syne, sans-serif" }}>
              <Sparkles className="w-5 h-5 text-violet-400" /> Knowledge Quality
            </h2>
            <p className="text-xs text-zinc-500 mt-0.5">Find and remove duplicate knowledge chunks</p>
          </div>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-6 max-w-3xl mx-auto space-y-6">
          {/* Agent Selector */}
          <div className="space-y-2">
            <label className="text-xs text-zinc-500 font-medium">Select Agent</label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {agents.map(a => (
                <button key={a.agent_id} onClick={() => { setSelectedAgent(a); setDuplicates([]); setStats(null); }}
                  className={`flex items-center gap-2 px-3 py-2.5 rounded-lg text-left transition-colors border ${selectedAgent?.agent_id === a.agent_id ? "bg-violet-500/10 border-violet-500/30" : "bg-zinc-900/40 border-zinc-800/40 hover:border-zinc-700"}`}
                  data-testid={`dedup-agent-${a.agent_id}`}>
                  <div className="w-6 h-6 rounded flex items-center justify-center text-[9px] font-bold text-white" style={{ backgroundColor: a.color || "#6366f1" }}>
                    {a.name?.slice(0, 2).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-zinc-300 truncate">{a.name}</p>
                    <p className="text-[9px] text-zinc-600">{a.base_model}</p>
                  </div>
                </button>
              ))}
              {agents.length === 0 && (
                <p className="text-xs text-zinc-600 col-span-3 text-center py-4">No agents found. Create agents in the Studio tab first.</p>
              )}
            </div>
          </div>

          {/* Actions */}
          {selectedAgent && (
            <div className="flex items-center gap-3">
              <Button onClick={scanDuplicates} disabled={scanning}
                className="bg-violet-600 hover:bg-violet-700 text-white text-xs gap-1.5" data-testid="scan-duplicates-btn">
                {scanning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
                {scanning ? "Scanning..." : "Scan for Duplicates"}
              </Button>
              <Button variant="outline" onClick={rescoreKnowledge} disabled={rescoring}
                className="text-xs gap-1.5 border-zinc-700 text-zinc-300" data-testid="rescore-btn">
                {rescoring ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                {rescoring ? "Rescoring..." : "Rescore Quality"}
              </Button>
            </div>
          )}

          {/* Scan Results */}
          {stats && (
            <div className="bg-zinc-900/50 border border-zinc-800/40 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-zinc-200 font-medium">Scan Results</p>
                  <p className="text-[10px] text-zinc-500">
                    Checked {stats.total_checked} chunks — found {stats.duplicate_count} duplicate pairs
                  </p>
                </div>
                {duplicates.length > 0 && (
                  <Button size="sm" onClick={applyRemoval} disabled={removing}
                    className="bg-red-600 hover:bg-red-700 text-white text-xs gap-1" data-testid="apply-dedup-btn">
                    {removing ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}
                    Remove {duplicates.length} Duplicates
                  </Button>
                )}
              </div>

              {duplicates.length === 0 && stats.duplicate_count === 0 && (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                  <CheckCircle className="w-4 h-4 text-emerald-400" />
                  <p className="text-xs text-emerald-300">Knowledge base is clean — no duplicates detected</p>
                </div>
              )}

              {duplicates.length > 0 && (
                <div className="space-y-2">
                  {duplicates.map((d, i) => (
                    <div key={i} className="flex items-center gap-3 p-2.5 rounded-lg bg-zinc-800/40 border border-zinc-800/30" data-testid={`dup-pair-${i}`}>
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <Badge variant="secondary" className="bg-emerald-500/10 text-emerald-400 text-[8px]">
                            keep: {d.keep?.slice(0, 12)}
                          </Badge>
                          <Badge variant="secondary" className="bg-red-500/10 text-red-400 text-[8px]">
                            remove: {d.remove?.slice(0, 12)}
                          </Badge>
                        </div>
                      </div>
                      <Badge className="bg-zinc-700 text-zinc-300 text-[9px]">
                        {(d.similarity * 100).toFixed(0)}% similar
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Empty state when no agent selected */}
          {!selectedAgent && (
            <div className="text-center py-12">
              <Copy className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
              <p className="text-sm text-zinc-400">Select an agent to scan its knowledge base</p>
              <p className="text-xs text-zinc-600 mt-1">The deduplication engine finds near-identical content using similarity scoring</p>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
