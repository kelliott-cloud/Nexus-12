import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { handleSilent } from "@/lib/errorHandler";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { TrendingUp, BarChart3, DollarSign, MessageSquare, Loader2 } from "lucide-react";

export default function PerformanceTimeSeries({ workspaceId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState("30d");
  const [metric, setMetric] = useState("messages"); // messages | costs | tools

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [costRes, eventsRes] = await Promise.all([
        api.get(`/workspaces/${workspaceId}/costs?period=${period}`),
        api.get(`/workspaces/${workspaceId}/costs/actual?period=monthly`),
      ]);

      const daily = costRes.data?.daily || [];
      const byModel = costRes.data?.by_model || [];
      const actuals = eventsRes.data?.by_model || [];

      // Build time series data
      const timeSeriesData = daily.map(d => ({
        date: d.date,
        cost: d.cost_usd || 0,
        calls: d.calls || 0,
      }));

      setData({
        timeSeries: timeSeriesData,
        byModel,
        actuals,
        totalCost: costRes.data?.total_cost_usd || 0,
        totalCalls: costRes.data?.total_calls || 0,
      });
    } catch (err) { handleSilent(err, "PerformanceTimeSeries:fetch"); }
    setLoading(false);
  }, [workspaceId, period]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) return <div className="flex-1 flex items-center justify-center"><Loader2 className="w-5 h-5 animate-spin text-zinc-500" /></div>;
  if (!data) return null;

  const metrics = [
    { key: "messages", label: "Messages & Calls", icon: MessageSquare, color: "#22d3ee" },
    { key: "costs", label: "Cost Over Time", icon: DollarSign, color: "#10B981" },
    { key: "tools", label: "Model Usage", icon: BarChart3, color: "#8B5CF6" },
  ];

  return (
    <div className="flex-1 flex flex-col overflow-hidden" data-testid="performance-timeseries">
      <div className="flex-shrink-0 px-6 py-4 border-b border-zinc-800/60">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100 flex items-center gap-2" style={{ fontFamily: "Syne, sans-serif" }}>
              <TrendingUp className="w-5 h-5 text-emerald-400" /> Performance Analytics
            </h2>
            <p className="text-xs text-zinc-500 mt-0.5">Historical performance tracking</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex gap-0.5 bg-zinc-800 rounded-lg p-0.5">
              {metrics.map(m => (
                <button key={m.key} onClick={() => setMetric(m.key)} className={`px-2.5 py-1 rounded-md text-[10px] font-medium transition-colors flex items-center gap-1 ${metric === m.key ? "bg-zinc-700 text-zinc-100" : "text-zinc-500"}`} data-testid={`metric-${m.key}`}>
                  <m.icon className="w-3 h-3" /> {m.label}
                </button>
              ))}
            </div>
            <div className="flex gap-1">
              {["7d", "30d", "90d"].map(p => (
                <Button key={p} size="sm" variant={period === p ? "default" : "ghost"} onClick={() => setPeriod(p)} className="h-7 text-xs" data-testid={`perf-period-${p}`}>{p}</Button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-6 space-y-6 max-w-5xl mx-auto">
          {/* Summary Cards */}
          <div className="grid grid-cols-3 gap-4">
            <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800/40">
              <DollarSign className="w-4 h-4 text-emerald-400 mb-1" />
              <div className="text-2xl font-bold text-white">${data.totalCost.toFixed(2)}</div>
              <p className="text-[10px] text-zinc-500">Total Cost ({period})</p>
            </div>
            <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800/40">
              <MessageSquare className="w-4 h-4 text-cyan-400 mb-1" />
              <div className="text-2xl font-bold text-white">{data.totalCalls}</div>
              <p className="text-[10px] text-zinc-500">API Calls ({period})</p>
            </div>
            <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800/40">
              <BarChart3 className="w-4 h-4 text-violet-400 mb-1" />
              <div className="text-2xl font-bold text-white">{data.byModel.length}</div>
              <p className="text-[10px] text-zinc-500">Active Models</p>
            </div>
          </div>

          {/* Time Series Chart */}
          {data.timeSeries.length > 0 && (
            <div className="bg-zinc-900/50 border border-zinc-800/40 rounded-xl p-4">
              <p className="text-xs text-zinc-400 mb-3">
                {metric === "messages" ? "Daily API Calls" : metric === "costs" ? "Daily Spend ($)" : "Model Distribution"}
              </p>
              <ResponsiveContainer width="100%" height={280}>
                {metric === "costs" ? (
                  <AreaChart data={data.timeSeries}>
                    <defs>
                      <linearGradient id="costGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10B981" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#10B981" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                    <XAxis dataKey="date" tick={{ fill: "#71717a", fontSize: 10 }} tickFormatter={v => v?.slice(5)} />
                    <YAxis tick={{ fill: "#71717a", fontSize: 10 }} tickFormatter={v => `$${v}`} />
                    <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", borderRadius: 8, fontSize: 11 }} labelStyle={{ color: "#a1a1aa" }} />
                    <Area type="monotone" dataKey="cost" stroke="#10B981" fill="url(#costGrad)" strokeWidth={2} name="Cost ($)" />
                  </AreaChart>
                ) : (
                  <LineChart data={data.timeSeries}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                    <XAxis dataKey="date" tick={{ fill: "#71717a", fontSize: 10 }} tickFormatter={v => v?.slice(5)} />
                    <YAxis tick={{ fill: "#71717a", fontSize: 10 }} />
                    <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", borderRadius: 8, fontSize: 11 }} labelStyle={{ color: "#a1a1aa" }} />
                    <Line type="monotone" dataKey="calls" stroke="#22d3ee" strokeWidth={2} dot={false} name="API Calls" />
                  </LineChart>
                )}
              </ResponsiveContainer>
            </div>
          )}

          {data.timeSeries.length === 0 && (
            <div className="bg-zinc-900/50 border border-zinc-800/40 rounded-xl p-8 text-center">
              <TrendingUp className="w-8 h-8 text-zinc-700 mx-auto mb-2" />
              <p className="text-xs text-zinc-500">No usage data yet. Performance data will appear as agents are used in channels.</p>
            </div>
          )}

          {/* Model Breakdown */}
          {data.byModel.length > 0 && (
            <div className="bg-zinc-900/50 border border-zinc-800/40 rounded-xl p-4">
              <p className="text-xs text-zinc-400 mb-3">Usage by Model</p>
              <div className="space-y-2">
                {data.byModel.map((m, i) => {
                  const maxCost = Math.max(...data.byModel.map(x => x.cost_usd || 0), 0.01);
                  return (
                    <div key={i} className="flex items-center gap-3" data-testid={`model-usage-${i}`}>
                      <span className="text-xs text-zinc-300 w-24 truncate">{m.model}</span>
                      <div className="flex-1 h-3 bg-zinc-800 rounded-full overflow-hidden">
                        <div className="h-full bg-gradient-to-r from-cyan-500 to-violet-500 rounded-full" style={{ width: `${((m.cost_usd || 0) / maxCost) * 100}%` }} />
                      </div>
                      <span className="text-[10px] text-zinc-500 w-16 text-right">${(m.cost_usd || 0).toFixed(4)}</span>
                      <span className="text-[10px] text-zinc-600 w-16 text-right">{m.calls || 0} calls</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
