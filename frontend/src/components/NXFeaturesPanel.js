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
  Route, GitBranch, DollarSign, Plug, ActivitySquare, Loader2, Play, Plus,
  ArrowRight, Zap, Eye, RotateCcw, GitFork, Download, RefreshCw,
  BarChart3, Shield, Search, Trash2, CheckCircle2, XCircle
} from "lucide-react";
import { FeatureHelp, FEATURE_HELP } from "@/components/FeatureHelp";

const TABS = [
  { key: "routing", label: "Model Routing", icon: Route },
  { key: "workspaces", label: "Workspaces", icon: GitBranch },
  { key: "costs", label: "Cost Controls", icon: DollarSign },
  { key: "mcp", label: "Integrations", icon: Plug },
  { key: "traces", label: "Execution Chains", icon: ActivitySquare },
];

export default function NXFeaturesPanel({ workspaceId }) {
  const [tab, setTab] = useState("routing");

  return (
    <div className="flex-1 overflow-y-auto" data-testid="nx-features-panel">
      <div className="border-b border-zinc-800 px-6 pt-4">
        <h2 className="text-lg font-semibold text-zinc-100 mb-3">Nexus Platform</h2>
        <div className="flex gap-1 overflow-x-auto pb-0">
          {TABS.map(t => {
            const Icon = t.icon;
            return (
              <button key={t.key} onClick={() => setTab(t.key)}
                className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors whitespace-nowrap ${tab === t.key ? "border-cyan-500 text-zinc-100" : "border-transparent text-zinc-500 hover:text-zinc-300"}`}
                data-testid={`nx-tab-${t.key}`}>
                <Icon className="w-3.5 h-3.5" /> {t.label}
              </button>
            );
          })}
        </div>
      </div>
      <div className="p-6 max-w-6xl mx-auto">
        <FeatureHelp featureId="nx-platform" {...FEATURE_HELP["nx-platform"]} />
        {tab === "routing" && <RoutingTab workspaceId={workspaceId} />}
        {tab === "workspaces" && <WorkspacesTab workspaceId={workspaceId} />}
        {tab === "costs" && <CostControlsTab workspaceId={workspaceId} />}
        {tab === "mcp" && <MCPTab workspaceId={workspaceId} />}
        {tab === "traces" && <ExecutionTracesTab workspaceId={workspaceId} />}
      </div>
    </div>
  );
}

// ============ NX-001: Model Routing ============
function RoutingTab({ workspaceId }) {
  const [routing, setRouting] = useState([]);
  const [rules, setRules] = useState([]);
  const [comparePrompt, setComparePrompt] = useState("");
  const [compareModels, setCompareModels] = useState(["gpt-4o", "claude-sonnet-4-5-20250929"]);
  const [compareResults, setCompareResults] = useState(null);
  const [comparing, setComparing] = useState(false);
  const [showRuleForm, setShowRuleForm] = useState(false);
  const [ruleName, setRuleName] = useState("");
  const [ruleModel, setRuleModel] = useState("");

  useEffect(() => {
    api.get(`/workspaces/${workspaceId}/routing/active`).then(r => setRouting(r.data.routing || [])).catch(() => {});
    api.get(`/workspaces/${workspaceId}/routing/rules`).then(r => setRules(r.data.rules || [])).catch(() => {});
  }, [workspaceId]);

  const runComparison = async () => {
    if (!comparePrompt.trim()) return;
    setComparing(true);
    try {
      const res = await api.post(`/workspaces/${workspaceId}/routing/compare`, {
        prompt: comparePrompt, models: compareModels, system_prompt: "",
      });
      setCompareResults(res.data);
    } catch (err) { toast.error("Comparison failed"); }
    setComparing(false);
  };

  const createRule = async () => {
    if (!ruleName || !ruleModel) return;
    try {
      await api.post(`/workspaces/${workspaceId}/routing/rules`, { name: ruleName, model: ruleModel, priority: 0 });
      toast.success("Rule created");
      setShowRuleForm(false); setRuleName(""); setRuleModel("");
      api.get(`/workspaces/${workspaceId}/routing/rules`).then(r => setRules(r.data.rules || []));
    } catch (err) { toast.error("Failed"); }
  };

  return (
    <div className="space-y-6" data-testid="routing-tab">
      <div className="flex items-center justify-between">
        <p className="text-sm text-zinc-500">See which model handles each task. Override assignments and compare outputs.</p>
        <Button size="sm" onClick={() => setShowRuleForm(!showRuleForm)} className="bg-cyan-600 hover:bg-cyan-700" data-testid="routing-add-rule"><Plus className="w-3 h-3 mr-1" /> Add Rule</Button>
      </div>

      {showRuleForm && (
        <Card className="bg-zinc-900 border-zinc-800"><CardContent className="py-4 flex gap-3 items-end">
          <div className="flex-1"><label className="text-xs text-zinc-500 mb-1 block">Rule Name</label><Input value={ruleName} onChange={e => setRuleName(e.target.value)} className="bg-zinc-800 border-zinc-700 h-8" placeholder="e.g. Always use Claude for code" /></div>
          <div className="w-48"><label className="text-xs text-zinc-500 mb-1 block">Route to Model</label><Input value={ruleModel} onChange={e => setRuleModel(e.target.value)} className="bg-zinc-800 border-zinc-700 h-8" placeholder="claude-sonnet-4-5" /></div>
          <Button size="sm" onClick={createRule} className="bg-cyan-600 h-8">Save</Button>
        </CardContent></Card>
      )}

      {rules.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-zinc-300">Active Routing Rules</h3>
          {rules.map(r => (
            <div key={r.rule_id} className="flex items-center justify-between px-3 py-2 bg-zinc-900/50 rounded-lg border border-zinc-800">
              <div className="flex items-center gap-2"><Route className="w-3.5 h-3.5 text-cyan-400" /><span className="text-sm text-zinc-200">{r.name}</span></div>
              <Badge variant="outline" className="text-xs border-zinc-700">{r.model}</Badge>
            </div>
          ))}
        </div>
      )}

      <Card className="bg-zinc-900 border-zinc-800" data-testid="comparison-panel">
        <CardHeader><CardTitle className="text-sm text-zinc-100">Side-by-Side Model Comparison</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <Textarea placeholder="Enter a prompt to compare across models..." value={comparePrompt} onChange={e => setComparePrompt(e.target.value)} rows={3} className="bg-zinc-800 border-zinc-700" />
          <div className="flex gap-2 items-center">
            <span className="text-xs text-zinc-500">Models:</span>
            {["gpt-4o", "claude-sonnet-4-5-20250929", "gemini-2.0-flash", "deepseek-chat"].map(m => (
              <button key={m} onClick={() => setCompareModels(prev => prev.includes(m) ? prev.filter(x => x !== m) : [...prev, m].slice(0, 4))}
                className={`px-2 py-1 text-xs rounded border ${compareModels.includes(m) ? "bg-cyan-600/20 border-cyan-600/50 text-cyan-300" : "bg-zinc-800 border-zinc-700 text-zinc-500"}`}>
                {m.split("-")[0]}
              </button>
            ))}
          </div>
          <Button onClick={runComparison} disabled={comparing || !comparePrompt.trim()} className="bg-cyan-600 hover:bg-cyan-700 w-full" data-testid="run-comparison">
            {comparing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Zap className="w-4 h-4 mr-2" />} Compare {compareModels.length} Models
          </Button>
          {compareResults && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
              {(compareResults.results || []).map((r, i) => (
                <Card key={i} className={`border ${r.status === "completed" ? "border-zinc-700 bg-zinc-900/50" : "border-red-800/30 bg-red-900/10"}`}>
                  <CardContent className="py-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <Badge variant="outline" className="text-xs border-zinc-700">{r.model}</Badge>
                      <span className="text-xs text-zinc-500">{r.latency_ms}ms</span>
                    </div>
                    {r.status === "completed" ? (
                      <p className="text-xs text-zinc-300 whitespace-pre-wrap max-h-40 overflow-y-auto">{r.output}</p>
                    ) : (
                      <p className="text-xs text-red-400">{r.error}</p>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {routing.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-zinc-300">Recent Routing Activity</h3>
          {routing.slice(0, 10).map((r, i) => (
            <div key={i} className="flex items-center justify-between px-3 py-2 bg-zinc-900/30 rounded border border-zinc-800/50 text-xs">
              <div className="flex items-center gap-2"><span className="text-zinc-400">{r.agent}</span><ArrowRight className="w-3 h-3 text-zinc-600" /><span className="text-cyan-400">{r.model || "auto"}</span></div>
              <div className="flex items-center gap-3"><span className="text-zinc-500">{r.tokens} tok</span><span className="text-emerald-400">${r.cost_usd?.toFixed(4)}</span></div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============ NX-002: Workspace Branching & Snapshots ============
function WorkspacesTab({ workspaceId }) {
  const [snapshots, setSnapshots] = useState([]);
  const [summary, setSummary] = useState(null);
  const [branchName, setBranchName] = useState("");
  const [snapName, setSnapName] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.get(`/workspaces/${workspaceId}/snapshots`).then(r => setSnapshots(r.data.snapshots || [])).catch(() => {});
    api.get(`/workspaces/${workspaceId}/context-summary`).then(r => setSummary(r.data)).catch(() => {});
  }, [workspaceId]);

  const createBranch = async () => {
    if (!branchName) return;
    setLoading(true);
    try {
      const res = await api.post(`/workspaces/${workspaceId}/branch`, { name: branchName });
      toast.success(`Branched to ${res.data.workspace_id}`);
      setBranchName("");
    } catch (err) { toast.error("Branch failed"); }
    setLoading(false);
  };

  const createSnapshot = async () => {
    if (!snapName) return;
    try {
      await api.post(`/workspaces/${workspaceId}/snapshots`, { name: snapName });
      toast.success("Snapshot saved");
      setSnapName("");
      api.get(`/workspaces/${workspaceId}/snapshots`).then(r => setSnapshots(r.data.snapshots || []));
    } catch (err) { toast.error("Snapshot failed"); }
  };

  return (
    <div className="space-y-6" data-testid="workspaces-tab">
      {summary && (
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader><CardTitle className="text-sm text-zinc-100">Project Context Summary</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-xs text-zinc-400">
            <div className="grid grid-cols-3 gap-4">
              <div><span className="text-zinc-500">Channels:</span> <span className="text-zinc-200">{summary.channel_count}</span></div>
              <div><span className="text-zinc-500">Recent Activity:</span> <span className="text-zinc-200">{summary.recent_activity} msgs</span></div>
              <div><span className="text-zinc-500">Memory Entries:</span> <span className="text-zinc-200">{summary.memory_entries}</span></div>
            </div>
            {summary.key_topics?.length > 0 && <div><span className="text-zinc-500">Key Topics: </span>{summary.key_topics.filter(Boolean).slice(0, 8).map(t => <Badge key={t} variant="outline" className="text-xs border-zinc-700 mr-1">{t}</Badge>)}</div>}
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-2 gap-4">
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader><CardTitle className="text-sm text-zinc-100">Branch Workspace</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <p className="text-xs text-zinc-500">Fork this workspace to explore alternatives without losing current state.</p>
            <Input placeholder="Branch name" value={branchName} onChange={e => setBranchName(e.target.value)} className="bg-zinc-800 border-zinc-700" data-testid="branch-name" />
            <Button onClick={createBranch} disabled={loading || !branchName} className="bg-indigo-600 hover:bg-indigo-700 w-full" data-testid="create-branch">
              <GitBranch className="w-4 h-4 mr-2" /> Create Branch
            </Button>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader><CardTitle className="text-sm text-zinc-100">Save Snapshot</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <p className="text-xs text-zinc-500">Save current state as a named checkpoint you can restore later.</p>
            <Input placeholder="Snapshot name" value={snapName} onChange={e => setSnapName(e.target.value)} className="bg-zinc-800 border-zinc-700" data-testid="snap-name" />
            <Button onClick={createSnapshot} disabled={!snapName} className="bg-emerald-600 hover:bg-emerald-700 w-full" data-testid="create-snap">
              <Shield className="w-4 h-4 mr-2" /> Save Snapshot
            </Button>
          </CardContent>
        </Card>
      </div>

      {snapshots.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-zinc-300">Saved Snapshots</h3>
          {snapshots.map(s => (
            <Card key={s.snapshot_id} className="bg-zinc-900/50 border-zinc-800">
              <CardContent className="py-3 flex items-center justify-between">
                <div><span className="text-sm text-zinc-200">{s.name}</span><span className="text-xs text-zinc-500 ml-2">{s.channel_states?.length} channels, {s.memory_count} memories</span></div>
                <span className="text-xs text-zinc-600">{new Date(s.created_at).toLocaleDateString()}</span>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

// ============ NX-004: Cost Controls ============
function CostControlsTab({ workspaceId }) {
  const [budgets, setBudgets] = useState([]);
  const [attribution, setAttribution] = useState(null);
  const [estPrompt, setEstPrompt] = useState("");
  const [estModel, setEstModel] = useState("gpt-4o");
  const [estimate, setEstimate] = useState(null);
  const [newLimit, setNewLimit] = useState("5");
  const [newPeriod, setNewPeriod] = useState("daily");

  useEffect(() => {
    api.get(`/workspaces/${workspaceId}/cost/budgets`).then(r => setBudgets(r.data.budgets || [])).catch(() => {});
    api.get(`/workspaces/${workspaceId}/cost/attribution?period=7d`).then(r => setAttribution(r.data)).catch(() => {});
  }, [workspaceId]);

  const getEstimate = async () => {
    if (!estPrompt) return;
    try {
      const res = await api.post(`/workspaces/${workspaceId}/cost/estimate`, { prompt: estPrompt, model: estModel });
      setEstimate(res.data);
    } catch (err) { toast.error("Estimate failed"); }
  };

  const addBudget = async () => {
    try {
      await api.post(`/workspaces/${workspaceId}/cost/budgets`, { scope: "workspace", limit_usd: parseFloat(newLimit), period: newPeriod, pause_on_exceed: true });
      toast.success("Budget limit set");
      api.get(`/workspaces/${workspaceId}/cost/budgets`).then(r => setBudgets(r.data.budgets || []));
    } catch (err) { toast.error("Failed"); }
  };

  return (
    <div className="space-y-6" data-testid="costs-tab">
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader><CardTitle className="text-sm text-zinc-100">Pre-Execution Cost Estimate</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <Textarea placeholder="Paste your prompt to estimate cost..." value={estPrompt} onChange={e => setEstPrompt(e.target.value)} rows={2} className="bg-zinc-800 border-zinc-700" />
          <div className="flex gap-2">
            <Select value={estModel} onValueChange={setEstModel}><SelectTrigger className="w-48 bg-zinc-800 border-zinc-700"><SelectValue /></SelectTrigger>
              <SelectContent>{["gpt-4o", "gpt-4o-mini", "claude-sonnet-4-5-20250929", "gemini-2.0-flash", "deepseek-chat"].map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}</SelectContent>
            </Select>
            <Button onClick={getEstimate} className="bg-cyan-600 hover:bg-cyan-700"><DollarSign className="w-4 h-4 mr-1" /> Estimate</Button>
          </div>
          {estimate && (
            <div className="p-3 bg-zinc-800/50 rounded-lg border border-zinc-700/30 space-y-2">
              <div className="flex justify-between"><span className="text-xs text-zinc-400">Estimated Cost</span><span className="text-lg font-bold text-emerald-400">${estimate.estimated_cost_usd}</span></div>
              <div className="text-xs text-zinc-500">~{estimate.estimated_tokens} tokens | Range: ${estimate.cost_range?.low} - ${estimate.cost_range?.high}</div>
              {estimate.alternatives?.length > 0 && (
                <div className="mt-2"><span className="text-xs text-zinc-500">Cheaper alternatives:</span>
                  {estimate.alternatives.slice(0, 3).map(a => (
                    <div key={a.model} className="flex justify-between text-xs mt-1"><span className="text-zinc-400">{a.model}</span><span className="text-emerald-400">${a.estimated_cost}</span></div>
                  ))}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader><CardTitle className="text-sm text-zinc-100">Budget Limits</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2 items-end">
            <div><label className="text-xs text-zinc-500 mb-1 block">Limit ($)</label><Input type="number" value={newLimit} onChange={e => setNewLimit(e.target.value)} className="bg-zinc-800 border-zinc-700 h-8 w-24" /></div>
            <Select value={newPeriod} onValueChange={setNewPeriod}><SelectTrigger className="bg-zinc-800 border-zinc-700 h-8 w-28"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="daily">Daily</SelectItem><SelectItem value="weekly">Weekly</SelectItem><SelectItem value="monthly">Monthly</SelectItem></SelectContent>
            </Select>
            <Button size="sm" onClick={addBudget} className="bg-amber-600 hover:bg-amber-700 h-8"><Plus className="w-3 h-3 mr-1" /> Set Limit</Button>
          </div>
          {budgets.map(b => (
            <div key={b.budget_id} className="flex items-center justify-between px-3 py-2 bg-zinc-800/30 rounded border border-zinc-700/30">
              <span className="text-sm text-zinc-200">${b.limit_usd}/{b.period}</span>
              <Badge variant="outline" className={`text-xs ${b.pause_on_exceed ? "border-amber-800 text-amber-400" : "border-zinc-700"}`}>{b.pause_on_exceed ? "Auto-pause" : "Alert only"}</Badge>
            </div>
          ))}
        </CardContent>
      </Card>

      {attribution && attribution.by_model_agent?.length > 0 && (
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader><CardTitle className="text-sm text-zinc-100">Cost Attribution (7 days)</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {attribution.by_model_agent.map((a, i) => (
              <div key={i} className="flex items-center justify-between text-xs py-1 border-b border-zinc-800/50 last:border-0">
                <div><span className="text-zinc-300">{a.agent}</span> <span className="text-zinc-600">via</span> <span className="text-cyan-400">{a.model}</span></div>
                <div className="flex gap-4"><span className="text-zinc-500">{a.total_tokens} tok</span><span className="text-emerald-400">${a.total_cost_usd}</span></div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ============ NX-005: MCP Integrations ============
function MCPTab({ workspaceId }) {
  const [connectors, setConnectors] = useState([]);
  const [connections, setConnections] = useState([]);
  const [mcpUrl, setMcpUrl] = useState("");
  const [mcpName, setMcpName] = useState("");
  const [connecting, setConnecting] = useState(false);

  useEffect(() => {
    api.get("/mcp/connectors").then(r => setConnectors(r.data.connectors || [])).catch(() => {});
    api.get(`/workspaces/${workspaceId}/mcp/connections`).then(r => setConnections(r.data.connections || [])).catch(() => {});
  }, [workspaceId]);

  const connectServer = async () => {
    if (!mcpUrl) return;
    setConnecting(true);
    try {
      const res = await api.post(`/workspaces/${workspaceId}/mcp/connect`, { url: mcpUrl, name: mcpName });
      toast.success(res.data.status === "active" ? "Connected!" : "Connection pending");
      setMcpUrl(""); setMcpName("");
      api.get(`/workspaces/${workspaceId}/mcp/connections`).then(r => setConnections(r.data.connections || []));
    } catch (err) { toast.error("Connection failed"); }
    setConnecting(false);
  };

  return (
    <div className="space-y-6" data-testid="mcp-tab">
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader><CardTitle className="text-sm text-zinc-100">Connect MCP Server</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <Input placeholder="MCP server URL (e.g. https://mcp.example.com)" value={mcpUrl} onChange={e => setMcpUrl(e.target.value)} className="bg-zinc-800 border-zinc-700" data-testid="mcp-url" />
          <Input placeholder="Connection name (optional)" value={mcpName} onChange={e => setMcpName(e.target.value)} className="bg-zinc-800 border-zinc-700" />
          <Button onClick={connectServer} disabled={connecting || !mcpUrl} className="bg-cyan-600 hover:bg-cyan-700 w-full" data-testid="mcp-connect">
            {connecting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Plug className="w-4 h-4 mr-2" />} Connect
          </Button>
        </CardContent>
      </Card>

      {connections.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-zinc-300">Active Connections</h3>
          {connections.map(c => (
            <Card key={c.connection_id} className="bg-zinc-900/50 border-zinc-800">
              <CardContent className="py-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${c.status === "active" ? "bg-emerald-400" : "bg-red-400"}`} />
                  <span className="text-sm text-zinc-200">{c.name}</span>
                  {c.tools_discovered?.length > 0 && <Badge variant="outline" className="text-xs border-zinc-700">{c.tools_discovered.length} tools</Badge>}
                </div>
                <Badge variant="outline" className={`text-xs ${c.status === "active" ? "border-emerald-800 text-emerald-400" : "border-red-800 text-red-400"}`}>{c.status}</Badge>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <div className="space-y-2">
        <h3 className="text-sm font-medium text-zinc-300">Connector Marketplace</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          {connectors.map(c => (
            <Card key={c.connector_id} className="bg-zinc-900/50 border-zinc-800 hover:border-zinc-700 transition-colors">
              <CardContent className="py-3 text-center">
                <div className="text-sm font-medium text-zinc-200">{c.name}</div>
                <div className="text-xs text-zinc-500 mt-1">{c.category}</div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}

// ============ NX-006: Execution Traces ============
function ExecutionTracesTab({ workspaceId }) {
  const [traces, setTraces] = useState([]);
  const [selectedTrace, setSelectedTrace] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/workspaces/${workspaceId}/execution-traces`).then(r => { setTraces(r.data.traces || []); setLoading(false); }).catch(() => setLoading(false));
  }, [workspaceId]);

  const viewTrace = async (traceId) => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/execution-traces/${traceId}`);
      setSelectedTrace(res.data);
    } catch (err) { toast.error("Failed to load trace"); }
  };

  const replayStep = async (traceId, stepId) => {
    try {
      const res = await api.post(`/workspaces/${workspaceId}/execution-traces/${traceId}/replay/${stepId}`, {});
      toast.success("Step replayed");
    } catch (err) { toast.error("Replay failed"); }
  };

  const forkStep = async (traceId, stepId) => {
    try {
      const res = await api.post(`/workspaces/${workspaceId}/execution-traces/${traceId}/fork/${stepId}`, {});
      toast.success(`Forked: ${res.data.run_id}`);
      api.get(`/workspaces/${workspaceId}/execution-traces`).then(r => setTraces(r.data.traces || []));
    } catch (err) { toast.error("Fork failed"); }
  };

  const exportTrace = (traceId) => {
    window.open(`${api.defaults.baseURL}/workspaces/${workspaceId}/execution-traces/${traceId}/export`, "_blank");
  };

  if (loading) return <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-zinc-500" /></div>;

  return (
    <div className="space-y-6" data-testid="traces-tab">
      {!selectedTrace ? (
        <>
          <p className="text-sm text-zinc-500">Visual execution traces for multi-agent workflows. Inspect, replay, fork, and export.</p>
          {traces.length === 0 ? (
            <Card className="bg-zinc-900 border-zinc-800"><CardContent className="py-12 text-center text-zinc-500">No execution traces yet. Run an orchestration to generate traces.</CardContent></Card>
          ) : traces.map(t => (
            <Card key={t.trace_id} className="bg-zinc-900/50 border-zinc-800 hover:border-zinc-700 cursor-pointer transition-colors" onClick={() => viewTrace(t.trace_id)}>
              <CardContent className="py-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {t.status === "completed" ? <CheckCircle2 className="w-5 h-5 text-emerald-400" /> : <XCircle className="w-5 h-5 text-red-400" />}
                  <div>
                    <div className="text-sm font-medium text-zinc-200">{t.name || t.trace_id}</div>
                    <div className="text-xs text-zinc-500">{t.step_count} steps &middot; {t.type}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button size="sm" variant="ghost" onClick={e => { e.stopPropagation(); exportTrace(t.trace_id); }} className="h-7 text-xs text-zinc-400"><Download className="w-3 h-3 mr-1" /> Export</Button>
                  <span className="text-xs text-zinc-600">{new Date(t.started_at).toLocaleString()}</span>
                </div>
              </CardContent>
            </Card>
          ))}
        </>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <Button variant="ghost" size="sm" onClick={() => setSelectedTrace(null)}>Back to Traces</Button>
            <Button size="sm" variant="ghost" onClick={() => exportTrace(selectedTrace.trace_id)} className="text-zinc-400"><Download className="w-3 h-3 mr-1" /> Export JSON</Button>
          </div>
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader><CardTitle className="text-sm text-zinc-100">{selectedTrace.name} — Execution DAG</CardTitle></CardHeader>
            <CardContent className="space-y-1">
              <div className="text-xs text-zinc-500 mb-3">Input: {selectedTrace.input_text?.slice(0, 200)}</div>
              {(selectedTrace.nodes || []).map((node, i) => (
                <div key={node.node_id} className={`p-3 rounded-lg border ${node.status === "completed" ? "border-emerald-800/30 bg-emerald-900/10" : node.status === "failed" ? "border-red-800/30 bg-red-900/10" : "border-zinc-800"}`}>
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono text-cyan-400">#{node.node_id}</span>
                      <span className="text-sm text-zinc-200">{node.agent}</span>
                      <Badge variant="outline" className={`text-xs ${node.status === "completed" ? "border-emerald-800 text-emerald-400" : "border-red-800 text-red-400"}`}>{node.status}</Badge>
                    </div>
                    <div className="flex gap-1">
                      <Button size="sm" variant="ghost" onClick={() => replayStep(selectedTrace.trace_id, node.node_id)} className="h-6 text-xs text-zinc-400" title="Replay"><RotateCcw className="w-3 h-3" /></Button>
                      <Button size="sm" variant="ghost" onClick={() => forkStep(selectedTrace.trace_id, node.node_id)} className="h-6 text-xs text-zinc-400" title="Fork"><GitFork className="w-3 h-3" /></Button>
                    </div>
                  </div>
                  {node.output && <div className="text-xs text-zinc-400 mt-1 max-h-24 overflow-y-auto whitespace-pre-wrap">{node.output}</div>}
                  {node.error && <div className="text-xs text-red-400 mt-1">{node.error}</div>}
                  {i < (selectedTrace.nodes?.length || 0) - 1 && selectedTrace.execution_mode !== "parallel" && (
                    <div className="flex justify-center py-1"><ArrowRight className="w-4 h-4 text-zinc-700 rotate-90" /></div>
                  )}
                </div>
              ))}
              {selectedTrace.final_output && (
                <div className="mt-3 p-3 bg-zinc-800/50 rounded-lg border border-zinc-700/30">
                  <div className="text-xs text-zinc-500 mb-1">Final Output</div>
                  <div className="text-sm text-zinc-200 whitespace-pre-wrap">{selectedTrace.final_output}</div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
