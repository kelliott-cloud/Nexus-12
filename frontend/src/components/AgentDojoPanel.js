import { useState, useEffect } from "react";
import { api } from "@/App";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Loader2, Zap, Play, Pause, XCircle, RefreshCw, ChevronRight, Users, Clock, DollarSign, Database, Sparkles, BookOpen } from "lucide-react";
import { toast } from "sonner";

const STATUS_COLORS = {
  pending: "bg-zinc-700 text-zinc-300",
  running: "bg-amber-500/20 text-amber-400",
  completed: "bg-emerald-500/20 text-emerald-400",
  failed: "bg-red-500/20 text-red-400",
  cancelled: "bg-zinc-800 text-zinc-500",
  paused: "bg-blue-500/20 text-blue-400",
};

export default function AgentDojoPanel({ workspaceId }) {
  const [tab, setTab] = useState("sessions");
  const [sessions, setSessions] = useState([]);
  const [scenarios, setScenarios] = useState([]);
  const [extractions, setExtractions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedSession, setSelectedSession] = useState(null);
  const [analytics, setAnalytics] = useState({});

  useEffect(() => { loadData(); }, [workspaceId, tab]);

  const loadData = async () => {
    setLoading(true);
    try {
      if (tab === "sessions" || tab === "detail") {
        const r = await api.get(`/workspaces/${workspaceId}/dojo/sessions`);
        setSessions(r.data?.sessions || []);
      }
      if (tab === "dojo-scenarios") {
        const r = await api.get(`/dojo/scenarios?ws_id=${workspaceId}`);
        setScenarios(r.data?.scenarios || []);
      }
      if (tab === "dojo-data") {
        const r = await api.get(`/workspaces/${workspaceId}/dojo/analytics`).catch(() => ({ data: {} }));
        setAnalytics(r.data || {});
        const sessR = await api.get(`/workspaces/${workspaceId}/dojo/sessions?status=completed`).catch(() => ({ data: { sessions: [] } }));
        const completedSessions = sessR.data?.sessions || [];
        const allExtractions = [];
        for (const s of completedSessions.slice(0, 10)) {
          try {
            const extR = await api.get(`/dojo/sessions/${s.session_id}/extracted-data`);
            if (extR.data?.extractions) allExtractions.push(...extR.data.extractions);
            else if (extR.data) allExtractions.push(extR.data);
          } catch {}
        }
        setExtractions(allExtractions);
      }
    } catch {}
    setLoading(false);
  };

  const startSession = async (scenario) => {
    try {
      const defaultModels = ["claude", "chatgpt", "gemini", "deepseek"];
      const agents = (scenario.roles || []).map((role, i) => ({
        agent_id: defaultModels[i % defaultModels.length],
        role: role.role || `Agent ${i + 1}`, domain: role.domain || "",
        methodology: role.methodology || "", base_model: defaultModels[i % defaultModels.length], is_driver: !!role.is_driver,
      }));
      if (agents.length === 0) {
        agents.push({ agent_id: "claude", role: "analyst", base_model: "claude" });
        agents.push({ agent_id: "chatgpt", role: "critic", base_model: "chatgpt" });
      }
      const task = scenario.default_task || { description: "Collaborative analysis session", success_criteria: "Produce actionable insights" };
      const config = { ...(scenario.config_defaults || {}), max_turns: scenario.config_defaults?.max_turns || 30, cost_cap_usd: scenario.config_defaults?.cost_cap_usd || 2.0 };
      const r = await api.post(`/workspaces/${workspaceId}/dojo/sessions`, {
        scenario_id: scenario.scenario_id, agents, task: { ...task, max_turns: config.max_turns }, config, auto_start: true,
      });
      toast.success(`Dojo session started: ${r.data?.session_id}`);
      loadData();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed to start session"); }
  };

  const cancelSession = async (sessionId) => {
    try {
      await api.post(`/dojo/sessions/${sessionId}/cancel`);
      toast.success("Session cancelled");
      loadData();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const openSessionDetail = async (session) => {
    try {
      const r = await api.get(`/dojo/sessions/${session.session_id}`);
      setSelectedSession(r.data);
    } catch { setSelectedSession(session); }
    setTab("detail");
  };

  const approveExtraction = async (extractionId) => {
    try {
      await api.post(`/dojo/extracted/${extractionId}/approve`);
      toast.success("Data approved");
      try { const ir = await api.post(`/dojo/extracted/${extractionId}/ingest`); toast.success(`${ir.data?.ingested || 0} chunks ingested`); } catch {}
      loadData();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  // WebSocket listener for live dojo updates
  useEffect(() => {
    const handler = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "dojo:turn_completed" && selectedSession && data.session_id === selectedSession.session_id) {
          api.get(`/dojo/sessions/${data.session_id}`).then(r => setSelectedSession(r.data)).catch(() => {});
        }
        if (data.type === "dojo:session_completed") loadData();
      } catch {}
    };
    if (window._nexusWs) {
      window._nexusWs.addEventListener("message", handler);
      return () => window._nexusWs.removeEventListener("message", handler);
    }
  }, [selectedSession?.session_id]);

  const tabs = [
    { key: "sessions", label: "Sessions" },
    { key: "dojo-scenarios", label: "Scenarios" },
    { key: "dojo-data", label: "Training Data" },
    { key: "detail", label: "Session Detail", hidden: !selectedSession },
  ];

  if (loading) return <div className="p-8 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-zinc-500" /></div>;

  return (
    <div className="p-6 space-y-6" data-testid="agent-dojo-panel">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500 to-red-600 flex items-center justify-center">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-zinc-100" style={{ fontFamily: 'Syne, sans-serif' }}>Agent Dojo</h2>
            <p className="text-xs text-zinc-500">Autonomous agent-to-agent role-playing, mutual training, and synthetic data generation. Agents assume complementary roles and collaborate to solve tasks, generating high-quality training data from their conversations.</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={loadData} className="border-zinc-700 text-zinc-400">
          <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Refresh
        </Button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-zinc-800">
        {tabs.filter(t => !t.hidden).map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors ${
              tab === t.key ? "text-zinc-100 border-orange-500" : "text-zinc-500 border-transparent hover:text-zinc-300"
            }`} data-testid={`dojo-tab-${t.key}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Sessions Tab */}
      {tab === "sessions" && (
        <div className="space-y-3">
          {sessions.length === 0 ? (
            <div className="text-center py-12">
              <Zap className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
              <p className="text-sm text-zinc-500">No Dojo sessions yet. Pick a scenario to start training.</p>
            </div>
          ) : (
            sessions.map(s => (
              <div key={s.session_id} className="p-4 rounded-xl bg-zinc-950/50 border border-zinc-800/40 hover:border-zinc-700 cursor-pointer transition-colors"
                onClick={() => openSessionDetail(s)} data-testid={`dojo-session-${s.session_id}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Badge className={`text-[10px] ${STATUS_COLORS[s.status] || STATUS_COLORS.pending}`}>{s.status}</Badge>
                    <span className="text-sm text-zinc-200">{s.scenario_id || "Custom Session"}</span>
                    <div className="flex items-center gap-1 text-[10px] text-zinc-500">
                      <Users className="w-3 h-3" /> {(s.agents || []).length} agents
                      <Clock className="w-3 h-3 ml-2" /> {s.turn_count || 0} turns
                      <DollarSign className="w-3 h-3 ml-2" /> ${(s.cost_tracking?.total_cost_usd || 0).toFixed(4)}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {s.status === "running" && (
                      <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); cancelSession(s.session_id); }}
                        className="text-xs border-zinc-700 text-red-400 h-7"><XCircle className="w-3 h-3 mr-1" /> Cancel</Button>
                    )}
                    <ChevronRight className="w-3.5 h-3.5 text-zinc-600" />
                  </div>
                </div>
                {s.status === "running" && s.config?.max_turns && (
                  <div className="mt-2 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                    <div className="h-full bg-orange-500 rounded-full transition-all" style={{ width: `${((s.turn_count || 0) / s.config.max_turns) * 100}%` }} />
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* Scenarios Tab */}
      {tab === "dojo-scenarios" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {scenarios.length === 0 ? (
            <div className="col-span-2 text-center py-12 text-zinc-500 text-sm">Loading scenarios...</div>
          ) : (
            scenarios.map(sc => (
              <div key={sc.scenario_id} className="p-4 rounded-xl bg-zinc-950/50 border border-zinc-800/40 hover:border-zinc-700 transition-colors" data-testid={`dojo-scenario-${sc.scenario_id}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-zinc-200">{sc.name}</span>
                      <Badge className="text-[9px] bg-zinc-800 text-zinc-500">{sc.category || "general"}</Badge>
                    </div>
                    <p className="text-xs text-zinc-500 mt-1 line-clamp-2">{sc.description}</p>
                    {sc.roles && (
                      <div className="flex gap-1 mt-2">
                        {sc.roles.map((r, i) => (
                          <Badge key={i} className="text-[9px] bg-violet-500/15 text-violet-400">{r.role || r.role_name || "Agent"}</Badge>
                        ))}
                      </div>
                    )}
                  </div>
                  <Button size="sm" onClick={() => startSession(sc)}
                    className="bg-orange-600 hover:bg-orange-500 text-white text-xs h-7 shrink-0">
                    <Play className="w-3 h-3 mr-1" /> Start
                  </Button>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Training Data Tab */}
      {tab === "dojo-data" && (
        <div className="space-y-4">
          {analytics.total_sessions > 0 && (
            <div className="grid grid-cols-4 gap-3">
              <div className="p-3 rounded-lg bg-zinc-900/50 border border-zinc-800/40 text-center">
                <p className="text-lg font-semibold text-zinc-200">{analytics.completed_sessions || 0}</p>
                <p className="text-[10px] text-zinc-500">Completed Sessions</p>
              </div>
              <div className="p-3 rounded-lg bg-zinc-900/50 border border-zinc-800/40 text-center">
                <p className="text-lg font-semibold text-zinc-200">{analytics.total_pairs_extracted || 0}</p>
                <p className="text-[10px] text-zinc-500">Pairs Extracted</p>
              </div>
              <div className="p-3 rounded-lg bg-zinc-900/50 border border-zinc-800/40 text-center">
                <p className="text-lg font-semibold text-amber-400">{(analytics.avg_quality || 0).toFixed(2)}</p>
                <p className="text-[10px] text-zinc-500">Avg Quality</p>
              </div>
              <div className="p-3 rounded-lg bg-zinc-900/50 border border-zinc-800/40 text-center">
                <p className="text-lg font-semibold text-zinc-200">${(analytics.total_cost_usd || 0).toFixed(4)}</p>
                <p className="text-[10px] text-zinc-500">Total Cost</p>
              </div>
            </div>
          )}
          {extractions.length === 0 ? (
            <div className="text-center py-12">
              <Database className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
              <p className="text-sm text-zinc-500">No training data extracted yet. Complete a Dojo session to generate data.</p>
            </div>
          ) : (
            extractions.map(ext => (
              <div key={ext.extraction_id} className="rounded-xl bg-zinc-950/50 border border-zinc-800/40 overflow-hidden">
                <div className="flex items-center justify-between p-3 border-b border-zinc-800/30">
                  <div className="flex items-center gap-3">
                    <Badge className={`text-[9px] ${ext.status === "ingested" || ext.status === "approved" ? "bg-emerald-500/15 text-emerald-400" : ext.status === "rejected" ? "bg-red-500/15 text-red-400" : "bg-amber-500/15 text-amber-400"}`}>{ext.status}</Badge>
                    <span className="text-xs text-zinc-300 font-mono">{ext.session_id}</span>
                    <span className="text-[10px] text-zinc-500">{ext.pair_count || 0} pairs</span>
                    <span className="text-[10px] text-zinc-500">Avg quality: {(ext.avg_quality || 0).toFixed(2)}</span>
                  </div>
                  {ext.status === "pending" && (
                    <Button size="sm" onClick={() => approveExtraction(ext.extraction_id)}
                      className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs h-7">
                      <Sparkles className="w-3 h-3 mr-1" /> Approve & Ingest
                    </Button>
                  )}
                </div>
                {ext.pairs && ext.pairs.slice(0, 5).map((pair, pi) => (
                  <div key={pi} className="p-3 border-b border-zinc-800/20 last:border-0">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge className="text-[8px] bg-zinc-800 text-zinc-500">{pair.topic || "general"}</Badge>
                      <span className="text-[10px] text-zinc-600">Quality: {(pair.quality_score || 0).toFixed(2)}</span>
                    </div>
                    <p className="text-xs text-zinc-400 bg-zinc-900/50 rounded p-2 mb-1"><strong className="text-zinc-300">Q:</strong> {pair.question?.substring(0, 200)}</p>
                    <p className="text-xs text-zinc-500 bg-zinc-900/50 rounded p-2"><strong className="text-zinc-400">A:</strong> {pair.answer?.substring(0, 300)}</p>
                  </div>
                ))}
                {ext.pairs && ext.pairs.length > 5 && (
                  <div className="p-2 text-center text-[10px] text-zinc-600">+ {ext.pairs.length - 5} more pairs</div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* Session Detail */}
      {tab === "detail" && selectedSession && (
        <div className="space-y-4" data-testid="dojo-session-detail">
          <button onClick={() => setTab("sessions")} className="text-xs text-zinc-500 hover:text-zinc-300">&larr; Back to sessions</button>
          <div className="flex items-center gap-3">
            <Badge className={`${STATUS_COLORS[selectedSession.status]}`}>{selectedSession.status}</Badge>
            <span className="text-sm font-mono text-zinc-300">{selectedSession.session_id}</span>
          </div>
          {/* Agents */}
          <div className="flex gap-2">
            {(selectedSession.agents || []).map((a, i) => (
              <div key={i} className="px-3 py-2 rounded-lg bg-zinc-900/50 border border-zinc-800/40 text-xs">
                <span className="text-zinc-200 font-medium">{a.agent_id}</span>
                <span className="text-zinc-500 ml-2">as {a.role}</span>
              </div>
            ))}
          </div>
          {/* Turns */}
          {selectedSession.turns && selectedSession.turns.length > 0 && (
            <div className="space-y-2 max-h-[400px] overflow-y-auto">
              {selectedSession.turns.map((t, i) => (
                <div key={i} className={`p-3 rounded-lg border text-xs ${i % 2 === 0 ? "bg-violet-500/5 border-violet-500/15" : "bg-cyan-500/5 border-cyan-500/15"}`}>
                  <div className="flex items-center gap-2 mb-1">
                    <Badge className="text-[9px] bg-zinc-800 text-zinc-400">Turn {t.turn_number || i + 1}</Badge>
                    <span className="text-zinc-300 font-medium">{t.agent_id}</span>
                    <span className="text-zinc-600">({t.role})</span>
                    {t.confidence?.score != null && <span className="text-amber-400">{Math.round(t.confidence.score * 100)}%</span>}
                  </div>
                  <p className="text-zinc-400 whitespace-pre-wrap">{t.content?.substring(0, 500)}</p>
                </div>
              ))}
            </div>
          )}
          {/* Cost / Stats */}
          <div className="flex gap-4 text-xs text-zinc-500">
            <span>Turns: {selectedSession.turn_count || 0}</span>
            <span>Cost: ${(selectedSession.cost_tracking?.total_cost_usd || 0).toFixed(4)}</span>
            {selectedSession.extracted_count != null && <span>Extracted: {selectedSession.extracted_count} pairs</span>}
          </div>
        </div>
      )}
    </div>
  );
}
