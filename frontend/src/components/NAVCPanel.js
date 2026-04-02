import { useState, useEffect } from "react";
import { api } from "@/App";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Loader2, Zap, Play, BarChart3, Check, X, ArrowRight, Trash2, RefreshCw, RotateCcw, Link2, Unlink } from "lucide-react";
import { toast } from "sonner";
import NAVCCompare from "@/components/NAVCCompare";

const BIT_WIDTHS = [2, 4, 8];
const TARGET_TYPES = [
  { id: "vector_index", label: "Vector Index", desc: "Compress knowledge embeddings" },
  { id: "kv_cache", label: "KV Cache", desc: "Compress inference key-value cache" },
];
const KV_MODELS = [
  { id: "custom", label: "Custom (8L×8H)" },
  { id: "gpt2-small", label: "GPT-2 Small (12L×12H)" },
  { id: "llama-3-8b", label: "Llama 3 8B (32L×32H)" },
  { id: "mistral-7b", label: "Mistral 7B (32L×32H)" },
];

const STATUS_COLORS = {
  queued: "bg-zinc-700 text-zinc-300",
  running: "bg-amber-500/20 text-amber-400",
  completed: "bg-emerald-500/20 text-emerald-400",
  failed: "bg-red-500/20 text-red-400",
  cancelled: "bg-zinc-800 text-zinc-500",
};

export default function NAVCPanel({ workspaceId }) {
  const [tab, setTab] = useState("profiles");
  const [profiles, setProfiles] = useState([]);
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [targetType, setTargetType] = useState("vector_index");
  const [bitWidth, setBitWidth] = useState(4);
  const [enableResidual, setEnableResidual] = useState(true);
  const [kvModel, setKvModel] = useState("custom");
  const [selectedRun, setSelectedRun] = useState(null);
  const [promotions, setPromotions] = useState([]);
  const [binding, setBinding] = useState(null);

  useEffect(() => { loadData(); }, [workspaceId]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [profileRes, runRes, promoRes, bindRes] = await Promise.all([
        api.get(`/workspaces/${workspaceId}/turboquant/profiles`),
        api.get(`/workspaces/${workspaceId}/turboquant/runs`),
        api.get(`/workspaces/${workspaceId}/turboquant/promotions`).catch(() => ({ data: { promotions: [] } })),
        api.get(`/workspaces/${workspaceId}/turboquant/binding`).catch(() => ({ data: { binding: null } })),
      ]);
      setProfiles(profileRes.data?.profiles || []);
      setRuns(runRes.data?.runs || []);
      setPromotions(promoRes.data?.promotions || []);
      setBinding(bindRes.data?.binding || null);
    } catch { toast.error("Failed to load NAVC data"); }
    setLoading(false);
  };

  const createProfile = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await api.post(`/workspaces/${workspaceId}/turboquant/profiles`, {
        name: newName, target_type: targetType, bit_width: bitWidth,
        enable_residual: enableResidual, rotation_seed: 42,
        kv_config: targetType === "kv_cache" ? { model_name: kvModel } : null,
      });
      toast.success("Profile created");
      setNewName("");
      loadData();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
    setCreating(false);
  };

  const deleteProfile = async (profileId) => {
    try {
      await api.delete(`/workspaces/${workspaceId}/turboquant/profiles/${profileId}`);
      toast.success("Profile deleted");
      loadData();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const startRun = async (profileId) => {
    try {
      await api.post(`/workspaces/${workspaceId}/turboquant/runs`, {
        profile_id: profileId, run_baseline: true,
      });
      toast.success("Benchmark started — will complete in background");
      setTimeout(loadData, 2000);
      setTimeout(loadData, 8000);
    } catch (e) { toast.error(e.response?.data?.detail || "Failed to start run"); }
  };

  const cancelRun = async (runId) => {
    try {
      await api.post(`/workspaces/${workspaceId}/turboquant/runs/${runId}/cancel`);
      toast.success("Run cancelled");
      loadData();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const promoteRun = async (runId) => {
    try {
      await api.post(`/workspaces/${workspaceId}/turboquant/promotions`, {
        run_id: runId, target_binding: "knowledge_retrieval", notes: "",
      });
      toast.success("Run promoted!");
      loadData();
    } catch (e) { toast.error(e.response?.data?.detail || "Promotion failed"); }
  };

  const rollbackPromotion = async (promoId) => {
    try {
      await api.post(`/workspaces/${workspaceId}/turboquant/promotions/${promoId}/rollback`);
      toast.success("Promotion rolled back");
      loadData();
    } catch (e) { toast.error(e.response?.data?.detail || "Rollback failed"); }
  };

  const bindPromotion = async (promoId) => {
    try {
      await api.post(`/workspaces/${workspaceId}/turboquant/bind`, { promotion_id: promoId });
      toast.success("Bound to workspace retrieval");
      loadData();
    } catch (e) { toast.error(e.response?.data?.detail || "Bind failed"); }
  };

  const unbind = async () => {
    try {
      await api.delete(`/workspaces/${workspaceId}/turboquant/binding`);
      toast.success("Binding removed");
      loadData();
    } catch (e) { toast.error(e.response?.data?.detail || "Unbind failed"); }
  };

  const tabs = [
    { key: "profiles", label: "Profiles" },
    { key: "runs", label: "Runs" },
    { key: "compare", label: "Compare" },
    { key: "promotions", label: "Promotions" },
    { key: "detail", label: "Run Detail", hidden: !selectedRun },
  ];

  if (loading) return <div className="p-8 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-zinc-500" /></div>;

  return (
    <div className="p-6 space-y-6" data-testid="turboquant-panel">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-cyan-500 flex items-center justify-center">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-zinc-100" style={{ fontFamily: 'Syne, sans-serif' }}>Nexus Adaptive Vector Compression</h2>
            <p className="text-xs text-zinc-500">NAVC</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={loadData} className="border-zinc-700 text-zinc-400" data-testid="tq-refresh">
          <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Refresh
        </Button>
      </div>

      {/* Feature Description */}
      <div className="rounded-xl bg-zinc-900/40 border border-zinc-800/50 p-4" data-testid="navc-description">
        <p className="text-sm text-zinc-300 leading-relaxed">
          NAVC compresses high-dimensional vectors and KV-cache tensors using a three-stage pipeline: deterministic random rotation, configurable-bitwidth scalar quantization, and optional 1-bit QJL residual correction. Create compression profiles, benchmark against your workspace data, review quality gates, and deploy promoted configurations to production retrieval — all without leaving Nexus.
        </p>
        <div className="flex flex-wrap gap-3 mt-3">
          <span className="text-[10px] px-2 py-1 rounded-md bg-violet-500/10 text-violet-400 border border-violet-500/20">2/4/8-bit quantization</span>
          <span className="text-[10px] px-2 py-1 rounded-md bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">KV-cache compression</span>
          <span className="text-[10px] px-2 py-1 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Embedding index compression</span>
          <span className="text-[10px] px-2 py-1 rounded-md bg-amber-500/10 text-amber-400 border border-amber-500/20">Promotion gates</span>
          <span className="text-[10px] px-2 py-1 rounded-md bg-pink-500/10 text-pink-400 border border-pink-500/20">Deployment binding</span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-zinc-800">
        {tabs.filter(t => !t.hidden).map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors ${
              tab === t.key ? "text-zinc-100 border-cyan-500" : "text-zinc-500 border-transparent hover:text-zinc-300"
            }`} data-testid={`tq-tab-${t.key}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Profiles Tab */}
      {tab === "profiles" && (
        <div className="space-y-4">
          {/* Create Profile */}
          <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/60 space-y-3" data-testid="tq-create-profile">
            <p className="text-xs font-medium text-zinc-300">New Compression Profile</p>
            <div className="flex items-end gap-3 flex-wrap">
              <div className="flex-1 min-w-[200px]">
                <Input value={newName} onChange={e => setNewName(e.target.value)} placeholder="Profile name..."
                  className="bg-zinc-950 border-zinc-800 text-sm" data-testid="tq-profile-name" />
              </div>
              <select value={targetType} onChange={e => setTargetType(e.target.value)}
                className="bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-300" data-testid="tq-target-type">
                {TARGET_TYPES.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
              </select>
              {targetType === "kv_cache" && (
                <select value={kvModel} onChange={e => setKvModel(e.target.value)}
                  className="bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-300" data-testid="tq-kv-model">
                  {KV_MODELS.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
                </select>
              )}
              <select value={bitWidth} onChange={e => setBitWidth(Number(e.target.value))}
                className="bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-300" data-testid="tq-bit-width">
                {BIT_WIDTHS.map(b => <option key={b} value={b}>{b}-bit</option>)}
              </select>
              <label className="flex items-center gap-1.5 text-xs text-zinc-400">
                <input type="checkbox" checked={enableResidual} onChange={e => setEnableResidual(e.target.checked)}
                  className="rounded border-zinc-700" data-testid="tq-residual" />
                QJL Residual
              </label>
              <Button onClick={createProfile} disabled={creating || !newName.trim()}
                className="bg-cyan-600 hover:bg-cyan-500 text-white text-xs" data-testid="tq-create-btn">
                {creating ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <Zap className="w-3.5 h-3.5 mr-1" />}
                Create
              </Button>
            </div>
          </div>

          {/* Profile List */}
          {profiles.length === 0 ? (
            <div className="text-center py-12 text-zinc-500 text-sm">No compression profiles yet. Create one above.</div>
          ) : (
            <div className="space-y-2">
              {profiles.map(p => (
                <div key={p.profile_id} className="flex items-center justify-between p-4 rounded-xl bg-zinc-950/50 border border-zinc-800/40" data-testid={`tq-profile-${p.profile_id}`}>
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-8 h-8 rounded-lg bg-violet-500/15 flex items-center justify-center shrink-0">
                      <Zap className="w-4 h-4 text-violet-400" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-zinc-200 truncate">{p.name}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <Badge className="text-[9px] bg-zinc-800 text-zinc-400">{p.target_type}</Badge>
                        <Badge className="text-[9px] bg-cyan-500/15 text-cyan-400">{p.bit_width}-bit</Badge>
                        {p.enable_residual && <Badge className="text-[9px] bg-violet-500/15 text-violet-400">QJL</Badge>}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Button size="sm" variant="outline" onClick={() => startRun(p.profile_id)}
                      className="text-xs border-zinc-700 text-emerald-400 h-7" data-testid={`tq-run-${p.profile_id}`}>
                      <Play className="w-3 h-3 mr-1" /> Benchmark
                    </Button>
                    <button onClick={() => deleteProfile(p.profile_id)} className="p-1.5 text-zinc-600 hover:text-red-400 transition-colors">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Runs Tab */}
      {tab === "runs" && (
        <div className="space-y-2">
          {runs.length === 0 ? (
            <div className="text-center py-12 text-zinc-500 text-sm">No benchmark runs yet. Start one from a profile.</div>
          ) : (
            runs.map(r => {
              const profile = profiles.find(p => p.profile_id === r.profile_id);
              return (
                <div key={r.run_id} className="p-4 rounded-xl bg-zinc-950/50 border border-zinc-800/40 cursor-pointer hover:border-zinc-700 transition-colors"
                  onClick={() => { setSelectedRun(r); setTab("detail"); }} data-testid={`tq-run-row-${r.run_id}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Badge className={`text-[10px] ${STATUS_COLORS[r.status] || STATUS_COLORS.queued}`}>{r.status}</Badge>
                      <span className="text-sm text-zinc-200">{profile?.name || r.profile_id}</span>
                      {r.metrics && (
                        <span className="text-xs text-zinc-500">
                          {r.metrics.memory?.compression_ratio}x compression · {r.metrics.memory?.memory_reduction_pct}% saved
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {r.promotion_eval?.eligible && (
                        <Badge className="text-[9px] bg-emerald-500/15 text-emerald-400">Promotable</Badge>
                      )}
                      {r.status === "running" && (
                        <button onClick={(e) => { e.stopPropagation(); cancelRun(r.run_id); }}
                          className="text-xs text-red-400 hover:text-red-300">Cancel</button>
                      )}
                      <ArrowRight className="w-3.5 h-3.5 text-zinc-600" />
                    </div>
                  </div>
                  {r.status === "running" && (
                    <div className="mt-2 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                      <div className="h-full bg-cyan-500 rounded-full transition-all" style={{ width: `${r.progress || 0}%` }} />
                    </div>
                  )}
                  {r.error && <p className="mt-1 text-xs text-red-400">{r.error}</p>}
                </div>
              );
            })
          )}
        </div>
      )}

      {/* Compare Tab */}
      {tab === "compare" && (
        <NAVCCompare workspaceId={workspaceId} runs={runs} />
      )}

      {/* Promotions Tab */}
      {tab === "promotions" && (
        <div className="space-y-4">
          {/* Active Binding */}
          {binding && (
            <div className="p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/20" data-testid="tq-active-binding">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Link2 className="w-4 h-4 text-emerald-400" />
                  <div>
                    <p className="text-xs font-medium text-emerald-300">Active Deployment Binding</p>
                    <p className="text-[10px] text-zinc-500">Target: {binding.target_binding} · Bound {new Date(binding.bound_at).toLocaleDateString()}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge className="text-[9px] bg-emerald-500/15 text-emerald-400">
                    {binding.metrics_snapshot?.memory?.compression_ratio}x compression
                  </Badge>
                  <Button size="sm" variant="outline" onClick={unbind}
                    className="text-xs border-zinc-700 text-red-400 h-7" data-testid="tq-unbind">
                    <Unlink className="w-3 h-3 mr-1" /> Unbind
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Promotion List */}
          {promotions.length === 0 ? (
            <div className="text-center py-12 text-zinc-500 text-sm">
              No promotions yet. Complete a benchmark run and promote eligible results.
            </div>
          ) : (
            <div className="space-y-2">
              {promotions.map(p => (
                <div key={p.promotion_id} className={`p-4 rounded-xl border ${
                  p.status === "active" ? "bg-zinc-950/50 border-emerald-500/20" : "bg-zinc-950/30 border-zinc-800/30 opacity-60"
                }`} data-testid={`tq-promo-${p.promotion_id}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Badge className={`text-[10px] ${p.status === "active" ? "bg-emerald-500/15 text-emerald-400" : "bg-zinc-800 text-zinc-500"}`}>
                        {p.status}
                      </Badge>
                      <span className="text-xs text-zinc-300">{p.target_binding}</span>
                      <span className="text-[10px] text-zinc-500">
                        {p.metrics_snapshot?.memory?.compression_ratio}x · {p.metrics_snapshot?.memory?.memory_reduction_pct}% saved
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      {p.status === "active" && !binding && (
                        <Button size="sm" variant="outline" onClick={() => bindPromotion(p.promotion_id)}
                          className="text-xs border-zinc-700 text-cyan-400 h-7" data-testid={`tq-bind-${p.promotion_id}`}>
                          <Link2 className="w-3 h-3 mr-1" /> Deploy
                        </Button>
                      )}
                      {p.status === "active" && (
                        <Button size="sm" variant="outline" onClick={() => rollbackPromotion(p.promotion_id)}
                          className="text-xs border-zinc-700 text-amber-400 h-7" data-testid={`tq-rollback-${p.promotion_id}`}>
                          <RotateCcw className="w-3 h-3 mr-1" /> Rollback
                        </Button>
                      )}
                    </div>
                  </div>
                  <p className="text-[10px] text-zinc-600 mt-1">
                    Run: {p.run_id} · Promoted {new Date(p.promoted_at).toLocaleString()}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Run Detail Tab */}
      {tab === "detail" && selectedRun && (
        <div className="space-y-4" data-testid="tq-run-detail">
          <button onClick={() => setTab("runs")} className="text-xs text-zinc-500 hover:text-zinc-300">
            &larr; Back to runs
          </button>

          <div className="flex items-center gap-3">
            <Badge className={`${STATUS_COLORS[selectedRun.status]}`}>{selectedRun.status}</Badge>
            <span className="text-sm text-zinc-300 font-mono">{selectedRun.run_id}</span>
            {selectedRun.promotion_eval?.eligible && (
              <Button size="sm" onClick={() => promoteRun(selectedRun.run_id)}
                className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs h-7 ml-auto" data-testid="tq-promote-run">
                <ArrowRight className="w-3 h-3 mr-1" /> Promote
              </Button>
            )}
          </div>

          {selectedRun.metrics && (
            <>
              {/* Metrics Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  { label: "Compression", value: `${selectedRun.metrics.memory?.compression_ratio}x`, color: "text-cyan-400" },
                  { label: "Memory Saved", value: `${selectedRun.metrics.memory?.memory_reduction_pct}%`, color: "text-emerald-400" },
                  { label: "MSE", value: selectedRun.metrics.distortion?.mse?.toFixed(6), color: "text-amber-400" },
                  { label: "SNR", value: `${selectedRun.metrics.distortion?.snr_db?.toFixed(1)} dB`, color: "text-violet-400" },
                ].map(m => (
                  <div key={m.label} className="p-3 rounded-lg bg-zinc-900/50 border border-zinc-800/40">
                    <p className="text-[10px] text-zinc-500 uppercase">{m.label}</p>
                    <p className={`text-xl font-bold mt-1 ${m.color}`}>{m.value}</p>
                  </div>
                ))}
              </div>

              {/* Gates */}
              <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/40">
                <p className="text-xs font-medium text-zinc-300 mb-3">Promotion Gates</p>
                <div className="flex flex-wrap gap-3">
                  {Object.entries(selectedRun.metrics.gates || {}).filter(([k]) => k !== "all_pass").map(([key, pass]) => (
                    <div key={key} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs ${pass ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"}`}>
                      {pass ? <Check className="w-3 h-3" /> : <X className="w-3 h-3" />}
                      {key.replace("_pass", "")}
                    </div>
                  ))}
                </div>

              {/* KV Cache: Attention Quality */}
              {selectedRun.metrics.attention_quality && (
                <div className="mt-3 p-3 rounded-lg bg-zinc-950/50 border border-zinc-800/30">
                  <p className="text-[10px] text-zinc-500 uppercase mb-2">Attention Quality</p>
                  <div className="flex gap-4 text-xs">
                    {selectedRun.metrics.attention_quality.output_cosine_similarity != null && (
                      <span className="text-cyan-400">Cosine: {selectedRun.metrics.attention_quality.output_cosine_similarity}</span>
                    )}
                    {selectedRun.metrics.attention_quality.attention_kl_div != null && (
                      <span className="text-amber-400">KL Div: {selectedRun.metrics.attention_quality.attention_kl_div}</span>
                    )}
                  </div>
                </div>
              )}

              {/* KV Cache: Per-Layer Breakdown */}
              {selectedRun.metrics.per_layer && selectedRun.metrics.per_layer.length > 0 && (
                <div className="mt-3 p-3 rounded-lg bg-zinc-950/50 border border-zinc-800/30">
                  <p className="text-[10px] text-zinc-500 uppercase mb-2">Per-Layer Distortion</p>
                  <div className="space-y-1 max-h-40 overflow-y-auto text-xs">
                    {selectedRun.metrics.per_layer.map(l => (
                      <div key={l.layer} className="flex items-center gap-3 text-zinc-400">
                        <span className="w-16 text-zinc-500">Layer {l.layer}</span>
                        <span className="w-12">{l.bit_width}b</span>
                        <span>K: {l.avg_key_mse?.toFixed(5)}</span>
                        <span>V: {l.avg_value_mse?.toFixed(5)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* KV Model Config */}
              {selectedRun.metrics.model_config && (
                <div className="mt-3 flex gap-3 text-[10px] text-zinc-500">
                  <span>Model: {selectedRun.metrics.model_config.model_name}</span>
                  <span>{selectedRun.metrics.model_config.layers}L × {selectedRun.metrics.model_config.heads}H</span>
                  <span>Seq: {selectedRun.metrics.model_config.seq_len}</span>
                  <span>Dim: {selectedRun.metrics.model_config.head_dim}</span>
                </div>
              )}
                {selectedRun.promotion_eval && (
                  <div className="mt-3 flex items-center gap-2">
                    <Badge className={selectedRun.promotion_eval.eligible ? "bg-emerald-500/15 text-emerald-400" : "bg-zinc-800 text-zinc-500"}>
                      {selectedRun.promotion_eval.eligible ? "Eligible for Promotion" : "Not Eligible"}
                    </Badge>
                    <span className="text-xs text-zinc-500">Score: {selectedRun.promotion_eval.score}</span>
                  </div>
                )}
              </div>

              {/* Timing */}
              <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/40">
                <p className="text-xs font-medium text-zinc-300 mb-2">Timing</p>
                <div className="flex gap-4 text-xs text-zinc-400">
                  <span>Rotation: {selectedRun.metrics.timing?.rotation_ms}ms</span>
                  <span>Quantize: {selectedRun.metrics.timing?.quantize_ms}ms</span>
                  <span>Total: {selectedRun.metrics.timing?.total_ms}ms</span>
                </div>
              </div>

              {/* Config */}
              <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/40">
                <p className="text-xs font-medium text-zinc-300 mb-2">Configuration</p>
                <div className="flex gap-3 text-xs text-zinc-400">
                  <span>Bit width: {selectedRun.metrics.config?.bit_width}</span>
                  <span>Dimensions: {selectedRun.metrics.config?.dim}</span>
                  <span>Vectors: {selectedRun.metrics.config?.n_vectors}</span>
                  <span>Seed: {selectedRun.metrics.config?.seed}</span>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
