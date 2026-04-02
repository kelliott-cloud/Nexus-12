import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { handleSilent } from "@/lib/errorHandler";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  BarChart3, TrendingUp, AlertTriangle, Target, Zap, Brain, ArrowUp, ArrowDown
} from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, AreaChart, Area
} from "recharts";

export default function TrainingAnalytics({ workspaceId, agentId, agentName }) {
  const [effectiveness, setEffectiveness] = useState(null);
  const [gaps, setGaps] = useState(null);
  const [timeseries, setTimeseries] = useState(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  const fetchData = useCallback(async () => {
    if (!agentId) return;
    setLoading(true);
    try {
      const [effRes, gapRes, tsRes] = await Promise.all([
        api.get(`/workspaces/${workspaceId}/agents/${agentId}/analytics/effectiveness`),
        api.get(`/workspaces/${workspaceId}/agents/${agentId}/analytics/gaps`),
        api.get(`/workspaces/${workspaceId}/agents/${agentId}/analytics/timeseries?days=${days}`),
      ]);
      setEffectiveness(effRes.data);
      setGaps(gapRes.data);
      setTimeseries(tsRes.data);
    } catch (err) { handleSilent(err, "Analytics:fetch"); }
    setLoading(false);
  }, [workspaceId, agentId, days]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (!agentId) return null;
  if (loading) return <div className="flex items-center justify-center py-8 text-zinc-500 text-sm">Loading analytics...</div>;

  const summary = timeseries?.summary || {};
  const timeline = timeseries?.timeline || [];
  const topPerformers = effectiveness?.top_performers || [];
  const lowPerformers = effectiveness?.low_performers || [];
  const gapsList = gaps?.gaps || [];
  const topicCoverage = gaps?.topic_coverage || [];
  const catDist = gaps?.category_distribution || {};

  return (
    <div className="space-y-5" data-testid="training-analytics">
      {/* Period Selector */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-300">Training Analytics</h3>
        <div className="flex gap-1">
          {[7, 30, 90].map(d => (
            <button key={d} onClick={() => setDays(d)}
              className={`px-2.5 py-1 text-[10px] rounded-md ${days === d ? "bg-cyan-400/10 text-cyan-400" : "text-zinc-500 hover:text-zinc-300"}`}
              data-testid={`analytics-period-${d}d`}>
              {d}d
            </button>
          ))}
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-5 gap-2">
        <MiniStat label="Total Chunks" value={summary.total_chunks} color="text-cyan-400" />
        <MiniStat label="Sessions" value={summary.total_sessions} color="text-violet-400" />
        <MiniStat label="New (period)" value={summary.new_chunks_in_period} color="text-emerald-400" />
        <MiniStat label="Retrievals" value={summary.total_retrievals_in_period} color="text-amber-400" />
        <MiniStat label="Used" value={effectiveness?.chunks_used || 0} suffix={`/${effectiveness?.total_chunks || 0}`} color="text-zinc-300" />
      </div>

      {/* Time Series Chart */}
      {timeline.length > 0 && (
        <Card className="bg-zinc-900/60 border-zinc-800/60">
          <CardHeader className="p-3 pb-0">
            <CardTitle className="text-xs text-zinc-500">Knowledge Growth & Activity</CardTitle>
          </CardHeader>
          <CardContent className="p-3">
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={timeline} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
                <XAxis dataKey="date" tick={{ fill: "#555", fontSize: 9 }} tickFormatter={d => d.slice(5)} />
                <YAxis tick={{ fill: "#555", fontSize: 9 }} width={30} />
                <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #333", fontSize: 11, borderRadius: 8 }} />
                <Area type="monotone" dataKey="new_chunks" stroke="#22d3ee" fill="#22d3ee" fillOpacity={0.15} strokeWidth={1.5} name="New Chunks" />
                <Area type="monotone" dataKey="retrievals" stroke="#f59e0b" fill="#f59e0b" fillOpacity={0.1} strokeWidth={1.5} name="Retrievals" />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {/* Knowledge Gaps */}
      {gapsList.length > 0 && (
        <Card className="bg-zinc-900/60 border-zinc-800/60" data-testid="knowledge-gaps">
          <CardHeader className="p-3 pb-1">
            <CardTitle className="text-xs text-zinc-500 flex items-center gap-1.5">
              <AlertTriangle className="w-3 h-3 text-amber-400" /> Knowledge Gaps ({gapsList.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="p-3 pt-0 space-y-1.5">
            {gapsList.map((g, i) => (
              <div key={i} className="flex items-start gap-2.5 py-1.5 border-b border-zinc-800/20 last:border-0">
                <Badge variant="secondary" className={`text-[8px] mt-0.5 ${
                  g.severity === "high" ? "bg-red-500/10 text-red-400" :
                  g.severity === "medium" ? "bg-amber-500/10 text-amber-400" :
                  "bg-zinc-800 text-zinc-500"
                }`}>{g.severity}</Badge>
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-zinc-300">{g.skill}</p>
                  <p className="text-[10px] text-zinc-500">{g.suggestion}</p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Topic Coverage + Category Distribution */}
      <div className="grid grid-cols-2 gap-3">
        {topicCoverage.length > 0 && (
          <Card className="bg-zinc-900/60 border-zinc-800/60" data-testid="topic-coverage">
            <CardHeader className="p-3 pb-1">
              <CardTitle className="text-xs text-zinc-500">Topic Coverage</CardTitle>
            </CardHeader>
            <CardContent className="p-3 pt-0 space-y-1">
              {topicCoverage.slice(0, 8).map(t => (
                <div key={t.topic} className="flex items-center gap-2">
                  <span className="text-[10px] text-zinc-400 w-24 truncate">{t.topic}</span>
                  <div className="flex-1 h-1.5 bg-zinc-800 rounded-full">
                    <div className="h-full bg-cyan-400/60 rounded-full" style={{ width: `${Math.min((t.chunk_count / Math.max(...topicCoverage.map(x => x.chunk_count), 1)) * 100, 100)}%` }} />
                  </div>
                  <span className="text-[9px] text-zinc-500 w-6 text-right">{t.chunk_count}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        <Card className="bg-zinc-900/60 border-zinc-800/60" data-testid="category-distribution">
          <CardHeader className="p-3 pb-1">
            <CardTitle className="text-xs text-zinc-500">Category Mix</CardTitle>
          </CardHeader>
          <CardContent className="p-3 pt-0 space-y-1.5">
            {Object.entries(catDist).map(([cat, data]) => (
              <div key={cat} className="flex items-center justify-between text-[10px]">
                <span className="text-zinc-400 capitalize">{cat}</span>
                <div className="flex items-center gap-2">
                  <span className="text-zinc-500">{data.count} chunks</span>
                  <Badge variant="secondary" className={`text-[8px] ${data.avg_quality >= 0.7 ? "bg-emerald-500/10 text-emerald-400" : "bg-zinc-800 text-zinc-500"}`}>
                    q:{data.avg_quality}
                  </Badge>
                </div>
              </div>
            ))}
            {Object.keys(catDist).length === 0 && <p className="text-[10px] text-zinc-600">No data</p>}
          </CardContent>
        </Card>
      </div>

      {/* Top Performers */}
      {topPerformers.length > 0 && (
        <Card className="bg-zinc-900/60 border-zinc-800/60" data-testid="top-performers">
          <CardHeader className="p-3 pb-1">
            <CardTitle className="text-xs text-zinc-500 flex items-center gap-1.5">
              <ArrowUp className="w-3 h-3 text-emerald-400" /> Most Effective Chunks
            </CardTitle>
          </CardHeader>
          <CardContent className="p-3 pt-0 space-y-1">
            {topPerformers.slice(0, 5).map(c => (
              <div key={c.chunk_id} className="flex items-start gap-2 py-1 border-b border-zinc-800/20 last:border-0">
                <div className="flex-1 min-w-0">
                  <p className="text-[10px] text-zinc-400 line-clamp-1">{c.content}</p>
                  <div className="flex gap-2 mt-0.5 text-[9px] text-zinc-600">
                    <span>{c.topic}</span>
                    <span>{c.times_retrieved} retrievals</span>
                    <span>{c.times_helpful} helpful</span>
                  </div>
                </div>
                <span className="text-[10px] font-mono text-emerald-400">{Math.round(c.effectiveness_score * 10) / 10}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Low Performers */}
      {lowPerformers.length > 0 && (
        <Card className="bg-zinc-900/60 border-zinc-800/60" data-testid="low-performers">
          <CardHeader className="p-3 pb-1">
            <CardTitle className="text-xs text-zinc-500 flex items-center gap-1.5">
              <ArrowDown className="w-3 h-3 text-red-400" /> Least Effective (consider revising)
            </CardTitle>
          </CardHeader>
          <CardContent className="p-3 pt-0 space-y-1">
            {lowPerformers.slice(0, 5).map(c => (
              <div key={c.chunk_id} className="flex items-start gap-2 py-1 border-b border-zinc-800/20 last:border-0">
                <div className="flex-1 min-w-0">
                  <p className="text-[10px] text-zinc-400 line-clamp-1">{c.content}</p>
                  <div className="flex gap-2 mt-0.5 text-[9px] text-zinc-600">
                    <span>{c.topic}</span>
                    <span>{c.times_retrieved} retr / {c.times_helpful} helpful</span>
                  </div>
                </div>
                <span className="text-[10px] font-mono text-red-400">{Math.round((c.helpfulness_ratio || 0) * 100)}%</span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function MiniStat({ label, value, suffix, color }) {
  return (
    <div className="bg-zinc-900/50 border border-zinc-800/40 rounded-lg p-2 text-center">
      <p className="text-[9px] uppercase tracking-wider text-zinc-600">{label}</p>
      <p className={`text-lg font-bold mt-0.5 ${color}`}>{value || 0}<span className="text-[10px] text-zinc-600">{suffix || ""}</span></p>
    </div>
  );
}
