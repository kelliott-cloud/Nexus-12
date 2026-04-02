import { useState, useEffect, useRef, useCallback } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { api, API } from "@/App";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { X, CheckCircle2, XCircle, Loader2, Clock, Zap, DollarSign, AlertTriangle, Pause, FileText } from "lucide-react";

const EVENT_ICONS = {
  "run:started": Zap,
  "run:completed": CheckCircle2,
  "run:failed": XCircle,
  "run:paused": Pause,
  "run:resumed": Zap,
  "run:cancelled": XCircle,
  "node:started": Loader2,
  "node:completed": CheckCircle2,
  "node:failed": XCircle,
  "node:retrying": AlertTriangle,
};

const EVENT_COLORS = {
  "run:started": "text-blue-400",
  "run:completed": "text-emerald-400",
  "run:failed": "text-red-400",
  "run:paused": "text-amber-400",
  "run:resumed": "text-blue-400",
  "run:cancelled": "text-zinc-400",
  "node:started": "text-blue-400 animate-spin",
  "node:completed": "text-emerald-400",
  "node:failed": "text-red-400",
  "node:retrying": "text-amber-400",
};

export default function RunMonitor({ runId, workflowId, workspaceId, onClose }) {
  const [events, setEvents] = useState([]);
  const [runData, setRunData] = useState(null);
  const [status, setStatus] = useState("connecting");
  const eventSourceRef = useRef(null);
  const eventsEndRef = useRef(null);

  // Fetch initial run data
  useEffect(() => {
    const fetchRun = async () => {
      try {
        const res = await api.get(`/workflow-runs/${runId}`);
        setRunData(res.data);
        if (["completed", "failed", "cancelled"].includes(res.data.status)) {
          setStatus(res.data.status);
        }
      } catch (err) {
        console.error("Failed to fetch run:", err);
      }
    };
    fetchRun();
  }, [runId]);

  // SSE streaming
  useEffect(() => {
    const evtSource = new EventSource(`${API}/workflow-runs/${runId}/stream`, { withCredentials: true });
    eventSourceRef.current = evtSource;
    setStatus("connected");

    evtSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.event === "heartbeat") return;

        setEvents((prev) => [...prev, { ...data, timestamp: new Date().toISOString() }]);

        if (data.status) setStatus(data.status);
        if (data.event === "run:completed" || data.event === "run:failed" || data.event === "run:cancelled") {
          evtSource.close();
          // Refresh run data for final totals
          api.get(`/workflow-runs/${runId}`).then((res) => setRunData(res.data)).catch(() => {});
        }
      } catch (e) {
        console.error("SSE parse error:", e);
      }
    };

    evtSource.onerror = () => {
      setStatus("disconnected");
      evtSource.close();
    };

    return () => {
      evtSource.close();
    };
  }, [runId]);

  // Auto scroll
  useEffect(() => {
    eventsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  const cancelRun = async () => {
    try {
      await api.post(`/workflow-runs/${runId}/cancel`);
      setStatus("cancelled");
    } catch (err) {
      // ignore
    }
  };

  const isRunning = !["completed", "failed", "cancelled", "disconnected"].includes(status);

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center" data-testid="run-monitor">
      <div className="bg-zinc-900 border border-zinc-800 rounded-lg w-full max-w-2xl max-h-[80vh] flex flex-col mx-4">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-zinc-800">
          <div className="flex items-center gap-3">
            <h3 className="text-sm font-medium text-zinc-100">Run Monitor</h3>
            <span className={`text-[10px] px-2 py-0.5 rounded uppercase font-medium ${
              status === "completed" ? "bg-emerald-600/20 text-emerald-400" :
              status === "failed" ? "bg-red-600/20 text-red-400" :
              status === "running" || status === "connected" ? "bg-blue-600/20 text-blue-400" :
              status === "paused_at_gate" ? "bg-amber-600/20 text-amber-400" :
              "bg-zinc-700/50 text-zinc-400"
            }`} data-testid="run-status">
              {status === "connected" ? "running" : status}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {isRunning && (
              <Button variant="outline" size="sm" onClick={cancelRun} className="border-zinc-700 text-red-400 hover:bg-zinc-800 text-xs" data-testid="cancel-run-btn">
                <XCircle className="w-3 h-3 mr-1" />
                Cancel
              </Button>
            )}
            <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Stats bar */}
        {runData && (
          <div className="flex items-center gap-6 px-4 py-2 border-b border-zinc-800/60 text-xs text-zinc-400">
            <span className="flex items-center gap-1"><Zap className="w-3 h-3" /> {runData.total_tokens || 0} tokens</span>
            <span className="flex items-center gap-1"><DollarSign className="w-3 h-3" /> ${(runData.total_cost_usd || 0).toFixed(4)}</span>
            <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {((runData.total_duration_ms || 0) / 1000).toFixed(1)}s</span>
          </div>
        )}

        {/* Events log */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2 min-h-[200px]" data-testid="run-events">
          {events.length === 0 && (
            <div className="flex items-center justify-center py-10 text-zinc-600">
              <Loader2 className="w-5 h-5 animate-spin mr-2" />
              Waiting for events...
            </div>
          )}
          {events.map((evt, idx) => {
            const Icon = EVENT_ICONS[evt.event] || Zap;
            const colorClass = EVENT_COLORS[evt.event] || "text-zinc-400";
            return (
              <div key={idx} className="flex items-start gap-3 text-sm" data-testid={`run-event-${idx}`}>
                <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${colorClass}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-zinc-300">
                      {evt.label || evt.event}
                    </span>
                    {evt.model && <span className="text-[10px] text-zinc-600">{evt.model}</span>}
                    {evt.attempt && evt.attempt > 1 && (
                      <span className="text-[10px] text-amber-500">attempt {evt.attempt}</span>
                    )}
                  </div>
                  {evt.output_summary && (
                    <p className="text-xs text-zinc-500 mt-0.5 truncate">{evt.output_summary}</p>
                  )}
                  {evt.error_message && (
                    <p className="text-xs text-red-400 mt-0.5">{evt.error_message}</p>
                  )}
                  {evt.tokens > 0 && (
                    <p className="text-[10px] text-zinc-600 mt-0.5">
                      {evt.tokens} tokens | ${evt.cost?.toFixed(4)} | {(evt.duration_ms / 1000).toFixed(1)}s
                    </p>
                  )}
                </div>
                <span className="text-[10px] text-zinc-700 shrink-0">
                  {new Date(evt.timestamp).toLocaleTimeString()}
                </span>
              </div>
            );
          })}
          <div ref={eventsEndRef} />
        </div>

        {/* Final output */}
        {runData?.final_output && status === "completed" && (
          <div className="border-t border-zinc-800 p-4">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-xs font-medium text-zinc-400">Final Output</h4>
              {workspaceId && (
                <Button variant="outline" size="sm" className="text-xs border-zinc-700 text-zinc-400 hover:text-zinc-200 h-7" data-testid="save-as-artifact-btn"
                  onClick={async () => {
                    try {
                      await api.post(`/workspaces/${workspaceId}/artifacts`, {
                        name: `Run ${runId} Output`,
                        content: JSON.stringify(runData.final_output, null, 2),
                        content_type: "json",
                        workflow_id: workflowId,
                        run_id: runId,
                        tags: ["workflow-output"],
                      });
                      toast.success("Saved as artifact");
                    } catch (err) { toast.error("Failed to save artifact"); }
                  }}
                >
                  <FileText className="w-3 h-3 mr-1" />
                  Save as Artifact
                </Button>
              )}
            </div>
            <pre className="bg-zinc-800/50 rounded-md p-3 text-xs text-zinc-300 overflow-auto max-h-[200px]" data-testid="run-final-output">
              {JSON.stringify(runData.final_output, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
