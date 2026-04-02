import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { handleSilent } from "@/lib/errorHandler";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Clock, Plus, Trash2, Loader2, Play, Pause, RefreshCw, Calendar
} from "lucide-react";
import { FeatureHelp, FEATURE_HELP } from "@/components/FeatureHelp";

export default function OrchSchedulePanel({ workspaceId }) {
  const [orchestrations, setOrchestrations] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [orchId, setOrchId] = useState("");
  const [inputText, setInputText] = useState("");
  const [interval, setInterval] = useState("60");
  const [creating, setCreating] = useState(false);

  const fetchOrchestrations = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/orchestrations`);
      setOrchestrations(res.data.orchestrations || []);
    } catch (err) { handleSilent(err, "OS:orchs"); }
  }, [workspaceId]);

  const fetchSchedules = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/orchestration-schedules`);
      setSchedules(res.data.schedules || []);
    } catch (err) { handleSilent(err, "OS:list"); }
    setLoading(false);
  }, [workspaceId]);

  useEffect(() => { fetchOrchestrations(); fetchSchedules(); }, [fetchOrchestrations, fetchSchedules]);

  const createSchedule = async () => {
    if (!orchId || !inputText.trim()) return toast.error("Select orchestration and enter input text");
    setCreating(true);
    try {
      await api.post(`/workspaces/${workspaceId}/orchestration-schedules`, {
        orchestration_id: orchId, input_text: inputText, interval_minutes: parseInt(interval),
      });
      toast.success("Schedule created");
      setShowCreate(false); setOrchId(""); setInputText("");
      fetchSchedules();
    } catch (err) { toast.error("Failed"); handleSilent(err, "OS:create"); }
    setCreating(false);
  };

  const toggleSchedule = async (sched) => {
    try {
      await api.put(`/workspaces/${workspaceId}/orchestration-schedules/${sched.schedule_id}`, { enabled: !sched.enabled });
      toast.success(sched.enabled ? "Paused" : "Resumed");
      fetchSchedules();
    } catch (err) { toast.error("Update failed"); }
  };

  const deleteSchedule = async (schedId) => {
    try {
      await api.delete(`/workspaces/${workspaceId}/orchestration-schedules/${schedId}`);
      toast.success("Deleted");
      fetchSchedules();
    } catch (err) { toast.error("Delete failed"); }
  };

  const formatInterval = (mins) => {
    if (mins < 60) return `${mins}m`;
    if (mins < 1440) return `${Math.round(mins/60)}h`;
    return `${Math.round(mins/1440)}d`;
  };

  if (loading) return <div className="flex-1 flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-zinc-500" /></div>;

  return (
    <div className="flex-1 overflow-y-auto p-6" data-testid="orch-schedule-panel">
      <div className="max-w-5xl mx-auto space-y-6">
        <FeatureHelp featureId="orch-schedules" {...FEATURE_HELP["orch-schedules"]} />
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100">Orchestration Schedules</h2>
            <p className="text-sm text-zinc-500 mt-1">Run orchestrations automatically on a recurring interval</p>
          </div>
          <Button size="sm" onClick={() => setShowCreate(!showCreate)} className="bg-indigo-600 hover:bg-indigo-700" data-testid="os-create-btn">
            <Plus className="w-4 h-4 mr-1" /> New Schedule
          </Button>
        </div>

        {showCreate && (
          <Card className="bg-zinc-900 border-zinc-800" data-testid="os-create-form">
            <CardContent className="py-4 space-y-3">
              <Select value={orchId} onValueChange={setOrchId}>
                <SelectTrigger className="bg-zinc-800 border-zinc-700" data-testid="os-orch-select"><SelectValue placeholder="Select orchestration" /></SelectTrigger>
                <SelectContent>{orchestrations.map(o => <SelectItem key={o.orchestration_id} value={o.orchestration_id}>{o.name}</SelectItem>)}</SelectContent>
              </Select>
              <Input placeholder="Input text for each run" value={inputText} onChange={e => setInputText(e.target.value)} className="bg-zinc-800 border-zinc-700" data-testid="os-input-text" />
              <div className="flex gap-3 items-center">
                <span className="text-sm text-zinc-400">Run every</span>
                <Select value={interval} onValueChange={setInterval}>
                  <SelectTrigger className="w-32 bg-zinc-800 border-zinc-700"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="5">5 min</SelectItem>
                    <SelectItem value="15">15 min</SelectItem>
                    <SelectItem value="30">30 min</SelectItem>
                    <SelectItem value="60">1 hour</SelectItem>
                    <SelectItem value="360">6 hours</SelectItem>
                    <SelectItem value="720">12 hours</SelectItem>
                    <SelectItem value="1440">Daily</SelectItem>
                    <SelectItem value="10080">Weekly</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button onClick={createSchedule} disabled={creating} className="bg-indigo-600 hover:bg-indigo-700 w-full" data-testid="os-save-btn">
                {creating ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Calendar className="w-4 h-4 mr-2" />}
                Create Schedule
              </Button>
            </CardContent>
          </Card>
        )}

        {schedules.length === 0 ? (
          <Card className="bg-zinc-900 border-zinc-800"><CardContent className="py-12 text-center text-zinc-500">No scheduled orchestrations. Create one to automate agent workflows.</CardContent></Card>
        ) : schedules.map(sched => (
          <Card key={sched.schedule_id} className="bg-zinc-900/50 border-zinc-800" data-testid={`os-card-${sched.schedule_id}`}>
            <CardContent className="py-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${sched.enabled ? "bg-emerald-600/15" : "bg-zinc-800"}`}>
                  {sched.enabled ? <Play className="w-5 h-5 text-emerald-400" /> : <Pause className="w-5 h-5 text-zinc-500" />}
                </div>
                <div>
                  <div className="text-sm font-medium text-zinc-200">{sched.orchestration_name}</div>
                  <div className="text-xs text-zinc-500">Every {formatInterval(sched.interval_minutes)} &middot; {sched.run_count} runs &middot; Input: "{sched.input_text?.slice(0, 40)}..."</div>
                  {sched.last_run_at && <div className="text-xs text-zinc-600">Last run: {new Date(sched.last_run_at).toLocaleString()}</div>}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className={`text-xs ${sched.enabled ? "border-emerald-800 text-emerald-400" : "border-zinc-700 text-zinc-500"}`}>
                  {sched.enabled ? "Active" : "Paused"}
                </Badge>
                <Switch checked={sched.enabled} onCheckedChange={() => toggleSchedule(sched)} className="scale-75" />
                <Button variant="ghost" size="sm" onClick={() => deleteSchedule(sched.schedule_id)} className="text-zinc-500 hover:text-red-400 h-7"><Trash2 className="w-3.5 h-3.5" /></Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
