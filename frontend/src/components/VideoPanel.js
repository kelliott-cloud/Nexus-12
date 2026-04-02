import { useState, useEffect, useCallback } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Video, Loader2, Trash2, Download, Sparkles, Clock, BarChart3, Key, Play, Send } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/App";
import SocialPublishModal from "@/components/SocialPublishModal";

export default function VideoPanel({ workspaceId }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [negativePrompt, setNegativePrompt] = useState("");
  const [size, setSize] = useState("1280x720");
  const [publishOpen, setPublishOpen] = useState(false);
  const [publishMediaId, setPublishMediaId] = useState("");
  const [publishMediaName, setPublishMediaName] = useState("");
  const [duration, setDuration] = useState(4);
  const [style, setStyle] = useState("natural");
  const [useOwnKey, setUseOwnKey] = useState(false);
  const [selectedItem, setSelectedItem] = useState(null);
  const [mediaData, setMediaData] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [capabilities, setCapabilities] = useState(null);

  const fetchItems = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/media?media_type=video`);
      setItems(res.data.items || []);
    } catch (err) { handleSilent(err, "VideoPanel:op1"); } finally { setLoading(false); }
  }, [workspaceId]);

  const fetchMetrics = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/media/metrics`);
      setMetrics(res.data.metrics?.find(m => m.type === "video"));
    } catch (err) { handleSilent(err, "VideoPanel:op2"); }
  }, [workspaceId]);

  useEffect(() => { fetchItems(); fetchMetrics(); }, [fetchItems, fetchMetrics]);
  useEffect(() => {
    api.get("/platform/capabilities").then(r => setCapabilities(r.data?.features || null)).catch(() => {});
  }, []);

  const handleGenerate = async () => {
    if (!prompt.trim() || generating) return;
    setGenerating(true);
    toast.info("Generating video — this may take 2-5 minutes...");
    try {
      const res = await api.post(`/workspaces/${workspaceId}/generate-video`, { prompt, negative_prompt: negativePrompt, size, duration, style, model: "gemini-veo", use_own_key: useOwnKey });
      toast.success(`Video generated in ${(res.data.duration_ms / 1000).toFixed(0)}s`);
      setPrompt(""); fetchItems(); fetchMetrics();
    } catch (err) { toast.error(err.response?.data?.detail || "Generation failed"); }
    finally { setGenerating(false); }
  };

  const viewItem = async (item) => {
    setSelectedItem(item); setMediaData(null);
    try { const res = await api.get(`/media/${item.media_id}/data`); setMediaData(res.data.data); }
    catch (err) { toast.error("Failed to load"); }
  };

  return (
    <div className="flex-1 overflow-y-auto p-6" data-testid="video-panel">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100 flex items-center gap-2" style={{ fontFamily: "Syne, sans-serif" }}><Video className="w-5 h-5 text-red-400" /> Video Generation</h2>
            <p className="text-sm text-zinc-500 mt-0.5">Video Concepts (AI-Described)</p>
          </div>
        </div>
        {metrics && <div className="flex items-center gap-4 px-4 py-2.5 rounded-lg bg-zinc-900/60 border border-zinc-800/40" data-testid="video-metrics"><BarChart3 className="w-3.5 h-3.5 text-zinc-400" /><span className="text-xs text-zinc-400">{metrics.total} generated</span><span className="text-xs text-emerald-400">{metrics.success_rate}% success</span><Clock className="w-3 h-3 text-zinc-500" /><span className="text-xs text-zinc-500">avg {((metrics.avg_duration_ms || 0) / 1000).toFixed(0)}s</span></div>}
        <div className="space-y-3">
          {capabilities?.video_generation && !capabilities.video_generation.enabled && (
            <div className="rounded-xl border border-amber-500/20 bg-amber-500/8 px-4 py-3" data-testid="video-generation-disabled-notice">
              <p className="text-sm font-medium text-amber-300">Video generation is not enabled yet</p>
              <p className="text-xs text-amber-100/80 mt-1">{capabilities.video_generation.reason}</p>
            </div>
          )}
          <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Describe the video you want to generate..." className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-red-500/50 resize-none min-h-[80px]" disabled={generating} data-testid="video-prompt-input" />
          <input value={negativePrompt} onChange={(e) => setNegativePrompt(e.target.value)} placeholder="Negative prompt — things to avoid (optional)" className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-4 py-2 text-xs text-zinc-300 placeholder:text-zinc-600 focus:outline-none" data-testid="video-negative-prompt" />
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-3 flex-wrap">
              <select value={size} onChange={(e) => setSize(e.target.value)} className="bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-zinc-300" data-testid="video-size-select">
                <option value="1280x720">HD 720p</option><option value="1792x1024">Widescreen</option><option value="1024x1792">Portrait</option><option value="1024x1024">Square</option>
                <option value="1920x1080">YouTube (16:9)</option><option value="1080x1920">TikTok/Reels (9:16)</option><option value="1080x1080">Instagram Feed (1:1)</option>
              </select>
              <select value={duration} onChange={(e) => setDuration(parseInt(e.target.value))} className="bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-zinc-300" data-testid="video-duration-select">
                <option value={4}>4 sec</option><option value={8}>8 sec</option><option value={12}>12 sec</option>
              </select>
              <select value={style} onChange={(e) => setStyle(e.target.value)} className="bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-zinc-300" data-testid="video-style-select">
                <option value="natural">Natural</option><option value="cinematic">Cinematic</option><option value="animated">Animated</option><option value="documentary">Documentary</option><option value="slow_motion">Slow Motion</option><option value="timelapse">Timelapse</option>
              </select>
              <label className="flex items-center gap-2 text-xs text-zinc-500 cursor-pointer"><input type="checkbox" checked={useOwnKey} onChange={(e) => setUseOwnKey(e.target.checked)} className="rounded border-zinc-700 bg-zinc-900" /><Key className="w-3 h-3" /> Own key</label>
            </div>
            <Button onClick={handleGenerate} disabled={!prompt.trim() || generating || (capabilities?.video_generation && !capabilities.video_generation.enabled)} className="bg-emerald-500 hover:bg-emerald-400 text-white font-semibold gap-2" data-testid="generate-video-btn">
              {generating ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</> : <><Sparkles className="w-4 h-4" /> Generate</>}
            </Button>
          </div>
        </div>
        {loading ? <div className="text-center py-12 text-zinc-500">Loading...</div> : items.length === 0 ? (
          <div className="text-center py-16" data-testid="empty-videos"><Video className="w-10 h-10 text-zinc-700 mx-auto mb-3" /><p className="text-zinc-400">No videos generated yet</p></div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3" data-testid="video-gallery">
            {items.map((item) => (
              <div key={item.media_id} className="rounded-xl bg-zinc-900/60 border border-zinc-800/60 overflow-hidden hover:border-zinc-700 cursor-pointer group" onClick={() => viewItem(item)} data-testid={`video-card-${item.media_id}`}>
                <div className="aspect-video bg-zinc-800/40 flex items-center justify-center relative"><Video className="w-8 h-8 text-zinc-700" /><div className="absolute bottom-2 right-2 px-1.5 py-0.5 rounded bg-black/60 text-[10px] text-zinc-300">{item.duration_seconds}s</div></div>
                <div className="p-2.5"><p className="text-xs text-zinc-300 line-clamp-2">{item.prompt}</p><div className="flex items-center justify-between mt-1.5"><span className="text-[10px] text-zinc-600">{item.size}</span><div className="flex items-center gap-1"><button onClick={(e) => { e.stopPropagation(); setPublishMediaId(item.media_id); setPublishMediaName(item.prompt?.substring(0,50) || "Video"); setPublishOpen(true); }} className="p-1 rounded text-zinc-700 hover:text-cyan-400 opacity-0 group-hover:opacity-100" title="Publish"><Send className="w-3 h-3" /></button><button onClick={(e) => { e.stopPropagation(); api.delete(`/media/${item.media_id}`).then(() => { toast.success("Deleted"); fetchItems(); }); }} className="p-1 rounded text-zinc-700 hover:text-red-400 opacity-0 group-hover:opacity-100"><Trash2 className="w-3 h-3" /></button></div></div></div>
              </div>
            ))}
          </div>
        )}
        <Dialog open={!!selectedItem} onOpenChange={(open) => { if (!open) { setSelectedItem(null); setMediaData(null); } }}>
          <DialogContent className="bg-zinc-900 border-zinc-800 max-w-2xl"><DialogHeader><DialogTitle className="text-zinc-100 text-sm">Video</DialogTitle></DialogHeader>
            {mediaData ? <video controls className="w-full rounded-lg" src={`data:video/mp4;base64,${mediaData}`} data-testid="video-preview" /> : <div className="aspect-video bg-zinc-800 rounded-lg flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-zinc-500" /></div>}
            <p className="text-sm text-zinc-400">{selectedItem?.prompt}</p>
          </DialogContent>
        </Dialog>
      </div>
      <SocialPublishModal open={publishOpen} onOpenChange={setPublishOpen} mediaId={publishMediaId} mediaName={publishMediaName} workspaceId={workspaceId} />
    </div>
  );
}
