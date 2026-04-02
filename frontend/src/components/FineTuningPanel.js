import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { handleSilent } from "@/lib/errorHandler";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import {
  Sparkles, Database, Play, Trash2, Loader2, Download, CheckCircle2,
  XCircle, Clock, Zap, FileJson, BarChart3, Wand2, ArrowRight
} from "lucide-react";
import { FeatureHelp, FEATURE_HELP } from "@/components/FeatureHelp";

export default function FineTuningPanel({ workspaceId }) {
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState("");
  const [datasets, setDatasets] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("datasets");

  // Create dataset form
  const [dsName, setDsName] = useState("");
  const [includeKnowledge, setIncludeKnowledge] = useState(true);
  const [includeConversations, setIncludeConversations] = useState(true);
  const [minQuality, setMinQuality] = useState("0.5");
  const [maxExamples, setMaxExamples] = useState("500");
  const [creating, setCreating] = useState(false);

  // Job detail
  const [selectedJob, setSelectedJob] = useState(null);
  const [applying, setApplying] = useState(false);

  const fetchAgents = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/agents`);
      const list = res.data.agents || res.data || [];
      setAgents(list);
      if (list.length > 0 && !selectedAgent) setSelectedAgent(list[0].agent_id);
    } catch (err) { handleSilent(err, "FT:agents"); }
    setLoading(false);
  }, [workspaceId, selectedAgent]);

  const fetchDatasets = useCallback(async () => {
    if (!selectedAgent) return;
    try {
      const res = await api.get(`/workspaces/${workspaceId}/agents/${selectedAgent}/finetune/datasets`);
      setDatasets(res.data.datasets || []);
    } catch (err) { handleSilent(err, "FT:datasets"); }
  }, [workspaceId, selectedAgent]);

  const fetchJobs = useCallback(async () => {
    if (!selectedAgent) return;
    try {
      const res = await api.get(`/workspaces/${workspaceId}/agents/${selectedAgent}/finetune/jobs`);
      setJobs(res.data.jobs || []);
    } catch (err) { handleSilent(err, "FT:jobs"); }
    setLoading(false);
  }, [workspaceId, selectedAgent]);

  useEffect(() => { fetchAgents(); }, [fetchAgents]);
  useEffect(() => { if (selectedAgent) { fetchDatasets(); fetchJobs(); } }, [selectedAgent, fetchDatasets, fetchJobs]);

  const createDataset = async () => {
    if (!dsName.trim()) return toast.error("Dataset name required");
    setCreating(true);
    try {
      const res = await api.post(`/workspaces/${workspaceId}/agents/${selectedAgent}/finetune/datasets`, {
        name: dsName, include_knowledge: includeKnowledge, include_conversations: includeConversations,
        min_quality_score: parseFloat(minQuality), max_examples: parseInt(maxExamples),
      });
      toast.success(`Dataset created with ${res.data.example_count} examples`);
      setDsName("");
      fetchDatasets();
    } catch (err) { toast.error("Failed to create dataset"); handleSilent(err, "FT:createDs"); }
    setCreating(false);
  };

  const deleteDataset = async (dsId) => {
    try {
      await api.delete(`/workspaces/${workspaceId}/agents/${selectedAgent}/finetune/datasets/${dsId}`);
      toast.success("Dataset deleted");
      fetchDatasets();
    } catch (err) { toast.error("Delete failed"); }
  };

  const exportDataset = async (dsId) => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/agents/${selectedAgent}/finetune/datasets/${dsId}/export`, { responseType: "blob" });
      const url = URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a"); a.href = url; a.download = `${dsId}.jsonl`; a.click();
      URL.revokeObjectURL(url);
      toast.success("Dataset exported");
    } catch (err) { toast.error("Export failed"); }
  };

  const startJob = async (dsId) => {
    try {
      await api.post(`/workspaces/${workspaceId}/agents/${selectedAgent}/finetune/jobs`, {
        dataset_id: dsId, base_model: "claude-sonnet-4-5-20250929", provider: "anthropic",
      });
      toast.success("Fine-tuning job started with Claude");
      setTab("jobs");
      fetchJobs();
    } catch (err) { toast.error("Failed to start job"); handleSilent(err, "FT:startJob"); }
  };

  const fetchJobDetail = async (jobId) => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/agents/${selectedAgent}/finetune/jobs/${jobId}`);
      setSelectedJob(res.data);
    } catch (err) { handleSilent(err, "FT:jobDetail"); }
  };

  const applyJob = async (jobId) => {
    setApplying(true);
    try {
      await api.post(`/workspaces/${workspaceId}/agents/${selectedAgent}/finetune/jobs/${jobId}/apply`);
      toast.success("Optimized prompt applied to agent");
      setSelectedJob(null);
      fetchJobs();
    } catch (err) { toast.error(err?.response?.data?.detail || "Apply failed"); handleSilent(err, "FT:apply"); }
    setApplying(false);
  };

  const statusBadge = (status) => {
    const colors = {
      running: "border-amber-800 text-amber-400",
      evaluating_dataset: "border-blue-800 text-blue-400",
      generating_prompt: "border-purple-800 text-purple-400",
      completed: "border-emerald-800 text-emerald-400",
      failed: "border-red-800 text-red-400",
    };
    return <Badge variant="outline" className={`text-xs ${colors[status] || "border-zinc-700"}`}>{status}</Badge>;
  };

  const agentName = agents.find(a => a.agent_id === selectedAgent)?.name || "";

  if (loading && agents.length === 0) return <div className="flex-1 flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-zinc-500" /></div>;

  if (agents.length === 0) return (
    <div className="flex-1 flex items-center justify-center p-6" data-testid="finetune-panel">
      <p className="text-zinc-500">No agents in this workspace. Create an agent first to use fine-tuning.</p>
    </div>
  );

  return (
    <div className="flex-1 overflow-y-auto p-6" data-testid="finetune-panel">
      <div className="max-w-5xl mx-auto space-y-6">
        <FeatureHelp featureId="fine-tuning" {...FEATURE_HELP["fine-tuning"]} />
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100">Fine-Tuning Pipeline</h2>
            <p className="text-sm text-zinc-500 mt-1">Build training datasets and optimize agents with Claude AI</p>
          </div>
          <Select value={selectedAgent} onValueChange={setSelectedAgent}>
            <SelectTrigger className="w-56 bg-zinc-800 border-zinc-700" data-testid="ft-agent-select">
              <SelectValue placeholder="Select agent" />
            </SelectTrigger>
            <SelectContent>
              {agents.map(a => <SelectItem key={a.agent_id} value={a.agent_id}>{a.name}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>

        <div className="flex gap-2 border-b border-zinc-800 pb-0">
          {["datasets", "jobs"].map(t => (
            <button key={t} onClick={() => setTab(t)} className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${tab === t ? "border-indigo-500 text-zinc-100" : "border-transparent text-zinc-500 hover:text-zinc-300"}`} data-testid={`ft-tab-${t}`}>
              {t === "datasets" ? "Datasets" : "Training Jobs"}
            </button>
          ))}
        </div>

        {tab === "datasets" && (
          <div className="space-y-4">
            <Card className="bg-zinc-900 border-zinc-800" data-testid="ft-create-dataset">
              <CardHeader><CardTitle className="text-sm text-zinc-100">Create Training Dataset</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <Input placeholder="Dataset name" value={dsName} onChange={e => setDsName(e.target.value)} className="bg-zinc-800 border-zinc-700" data-testid="ft-ds-name" />
                <div className="grid grid-cols-2 gap-4">
                  <div className="flex items-center gap-2">
                    <Switch checked={includeKnowledge} onCheckedChange={setIncludeKnowledge} data-testid="ft-include-knowledge" />
                    <span className="text-sm text-zinc-300">Include knowledge chunks</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Switch checked={includeConversations} onCheckedChange={setIncludeConversations} data-testid="ft-include-conv" />
                    <span className="text-sm text-zinc-300">Include conversations</span>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-zinc-500 mb-1 block">Min quality score</label>
                    <Input type="number" step="0.1" min="0" max="1" value={minQuality} onChange={e => setMinQuality(e.target.value)} className="bg-zinc-800 border-zinc-700 h-8" />
                  </div>
                  <div>
                    <label className="text-xs text-zinc-500 mb-1 block">Max examples</label>
                    <Input type="number" min="10" max="2000" value={maxExamples} onChange={e => setMaxExamples(e.target.value)} className="bg-zinc-800 border-zinc-700 h-8" />
                  </div>
                </div>
                <Button onClick={createDataset} disabled={creating || !dsName.trim()} className="bg-indigo-600 hover:bg-indigo-700 w-full" data-testid="ft-create-ds-btn">
                  {creating ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Database className="w-4 h-4 mr-2" />}
                  Build Dataset from {agentName || "Agent"}'s Knowledge
                </Button>
              </CardContent>
            </Card>

            {datasets.length === 0 ? (
              <p className="text-sm text-zinc-500 text-center py-8">No datasets yet. Create one from your agent's knowledge base.</p>
            ) : datasets.map(ds => (
              <Card key={ds.dataset_id} className="bg-zinc-900/50 border-zinc-800" data-testid={`ft-dataset-${ds.dataset_id}`}>
                <CardContent className="py-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-blue-600/15 flex items-center justify-center">
                      <FileJson className="w-4 h-4 text-blue-400" />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-zinc-200">{ds.name}</div>
                      <div className="text-xs text-zinc-500">{ds.example_count} examples &middot; {new Date(ds.created_at).toLocaleDateString()}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button variant="ghost" size="sm" onClick={() => exportDataset(ds.dataset_id)} className="text-zinc-400" data-testid={`ft-export-${ds.dataset_id}`}><Download className="w-3.5 h-3.5" /></Button>
                    <Button size="sm" onClick={() => startJob(ds.dataset_id)} className="bg-emerald-600 hover:bg-emerald-700 text-xs h-7" data-testid={`ft-train-${ds.dataset_id}`}>
                      <Sparkles className="w-3 h-3 mr-1" /> Train with Claude
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => deleteDataset(ds.dataset_id)} className="text-zinc-500 hover:text-red-400"><Trash2 className="w-3.5 h-3.5" /></Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {tab === "jobs" && (
          <div className="space-y-4">
            {jobs.length === 0 ? (
              <p className="text-sm text-zinc-500 text-center py-8">No training jobs yet. Create a dataset first, then start training.</p>
            ) : jobs.map(job => (
              <Card key={job.job_id} className="bg-zinc-900/50 border-zinc-800 cursor-pointer hover:border-zinc-700 transition-colors" onClick={() => fetchJobDetail(job.job_id)} data-testid={`ft-job-${job.job_id}`}>
                <CardContent className="py-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-lg bg-purple-600/15 flex items-center justify-center">
                        <Wand2 className="w-4 h-4 text-purple-400" />
                      </div>
                      <div>
                        <div className="text-sm font-medium text-zinc-200">{job.dataset_name || job.job_id}</div>
                        <div className="text-xs text-zinc-500">{job.base_model} &middot; {job.example_count} examples</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {statusBadge(job.status)}
                      {job.status === "completed" && (
                        <Button size="sm" onClick={e => { e.stopPropagation(); applyJob(job.job_id); }} disabled={applying} className="bg-emerald-600 hover:bg-emerald-700 text-xs h-7" data-testid={`ft-apply-${job.job_id}`}>
                          {applying ? <Loader2 className="w-3 h-3 animate-spin" /> : <><Zap className="w-3 h-3 mr-1" /> Apply</>}
                        </Button>
                      )}
                    </div>
                  </div>
                  {(job.status === "running" || job.status === "evaluating_dataset" || job.status === "generating_prompt") && (
                    <Progress value={job.progress || 0} className="h-1.5" />
                  )}
                </CardContent>
              </Card>
            ))}

            {selectedJob && (
              <Card className="bg-zinc-900 border-zinc-800" data-testid="ft-job-detail">
                <CardHeader>
                  <CardTitle className="text-base text-zinc-100">Job Details: {selectedJob.job_id}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {selectedJob.evaluation_results && (
                    <div className="space-y-3">
                      <div className="text-xs text-zinc-400 font-medium">Evaluation Results</div>
                      <div className="grid grid-cols-4 gap-3">
                        {["overall_quality", "consistency_score", "coverage_score", "tone_alignment"].map(key => (
                          <div key={key} className="p-3 bg-zinc-800/50 rounded-lg border border-zinc-700/30 text-center">
                            <div className="text-lg font-bold text-zinc-100">{selectedJob.evaluation_results[key] || 0}</div>
                            <div className="text-xs text-zinc-500 mt-0.5">{key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}</div>
                          </div>
                        ))}
                      </div>
                      {selectedJob.evaluation_results.strengths && (
                        <div>
                          <div className="text-xs text-emerald-400 font-medium mb-1">Strengths</div>
                          {selectedJob.evaluation_results.strengths.map((s, i) => <div key={i} className="text-xs text-zinc-400 ml-2">+ {s}</div>)}
                        </div>
                      )}
                      {selectedJob.evaluation_results.weaknesses && (
                        <div>
                          <div className="text-xs text-amber-400 font-medium mb-1">Areas for Improvement</div>
                          {selectedJob.evaluation_results.weaknesses.map((w, i) => <div key={i} className="text-xs text-zinc-400 ml-2">- {w}</div>)}
                        </div>
                      )}
                    </div>
                  )}
                  {selectedJob.optimized_prompt && (
                    <div className="space-y-2">
                      <div className="text-xs text-zinc-400 font-medium">Optimized System Prompt</div>
                      <div className="p-3 bg-zinc-800/50 rounded-lg border border-zinc-700/30 text-sm text-zinc-300 whitespace-pre-wrap max-h-60 overflow-y-auto">
                        {selectedJob.optimized_prompt}
                      </div>
                    </div>
                  )}
                  {selectedJob.error && (
                    <div className="p-3 bg-red-900/20 rounded-lg border border-red-800/30 text-sm text-red-400">{selectedJob.error}</div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
