import { useState, useEffect, useCallback } from "react";
import { useConfirm } from "@/components/ConfirmDialog";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Clock, Plus, Play, Pause, Trash2, RotateCw, History, Zap, ClipboardList, Target, MessageSquare } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/App";

const ACTION_ICONS = {
  project_review: <ClipboardList className="w-4 h-4" />,
  task_triage: <Target className="w-4 h-4" />,
  standup_summary: <MessageSquare className="w-4 h-4" />,
  custom: <Zap className="w-4 h-4" />,
};

const ACTION_COLORS = {
  project_review: "text-blue-400 bg-blue-500/10 border-blue-500/20",
  task_triage: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  standup_summary: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  custom: "text-purple-400 bg-purple-500/10 border-purple-500/20",
};

const STATUS_STYLES = {
  completed: "text-emerald-400",
  failed: "text-red-400",
  running: "text-amber-400",
};

export default function SchedulePanel({ workspaceId, channels }) {
  const { confirm: confirmAction, ConfirmDialog: ConfirmDlg } = useConfirm();
  const [schedules, setSchedules] = useState([]);
  const [actionTypes, setActionTypes] = useState([]);
  const [intervals, setIntervals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyData, setHistoryData] = useState([]);
  const [historyScheduleId, setHistoryScheduleId] = useState(null);

  // Form state
  const [formChannelId, setFormChannelId] = useState("");
  const [formAgentKey, setFormAgentKey] = useState("");
  const [formActionType, setFormActionType] = useState("project_review");
  const [formInterval, setFormInterval] = useState(1440);
  const [formCustomPrompt, setFormCustomPrompt] = useState("");
  const [channelAgents, setChannelAgents] = useState([]);

  const fetchSchedules = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/schedules`);
      setSchedules(res.data || []);
    } catch (err) { handleError(err, "SchedulePanel:op1"); } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  const fetchActionTypes = useCallback(async () => {
    try {
      const res = await api.get("/schedules/action-types");
      setActionTypes(res.data.action_types || []);
      setIntervals(res.data.valid_intervals || []);
    } catch (err) { handleSilent(err, "SchedulePanel:op1"); }
  }, []);

  useEffect(() => {
    fetchSchedules();
    fetchActionTypes();
  }, [fetchSchedules, fetchActionTypes]);

  // When channel selection changes, load its agents
  useEffect(() => {
    if (!formChannelId) {
      setChannelAgents([]);
      return;
    }
    api.get(`/channels/${formChannelId}/mentionable`)
      .then((r) => {
        const agents = (r.data?.agents || []).filter((a) => a.type !== "special");
        setChannelAgents(agents);
        if (agents.length > 0 && !formAgentKey) {
          setFormAgentKey(agents[0].key);
        }
      })
      .catch(() => setChannelAgents([]));
  }, [formChannelId]);

  const handleCreate = async () => {
    if (!formChannelId || !formAgentKey) {
      toast.error("Select a channel and agent");
      return;
    }
    try {
      await api.post(`/workspaces/${workspaceId}/schedules`, {
        channel_id: formChannelId,
        agent_key: formAgentKey,
        action_type: formActionType,
        custom_prompt: formActionType === "custom" ? formCustomPrompt : null,
        interval_minutes: formInterval,
        enabled: true,
      });
      toast.success("Schedule created");
      setCreateOpen(false);
      resetForm();
      fetchSchedules();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to create schedule");
    }
  };

  const resetForm = () => {
    setFormChannelId("");
    setFormAgentKey("");
    setFormActionType("project_review");
    setFormInterval(1440);
    setFormCustomPrompt("");
    setChannelAgents([]);
  };

  const toggleSchedule = async (schedule) => {
    try {
      await api.put(`/schedules/${schedule.schedule_id}`, {
        enabled: !schedule.enabled,
      });
      fetchSchedules();
      toast.success(schedule.enabled ? "Schedule paused" : "Schedule resumed");
    } catch (err) { handleError(err, "SchedulePanel:op2"); }
  };

  const deleteSchedule = async (scheduleId) => {
    const _ok = await confirmAction("Delete Schedule", "Delete this scheduled action?"); if (!_ok) return;
    try {
      await api.delete(`/schedules/${scheduleId}`);
      fetchSchedules();
      toast.success("Schedule deleted");
    } catch (err) { handleError(err, "SchedulePanel:op3"); }
  };

  const triggerNow = async (scheduleId) => {
    try {
      await api.post(`/schedules/${scheduleId}/run`);
      toast.success("Schedule triggered — check the channel for results");
      fetchSchedules();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to trigger");
    }
  };

  const viewHistory = async (scheduleId) => {
    try {
      const res = await api.get(`/schedules/${scheduleId}/history`);
      setHistoryData(res.data || []);
      setHistoryScheduleId(scheduleId);
      setHistoryOpen(true);
    } catch (err) { handleError(err, "SchedulePanel:op4"); }
  };

  const formatInterval = (mins) => {
    const match = intervals.find((i) => i.minutes === mins);
    return match ? match.label : `${mins}m`;
  };

  const formatTime = (iso) => {
    if (!iso) return "Never";
    try {
      const d = new Date(iso);
      return d.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
    } catch (err) { handleSilent(err, "SchedulePanel:op5"); return iso; }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="flex gap-2">
          <div className="w-2 h-2 rounded-full bg-zinc-600 animate-bounce" style={{ animationDelay: "0ms" }} />
          <div className="w-2 h-2 rounded-full bg-zinc-600 animate-bounce" style={{ animationDelay: "150ms" }} />
          <div className="w-2 h-2 rounded-full bg-zinc-600 animate-bounce" style={{ animationDelay: "300ms" }} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-6" data-testid="schedule-panel">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100" style={{ fontFamily: "Syne, sans-serif" }}>
              Agent Schedules
            </h2>
            <p className="text-sm text-zinc-500 mt-0.5">
              Automate recurring AI actions — reviews, triages, and summaries
            </p>
          </div>

          {/* Info banner */}
          <div className="p-3 rounded-lg bg-amber-500/5 border border-amber-500/15 flex items-start gap-3 mb-4">
            <Clock className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-zinc-400 leading-relaxed">Schedules run AI agents automatically on a timer. Set up daily standups, weekly project reviews, or custom recurring tasks.</p>
          </div>

          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild>
              <Button
                className="bg-zinc-100 text-zinc-900 hover:bg-zinc-200 gap-2"
                data-testid="create-schedule-btn"
              >
                <Plus className="w-4 h-4" />
                New Schedule
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-zinc-900 border-zinc-800 max-w-md">
              <DialogHeader>
                <DialogTitle className="text-zinc-100" style={{ fontFamily: "Syne, sans-serif" }}>
                  Create Schedule
                </DialogTitle>
              </DialogHeader>
              <div className="space-y-4 mt-2">
                {/* Channel */}
                <div>
                  <label className="text-xs text-zinc-500 mb-1.5 block">Channel</label>
                  <select
                    value={formChannelId}
                    onChange={(e) => { setFormChannelId(e.target.value); setFormAgentKey(""); }}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:ring-1 focus:ring-zinc-700"
                    data-testid="schedule-channel-select"
                  >
                    <option value="">Select channel...</option>
                    {(channels || []).map((ch) => (
                      <option key={ch.channel_id} value={ch.channel_id}>
                        # {ch.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Agent */}
                <div>
                  <label className="text-xs text-zinc-500 mb-1.5 block">Agent</label>
                  <select
                    value={formAgentKey}
                    onChange={(e) => setFormAgentKey(e.target.value)}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:ring-1 focus:ring-zinc-700"
                    disabled={!formChannelId}
                    data-testid="schedule-agent-select"
                  >
                    <option value="">Select agent...</option>
                    {channelAgents.map((a) => (
                      <option key={a.key} value={a.key}>
                        {a.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Action Type */}
                <div>
                  <label className="text-xs text-zinc-500 mb-1.5 block">Action</label>
                  <div className="grid grid-cols-2 gap-2">
                    {actionTypes.map((at) => (
                      <button
                        key={at.key}
                        onClick={() => setFormActionType(at.key)}
                        className={`flex items-center gap-2 px-3 py-2.5 rounded-lg border text-left text-sm transition-all ${
                          formActionType === at.key
                            ? ACTION_COLORS[at.key] + " border-current"
                            : "text-zinc-400 bg-zinc-950 border-zinc-800 hover:border-zinc-700"
                        }`}
                        data-testid={`action-type-${at.key}`}
                      >
                        {ACTION_ICONS[at.key]}
                        <span className="truncate">{at.name}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Custom Prompt */}
                {formActionType === "custom" && (
                  <div>
                    <label className="text-xs text-zinc-500 mb-1.5 block">Custom Prompt</label>
                    <textarea
                      value={formCustomPrompt}
                      onChange={(e) => setFormCustomPrompt(e.target.value)}
                      rows={3}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:ring-1 focus:ring-zinc-700 resize-none"
                      placeholder="Describe what the agent should do..."
                      data-testid="schedule-custom-prompt"
                    />
                  </div>
                )}

                {/* Interval */}
                <div>
                  <label className="text-xs text-zinc-500 mb-1.5 block">Frequency</label>
                  <select
                    value={formInterval}
                    onChange={(e) => setFormInterval(parseInt(e.target.value))}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:ring-1 focus:ring-zinc-700"
                    data-testid="schedule-interval-select"
                  >
                    {intervals.map((iv) => (
                      <option key={iv.minutes} value={iv.minutes}>
                        {iv.label}
                      </option>
                    ))}
                  </select>
                </div>

                <Button
                  onClick={handleCreate}
                  className="w-full bg-zinc-100 text-zinc-900 hover:bg-zinc-200"
                  disabled={!formChannelId || !formAgentKey}
                  data-testid="submit-schedule-btn"
                >
                  Create Schedule
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        {/* Schedule List */}
        {schedules.length === 0 ? (
          <div className="text-center py-16" data-testid="empty-schedules">
            <div className="w-14 h-14 rounded-2xl bg-zinc-900 border border-zinc-800 flex items-center justify-center mx-auto mb-4">
              <Clock className="w-6 h-6 text-zinc-600" />
            </div>
            <h3 className="text-base font-semibold text-zinc-400 mb-1" style={{ fontFamily: "Syne, sans-serif" }}>
              No schedules yet
            </h3>
            <p className="text-sm text-zinc-600 max-w-sm mx-auto mb-4">
              Create a schedule to have AI agents automatically review projects, triage tasks, or generate summaries
            </p>
            <Button onClick={() => setCreateOpen(true)} className="bg-emerald-500 hover:bg-emerald-400 text-white font-semibold gap-2" data-testid="empty-create-schedule-btn">
              <Plus className="w-4 h-4" /> Create Schedule
            </Button>
          </div>
        ) : (
          <div className="space-y-3" data-testid="schedule-list">
            {schedules.map((s) => (
              <div
                key={s.schedule_id}
                className={`rounded-xl border p-4 transition-all ${
                  s.enabled
                    ? "bg-zinc-900/60 border-zinc-800/60"
                    : "bg-zinc-950/40 border-zinc-800/30 opacity-60"
                }`}
                data-testid={`schedule-${s.schedule_id}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className={`w-9 h-9 rounded-lg flex items-center justify-center border ${ACTION_COLORS[s.action_type] || "text-zinc-400 bg-zinc-800 border-zinc-700"}`}>
                      {ACTION_ICONS[s.action_type] || <Zap className="w-4 h-4" />}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-zinc-200 truncate">
                          {s.action_type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                        </span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-500 border border-zinc-700/40 font-mono">
                          {s.agent_name}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-[11px] text-zinc-500">
                        <span># {s.channel_name}</span>
                        <span>{formatInterval(s.interval_minutes)}</span>
                        {s.last_status && (
                          <span className={STATUS_STYLES[s.last_status] || "text-zinc-500"}>
                            {s.last_status}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 mt-0.5 text-[10px] text-zinc-600 font-mono">
                        <span>Last: {formatTime(s.last_run_at)}</span>
                        <span>Next: {formatTime(s.next_run_at)}</span>
                        <span>{s.run_count} runs</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <button
                      onClick={() => triggerNow(s.schedule_id)}
                      className="p-1.5 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
                      title="Run now"
                      data-testid={`trigger-schedule-${s.schedule_id}`}
                    >
                      <Play className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => toggleSchedule(s)}
                      className="p-1.5 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
                      title={s.enabled ? "Pause" : "Resume"}
                      data-testid={`toggle-schedule-${s.schedule_id}`}
                    >
                      {s.enabled ? <Pause className="w-3.5 h-3.5" /> : <RotateCw className="w-3.5 h-3.5" />}
                    </button>
                    <button
                      onClick={() => viewHistory(s.schedule_id)}
                      className="p-1.5 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
                      title="History"
                      data-testid={`history-schedule-${s.schedule_id}`}
                    >
                      <History className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => deleteSchedule(s.schedule_id)}
                      className="p-1.5 rounded-md text-zinc-500 hover:text-red-400 hover:bg-zinc-800 transition-colors"
                      title="Delete"
                      data-testid={`delete-schedule-${s.schedule_id}`}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* History Dialog */}
        <Dialog open={historyOpen} onOpenChange={setHistoryOpen}>
          <DialogContent className="bg-zinc-900 border-zinc-800 max-w-md">
            <DialogHeader>
              <DialogTitle className="text-zinc-100" style={{ fontFamily: "Syne, sans-serif" }}>
                Run History
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-2 mt-2 max-h-72 overflow-y-auto" data-testid="schedule-history">
              {historyData.length === 0 ? (
                <p className="text-sm text-zinc-500 text-center py-4">No runs yet</p>
              ) : (
                historyData.map((run) => (
                  <div
                    key={run.run_id}
                    className="flex items-center justify-between px-3 py-2.5 rounded-lg bg-zinc-950 border border-zinc-800/40"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className={`text-xs font-medium ${STATUS_STYLES[run.status] || "text-zinc-400"}`}>
                          {run.status}
                        </span>
                        <span className="text-[10px] text-zinc-600 font-mono">
                          {run.action_type}
                        </span>
                      </div>
                      <span className="text-[10px] text-zinc-600 font-mono">
                        {formatTime(run.started_at)}
                      </span>
                    </div>
                    <div className="text-right">
                      <span className="text-[10px] text-zinc-500">{run.tool_calls_count} tools</span>
                      {run.error && (
                        <p className="text-[10px] text-red-400 truncate max-w-[180px]" title={run.error}>
                          {run.error}
                        </p>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </DialogContent>
        </Dialog>
        <ConfirmDlg />
      </div>
    </div>
    );
}
