/**
 * DeploymentDetail — Right-side detail view for a selected deployment.
 * Shows header, stats, webhooks, schedules, run history, and action buttons.
 * Extracted from DeploymentPanel.js for maintainability.
 */
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Play, Pause, Trash2, Zap, Loader2, Plus, Activity, CheckCircle2, XCircle,
  DollarSign, Link2, Clock, Rocket
} from "lucide-react";

const STATUS_COLORS = {
  draft: "bg-zinc-600", active: "bg-emerald-500", paused: "bg-amber-500",
  completed: "bg-blue-500", failed: "bg-red-500", archived: "bg-zinc-700",
};

export function DeploymentDetail({
  selectedDep, activateDep, pauseDep, deleteDep,
  triggerRun, triggering, createWebhook, deleteWebhook,
  createSchedule, deleteSchedule,
  webhooks, schedules, runs, actions, templates,
}) {
  if (!selectedDep) {
    return (
      <div className="flex-1 flex items-center justify-center text-center p-8">
        <div>
          <Rocket className="w-12 h-12 text-zinc-800 mx-auto mb-3" />
          <p className="text-sm text-zinc-400 mb-1">Select a deployment to view details</p>
          <p className="text-xs text-zinc-600">Or create a new autonomous agent deployment</p>
        </div>
      </div>
    );
  }

  return (
    <>
      {/* Header */}
      <div className="px-6 py-4 border-b border-zinc-800/40 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold text-zinc-100">{selectedDep.name}</h2>
            <Badge className={`text-[9px] ${STATUS_COLORS[selectedDep.status]} text-white`}>{selectedDep.status}</Badge>
          </div>
          <p className="text-xs text-zinc-500 mt-0.5">{selectedDep.objective?.goal?.substring(0, 100) || "No objective"}</p>
        </div>
        <div className="flex items-center gap-2">
          {selectedDep.status === "draft" && (
            <Button size="sm" onClick={() => activateDep(selectedDep.deployment_id)} className="bg-emerald-500 hover:bg-emerald-400 text-white text-xs gap-1" data-testid="activate-btn">
              <Play className="w-3 h-3" /> Activate
            </Button>
          )}
          {selectedDep.status === "active" && (
            <>
              <Button size="sm" onClick={() => triggerRun(selectedDep.deployment_id)} disabled={triggering} className="bg-cyan-500 hover:bg-cyan-400 text-white text-xs gap-1" data-testid="trigger-btn">
                {triggering ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />} Trigger Run
              </Button>
              <Button size="sm" variant="outline" onClick={() => pauseDep(selectedDep.deployment_id)} className="border-zinc-700 text-zinc-400 text-xs gap-1">
                <Pause className="w-3 h-3" /> Pause
              </Button>
            </>
          )}
          {selectedDep.status === "paused" && (
            <Button size="sm" onClick={() => activateDep(selectedDep.deployment_id)} className="bg-emerald-500 hover:bg-emerald-400 text-white text-xs gap-1">
              <Play className="w-3 h-3" /> Resume
            </Button>
          )}
          <Button size="sm" variant="ghost" onClick={() => deleteDep(selectedDep.deployment_id)} className="text-red-400 hover:text-red-300 text-xs">
            <Trash2 className="w-3 h-3" />
          </Button>
        </div>
      </div>

      {/* Stats */}
      {selectedDep.stats && (
        <div className="px-6 py-3 border-b border-zinc-800/30 flex items-center gap-6 text-xs">
          <div className="flex items-center gap-1.5 text-zinc-400"><Activity className="w-3.5 h-3.5" /> {selectedDep.stats.total_runs} runs</div>
          <div className="flex items-center gap-1.5 text-emerald-400"><CheckCircle2 className="w-3.5 h-3.5" /> {selectedDep.stats.successful_runs} ok</div>
          <div className="flex items-center gap-1.5 text-red-400"><XCircle className="w-3.5 h-3.5" /> {selectedDep.stats.failed_runs} failed</div>
          <div className="flex items-center gap-1.5 text-zinc-400"><DollarSign className="w-3.5 h-3.5" /> ${selectedDep.stats.total_cost_usd}</div>
        </div>
      )}

      {/* Runs, webhooks, schedules */}
      <ScrollArea className="flex-1 px-6 py-4">
        {/* Webhooks */}
        <div className="mb-4">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-xs font-semibold text-zinc-400 flex items-center gap-1"><Link2 className="w-3 h-3" /> Webhooks</h3>
            <Button size="sm" onClick={() => createWebhook(selectedDep.deployment_id)} className="h-6 px-2 text-[10px] bg-zinc-800 text-zinc-300"><Plus className="w-3 h-3 mr-1" />Add</Button>
          </div>
          {webhooks.length === 0 ? (
            <p className="text-[10px] text-zinc-600">No webhooks configured</p>
          ) : (
            <div className="space-y-1">
              {webhooks.map(wh => (
                <div key={wh.webhook_id} className="flex items-center justify-between px-2 py-1.5 rounded bg-zinc-900/40 border border-zinc-800/30">
                  <code className="text-[9px] text-cyan-400 font-mono truncate flex-1 mr-2">{wh.url}</code>
                  <Button size="sm" variant="ghost" onClick={() => deleteWebhook(wh.webhook_id)} className="h-5 px-1 text-zinc-600 hover:text-red-400"><Trash2 className="w-2.5 h-2.5" /></Button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Schedules */}
        <div className="mb-4">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-xs font-semibold text-zinc-400 flex items-center gap-1"><Clock className="w-3 h-3" /> Schedules</h3>
            <Button size="sm" onClick={() => createSchedule(selectedDep.deployment_id)} className="h-6 px-2 text-[10px] bg-zinc-800 text-zinc-300"><Plus className="w-3 h-3 mr-1" />Add</Button>
          </div>
          {schedules.length === 0 ? (
            <p className="text-[10px] text-zinc-600">No schedules configured</p>
          ) : (
            <div className="space-y-1">
              {schedules.map(s => (
                <div key={s.schedule_id} className="flex items-center justify-between px-2 py-1.5 rounded bg-zinc-900/40 border border-zinc-800/30">
                  <span className="text-[10px] text-zinc-300">{s.cron_expression || s.interval}</span>
                  <Button size="sm" variant="ghost" onClick={() => deleteSchedule(s.schedule_id)} className="h-5 px-1 text-zinc-600 hover:text-red-400"><Trash2 className="w-2.5 h-2.5" /></Button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Runs */}
        <div className="mb-4">
          <h3 className="text-xs font-semibold text-zinc-400 mb-2">Recent Runs</h3>
          {runs.length === 0 ? (
            <p className="text-[10px] text-zinc-600">No runs yet</p>
          ) : (
            <div className="space-y-1.5">
              {runs.map(run => (
                <div key={run.run_id} className="p-2.5 rounded-lg border border-zinc-800/30 bg-zinc-900/30">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-mono text-zinc-500">{run.run_id}</span>
                    <Badge className={`text-[8px] ${run.status === "completed" ? "bg-emerald-500/20 text-emerald-400" : run.status === "failed" ? "bg-red-500/20 text-red-400" : "bg-zinc-700 text-zinc-400"}`}>{run.status}</Badge>
                  </div>
                  <div className="flex items-center gap-3 text-[9px] text-zinc-500">
                    <span>{run.trigger_type}</span>
                    {run.duration_ms && <span>{(run.duration_ms / 1000).toFixed(1)}s</span>}
                    {run.cost_usd && <span>${run.cost_usd}</span>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Actions */}
        {actions.length > 0 && (
          <div className="mb-4">
            <h3 className="text-xs font-semibold text-zinc-400 mb-2">Actions Log</h3>
            <div className="space-y-1">
              {actions.map((act, i) => (
                <div key={act.action_id || `act-${i}`} className="p-2 rounded border border-zinc-800/20 bg-zinc-950/40 text-[10px]">
                  <span className="text-zinc-500">#{act.sequence}</span> <span className="text-zinc-300">{act.action_type}</span>
                  {act.agent_key && <span className="text-zinc-600 ml-1">({act.agent_key})</span>}
                </div>
              ))}
            </div>
          </div>
        )}
      </ScrollArea>
    </>
  );
}
