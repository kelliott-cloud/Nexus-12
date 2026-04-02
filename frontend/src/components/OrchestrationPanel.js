import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { handleSilent } from "@/lib/errorHandler";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Network, Play, Plus, Trash2, Loader2, ChevronDown, ChevronRight,
  CheckCircle2, XCircle, Clock, Zap, ArrowRight, GitBranch
} from "lucide-react";
import { FeatureHelp, FEATURE_HELP } from "@/components/FeatureHelp";

export default function OrchestrationPanel({ workspaceId }) {
  const [agents, setAgents] = useState([]);
  const [orchestrations, setOrchestrations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState("list");
  const [selectedOrch, setSelectedOrch] = useState(null);
  const [runs, setRuns] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);

  // Create form
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [mode, setMode] = useState("sequential");
  const [steps, setSteps] = useState([{ agent_id: "", prompt_template: "{input}", condition: "" }]);

  // Run form
  const [runInput, setRunInput] = useState("");
  const [running, setRunning] = useState(false);

  const fetchAgents = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/agents`);
      setAgents(res.data.agents || res.data || []);
    } catch (err) { handleSilent(err, "Orch:agents"); }
  }, [workspaceId]);

  const fetchOrchestrations = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/orchestrations`);
      setOrchestrations(res.data.orchestrations || []);
    } catch (err) { handleSilent(err, "Orch:list"); }
    setLoading(false);
  }, [workspaceId]);

  useEffect(() => { fetchAgents(); fetchOrchestrations(); }, [fetchAgents, fetchOrchestrations]);

  const createOrchestration = async () => {
    if (!name.trim() || steps.length === 0) return toast.error("Name and at least one step required");
    const validSteps = steps.filter(s => s.agent_id);
    if (validSteps.length === 0) return toast.error("Select an agent for each step");
    try {
      await api.post(`/workspaces/${workspaceId}/orchestrations`, {
        name, description, execution_mode: mode, steps: validSteps,
      });
      toast.success("Orchestration created");
      setView("list"); setName(""); setDescription(""); setSteps([{ agent_id: "", prompt_template: "{input}", condition: "" }]);
      fetchOrchestrations();
    } catch (err) { toast.error("Failed to create"); handleSilent(err, "Orch:create"); }
  };

  const deleteOrchestration = async (orchId) => {
    try {
      await api.delete(`/workspaces/${workspaceId}/orchestrations/${orchId}`);
      toast.success("Deleted");
      fetchOrchestrations();
      if (selectedOrch?.orchestration_id === orchId) setSelectedOrch(null);
    } catch (err) { toast.error("Delete failed"); }
  };

  const runOrchestration = async () => {
    if (!runInput.trim() || !selectedOrch) return;
    setRunning(true);
    try {
      const res = await api.post(`/workspaces/${workspaceId}/orchestrations/${selectedOrch.orchestration_id}/run`, {
        input_text: runInput,
      });
      toast.success("Orchestration started");
      setRunInput("");
      fetchRuns(selectedOrch.orchestration_id);
    } catch (err) { toast.error("Run failed"); handleSilent(err, "Orch:run"); }
    setRunning(false);
  };

  const fetchRuns = async (orchId) => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/orchestrations/${orchId}/runs`);
      setRuns(res.data.runs || []);
    } catch (err) { handleSilent(err, "Orch:runs"); }
  };

  const fetchRunDetail = async (runId) => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/orchestration-runs/${runId}`);
      setSelectedRun(res.data);
    } catch (err) { handleSilent(err, "Orch:runDetail"); }
  };

  const selectOrchestration = (orch) => {
    setSelectedOrch(orch);
    setView("detail");
    fetchRuns(orch.orchestration_id);
  };

  const addStep = () => setSteps([...steps, { agent_id: "", prompt_template: "{input}", condition: "" }]);
  const removeStep = (i) => setSteps(steps.filter((_, idx) => idx !== i));
  const updateStep = (i, field, val) => {
    const updated = [...steps];
    updated[i] = { ...updated[i], [field]: val };
    setSteps(updated);
  };

  const getAgentName = (id) => agents.find(a => a.agent_id === id)?.name || id;

  const statusIcon = (status) => {
    if (status === "completed") return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
    if (status === "failed") return <XCircle className="w-4 h-4 text-red-400" />;
    if (status === "running") return <Loader2 className="w-4 h-4 text-amber-400 animate-spin" />;
    return <Clock className="w-4 h-4 text-zinc-500" />;
  };

  if (loading) return <div className="flex-1 flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-zinc-500" /></div>;

  return (
    <div className="flex-1 overflow-y-auto p-6" data-testid="orchestration-panel">
      <div className="max-w-5xl mx-auto space-y-6">
        <FeatureHelp featureId="orchestration" {...FEATURE_HELP["orchestration"]} />
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100">Multi-Agent Orchestration</h2>
            <p className="text-sm text-zinc-500 mt-1">Chain agents together in sequential or parallel workflows</p>
          </div>
          <div className="flex gap-2">
            {view !== "list" && (
              <Button variant="ghost" size="sm" onClick={() => { setView("list"); setSelectedOrch(null); setSelectedRun(null); }} data-testid="orch-back-btn">
                Back
              </Button>
            )}
            <Button size="sm" onClick={() => setView("create")} className="bg-indigo-600 hover:bg-indigo-700" data-testid="orch-create-btn">
              <Plus className="w-4 h-4 mr-1" /> New Orchestration
            </Button>
          </div>
        </div>

        {view === "create" && (
          <Card className="bg-zinc-900 border-zinc-800" data-testid="orch-create-form">
            <CardHeader><CardTitle className="text-base text-zinc-100">Create Orchestration</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <Input placeholder="Orchestration name" value={name} onChange={e => setName(e.target.value)} className="bg-zinc-800 border-zinc-700" data-testid="orch-name-input" />
              <Input placeholder="Description (optional)" value={description} onChange={e => setDescription(e.target.value)} className="bg-zinc-800 border-zinc-700" data-testid="orch-desc-input" />
              <Select value={mode} onValueChange={setMode}>
                <SelectTrigger className="bg-zinc-800 border-zinc-700" data-testid="orch-mode-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="sequential">Sequential (chain)</SelectItem>
                  <SelectItem value="parallel">Parallel (fan-out)</SelectItem>
                </SelectContent>
              </Select>

              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-zinc-400 font-medium">Steps</span>
                  <Button variant="ghost" size="sm" onClick={addStep} data-testid="orch-add-step-btn"><Plus className="w-3 h-3 mr-1" /> Add Step</Button>
                </div>
                {steps.map((step, i) => (
                  <div key={i} className="flex items-start gap-2 p-3 bg-zinc-800/50 rounded-lg border border-zinc-700/50">
                    <div className="flex items-center justify-center w-6 h-6 rounded-full bg-indigo-600/20 text-indigo-400 text-xs font-bold mt-1">{i + 1}</div>
                    <div className="flex-1 space-y-2">
                      <Select value={step.agent_id} onValueChange={v => updateStep(i, "agent_id", v)}>
                        <SelectTrigger className="bg-zinc-800 border-zinc-700 h-8 text-sm" data-testid={`orch-step-${i}-agent`}>
                          <SelectValue placeholder="Select agent" />
                        </SelectTrigger>
                        <SelectContent>
                          {agents.map(a => <SelectItem key={a.agent_id} value={a.agent_id}>{a.name}</SelectItem>)}
                        </SelectContent>
                      </Select>
                      <Input placeholder="Prompt template (use {input})" value={step.prompt_template} onChange={e => updateStep(i, "prompt_template", e.target.value)} className="bg-zinc-800 border-zinc-700 h-8 text-sm" data-testid={`orch-step-${i}-prompt`} />
                      {mode === "sequential" && (
                        <Input placeholder="Condition (optional, e.g. contains:keyword)" value={step.condition} onChange={e => updateStep(i, "condition", e.target.value)} className="bg-zinc-800 border-zinc-700 h-8 text-xs" />
                      )}
                    </div>
                    {steps.length > 1 && <Button variant="ghost" size="sm" onClick={() => removeStep(i)} className="text-red-400 hover:text-red-300 mt-1"><Trash2 className="w-3 h-3" /></Button>}
                  </div>
                ))}
              </div>

              <Button onClick={createOrchestration} className="bg-indigo-600 hover:bg-indigo-700 w-full" data-testid="orch-save-btn">
                <Network className="w-4 h-4 mr-2" /> Create Orchestration
              </Button>
            </CardContent>
          </Card>
        )}

        {view === "list" && (
          <div className="space-y-3">
            {orchestrations.length === 0 ? (
              <Card className="bg-zinc-900 border-zinc-800"><CardContent className="py-12 text-center text-zinc-500">No orchestrations yet. Create one to chain agents together.</CardContent></Card>
            ) : orchestrations.map(orch => (
              <Card key={orch.orchestration_id} className="bg-zinc-900 border-zinc-800 hover:border-zinc-700 transition-colors cursor-pointer" onClick={() => selectOrchestration(orch)} data-testid={`orch-card-${orch.orchestration_id}`}>
                <CardContent className="py-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-indigo-600/15 flex items-center justify-center">
                      <Network className="w-5 h-5 text-indigo-400" />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-zinc-100">{orch.name}</div>
                      <div className="text-xs text-zinc-500 mt-0.5">{orch.step_count} steps &middot; {orch.execution_mode} &middot; {orch.run_count || 0} runs</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-xs border-zinc-700">{orch.execution_mode}</Badge>
                    <Button variant="ghost" size="sm" onClick={e => { e.stopPropagation(); deleteOrchestration(orch.orchestration_id); }} className="text-zinc-500 hover:text-red-400" data-testid={`orch-delete-${orch.orchestration_id}`}>
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {view === "detail" && selectedOrch && (
          <div className="space-y-4">
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-base text-zinc-100">{selectedOrch.name}</CardTitle>
                    <p className="text-xs text-zinc-500 mt-1">{selectedOrch.description || "No description"}</p>
                  </div>
                  <Badge variant="outline" className="border-zinc-700">{selectedOrch.execution_mode}</Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="text-xs text-zinc-400 font-medium mb-2">Agent Pipeline</div>
                <div className="flex items-center gap-2 flex-wrap">
                  {(selectedOrch.steps || []).map((step, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <div className="px-3 py-1.5 bg-zinc-800 rounded-lg border border-zinc-700/50 text-sm text-zinc-200">
                        <span className="text-indigo-400 font-mono text-xs mr-1.5">#{i+1}</span>
                        {getAgentName(step.agent_id)}
                      </div>
                      {i < (selectedOrch.steps?.length || 0) - 1 && <ArrowRight className="w-4 h-4 text-zinc-600" />}
                    </div>
                  ))}
                </div>

                <div className="pt-4 border-t border-zinc-800 flex gap-2">
                  <Input placeholder="Enter input text to process through the chain..." value={runInput} onChange={e => setRunInput(e.target.value)} className="bg-zinc-800 border-zinc-700 flex-1" data-testid="orch-run-input" />
                  <Button onClick={runOrchestration} disabled={running || !runInput.trim()} className="bg-emerald-600 hover:bg-emerald-700" data-testid="orch-run-btn">
                    {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Play className="w-4 h-4 mr-1" /> Run</>}
                  </Button>
                </div>
              </CardContent>
            </Card>

            <div className="space-y-2">
              <h3 className="text-sm font-medium text-zinc-300">Run History</h3>
              {runs.length === 0 ? (
                <p className="text-xs text-zinc-500">No runs yet.</p>
              ) : runs.map(run => (
                <Card key={run.run_id} className="bg-zinc-900/50 border-zinc-800 cursor-pointer hover:border-zinc-700 transition-colors" onClick={() => fetchRunDetail(run.run_id)} data-testid={`orch-run-${run.run_id}`}>
                  <CardContent className="py-3 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {statusIcon(run.status)}
                      <span className="text-sm text-zinc-300">{run.run_id.slice(0, 15)}...</span>
                      <Badge variant="outline" className={`text-xs ${run.status === "completed" ? "border-emerald-800 text-emerald-400" : run.status === "failed" ? "border-red-800 text-red-400" : "border-amber-800 text-amber-400"}`}>{run.status}</Badge>
                    </div>
                    <span className="text-xs text-zinc-500">{new Date(run.started_at).toLocaleString()}</span>
                  </CardContent>
                </Card>
              ))}
            </div>

            {selectedRun && (
              <Card className="bg-zinc-900 border-zinc-800" data-testid="orch-run-detail">
                <CardHeader>
                  <CardTitle className="text-base text-zinc-100">Run Detail: {selectedRun.run_id}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="text-xs text-zinc-400">Input: <span className="text-zinc-300">{selectedRun.input_text?.slice(0, 200)}</span></div>
                  {selectedRun.final_output && (
                    <div className="p-3 bg-zinc-800/50 rounded-lg border border-zinc-700/50">
                      <div className="text-xs text-zinc-400 mb-1">Final Output</div>
                      <div className="text-sm text-zinc-200 whitespace-pre-wrap">{selectedRun.final_output}</div>
                    </div>
                  )}
                  {(selectedRun.step_results || []).map((sr, i) => (
                    <div key={i} className="flex items-start gap-2 p-2 bg-zinc-800/30 rounded border border-zinc-700/30">
                      {statusIcon(sr.status)}
                      <div className="flex-1">
                        <div className="text-xs font-medium text-zinc-300">{getAgentName(sr.agent_id)} <span className="text-zinc-500">({sr.step_id})</span></div>
                        {sr.output && <div className="text-xs text-zinc-400 mt-1 line-clamp-3">{sr.output}</div>}
                        {sr.error && <div className="text-xs text-red-400 mt-1">{sr.error}</div>}
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
