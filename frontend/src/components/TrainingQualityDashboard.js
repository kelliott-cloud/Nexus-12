import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { handleSilent } from "@/lib/errorHandler";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import {
  BarChart3, Brain, Loader2, AlertTriangle, CheckCircle, Zap, BookOpen, RefreshCw, Sparkles, ChevronRight
} from "lucide-react";

export default function TrainingQualityDashboard({ workspaceId }) {
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filling, setFilling] = useState(null);

  const fetchAgents = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/agents`);
      setAgents(res.data.agents || []);
    } catch (err) { handleSilent(err, "TQD:agents"); }
    setLoading(false);
  }, [workspaceId]);

  useEffect(() => { fetchAgents(); }, [fetchAgents]);

  const selectAgent = async (agent) => {
    setSelectedAgent(agent);
    setDashboard(null);
    try {
      const res = await api.get(`/workspaces/${workspaceId}/agents/${agent.agent_id}/train/quality-dashboard`);
      setDashboard(res.data);
    } catch (err) { handleSilent(err, "TQD:dashboard"); }
  };

  const fillGap = async (skillId, topics) => {
    if (!selectedAgent || !topics.length) return;
    setFilling(skillId);
    try {
      const res = await api.post(`/workspaces/${workspaceId}/agents/${selectedAgent.agent_id}/train/topics`, {
        topics: topics.map(t => ({ topic: t, depth: "standard" })),
      });
      toast.success(`Training started for ${topics.length} topics`);
      setTimeout(() => selectAgent(selectedAgent), 3000);
    } catch (err) {
      toast.error("Failed to start training");
      handleSilent(err, "TQD:fill");
    }
    setFilling(null);
  };

  const toggleAutoRefresh = async (enabled) => {
    if (!selectedAgent) return;
    try {
      await api.post(`/workspaces/${workspaceId}/agents/${selectedAgent.agent_id}/train/auto-refresh`, { enabled, interval_days: 30 });
      toast.success(enabled ? "Auto-refresh enabled" : "Auto-refresh disabled");
      if (dashboard) setDashboard(d => ({ ...d, auto_refresh: enabled }));
    } catch (err) { toast.error("Failed to update"); handleSilent(err, "TQD:refresh"); }
  };

  if (loading) {
    return <div className="flex-1 flex items-center justify-center"><Loader2 className="w-5 h-5 animate-spin text-zinc-500" /></div>;
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden" data-testid="training-quality-dashboard">
      <div className="flex-shrink-0 px-6 py-4 border-b border-zinc-800/60">
        <h2 className="text-lg font-semibold text-zinc-100 flex items-center gap-2" style={{ fontFamily: "Syne, sans-serif" }}>
          <Sparkles className="w-5 h-5 text-cyan-400" /> Training Quality Dashboard
        </h2>
        <p className="text-xs text-zinc-500 mt-0.5">Knowledge coverage per skill with gap detection</p>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-6 max-w-4xl mx-auto space-y-6">
          {/* Agent selector */}
          <div className="space-y-2">
            <label className="text-xs text-zinc-500 font-medium">Select Agent</label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {agents.map(a => (
                <button key={a.agent_id} onClick={() => selectAgent(a)}
                  className={`flex items-center gap-2 px-3 py-2.5 rounded-lg text-left transition-colors border ${selectedAgent?.agent_id === a.agent_id ? "bg-cyan-500/10 border-cyan-500/30" : "bg-zinc-900/40 border-zinc-800/40 hover:border-zinc-700"}`}
                  data-testid={`tqd-agent-${a.agent_id}`}>
                  <div className="w-6 h-6 rounded flex items-center justify-center text-[9px] font-bold text-white" style={{ backgroundColor: a.color || "#6366f1" }}>
                    {a.name?.slice(0, 2).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-zinc-300 truncate">{a.name}</p>
                    <p className="text-[9px] text-zinc-600">{a.skills?.length || 0} skills</p>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Dashboard content */}
          {selectedAgent && dashboard && (
            <div className="space-y-4">
              {/* Summary bar */}
              <div className="flex items-center gap-4 p-4 bg-zinc-900/50 border border-zinc-800/40 rounded-xl">
                <div className="text-center">
                  <div className="text-2xl font-bold text-cyan-400">{dashboard.total_chunks}</div>
                  <p className="text-[9px] text-zinc-600">Total Chunks</p>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-zinc-200">{dashboard.skill_coverage?.length || 0}</div>
                  <p className="text-[9px] text-zinc-600">Skills Tracked</p>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-emerald-400">
                    {dashboard.skill_coverage?.filter(s => s.coverage_pct >= 50).length || 0}
                  </div>
                  <p className="text-[9px] text-zinc-600">Well Covered</p>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-amber-400">
                    {dashboard.skill_coverage?.filter(s => s.coverage_pct < 25).length || 0}
                  </div>
                  <p className="text-[9px] text-zinc-600">Gaps</p>
                </div>
                <div className="flex-1" />
                <Button variant="outline" size="sm"
                  className={`text-xs gap-1 ${dashboard.auto_refresh ? "border-cyan-500/30 text-cyan-400" : "border-zinc-700 text-zinc-400"}`}
                  onClick={() => toggleAutoRefresh(!dashboard.auto_refresh)}
                  data-testid="toggle-auto-refresh">
                  <RefreshCw className="w-3 h-3" /> {dashboard.auto_refresh ? "Auto-refresh ON" : "Enable Auto-refresh"}
                </Button>
              </div>

              {/* Per-skill coverage */}
              <div className="space-y-2">
                <p className="text-xs text-zinc-500 font-medium">Skill Coverage Analysis</p>
                {dashboard.skill_coverage?.map(sc => {
                  const isGap = sc.coverage_pct < 25;
                  const isGood = sc.coverage_pct >= 50;
                  return (
                    <div key={sc.skill_id} className={`p-3 rounded-xl border transition-colors ${isGap ? "bg-amber-950/10 border-amber-900/30" : isGood ? "bg-emerald-950/10 border-emerald-900/20" : "bg-zinc-900/40 border-zinc-800/40"}`}
                      data-testid={`tqd-skill-${sc.skill_id}`}>
                      <div className="flex items-center gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="text-sm text-zinc-200 font-medium">{sc.skill_id.replace(/_/g, " ")}</p>
                            <Badge className={`text-[8px] ${isGap ? "bg-amber-500/10 text-amber-400" : isGood ? "bg-emerald-500/10 text-emerald-400" : "bg-zinc-800 text-zinc-400"}`}>
                              {sc.level}
                            </Badge>
                          </div>
                          <div className="flex items-center gap-3 mt-1.5">
                            <div className="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden">
                              <div className="h-full rounded-full transition-all duration-500"
                                style={{
                                  width: `${sc.coverage_pct}%`,
                                  backgroundColor: isGap ? "#f59e0b" : isGood ? "#22c55e" : "#3b82f6",
                                }} />
                            </div>
                            <span className="text-xs font-bold text-zinc-300 w-12 text-right">{sc.coverage_pct}%</span>
                          </div>
                          <div className="flex items-center gap-3 mt-1 text-[9px] text-zinc-600">
                            <span>{sc.chunk_count} chunks</span>
                            <span>{sc.covered_topics.length}/{sc.suggested_topics.length} topics covered</span>
                            {sc.avg_quality > 0 && <span>q: {sc.avg_quality}</span>}
                          </div>
                        </div>
                        <div className="flex items-center gap-1">
                          {isGap ? (
                            <AlertTriangle className="w-4 h-4 text-amber-400" />
                          ) : isGood ? (
                            <CheckCircle className="w-4 h-4 text-emerald-400" />
                          ) : null}
                        </div>
                      </div>

                      {/* Uncovered topics with fill-gap button */}
                      {sc.uncovered_topics.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-zinc-800/30">
                          <div className="flex items-center justify-between mb-1">
                            <p className="text-[9px] text-zinc-600">Missing coverage:</p>
                            <Button size="sm" onClick={() => fillGap(sc.skill_id, sc.uncovered_topics)}
                              disabled={filling === sc.skill_id}
                              className="bg-cyan-600 hover:bg-cyan-700 text-white text-[9px] h-5 px-2 gap-0.5"
                              data-testid={`fill-gap-${sc.skill_id}`}>
                              {filling === sc.skill_id ? <Loader2 className="w-2.5 h-2.5 animate-spin" /> : <Zap className="w-2.5 h-2.5" />}
                              Fill Gap
                            </Button>
                          </div>
                          <div className="flex flex-wrap gap-1">
                            {sc.uncovered_topics.map(t => (
                              <Badge key={t} variant="secondary" className="bg-zinc-800 text-zinc-500 text-[8px]">{t}</Badge>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
                {(!dashboard.skill_coverage || dashboard.skill_coverage.length === 0) && (
                  <div className="text-center py-8">
                    <Brain className="w-8 h-8 text-zinc-700 mx-auto mb-2" />
                    <p className="text-xs text-zinc-500">No skills configured for this agent</p>
                    <p className="text-[10px] text-zinc-600 mt-1">Add skills in the Agent Studio to see coverage analysis</p>
                  </div>
                )}
              </div>

              {/* Topic breakdown */}
              {dashboard.topic_breakdown && Object.keys(dashboard.topic_breakdown).length > 0 && (
                <div className="bg-zinc-900/50 border border-zinc-800/40 rounded-xl p-4 space-y-2">
                  <p className="text-xs text-zinc-500 font-medium">Topic Breakdown</p>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {Object.entries(dashboard.topic_breakdown).map(([topic, data]) => (
                      <div key={topic} className="flex items-center gap-2 p-2 rounded-lg bg-zinc-800/30">
                        <BookOpen className="w-3 h-3 text-zinc-600 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <p className="text-[10px] text-zinc-300 truncate">{topic}</p>
                          <p className="text-[8px] text-zinc-600">{data.count} chunks, q:{data.avg_quality}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Empty state */}
          {!selectedAgent && (
            <div className="text-center py-12">
              <BarChart3 className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
              <p className="text-sm text-zinc-400">Select an agent to view training quality</p>
              <p className="text-xs text-zinc-600 mt-1">See knowledge coverage per skill and fill gaps with one click</p>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
