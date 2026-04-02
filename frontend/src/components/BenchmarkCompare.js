import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { handleSilent } from "@/lib/errorHandler";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import {
  Target, TrendingUp, BarChart3, ChevronUp, ChevronDown, Minus, Loader2
} from "lucide-react";
import { FeatureHelp, FEATURE_HELP } from "@/components/FeatureHelp";

export default function BenchmarkCompare({ workspaceId }) {
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState("");
  const [comparison, setComparison] = useState([]);
  const [trend, setTrend] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchAgents = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/agents`);
      const list = res.data.agents || res.data || [];
      setAgents(list);
      if (list.length > 0 && !selectedAgent) setSelectedAgent(list[0].agent_id);
    } catch (err) { handleSilent(err, "BC:agents"); }
    setLoading(false);
  }, [workspaceId, selectedAgent]);

  const fetchComparison = useCallback(async () => {
    if (!selectedAgent) return;
    try {
      const res = await api.get(`/workspaces/${workspaceId}/agents/${selectedAgent}/benchmarks/compare`);
      setComparison(res.data.comparison || []);
      setTrend(res.data.trend || []);
    } catch (err) { handleSilent(err, "BC:compare"); }
  }, [workspaceId, selectedAgent]);

  useEffect(() => { fetchAgents(); }, [fetchAgents]);
  useEffect(() => { if (selectedAgent) fetchComparison(); }, [selectedAgent, fetchComparison]);

  const scoreColor = (s) => s >= 80 ? "text-emerald-400" : s >= 50 ? "text-amber-400" : "text-red-400";
  const trendIcon = (curr, prev) => {
    if (!prev) return <Minus className="w-3 h-3 text-zinc-500" />;
    if (curr > prev) return <ChevronUp className="w-3 h-3 text-emerald-400" />;
    if (curr < prev) return <ChevronDown className="w-3 h-3 text-red-400" />;
    return <Minus className="w-3 h-3 text-zinc-500" />;
  };

  if (loading) return <div className="flex-1 flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-zinc-500" /></div>;

  return (
    <div className="flex-1 overflow-y-auto p-6" data-testid="benchmark-compare-panel">
      <div className="max-w-5xl mx-auto space-y-6">
        <FeatureHelp featureId="benchmark-compare" {...FEATURE_HELP["benchmark-compare"]} />
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100">Benchmark Comparison</h2>
            <p className="text-sm text-zinc-500 mt-1">Compare agent performance across benchmark runs</p>
          </div>
          <Select value={selectedAgent} onValueChange={setSelectedAgent}>
            <SelectTrigger className="w-48 bg-zinc-800 border-zinc-700" data-testid="bc-agent-select"><SelectValue placeholder="Select agent" /></SelectTrigger>
            <SelectContent>{agents.map(a => <SelectItem key={a.agent_id} value={a.agent_id}>{a.name}</SelectItem>)}</SelectContent>
          </Select>
        </div>

        {comparison.length === 0 ? (
          <Card className="bg-zinc-900 border-zinc-800"><CardContent className="py-12 text-center text-zinc-500">No benchmark runs to compare. Run benchmarks first.</CardContent></Card>
        ) : (
          <>
            {/* Score Trend */}
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader><CardTitle className="text-sm text-zinc-100">Score Trend</CardTitle></CardHeader>
              <CardContent>
                <div className="flex items-end gap-3 h-32">
                  {comparison.map((run, i) => (
                    <div key={run.run_id} className="flex-1 flex flex-col items-center gap-1">
                      <div className="flex items-center gap-1">
                        {trendIcon(run.avg_score, i > 0 ? comparison[i-1].avg_score : null)}
                        <span className={`text-sm font-bold ${scoreColor(run.avg_score)}`}>{run.avg_score}</span>
                      </div>
                      <div className="w-full bg-zinc-800 rounded-full overflow-hidden" style={{ height: `${Math.max(run.avg_score, 5)}%` }}>
                        <div className={`w-full h-full rounded-full ${run.avg_score >= 80 ? "bg-emerald-500" : run.avg_score >= 50 ? "bg-amber-500" : "bg-red-500"}`} />
                      </div>
                      <span className="text-xs text-zinc-600 truncate max-w-full">{run.started_at?.slice(5, 10)}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Detailed Comparison Table */}
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader><CardTitle className="text-sm text-zinc-100">Run-by-Run Comparison</CardTitle></CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-zinc-800">
                        <th className="text-left py-2 px-3 text-zinc-500 font-medium">Metric</th>
                        {comparison.map(run => (
                          <th key={run.run_id} className="text-center py-2 px-3 text-zinc-400 font-medium">
                            <div className="text-xs">{run.suite_name}</div>
                            <div className="text-xs text-zinc-600">{run.started_at?.slice(0, 10)}</div>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        { label: "Avg Score", key: "avg_score" },
                        { label: "Pass Rate", key: "pass_rate", suffix: "%" },
                        { label: "Passed", key: "passed" },
                        { label: "Total Cases", key: "total_cases" },
                      ].map(({ label, key, suffix }) => (
                        <tr key={key} className="border-b border-zinc-800/50">
                          <td className="py-2 px-3 text-zinc-300">{label}</td>
                          {comparison.map(run => (
                            <td key={run.run_id} className={`text-center py-2 px-3 font-mono ${key === "avg_score" || key === "pass_rate" ? scoreColor(run[key]) : "text-zinc-300"}`}>
                              {run[key]}{suffix || ""}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>

            {/* Category Breakdown */}
            {comparison.length > 0 && comparison[0].by_category && (
              <Card className="bg-zinc-900 border-zinc-800">
                <CardHeader><CardTitle className="text-sm text-zinc-100">Category Breakdown (Latest Run)</CardTitle></CardHeader>
                <CardContent className="space-y-3">
                  {Object.entries(comparison[comparison.length - 1].by_category || {}).map(([cat, data]) => (
                    <div key={cat} className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="text-zinc-300 capitalize">{cat}</span>
                        <span className={scoreColor(data.avg_score)}>{data.avg_score} ({data.passed}/{data.total} passed)</span>
                      </div>
                      <Progress value={data.avg_score} className="h-1.5" />
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </>
        )}
      </div>
    </div>
  );
}
