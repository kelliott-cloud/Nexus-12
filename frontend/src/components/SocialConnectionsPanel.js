import { useState, useEffect } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Youtube, ExternalLink, Plus, Trash2, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { api } from "@/App";
import { toast } from "sonner";

export function SocialConnectionsPanel() {
  const [platforms, setPlatforms] = useState([]);
  const [connections, setConnections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(null);

  useEffect(() => { load(); }, []);

  const load = async () => {
    try {
      const [pRes, cRes] = await Promise.all([
        api.get("/social/platforms"),
        api.get("/social/connections"),
      ]);
      setPlatforms(pRes.data?.platforms || []);
      setConnections(cRes.data || []);
    } catch (err) { handleSilent(err, "SocialConnectionsPanel:op1"); } finally { setLoading(false); }
  };

  const connect = async (platform) => {
    setConnecting(platform);
    try {
      const res = await api.post("/social/connect", {
        platform,
        redirect_uri: `${window.location.origin}/social/callback`,
      });
      if (res.data?.auth_url) {
        window.open(res.data.auth_url, "_blank", "width=600,height=700");
        toast.info("Complete the authorization in the popup window");
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || "Connection failed");
    }
    setConnecting(null);
  };

  const disconnect = async (connId) => {
    try {
      await api.delete(`/social/connections/${connId}`);
      toast.success("Disconnected");
      load();
    } catch (err) { toast.error("Failed to disconnect"); }
  };

  if (loading) return <div className="p-4"><Loader2 className="w-4 h-4 animate-spin text-zinc-500" /></div>;

  return (
    <div className="space-y-4" data-testid="social-connections-panel">
      <div>
        <h3 className="text-sm font-semibold text-zinc-300 mb-1">Social Media Accounts</h3>
        <p className="text-xs text-zinc-500 mb-3">Connect your social accounts to publish content directly from Nexus Cloud</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {platforms.map(p => (
          <div key={p.platform} className="p-3 rounded-lg border border-zinc-800/40 bg-zinc-900/30">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-zinc-300">{p.name}</span>
              {p.connected ? (
                <Badge className="text-[8px] bg-emerald-500/20 text-emerald-400">Connected</Badge>
              ) : (
                <Badge className="text-[8px] bg-zinc-800 text-zinc-500">Not Connected</Badge>
              )}
            </div>
            {p.connected ? (
              <p className="text-[10px] text-zinc-500">{p.connections} account(s) connected</p>
            ) : p.configured ? (
              <Button size="sm" onClick={() => connect(p.platform)} disabled={connecting === p.platform}
                className="w-full h-7 text-[10px] bg-cyan-500 hover:bg-cyan-400 text-white mt-1">
                {connecting === p.platform ? <Loader2 className="w-3 h-3 animate-spin" /> : <><Plus className="w-3 h-3 mr-1" /> Connect</>}
              </Button>
            ) : (
              <p className="text-[10px] text-zinc-600 mt-1">Add API key in Integration Settings</p>
            )}
          </div>
        ))}
      </div>

      {connections.filter(c => c.status === "active").length > 0 && (
        <div className="space-y-1 mt-4">
          <p className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Active Connections</p>
          {connections.filter(c => c.status === "active").map(conn => (
            <div key={conn.connection_id} className="flex items-center justify-between p-2 rounded-lg bg-zinc-800/30 text-xs">
              <div className="flex items-center gap-2 text-zinc-400">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-zinc-300">{conn.provider}</span>
                {conn.account_name && <span className="text-zinc-500">({conn.account_name})</span>}
              </div>
              <Button size="sm" variant="ghost" onClick={() => disconnect(conn.connection_id)} className="h-6 text-red-400 hover:text-red-300">
                <Trash2 className="w-3 h-3" />
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default SocialConnectionsPanel;
