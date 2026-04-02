import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { handleSilent } from "@/lib/errorHandler";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Plug, Key, Plus, Trash2, Loader2, Copy, CheckCircle2, Globe,
  ArrowUpDown, Activity, RefreshCw, Shield, MessageSquare
} from "lucide-react";

const TABS = ["connection", "mappings", "activity"];

export default function OpenClawPanel({ workspaceId }) {
  const [tab, setTab] = useState("connection");
  return (
    <div className="space-y-4" data-testid="openclaw-panel">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-orange-600/15 flex items-center justify-center"><Plug className="w-5 h-5 text-orange-400" /></div>
        <div><h3 className="text-sm font-medium text-zinc-100">OpenClaw Integration</h3><p className="text-xs text-zinc-500">Connect Nexus agents to WhatsApp, Telegram, Discord via OpenClaw gateway</p></div>
      </div>
      <div className="flex gap-1 border-b border-zinc-800 pb-0">
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)} className={`px-3 py-2 text-xs font-medium border-b-2 transition-colors capitalize ${tab === t ? "border-orange-500 text-zinc-100" : "border-transparent text-zinc-500 hover:text-zinc-300"}`} data-testid={`oc-tab-${t}`}>{t}</button>
        ))}
      </div>
      {tab === "connection" && <ConnectionTab workspaceId={workspaceId} />}
      {tab === "mappings" && <MappingsTab workspaceId={workspaceId} />}
      {tab === "activity" && <ActivityTab workspaceId={workspaceId} />}
    </div>
  );
}

function ConnectionTab({ workspaceId }) {
  const [tokens, setTokens] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newLabel, setNewLabel] = useState("OpenClaw Gateway");
  const [newToken, setNewToken] = useState(null);
  const [copied, setCopied] = useState(false);
  const [health, setHealth] = useState(null);

  useEffect(() => {
    api.get("/openclaw/tokens").then(r => setTokens(r.data.tokens || [])).catch(() => {});
    api.get("/openclaw/health").then(r => setHealth(r.data)).catch(() => {});
    setLoading(false);
  }, []);

  const createToken = async () => {
    try {
      const res = await api.post("/openclaw/tokens", { workspace_id: workspaceId, label: newLabel });
      setNewToken(res.data);
      setNewLabel("OpenClaw Gateway");
      api.get("/openclaw/tokens").then(r => setTokens(r.data.tokens || []));
    } catch (err) { toast.error("Failed to create token"); }
  };

  const revokeToken = async (tokenId) => {
    try { await api.delete(`/openclaw/tokens/${tokenId}`); toast.success("Token revoked"); api.get("/openclaw/tokens").then(r => setTokens(r.data.tokens || [])); } catch (err) { toast.error("Revoke failed"); }
  };

  const copyToken = () => {
    if (newToken?.token) { navigator.clipboard.writeText(newToken.token); setCopied(true); setTimeout(() => setCopied(false), 2000); }
  };

  return (
    <div className="space-y-4" data-testid="oc-connection">
      {health && (
        <div className="flex items-center gap-3 text-xs text-zinc-400">
          <Badge className={`text-[9px] ${health.status === "ok" ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"}`}>{health.status}</Badge>
          <span>v{health.version}</span>
          <span>{health.connected_workspaces} workspace(s)</span>
          <span>{health.active_sessions} active sessions</span>
        </div>
      )}

      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader><CardTitle className="text-sm text-zinc-100">API Tokens</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Input value={newLabel} onChange={e => setNewLabel(e.target.value)} placeholder="Token label" className="bg-zinc-800 border-zinc-700 flex-1" />
            <Button onClick={createToken} className="bg-orange-600 hover:bg-orange-700" data-testid="oc-create-token"><Key className="w-3.5 h-3.5 mr-1" /> Generate</Button>
          </div>
          {newToken && (
            <div className="p-3 bg-orange-900/10 border border-orange-800/30 rounded-lg space-y-2">
              <p className="text-xs text-orange-400 font-medium">Token created — copy it now (shown only once):</p>
              <div className="flex gap-2">
                <code className="text-xs bg-zinc-800 text-zinc-200 px-2 py-1 rounded flex-1 font-mono break-all">{newToken.token}</code>
                <Button size="sm" variant="ghost" onClick={copyToken} className="h-7">{copied ? <CheckCircle2 className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}</Button>
              </div>
              <Button size="sm" variant="ghost" onClick={() => setNewToken(null)} className="text-xs text-zinc-500">Dismiss</Button>
            </div>
          )}
          {tokens.map(t => (
            <div key={t.token_id} className="flex items-center justify-between py-2 border-b border-zinc-800/30 last:border-0">
              <div className="flex items-center gap-2 text-xs">
                <Key className="w-3 h-3 text-zinc-500" />
                <span className="text-zinc-300">{t.label}</span>
                <Badge className={`text-[8px] ${t.revoked ? "bg-red-500/20 text-red-400" : "bg-emerald-500/20 text-emerald-400"}`}>{t.revoked ? "revoked" : "active"}</Badge>
                {t.last_used_at && <span className="text-zinc-600">Last used: {new Date(t.last_used_at).toLocaleDateString()}</span>}
              </div>
              {!t.revoked && <Button size="sm" variant="ghost" onClick={() => revokeToken(t.token_id)} className="h-6 text-red-400"><Trash2 className="w-3 h-3" /></Button>}
            </div>
          ))}
        </CardContent>
      </Card>

      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader><CardTitle className="text-sm text-zinc-100">Setup Instructions</CardTitle></CardHeader>
        <CardContent className="space-y-2 text-xs text-zinc-400">
          <p>1. Install OpenClaw gateway and the Nexus bridge plugin</p>
          <p>2. Add your token to <code className="bg-zinc-800 px-1 rounded">~/.openclaw/openclaw.json</code>:</p>
          <pre className="bg-zinc-800 p-2 rounded text-[10px] text-zinc-300 overflow-x-auto">{`{
  "plugins": {
    "nexus-bridge": {
      "nexus_api_url": "${window.location.origin}/api",
      "nexus_api_token": "nxoc_YOUR_TOKEN_HERE",
      "workspace_id": "${workspaceId}"
    }
  }
}`}</pre>
          <p>3. Messages from WhatsApp/Telegram/Discord will route to Nexus agents</p>
        </CardContent>
      </Card>
    </div>
  );
}

function MappingsTab({ workspaceId }) {
  const [mappings, setMappings] = useState([]);
  const [agents, setAgents] = useState([]);
  const [newPattern, setNewPattern] = useState("*");
  const [newAgent, setNewAgent] = useState("auto");

  useEffect(() => {
    api.get(`/openclaw/mappings/${workspaceId}`).then(r => setMappings(r.data.mappings || [])).catch(() => {});
    api.get(`/workspaces/${workspaceId}/agents`).then(r => { const a = r.data?.agents || r.data || []; setAgents(a); }).catch(() => {});
  }, [workspaceId]);

  const createMapping = async () => {
    try {
      await api.post("/openclaw/mappings", { workspace_id: workspaceId, sender_pattern: newPattern, agent_id: newAgent, priority: mappings.length });
      toast.success("Mapping created");
      setNewPattern("*"); setNewAgent("auto");
      api.get(`/openclaw/mappings/${workspaceId}`).then(r => setMappings(r.data.mappings || []));
    } catch (err) { toast.error("Failed"); }
  };

  const deleteMapping = async (id) => {
    try { await api.delete(`/openclaw/mappings/${id}`); toast.success("Deleted"); api.get(`/openclaw/mappings/${workspaceId}`).then(r => setMappings(r.data.mappings || [])); } catch (err) { toast.error("Failed"); }
  };

  const channelIcons = { whatsapp: "🟢", telegram: "🔵", discord: "🟣", sms: "💬", "*": "🌐" };

  return (
    <div className="space-y-4" data-testid="oc-mappings">
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader><CardTitle className="text-sm text-zinc-100">Channel → Agent Mappings</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2 items-end">
            <div className="flex-1"><label className="text-[10px] text-zinc-500 mb-1 block">Sender Pattern</label><Input value={newPattern} onChange={e => setNewPattern(e.target.value)} placeholder="* or +1555... or telegram:*" className="bg-zinc-800 border-zinc-700 h-8 text-sm" /></div>
            <div className="w-40"><label className="text-[10px] text-zinc-500 mb-1 block">Route to Agent</label>
              <Select value={newAgent} onValueChange={setNewAgent}>
                <SelectTrigger className="bg-zinc-800 border-zinc-700 h-8 text-sm"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="auto">Auto-route</SelectItem>{agents.map(a => <SelectItem key={a.agent_id} value={a.agent_id}>{a.name}</SelectItem>)}{["chatgpt","claude","gemini"].map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <Button size="sm" onClick={createMapping} className="bg-orange-600 hover:bg-orange-700 h-8"><Plus className="w-3 h-3 mr-1" /> Add</Button>
          </div>
          {mappings.length === 0 ? (
            <p className="text-xs text-zinc-500 text-center py-4">No mappings. Add one to route messages to agents.</p>
          ) : mappings.map(m => (
            <div key={m.mapping_id} className="flex items-center justify-between py-2 px-3 bg-zinc-800/30 rounded border border-zinc-700/30">
              <div className="flex items-center gap-2 text-xs">
                <span>{channelIcons[m.sender_pattern] || channelIcons["*"]}</span>
                <code className="text-zinc-300 bg-zinc-800 px-1 rounded">{m.sender_pattern}</code>
                <span className="text-zinc-600">→</span>
                <Badge variant="outline" className="text-xs border-zinc-700">{m.agent_id}</Badge>
                {m.priority > 0 && <span className="text-zinc-600">P{m.priority}</span>}
              </div>
              <Button size="sm" variant="ghost" onClick={() => deleteMapping(m.mapping_id)} className="h-6 text-red-400"><Trash2 className="w-3 h-3" /></Button>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function ActivityTab({ workspaceId }) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/openclaw/activity/${workspaceId}?limit=30`).then(r => setMessages(r.data.messages || [])).catch(() => {});
    setLoading(false);
  }, [workspaceId]);

  if (loading) return <div className="flex justify-center py-8"><Loader2 className="w-5 h-5 animate-spin text-zinc-500" /></div>;

  return (
    <div className="space-y-3" data-testid="oc-activity">
      <div className="flex items-center justify-between">
        <p className="text-xs text-zinc-500">{messages.length} recent messages</p>
        <Button size="sm" variant="ghost" onClick={() => api.get(`/openclaw/activity/${workspaceId}?limit=30`).then(r => setMessages(r.data.messages || []))} className="h-7 text-xs text-zinc-400"><RefreshCw className="w-3 h-3 mr-1" /> Refresh</Button>
      </div>
      {messages.length === 0 ? (
        <p className="text-xs text-zinc-500 text-center py-8">No OpenClaw messages yet. Connect a gateway to start.</p>
      ) : messages.map(msg => (
        <div key={msg.message_id} className={`p-2 rounded border ${msg.direction === "inbound" ? "border-zinc-800 bg-zinc-900/30" : "border-orange-800/20 bg-orange-900/5"}`}>
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-2 text-xs">
              <Badge className={`text-[8px] ${msg.direction === "inbound" ? "bg-zinc-700 text-zinc-300" : "bg-orange-500/20 text-orange-400"}`}>{msg.direction}</Badge>
              {msg.agent_id && <span className="text-zinc-500">{msg.agent_id}</span>}
              {msg.model_used && <span className="text-cyan-400/60">{msg.model_used}</span>}
            </div>
            <div className="flex items-center gap-2 text-[10px] text-zinc-600">
              {msg.cost_usd > 0 && <span>${msg.cost_usd.toFixed(4)}</span>}
              {msg.latency_ms > 0 && <span>{msg.latency_ms}ms</span>}
              <span>{new Date(msg.created_at).toLocaleTimeString()}</span>
            </div>
          </div>
          <p className="text-xs text-zinc-300 line-clamp-2">{msg.content}</p>
        </div>
      ))}
    </div>
  );
}
