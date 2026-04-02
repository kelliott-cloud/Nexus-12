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
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  GitBranch, Play, Plus, Trash2, Loader2, CheckCircle2, XCircle, Pause,
  RotateCcw, ArrowRight, ArrowDown, Zap, Download, Eye, BarChart3,
  Clock, DollarSign, AlertTriangle, BookTemplate, Settings2
} from "lucide-react";
import { FeatureHelp, FEATURE_HELP } from "@/components/FeatureHelp";

const TABS = ["pipelines", "templates", "analytics"];

export default function A2APipelinePanel({ workspaceId }) {
  const [tab, setTab] = useState("pipelines");
  const [agents, setAgents] = useState([]);

  useEffect(() => {
    api.get(`/workspaces/${workspaceId}/agents`).then(r => {
      const a = r.data?.agents || r.data || [];
      setAgents(a);
    }).catch(() => {});
  }, [workspaceId]);

  return (
    <div className="flex-1 overflow-y-auto" data-testid="a2a-pipeline-panel">
      <div className="border-b border-zinc-800 px-6 pt-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100">A2A Autonomous Workflows</h2>
            <p className="text-xs text-zinc-500 mt-0.5">Multi-agent pipelines with quality gates, routing, and retries</p>
          </div>
        </div>
        <div className="flex gap-1">
          {TABS.map(t => (
            <button key={t} onClick={() => setTab(t)} className={`px-3 py-2 text-xs font-medium border-b-2 transition-colors capitalize ${tab === t ? "border-cyan-500 text-zinc-100" : "border-transparent text-zinc-500 hover:text-zinc-300"}`} data-testid={`a2a-tab-${t}`}>{t}</button>
          ))}
        </div>
      </div>
      <div className="p-6 max-w-6xl mx-auto">
        <FeatureHelp featureId="a2a-pipelines" {...FEATURE_HELP["a2a-pipelines"]} />
        {tab === "pipelines" && <PipelinesTab workspaceId={workspaceId} agents={agents} />}
        {tab === "templates" && <TemplatesTab workspaceId={workspaceId} />}
        {tab === "analytics" && <AnalyticsTab workspaceId={workspaceId} />}
      </div>
    </div>
  );
}

function PipelinesTab({ workspaceId, agents }) {
  const [pipelines, setPipelines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState("list");
  const [selectedPipeline, setSelectedPipeline] = useState(null);
  const [runs, setRuns] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);
  const [runSteps, setRunSteps] = useState([]);
  const [triggerPayload, setTriggerPayload] = useState("");
  const [triggering, setTriggering] = useState(false);
  // Create form
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [steps, setSteps] = useState([{ name: "", agent_id: "", prompt_template: "{trigger_payload}", quality_gate: { enabled: false }, routing: { type: "sequential" } }]);

  const fetchPipelines = useCallback(async () => {
    try {
      const r = await api.get(`/workspaces/${workspaceId}/a2a/pipelines`);
      setPipelines(r.data.pipelines || []);
    } catch (err) { handleSilent(err, "A2A:list"); }
    setLoading(false);
  }, [workspaceId]);

  useEffect(() => { fetchPipelines(); }, [fetchPipelines]);

  const createPipeline = async () => {
    if (!name.trim()) return toast.error("Name required");
    try {
      const stepsData = steps.filter(s => s.agent_id).map((s, i) => ({
        ...s, step_id: `step_${String(i).padStart(3, '0')}`,
        routing: { ...s.routing, next_step_id: i < steps.length - 1 ? `step_${String(i + 1).padStart(3, '0')}` : null },
      }));
      await api.post(`/workspaces/${workspaceId}/a2a/pipelines`, { name, description, steps: stepsData, settings: { max_total_cost_usd: 5.0, on_failure: "pause_and_notify" } });
      toast.success("Pipeline created");
      setView("list"); setName(""); setDescription("");
      setSteps([{ name: "", agent_id: "", prompt_template: "{trigger_payload}", quality_gate: { enabled: false }, routing: { type: "sequential" } }]);
      fetchPipelines();
    } catch (err) { toast.error("Failed"); }
  };

  const triggerPipeline = async (pipelineId) => {
    setTriggering(true);
    try {
      const res = await api.post(`/a2a/pipelines/${pipelineId}/trigger`, { trigger_type: "manual", payload: triggerPayload || "Manual trigger" });
      toast.success(`Run started: ${res.data.run_id}`);
      setTriggerPayload("");
      if (selectedPipeline) fetchRuns(pipelineId);
    } catch (err) { toast.error("Trigger failed"); }
    setTriggering(false);
  };

  const fetchRuns = async (pipelineId) => {
    try {
      const r = await api.get(`/a2a/pipelines/${pipelineId}/runs`);
      setRuns(r.data.runs || []);
    } catch (err) { handleSilent(err, "A2A:runs"); }
  };

  const viewRun = async (runId) => {
    try {
      const [runRes, stepsRes] = await Promise.all([
        api.get(`/a2a/runs/${runId}`),
        api.get(`/a2a/runs/${runId}/steps`),
      ]);
      setSelectedRun(runRes.data);
      setRunSteps(stepsRes.data.steps || []);
    } catch (err) { handleSilent(err, "A2A:runDetail"); }
  };

  const selectPipeline = (p) => { setSelectedPipeline(p); setView("detail"); fetchRuns(p.pipeline_id); };

  const toggleStatus = async (p) => {
    try {
      const action = p.status === "active" ? "pause" : "activate";
      await api.post(`/a2a/pipelines/${p.pipeline_id}/${action}`);
      toast.success(action === "activate" ? "Activated" : "Paused");
      fetchPipelines();
    } catch (err) { toast.error("Failed"); }
  };

  const deletePipeline = async (pipelineId) => {
    try { await api.delete(`/a2a/pipelines/${pipelineId}`); toast.success("Deleted"); fetchPipelines(); setView("list"); } catch (err) { toast.error("Delete failed"); }
  };

  const addStep = () => setSteps([...steps, { name: "", agent_id: "", prompt_template: "{pipeline_context}", quality_gate: { enabled: false }, routing: { type: "sequential" } }]);
  const removeStep = (i) => setSteps(steps.filter((_, idx) => idx !== i));
  const updateStep = (i, field, val) => { const u = [...steps]; u[i] = { ...u[i], [field]: val }; setSteps(u); };

  const statusBadge = (status) => {
    const m = { active: "border-emerald-800 text-emerald-400", paused: "border-amber-800 text-amber-400", draft: "border-zinc-700 text-zinc-400", running: "border-blue-800 text-blue-400", completed: "border-emerald-800 text-emerald-400", failed: "border-red-800 text-red-400", cancelled: "border-zinc-700 text-zinc-500" };
    return <Badge variant="outline" className={`text-xs ${m[status] || "border-zinc-700"}`}>{status}</Badge>;
  };

  if (loading) return <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-zinc-500" /></div>;

  return (
    <div className="space-y-4">
      {view === "list" && (
        <>
          <div className="flex justify-end"><Button size="sm" onClick={() => setView("create")} className="bg-cyan-600 hover:bg-cyan-700" data-testid="a2a-create-btn"><Plus className="w-3.5 h-3.5 mr-1" /> New Pipeline</Button></div>
          {pipelines.length === 0 ? (
            <Card className="bg-zinc-900 border-zinc-800"><CardContent className="py-12 text-center text-zinc-500">No A2A pipelines yet. Create one or install a template.</CardContent></Card>
          ) : pipelines.map(p => (
            <Card key={p.pipeline_id} className="bg-zinc-900/50 border-zinc-800 hover:border-zinc-700 cursor-pointer transition-colors" onClick={() => selectPipeline(p)} data-testid={`a2a-pipeline-${p.pipeline_id}`}>
              <CardContent className="py-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-cyan-600/15 flex items-center justify-center"><GitBranch className="w-5 h-5 text-cyan-400" /></div>
                  <div>
                    <div className="text-sm font-medium text-zinc-100">{p.name}</div>
                    <div className="text-xs text-zinc-500">{p.steps?.length || 0} steps · {p.run_count || 0} runs</div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {statusBadge(p.status)}
                  <Button size="sm" variant="ghost" onClick={e => { e.stopPropagation(); toggleStatus(p); }} className="h-7 text-xs">{p.status === "active" ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}</Button>
                  <Button size="sm" variant="ghost" onClick={e => { e.stopPropagation(); deletePipeline(p.pipeline_id); }} className="h-7 text-zinc-500 hover:text-red-400"><Trash2 className="w-3 h-3" /></Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </>
      )}

      {view === "create" && (
        <Card className="bg-zinc-900 border-zinc-800" data-testid="a2a-create-form">
          <CardHeader><CardTitle className="text-sm text-zinc-100">Create A2A Pipeline</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <Input placeholder="Pipeline name" value={name} onChange={e => setName(e.target.value)} className="bg-zinc-800 border-zinc-700" data-testid="a2a-name" />
            <Input placeholder="Description" value={description} onChange={e => setDescription(e.target.value)} className="bg-zinc-800 border-zinc-700" />
            <div className="space-y-3">
              <div className="flex items-center justify-between"><span className="text-xs text-zinc-400 font-medium">Pipeline Steps</span><Button variant="ghost" size="sm" onClick={addStep}><Plus className="w-3 h-3 mr-1" /> Add Step</Button></div>
              {steps.map((step, i) => (
                <div key={i} className="p-3 bg-zinc-800/50 rounded-lg border border-zinc-700/50 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2"><span className="text-xs text-cyan-400 font-mono">Step {i + 1}</span></div>
                    {steps.length > 1 && <Button variant="ghost" size="sm" onClick={() => removeStep(i)} className="h-6 text-zinc-500 hover:text-red-400"><Trash2 className="w-3 h-3" /></Button>}
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <Input placeholder="Step name" value={step.name} onChange={e => updateStep(i, "name", e.target.value)} className="bg-zinc-800 border-zinc-700 h-8 text-sm" />
                    <Select value={step.agent_id} onValueChange={v => updateStep(i, "agent_id", v)}>
                      <SelectTrigger className="bg-zinc-800 border-zinc-700 h-8 text-sm"><SelectValue placeholder="Select agent" /></SelectTrigger>
                      <SelectContent>
                        {["chatgpt", "claude", "gemini", "deepseek", "mistral"].map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                        {agents.map(a => <SelectItem key={a.agent_id} value={a.agent_id}>{a.name}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <Textarea placeholder="Prompt template (use {trigger_payload}, {pipeline_context}, {step_000_output})" value={step.prompt_template} onChange={e => updateStep(i, "prompt_template", e.target.value)} rows={2} className="bg-zinc-800 border-zinc-700 text-sm" />
                  <div className="flex items-center gap-2">
                    <Switch checked={step.quality_gate.enabled} onCheckedChange={v => updateStep(i, "quality_gate", { ...step.quality_gate, enabled: v, method: "ai_validation", min_score: 0.7, max_retries: 2 })} className="scale-75" />
                    <span className="text-xs text-zinc-500">Quality gate</span>
                  </div>
                  {i < steps.length - 1 && <div className="flex justify-center py-1"><ArrowDown className="w-4 h-4 text-zinc-600" /></div>}
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <Button onClick={createPipeline} className="bg-cyan-600 hover:bg-cyan-700 flex-1" data-testid="a2a-save-btn"><GitBranch className="w-4 h-4 mr-2" /> Create Pipeline</Button>
              <Button variant="ghost" onClick={() => setView("list")}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {view === "detail" && selectedPipeline && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <Button variant="ghost" size="sm" onClick={() => { setView("list"); setSelectedPipeline(null); setSelectedRun(null); }}>← Back</Button>
            <div className="flex gap-2">
              <Button size="sm" variant="ghost" onClick={() => toggleStatus(selectedPipeline)} className="text-xs">{selectedPipeline.status === "active" ? "Pause" : "Activate"}</Button>
              <Button size="sm" variant="ghost" onClick={() => deletePipeline(selectedPipeline.pipeline_id)} className="text-xs text-red-400">Delete</Button>
            </div>
          </div>
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="py-4 space-y-3">
              <div className="flex items-center justify-between">
                <div><h3 className="text-base font-medium text-zinc-100">{selectedPipeline.name}</h3><p className="text-xs text-zinc-500">{selectedPipeline.description}</p></div>
                {statusBadge(selectedPipeline.status)}
              </div>
              <div className="flex items-center gap-1 flex-wrap">
                {(selectedPipeline.steps || []).map((s, i) => (
                  <div key={i} className="flex items-center gap-1">
                    <span className="px-2 py-1 bg-zinc-800 rounded text-xs text-zinc-200 border border-zinc-700/50">{s.name || s.agent_id}</span>
                    {s.quality_gate?.enabled && <span className="text-xs text-amber-400">✓QG</span>}
                    {i < (selectedPipeline.steps?.length || 0) - 1 && <ArrowRight className="w-3 h-3 text-zinc-600" />}
                  </div>
                ))}
              </div>
              <div className="flex gap-2 pt-2 border-t border-zinc-800">
                <Input placeholder="Trigger payload..." value={triggerPayload} onChange={e => setTriggerPayload(e.target.value)} className="bg-zinc-800 border-zinc-700 flex-1" data-testid="a2a-trigger-input" />
                <Button onClick={() => triggerPipeline(selectedPipeline.pipeline_id)} disabled={triggering} className="bg-emerald-600 hover:bg-emerald-700" data-testid="a2a-trigger-btn">
                  {triggering ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Play className="w-4 h-4 mr-1" /> Trigger</>}
                </Button>
              </div>
            </CardContent>
          </Card>

          <h3 className="text-sm font-medium text-zinc-300">Run History</h3>
          {runs.length === 0 ? <p className="text-xs text-zinc-500">No runs yet.</p> : runs.map(run => (
            <Card key={run.run_id} className={`bg-zinc-900/50 border-zinc-800 cursor-pointer hover:border-zinc-700 transition-colors ${selectedRun?.run_id === run.run_id ? "border-cyan-600/50" : ""}`} onClick={() => viewRun(run.run_id)}>
              <CardContent className="py-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {run.status === "completed" ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : run.status === "running" ? <Loader2 className="w-4 h-4 text-blue-400 animate-spin" /> : run.status === "failed" ? <XCircle className="w-4 h-4 text-red-400" /> : run.status === "paused" ? <Pause className="w-4 h-4 text-amber-400" /> : <Clock className="w-4 h-4 text-zinc-500" />}
                  <span className="text-sm text-zinc-300">{run.run_id.slice(0, 20)}</span>
                  {statusBadge(run.status)}
                </div>
                <div className="flex items-center gap-3 text-xs text-zinc-500">
                  <span>${run.total_cost_usd?.toFixed(4) || "0"}</span>
                  <span>{run.total_duration_ms ? `${(run.total_duration_ms / 1000).toFixed(1)}s` : "-"}</span>
                  <span>{new Date(run.started_at).toLocaleString()}</span>
                </div>
              </CardContent>
            </Card>
          ))}

          {selectedRun && (
            <Card className="bg-zinc-900 border-zinc-800" data-testid="a2a-run-detail">
              <CardHeader><CardTitle className="text-sm text-zinc-100">Run: {selectedRun.run_id}</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-4 gap-3 text-center">
                  {[
                    { label: "Status", value: selectedRun.status, icon: selectedRun.status === "completed" ? CheckCircle2 : XCircle },
                    { label: "Cost", value: `$${selectedRun.total_cost_usd?.toFixed(4) || "0"}`, icon: DollarSign },
                    { label: "Duration", value: selectedRun.total_duration_ms ? `${(selectedRun.total_duration_ms / 1000).toFixed(1)}s` : "-", icon: Clock },
                    { label: "Steps", value: runSteps.length, icon: GitBranch },
                  ].map(({ label, value, icon: Icon }) => (
                    <div key={label} className="p-2 bg-zinc-800/50 rounded-lg">
                      <Icon className="w-4 h-4 text-zinc-500 mx-auto mb-1" />
                      <div className="text-sm font-bold text-zinc-200">{value}</div>
                      <div className="text-xs text-zinc-500">{label}</div>
                    </div>
                  ))}
                </div>
                {selectedRun.error && <div className="p-2 bg-red-900/20 rounded border border-red-800/30 text-xs text-red-400">{selectedRun.error}</div>}
                {runSteps.map((step, i) => (
                  <div key={step.exec_id} className={`p-3 rounded-lg border ${step.status === "completed" ? "border-emerald-800/30 bg-emerald-900/5" : step.status === "failed" ? "border-red-800/30 bg-red-900/5" : "border-zinc-800"}`}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        {step.status === "completed" ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> : step.status === "failed" ? <XCircle className="w-3.5 h-3.5 text-red-400" /> : <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin" />}
                        <span className="text-sm text-zinc-200">{step.step_id}</span>
                        <span className="text-xs text-zinc-500">{step.agent_id}</span>
                        {step.attempt > 1 && <Badge variant="outline" className="text-xs border-amber-800 text-amber-400">attempt {step.attempt}</Badge>}
                      </div>
                      <div className="flex items-center gap-2 text-xs text-zinc-500">
                        {step.quality_score != null && <span className={step.quality_score >= 0.7 ? "text-emerald-400" : "text-amber-400"}>Q:{step.quality_score?.toFixed(2)}</span>}
                        <span>${step.cost_usd?.toFixed(4) || "0"}</span>
                        <span>{step.duration_ms}ms</span>
                      </div>
                    </div>
                    {step.output && <div className="text-xs text-zinc-400 mt-1 max-h-32 overflow-y-auto whitespace-pre-wrap bg-zinc-800/30 p-2 rounded">{step.output}</div>}
                    {step.error && <div className="text-xs text-red-400 mt-1">{step.error}</div>}
                    {step.quality_feedback && <div className="text-xs text-amber-400/70 mt-1">Feedback: {step.quality_feedback}</div>}
                    {i < runSteps.length - 1 && <div className="flex justify-center py-1"><ArrowDown className="w-3 h-3 text-zinc-700" /></div>}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

function TemplatesTab({ workspaceId }) {
  const [templates, setTemplates] = useState([]);
  const [installing, setInstalling] = useState(null);

  useEffect(() => {
    api.get(`/workspaces/${workspaceId}/a2a/templates`).then(r => setTemplates(r.data.templates || [])).catch(() => {});
  }, [workspaceId]);

  const install = async (tpl) => {
    setInstalling(tpl.template_id);
    try {
      await api.post(`/workspaces/${workspaceId}/a2a/pipelines`, { name: tpl.name, description: tpl.description, steps: tpl.steps, settings: tpl.settings || {}, triggers: tpl.triggers || [] });
      toast.success(`Installed "${tpl.name}"`);
    } catch (err) { toast.error("Install failed"); }
    setInstalling(null);
  };

  const catColors = { development: "border-emerald-800 text-emerald-400", content: "border-purple-800 text-purple-400", support: "border-blue-800 text-blue-400", analytics: "border-amber-800 text-amber-400", productivity: "border-cyan-800 text-cyan-400" };

  return (
    <div className="space-y-4" data-testid="a2a-templates">
      <p className="text-sm text-zinc-500">Pre-built autonomous workflow templates. Install with one click.</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {templates.map(tpl => (
          <Card key={tpl.template_id} className="bg-zinc-900 border-zinc-800 hover:border-zinc-700 transition-colors">
            <CardContent className="py-4 space-y-3">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-sm font-medium text-zinc-100">{tpl.name}</h3>
                  <Badge variant="outline" className={`text-xs mt-1 ${catColors[tpl.category] || "border-zinc-700"}`}>{tpl.category}</Badge>
                </div>
              </div>
              <p className="text-xs text-zinc-400">{tpl.description}</p>
              <div className="flex items-center gap-1 flex-wrap">
                {(tpl.steps || []).map((s, i) => (
                  <div key={i} className="flex items-center gap-1">
                    <span className="px-1.5 py-0.5 bg-zinc-800 rounded text-xs text-zinc-300 border border-zinc-700/50">{s.name || s.agent_id}</span>
                    {i < (tpl.steps?.length || 0) - 1 && <ArrowRight className="w-3 h-3 text-zinc-600" />}
                  </div>
                ))}
              </div>
              <Button size="sm" onClick={() => install(tpl)} disabled={installing === tpl.template_id} className="bg-cyan-600 hover:bg-cyan-700 w-full text-xs" data-testid={`a2a-install-${tpl.template_id}`}>
                {installing === tpl.template_id ? <Loader2 className="w-3 h-3 animate-spin" /> : <><Download className="w-3 h-3 mr-1" /> Install Pipeline</>}
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

  useEffect(() => {
    api.get(`/workspaces/${workspaceId}/a2a/analytics`).then(r => setData(r.data)).catch(() => {});
  }, [workspaceId]);

  if (!data) return <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-zinc-500" /></div>;

  return (
    <div className="space-y-4" data-testid="a2a-analytics">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Total Runs", value: data.total_runs, icon: GitBranch, color: "text-cyan-400" },
          { label: "Success Rate", value: `${data.success_rate}%`, icon: CheckCircle2, color: data.success_rate >= 80 ? "text-emerald-400" : "text-amber-400" },
          { label: "Total Cost", value: `$${data.total_cost_usd}`, icon: DollarSign, color: "text-emerald-400" },
          { label: "Avg Duration", value: data.avg_duration_ms ? `${(data.avg_duration_ms / 1000).toFixed(1)}s` : "-", icon: Clock, color: "text-zinc-300" },
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
      <div className="grid grid-cols-2 gap-4">
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="py-4">
            <div className="text-sm text-zinc-300 mb-2">Completed</div>
            <div className="text-3xl font-bold text-emerald-400">{data.completed}</div>
          </CardContent>
        </Card>
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="py-4">
            <div className="text-sm text-zinc-300 mb-2">Failed</div>
            <div className="text-3xl font-bold text-red-400">{data.failed}</div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
