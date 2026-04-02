import { useState, useEffect, useCallback, useMemo } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Rocket, Plus, Play, Pause, Trash2, Clock, DollarSign, Activity, AlertTriangle, CheckCircle2, XCircle, Loader2, ChevronRight, Zap, Settings, Link2, Calendar, Copy, Check } from "lucide-react";
import { api } from "@/App";
import { useConfirm } from "@/components/ConfirmDialog";
import { toast } from "sonner";
import { DeploymentDetail } from "@/components/DeploymentDetail";

const STATUS_COLORS = {
  draft: "bg-zinc-600", active: "bg-emerald-500", paused: "bg-amber-500",
  failed: "bg-red-500", archived: "bg-zinc-700",
  running: "bg-blue-500 animate-pulse", queued: "bg-zinc-500",
  completed: "bg-emerald-500", cancelled: "bg-zinc-600",
  paused_approval: "bg-amber-500 animate-pulse",
};

export default function DeploymentPanel({ workspaceId, channels = [] }) {
  const { confirm: confirmAction, ConfirmDialog: ConfirmDlg } = useConfirm();
  const [deployments, setDeployments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedDep, setSelectedDep] = useState(null);
  const [runs, setRuns] = useState([]);
  const [runsLoading, setRunsLoading] = useState(false);
  const [newName, setNewName] = useState("");
  const [newGoal, setNewGoal] = useState("");
  const [newAgent, setNewAgent] = useState("chatgpt");
  const [newOutputChannel, setNewOutputChannel] = useState("");
  const [triggering, setTriggering] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [actions, setActions] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);
  const [limits, setLimits] = useState(null);
  const [webhooks, setWebhooks] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [copiedWh, setCopiedWh] = useState(null);
  const [newCron, setNewCron] = useState("");

  const fetchDeployments = useCallback(async () => {
    try {
      const [depRes, tmplRes, limRes] = await Promise.all([
        api.get(`/workspaces/${workspaceId}/deployments`),
        api.get("/deployment-templates").catch(() => ({ data: [] })),
        api.get(`/workspaces/${workspaceId}/deployment-limits`).catch(() => ({ data: null })),
      ]);
      setDeployments(depRes.data || []);
      setTemplates(tmplRes.data || []);
      setLimits(limRes.data);
    } catch (err) { toast.error("Failed to load deployments"); }
    finally { setLoading(false); }
  }, [workspaceId]);

  useEffect(() => { fetchDeployments(); }, [fetchDeployments]);

  const fetchRuns = async (depId) => {
    setRunsLoading(true);
    try {
      const res = await api.get(`/deployments/${depId}/runs?limit=10`);
      setRuns(res.data || []);
    } catch (err) { setRuns([]); }
    setRunsLoading(false);
  };

  const createDeployment = async () => {
    if (!newName.trim() || !newGoal.trim()) return;
    try {
      const res = await api.post(`/workspaces/${workspaceId}/deployments`, {
        name: newName,
        agents: [{ agent_key: newAgent, role: "primary" }],
        objective: { goal: newGoal, success_criteria: [], output_channel_id: newOutputChannel },
        triggers: [{ type: "manual" }],
      });
      setCreateOpen(false);
      setNewName(""); setNewGoal(""); setNewOutputChannel("");
      toast.success("Deployment created");
      fetchDeployments();
      setSelectedDep(res.data);
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  const activateDep = async (depId) => {
    try {
      await api.post(`/deployments/${depId}/activate`);
      toast.success("Deployment activated");
      fetchDeployments();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed to activate"); }
  };

  const pauseDep = async (depId) => {
    try {
      await api.post(`/deployments/${depId}/pause`);
      toast.success("Deployment paused");
      fetchDeployments();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  const triggerRun = async (depId) => {
    setTriggering(true);
    try {
      const res = await api.post(`/deployments/${depId}/trigger`, {});
      toast.success(`Run started: ${res.data.run_id}`);
      if (selectedDep?.deployment_id === depId) fetchRuns(depId);
      fetchDeployments();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed to trigger"); }
    setTriggering(false);
  };

  const deleteDep = async (depId) => {
    const ok = await confirmAction("Archive Deployment", "Archive this deployment? It can be restored later."); if (!ok) return;
    try {
      await api.delete(`/deployments/${depId}`);
      toast.success("Archived");
      if (selectedDep?.deployment_id === depId) setSelectedDep(null);
      fetchDeployments();
    } catch (err) { toast.error("Failed"); }
  };

  const selectDep = (dep) => {
    setSelectedDep(dep);
    setSelectedRun(null);
    setActions([]);
    fetchRuns(dep.deployment_id);
    // Load webhooks and schedules
    api.get(`/deployments/${dep.deployment_id}/webhooks`).then(r => setWebhooks(r.data || [])).catch(() => setWebhooks([]));
    api.get(`/deployments/${dep.deployment_id}/schedules`).then(r => setSchedules(r.data || [])).catch(() => setSchedules([]));
  };

  const createWebhook = async (depId) => {
    try {
      const res = await api.post(`/deployments/${depId}/webhooks`, { events: ["*"] });
      setWebhooks(prev => [...prev, res.data]);
      toast.success("Webhook created");
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  const deleteWebhook = async (whId) => {
    try {
      await api.delete(`/deployment-webhooks/${whId}`);
      setWebhooks(prev => prev.filter(w => w.webhook_id !== whId));
      toast.success("Webhook removed");
    } catch (err) { toast.error("Failed"); }
  };

  const createSchedule = async (depId) => {
    if (!newCron.trim()) return;
    try {
      const res = await api.post(`/deployments/${depId}/schedules`, { schedule: newCron, description: "" });
      setSchedules(prev => [...prev, res.data]);
      setNewCron("");
      toast.success("Schedule created");
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  const deleteSchedule = async (schedId) => {
    try {
      await api.delete(`/deployment-schedules/${schedId}`);
      setSchedules(prev => prev.filter(s => s.schedule_id !== schedId));
      toast.success("Schedule removed");
    } catch (err) { toast.error("Failed"); }
  };

  const viewRunActions = async (run) => {
    setSelectedRun(run);
    try {
      const res = await api.get(`/deployment-runs/${run.run_id}/actions`);
      setActions(res.data || []);
    } catch (err) { setActions([]); }
  };

  const createFromTemplate = async (template) => {
    try {
      const res = await api.post(`/workspaces/${workspaceId}/deployments/from-template`, {
        template_id: template.id,
        name: template.name,
        output_channel_id: "",
      });
      setCreateOpen(false);
      toast.success(`Created "${template.name}" from template`);
      fetchDeployments();
      setSelectedDep(res.data);
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  const AGENTS = [
    { key: "chatgpt", name: "ChatGPT" }, { key: "claude", name: "Claude" },
    { key: "gemini", name: "Gemini" }, { key: "deepseek", name: "DeepSeek" },
    { key: "grok", name: "Grok" }, { key: "mistral", name: "Mistral" },
    { key: "manus", name: "Manus" },
  ];

  const activeDeployments = useMemo(() => deployments.filter(d => d.status !== "archived"), [deployments]);

  if (loading) return <div className="flex-1 flex items-center justify-center"><Loader2 className="w-5 h-5 animate-spin text-zinc-500" /></div>;

  return (
    <div className="flex-1 flex min-h-0" data-testid="deployment-panel">
      {/* Left: Deployment List */}
      <div className="w-80 border-r border-zinc-800/60 flex flex-col">
        <div className="px-4 py-3 border-b border-zinc-800/40 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Rocket className="w-4 h-4 text-cyan-400" />
            <span className="text-sm font-semibold text-zinc-200">Deployments</span>
            <Badge className="text-[9px] bg-zinc-800 text-zinc-400">{deployments.length}</Badge>
          </div>
          <Button size="sm" onClick={() => setCreateOpen(true)} className="h-7 px-2 bg-cyan-500 hover:bg-cyan-400 text-white" data-testid="create-deployment-btn">
            <Plus className="w-3.5 h-3.5" />
          </Button>
        </div>
        <ScrollArea className="flex-1">
          {deployments.length === 0 ? (
            <div className="p-6 text-center">
              <Rocket className="w-8 h-8 text-zinc-700 mx-auto mb-2" />
              <p className="text-xs text-zinc-500">No deployments yet</p>
              <Button size="sm" onClick={() => setCreateOpen(true)} className="mt-3 bg-zinc-800 text-zinc-300 text-xs">Create First Deployment</Button>
            </div>
          ) : (
            <div className="p-2 space-y-1">
              {activeDeployments.map(dep => (
                <button key={dep.deployment_id} onClick={() => selectDep(dep)}
                  className={`w-full text-left p-3 rounded-lg border transition-all ${
                    selectedDep?.deployment_id === dep.deployment_id
                      ? "border-cyan-500/40 bg-cyan-500/5"
                      : "border-zinc-800/40 hover:border-zinc-700 bg-zinc-900/30"
                  }`} data-testid={`dep-${dep.deployment_id}`}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-zinc-200 truncate">{dep.name}</span>
                    <div className={`w-2 h-2 rounded-full ${STATUS_COLORS[dep.status] || "bg-zinc-600"}`} />
                  </div>
                  <div className="flex items-center gap-3 text-[10px] text-zinc-500">
                    <span>{dep.status}</span>
                    {dep.stats && <span>${dep.stats.total_cost_usd || 0}</span>}
                    {dep.stats && <span>{dep.stats.total_runs || 0} runs</span>}
                  </div>
                </button>
              ))}
            </div>
          )}
        </ScrollArea>
      </div>
      {/* Right: Detail View */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <DeploymentDetail
          selectedDep={selectedDep}
          activateDep={activateDep}
          pauseDep={pauseDep}
          deleteDep={deleteDep}
          triggerRun={triggerRun}
          triggering={triggering}
          createWebhook={createWebhook}
          deleteWebhook={deleteWebhook}
          createSchedule={createSchedule}
          deleteSchedule={deleteSchedule}
          webhooks={webhooks}
          schedules={schedules}
          runs={runs}
          actions={actions}
          templates={templates}
        />
      </div>

      {/* Create Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-md">
          <DialogHeader>
            <DialogTitle className="text-zinc-100 flex items-center gap-2"><Rocket className="w-4 h-4 text-cyan-400" /> New Deployment</DialogTitle>
            <DialogDescription className="text-zinc-500">Create from template or start from scratch</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 mt-2">
            {/* Templates */}
            {templates.length > 0 && (
              <div>
                <label className="text-xs text-zinc-500 mb-1.5 block">Quick Start Templates</label>
                <div className="grid grid-cols-2 gap-1.5 mb-3">
                  {templates.map(t => (
                    <button key={t.id} onClick={() => createFromTemplate(t)}
                      className="p-2 rounded-lg border border-zinc-800/40 hover:border-cyan-500/30 bg-zinc-900/50 text-left transition-all"
                      data-testid={`template-${t.id}`}>
                      <span className="text-[11px] font-medium text-zinc-300 block">{t.name}</span>
                      <span className="text-[9px] text-zinc-600 line-clamp-2">{t.description}</span>
                    </button>
                  ))}
                </div>
                <div className="border-t border-zinc-800/30 pt-2 mb-1">
                  <span className="text-[10px] text-zinc-600 uppercase tracking-wider">Or create custom</span>
                </div>
              </div>
            )}
            <Input value={newName} onChange={e => setNewName(e.target.value)} placeholder="Deployment name" className="bg-zinc-950 border-zinc-800" data-testid="dep-name-input" />
            <textarea value={newGoal} onChange={e => setNewGoal(e.target.value)} placeholder="Objective / Goal (what should the agent accomplish?)" className="w-full bg-zinc-950 border border-zinc-800 rounded-md px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 min-h-[80px]" data-testid="dep-goal-input" />
            <div>
              <label className="text-xs text-zinc-500 mb-1 block">Primary Agent</label>
              <select value={newAgent} onChange={e => setNewAgent(e.target.value)} className="w-full bg-zinc-950 border border-zinc-800 rounded-md px-3 py-2 text-sm text-zinc-200" data-testid="dep-agent-select">
                {AGENTS.map(a => <option key={a.key} value={a.key}>{a.name}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-zinc-500 mb-1 block">Output Channel (optional)</label>
              <select value={newOutputChannel} onChange={e => setNewOutputChannel(e.target.value)} className="w-full bg-zinc-950 border border-zinc-800 rounded-md px-3 py-2 text-sm text-zinc-200">
                <option value="">None</option>
                {channels.map(ch => <option key={ch.channel_id} value={ch.channel_id}>#{ch.name}</option>)}
              </select>
            </div>
            <Button onClick={createDeployment} disabled={!newName.trim() || !newGoal.trim()} className="w-full bg-cyan-500 hover:bg-cyan-400 text-white" data-testid="dep-create-submit">Create Deployment</Button>
          </div>
        </DialogContent>
      </Dialog>
      <ConfirmDlg />
    </div>
  );
}
