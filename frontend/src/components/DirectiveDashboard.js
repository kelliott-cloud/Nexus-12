import { useState, useEffect } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { api } from "@/App";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Target, CheckCircle2, AlertTriangle, Clock, Bot, Zap, DollarSign } from "lucide-react";
import { toast } from "sonner";

const AI_COLORS = {
  claude: "#D97757", chatgpt: "#10A37F", gemini: "#4285F4", deepseek: "#4D6BFE",
  grok: "#F5F5F5", groq: "#F55036", perplexity: "#20B2AA", mistral: "#FF7000",
  cohere: "#39594D", mercury: "#00D4FF", pi: "#FF6B35", manus: "#6C5CE7",
  qwen: "#615EFF", kimi: "#000000", llama: "#0467DF", glm: "#3D5AFE",
  cursor: "#00E5A0", notebooklm: "#FBBC04", copilot: "#171515",
};
const AI_NAMES = {
  claude: "Claude", chatgpt: "ChatGPT", gemini: "Gemini", deepseek: "DeepSeek",
  grok: "Grok", groq: "Groq", perplexity: "Perplexity", mistral: "Mistral",
  cohere: "Cohere", mercury: "Mercury 2", pi: "Pi", manus: "Manus",
  qwen: "Qwen", kimi: "Kimi", llama: "Llama", glm: "GLM",
  cursor: "Cursor", notebooklm: "NotebookLM", copilot: "GitHub Copilot",
};

export default function DirectiveDashboard({ workspaceId }) {
  const [directive, setDirective] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const dirRes = await api.get(`/workspaces/${workspaceId}/directives/active`);
        const dir = dirRes.data?.directive;
        setDirective(dir);
        if (dir) {
          const [dashRes, taskRes] = await Promise.all([
            api.get(`/directives/${dir.directive_id}/dashboard`),
            api.get(`/directives/${dir.directive_id}/tasks`),
          ]);
          setDashboard(dashRes.data);
          setTasks(taskRes.data?.tasks || []);
        }
      } catch (err) { handleSilent(err, "DirectiveDashboard:op1"); }
      setLoading(false);
    };
    load();
  }, [workspaceId]);

  const checkGate = async (phaseId) => {
    if (!directive) return;
    try {
      const res = await api.post(`/directives/${directive.directive_id}/check-gate/${phaseId}`);
      if (res.data.gate_passed) toast.success("Phase gate passed! Next phase unlocked.");
      else toast.info(`Gate not met: ${res.data.remaining} tasks remaining`);
    } catch (err) { toast.error("Gate check failed"); }
  };

  if (loading) return <div className="p-6 text-center text-zinc-500">Loading...</div>;
  if (!directive) return (
    <div className="p-6 text-center">
      <Target className="w-10 h-10 text-zinc-800 mx-auto mb-3" />
      <p className="text-sm text-zinc-500">No active directive</p>
      <p className="text-xs text-zinc-600 mt-1">Open a channel and click the target icon to create one</p>
    </div>
  );

  const d = dashboard;

  return (
    <div className="h-full flex flex-col" data-testid="directive-dashboard">
      <div className="flex-shrink-0 px-6 py-4 border-b border-zinc-800/60">
        <div className="flex items-center gap-2">
          <Target className="w-5 h-5 text-amber-400" />
          <h2 className="text-lg font-semibold text-zinc-200" style={{ fontFamily: "Syne, sans-serif" }}>Directive Dashboard</h2>
          <Badge className="bg-emerald-500/20 text-emerald-400 text-[10px]">Active</Badge>
        </div>
        <p className="text-sm text-zinc-400 mt-1">{directive.project_name}</p>
        {directive.goal && <p className="text-xs text-zinc-500 mt-0.5">{directive.goal}</p>}
      </div>

      <ScrollArea className="flex-1">
        <div className="p-6 space-y-6">
          {/* Overall Progress */}
          {d?.overall && (
            <div className="grid grid-cols-4 gap-3">
              <div className="p-3 rounded-lg bg-zinc-800/30 border border-zinc-800/40 text-center">
                <p className="text-2xl font-bold text-zinc-200">{d.overall.progress}%</p>
                <p className="text-[10px] text-zinc-500">Progress</p>
              </div>
              <div className="p-3 rounded-lg bg-zinc-800/30 border border-zinc-800/40 text-center">
                <p className="text-2xl font-bold text-emerald-400">{d.overall.done}</p>
                <p className="text-[10px] text-zinc-500">Completed</p>
              </div>
              <div className="p-3 rounded-lg bg-zinc-800/30 border border-zinc-800/40 text-center">
                <p className="text-2xl font-bold text-zinc-300">{d.overall.total - d.overall.done}</p>
                <p className="text-[10px] text-zinc-500">Remaining</p>
              </div>
              <div className="p-3 rounded-lg bg-zinc-800/30 border border-zinc-800/40 text-center">
                <p className="text-2xl font-bold text-red-400">{d.overall.escalated}</p>
                <p className="text-[10px] text-zinc-500">Escalated</p>
              </div>
            </div>
          )}

          {/* Phase Progress */}
          {d?.phases?.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">Phases</h3>
              <div className="space-y-2">
                {d.phases.map(phase => (
                  <div key={phase.phase_id} className="p-3 rounded-lg bg-zinc-800/20 border border-zinc-800/40">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        {phase.gate_passed ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <Clock className="w-4 h-4 text-zinc-500" />}
                        <span className="text-sm font-medium text-zinc-200">{phase.name}</span>
                        <span className="text-[10px] text-zinc-600">{phase.merged}/{phase.total}</span>
                      </div>
                      {!phase.gate_passed && phase.total > 0 && (
                        <Button size="sm" variant="outline" onClick={() => checkGate(phase.phase_id)}
                          className="border-zinc-700 text-zinc-300 h-6 text-[10px]">Check Gate</Button>
                      )}
                    </div>
                    <div className="w-full h-2 bg-zinc-800 rounded-full overflow-hidden">
                      <div className="h-full rounded-full transition-all" style={{
                        width: `${phase.progress}%`,
                        backgroundColor: phase.gate_passed ? "#10b981" : phase.failed > 0 ? "#f59e0b" : "#3b82f6",
                      }} />
                    </div>
                    {phase.failed > 0 && (
                      <p className="text-[10px] text-red-400 mt-1 flex items-center gap-1"><AlertTriangle className="w-3 h-3" />{phase.failed} failed/escalated</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Agent Stats */}
          {d?.agent_stats?.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-1"><Bot className="w-3 h-3" /> Agent Performance</h3>
              <div className="space-y-1.5">
                {d.agent_stats.map(a => (
                  <div key={a.agent} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-zinc-800/20">
                    <div className="w-6 h-6 rounded-full flex items-center justify-center text-[9px] font-bold"
                      style={{ backgroundColor: AI_COLORS[a.agent] || "#666", color: a.agent === "grok" ? "#09090b" : "#fff" }}>
                      {(AI_NAMES[a.agent] || a.agent)[0]}
                    </div>
                    <span className="text-xs text-zinc-300 w-20">{AI_NAMES[a.agent] || a.agent}</span>
                    <div className="flex-1 flex gap-2">
                      <Badge className="bg-emerald-500/15 text-emerald-400 text-[9px]">{a.merged} done</Badge>
                      {a.failed > 0 && <Badge className="bg-red-500/15 text-red-400 text-[9px]">{a.failed} failed</Badge>}
                      <span className="text-[10px] text-zinc-600 ml-auto">{a.total} total</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Cost */}
          {d?.cost && (
            <div>
              <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-1"><DollarSign className="w-3 h-3" /> Token Budget</h3>
              <div className="p-3 rounded-lg bg-zinc-800/20 border border-zinc-800/40">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-zinc-400">{d.cost.total_tokens.toLocaleString()} / {d.cost.budget.toLocaleString()}</span>
                  <span className={`text-xs font-medium ${d.cost.percentage >= 80 ? "text-red-400" : d.cost.percentage >= 50 ? "text-amber-400" : "text-emerald-400"}`}>{d.cost.percentage}%</span>
                </div>
                <div className="w-full h-2.5 bg-zinc-800 rounded-full overflow-hidden">
                  <div className="h-full rounded-full transition-all" style={{
                    width: `${Math.min(d.cost.percentage, 100)}%`,
                    backgroundColor: d.cost.percentage >= 80 ? "#ef4444" : d.cost.percentage >= 50 ? "#f59e0b" : "#10b981",
                  }} />
                </div>
              </div>
            </div>
          )}

          {/* Tasks */}
          {tasks.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">Tasks ({tasks.length})</h3>
              <div className="space-y-1">
                {tasks.map(t => (
                  <div key={t.task_id} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-zinc-800/10 hover:bg-zinc-800/30">
                    {t.status === "merged" ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" /> :
                     t.status === "escalated" ? <AlertTriangle className="w-3.5 h-3.5 text-red-400 flex-shrink-0" /> :
                     t.status === "in_progress" ? <Clock className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" /> :
                     <div className="w-3.5 h-3.5 rounded-full border border-zinc-700 flex-shrink-0" />}
                    <span className={`text-xs flex-1 ${t.status === "merged" ? "text-zinc-500 line-through" : "text-zinc-300"}`}>{t.title}</span>
                    <span className="text-[9px] text-zinc-600">{AI_NAMES[t.assigned_agent] || t.assigned_agent}</span>
                    <Badge className={`text-[8px] ${
                      t.status === "merged" ? "bg-emerald-500/15 text-emerald-400" :
                      t.status === "escalated" ? "bg-red-500/15 text-red-400" :
                      t.status === "in_progress" ? "bg-blue-500/15 text-blue-400" :
                      "bg-zinc-800 text-zinc-500"
                    }`}>{t.status}</Badge>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
