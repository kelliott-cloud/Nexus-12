import { useState, useEffect } from "react";
import { api } from "@/App";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Loader2, ArrowLeftRight } from "lucide-react";
import { toast } from "sonner";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";

const COLORS = ["#06b6d4", "#8b5cf6", "#f59e0b", "#10b981", "#ec4899", "#3b82f6"];

export default function NAVCCompare({ workspaceId, runs = [], onClose }) {
  const [selectedIds, setSelectedIds] = useState([]);
  const [comparison, setComparison] = useState(null);
  const [loading, setLoading] = useState(false);

  const completedRuns = runs.filter(r => r.status === "completed" && r.metrics);

  const toggleSelect = (runId) => {
    setSelectedIds(prev =>
      prev.includes(runId) ? prev.filter(id => id !== runId) : prev.length < 6 ? [...prev, runId] : prev
    );
  };

  const compare = async () => {
    if (selectedIds.length < 2) { toast.error("Select at least 2 runs"); return; }
    setLoading(true);
    try {
      const res = await api.get(`/workspaces/${workspaceId}/turboquant/compare?run_ids=${selectedIds.join(",")}`);
      setComparison(res.data);
    } catch (e) { toast.error(e.response?.data?.detail || "Compare failed"); }
    setLoading(false);
  };

  const ChartCard = ({ title, data, unit = "", color = "#06b6d4" }) => (
    <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/40">
      <p className="text-xs font-medium text-zinc-300 mb-3">{title}</p>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
          <XAxis dataKey="name" tick={{ fill: "#71717a", fontSize: 10 }} />
          <YAxis tick={{ fill: "#71717a", fontSize: 10 }} />
          <Tooltip
            contentStyle={{ backgroundColor: "#18181b", border: "1px solid #3f3f46", borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: "#e4e4e7" }}
            formatter={(v) => [`${v}${unit}`, title]}
          />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );

  return (
    <div className="space-y-4" data-testid="tq-compare">
      {/* Run Selector */}
      <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/40">
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs font-medium text-zinc-300">Select runs to compare (2-6)</p>
          <Button size="sm" onClick={compare} disabled={selectedIds.length < 2 || loading}
            className="bg-cyan-600 hover:bg-cyan-500 text-white text-xs h-7" data-testid="tq-compare-btn">
            {loading ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <ArrowLeftRight className="w-3 h-3 mr-1" />}
            Compare ({selectedIds.length})
          </Button>
        </div>
        <div className="space-y-1.5 max-h-48 overflow-y-auto">
          {completedRuns.map(r => (
            <label key={r.run_id} className={`flex items-center gap-3 p-2 rounded-lg cursor-pointer transition-colors ${
              selectedIds.includes(r.run_id) ? "bg-cyan-500/10 border border-cyan-500/20" : "bg-zinc-950/50 border border-zinc-800/30 hover:border-zinc-700"
            }`}>
              <input type="checkbox" checked={selectedIds.includes(r.run_id)} onChange={() => toggleSelect(r.run_id)}
                className="rounded border-zinc-700" />
              <span className="text-xs text-zinc-300 flex-1">{r.run_id}</span>
              <Badge className="text-[9px] bg-zinc-800 text-zinc-400">{r.metrics?.config?.bit_width || "?"}b</Badge>
              <span className="text-[10px] text-zinc-500">{r.metrics?.memory?.compression_ratio}x</span>
            </label>
          ))}
          {completedRuns.length === 0 && <p className="text-xs text-zinc-500 py-4 text-center">No completed runs to compare</p>}
        </div>
      </div>

      {/* Comparison Charts */}
      {comparison && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ChartCard title="Compression Ratio" data={comparison.chart_data?.compression || []} unit="x" />
            <ChartCard title="Memory Saved (%)" data={comparison.chart_data?.memory_saved || []} unit="%" />
            <ChartCard title="MSE (lower = better)" data={comparison.chart_data?.mse || []} />
            <ChartCard title="SNR dB (higher = better)" data={comparison.chart_data?.snr || []} unit=" dB" />
          </div>

          {/* Best picks */}
          {comparison.best && (
            <div className="flex gap-3 text-xs text-zinc-400">
              <span>Best compression: <span className="text-cyan-400">{comparison.best.compression}</span></span>
              <span>Best quality: <span className="text-emerald-400">{comparison.best.quality}</span></span>
            </div>
          )}

          {/* Run details table */}
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-zinc-800 text-zinc-500">
                  <th className="text-left py-2 px-3">Profile</th>
                  <th className="text-left py-2 px-3">Type</th>
                  <th className="text-right py-2 px-3">Bits</th>
                  <th className="text-right py-2 px-3">Ratio</th>
                  <th className="text-right py-2 px-3">Saved</th>
                  <th className="text-right py-2 px-3">MSE</th>
                  <th className="text-right py-2 px-3">SNR</th>
                  <th className="text-right py-2 px-3">Eligible</th>
                </tr>
              </thead>
              <tbody>
                {comparison.runs?.map((r, i) => (
                  <tr key={r.run_id} className="border-b border-zinc-800/40 hover:bg-zinc-900/30">
                    <td className="py-2 px-3 text-zinc-200">{r.profile_name}</td>
                    <td className="py-2 px-3"><Badge className="text-[9px] bg-zinc-800 text-zinc-400">{r.target_type}</Badge></td>
                    <td className="py-2 px-3 text-right text-zinc-300">{r.bit_width}b</td>
                    <td className="py-2 px-3 text-right text-cyan-400">{r.metrics?.memory?.compression_ratio}x</td>
                    <td className="py-2 px-3 text-right text-emerald-400">{r.metrics?.memory?.memory_reduction_pct}%</td>
                    <td className="py-2 px-3 text-right text-amber-400">{r.metrics?.distortion?.mse?.toFixed(6)}</td>
                    <td className="py-2 px-3 text-right text-violet-400">{r.metrics?.distortion?.snr_db?.toFixed(1)}</td>
                    <td className="py-2 px-3 text-right">{r.promotion_eval?.eligible ? <Badge className="bg-emerald-500/15 text-emerald-400 text-[9px]">Yes</Badge> : <Badge className="bg-zinc-800 text-zinc-500 text-[9px]">No</Badge>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
