import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { handleSilent } from "@/lib/errorHandler";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Bell, AlertTriangle, CheckCircle, DollarSign, X } from "lucide-react";

export default function CostAlerts({ workspaceId }) {
  const [alerts, setAlerts] = useState([]);
  const [thresholds, setThresholds] = useState([50, 80, 90, 100]);
  const [editThresholds, setEditThresholds] = useState(false);
  const [newThreshold, setNewThreshold] = useState("");

  const fetchAlerts = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/cost-alerts`);
      setAlerts(res.data?.alerts || []);
    } catch (err) { handleSilent(err, "CostAlerts:fetch"); }
  }, [workspaceId]);

  useEffect(() => { fetchAlerts(); }, [fetchAlerts]);

  const acknowledgeAll = async () => {
    try {
      await api.put(`/workspaces/${workspaceId}/cost-alerts/acknowledge`);
      toast.success("Alerts acknowledged");
      fetchAlerts();
    } catch { toast.error("Failed"); }
  };

  const saveThresholds = async () => {
    try {
      await api.put(`/workspaces/${workspaceId}/budget/thresholds`, { thresholds });
      toast.success("Thresholds updated");
      setEditThresholds(false);
    } catch { toast.error("Failed"); }
  };

  const addThreshold = () => {
    const val = parseInt(newThreshold);
    if (val > 0 && val <= 100 && !thresholds.includes(val)) {
      setThresholds(prev => [...prev, val].sort((a, b) => a - b));
      setNewThreshold("");
    }
  };

  const unacked = alerts.filter(a => !a.acknowledged).length;
  const sevColors = { critical: "text-red-400 bg-red-500/10", warning: "text-amber-400 bg-amber-500/10", info: "text-cyan-400 bg-cyan-500/10" };

  return (
    <div className="space-y-4" data-testid="cost-alerts">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bell className="w-4 h-4 text-amber-400" />
          <span className="text-sm font-medium text-zinc-200">Cost Alerts</span>
          {unacked > 0 && <Badge className="bg-red-500 text-white text-[9px] px-1.5">{unacked}</Badge>}
        </div>
        <div className="flex gap-2">
          {unacked > 0 && (
            <Button size="sm" variant="ghost" onClick={acknowledgeAll} className="h-7 text-xs text-zinc-400 gap-1" data-testid="acknowledge-all-btn">
              <CheckCircle className="w-3 h-3" /> Acknowledge All
            </Button>
          )}
          <Button size="sm" variant="ghost" onClick={() => setEditThresholds(!editThresholds)} className="h-7 text-xs text-zinc-500" data-testid="edit-thresholds-btn">
            Thresholds
          </Button>
        </div>
      </div>

      {editThresholds && (
        <div className="bg-zinc-800/30 rounded-lg p-3">
          <p className="text-[10px] text-zinc-500 mb-2">Alert when budget reaches these percentages:</p>
          <div className="flex gap-1.5 flex-wrap mb-2">
            {thresholds.map(t => (
              <Badge key={t} className="bg-zinc-700 text-zinc-300 text-[10px] gap-1">
                {t}%
                <button onClick={() => setThresholds(prev => prev.filter(x => x !== t))}><X className="w-2.5 h-2.5" /></button>
              </Badge>
            ))}
          </div>
          <div className="flex gap-2">
            <Input value={newThreshold} onChange={e => setNewThreshold(e.target.value)} placeholder="Add %" type="number" min="1" max="100" className="bg-zinc-950 border-zinc-800 h-7 text-xs w-20" onKeyDown={e => e.key === "Enter" && addThreshold()} data-testid="threshold-input" />
            <Button size="sm" onClick={saveThresholds} className="h-7 text-xs bg-cyan-500 text-white" data-testid="save-thresholds-btn">Save</Button>
          </div>
        </div>
      )}

      {alerts.length === 0 ? (
        <p className="text-xs text-zinc-600 text-center py-4">No cost alerts. Alerts will appear when spending exceeds configured thresholds.</p>
      ) : (
        <div className="space-y-1.5">
          {alerts.map((a, i) => (
            <div key={i} className={`flex items-start gap-2 p-3 rounded-lg border ${a.acknowledged ? "border-zinc-800/20 opacity-50" : "border-zinc-800/40"}`} data-testid={`alert-${i}`}>
              <AlertTriangle className={`w-3.5 h-3.5 flex-shrink-0 mt-0.5 ${a.severity === "critical" ? "text-red-400" : a.severity === "warning" ? "text-amber-400" : "text-cyan-400"}`} />
              <div className="flex-1">
                <p className="text-xs text-zinc-300">{a.message}</p>
                <div className="flex gap-2 mt-1 text-[9px] text-zinc-600">
                  <Badge variant="secondary" className={`${sevColors[a.severity] || ""} text-[8px]`}>{a.severity}</Badge>
                  <span>{new Date(a.created_at).toLocaleDateString()}</span>
                  {a.acknowledged && <span className="text-emerald-600">acknowledged</span>}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
