import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Shield, Bot, Check, X, Crown, Loader2 } from "lucide-react";

export default function TPMDesignation({ workspaceId }) {
  const [agents, setAgents] = useState([]);
  const [tpmData, setTpmData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [setting, setSetting] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const [agentsRes, tpmRes] = await Promise.all([
          api.get(`/workspaces/${workspaceId}/agents`),
          api.get(`/workspaces/${workspaceId}/tpm`),
        ]);
        const agentList = agentsRes.data?.agents || agentsRes.data || [];
        setAgents(Array.isArray(agentList) ? agentList : []);
        setTpmData(tpmRes.data);
      } catch {}
      setLoading(false);
    };
    load();
  }, [workspaceId]);

  const designate = async (agentId) => {
    setSetting(true);
    try {
      await api.put(`/workspaces/${workspaceId}/tpm`, { agent_id: agentId });
      const r = await api.get(`/workspaces/${workspaceId}/tpm`);
      setTpmData(r.data);
      toast.success(agentId ? "TPM designated" : "TPM removed");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
    setSetting(false);
  };

  if (loading) return <div className="p-4 text-center"><Loader2 className="w-4 h-4 animate-spin mx-auto text-zinc-600" /></div>;

  const currentTpm = tpmData?.tpm_agent_id;
  const tpmAgent = tpmData?.tpm_agent;
  const tpmChannel = tpmData?.tpm_channel;

  return (
    <div className="space-y-4" data-testid="tpm-designation">
      <div className="flex items-center gap-2 mb-1">
        <Crown className="w-4 h-4 text-amber-400" />
        <h3 className="text-sm font-semibold text-zinc-200">TPM Designation</h3>
      </div>
      <p className="text-xs text-zinc-500">
        Designate one AI agent as the Technical Project Manager. The TPM coordinates all other agents,
        assigns tasks, prevents duplicate work, and manages the project lifecycle. Only one TPM per workspace.
      </p>

      {/* Current TPM */}
      {currentTpm && tpmAgent ? (
        <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-amber-500/20 flex items-center justify-center">
                <Crown className="w-4 h-4 text-amber-400" />
              </div>
              <div>
                <p className="text-sm font-semibold text-amber-300">{tpmAgent.name}</p>
                <p className="text-[10px] text-zinc-500">{tpmAgent.base_model} · Designated TPM</p>
              </div>
            </div>
            <Button size="sm" variant="outline" onClick={() => designate(null)} disabled={setting}
              className="text-[10px] border-zinc-700 text-zinc-400 h-7">
              {setting ? <Loader2 className="w-3 h-3 animate-spin" /> : <X className="w-3 h-3 mr-1" />}
              Remove
            </Button>
          </div>
          {tpmChannel && (
            <p className="text-[10px] text-zinc-600 mt-2">
              TPM Channel: <span className="text-zinc-400">#{tpmChannel.name}</span> · {(tpmChannel.ai_agents || []).length} agent
            </p>
          )}
        </div>
      ) : (
        <div className="p-4 rounded-xl bg-zinc-900/40 border border-zinc-800/50 text-center">
          <Shield className="w-8 h-8 text-zinc-700 mx-auto mb-2" />
          <p className="text-sm text-zinc-400">No TPM designated</p>
          <p className="text-[10px] text-zinc-600">Select an agent below to designate as TPM</p>
        </div>
      )}

      {/* Agent list */}
      <div className="space-y-1.5">
        <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-wider">Available Agents</p>
        {agents.length === 0 ? (
          <p className="text-xs text-zinc-600 py-3">No agents in this workspace. Create an agent first.</p>
        ) : (
          agents.map(agent => {
            const isCurrentTpm = agent.agent_id === currentTpm;
            return (
              <div key={agent.agent_id}
                className={`flex items-center justify-between p-2.5 rounded-lg border transition-colors ${
                  isCurrentTpm ? 'border-amber-500/30 bg-amber-500/5' : 'border-zinc-800/40 bg-zinc-950/50 hover:border-zinc-700'
                }`}>
                <div className="flex items-center gap-2.5">
                  <div className="w-7 h-7 rounded-md flex items-center justify-center text-[10px] font-bold text-white"
                    style={{ backgroundColor: agent.color || '#555' }}>
                    {(agent.name || "?")[0]}
                  </div>
                  <div>
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm text-zinc-200">{agent.name}</span>
                      {isCurrentTpm && <Badge className="bg-amber-500/15 text-amber-400 text-[8px]">TPM</Badge>}
                    </div>
                    <p className="text-[9px] text-zinc-600">{agent.base_model}</p>
                  </div>
                </div>
                {!isCurrentTpm && (
                  <Button size="sm" onClick={() => designate(agent.agent_id)} disabled={setting}
                    className="text-[10px] bg-zinc-800 hover:bg-zinc-700 text-zinc-300 h-7 px-3">
                    {setting ? <Loader2 className="w-3 h-3 animate-spin" /> : <Crown className="w-3 h-3 mr-1" />}
                    Set as TPM
                  </Button>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
