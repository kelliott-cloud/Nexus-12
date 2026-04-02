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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Target, Play, Plus, Trash2, Loader2, CheckCircle2, XCircle,
  Clock, BarChart3, Award, ChevronRight, FlaskConical, Crosshair
} from "lucide-react";
import { FeatureHelp, FEATURE_HELP } from "@/components/FeatureHelp";

export default function BenchmarksPanel({ workspaceId }) {
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState("");
  const [suites, setSuites] = useState([]);
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("suites");
  const [selectedRun, setSelectedRun] = useState(null);

  // Create suite form
  const [showCreate, setShowCreate] = useState(false);
  const [suiteName, setSuiteName] = useState("");
  const [cases, setCases] = useState([{ question: "", expected_keywords: "", expected_topic: "", category: "general" }]);
  const [creatingOrRunning, setCreatingOrRunning] = useState(false);

  const fetchAgents = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/agents`);
      const list = res.data.agents || res.data || [];
      setAgents(list);
      if (list.length > 0 && !selectedAgent) setSelectedAgent(list[0].agent_id);
    } catch (err) { handleSilent(err, "BM:agents"); }
    setLoading(false);
  }, [workspaceId, selectedAgent]);

  const fetchSuites = useCallback(async () => {
    if (!selectedAgent) return;
    try {
      const res = await api.get(`/workspaces/${workspaceId}/agents/${selectedAgent}/benchmarks/suites`);
      setSuites(res.data.suites || []);
    } catch (err) { handleSilent(err, "BM:suites"); }
  }, [workspaceId, selectedAgent]);

  const fetchRuns = useCallback(async () => {
    if (!selectedAgent) return;
    try {
      const res = await api.get(`/workspaces/${workspaceId}/agents/${selectedAgent}/benchmarks/runs`);
      setRuns(res.data.runs || []);
    } catch (err) { handleSilent(err, "BM:runs"); }
    setLoading(false);
  }, [workspaceId, selectedAgent]);

  useEffect(() => { fetchAgents(); }, [fetchAgents]);
  useEffect(() => { if (selectedAgent) { fetchSuites(); fetchRuns(); } }, [selectedAgent, fetchSuites, fetchRuns]);

  const createSuite = async () => {
    if (!suiteName.trim()) return toast.error("Suite name required");
    const validCases = cases.filter(c => c.question.trim().length >= 5).map(c => ({
      question: c.question.trim(),
      expected_keywords: c.expected_keywords ? c.expected_keywords.split(",").map(k => k.trim()).filter(Boolean) : [],
      expected_topic: c.expected_topic,
      category: c.category || "general",
    }));
    if (validCases.length === 0) return toast.error("Add at least one test case (min 5 chars)");
    setCreatingOrRunning(true);
    try {
      await api.post(`/workspaces/${workspaceId}/agents/${selectedAgent}/benchmarks/suites`, {
        name: suiteName, cases: validCases,
      });
      toast.success("Benchmark suite created");
      setShowCreate(false); setSuiteName("");
      setCases([{ question: "", expected_keywords: "", expected_topic: "", category: "general" }]);
      fetchSuites();
    } catch (err) { toast.error("Failed to create suite"); handleSilent(err, "BM:create"); }
    setCreatingOrRunning(false);
  };

  const deleteSuite = async (suiteId) => {
    try {
      await api.delete(`/workspaces/${workspaceId}/agents/${selectedAgent}/benchmarks/suites/${suiteId}`);
      toast.success("Suite deleted");
      fetchSuites();
    } catch (err) { toast.error("Delete failed"); }
  };

  const runBenchmark = async (suiteId) => {
    setCreatingOrRunning(true);
    try {
      await api.post(`/workspaces/${workspaceId}/agents/${selectedAgent}/benchmarks/run`, { suite_id: suiteId });
      toast.success("Benchmark started");
      setTab("runs");
      fetchRuns();
    } catch (err) { toast.error("Failed to start benchmark"); handleSilent(err, "BM:run"); }
    setCreatingOrRunning(false);
  };

  const fetchRunDetail = async (runId) => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/agents/${selectedAgent}/benchmarks/runs/${runId}`);
      setSelectedRun(res.data);
    } catch (err) { handleSilent(err, "BM:runDetail"); }
  };

  const addCase = () => setCases([...cases, { question: "", expected_keywords: "", expected_topic: "", category: "general" }]);
  const removeCase = (i) => setCases(cases.filter((_, idx) => idx !== i));
  const updateCase = (i, field, val) => {
    const updated = [...cases];
    updated[i] = { ...updated[i], [field]: val };
    setCases(updated);
  };

  const scoreColor = (score) => {
    if (score >= 80) return "text-emerald-400";
    if (score >= 50) return "text-amber-400";
    return "text-red-400";
  };

  const scoreBg = (score) => {
    if (score >= 80) return "bg-emerald-500";
    if (score >= 50) return "bg-amber-500";
    return "bg-red-500";
  };

  if (loading && agents.length === 0) return <div className="flex-1 flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-zinc-500" /></div>;

  if (agents.length === 0) return (
    <div className="flex-1 flex items-center justify-center p-6" data-testid="benchmarks-panel">
      <p className="text-zinc-500">No agents in this workspace. Create an agent first to run benchmarks.</p>
    </div>
  );

  return (
    <div className="flex-1 overflow-y-auto p-6" data-testid="benchmarks-panel">
      <div className="max-w-5xl mx-auto space-y-6">
        <FeatureHelp featureId="benchmarks" {...FEATURE_HELP["benchmarks"]} />
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100">Agent Performance Benchmarks</h2>
            <p className="text-sm text-zinc-500 mt-1">Test agent accuracy, response quality, and knowledge utilization</p>
          </div>
          <div className="flex items-center gap-3">
            <Select value={selectedAgent} onValueChange={setSelectedAgent}>
              <SelectTrigger className="w-48 bg-zinc-800 border-zinc-700" data-testid="bm-agent-select">
                <SelectValue placeholder="Select agent" />
              </SelectTrigger>
              <SelectContent>
                {agents.map(a => <SelectItem key={a.agent_id} value={a.agent_id}>{a.name}</SelectItem>)}
              </SelectContent>
            </Select>
            <Button size="sm" onClick={() => setShowCreate(!showCreate)} className="bg-indigo-600 hover:bg-indigo-700" data-testid="bm-create-btn">
              <Plus className="w-4 h-4 mr-1" /> New Suite
            </Button>
          </div>
        </div>

        {showCreate && (
          <Card className="bg-zinc-900 border-zinc-800" data-testid="bm-create-form">
            <CardHeader><CardTitle className="text-sm text-zinc-100">Create Benchmark Suite</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <Input placeholder="Suite name" value={suiteName} onChange={e => setSuiteName(e.target.value)} className="bg-zinc-800 border-zinc-700" data-testid="bm-suite-name" />
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-zinc-400 font-medium">Test Cases</span>
                  <Button variant="ghost" size="sm" onClick={addCase} data-testid="bm-add-case"><Plus className="w-3 h-3 mr-1" /> Add Case</Button>
                </div>
                {cases.map((tc, i) => (
                  <div key={i} className="p-3 bg-zinc-800/50 rounded-lg border border-zinc-700/50 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-indigo-400 font-mono">Case #{i+1}</span>
                      {cases.length > 1 && <Button variant="ghost" size="sm" onClick={() => removeCase(i)} className="h-6 text-zinc-500 hover:text-red-400"><Trash2 className="w-3 h-3" /></Button>}
                    </div>
                    <Input placeholder="Test question (min 5 chars)" value={tc.question} onChange={e => updateCase(i, "question", e.target.value)} className="bg-zinc-800 border-zinc-700 h-8 text-sm" data-testid={`bm-case-${i}-question`} />
                    <div className="grid grid-cols-3 gap-2">
                      <Input placeholder="Expected keywords (comma separated)" value={tc.expected_keywords} onChange={e => updateCase(i, "expected_keywords", e.target.value)} className="bg-zinc-800 border-zinc-700 h-8 text-xs" />
                      <Input placeholder="Expected topic" value={tc.expected_topic} onChange={e => updateCase(i, "expected_topic", e.target.value)} className="bg-zinc-800 border-zinc-700 h-8 text-xs" />
                      <Select value={tc.category} onValueChange={v => updateCase(i, "category", v)}>
                        <SelectTrigger className="bg-zinc-800 border-zinc-700 h-8 text-xs"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {["general", "accuracy", "reasoning", "knowledge", "creativity"].map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                ))}
              </div>
              <Button onClick={createSuite} disabled={creatingOrRunning} className="bg-indigo-600 hover:bg-indigo-700 w-full" data-testid="bm-save-suite">
                {creatingOrRunning ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <FlaskConical className="w-4 h-4 mr-2" />}
                Create Suite ({cases.filter(c => c.question.trim().length >= 5).length} cases)
              </Button>
            </CardContent>
          </Card>
        )}

        <div className="flex gap-2 border-b border-zinc-800 pb-0">
          {["suites", "runs"].map(t => (
            <button key={t} onClick={() => { setTab(t); setSelectedRun(null); }} className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${tab === t ? "border-indigo-500 text-zinc-100" : "border-transparent text-zinc-500 hover:text-zinc-300"}`} data-testid={`bm-tab-${t}`}>
              {t === "suites" ? "Test Suites" : "Benchmark Runs"}
            </button>
          ))}
        </div>

        {tab === "suites" && (
          <div className="space-y-3">
            {suites.length === 0 ? (
              <p className="text-sm text-zinc-500 text-center py-8">No benchmark suites yet. Create one to test your agent.</p>
            ) : suites.map(suite => (
              <Card key={suite.suite_id} className="bg-zinc-900/50 border-zinc-800" data-testid={`bm-suite-${suite.suite_id}`}>
                <CardContent className="py-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-indigo-600/15 flex items-center justify-center">
                      <FlaskConical className="w-4 h-4 text-indigo-400" />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-zinc-200">{suite.name}</div>
                      <div className="text-xs text-zinc-500">{suite.case_count} test cases &middot; Created {new Date(suite.created_at).toLocaleDateString()}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button size="sm" onClick={() => runBenchmark(suite.suite_id)} disabled={creatingOrRunning} className="bg-emerald-600 hover:bg-emerald-700 text-xs h-7" data-testid={`bm-run-${suite.suite_id}`}>
                      <Play className="w-3 h-3 mr-1" /> Run
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => deleteSuite(suite.suite_id)} className="text-zinc-500 hover:text-red-400 h-7"><Trash2 className="w-3.5 h-3.5" /></Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {tab === "runs" && (
          <div className="space-y-4">
            {runs.length === 0 ? (
              <p className="text-sm text-zinc-500 text-center py-8">No benchmark runs yet. Run a test suite to see results.</p>
            ) : runs.map(run => (
              <Card key={run.run_id} className={`bg-zinc-900/50 border-zinc-800 cursor-pointer transition-colors ${selectedRun?.run_id === run.run_id ? "border-indigo-600/50" : "hover:border-zinc-700"}`} onClick={() => fetchRunDetail(run.run_id)} data-testid={`bm-run-card-${run.run_id}`}>
                <CardContent className="py-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      {run.status === "completed" ? <Target className="w-5 h-5 text-emerald-400" /> : run.status === "running" ? <Loader2 className="w-5 h-5 text-amber-400 animate-spin" /> : <XCircle className="w-5 h-5 text-red-400" />}
                      <div>
                        <div className="text-sm font-medium text-zinc-200">{run.suite_name}</div>
                        <div className="text-xs text-zinc-500">{new Date(run.started_at).toLocaleString()}</div>
                      </div>
                    </div>
                    {run.summary && (
                      <div className="flex items-center gap-4 text-right">
                        <div>
                          <div className={`text-xl font-bold ${scoreColor(run.summary.avg_score)}`}>{run.summary.avg_score}</div>
                          <div className="text-xs text-zinc-500">Avg Score</div>
                        </div>
                        <div>
                          <div className="text-lg font-semibold text-zinc-200">{run.summary.pass_rate}%</div>
                          <div className="text-xs text-zinc-500">Pass Rate</div>
                        </div>
                        <Badge variant="outline" className={`text-xs ${run.summary.pass_rate >= 80 ? "border-emerald-800 text-emerald-400" : run.summary.pass_rate >= 50 ? "border-amber-800 text-amber-400" : "border-red-800 text-red-400"}`}>
                          {run.summary.passed}/{run.summary.total_cases} passed
                        </Badge>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}

            {selectedRun && selectedRun.results && (
              <Card className="bg-zinc-900 border-zinc-800" data-testid="bm-run-detail">
                <CardHeader>
                  <CardTitle className="text-base text-zinc-100">Detailed Results: {selectedRun.suite_name}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {selectedRun.summary && (
                    <div className="grid grid-cols-4 gap-3 mb-4">
                      {[
                        { label: "Average Score", value: selectedRun.summary.avg_score, icon: Award },
                        { label: "Pass Rate", value: `${selectedRun.summary.pass_rate}%`, icon: Target },
                        { label: "Passed", value: selectedRun.summary.passed, icon: CheckCircle2 },
                        { label: "Failed", value: selectedRun.summary.failed, icon: XCircle },
                      ].map(({ label, value, icon: Icon }) => (
                        <div key={label} className="p-3 bg-zinc-800/50 rounded-lg border border-zinc-700/30 text-center">
                          <Icon className="w-4 h-4 text-zinc-500 mx-auto mb-1" />
                          <div className="text-lg font-bold text-zinc-100">{value}</div>
                          <div className="text-xs text-zinc-500">{label}</div>
                        </div>
                      ))}
                    </div>
                  )}

                  {selectedRun.results.map((result, i) => (
                    <div key={i} className={`p-3 rounded-lg border ${result.passed ? "bg-emerald-900/10 border-emerald-800/30" : "bg-red-900/10 border-red-800/30"}`}>
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          {result.passed ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-red-400" />}
                          <span className="text-sm text-zinc-200">{result.question}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="text-xs border-zinc-700">{result.category}</Badge>
                          <span className={`text-sm font-bold ${scoreColor(result.overall_score)}`}>{result.overall_score}</span>
                        </div>
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        {[
                          { label: "Retrieval", score: result.retrieval_score },
                          { label: "Keywords", score: result.keyword_score, detail: `${result.keywords_found || 0}/${result.keywords_total || 0}` },
                          { label: "Topic", score: result.topic_score },
                        ].map(({ label, score, detail }) => (
                          <div key={label} className="text-xs">
                            <div className="flex justify-between text-zinc-500 mb-0.5">
                              <span>{label}</span>
                              <span className={scoreColor(score)}>{score}{detail ? ` (${detail})` : ""}</span>
                            </div>
                            <Progress value={score} className="h-1" />
                          </div>
                        ))}
                      </div>
                      {result.error && <div className="text-xs text-red-400 mt-1">{result.error}</div>}
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
