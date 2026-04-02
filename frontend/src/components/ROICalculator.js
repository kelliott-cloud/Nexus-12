import { useState, useEffect, useCallback } from "react";
import { api } from "@/App";
import { handleSilent } from "@/lib/errorHandler";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { DollarSign, TrendingUp, Clock, Zap, BarChart3, ArrowUpRight, ArrowDownRight, Minus, GitCompare } from "lucide-react";

export default function ROICalculator({ workspaceId }) {
  const [activeView, setActiveView] = useState("calculator");
  const [summary, setSummary] = useState(null);
  const [byModel, setByModel] = useState(null);
  const [byAgent, setByAgent] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [comparison, setComparison] = useState(null);
  const [period, setPeriod] = useState("30d");
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    if (!workspaceId) return;
    setLoading(true);
    try {
      const promises = [
        api.get(`/workspaces/${workspaceId}/roi/summary?period=${period}`),
        api.get(`/workspaces/${workspaceId}/roi/by-model?period=${period}`),
        api.get(`/workspaces/${workspaceId}/roi/by-agent?period=${period}`),
        api.get(`/workspaces/${workspaceId}/roi/forecast?days_ahead=30`),
      ];
      if (activeView === "comparison") {
        promises.push(api.get(`/roi-comparison/workspaces?period=${period}`));
      }
      const results = await Promise.all(promises);
      setSummary(results[0].data);
      setByModel(results[1].data);
      setByAgent(results[2].data);
      setForecast(results[3].data);
      if (results[4]) setComparison(results[4].data);
    } catch (err) { handleSilent(err, "ROI:fetch"); }
    setLoading(false);
  }, [workspaceId, period, activeView]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Fetch comparison data when switching to that view
  const fetchComparison = useCallback(async () => {
    try {
      const res = await api.get(`/roi-comparison/workspaces?period=${period}`);
      setComparison(res.data);
    } catch (err) { handleSilent(err, "ROI:comparison"); }
  }, [period]);

  useEffect(() => {
    if (activeView === "comparison" && !comparison) fetchComparison();
  }, [activeView, comparison, fetchComparison]);

  const TrendIcon = ({ trend }) => {
    if (trend === "increasing") return <ArrowUpRight className="w-3.5 h-3.5 text-red-400" />;
    if (trend === "decreasing") return <ArrowDownRight className="w-3.5 h-3.5 text-emerald-400" />;
    return <Minus className="w-3.5 h-3.5 text-zinc-500" />;
  };

  const StatCard = ({ icon: Icon, label, value, sub, color = "cyan" }) => (
    <Card className="bg-zinc-900/60 border-zinc-800/60" data-testid={`roi-stat-${label.toLowerCase().replace(/\s+/g, "-")}`}>
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          <div className={`p-2 rounded-lg bg-${color}-400/10`}>
            <Icon className={`w-4 h-4 text-${color}-400`} />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</p>
            <p className="text-xl font-bold text-zinc-100 mt-0.5">{value}</p>
            {sub && <p className="text-[10px] text-zinc-500 mt-0.5">{sub}</p>}
          </div>
        </div>
      </CardContent>
    </Card>
  );

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center text-zinc-500 text-sm" data-testid="roi-loading">
        Loading ROI data...
      </div>
    );
  }

  const costs = summary?.costs || {};
  const roi = summary?.roi || {};
  const vol = summary?.volume || {};
  const hasData = costs.total_calls > 0 || vol.total_messages > 0;

  return (
    <ScrollArea className="flex-1">
      <div className="p-6 space-y-6 max-w-5xl mx-auto" data-testid="roi-calculator">
        {/* Header with view toggle */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100">AI Agent Model ROI Calculator</h2>
            <p className="text-xs text-zinc-500 mt-0.5">Cost analysis, model comparison & forecasting from real usage data</p>
          </div>
          <div className="flex items-center gap-3">
            {/* View toggle */}
            <div className="flex gap-1 bg-zinc-800/50 rounded-lg p-0.5">
              <button
                onClick={() => setActiveView("calculator")}
                className={`px-3 py-1 text-xs rounded-md transition-colors ${
                  activeView === "calculator" ? "bg-zinc-700 text-zinc-200" : "text-zinc-500 hover:text-zinc-300"
                }`}
                data-testid="roi-view-calculator"
              >
                Calculator
              </button>
              <button
                onClick={() => setActiveView("comparison")}
                className={`px-3 py-1 text-xs rounded-md transition-colors flex items-center gap-1.5 ${
                  activeView === "comparison" ? "bg-zinc-700 text-zinc-200" : "text-zinc-500 hover:text-zinc-300"
                }`}
                data-testid="roi-view-comparison"
              >
                <GitCompare className="w-3 h-3" />
                Compare
              </button>
            </div>
            {/* Period selector */}
            <div className="flex gap-1">
              {["7d", "30d", "90d"].map(p => (
                <button
                  key={p}
                  onClick={() => setPeriod(p)}
                  className={`px-3 py-1 text-xs rounded-md transition-colors ${
                    period === p ? "bg-cyan-400/10 text-cyan-400" : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50"
                  }`}
                  data-testid={`roi-period-${p}`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Comparison View */}
        {activeView === "comparison" && (
          <ComparisonView comparison={comparison} period={period} currentWorkspaceId={workspaceId} />
        )}

        {/* Calculator View */}
        {activeView === "calculator" && (<>
        {!hasData && (
          <Card className="bg-zinc-900/60 border-zinc-800/60">
            <CardContent className="p-8 text-center">
              <BarChart3 className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
              <p className="text-sm text-zinc-400">No usage data yet for this period</p>
              <p className="text-xs text-zinc-600 mt-1">Start using AI agents in channels to see ROI metrics populate here</p>
            </CardContent>
          </Card>
        )}

        {/* Summary Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatCard icon={DollarSign} label="Total Cost" value={`$${costs.total_usd || 0}`} sub={`${costs.total_calls || 0} API calls`} color="cyan" />
          <StatCard icon={Clock} label="Time Saved" value={`${roi.time_saved_hours || 0}h`} sub={`$${roi.human_cost_equivalent_usd || 0} equivalent`} color="emerald" />
          <StatCard icon={TrendingUp} label="ROI Multiplier" value={`${roi.roi_multiplier || 0}x`} sub={`${roi.efficiency_score || 0}% efficiency`} color="amber" />
          <StatCard icon={Zap} label="Messages" value={vol.agent_messages || 0} sub={`${vol.human_messages || 0} human / ${vol.agent_messages || 0} AI`} color="violet" />
        </div>

        {/* Cost per metric */}
        {hasData && (
          <div className="grid grid-cols-2 gap-3">
            <Card className="bg-zinc-900/60 border-zinc-800/60">
              <CardHeader className="p-3 pb-1"><CardTitle className="text-xs text-zinc-500">Cost Efficiency</CardTitle></CardHeader>
              <CardContent className="p-3 pt-0 space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="text-zinc-400">Per message</span>
                  <span className="text-zinc-200 font-mono">${costs.cost_per_message || 0}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-zinc-400">Per 1K tokens</span>
                  <span className="text-zinc-200 font-mono">${costs.cost_per_1k_tokens || 0}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-zinc-400">Total tokens</span>
                  <span className="text-zinc-200 font-mono">{(costs.total_tokens || 0).toLocaleString()}</span>
                </div>
              </CardContent>
            </Card>

            {/* Forecast */}
            <Card className="bg-zinc-900/60 border-zinc-800/60">
              <CardHeader className="p-3 pb-1">
                <CardTitle className="text-xs text-zinc-500 flex items-center gap-1.5">
                  Forecast (next 30d) <TrendIcon trend={forecast?.trend} />
                </CardTitle>
              </CardHeader>
              <CardContent className="p-3 pt-0 space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="text-zinc-400">Projected cost</span>
                  <span className="text-zinc-200 font-mono">${forecast?.total_forecast_usd || 0}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-zinc-400">Daily average</span>
                  <span className="text-zinc-200 font-mono">${forecast?.daily_avg_forecast || 0}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-zinc-400">Trend</span>
                  <Badge variant="secondary" className="text-[9px] bg-zinc-800">{forecast?.trend || "n/a"}</Badge>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Model Comparison */}
        {byModel?.models?.length > 0 && (
          <Card className="bg-zinc-900/60 border-zinc-800/60" data-testid="roi-model-comparison">
            <CardHeader className="p-3 pb-1"><CardTitle className="text-xs text-zinc-500">Model Comparison</CardTitle></CardHeader>
            <CardContent className="p-3 pt-0">
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-zinc-600 border-b border-zinc-800/60">
                      <th className="text-left py-1.5 font-medium">Model</th>
                      <th className="text-right py-1.5 font-medium">Cost</th>
                      <th className="text-right py-1.5 font-medium">Calls</th>
                      <th className="text-right py-1.5 font-medium">$/Call</th>
                      <th className="text-right py-1.5 font-medium">$/1K tok</th>
                      <th className="text-right py-1.5 font-medium">Latency</th>
                    </tr>
                  </thead>
                  <tbody>
                    {byModel.models.map(m => (
                      <tr key={m.model} className="border-b border-zinc-800/30 text-zinc-300">
                        <td className="py-1.5 font-medium">{m.model}</td>
                        <td className="text-right font-mono">${m.cost_usd}</td>
                        <td className="text-right">{m.calls}</td>
                        <td className="text-right font-mono">${m.cost_per_call}</td>
                        <td className="text-right font-mono">${m.cost_per_1k_tokens}</td>
                        <td className="text-right">{m.avg_latency_ms}ms</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Per-Agent ROI */}
        {byAgent?.agents?.length > 0 && (
          <Card className="bg-zinc-900/60 border-zinc-800/60" data-testid="roi-agent-breakdown">
            <CardHeader className="p-3 pb-1"><CardTitle className="text-xs text-zinc-500">Per-Agent ROI</CardTitle></CardHeader>
            <CardContent className="p-3 pt-0">
              <div className="space-y-2">
                {byAgent.agents.map(a => {
                  const roiColor = a.roi >= 10 ? "emerald" : a.roi >= 5 ? "cyan" : a.roi >= 1 ? "amber" : "red";
                  return (
                    <div key={a.agent} className="flex items-center gap-3 py-1.5 border-b border-zinc-800/30 last:border-0">
                      <span className="text-xs text-zinc-300 font-medium w-24 truncate">{a.agent}</span>
                      <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                        <div
                          className={`h-full bg-${roiColor}-400 rounded-full`}
                          style={{ width: `${Math.min(a.roi / 20 * 100, 100)}%` }}
                        />
                      </div>
                      <span className="text-xs font-mono text-zinc-400 w-16 text-right">${a.cost_usd}</span>
                      <Badge variant="secondary" className={`text-[9px] bg-${roiColor}-400/10 text-${roiColor}-400`}>{a.roi}x ROI</Badge>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        )}
        </>)}
      </div>
    </ScrollArea>
  );
}

function ComparisonView({ comparison, period, currentWorkspaceId }) {
  const workspaces = comparison?.workspaces || [];

  if (!workspaces.length) {
    return (
      <Card className="bg-zinc-900/60 border-zinc-800/60">
        <CardContent className="p-8 text-center">
          <GitCompare className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
          <p className="text-sm text-zinc-400">No workspace data available for comparison</p>
          <p className="text-xs text-zinc-600 mt-1">Join or create multiple workspaces to compare ROI across them</p>
        </CardContent>
      </Card>
    );
  }

  const maxROI = Math.max(...workspaces.map(w => w.roi_multiplier), 1);
  const maxCost = Math.max(...workspaces.map(w => w.total_cost_usd), 1);

  return (
    <div className="space-y-4" data-testid="roi-comparison-view">
      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-3">
        <Card className="bg-zinc-900/60 border-zinc-800/60">
          <CardContent className="p-4 text-center">
            <p className="text-[10px] uppercase tracking-wider text-zinc-500">Workspaces</p>
            <p className="text-2xl font-bold text-zinc-100 mt-1">{workspaces.length}</p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-900/60 border-zinc-800/60">
          <CardContent className="p-4 text-center">
            <p className="text-[10px] uppercase tracking-wider text-zinc-500">Total Cost ({period})</p>
            <p className="text-2xl font-bold text-cyan-400 mt-1">
              ${workspaces.reduce((sum, w) => sum + w.total_cost_usd, 0).toFixed(2)}
            </p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-900/60 border-zinc-800/60">
          <CardContent className="p-4 text-center">
            <p className="text-[10px] uppercase tracking-wider text-zinc-500">Best ROI</p>
            <p className="text-2xl font-bold text-emerald-400 mt-1">
              {workspaces[0]?.roi_multiplier || 0}x
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Comparison table */}
      <Card className="bg-zinc-900/60 border-zinc-800/60" data-testid="roi-comparison-table">
        <CardHeader className="p-3 pb-1">
          <CardTitle className="text-xs text-zinc-500">Workspace ROI Comparison</CardTitle>
        </CardHeader>
        <CardContent className="p-3 pt-0">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-zinc-600 border-b border-zinc-800/60">
                  <th className="text-left py-2 font-medium">Workspace</th>
                  <th className="text-right py-2 font-medium">Cost</th>
                  <th className="text-right py-2 font-medium">Calls</th>
                  <th className="text-right py-2 font-medium">Messages</th>
                  <th className="text-right py-2 font-medium">Time Saved</th>
                  <th className="text-right py-2 font-medium">ROI</th>
                  <th className="text-right py-2 font-medium">Efficiency</th>
                </tr>
              </thead>
              <tbody>
                {workspaces.map(ws => {
                  const isCurrent = ws.workspace_id === currentWorkspaceId;
                  return (
                    <tr key={ws.workspace_id} className={`border-b border-zinc-800/30 ${isCurrent ? "bg-cyan-400/5" : ""}`}>
                      <td className="py-2">
                        <div className="flex items-center gap-2">
                          <span className={`font-medium ${isCurrent ? "text-cyan-400" : "text-zinc-300"}`}>
                            {ws.workspace_name}
                          </span>
                          {isCurrent && <Badge variant="secondary" className="text-[8px] bg-cyan-400/10 text-cyan-400">Current</Badge>}
                        </div>
                      </td>
                      <td className="text-right font-mono text-zinc-300">${ws.total_cost_usd}</td>
                      <td className="text-right text-zinc-400">{ws.total_calls}</td>
                      <td className="text-right text-zinc-400">{ws.total_messages}</td>
                      <td className="text-right text-zinc-400">{ws.time_saved_hours}h</td>
                      <td className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <div className="w-16 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-emerald-400 rounded-full"
                              style={{ width: `${Math.min((ws.roi_multiplier / maxROI) * 100, 100)}%` }}
                            />
                          </div>
                          <span className="text-emerald-400 font-mono font-medium">{ws.roi_multiplier}x</span>
                        </div>
                      </td>
                      <td className="text-right">
                        <Badge variant="secondary" className={`text-[9px] ${
                          ws.efficiency_score >= 80 ? "bg-emerald-400/10 text-emerald-400" :
                          ws.efficiency_score >= 50 ? "bg-amber-400/10 text-amber-400" :
                          "bg-zinc-800 text-zinc-400"
                        }`}>
                          {ws.efficiency_score}%
                        </Badge>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Cost distribution bars */}
      <Card className="bg-zinc-900/60 border-zinc-800/60">
        <CardHeader className="p-3 pb-1">
          <CardTitle className="text-xs text-zinc-500">Cost Distribution</CardTitle>
        </CardHeader>
        <CardContent className="p-3 pt-0 space-y-2">
          {workspaces.map(ws => (
            <div key={ws.workspace_id} className="flex items-center gap-3">
              <span className="text-xs text-zinc-400 w-28 truncate">{ws.workspace_name}</span>
              <div className="flex-1 h-3 bg-zinc-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-cyan-400/70 rounded-full transition-all"
                  style={{ width: `${maxCost > 0 ? (ws.total_cost_usd / maxCost) * 100 : 0}%` }}
                />
              </div>
              <span className="text-xs font-mono text-zinc-300 w-16 text-right">${ws.total_cost_usd}</span>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Resource overview per workspace */}
      <div className="grid grid-cols-2 gap-3">
        {workspaces.slice(0, 4).map(ws => (
          <Card key={ws.workspace_id} className={`bg-zinc-900/60 border-zinc-800/60 ${ws.workspace_id === currentWorkspaceId ? "ring-1 ring-cyan-400/20" : ""}`}>
            <CardContent className="p-3 space-y-1.5">
              <p className="text-xs font-medium text-zinc-200 truncate">{ws.workspace_name}</p>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                <div className="flex justify-between text-[10px]">
                  <span className="text-zinc-500">Agents</span>
                  <span className="text-zinc-300">{ws.agent_count}</span>
                </div>
                <div className="flex justify-between text-[10px]">
                  <span className="text-zinc-500">Knowledge</span>
                  <span className="text-zinc-300">{ws.knowledge_chunks}</span>
                </div>
                <div className="flex justify-between text-[10px]">
                  <span className="text-zinc-500">AI Msgs</span>
                  <span className="text-zinc-300">{ws.agent_messages}</span>
                </div>
                <div className="flex justify-between text-[10px]">
                  <span className="text-zinc-500">Saved</span>
                  <span className="text-emerald-400">${ws.human_cost_equivalent_usd}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
