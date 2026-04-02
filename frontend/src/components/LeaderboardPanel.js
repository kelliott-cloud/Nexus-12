import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { handleSilent } from "@/lib/errorHandler";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Trophy, Medal, Star, TrendingUp, Brain, MessageSquare, Loader2, Crown, Award
} from "lucide-react";

const METRICS = [
  { key: "evaluation", label: "Evaluation Score", icon: Star },
  { key: "skills", label: "Skill Count", icon: Brain },
  { key: "messages", label: "Message Volume", icon: MessageSquare },
];

const RANK_STYLES = {
  1: { bg: "bg-amber-500/10 border-amber-500/30", text: "text-amber-400", icon: Crown },
  2: { bg: "bg-zinc-400/10 border-zinc-400/30", text: "text-zinc-300", icon: Medal },
  3: { bg: "bg-orange-500/10 border-orange-400/30", text: "text-orange-400", icon: Award },
};

export default function LeaderboardPanel() {
  const [agents, setAgents] = useState([]);
  const [skills, setSkills] = useState([]);
  const [metric, setMetric] = useState("evaluation");
  const [view, setView] = useState("agents");
  const [loading, setLoading] = useState(true);
  const [snapshots, setSnapshots] = useState([]);
  const [showSnapshots, setShowSnapshots] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      if (view === "agents") {
        const res = await api.get(`/leaderboard/agents?metric=${metric}&limit=25`);
        setAgents(res.data?.leaderboard || []);
      } else if (view === "skills") {
        const res = await api.get(`/leaderboard/skills?limit=30`);
        setSkills(res.data?.leaderboard || []);
      } else if (view === "trends") {
        const res = await api.get(`/leaderboard/snapshots?days=30&limit=10`);
        setSnapshots(res.data?.snapshots || []);
      }
    } catch (err) { handleSilent(err, "Leaderboard:fetch"); }
    setLoading(false);
  }, [metric, view]);

  useEffect(() => { fetchData(); }, [fetchData]);

  return (
    <div className="flex-1 flex flex-col overflow-hidden" data-testid="leaderboard-panel">
      <div className="flex-shrink-0 px-6 py-4 border-b border-zinc-800/60">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100 flex items-center gap-2" style={{ fontFamily: "Syne, sans-serif" }}>
              <Trophy className="w-5 h-5 text-amber-400" /> Agent Leaderboard
            </h2>
            <p className="text-xs text-zinc-500 mt-0.5">Cross-workspace rankings by performance</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex gap-0.5 bg-zinc-800 rounded-lg p-0.5">
              <button onClick={() => setView("agents")}
                className={`px-2.5 py-1 rounded-md text-[10px] font-medium transition-colors ${view === "agents" ? "bg-zinc-700 text-zinc-100" : "text-zinc-500"}`}
                data-testid="lb-view-agents">Agents</button>
              <button onClick={() => setView("skills")}
                className={`px-2.5 py-1 rounded-md text-[10px] font-medium transition-colors ${view === "skills" ? "bg-zinc-700 text-zinc-100" : "text-zinc-500"}`}
                data-testid="lb-view-skills">Skills</button>
              <button onClick={() => setView("trends")}
                className={`px-2.5 py-1 rounded-md text-[10px] font-medium transition-colors ${view === "trends" ? "bg-zinc-700 text-zinc-100" : "text-zinc-500"}`}
                data-testid="lb-view-trends">Trends</button>
            </div>
            {view === "agents" && (
              <div className="flex gap-0.5 bg-zinc-800 rounded-lg p-0.5">
                {METRICS.map(m => (
                  <button key={m.key} onClick={() => setMetric(m.key)}
                    className={`px-2.5 py-1 rounded-md text-[10px] font-medium transition-colors flex items-center gap-1 ${metric === m.key ? "bg-zinc-700 text-zinc-100" : "text-zinc-500"}`}
                    data-testid={`lb-metric-${m.key}`}>
                    <m.icon className="w-3 h-3" /> {m.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="w-5 h-5 animate-spin text-zinc-500" />
        </div>
      ) : (
        <ScrollArea className="flex-1">
          <div className="p-6 max-w-3xl mx-auto space-y-2">
            {view === "agents" ? (
              agents.length === 0 ? (
                <div className="text-center py-16">
                  <Trophy className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
                  <p className="text-sm text-zinc-400">No ranked agents yet</p>
                  <p className="text-xs text-zinc-600 mt-1">Agents need evaluation scores or activity to appear on the leaderboard</p>
                </div>
              ) : (
                agents.map((agent) => {
                  const style = RANK_STYLES[agent.rank] || {};
                  const RankIcon = style.icon || TrendingUp;
                  return (
                    <div key={agent.agent_id}
                      className={`flex items-center gap-4 p-3.5 rounded-xl border transition-colors ${style.bg || "bg-zinc-900/40 border-zinc-800/40"}`}
                      data-testid={`lb-agent-${agent.rank}`}>
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold ${style.text || "text-zinc-400"}`}>
                        {agent.rank <= 3 ? <RankIcon className="w-5 h-5" /> : <span>{agent.rank}</span>}
                      </div>
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center text-[10px] font-bold text-white"
                        style={{ backgroundColor: agent.color || "#6366f1" }}>
                        {agent.name?.slice(0, 2).toUpperCase()}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-zinc-200 font-medium truncate">{agent.name}</p>
                        <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                          <span>{agent.base_model}</span>
                          <span>{agent.skills_count || 0} skills</span>
                          {agent.workspace_id && <span className="text-zinc-700">ws:{agent.workspace_id.slice(0, 8)}</span>}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-lg font-bold text-zinc-100">{typeof agent.score === "number" ? agent.score.toFixed(1) : agent.score}</div>
                        <p className="text-[9px] text-zinc-600">{metric}</p>
                      </div>
                      {agent.badges?.length > 0 && (
                        <div className="flex gap-1">
                          {agent.badges.slice(0, 3).map((b, i) => (
                            <Badge key={i} variant="secondary" className="bg-amber-500/10 text-amber-400 text-[8px]">{b}</Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })
              )
            ) : (
              skills.length === 0 ? (
                <div className="text-center py-16">
                  <Brain className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
                  <p className="text-sm text-zinc-400">No skill rankings yet</p>
                  <p className="text-xs text-zinc-600 mt-1">Agents need skill proficiency data to appear here</p>
                </div>
              ) : (
                skills.map((record) => (
                  <div key={`${record.agent_key}-${record.skill}`}
                    className="flex items-center gap-4 p-3 rounded-xl bg-zinc-900/40 border border-zinc-800/40"
                    data-testid={`lb-skill-${record.rank}`}>
                    <div className="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold text-zinc-400 bg-zinc-800">
                      {record.rank}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-zinc-200 font-medium">{record.skill}</p>
                      <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                        <span>{record.agent_key}</span>
                        <Badge variant="secondary" className="text-[8px] bg-zinc-800 text-zinc-400">{record.level}</Badge>
                        {record.streak > 0 && <span className="text-amber-500">{record.streak} streak</span>}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-bold text-zinc-100">{record.proficiency}</div>
                      <p className="text-[9px] text-zinc-600">{record.xp || 0} XP</p>
                    </div>
                  </div>
                ))
              )
            )}

            {/* Trends view */}
            {view === "trends" && (
              snapshots.length === 0 ? (
                <div className="text-center py-16">
                  <TrendingUp className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
                  <p className="text-sm text-zinc-400">No snapshots yet</p>
                  <p className="text-xs text-zinc-600 mt-1">Leaderboard snapshots are captured daily automatically</p>
                </div>
              ) : (
                snapshots.map((snap) => (
                  <div key={snap.snapshot_id} className="bg-zinc-900/40 border border-zinc-800/40 rounded-xl p-3 space-y-2"
                    data-testid={`lb-snapshot-${snap.snapshot_id}`}>
                    <div className="flex items-center justify-between">
                      <p className="text-xs text-zinc-400">{new Date(snap.timestamp).toLocaleDateString()} — {snap.total_agents} agents</p>
                      <Badge variant="secondary" className="text-[8px] bg-zinc-800 text-zinc-500">{snap.data?.length || 0} ranked</Badge>
                    </div>
                    <div className="space-y-1">
                      {(snap.data || []).slice(0, 5).map(entry => (
                        <div key={entry.agent_id} className="flex items-center gap-2 text-[10px]">
                          <span className={`w-5 text-right font-bold ${entry.rank <= 3 ? "text-amber-400" : "text-zinc-500"}`}>#{entry.rank}</span>
                          <span className="text-zinc-300 flex-1 truncate">{entry.name}</span>
                          <span className="text-zinc-500">{entry.score || 0}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))
              )
            )}
          </div>
        </ScrollArea>
      )}
    </div>
  );
}
