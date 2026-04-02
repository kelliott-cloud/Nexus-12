import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { handleSilent } from "@/lib/errorHandler";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { SkillBadgeList } from "@/components/SkillBadges";
import {
  Play, Loader2, CheckCircle, AlertTriangle, Star, Brain, Trophy, Clock, ChevronDown
} from "lucide-react";

const LEVEL_COLORS = {
  master: "text-amber-400 bg-amber-500/10",
  expert: "text-violet-400 bg-violet-500/10",
  advanced: "text-blue-400 bg-blue-500/10",
  intermediate: "text-emerald-400 bg-emerald-500/10",
  novice: "text-zinc-400 bg-zinc-700",
};

export default function AgentEvaluation({ workspaceId }) {
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [agentData, setAgentData] = useState(null);
  const [assessing, setAssessing] = useState(false);
  const [assessments, setAssessments] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchAgents = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/agents`);
      setAgents(res.data.agents || []);
    } catch (err) { handleSilent(err, "Eval:agents"); }
    setLoading(false);
  }, [workspaceId]);

  useEffect(() => { fetchAgents(); }, [fetchAgents]);

  const selectAgent = async (agent) => {
    setSelectedAgent(agent);
    setAgentData(null);
    try {
      const [skillsRes, historyRes] = await Promise.all([
        api.get(`/workspaces/${workspaceId}/agents/${agent.agent_id}/skills`),
        api.get(`/workspaces/${workspaceId}/agents/${agent.agent_id}/skills/history`),
      ]);
      setAgentData({
        proficiency: skillsRes.data.proficiency || [],
        configured: skillsRes.data.configured_skills || [],
        evaluation: skillsRes.data.evaluation || {},
        history: historyRes.data.history || [],
      });
    } catch (err) { handleSilent(err, "Eval:select"); }
  };

  const runAssessment = async (skillIds = []) => {
    if (!selectedAgent) return;
    setAssessing(true);
    try {
      const res = await api.post(`/workspaces/${workspaceId}/agents/${selectedAgent.agent_id}/skills/assess`, { skill_ids: skillIds });
      toast.success(`Assessment complete — Overall: ${res.data.overall_score}`);
      setAssessments(prev => [res.data, ...prev]);
      await selectAgent(selectedAgent);
    } catch (err) {
      toast.error("Assessment failed — check AI key configuration");
      handleSilent(err, "Eval:assess");
    }
    setAssessing(false);
  };

  if (loading) {
    return <div className="flex-1 flex items-center justify-center"><Loader2 className="w-5 h-5 animate-spin text-zinc-500" /></div>;
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden" data-testid="agent-evaluation-panel">
      <div className="flex-shrink-0 px-6 py-4 border-b border-zinc-800/60">
        <h2 className="text-lg font-semibold text-zinc-100 flex items-center gap-2" style={{ fontFamily: "Syne, sans-serif" }}>
          <Trophy className="w-5 h-5 text-amber-400" /> Agent Evaluation & Certification
        </h2>
        <p className="text-xs text-zinc-500 mt-0.5">Run AI-powered assessments to evaluate agent skill proficiency</p>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-6 max-w-4xl mx-auto space-y-6">
          {/* Agent Selector */}
          <div className="space-y-2">
            <label className="text-xs text-zinc-500 font-medium">Select Agent to Evaluate</label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {agents.map(a => (
                <button key={a.agent_id} onClick={() => selectAgent(a)}
                  className={`flex items-center gap-2 px-3 py-2.5 rounded-lg text-left transition-colors border ${selectedAgent?.agent_id === a.agent_id ? "bg-amber-500/10 border-amber-500/30" : "bg-zinc-900/40 border-zinc-800/40 hover:border-zinc-700"}`}
                  data-testid={`eval-agent-${a.agent_id}`}>
                  <div className="w-6 h-6 rounded flex items-center justify-center text-[9px] font-bold text-white" style={{ backgroundColor: a.color || "#6366f1" }}>
                    {a.name?.slice(0, 2).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-zinc-300 truncate">{a.name}</p>
                    <p className="text-[9px] text-zinc-600">{a.base_model}</p>
                  </div>
                  {a.evaluation?.overall_score > 0 && (
                    <span className="text-xs font-bold text-amber-400">{a.evaluation.overall_score}</span>
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Agent Details & Assessment */}
          {selectedAgent && agentData && (
            <div className="space-y-4">
              {/* Current Evaluation Summary */}
              <div className="bg-zinc-900/50 border border-zinc-800/40 rounded-xl p-4">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <p className="text-sm text-zinc-200 font-medium">{selectedAgent.name}</p>
                    <p className="text-[10px] text-zinc-500">
                      {agentData.evaluation?.last_assessed
                        ? `Last assessed: ${new Date(agentData.evaluation.last_assessed).toLocaleDateString()}`
                        : "Never assessed"}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    {agentData.evaluation?.overall_score > 0 && (
                      <div className="text-center">
                        <div className="text-2xl font-bold text-amber-400">{agentData.evaluation.overall_score}</div>
                        <p className="text-[9px] text-zinc-600">Overall Score</p>
                      </div>
                    )}
                    <Button onClick={() => runAssessment()} disabled={assessing}
                      className="bg-amber-600 hover:bg-amber-700 text-white text-xs gap-1.5" data-testid="run-assessment-btn">
                      {assessing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                      {assessing ? "Assessing..." : "Run Full Assessment"}
                    </Button>
                  </div>
                </div>

                {/* Badges */}
                {agentData.evaluation?.badges?.length > 0 && (
                  <div className="mb-3">
                    <SkillBadgeList badges={agentData.evaluation.badges} size="lg" max={8} />
                  </div>
                )}

                {/* Skill Scores Grid */}
                {agentData.evaluation?.skill_scores && Object.keys(agentData.evaluation.skill_scores).length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs text-zinc-500 font-medium">Skill Scores</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {Object.entries(agentData.evaluation.skill_scores).map(([skillId, data]) => (
                        <div key={skillId} className="flex items-center gap-3 p-2.5 rounded-lg bg-zinc-800/40 border border-zinc-800/30">
                          <div className="flex-1 min-w-0">
                            <p className="text-xs text-zinc-300">{skillId.replace(/_/g, " ")}</p>
                            <div className="flex items-center gap-2 mt-1">
                              <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                                <div className="h-full rounded-full transition-all duration-500"
                                  style={{ width: `${data.score}%`, backgroundColor: data.score >= 75 ? "#22c55e" : data.score >= 50 ? "#f59e0b" : "#ef4444" }} />
                              </div>
                              <span className="text-xs font-bold text-zinc-200">{data.score}</span>
                            </div>
                            {data.response_preview && (
                              <p className="text-[9px] text-zinc-600 mt-1 truncate">"{data.response_preview}"</p>
                            )}
                          </div>
                          <Button variant="ghost" size="sm" onClick={() => runAssessment([skillId])} disabled={assessing}
                            className="text-[9px] text-zinc-500 h-6 px-2" data-testid={`reassess-${skillId}`}>
                            Re-test
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Configured Skills & Proficiency */}
              <div className="bg-zinc-900/50 border border-zinc-800/40 rounded-xl p-4 space-y-3">
                <p className="text-xs text-zinc-500 font-medium">Skill Proficiency Tracking</p>
                {agentData.proficiency.length === 0 ? (
                  <p className="text-xs text-zinc-600 py-2">No proficiency data yet. Run an assessment or use the agent in channels to build data.</p>
                ) : (
                  <div className="space-y-1.5">
                    {agentData.proficiency.map(s => {
                      const lc = LEVEL_COLORS[s.level] || LEVEL_COLORS.novice;
                      return (
                        <div key={s.skill} className="flex items-center gap-3 p-2 rounded-lg bg-zinc-800/30">
                          <div className="w-20">
                            <p className="text-xs text-zinc-300">{s.skill?.replace(/_/g, " ")}</p>
                          </div>
                          <Badge className={`text-[8px] ${lc}`}>{s.level || "novice"}</Badge>
                          <div className="flex-1 h-1 bg-zinc-800 rounded-full overflow-hidden">
                            <div className="h-full bg-cyan-500 rounded-full" style={{ width: `${s.proficiency || 0}%` }} />
                          </div>
                          <span className="text-[10px] text-zinc-400 w-10 text-right">{s.proficiency || 0}%</span>
                          <span className="text-[10px] text-zinc-600 w-12 text-right">{s.xp || 0} XP</span>
                          {s.streak > 0 && <span className="text-[9px] text-amber-500">{s.streak} streak</span>}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Assessment History */}
              {assessments.length > 0 && (
                <div className="bg-zinc-900/50 border border-zinc-800/40 rounded-xl p-4 space-y-3">
                  <p className="text-xs text-zinc-500 font-medium">Recent Assessments (this session)</p>
                  {assessments.map((a, i) => (
                    <div key={i} className="flex items-center gap-3 p-2 rounded-lg bg-zinc-800/30">
                      <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                      <div className="flex-1">
                        <p className="text-xs text-zinc-300">Score: {a.overall_score} ({a.method})</p>
                        <p className="text-[9px] text-zinc-600">{Object.keys(a.skill_scores || {}).length} skills tested</p>
                      </div>
                      {a.badges_awarded?.length > 0 && (
                        <Badge className="bg-amber-500/10 text-amber-400 text-[8px]">+{a.badges_awarded.length} badges</Badge>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Empty state */}
          {!selectedAgent && (
            <div className="text-center py-12">
              <Brain className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
              <p className="text-sm text-zinc-400">Select an agent to view evaluation results</p>
              <p className="text-xs text-zinc-600 mt-1">AI-powered assessment tests each configured skill and awards certification badges</p>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
