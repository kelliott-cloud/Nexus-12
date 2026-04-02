import { useState, useEffect, useCallback } from "react";
import { useConfirm } from "@/components/ConfirmDialog";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Image, Loader2, Trash2, Download, Sparkles, Clock, BarChart3, Key } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/App";

export default function ImageGenPanel({ workspaceId }) {
  const { confirm: confirmAction, ConfirmDialog: ConfirmDlg } = useConfirm();
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [provider, setProvider] = useState("gemini");
  const [useOwnKey, setUseOwnKey] = useState(false);
  const [selectedImage, setSelectedImage] = useState(null);
  const [imageData, setImageData] = useState(null);
  const [metrics, setMetrics] = useState(null);

  const fetchImages = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/images`);
      setImages(res.data.images || []);
    } catch (err) { handleSilent(err, "ImageGenPanel:op1"); } finally { setLoading(false); }
  }, [workspaceId]);

  const fetchMetrics = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/image-gen/metrics`);
      setMetrics(res.data);
    } catch (err) { handleSilent(err, "ImageGenPanel:op2"); }
  }, [workspaceId]);

  useEffect(() => { fetchImages(); fetchMetrics(); }, [fetchImages, fetchMetrics]);

  const handleGenerate = async () => {
    if (!prompt.trim() || generating) return;
    setGenerating(true);
    try {
      const res = await api.post(`/workspaces/${workspaceId}/generate-image`, {
        prompt, provider, use_own_key: useOwnKey,
      });
      toast.success(`Image generated in ${(res.data.duration_ms / 1000).toFixed(1)}s`);
      setPrompt("");
      fetchImages();
      fetchMetrics();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Generation failed");
    } finally { setGenerating(false); }
  };

  const viewImage = async (img) => {
    setSelectedImage(img);
    setImageData(null);
    try {
      const res = await api.get(`/images/${img.image_id}/data`);
      setImageData(res.data.data);
    } catch (err) { toast.error("Failed to load image"); }
  };

  const deleteImage = async (imageId) => {
    const _ok = await confirmAction("Delete Image", "Delete this generated image?"); if (!_ok) return;
    try {
      await api.delete(`/images/${imageId}`);
      toast.success("Deleted");
      fetchImages();
      if (selectedImage?.image_id === imageId) { setSelectedImage(null); setImageData(null); }
    } catch (err) { toast.error("Failed to delete"); }
  };

  const downloadImage = () => {
    if (!imageData || !selectedImage) return;
    const link = document.createElement("a");
    link.href = `data:${selectedImage.mime_type};base64,${imageData}`;
    link.download = `nexus-${selectedImage.image_id}.png`;
    link.click();
  };

  return (
    <div className="flex-1 overflow-y-auto p-6" data-testid="image-gen-panel">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100 flex items-center gap-2" style={{ fontFamily: "Syne, sans-serif" }}>
              <Sparkles className="w-5 h-5 text-violet-400" /> Image Generation
            </h2>
            <p className="text-sm text-zinc-500 mt-0.5">Generate images with AI</p>
          </div>
        </div>

        {/* Metrics bar */}
        {metrics && metrics.total_requests > 0 && (
          <div className="flex items-center gap-4 px-4 py-2.5 rounded-lg bg-zinc-900/60 border border-zinc-800/40" data-testid="image-gen-metrics">
            <div className="flex items-center gap-1.5 text-xs text-zinc-400"><BarChart3 className="w-3.5 h-3.5" /><span>{metrics.total_requests} generated</span></div>
            <div className="flex items-center gap-1.5 text-xs text-emerald-400"><span>{metrics.success_rate}% success</span></div>
            <div className="flex items-center gap-1.5 text-xs text-zinc-500"><Clock className="w-3 h-3" /><span>avg {(metrics.avg_duration_ms / 1000).toFixed(1)}s</span></div>
          </div>
        )}

        {/* Prompt input */}
        <div className="space-y-3">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Describe the image you want to generate..."
            className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-violet-500/50 font-[Manrope] resize-none min-h-[80px]"
            disabled={generating}
            data-testid="image-prompt-input"
            onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleGenerate(); }}
          />
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                className="text-xs bg-zinc-900 border border-zinc-800 rounded-lg px-2 py-1.5 text-zinc-300 focus:outline-none focus:ring-1 focus:ring-violet-500/50"
                data-testid="image-provider-select"
              >
                <option value="gemini">Gemini Flash</option>
                <option value="imagen4">Imagen 4</option>
                <option value="openai">OpenAI (GPT Image)</option>
                <option value="nano_banana">Nano Banana (Edit + Generate)</option>
              </select>
              <label className="flex items-center gap-2 text-xs text-zinc-500 cursor-pointer">
                <input type="checkbox" checked={useOwnKey} onChange={(e) => setUseOwnKey(e.target.checked)} className="rounded border-zinc-700 bg-zinc-900" />
                <Key className="w-3 h-3" /> Use my own API key
              </label>
            </div>
            <Button onClick={handleGenerate} disabled={!prompt.trim() || generating} className="bg-emerald-500 hover:bg-emerald-400 text-white font-semibold gap-2" data-testid="generate-image-btn">
              {generating ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</> : <><Sparkles className="w-4 h-4" /> Generate</>}
            </Button>
          </div>
          <p className="text-[10px] text-zinc-600 text-right">Ctrl+Enter to generate</p>
        </div>

        {/* Image gallery */}
        {loading ? (
          <div className="text-center py-12 text-zinc-500">Loading...</div>
        ) : images.length === 0 ? (
          <div className="text-center py-16" data-testid="empty-images">
            <div className="w-14 h-14 rounded-2xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center mx-auto mb-4">
              <Image className="w-6 h-6 text-violet-400" />
            </div>
            <p className="text-zinc-400 font-medium">No images generated yet</p>
            <p className="text-sm text-zinc-600 mt-1">Enter a prompt above and click Generate</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3" data-testid="image-gallery">
            {images.map((img) => (
              <div key={img.image_id} className="rounded-xl bg-zinc-900/60 border border-zinc-800/60 overflow-hidden hover:border-zinc-700 transition-colors cursor-pointer group" onClick={() => viewImage(img)} data-testid={`image-card-${img.image_id}`}>
                <div className="aspect-square bg-zinc-800/40 flex items-center justify-center">
                  <Image className="w-8 h-8 text-zinc-700" />
                </div>
                <div className="p-2.5">
                  <p className="text-xs text-zinc-300 line-clamp-2">{img.prompt}</p>
                  <div className="flex items-center justify-between mt-1.5">
                    <span className="text-[10px] text-zinc-600">{img.duration_ms ? `${(img.duration_ms / 1000).toFixed(1)}s` : ""}</span>
                    <button onClick={(e) => { e.stopPropagation(); deleteImage(img.image_id); }} className="p-1 rounded text-zinc-700 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all"><Trash2 className="w-3 h-3" /></button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Image detail dialog */}
        <Dialog open={!!selectedImage} onOpenChange={(open) => { if (!open) { setSelectedImage(null); setImageData(null); } }}>
          <DialogContent className="bg-zinc-900 border-zinc-800 max-w-2xl">
            <DialogHeader>
              <DialogTitle className="text-zinc-100 text-sm">Generated Image</DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              {imageData ? (
                <img src={`data:${selectedImage?.mime_type || "image/png"};base64,${imageData}`} alt={selectedImage?.prompt} className="w-full rounded-lg" data-testid="image-preview" />
              ) : (
                <div className="aspect-video bg-zinc-800 rounded-lg flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-zinc-500" /></div>
              )}
              <p className="text-sm text-zinc-400">{selectedImage?.prompt}</p>
              <div className="flex items-center justify-between text-[10px] text-zinc-600">
                <span>Provider: {selectedImage?.provider} ({selectedImage?.key_source})</span>
                <span>{selectedImage?.duration_ms ? `${(selectedImage.duration_ms / 1000).toFixed(1)}s` : ""}</span>
              </div>
              <div className="flex gap-2">
                <Button onClick={downloadImage} disabled={!imageData} variant="outline" size="sm" className="border-zinc-700 text-zinc-300 gap-1.5"><Download className="w-3.5 h-3.5" /> Download</Button>
                <Button onClick={() => { if (selectedImage) deleteImage(selectedImage.image_id); }} variant="outline" size="sm" className="border-zinc-700 text-red-400 gap-1.5"><Trash2 className="w-3.5 h-3.5" /> Delete</Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    <ConfirmDlg />
    </div>
    );
}
