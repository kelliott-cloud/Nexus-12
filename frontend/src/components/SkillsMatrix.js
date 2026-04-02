import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { handleSilent } from "@/lib/errorHandler";
import { toast } from "sonner";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Brain, BarChart3, Code, Palette, Settings, Shield, Star, Zap,
  Trophy, TrendingUp, Award, ChevronDown, ChevronRight
} from "lucide-react";
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from "recharts";

const LEVEL_COLORS = { novice: "#6B7280", intermediate: "#3B82F6", advanced: "#8B5CF6", expert: "#F59E0B", master: "#EF4444" };
const LEVEL_ORDER = { novice: 0, intermediate: 1, advanced: 2, expert: 3, master: 4 };
const CATEGORY_ICONS = { engineering: Code, product: Palette, data: BarChart3, operations: Settings };

export default function SkillsMatrix({ workspaceId, agentId, agentName }) {
  const [skills, setSkills] = useState([]);
  const [categories, setCategories] = useState({});
  const [proficiency, setProficiency] = useState([]);
  const [configuredSkills, setConfiguredSkills] = useState([]);
  const [evaluation, setEvaluation] = useState({});
  const [leaderboard, setLeaderboard] = useState([]);
  const [expandedCats, setExpandedCats] = useState({});
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState("heatmap");
  const [compareAgents, setCompareAgents] = useState([]);
  const [availableAgents, setAvailableAgents] = useState([]);
  const [trainingDepth, setTrainingDepth] = useState({});
  const [showTrainingOverlay, setShowTrainingOverlay] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [skillsRes, agentSkillsRes, leaderRes, agentsRes] = await Promise.all([
        api.get("/skills"),
        agentId ? api.get(`/workspaces/${workspaceId}/agents/${agentId}/skills`) : Promise.resolve({ data: {} }),
        api.get(`/workspaces/${workspaceId}/skills/leaderboard`),
        api.get(`/workspaces/${workspaceId}/agents`),
      ]);
      setSkills(skillsRes.data.skills || []);
      setCategories(skillsRes.data.categories || {});
      setProficiency(agentSkillsRes.data.proficiency || []);
      setConfiguredSkills(agentSkillsRes.data.configured_skills || []);
      setEvaluation(agentSkillsRes.data.evaluation || {});
      setLeaderboard(leaderRes.data.leaderboard || []);
      setAvailableAgents(agentsRes.data.agents || []);

      // Fetch training depth for all agents
      const agents = agentsRes.data.agents || [];
      const depthMap = {};
      for (const agent of agents.slice(0, 10)) {
        try {
          const qRes = await api.get(`/workspaces/${workspaceId}/agents/${agent.agent_id}/train/quality-dashboard`);
          const coverage = qRes.data.skill_coverage || [];
          for (const sc of coverage) {
            const key = `${agent.agent_id}:${sc.skill_id}`;
            depthMap[key] = sc.chunk_count || 0;
          }
        } catch { /* some agents may not have training */ }
      }
      setTrainingDepth(depthMap);
    } catch (err) { handleSilent(err, "SkillsMatrix:fetch"); }
    setLoading(false);
  }, [workspaceId, agentId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const runAssessment = async () => {
    if (!agentId) return;
    try {
      await api.post(`/workspaces/${workspaceId}/agents/${agentId}/skills/assess`, { skill_ids: [] });
      toast.success("Assessment started");
      fetchData();
    } catch (err) { toast.error("Assessment failed"); }
  };

  const toggleCategory = (cat) => setExpandedCats(prev => ({ ...prev, [cat]: !prev[cat] }));

  const getSkillLevel = (skillId) => {
    const configured = configuredSkills.find(s => s.skill_id === skillId);
    const prof = proficiency.find(p => p.skill === skillId);
    return configured?.level || prof?.level || null;
  };

  const getSkillScore = (skillId) => {
    const evalScores = evaluation.skill_scores || {};
    return evalScores[skillId]?.score || null;
  };

  // Build radar chart data from configured skills + proficiency
  const radarData = configuredSkills.length > 0
    ? configuredSkills.map(s => {
        const prof = proficiency.find(p => p.skill === s.skill_id);
        const def = skills.find(sk => sk.skill_id === s.skill_id);
        return {
          skill: def?.name || s.skill_id.replace(/_/g, " "),
          level: LEVEL_ORDER[s.level || "novice"] * 25,
          proficiency: prof?.proficiency || 0,
          fullMark: 100,
        };
      })
    : proficiency.slice(0, 12).map(p => {
        const def = skills.find(sk => sk.skill_id === p.skill);
        return {
          skill: def?.name || p.skill?.replace(/_/g, " "),
          level: LEVEL_ORDER[p.level || "novice"] * 25,
          proficiency: p.proficiency || 0,
          fullMark: 100,
        };
      });

  if (loading) return <div className="flex-1 flex items-center justify-center"><div className="text-zinc-500 text-sm">Loading skills...</div></div>;

  const groupedSkills = {};
  skills.forEach(s => {
    if (!groupedSkills[s.category]) groupedSkills[s.category] = [];
    groupedSkills[s.category].push(s);
  });

  return (
    <div className="flex-1 flex flex-col overflow-hidden" data-testid="skills-matrix">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-zinc-800/60">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100" style={{ fontFamily: "Syne, sans-serif" }}>
              Skills Matrix {agentName && <span className="text-cyan-400 ml-1">{agentName}</span>}
            </h2>
            <p className="text-xs text-zinc-500 mt-0.5">{skills.length} skills across {Object.keys(categories).length} categories</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex bg-zinc-800 rounded-lg p-0.5">
              {["radar", "heatmap", "leaderboard"].map(m => (
                <button key={m} onClick={() => setViewMode(m)} className={`px-2.5 py-1 rounded-md text-[10px] font-medium transition-colors ${viewMode === m ? "bg-zinc-700 text-zinc-100" : "text-zinc-500 hover:text-zinc-300"}`} data-testid={`view-mode-${m}`}>
                  {m === "heatmap" ? "Heatmap" : m === "radar" ? "Radar" : "Leaderboard"}
                </button>
              ))}
            </div>
            {agentId && (
              <Button onClick={runAssessment} variant="outline" className="border-zinc-700 text-zinc-300 gap-1.5 text-xs" data-testid="run-assessment-btn">
                <Trophy className="w-3.5 h-3.5" /> Assess
              </Button>
            )}
            {viewMode === "heatmap" && (
              <button onClick={() => setShowTrainingOverlay(!showTrainingOverlay)}
                className={`px-2.5 py-1 rounded-md text-[10px] font-medium transition-colors border ${showTrainingOverlay ? "bg-cyan-400/10 border-cyan-500/30 text-cyan-400" : "border-zinc-700 text-zinc-500 hover:text-zinc-300"}`}
                data-testid="training-overlay-toggle">
                <Brain className="w-3 h-3 inline mr-1" />Training Depth
              </button>
            )}
          </div>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-6">
          {/* Evaluation Summary */}
          {agentId && evaluation.overall_score > 0 && (
            <div className="bg-zinc-800/30 border border-zinc-800/60 rounded-xl p-4 mb-6" data-testid="evaluation-summary">
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 rounded-xl bg-gradient-to-br from-cyan-500/20 to-violet-500/20 flex items-center justify-center">
                  <span className="text-2xl font-bold text-cyan-400">{evaluation.overall_score}</span>
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-zinc-200">Overall Score</p>
                  <p className="text-xs text-zinc-500">Last assessed: {evaluation.last_assessed ? new Date(evaluation.last_assessed).toLocaleDateString() : "Never"}</p>
                  {evaluation.badges?.length > 0 && (
                    <div className="flex gap-1 mt-1.5">
                      {evaluation.badges.map(b => (
                        <Badge key={b} className="bg-amber-500/10 text-amber-400 text-[9px]"><Award className="w-2.5 h-2.5 mr-0.5" />{b.replace(/-/g, " ")}</Badge>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {viewMode === "radar" && (
            <div className="space-y-4" data-testid="skills-radar">
              {/* Multi-agent comparison selector */}
              {availableAgents.length > 1 && (
                <div className="bg-zinc-900/50 border border-zinc-800/40 rounded-xl p-3">
                  <p className="text-[10px] text-zinc-500 mb-2">Compare agents (select up to 3):</p>
                  <div className="flex gap-1.5 flex-wrap">
                    {availableAgents.map(a => (
                      <button key={a.agent_id} onClick={() => {
                        setCompareAgents(prev => prev.includes(a.agent_id) ? prev.filter(x => x !== a.agent_id) : prev.length < 3 ? [...prev, a.agent_id] : prev);
                      }} className={`px-2.5 py-1 rounded-md text-[10px] border transition-all ${compareAgents.includes(a.agent_id) ? "border-cyan-500/50 bg-cyan-500/10 text-cyan-300" : "border-zinc-800 text-zinc-500 hover:border-zinc-700"}`} data-testid={`compare-agent-${a.agent_id}`}>
                        {a.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {radarData.length > 0 ? (
                <div className="bg-zinc-900/50 border border-zinc-800/40 rounded-xl p-4">
                  <p className="text-xs text-zinc-500 mb-3 text-center">
                    {compareAgents.length > 0 ? "Multi-agent skill comparison" : agentId ? "Agent skill proficiency radar" : "Workspace skill distribution"}
                  </p>
                  <div className="flex justify-center">
                    <ResponsiveContainer width={450} height={380}>
                      <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="75%">
                        <PolarGrid stroke="#333" strokeDasharray="3 3" />
                        <PolarAngleAxis dataKey="skill" tick={{ fill: "#a1a1aa", fontSize: 10 }} />
                        <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: "#555", fontSize: 9 }} />
                        <Radar name="Proficiency" dataKey="proficiency" stroke="#22d3ee" fill="#22d3ee" fillOpacity={0.2} strokeWidth={2} animationDuration={800} animationEasing="ease-out" />
                        <Radar name="Level" dataKey="level" stroke="#8B5CF6" fill="#8B5CF6" fillOpacity={0.1} strokeWidth={1} strokeDasharray="4 4" animationDuration={1000} animationEasing="ease-out" />
                      </RadarChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="flex justify-center gap-4 mt-2 text-[10px]">
                    <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-cyan-400 inline-block" /> Proficiency</span>
                    <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-violet-400 inline-block border-dashed" /> Configured Level</span>
                  </div>
                </div>
              ) : (
                <div className="text-center py-16">
                  <Brain className="w-8 h-8 text-zinc-700 mx-auto mb-2" />
                  <p className="text-xs text-zinc-500">{agentId ? "No skills configured for this agent" : "Select an agent to view radar chart"}</p>
                </div>
              )}
            </div>
          )}

          {viewMode === "heatmap" && (
            <div className="space-y-4">
              {Object.entries(groupedSkills).map(([catKey, catSkills]) => {
                const cat = categories[catKey] || { label: catKey, color: "#6B7280" };
                const Icon = CATEGORY_ICONS[catKey] || Brain;
                const expanded = expandedCats[catKey] !== false; // default expanded
                return (
                  <div key={catKey} className="bg-zinc-900/50 border border-zinc-800/40 rounded-xl overflow-hidden" data-testid={`skill-category-${catKey}`}>
                    <button onClick={() => toggleCategory(catKey)} className="w-full flex items-center justify-between px-4 py-3 hover:bg-zinc-800/30 transition-colors">
                      <div className="flex items-center gap-2">
                        <Icon className="w-4 h-4" style={{ color: cat.color }} />
                        <span className="text-sm font-medium text-zinc-200">{cat.label}</span>
                        <span className="text-[10px] text-zinc-600">{catSkills.length} skills</span>
                      </div>
                      {expanded ? <ChevronDown className="w-3.5 h-3.5 text-zinc-500" /> : <ChevronRight className="w-3.5 h-3.5 text-zinc-500" />}
                    </button>
                    {expanded && (
                      <div className="px-4 pb-3">
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                          {catSkills.map(skill => {
                            const level = getSkillLevel(skill.skill_id);
                            const score = getSkillScore(skill.skill_id);
                            const depthKey = agentId ? `${agentId}:${skill.skill_id}` : "";
                            const depth = trainingDepth[depthKey] || 0;
                            const glowIntensity = Math.min(depth / 10, 1);
                            const glowStyle = showTrainingOverlay && depth > 0
                              ? { boxShadow: `0 0 ${6 + glowIntensity * 16}px ${glowIntensity * 2}px rgba(34, 211, 238, ${0.15 + glowIntensity * 0.4})`, borderColor: `rgba(34, 211, 238, ${0.1 + glowIntensity * 0.3})` }
                              : depth > 0 ? { boxShadow: `0 0 ${4 + glowIntensity * 8}px ${glowIntensity * 0.5}px rgba(34, 211, 238, ${0.1 + glowIntensity * 0.3})` } : {};
                            return (
                              <div key={skill.skill_id} className={`flex items-center gap-2.5 px-3 py-2 rounded-lg transition-all border ${showTrainingOverlay && depth > 0 ? "bg-cyan-950/20 border-cyan-800/30" : "bg-zinc-800/30 hover:bg-zinc-800/50 border-transparent"}`} style={glowStyle} data-testid={`skill-cell-${skill.skill_id}`}>
                                <div className="w-6 h-6 rounded flex items-center justify-center" style={{ backgroundColor: (skill.color || "#6366f1") + "15", color: skill.color || "#6366f1" }}>
                                  <Zap className="w-3 h-3" />
                                </div>
                                <div className="flex-1 min-w-0">
                                  <p className="text-xs text-zinc-300 truncate">{skill.name}</p>
                                  {level ? (
                                    <div className="flex items-center gap-1.5 mt-0.5">
                                      <div className="flex gap-px">
                                        {["novice", "intermediate", "advanced", "expert", "master"].map((l, i) => (
                                          <div key={l} className="w-4 h-1.5 rounded-sm" style={{ backgroundColor: LEVEL_ORDER[level] >= i ? LEVEL_COLORS[level] : "#27272a" }} />
                                        ))}
                                      </div>
                                      <span className="text-[9px]" style={{ color: LEVEL_COLORS[level] }}>{level}</span>
                                      {depth > 0 && <span className="text-[8px] text-cyan-400">{depth} chunks</span>}
                                    </div>
                                  ) : (
                                    <span className="text-[9px] text-zinc-700">not assigned</span>
                                  )}
                                  {showTrainingOverlay && depth > 0 && (
                                    <div className="mt-1 flex items-center gap-1">
                                      <div className="w-full h-1 bg-zinc-800 rounded-full overflow-hidden">
                                        <div className="h-full bg-cyan-400 rounded-full transition-all" style={{ width: `${Math.min(depth * 5, 100)}%`, opacity: 0.6 + glowIntensity * 0.4 }} />
                                      </div>
                                      <span className="text-[8px] text-cyan-400 whitespace-nowrap">{depth}</span>
                                    </div>
                                  )}
                                  {showTrainingOverlay && depth === 0 && level && (
                                    <p className="text-[8px] text-amber-500/60 mt-0.5">No training data</p>
                                  )}
                                </div>
                                {score !== null && (
                                  <span className="text-[10px] font-medium text-zinc-400">{score}%</span>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {viewMode === "leaderboard" && (
            <div className="space-y-2" data-testid="skills-leaderboard">
              <p className="text-xs text-zinc-500 mb-3">Top agents by skill proficiency across this workspace</p>
              {leaderboard.length === 0 ? (
                <div className="text-center py-12">
                  <Trophy className="w-8 h-8 text-zinc-700 mx-auto mb-2" />
                  <p className="text-xs text-zinc-500">No proficiency data yet</p>
                </div>
              ) : (
                <div className="bg-zinc-900/50 border border-zinc-800/40 rounded-xl overflow-hidden">
                  <div className="grid grid-cols-[40px_1fr_120px_80px_60px] gap-2 px-4 py-2 border-b border-zinc-800/40 text-[10px] text-zinc-600 uppercase font-semibold">
                    <span>#</span>
                    <span>Agent</span>
                    <span>Skill</span>
                    <span>Level</span>
                    <span>Score</span>
                  </div>
                  {leaderboard.slice(0, 20).map((entry, i) => (
                    <div key={`${entry.agent_key}-${entry.skill}-${i}`} className="grid grid-cols-[40px_1fr_120px_80px_60px] gap-2 px-4 py-2 items-center hover:bg-zinc-800/30 transition-colors" data-testid={`leaderboard-row-${i}`}>
                      <span className={`text-xs font-bold ${i < 3 ? "text-amber-400" : "text-zinc-600"}`}>{i + 1}</span>
                      <span className="text-xs text-zinc-300 truncate">{entry.agent_key}</span>
                      <span className="text-xs text-zinc-400">{entry.skill?.replace(/_/g, " ")}</span>
                      <Badge variant="secondary" className="text-[9px] w-fit" style={{ backgroundColor: (LEVEL_COLORS[entry.level] || "#6B7280") + "20", color: LEVEL_COLORS[entry.level] || "#6B7280" }}>
                        {entry.level || "novice"}
                      </Badge>
                      <span className="text-xs text-zinc-400">{entry.proficiency || 0}%</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
