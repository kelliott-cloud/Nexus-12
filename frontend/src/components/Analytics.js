import { useState, useEffect, useCallback } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, RadarChart, Radar, PolarGrid,
  PolarAngleAxis, PolarRadiusAxis, AreaChart, Area
} from "recharts";
import { Zap, Clock, Code2, MessageSquare, TrendingUp, Crown, Lock } from "lucide-react";
import { api } from "@/App";

const AGENT_COLORS = {
  claude: "#D97757",
  chatgpt: "#10A37F",
  deepseek: "#4D6BFE",
  grok: "#F5F5F5",
};

const AGENT_NAMES = {
  claude: "Claude",
  chatgpt: "ChatGPT",
  deepseek: "DeepSeek",
  grok: "Grok",
};

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-3 shadow-xl">
      <p className="text-xs text-zinc-400 mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="text-sm font-medium" style={{ color: p.color }}>
          {p.name}: {typeof p.value === "number" ? p.value.toLocaleString() : p.value}
          {p.name.includes("time") || p.name.includes("Time") ? "ms" : ""}
        </p>
      ))}
    </div>
  );
};

export const Analytics = ({ workspaceId, userPlan }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchAnalytics = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/analytics`);
      setData(res.data);
    } catch (err) { handleSilent(err, "Analytics:op1"); }
    setLoading(false);
  }, [workspaceId]);

  useEffect(() => { fetchAnalytics(); }, [fetchAnalytics]);

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-zinc-600 text-sm">Loading analytics...</div>
  );

  const isEnterprise = userPlan === "enterprise";
  const overview = data?.overview || {};
  const models = data?.model_comparison || [];
  const timeline = data?.timeline || [];
  const patterns = data?.collaboration_patterns || [];

  // Prepare chart data
  const responseTimeData = models.map(m => ({
    name: AGENT_NAMES[m.agent] || m.agent,
    "Avg Response Time": m.avg_response_time_ms,
    "P95 Response Time": m.p95_response_time_ms,
    fill: AGENT_COLORS[m.agent] || "#666",
  }));

  const codeQualityData = models.map(m => ({
    name: AGENT_NAMES[m.agent] || m.agent,
    "Code Quality": m.avg_code_quality,
    fill: AGENT_COLORS[m.agent] || "#666",
  }));

  const pieData = models.map(m => ({
    name: AGENT_NAMES[m.agent] || m.agent,
    value: m.total_responses,
    color: AGENT_COLORS[m.agent] || "#666",
  }));

  const radarData = models.map(m => ({
    agent: AGENT_NAMES[m.agent] || m.agent,
    "Speed": Math.max(0, 100 - (m.avg_response_time_ms / 100)),
    "Code Quality": m.avg_code_quality,
    "Volume": Math.min(m.total_responses * 10, 100),
    "Code Output": Math.min(m.total_code_blocks * 15, 100),
    "Verbosity": Math.min(m.avg_content_length / 20, 100),
  }));

  const hasData = models.length > 0;

  return (
    <div className="h-full flex flex-col" data-testid="analytics-panel">
      <div className="px-6 py-4 border-b border-zinc-800/60 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-zinc-200" style={{ fontFamily: 'Syne, sans-serif' }}>
            AI Agent Analytics
          </h2>
          <Badge className="bg-amber-500/20 text-amber-400 text-[10px]">
            <Crown className="w-3 h-3 mr-1" /> PREMIUM
          </Badge>
        </div>
        <Button size="sm" variant="outline" onClick={fetchAnalytics} className="border-zinc-700 text-zinc-400 text-xs" data-testid="refresh-analytics">
          Refresh
        </Button>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-6 space-y-8">
          {!hasData ? (
            <div className="text-center py-16">
              <TrendingUp className="w-12 h-12 text-zinc-700 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-zinc-400 mb-2" style={{ fontFamily: 'Syne, sans-serif' }}>
                No analytics data yet
              </h3>
              <p className="text-sm text-zinc-600 max-w-sm mx-auto">
                Start AI collaborations to generate performance data. Analytics will appear after your first conversation.
              </p>
            </div>
          ) : (
            <>
              {/* Overview Cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="analytics-overview">
                <OverviewCard icon={MessageSquare} label="AI Responses" value={overview.total_ai_responses} />
                <OverviewCard icon={Clock} label="Avg Response" value={`${overview.avg_response_time_ms}ms`} />
                <OverviewCard icon={Zap} label="Top Performer" value={AGENT_NAMES[overview.top_performer] || "-"} accent={AGENT_COLORS[overview.top_performer]} />
                <OverviewCard icon={TrendingUp} label="Collaborations" value={overview.total_collaborations} />
              </div>

              {/* Response Time Chart */}
              <div className="p-5 rounded-xl bg-zinc-900/40 border border-zinc-800/60" data-testid="response-time-chart">
                <h3 className="text-sm font-semibold text-zinc-300 mb-4" style={{ fontFamily: 'Syne, sans-serif' }}>
                  Response Time Comparison
                </h3>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={responseTimeData} barGap={8}>
                    <XAxis dataKey="name" tick={{ fill: '#71717a', fontSize: 12 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: '#71717a', fontSize: 11 }} axisLine={false} tickLine={false} unit="ms" />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="Avg Response Time" radius={[4, 4, 0, 0]}>
                      {responseTimeData.map((entry, i) => <Cell key={i} fill={entry.fill} fillOpacity={0.8} />)}
                    </Bar>
                    <Bar dataKey="P95 Response Time" radius={[4, 4, 0, 0]}>
                      {responseTimeData.map((entry, i) => <Cell key={i} fill={entry.fill} fillOpacity={0.3} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Code Quality + Distribution */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="p-5 rounded-xl bg-zinc-900/40 border border-zinc-800/60" data-testid="code-quality-chart">
                  <h3 className="text-sm font-semibold text-zinc-300 mb-4" style={{ fontFamily: 'Syne, sans-serif' }}>
                    Code Quality Scores
                  </h3>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={codeQualityData} layout="vertical" barSize={20}>
                      <XAxis type="number" domain={[0, 100]} tick={{ fill: '#71717a', fontSize: 11 }} axisLine={false} tickLine={false} />
                      <YAxis type="category" dataKey="name" tick={{ fill: '#a1a1aa', fontSize: 12 }} axisLine={false} tickLine={false} width={80} />
                      <Tooltip content={<CustomTooltip />} />
                      <Bar dataKey="Code Quality" radius={[0, 4, 4, 0]}>
                        {codeQualityData.map((entry, i) => <Cell key={i} fill={entry.fill} fillOpacity={0.7} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div className="p-5 rounded-xl bg-zinc-900/40 border border-zinc-800/60" data-testid="distribution-chart">
                  <h3 className="text-sm font-semibold text-zinc-300 mb-4" style={{ fontFamily: 'Syne, sans-serif' }}>
                    Response Distribution
                  </h3>
                  <ResponsiveContainer width="100%" height={200}>
                    <PieChart>
                      <Pie data={pieData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={4} dataKey="value">
                        {pieData.map((entry, i) => <Cell key={i} fill={entry.color} fillOpacity={0.8} />)}
                      </Pie>
                      <Tooltip content={<CustomTooltip />} />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="flex justify-center gap-4 mt-2">
                    {pieData.map(d => (
                      <div key={d.name} className="flex items-center gap-1.5">
                        <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: d.color }} />
                        <span className="text-[10px] text-zinc-500">{d.name} ({d.value})</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Radar Chart - Model Comparison */}
              {radarData.length > 0 && (
                <div className="p-5 rounded-xl bg-zinc-900/40 border border-zinc-800/60" data-testid="radar-chart">
                  <h3 className="text-sm font-semibold text-zinc-300 mb-4" style={{ fontFamily: 'Syne, sans-serif' }}>
                    Model Capability Comparison
                  </h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <RadarChart data={[
                      { metric: "Speed", ...Object.fromEntries(radarData.map(r => [r.agent, r["Speed"]])) },
                      { metric: "Code Quality", ...Object.fromEntries(radarData.map(r => [r.agent, r["Code Quality"]])) },
                      { metric: "Volume", ...Object.fromEntries(radarData.map(r => [r.agent, r["Volume"]])) },
                      { metric: "Code Output", ...Object.fromEntries(radarData.map(r => [r.agent, r["Code Output"]])) },
                      { metric: "Verbosity", ...Object.fromEntries(radarData.map(r => [r.agent, r["Verbosity"]])) },
                    ]}>
                      <PolarGrid stroke="#27272a" />
                      <PolarAngleAxis dataKey="metric" tick={{ fill: '#71717a', fontSize: 11 }} />
                      <PolarRadiusAxis tick={false} axisLine={false} domain={[0, 100]} />
                      {radarData.map(r => (
                        <Radar key={r.agent} name={r.agent} dataKey={r.agent}
                          stroke={AGENT_COLORS[models.find(m => AGENT_NAMES[m.agent] === r.agent)?.agent] || "#666"}
                          fill={AGENT_COLORS[models.find(m => AGENT_NAMES[m.agent] === r.agent)?.agent] || "#666"}
                          fillOpacity={0.15} strokeWidth={2} />
                      ))}
                      <Tooltip content={<CustomTooltip />} />
                    </RadarChart>
                  </ResponsiveContainer>
                  <div className="flex justify-center gap-4 mt-2">
                    {models.map(m => (
                      <div key={m.agent} className="flex items-center gap-1.5">
                        <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: AGENT_COLORS[m.agent] }} />
                        <span className="text-[10px] text-zinc-500">{AGENT_NAMES[m.agent]}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Activity Timeline */}
              {timeline.length > 1 && (
                <div className="p-5 rounded-xl bg-zinc-900/40 border border-zinc-800/60" data-testid="timeline-chart">
                  <h3 className="text-sm font-semibold text-zinc-300 mb-4" style={{ fontFamily: 'Syne, sans-serif' }}>
                    Activity Timeline
                  </h3>
                  <ResponsiveContainer width="100%" height={160}>
                    <AreaChart data={timeline}>
                      <XAxis dataKey="timestamp" tick={{ fill: '#71717a', fontSize: 10 }} axisLine={false} tickLine={false}
                        tickFormatter={(v) => v ? new Date(v).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''} />
                      <YAxis tick={{ fill: '#71717a', fontSize: 11 }} axisLine={false} tickLine={false} />
                      <Tooltip content={<CustomTooltip />} />
                      <Area type="monotone" dataKey="count" stroke="#4D6BFE" fill="#4D6BFE" fillOpacity={0.1} strokeWidth={2} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Collaboration Patterns */}
              {patterns.length > 0 && (
                <div className="p-5 rounded-xl bg-zinc-900/40 border border-zinc-800/60" data-testid="patterns-section">
                  <h3 className="text-sm font-semibold text-zinc-300 mb-4" style={{ fontFamily: 'Syne, sans-serif' }}>
                    Collaboration Patterns
                  </h3>
                  <div className="space-y-2">
                    {patterns.map((p, i) => {
                      const [from, to] = p.pair.split("->");
                      return (
                        <div key={i} className="flex items-center gap-3 py-1.5">
                          <div className="flex items-center gap-1.5">
                            <div className="w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold"
                              style={{ backgroundColor: AGENT_COLORS[from], color: from === 'grok' ? '#09090b' : '#fff' }}>
                              {(AGENT_NAMES[from] || from)[0]}
                            </div>
                            <span className="text-xs text-zinc-500">&rarr;</span>
                            <div className="w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold"
                              style={{ backgroundColor: AGENT_COLORS[to], color: to === 'grok' ? '#09090b' : '#fff' }}>
                              {(AGENT_NAMES[to] || to)[0]}
                            </div>
                          </div>
                          <span className="text-xs text-zinc-400">{AGENT_NAMES[from]} followed by {AGENT_NAMES[to]}</span>
                          <span className="ml-auto text-xs font-mono text-zinc-500">{p.count}x</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Detailed Model Table */}
              <div className="p-5 rounded-xl bg-zinc-900/40 border border-zinc-800/60" data-testid="model-table">
                <h3 className="text-sm font-semibold text-zinc-300 mb-4" style={{ fontFamily: 'Syne, sans-serif' }}>
                  Detailed Model Statistics
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-zinc-500 text-xs font-mono border-b border-zinc-800">
                        <th className="text-left py-2 pr-4">Model</th>
                        <th className="text-right py-2 px-4">Responses</th>
                        <th className="text-right py-2 px-4">Avg Time</th>
                        <th className="text-right py-2 px-4">P95 Time</th>
                        <th className="text-right py-2 px-4">Code Quality</th>
                        <th className="text-right py-2 px-4">Code Blocks</th>
                        <th className="text-right py-2 pl-4">Avg Length</th>
                      </tr>
                    </thead>
                    <tbody>
                      {models.map(m => (
                        <tr key={m.agent} className="border-b border-zinc-800/40 hover:bg-zinc-800/20">
                          <td className="py-2.5 pr-4">
                            <div className="flex items-center gap-2">
                              <div className="w-4 h-4 rounded-full" style={{ backgroundColor: AGENT_COLORS[m.agent] }} />
                              <span className="text-zinc-200">{AGENT_NAMES[m.agent]}</span>
                            </div>
                          </td>
                          <td className="text-right py-2.5 px-4 text-zinc-400 font-mono">{m.total_responses}</td>
                          <td className="text-right py-2.5 px-4 text-zinc-400 font-mono">{m.avg_response_time_ms}ms</td>
                          <td className="text-right py-2.5 px-4 text-zinc-400 font-mono">{m.p95_response_time_ms}ms</td>
                          <td className="text-right py-2.5 px-4">
                            <span className={`font-mono ${m.avg_code_quality >= 70 ? 'text-emerald-400' : m.avg_code_quality >= 50 ? 'text-amber-400' : 'text-zinc-400'}`}>
                              {m.avg_code_quality}
                            </span>
                          </td>
                          <td className="text-right py-2.5 px-4 text-zinc-400 font-mono">{m.total_code_blocks}</td>
                          <td className="text-right py-2.5 pl-4 text-zinc-400 font-mono">{m.avg_content_length}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      </ScrollArea>
    </div>
  );
};

const OverviewCard = ({ icon: Icon, label, value, accent }) => (
  <div className="p-4 rounded-xl bg-zinc-900/40 border border-zinc-800/60">
    <Icon className="w-4 h-4 text-zinc-500 mb-2" />
    <div className="text-2xl font-bold text-zinc-200" style={{ fontFamily: 'Syne, sans-serif', color: accent || undefined }}>
      {value ?? 0}
    </div>
    <div className="text-[10px] text-zinc-600 font-mono uppercase tracking-wider">{label}</div>
  </div>
);

export default Analytics;
