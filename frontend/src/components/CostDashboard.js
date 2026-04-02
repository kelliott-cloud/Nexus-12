import { useState, useEffect } from "react";
import { handleSilent } from "@/lib/errorHandler";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DollarSign, BarChart3, TrendingUp, AlertTriangle, Settings, Loader2, RefreshCw, Clock } from "lucide-react";
import { ProviderIcon } from "@/components/ProviderIcons";
import { api } from "@/lib/api";
import { toast } from "sonner";

export default function CostDashboard({ workspaceId }) {
  const [costs, setCosts] = useState(null);
  const [actualCosts, setActualCosts] = useState(null);
  const [budget, setBudget] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [period, setPeriod] = useState("30d");
  const [editBudget, setEditBudget] = useState(false);
  const [newCap, setNewCap] = useState("");
  const [viewMode, setViewMode] = useState("actual"); // actual | estimated

  useEffect(() => {
    (async () => {
      try {
        const [cRes, bRes, aRes] = await Promise.all([
          api.get(`/workspaces/${workspaceId}/costs?period=${period}`),
          api.get(`/workspaces/${workspaceId}/budget`),
          api.get(`/workspaces/${workspaceId}/costs/actual?period=monthly`),
        ]);
        setCosts(cRes.data);
        setBudget(bRes.data);
        setActualCosts(aRes.data);
      } catch (err) { handleSilent(err, "CostDashboard:fetch"); } finally { setLoading(false); }
    })();
  }, [workspaceId, period]);

  const refreshCosts = async () => {
    setRefreshing(true);
    try {
      await api.post(`/workspaces/${workspaceId}/costs/refresh`);
      const aRes = await api.get(`/workspaces/${workspaceId}/costs/actual?period=monthly`);
      setActualCosts(aRes.data);
      toast.success("Costs refreshed");
    } catch (err) { toast.error("Refresh failed"); } finally { setRefreshing(false); }
  };

  const saveBudget = async () => {
    try {
      await api.put(`/workspaces/${workspaceId}/budget`, { monthly_cap_usd: parseFloat(newCap) || 0 });
      toast.success("Budget updated");
      setEditBudget(false);
      const b = await api.get(`/workspaces/${workspaceId}/budget`);
      setBudget(b.data);
    } catch (err) { toast.error("Failed"); }
  };

  if (loading) return <div className="p-6"><Loader2 className="w-5 h-5 animate-spin text-zinc-500" /></div>;

  const displayData = viewMode === "actual" && actualCosts?.by_model?.length > 0 ? actualCosts.by_model : costs?.by_model || [];
  const costField = viewMode === "actual" ? "actual_cost_usd" : "cost_usd";
  const totalCost = viewMode === "actual" && actualCosts?.totals?.total_actual_cost_usd != null
    ? actualCosts.totals.total_actual_cost_usd
    : costs?.total_cost_usd || 0;
  const maxCost = Math.max(...displayData.map(m => m[costField] || m.cost_usd || m.actual_cost_usd || 0), 0.01);

  return (
    <div className="flex-1 overflow-y-auto p-6" data-testid="cost-dashboard">
      <div className="max-w-5xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-zinc-100 flex items-center gap-2" style={{ fontFamily: "Syne, sans-serif" }}>
            <DollarSign className="w-5 h-5 text-emerald-400" /> AI Cost Intelligence
          </h2>
          <div className="flex items-center gap-2">
            <div className="flex gap-0.5 bg-zinc-800 rounded-lg p-0.5">
              <button onClick={() => setViewMode("actual")} className={`px-2.5 py-1 rounded-md text-[10px] font-medium transition-colors ${viewMode === "actual" ? "bg-emerald-500/20 text-emerald-400" : "text-zinc-500"}`} data-testid="cost-view-actual">Actual</button>
              <button onClick={() => setViewMode("estimated")} className={`px-2.5 py-1 rounded-md text-[10px] font-medium transition-colors ${viewMode === "estimated" ? "bg-cyan-500/20 text-cyan-400" : "text-zinc-500"}`} data-testid="cost-view-estimated">Estimated</button>
            </div>
            <div className="flex gap-1">
              {["7d", "30d", "90d"].map(p => (
                <Button key={p} size="sm" variant={period === p ? "default" : "ghost"} onClick={() => setPeriod(p)} className="h-7 text-xs" data-testid={`cost-period-${p}`}>{p}</Button>
              ))}
            </div>
            <Button size="sm" variant="ghost" onClick={refreshCosts} disabled={refreshing} className="h-7 text-xs text-zinc-400 gap-1" data-testid="cost-refresh-btn">
              <RefreshCw className={`w-3 h-3 ${refreshing ? "animate-spin" : ""}`} /> Refresh
            </Button>
          </div>
        </div>

        {/* Last computed badge */}
        {actualCosts?.last_computed && viewMode === "actual" && (
          <div className="flex items-center gap-1.5 text-[10px] text-zinc-600">
            <Clock className="w-3 h-3" />
            Last computed: {new Date(actualCosts.last_computed).toLocaleString()}
          </div>
        )}

        {/* Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800/40">
            <DollarSign className="w-4 h-4 text-emerald-400 mb-1" />
            <div className="text-2xl font-bold text-white" data-testid="cost-total">${totalCost.toFixed(2)}</div>
            <p className="text-[10px] text-zinc-500">{viewMode === "actual" ? "Actual" : "Estimated"} Cost ({viewMode === "actual" ? "MTD" : period})</p>
          </div>
          <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800/40">
            <BarChart3 className="w-4 h-4 text-cyan-400 mb-1" />
            <div className="text-2xl font-bold text-white" data-testid="cost-calls">{viewMode === "actual" ? (actualCosts?.totals?.total_calls || 0) : (costs?.total_calls || 0)}</div>
            <p className="text-[10px] text-zinc-500">API Calls</p>
          </div>
          <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800/40">
            <TrendingUp className="w-4 h-4 text-amber-400 mb-1" />
            <div className="text-2xl font-bold text-white" data-testid="cost-avg">${costs?.avg_cost_per_call || 0}</div>
            <p className="text-[10px] text-zinc-500">Avg Cost/Call</p>
          </div>
          <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800/40">
            <AlertTriangle className="w-4 h-4 text-purple-400 mb-1" />
            <div className="text-2xl font-bold text-white" data-testid="cost-budget-pct">{budget?.pct_used || 0}%</div>
            <p className="text-[10px] text-zinc-500">Budget Used</p>
          </div>
        </div>

        {/* Budget Section */}
        <div className="p-4 rounded-xl bg-zinc-900/40 border border-zinc-800/40">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-zinc-300">Monthly Budget</h3>
            <Button size="sm" variant="ghost" onClick={() => { setEditBudget(!editBudget); setNewCap(String(budget?.monthly_cap_usd || "")); }} className="h-6 text-[10px] text-zinc-500" data-testid="cost-edit-budget">
              <Settings className="w-3 h-3 mr-1" /> Edit
            </Button>
          </div>
          {budget?.monthly_cap_usd > 0 && (
            <div className="mb-2">
              <div className="flex justify-between text-[10px] text-zinc-500 mb-1">
                <span>${budget.current_month_spend} spent</span>
                <span>${budget.monthly_cap_usd} cap</span>
              </div>
              <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
                <div className={`h-full rounded-full transition-all ${budget.pct_used > 80 ? "bg-red-500" : budget.pct_used > 50 ? "bg-amber-500" : "bg-emerald-500"}`}
                  style={{ width: `${Math.min(budget.pct_used, 100)}%` }} />
              </div>
            </div>
          )}
          {editBudget && (
            <div className="flex gap-2 mt-2">
              <Input value={newCap} onChange={e => setNewCap(e.target.value)} placeholder="Monthly cap ($)" type="number" className="bg-zinc-950 border-zinc-800 h-8 text-xs" data-testid="cost-budget-input" />
              <Button size="sm" onClick={saveBudget} className="h-8 text-xs bg-cyan-500 text-white" data-testid="cost-save-budget">Save</Button>
            </div>
          )}
        </div>

        {/* Cost by Model/Provider */}
        <div>
          <h3 className="text-sm font-semibold text-zinc-300 mb-3">
            {viewMode === "actual" ? "Actual Cost by Provider & Model" : "Estimated Cost by Agent"}
          </h3>
          {displayData.length === 0 ? (
            <p className="text-xs text-zinc-600 text-center py-4">No AI usage data yet. Costs are computed hourly by the batch job.</p>
          ) : (
            <div className="space-y-2">
              {displayData.map((m, i) => {
                const cost = m[costField] || m.cost_usd || m.actual_cost_usd || 0;
                const label = viewMode === "actual" ? `${m.provider || ""}/${m.model || ""}` : (m.model || "unknown");
                const provider = viewMode === "actual" ? (m.provider || m.model || "unknown") : (m.model || "unknown");
                return (
                  <div key={`${label}-${i}`} className="flex items-center gap-3 p-2.5 rounded-lg bg-zinc-900/30 border border-zinc-800/20" data-testid={`cost-row-${i}`}>
                    <ProviderIcon provider={provider} size={24} />
                    <div className="flex-1 min-w-0">
                      <span className="text-xs text-zinc-300 block truncate">{label}</span>
                      <div className="flex gap-3 text-[9px] text-zinc-600 mt-0.5">
                        <span>{(m.input_tokens || m.tokens_in || 0).toLocaleString()} in</span>
                        <span>{(m.output_tokens || m.tokens_out || 0).toLocaleString()} out</span>
                        <span>{m.calls || 0} calls</span>
                      </div>
                    </div>
                    <div className="w-32 h-3 bg-zinc-800 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${viewMode === "actual" ? "bg-emerald-500" : "bg-cyan-500"}`} style={{ width: `${(cost / maxCost) * 100}%` }} />
                    </div>
                    <div className="text-right w-20">
                      <span className="text-xs font-medium text-zinc-200">${cost.toFixed(4)}</span>
                      {viewMode === "actual" && m.estimated_cost_usd != null && (
                        <p className="text-[9px] text-zinc-600">est: ${m.estimated_cost_usd.toFixed(4)}</p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Daily Trend (from estimated data) */}
        {(costs?.daily || []).length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-zinc-300 mb-3">Daily Spend Trend</h3>
            <div className="flex items-end gap-1 h-24">
              {(costs?.daily || []).slice(-30).map((d, i) => {
                const maxDaily = Math.max(...costs.daily.map(x => x.cost_usd), 0.01);
                const pct = (d.cost_usd / maxDaily) * 100;
                return (
                  <div key={i} className="flex-1 flex flex-col items-center" title={`${d.date}: $${d.cost_usd}`}>
                    <div className="w-full bg-cyan-500/60 rounded-t" style={{ height: `${Math.max(pct, 2)}%` }} />
                  </div>
                );
              })}
            </div>
            <div className="flex justify-between text-[9px] text-zinc-600 mt-1">
              <span>{costs.daily[0]?.date}</span>
              <span>{costs.daily[costs.daily.length - 1]?.date}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
