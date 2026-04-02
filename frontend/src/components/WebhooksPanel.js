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
  Webhook, Plus, Trash2, Loader2, CheckCircle2, XCircle, RefreshCw,
  Send, Zap, Globe, Clock, ChevronDown, ChevronRight, Eye
} from "lucide-react";
import { FeatureHelp, FEATURE_HELP } from "@/components/FeatureHelp";

const EVENT_CATEGORIES = {
  "Messages": ["message.created"],
  "Collaboration": ["collaboration.started", "collaboration.completed"],
  "Tasks": ["task.created", "task.updated", "task.completed"],
  "Workflows": ["workflow.run.started", "workflow.run.completed", "workflow.run.failed"],
  "Other": ["handoff.created", "schedule.executed", "artifact.created", "artifact.updated", "member.joined", "member.removed", "cost.alert.triggered"],
};

export default function WebhooksPanel({ workspaceId }) {
  const [webhooks, setWebhooks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [selectedHook, setSelectedHook] = useState(null);
  const [deliveries, setDeliveries] = useState([]);

  // Create form
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [secret, setSecret] = useState("");
  const [selectedEvents, setSelectedEvents] = useState([]);
  const [creating, setCreating] = useState(false);

  // Testing
  const [testing, setTesting] = useState(null);

  const fetchWebhooks = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/webhooks`);
      setWebhooks(Array.isArray(res.data) ? res.data : res.data.webhooks || []);
    } catch (err) { handleSilent(err, "WH:list"); }
    setLoading(false);
  }, [workspaceId]);

  useEffect(() => { fetchWebhooks(); }, [fetchWebhooks]);

  const createWebhook = async () => {
    if (!url.trim()) return toast.error("URL is required");
    if (selectedEvents.length === 0) return toast.error("Select at least one event");
    setCreating(true);
    try {
      await api.post(`/workspaces/${workspaceId}/webhooks`, {
        url, name: name || url.slice(0, 40), secret, events: selectedEvents,
      });
      toast.success("Webhook created");
      setShowCreate(false); setUrl(""); setName(""); setSecret(""); setSelectedEvents([]);
      fetchWebhooks();
    } catch (err) { toast.error(err?.response?.data?.detail || "Failed to create webhook"); }
    setCreating(false);
  };

  const deleteWebhook = async (hookId) => {
    try {
      await api.delete(`/webhooks/${hookId}`);
      toast.success("Webhook deleted");
      fetchWebhooks();
      if (selectedHook?.webhook_id === hookId) setSelectedHook(null);
    } catch (err) { toast.error("Delete failed"); }
  };

  const toggleWebhook = async (hook) => {
    try {
      await api.put(`/webhooks/${hook.webhook_id}`, { enabled: !hook.enabled });
      toast.success(hook.enabled ? "Webhook disabled" : "Webhook enabled");
      fetchWebhooks();
    } catch (err) { toast.error("Update failed"); }
  };

  const testWebhook = async (hookId) => {
    setTesting(hookId);
    try {
      const res = await api.post(`/webhooks/${hookId}/test`);
      if (res.data.success) toast.success(`Test delivered! Status: ${res.data.status_code}`);
      else toast.error(`Test failed. Status: ${res.data.status_code}`);
    } catch (err) { toast.error("Test delivery failed"); }
    setTesting(null);
  };

  const fetchDeliveries = async (hookId) => {
    try {
      const res = await api.get(`/webhooks/${hookId}/deliveries`);
      setDeliveries(Array.isArray(res.data) ? res.data : res.data.deliveries || []);
    } catch (err) { handleSilent(err, "WH:deliveries"); }
  };

  const selectHook = (hook) => {
    setSelectedHook(hook);
    fetchDeliveries(hook.webhook_id);
  };

  const toggleEvent = (event) => {
    setSelectedEvents(prev => prev.includes(event) ? prev.filter(e => e !== event) : [...prev, event]);
  };

  const toggleCategory = (events) => {
    const allSelected = events.every(e => selectedEvents.includes(e));
    if (allSelected) setSelectedEvents(prev => prev.filter(e => !events.includes(e)));
    else setSelectedEvents(prev => [...new Set([...prev, ...events])]);
  };

  if (loading) return <div className="flex-1 flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-zinc-500" /></div>;

  return (
    <div className="flex-1 overflow-y-auto p-6" data-testid="webhooks-panel">
      <div className="max-w-5xl mx-auto space-y-6">
        <FeatureHelp featureId="webhooks" {...FEATURE_HELP["webhooks"]} />
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100">Webhook Integrations</h2>
            <p className="text-sm text-zinc-500 mt-1">Send real-time event notifications to external systems</p>
          </div>
          <Button size="sm" onClick={() => setShowCreate(!showCreate)} className="bg-indigo-600 hover:bg-indigo-700" data-testid="wh-create-btn">
            <Plus className="w-4 h-4 mr-1" /> New Webhook
          </Button>
        </div>

        {showCreate && (
          <Card className="bg-zinc-900 border-zinc-800" data-testid="wh-create-form">
            <CardHeader><CardTitle className="text-sm text-zinc-100">Create Webhook</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <Input placeholder="Webhook URL (https://...)" value={url} onChange={e => setUrl(e.target.value)} className="bg-zinc-800 border-zinc-700" data-testid="wh-url-input" />
              <div className="grid grid-cols-2 gap-3">
                <Input placeholder="Name (optional)" value={name} onChange={e => setName(e.target.value)} className="bg-zinc-800 border-zinc-700" data-testid="wh-name-input" />
                <Input placeholder="Secret (optional)" value={secret} onChange={e => setSecret(e.target.value)} className="bg-zinc-800 border-zinc-700" data-testid="wh-secret-input" />
              </div>

              <div className="space-y-3">
                <div className="text-xs text-zinc-400 font-medium">Subscribe to Events</div>
                {Object.entries(EVENT_CATEGORIES).map(([category, events]) => (
                  <div key={category} className="space-y-1">
                    <button onClick={() => toggleCategory(events)} className="text-xs font-medium text-zinc-300 hover:text-zinc-100 flex items-center gap-1">
                      <ChevronRight className="w-3 h-3" /> {category}
                      <span className="text-zinc-600">({events.filter(e => selectedEvents.includes(e)).length}/{events.length})</span>
                    </button>
                    <div className="flex flex-wrap gap-1.5 ml-4">
                      {events.map(event => (
                        <button key={event} onClick={() => toggleEvent(event)}
                          className={`px-2 py-1 text-xs rounded border transition-colors ${selectedEvents.includes(event) ? "bg-indigo-600/20 border-indigo-600/50 text-indigo-300" : "bg-zinc-800 border-zinc-700 text-zinc-500 hover:text-zinc-300"}`}
                          data-testid={`wh-event-${event}`}>
                          {event}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              <Button onClick={createWebhook} disabled={creating || !url.trim() || selectedEvents.length === 0} className="bg-indigo-600 hover:bg-indigo-700 w-full" data-testid="wh-save-btn">
                {creating ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Webhook className="w-4 h-4 mr-2" />}
                Create Webhook ({selectedEvents.length} events)
              </Button>
            </CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-zinc-300">Registered Webhooks</h3>
            {webhooks.length === 0 ? (
              <Card className="bg-zinc-900 border-zinc-800"><CardContent className="py-8 text-center text-zinc-500 text-sm">No webhooks configured yet.</CardContent></Card>
            ) : webhooks.map(hook => (
              <Card key={hook.webhook_id} className={`bg-zinc-900/50 border-zinc-800 cursor-pointer transition-colors ${selectedHook?.webhook_id === hook.webhook_id ? "border-indigo-600/50" : "hover:border-zinc-700"}`} onClick={() => selectHook(hook)} data-testid={`wh-card-${hook.webhook_id}`}>
                <CardContent className="py-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 min-w-0">
                      <Globe className={`w-4 h-4 flex-shrink-0 ${hook.enabled ? "text-emerald-400" : "text-zinc-600"}`} />
                      <span className="text-sm font-medium text-zinc-200 truncate">{hook.name}</span>
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <Switch checked={hook.enabled} onCheckedChange={() => toggleWebhook(hook)} className="scale-75" data-testid={`wh-toggle-${hook.webhook_id}`} />
                      <Button variant="ghost" size="sm" onClick={e => { e.stopPropagation(); testWebhook(hook.webhook_id); }} disabled={testing === hook.webhook_id} className="h-7 text-xs text-zinc-400" data-testid={`wh-test-${hook.webhook_id}`}>
                        {testing === hook.webhook_id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />}
                      </Button>
                      <Button variant="ghost" size="sm" onClick={e => { e.stopPropagation(); deleteWebhook(hook.webhook_id); }} className="h-7 text-zinc-500 hover:text-red-400">
                        <Trash2 className="w-3 h-3" />
                      </Button>
                    </div>
                  </div>
                  <div className="text-xs text-zinc-500 truncate">{hook.url}</div>
                  <div className="flex flex-wrap gap-1">
                    {(hook.events || []).slice(0, 4).map(e => (
                      <Badge key={e} variant="outline" className="text-xs border-zinc-700 py-0">{e}</Badge>
                    ))}
                    {(hook.events || []).length > 4 && <Badge variant="outline" className="text-xs border-zinc-700 py-0">+{hook.events.length - 4}</Badge>}
                  </div>
                  <div className="flex items-center gap-3 text-xs text-zinc-600">
                    {hook.last_status && <span>Last status: <span className={hook.last_status >= 200 && hook.last_status < 300 ? "text-emerald-400" : "text-red-400"}>{hook.last_status}</span></span>}
                    {hook.failure_count > 0 && <span className="text-amber-400">{hook.failure_count} failures</span>}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="space-y-3">
            <h3 className="text-sm font-medium text-zinc-300">Delivery Log</h3>
            {!selectedHook ? (
              <Card className="bg-zinc-900 border-zinc-800"><CardContent className="py-8 text-center text-zinc-500 text-sm">Select a webhook to view delivery history.</CardContent></Card>
            ) : deliveries.length === 0 ? (
              <Card className="bg-zinc-900 border-zinc-800"><CardContent className="py-8 text-center text-zinc-500 text-sm">No deliveries yet for this webhook.</CardContent></Card>
            ) : deliveries.map(del => (
              <Card key={del.delivery_id} className="bg-zinc-900/30 border-zinc-800" data-testid={`wh-delivery-${del.delivery_id}`}>
                <CardContent className="py-2.5 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {del.success ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> : <XCircle className="w-3.5 h-3.5 text-red-400" />}
                    <Badge variant="outline" className="text-xs border-zinc-700 py-0">{del.event}</Badge>
                    <span className={`text-xs font-mono ${del.success ? "text-emerald-400" : "text-red-400"}`}>{del.status_code}</span>
                  </div>
                  <span className="text-xs text-zinc-600">{new Date(del.timestamp).toLocaleString()}</span>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
