import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { handleSilent } from "@/lib/errorHandler";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Progress } from "@/components/ui/progress";
import {
  Cpu, Play, Loader2, CheckCircle2, XCircle, Pause, ArrowDown,
  Clock, DollarSign, BarChart3, Eye, Zap, Download, GitBranch,
  Globe, Code, FileText, Search, Plus, RotateCcw, AlertTriangle
} from "lucide-react";
import { FeatureHelp, FEATURE_HELP } from "@/components/FeatureHelp";

const TABS = ["sessions", "templates", "analytics"];

export default function OperatorPanel({ workspaceId }) {
  const [tab, setTab] = useState("sessions");
  return (
    <div className="flex-1 overflow-y-auto" data-testid="operator-panel">
      <div className="border-b border-zinc-800 px-6 pt-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100">Nexus Operator</h2>
            <p className="text-xs text-zinc-500 mt-0.5">Multi-agent autonomous computer use — parallel execution with AI agents</p>
          </div>
        </div>
        <div className="flex gap-1">
          {TABS.map(t => (
            <button key={t} onClick={() => setTab(t)} className={`px-3 py-2 text-xs font-medium border-b-2 transition-colors capitalize ${tab === t ? "border-cyan-500 text-zinc-100" : "border-transparent text-zinc-500 hover:text-zinc-300"}`} data-testid={`op-tab-${t}`}>{t}</button>
          ))}
        </div>
      </div>
      <div className="p-6 max-w-6xl mx-auto">
        <FeatureHelp featureId="operator" {...FEATURE_HELP["operator"]} />
        {tab === "sessions" && <SessionsTab workspaceId={workspaceId} />}
        {tab === "templates" && <TemplatesTab workspaceId={workspaceId} />}
        {tab === "analytics" && <AnalyticsTab workspaceId={workspaceId} />}
      </div>
    </div>
  );
}

function SessionsTab({ workspaceId }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [goal, setGoal] = useState("");
  const [creating, setCreating] = useState(false);
  const [selected, setSelected] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [polling, setPolling] = useState(null);

  const fetchSessions = useCallback(async () => {
    try { const r = await api.get(`/workspaces/${workspaceId}/operator/sessions`); setSessions(r.data.sessions || []); } catch (err) { handleSilent(err, "OP:list"); }
    setLoading(false);
  }, [workspaceId]);

  useEffect(() => { fetchSessions(); }, [fetchSessions]);

  // Poll selected session
  useEffect(() => {
    if (!selected || !["executing", "planning"].includes(selected.status)) { if (polling) clearInterval(polling); return; }
    const iv = setInterval(async () => {
      try {
        const r = await api.get(`/operator/sessions/${selected.session_id}`);
        setSelected(r.data);
        const t = await api.get(`/operator/sessions/${selected.session_id}/tasks`);
        setTasks(t.data.tasks || []);
        if (["completed", "failed", "cancelled"].includes(r.data.status)) { clearInterval(iv); fetchSessions(); }
      } catch (err) { handleSilent(err, "OP:poll"); }
    }, 2000);
    setPolling(iv);
    return () => clearInterval(iv);
  }, [selected?.session_id, selected?.status]);

  const createSession = async () => {
    if (!goal.trim()) return;
    setCreating(true);
    try {
      const r = await api.post(`/workspaces/${workspaceId}/operator/sessions`, { goal, goal_type: "general" });
      toast.success("Session created — review the task plan");
      setGoal("");
      setSelected(r.data);
      fetchSessions();
    } catch (err) { toast.error("Failed to create session"); }
    setCreating(false);
  };

  const quickExecute = async () => {
    if (!goal.trim()) return;
    setCreating(true);
    try {
      const r = await api.post(`/workspaces/${workspaceId}/operator/quick`, { goal });
      toast.success(`Executing with ${r.data.task_count} tasks`);
      setGoal("");
      const full = await api.get(`/operator/sessions/${r.data.session_id}`);
      setSelected(full.data);
      fetchSessions();
    } catch (err) { toast.error("Failed"); }
    setCreating(false);
  };

  const approvePlan = async () => {
    if (!selected) return;
    try {
      await api.post(`/operator/sessions/${selected.session_id}/approve-plan`);
      toast.success("Execution started");
      const r = await api.get(`/operator/sessions/${selected.session_id}`);
      setSelected(r.data);
    } catch (err) { toast.error("Approve failed"); }
  };

  const cancelSession = async (sid) => {
    try { await api.post(`/operator/sessions/${sid}/cancel`); toast.success("Cancelled"); fetchSessions(); if (selected?.session_id === sid) setSelected(null); } catch (err) { toast.error("Cancel failed"); }
  };

  const viewSession = async (s) => {
    try {
      const [full, t] = await Promise.all([api.get(`/operator/sessions/${s.session_id}`), api.get(`/operator/sessions/${s.session_id}/tasks`)]);
      setSelected(full.data);
      setTasks(t.data.tasks || []);
    } catch (err) { handleSilent(err, "OP:view"); }
  };

  const statusIcon = (s) => {
    if (s === "completed") return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
    if (s === "failed") return <XCircle className="w-4 h-4 text-red-400" />;
    if (s === "executing" || s === "running") return <Loader2 className="w-4 h-4 text-cyan-400 animate-spin" />;
    if (s === "planning") return <Cpu className="w-4 h-4 text-amber-400" />;
    if (s === "paused") return <Pause className="w-4 h-4 text-amber-400" />;
    return <Clock className="w-4 h-4 text-zinc-500" />;
  };

  const statusColor = (s) => {
    if (s === "completed") return "border-emerald-800 text-emerald-400";
    if (s === "failed") return "border-red-800 text-red-400";
    if (s === "executing") return "border-cyan-800 text-cyan-400";
    if (s === "planning") return "border-amber-800 text-amber-400";
    return "border-zinc-700 text-zinc-400";
  };

  const typeIcon = (t) => {
    if (t?.includes("browser") || t?.includes("research")) return <Globe className="w-3 h-3" />;
    if (t?.includes("code")) return <Code className="w-3 h-3" />;
    if (t?.includes("writ") || t?.includes("doc")) return <FileText className="w-3 h-3" />;
    if (t?.includes("search")) return <Search className="w-3 h-3" />;
    return <Zap className="w-3 h-3" />;
  };

  if (loading) return <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-zinc-500" /></div>;

  return (
    <div className="space-y-4">
      {/* Goal Input */}
      <Card className="bg-zinc-900 border-zinc-800" data-testid="op-goal-card">
        <CardContent className="py-4 space-y-3">
          <Textarea placeholder="Describe what you want the Operator to do... (e.g., 'Research top 5 CRM tools and create a comparison document')" value={goal} onChange={e => setGoal(e.target.value)} rows={2} className="bg-zinc-800 border-zinc-700" data-testid="op-goal-input" />
          <div className="flex gap-2">
            <Button onClick={quickExecute} disabled={creating || !goal.trim()} className="bg-cyan-600 hover:bg-cyan-700 flex-1" data-testid="op-quick-btn">
              {creating ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Zap className="w-4 h-4 mr-2" />} Quick Execute
            </Button>
            <Button onClick={createSession} disabled={creating || !goal.trim()} variant="outline" className="border-zinc-700" data-testid="op-plan-btn">
              <Cpu className="w-4 h-4 mr-2" /> Plan First
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Selected Session Detail */}
      {selected && (
        <Card className="bg-zinc-900 border-zinc-800" data-testid="op-session-detail">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {statusIcon(selected.status)}
                <CardTitle className="text-sm text-zinc-100">{selected.goal?.slice(0, 80)}</CardTitle>
                <Badge variant="outline" className={`text-xs ${statusColor(selected.status)}`}>{selected.status}</Badge>
              </div>
              <div className="flex gap-1">
                {selected.status === "planning" && <Button size="sm" onClick={approvePlan} className="bg-emerald-600 hover:bg-emerald-700 h-7 text-xs" data-testid="op-approve"><Play className="w-3 h-3 mr-1" /> Approve & Execute</Button>}
                {["executing", "planning"].includes(selected.status) && <Button size="sm" variant="ghost" onClick={() => cancelSession(selected.session_id)} className="h-7 text-xs text-red-400">Cancel</Button>}
                <Button size="sm" variant="ghost" onClick={() => setSelected(null)} className="h-7 text-xs">Close</Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Metrics */}
            {selected.metrics && (
              <div className="grid grid-cols-4 gap-2">
                {[
                  { label: "Cost", value: `$${selected.metrics.total_cost_usd?.toFixed(4) || "0"}`, icon: DollarSign },
                  { label: "Duration", value: selected.metrics.total_duration_ms ? `${(selected.metrics.total_duration_ms / 1000).toFixed(1)}s` : "...", icon: Clock },
                  { label: "Tasks Done", value: `${selected.metrics.tasks_completed || 0}/${(selected.task_plan?.tasks || []).length}`, icon: CheckCircle2 },
                  { label: "Parallel Peak", value: selected.metrics.parallel_peak || 0, icon: GitBranch },
                ].map(({ label, value, icon: Icon }) => (
                  <div key={label} className="p-2 bg-zinc-800/50 rounded text-center">
                    <Icon className="w-3.5 h-3.5 text-zinc-500 mx-auto mb-1" />
                    <div className="text-sm font-bold text-zinc-200">{value}</div>
                    <div className="text-xs text-zinc-600">{label}</div>
                  </div>
                ))}
              </div>
            )}

            {/* Task Plan / Live Execution */}
            <div className="space-y-2">
              <h4 className="text-xs font-medium text-zinc-400">Task Execution</h4>
              {(tasks.length > 0 ? tasks : (selected.task_plan?.tasks || [])).map((task, i) => {
                const exec = tasks.find(t => t.task_id === (task.task_id || task.task_id));
                const status = exec?.status || "queued";
                return (
                  <div key={task.task_id || i} className={`p-3 rounded-lg border ${status === "completed" ? "border-emerald-800/30 bg-emerald-900/5" : status === "failed" ? "border-red-800/30 bg-red-900/5" : status === "running" ? "border-cyan-800/30 bg-cyan-900/5" : "border-zinc-800"}`}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        {statusIcon(status)}
                        <span className="text-xs text-zinc-500">{typeIcon(task.type)}</span>
                        <span className="text-sm text-zinc-200">{task.goal?.slice(0, 80) || task.name}</span>
                        {task.parallel_group && <Badge variant="outline" className="text-xs border-zinc-700 py-0">{task.parallel_group}</Badge>}
                      </div>
                      <div className="flex items-center gap-2 text-xs text-zinc-500">
                        {exec?.cost_usd > 0 && <span>${exec.cost_usd.toFixed(4)}</span>}
                        {exec?.duration_ms > 0 && <span>{(exec.duration_ms / 1000).toFixed(1)}s</span>}
                        <span className="text-cyan-400/60">{exec?.model || task.estimated_model_tier || ""}</span>
                      </div>
                    </div>
                    {exec?.output && <div className="text-xs text-zinc-400 mt-1 max-h-24 overflow-y-auto whitespace-pre-wrap bg-zinc-800/30 p-2 rounded">{exec.output.slice(0, 1000)}</div>}
                    {exec?.error && <div className="text-xs text-red-400 mt-1">{exec.error}</div>}
                    {i < (tasks.length || selected.task_plan?.tasks?.length || 0) - 1 && !task.parallel_group && <div className="flex justify-center py-0.5"><ArrowDown className="w-3 h-3 text-zinc-700" /></div>}
                  </div>
                );
              })}
            </div>

            {/* Results */}
            {selected.results?.summary && (
              <div className="p-3 bg-zinc-800/50 rounded-lg border border-zinc-700/30">
                <h4 className="text-xs font-medium text-zinc-400 mb-1">Results Summary</h4>
                <div className="text-sm text-zinc-200 whitespace-pre-wrap max-h-60 overflow-y-auto">{selected.results.summary}</div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Session History */}
      <h3 className="text-sm font-medium text-zinc-300">Session History</h3>
      {sessions.length === 0 ? (
        <p className="text-xs text-zinc-500 text-center py-8">No operator sessions yet. Enter a goal above to start.</p>
      ) : sessions.map(s => (
        <Card key={s.session_id} className="bg-zinc-900/50 border-zinc-800 hover:border-zinc-700 cursor-pointer transition-colors" onClick={() => viewSession(s)} data-testid={`op-session-${s.session_id}`}>
          <CardContent className="py-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              {statusIcon(s.status)}
              <span className="text-sm text-zinc-200">{s.goal?.slice(0, 60)}</span>
              <Badge variant="outline" className={`text-xs ${statusColor(s.status)}`}>{s.status}</Badge>
            </div>
            <div className="flex items-center gap-3 text-xs text-zinc-500">
              <span>{s.task_count} tasks</span>
              {s.metrics?.total_cost_usd > 0 && <span>${s.metrics.total_cost_usd.toFixed(4)}</span>}
              <span>{new Date(s.created_at).toLocaleString()}</span>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function TemplatesTab({ workspaceId }) {
  const [templates, setTemplates] = useState([]);
  useEffect(() => { api.get(`/workspaces/${workspaceId}/operator/templates`).then(r => setTemplates(r.data.templates || [])).catch(() => {}); }, [workspaceId]);

  const catColors = { research: "border-blue-800 text-blue-400", development: "border-emerald-800 text-emerald-400", content: "border-purple-800 text-purple-400", productivity: "border-cyan-800 text-cyan-400" };
  const [executing, setExecuting] = useState(null);

  const handleUseTemplate = async (tpl) => {
    setExecuting(tpl.template_id);
    const goal = prompt(`Enter details for: ${tpl.name}\n\nGoal template: ${tpl.goal}`, tpl.goal);
    if (!goal) { setExecuting(null); return; }
    try {
      await api.post(`/workspaces/${workspaceId}/operator/quick`, { goal, goal_type: tpl.category });
      toast.success("Operator session started");
    } catch (err) { toast.error("Failed"); }
    setExecuting(null);
  };

  return (
    <div className="space-y-4" data-testid="op-templates">
      <p className="text-sm text-zinc-500">Pre-built operator workflows. Click to customize and execute.</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {templates.map(tpl => (
          <Card key={tpl.template_id} className="bg-zinc-900 border-zinc-800 hover:border-zinc-700 transition-colors">
            <CardContent className="py-4 space-y-3">
              <div className="flex items-start justify-between">
                <div><h3 className="text-sm font-medium text-zinc-100">{tpl.name}</h3><Badge variant="outline" className={`text-xs mt-1 ${catColors[tpl.category] || "border-zinc-700"}`}>{tpl.category}</Badge></div>
                <div className="text-right text-xs text-zinc-500"><div>~${tpl.estimated_cost}</div><div>{tpl.estimated_time}</div></div>
              </div>
              <p className="text-xs text-zinc-400">{tpl.description}</p>
              <Button size="sm" onClick={() => handleUseTemplate(tpl)} disabled={executing === tpl.template_id} className="bg-cyan-600 hover:bg-cyan-700 w-full text-xs">
                {executing === tpl.template_id ? <Loader2 className="w-3 h-3 animate-spin" /> : <><Play className="w-3 h-3 mr-1" /> Use Template</>}
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function AnalyticsTab({ workspaceId }) {
  const [data, setData] = useState(null);
  useEffect(() => { api.get(`/workspaces/${workspaceId}/operator/analytics`).then(r => setData(r.data)).catch(() => {}); }, [workspaceId]);
  if (!data) return <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-zinc-500" /></div>;

  return (
    <div className="space-y-4" data-testid="op-analytics">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Total Sessions", value: data.total_sessions, icon: Cpu, color: "text-cyan-400" },
          { label: "Success Rate", value: `${data.success_rate}%`, icon: CheckCircle2, color: data.success_rate >= 80 ? "text-emerald-400" : "text-amber-400" },
          { label: "Total Cost", value: `$${data.total_cost_usd}`, icon: DollarSign, color: "text-emerald-400" },
          { label: "Tasks Executed", value: data.total_tasks_executed, icon: Zap, color: "text-zinc-300" },
        ].map(({ label, value, icon: Icon, color }) => (
          <Card key={label} className="bg-zinc-900 border-zinc-800">
            <CardContent className="py-4 text-center">
              <Icon className={`w-5 h-5 mx-auto mb-2 ${color}`} />
              <div className={`text-2xl font-bold ${color}`}>{value}</div>
              <div className="text-xs text-zinc-500 mt-1">{label}</div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
