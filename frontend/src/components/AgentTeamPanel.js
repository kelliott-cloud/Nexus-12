import { useState, useEffect } from "react";
import { api } from "@/App";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Loader2, Users, Play, Check, X, AlertTriangle, ChevronRight, RefreshCw, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

const STATUS_COLORS = {
  decomposing: "bg-violet-500/20 text-violet-400", running: "bg-amber-500/20 text-amber-400",
  validating: "bg-cyan-500/20 text-cyan-400", escalated: "bg-red-500/20 text-red-400",
  completed: "bg-emerald-500/20 text-emerald-400", failed: "bg-red-500/20 text-red-400",
};

export default function AgentTeamPanel({ workspaceId }) {
  const [tab, setTab] = useState("sessions");
  const [sessions, setSessions] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [goal, setGoal] = useState("");
  const [starting, setStarting] = useState(false);
  const [selected, setSelected] = useState(null);
  const [costLimit, setCostLimit] = useState(1.0);
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.7);
  const [selectedTemplate, setSelectedTemplate] = useState("");
  const [newTemplateName, setNewTemplateName] = useState("");

  useEffect(() => { loadData(); }, [workspaceId, tab]);

  // WebSocket listener for real-time updates
  useEffect(() => {
    const handler = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "agent_team_update" && selected && data.session_id === selected.session_id) {
          loadDetail(data.session_id);
        }
        if (data.event === "completed" || data.event === "escalated") {
          loadData();
        }
      } catch {}
    };
    if (window._nexusWs) {
      window._nexusWs.addEventListener("message", handler);
      return () => window._nexusWs.removeEventListener("message", handler);
    }
  }, [selected?.session_id]);

  const loadData = async () => {
    setLoading(true);
    try {
      if (tab === "sessions" || tab === "detail") {
        const r = await api.get(`/workspaces/${workspaceId}/agent-teams`);
        setSessions(r.data?.sessions || []);
      }
      if (tab === "templates") {
        const r = await api.get(`/workspaces/${workspaceId}/agent-team-templates`);
        setTemplates(r.data?.templates || []);
      }
    } catch {}
    setLoading(false);
  };

  const startTeam = async () => {
    if (!goal.trim() || goal.length < 10) { toast.error("Goal must be at least 10 characters"); return; }
    setStarting(true);
    try {
      const settings = { max_cost_usd: costLimit, confidence_threshold: confidenceThreshold, max_retries_per_subtask: 2, min_subtask_score: 0.6 };
      let r;
      if (selectedTemplate) {
        r = await api.post(`/workspaces/${workspaceId}/agent-teams/start-from-template`, { goal, template_id: selectedTemplate, settings });
      } else {
        r = await api.post(`/workspaces/${workspaceId}/agent-teams/start`, { goal, settings });
      }
      toast.success(`Team started: ${r.data?.session_id}`);
      setGoal("");
      setTimeout(loadData, 2000);
      setTimeout(loadData, 10000);
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
    setStarting(false);
  };

  const approveSession = async (sessionId, action, feedback = "") => {
    try {
      await api.post(`/workspaces/${workspaceId}/agent-teams/${sessionId}/approve`, { action, feedback });
      toast.success(`Action: ${action}`);
      loadData();
      if (selected?.session_id === sessionId) loadDetail(sessionId);
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const createTemplate = async () => {
    if (!newTemplateName.trim()) return;
    try {
      await api.post(`/workspaces/${workspaceId}/agent-team-templates`, {
        name: newTemplateName, description: "", default_settings: { max_cost_usd: costLimit, confidence_threshold: confidenceThreshold },
      });
      toast.success("Template saved");
      setNewTemplateName("");
      loadData();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const deleteTemplate = async (templateId) => {
    try {
      await api.delete(`/workspaces/${workspaceId}/agent-team-templates/${templateId}`);
      toast.success("Deleted");
      loadData();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const loadDetail = async (sessionId) => {
    try {
      const r = await api.get(`/workspaces/${workspaceId}/agent-teams/${sessionId}`);
      setSelected(r.data);
      setTab("detail");
    } catch { toast.error("Failed to load session"); }
  };

  const tabs = [
    { key: "sessions", label: "Sessions" },
    { key: "templates", label: "Templates" },
    { key: "detail", label: "Detail", hidden: !selected },
  ];

  return (
    <div className="p-6 space-y-6" data-testid="agent-team-panel">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-cyan-600 flex items-center justify-center">
            <Users className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-zinc-100" style={{ fontFamily: 'Syne, sans-serif' }}>Agent Teams</h2>
            <p className="text-xs text-zinc-500">Autonomous multi-model task execution with self-correction and human escalation</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={loadData} className="border-zinc-700 text-zinc-400">
          <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Refresh
        </Button>
      </div>

      {/* Goal Input + Settings */}
      <div className="p-4 rounded-xl bg-zinc-900/40 border border-zinc-800/50 space-y-3">
        <div className="flex gap-3">
          <Input value={goal} onChange={e => setGoal(e.target.value)} onKeyDown={e => e.key === "Enter" && startTeam()}
            placeholder="Describe a complex goal for the team to accomplish..."
            className="bg-zinc-950 border-zinc-800 text-sm flex-1" data-testid="team-goal-input" />
          <Button onClick={startTeam} disabled={starting || goal.length < 10}
            className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs shrink-0" data-testid="team-start-btn">
            {starting ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <Play className="w-3.5 h-3.5 mr-1" />} Launch Team
          </Button>
        </div>
        <div className="flex items-center gap-4 flex-wrap text-xs">
          {templates.length > 0 && (
            <select value={selectedTemplate} onChange={e => setSelectedTemplate(e.target.value)}
              className="bg-zinc-950 border border-zinc-800 rounded-lg px-2 py-1.5 text-xs text-zinc-300" data-testid="team-template-select">
              <option value="">No template</option>
              {templates.map(t => <option key={t.template_id} value={t.template_id}>{t.name}</option>)}
            </select>
          )}
          <label className="flex items-center gap-1.5 text-zinc-500">
            Budget: <input type="range" min="0.25" max="5" step="0.25" value={costLimit} onChange={e => setCostLimit(Number(e.target.value))}
              className="w-24 h-1.5 accent-emerald-500" /> <span className="text-zinc-300 w-12">${costLimit.toFixed(2)}</span>
          </label>
          <label className="flex items-center gap-1.5 text-zinc-500">
            Confidence: <input type="range" min="0.5" max="0.95" step="0.05" value={confidenceThreshold} onChange={e => setConfidenceThreshold(Number(e.target.value))}
              className="w-24 h-1.5 accent-cyan-500" /> <span className="text-zinc-300 w-10">{(confidenceThreshold * 100).toFixed(0)}%</span>
          </label>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-zinc-800">
        {tabs.filter(t => !t.hidden).map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors ${
              tab === t.key ? "text-zinc-100 border-emerald-500" : "text-zinc-500 border-transparent hover:text-zinc-300"
            }`}>{t.label}</button>
        ))}
      </div>

      {loading ? <div className="py-12 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-zinc-500" /></div> : (
        <>
          {tab === "sessions" && (
            <div className="space-y-2">
              {sessions.length === 0 ? (
                <div className="text-center py-12 text-zinc-500 text-sm">No team sessions yet. Enter a goal above to launch one.</div>
              ) : sessions.map(s => (
                <div key={s.session_id} className="p-4 rounded-xl bg-zinc-950/50 border border-zinc-800/40 hover:border-zinc-700 cursor-pointer transition-colors"
                  onClick={() => loadDetail(s.session_id)} data-testid={`team-session-${s.session_id}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      <Badge className={`text-[10px] shrink-0 ${STATUS_COLORS[s.status] || STATUS_COLORS.running}`}>{s.status}</Badge>
                      <span className="text-sm text-zinc-200 truncate">{s.goal}</span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0 text-[10px] text-zinc-500">
                      <span>{(s.decomposition?.subtask_count || 0)} subtasks</span>
                      <span>${(s.total_cost_usd || 0).toFixed(4)}</span>
                      {s.status === "escalated" && <AlertTriangle className="w-3.5 h-3.5 text-red-400" />}
                      <ChevronRight className="w-3.5 h-3.5 text-zinc-600" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {tab === "templates" && (
            <div className="space-y-3">
              <div className="flex gap-2">
                <Input value={newTemplateName} onChange={e => setNewTemplateName(e.target.value)}
                  placeholder="New template name..." className="bg-zinc-950 border-zinc-800 text-sm flex-1" />
                <Button size="sm" onClick={createTemplate} disabled={!newTemplateName.trim()}
                  className="bg-cyan-600 hover:bg-cyan-500 text-white text-xs"><Plus className="w-3 h-3 mr-1" /> Save</Button>
              </div>
              {templates.length === 0 ? (
                <div className="text-center py-12 text-zinc-500 text-sm">No team templates yet.</div>
              ) : templates.map(t => (
                <div key={t.template_id} className="flex items-center justify-between p-3 rounded-xl bg-zinc-950/50 border border-zinc-800/40">
                  <div>
                    <span className="text-sm font-medium text-zinc-200">{t.name}</span>
                    <p className="text-xs text-zinc-500 mt-0.5">{t.description || `Used ${t.times_used}x`}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-zinc-600">{t.times_used}x</span>
                    <button onClick={() => deleteTemplate(t.template_id)} className="p-1 text-zinc-600 hover:text-red-400">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {tab === "detail" && selected && (
            <div className="space-y-4" data-testid="team-detail">
              <button onClick={() => setTab("sessions")} className="text-xs text-zinc-500 hover:text-zinc-300">&larr; Back</button>
              <div className="flex items-center gap-3">
                <Badge className={`${STATUS_COLORS[selected.status]}`}>{selected.status}</Badge>
                <span className="text-sm font-mono text-zinc-300">{selected.session_id}</span>
                {selected.overall_confidence != null && <span className="text-xs text-zinc-500">Confidence: {(selected.overall_confidence * 100).toFixed(0)}%</span>}
              </div>
              <p className="text-sm text-zinc-300">{selected.goal}</p>

              {/* Escalation actions */}
              {selected.status === "escalated" && (
                <div className="p-3 rounded-lg bg-red-500/5 border border-red-500/20">
                  <p className="text-xs text-red-400 mb-2">{selected.escalation?.reason}</p>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={() => approveSession(selected.session_id, "approve")} className="bg-emerald-600 text-white text-xs h-7">
                      <Check className="w-3 h-3 mr-1" /> Approve & Deliver
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => approveSession(selected.session_id, "retry")} className="border-zinc-700 text-amber-400 text-xs h-7">Retry</Button>
                    <Button size="sm" variant="outline" onClick={() => approveSession(selected.session_id, "cancel")} className="border-zinc-700 text-red-400 text-xs h-7">Cancel</Button>
                  </div>
                </div>
              )}

              {/* Subtasks */}
              {selected.subtasks?.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-medium text-zinc-400">Subtasks ({selected.subtasks.length})</p>
                  {selected.subtasks.map((st, i) => (
                    <div key={st.subtask_id} className={`p-3 rounded-lg border ${
                      st.status === "completed" ? "border-emerald-500/20 bg-emerald-500/5" :
                      st.status === "failed" ? "border-red-500/20 bg-red-500/5" : "border-zinc-800/40 bg-zinc-950/50"
                    }`}>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Badge className="text-[9px] bg-zinc-800 text-zinc-400">{st.subtask_id}</Badge>
                          <span className="text-xs text-zinc-200">{st.title}</span>
                        </div>
                        <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                          {st.assigned_model && <Badge className="text-[8px] bg-zinc-800 text-zinc-400">{st.assigned_model}</Badge>}
                          {st.confidence != null && <span>{(st.confidence * 100).toFixed(0)}%</span>}
                          {st.status === "completed" ? <Check className="w-3 h-3 text-emerald-400" /> : st.status === "failed" ? <X className="w-3 h-3 text-red-400" /> : null}
                        </div>
                      </div>
                      {st.output && <p className="text-xs text-zinc-400 mt-2 bg-zinc-900/50 rounded p-2 max-h-32 overflow-y-auto whitespace-pre-wrap">{st.output.substring(0, 500)}</p>}
                      {st.validation && <p className="text-[10px] text-zinc-600 mt-1">Validated by {st.validation.validator_model}: {(st.validation.score * 100).toFixed(0)}%</p>}
                    </div>
                  ))}
                </div>
              )}

              {/* Audit Trail */}
              {selected.audit_trail?.length > 0 && (
                <div className="p-3 rounded-xl bg-zinc-900/50 border border-zinc-800/40">
                  <p className="text-xs font-medium text-zinc-400 mb-2">Audit Trail</p>
                  <div className="space-y-1 max-h-[200px] overflow-y-auto text-[10px] text-zinc-600">
                    {selected.audit_trail.map((a, i) => (
                      <div key={i}>{a.timestamp?.substring(11, 19)} — <span className="text-zinc-400">{a.event}</span>: {a.detail}</div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
