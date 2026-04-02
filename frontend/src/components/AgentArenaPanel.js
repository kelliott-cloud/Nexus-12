import { useState, useEffect, useCallback } from "react";
import { handleSilent } from "@/lib/errorHandler";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Swords, Trophy, ThumbsUp, Loader2, ChevronDown, BarChart3 } from "lucide-react";
import { ProviderIcon } from "@/components/ProviderIcons";
import { api } from "@/lib/api";
import { toast } from "sonner";

export default function AgentArenaPanel({ workspaceId }) {
  const [models, setModels] = useState([]);
  const [battles, setBattles] = useState([]);
  const [leaderboard, setLeaderboard] = useState([]);
  const [prompt, setPrompt] = useState("");
  const [selected, setSelected] = useState(["chatgpt", "claude"]);
  const [running, setRunning] = useState(false);
  const [activeBattle, setActiveBattle] = useState(null);
  const [tab, setTab] = useState("battle");

  // Fetch available models dynamically
  const fetchModels = useCallback(async () => {
    try {
      const res = await api.get("/ai-models");
      const data = res.data?.models || res.data || {};
      const modelList = Object.entries(data).map(([key, variants]) => {
        const variantList = Array.isArray(variants) ? variants : [];
        const defaultVariant = variantList.find(v => v.default) || variantList[0] || {};
        return {
          key,
          name: key.charAt(0).toUpperCase() + key.slice(1),
          variants: variantList,
          selectedVariant: defaultVariant.id || "",
        };
      });
      setModels(modelList);
    } catch (err) { handleSilent(err, "Arena:fetchModels"); }
  }, []);

  useEffect(() => {
    fetchModels();
    api.get(`/workspaces/${workspaceId}/arena/battles?limit=10`).then(r => setBattles(r.data || [])).catch(() => {});
    api.get(`/workspaces/${workspaceId}/arena/leaderboard`).then(r => setLeaderboard(r.data?.leaderboard || [])).catch(() => {});
  }, [workspaceId, fetchModels]);

  const toggleModel = (key) => {
    setSelected(prev => prev.includes(key) ? prev.filter(k => k !== key) : prev.length < 4 ? [...prev, key] : prev);
  };

  const updateVariant = (key, variantId) => {
    setModels(prev => prev.map(m => m.key === key ? { ...m, selectedVariant: variantId } : m));
  };

  const startBattle = async () => {
    if (!prompt.trim() || selected.length < 2) return;
    setRunning(true);
    try {
      const res = await api.post(`/workspaces/${workspaceId}/arena/battle`, { prompt, models: selected, category: "general" });
      setActiveBattle(res.data);
      const poll = setInterval(async () => {
        try {
          const b = await api.get(`/arena/battles/${res.data.battle_id}`);
          if (b.data.status === "completed") {
            setActiveBattle(b.data);
            clearInterval(poll);
            setRunning(false);
            // Refresh history
            api.get(`/workspaces/${workspaceId}/arena/battles?limit=10`).then(r => setBattles(r.data || [])).catch(() => {});
          }
        } catch { clearInterval(poll); setRunning(false); }
      }, 2000);
      // Safety timeout after 60s
      setTimeout(() => { clearInterval(poll); setRunning(false); }, 60000);
    } catch (err) { toast.error(err.response?.data?.detail || "Battle failed"); setRunning(false); }
  };

  const vote = async (battleId, winner) => {
    try {
      await api.post(`/arena/battles/${battleId}/vote`, { winner });
      toast.success(`Voted for ${winner}`);
      api.get(`/workspaces/${workspaceId}/arena/leaderboard`).then(r => setLeaderboard(r.data?.leaderboard || []));
    } catch { toast.error("Vote failed"); }
  };

  return (
    <div className="flex-1 flex flex-col min-h-0 p-6" data-testid="agent-arena">
      <div className="flex items-center gap-3 mb-4">
        <Swords className="w-5 h-5 text-amber-400" />
        <h2 className="text-lg font-semibold text-zinc-100" style={{ fontFamily: "Syne, sans-serif" }}>Agent Arena</h2>
        <div className="flex gap-1 ml-4">
          <Button size="sm" variant={tab === "battle" ? "default" : "ghost"} onClick={() => setTab("battle")} className="h-7 text-xs" data-testid="arena-tab-battle">Battle</Button>
          <Button size="sm" variant={tab === "history" ? "default" : "ghost"} onClick={() => setTab("history")} className="h-7 text-xs" data-testid="arena-tab-history">History</Button>
          <Button size="sm" variant={tab === "leaderboard" ? "default" : "ghost"} onClick={() => setTab("leaderboard")} className="h-7 text-xs" data-testid="arena-tab-leaderboard">Leaderboard</Button>
        </div>
      </div>

      {tab === "battle" && (
        <ScrollArea className="flex-1">
          <div className="space-y-4 pr-2">
            <textarea value={prompt} onChange={e => setPrompt(e.target.value)} placeholder="Enter a prompt to test across multiple AI models..."
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-3 text-sm text-zinc-200 placeholder:text-zinc-600 min-h-[80px] resize-none"
              data-testid="arena-prompt-input" />
            
            <div>
              <p className="text-xs text-zinc-500 mb-2">Select 2-4 agents to compete ({selected.length} selected):</p>
              <div className="flex flex-wrap gap-2">
                {models.map(m => (
                  <div key={m.key} className="flex flex-col gap-1">
                    <button onClick={() => toggleModel(m.key)}
                      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs transition-all ${selected.includes(m.key) ? "border-cyan-500/50 bg-cyan-500/10 text-cyan-300" : "border-zinc-800 text-zinc-500 hover:border-zinc-700"}`}
                      data-testid={`arena-model-${m.key}`}>
                      <ProviderIcon provider={m.key} size={18} />
                      <span>{m.name}</span>
                    </button>
                    {selected.includes(m.key) && m.variants.length > 1 && (
                      <select value={m.selectedVariant} onChange={e => updateVariant(m.key, e.target.value)}
                        className="h-6 px-1.5 rounded bg-zinc-900 border border-zinc-700 text-[10px] text-cyan-300"
                        data-testid={`arena-variant-${m.key}`}>
                        {m.variants.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
                      </select>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <Button onClick={startBattle} disabled={running || !prompt.trim() || selected.length < 2}
              className="bg-amber-500 hover:bg-amber-400 text-black font-semibold gap-2"
              data-testid="arena-start-btn">
              {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <Swords className="w-4 h-4" />}
              {running ? "Running..." : "Start Battle"}
            </Button>

            {/* Active Battle Results */}
            {activeBattle?.status === "completed" && (
              <div className="space-y-3 mt-4" data-testid="arena-results">
                <p className="text-xs text-zinc-400">Results for: &ldquo;{activeBattle.prompt?.substring(0, 80)}{activeBattle.prompt?.length > 80 ? "..." : ""}&rdquo;</p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {Object.entries(activeBattle.responses || {}).map(([model, resp]) => (
                    <div key={model} className="p-4 rounded-xl border border-zinc-800/50 bg-zinc-900/40" data-testid={`arena-result-${model}`}>
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <ProviderIcon provider={model} size={24} />
                          <span className="text-sm font-medium text-zinc-200">{model}</span>
                        </div>
                        <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                          <span>{resp.time_ms}ms</span>
                          <span>{resp.tokens} tok</span>
                        </div>
                      </div>
                      {resp.error ? (
                        <p className="text-xs text-red-400">{resp.error}</p>
                      ) : (
                        <p className="text-xs text-zinc-400 max-h-[200px] overflow-y-auto whitespace-pre-wrap">{resp.text?.substring(0, 1000)}</p>
                      )}
                      {!resp.error && (
                        <Button size="sm" onClick={() => vote(activeBattle.battle_id, model)}
                          className="mt-2 h-7 text-[10px] bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 gap-1"
                          data-testid={`arena-vote-${model}`}>
                          <ThumbsUp className="w-3 h-3" /> Vote Best
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeBattle?.status === "running" && (
              <div className="flex items-center gap-3 p-6 rounded-xl border border-zinc-800/40 bg-zinc-900/30 justify-center" data-testid="arena-running">
                <Loader2 className="w-5 h-5 animate-spin text-amber-400" />
                <span className="text-sm text-zinc-400">Models are generating responses...</span>
              </div>
            )}
          </div>
        </ScrollArea>
      )}

      {tab === "history" && (
        <ScrollArea className="flex-1">
          <div className="space-y-2 pr-2" data-testid="arena-history">
            {battles.length === 0 ? (
              <p className="text-sm text-zinc-500 text-center py-8">No battles yet. Run your first battle to get started.</p>
            ) : (
              battles.map(b => (
                <div key={b.battle_id} className="p-3 rounded-lg border border-zinc-800/40 bg-zinc-900/30 cursor-pointer hover:border-zinc-700/50 transition-colors"
                  onClick={() => setActiveBattle(b)}
                  data-testid={`arena-history-${b.battle_id}`}>
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-zinc-300 truncate flex-1">{b.prompt?.substring(0, 100)}</p>
                    <Badge variant="secondary" className={`text-[9px] ml-2 ${b.status === "completed" ? "bg-emerald-500/10 text-emerald-400" : "bg-amber-500/10 text-amber-400"}`}>
                      {b.status}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2 mt-1.5">
                    {(b.models || []).map(m => (
                      <div key={m} className="flex items-center gap-1">
                        <ProviderIcon provider={m} size={14} />
                        <span className="text-[10px] text-zinc-500">{m}</span>
                      </div>
                    ))}
                    {b.winner && <span className="text-[10px] text-amber-400 ml-auto">Winner: {b.winner}</span>}
                  </div>
                </div>
              ))
            )}
          </div>
        </ScrollArea>
      )}

      {tab === "leaderboard" && (
        <ScrollArea className="flex-1">
          <div data-testid="arena-leaderboard">
            {leaderboard.length === 0 ? (
              <p className="text-sm text-zinc-500 text-center py-8">No battles yet. Run your first battle to start the leaderboard.</p>
            ) : (
              <div className="space-y-2">
                {leaderboard.map((entry, i) => (
                  <div key={entry.model} className="flex items-center gap-3 p-3 rounded-lg border border-zinc-800/40 bg-zinc-900/30" data-testid={`arena-leaderboard-${entry.model}`}>
                    <span className={`text-lg font-bold w-8 ${i === 0 ? "text-amber-400" : i === 1 ? "text-zinc-300" : i === 2 ? "text-amber-700" : "text-zinc-600"}`}>#{i + 1}</span>
                    <ProviderIcon provider={entry.model} size={28} />
                    <div className="flex-1">
                      <span className="text-sm font-medium text-zinc-200">{entry.model}</span>
                      <div className="flex gap-3 text-[10px] text-zinc-500">
                        <span>{entry.wins} wins</span>
                        <span>{entry.total_battles} battles</span>
                      </div>
                    </div>
                    <div className="text-right">
                      <span className="text-lg font-bold text-cyan-400">{entry.win_rate}%</span>
                      <p className="text-[9px] text-zinc-600">win rate</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </ScrollArea>
      )}
    </div>
  );
}
