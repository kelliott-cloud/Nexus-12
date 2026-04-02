import { useState, useEffect, useCallback } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Volume2, Loader2, Trash2, Download, Sparkles, Clock, BarChart3, Key, Mic, Play } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/App";

const VOICES = [
  { id: "alloy", label: "Alloy — Neutral" }, { id: "ash", label: "Ash — Clear" },
  { id: "coral", label: "Coral — Warm" }, { id: "echo", label: "Echo — Calm" },
  { id: "fable", label: "Fable — Expressive" }, { id: "nova", label: "Nova — Energetic" },
  { id: "onyx", label: "Onyx — Deep" }, { id: "sage", label: "Sage — Wise" },
  { id: "shimmer", label: "Shimmer — Bright" },
];

export default function AudioPanel({ workspaceId }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [text, setText] = useState("");
  const [voice, setVoice] = useState("alloy");
  const [model, setModel] = useState("tts-1");
  const [speed, setSpeed] = useState(1.0);
  const [useOwnKey, setUseOwnKey] = useState(false);
  const [selectedItem, setSelectedItem] = useState(null);
  const [mediaData, setMediaData] = useState(null);

  const fetchItems = useCallback(async () => {
    try { const res = await api.get(`/workspaces/${workspaceId}/media?media_type=audio`); setItems(res.data.items || []); }
    catch (err) { handleSilent(err, "AudioPanel:op1"); } finally { setLoading(false); }
  }, [workspaceId]);

  useEffect(() => { fetchItems(); }, [fetchItems]);

  const handleGenerate = async () => {
    if (!text.trim() || generating) return;
    setGenerating(true);
    try {
      const res = await api.post(`/workspaces/${workspaceId}/generate-audio`, { text, voice, model, speed, use_own_key: useOwnKey });
      toast.success(`Audio generated in ${(res.data.duration_ms / 1000).toFixed(1)}s`);
      setText(""); fetchItems();
    } catch (err) { toast.error(err.response?.data?.detail || "Generation failed"); }
    finally { setGenerating(false); }
  };

  const viewItem = async (item) => {
    setSelectedItem(item); setMediaData(null);
    try { const res = await api.get(`/media/${item.media_id}/data`); setMediaData(res.data.data); }
    catch (err) { toast.error("Failed to load"); }
  };

  return (
    <div className="flex-1 overflow-y-auto p-6" data-testid="audio-panel">
      <div className="max-w-4xl mx-auto space-y-6">
        <div>
          <h2 className="text-lg font-semibold text-zinc-100 flex items-center gap-2" style={{ fontFamily: "Syne, sans-serif" }}><Volume2 className="w-5 h-5 text-violet-400" /> Audio Generation</h2>
          <p className="text-sm text-zinc-500 mt-0.5">Text-to-Speech with 9 AI voices</p>
        </div>
        <div className="space-y-3">
          <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="Enter text to convert to speech (max 4096 chars)..." className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-violet-500/50 resize-none min-h-[100px]" disabled={generating} maxLength={4096} data-testid="audio-text-input" />
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-3">
              <select value={voice} onChange={(e) => setVoice(e.target.value)} className="bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-zinc-300" data-testid="audio-voice-select">
                {VOICES.map(v => <option key={v.id} value={v.id}>{v.label}</option>)}
              </select>
              <select value={model} onChange={(e) => setModel(e.target.value)} className="bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-zinc-300">
                <option value="tts-1">Standard</option><option value="tts-1-hd">HD Quality</option>
              </select>
              <div className="flex items-center gap-1.5 text-xs text-zinc-500">
                <span>Speed:</span>
                <input type="range" min={0.5} max={2} step={0.1} value={speed} onChange={(e) => setSpeed(parseFloat(e.target.value))} className="w-16" />
                <span className="text-zinc-400 w-7">{speed}x</span>
              </div>
              <label className="flex items-center gap-2 text-xs text-zinc-500 cursor-pointer"><input type="checkbox" checked={useOwnKey} onChange={(e) => setUseOwnKey(e.target.checked)} className="rounded border-zinc-700 bg-zinc-900" /><Key className="w-3 h-3" /></label>
            </div>
            <Button onClick={handleGenerate} disabled={!text.trim() || generating} className="bg-emerald-500 hover:bg-emerald-400 text-white font-semibold gap-2" data-testid="generate-audio-btn">
              {generating ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</> : <><Sparkles className="w-4 h-4" /> Generate</>}
            </Button>
          </div>
          <p className="text-[10px] text-zinc-600 text-right">{text.length}/4096 chars</p>
        </div>
        {loading ? <div className="text-center py-12 text-zinc-500">Loading...</div> : items.length === 0 ? (
          <div className="text-center py-16" data-testid="empty-audio"><Volume2 className="w-10 h-10 text-zinc-700 mx-auto mb-3" /><p className="text-zinc-400">No audio generated yet</p></div>
        ) : (
          <div className="space-y-2" data-testid="audio-list">
            {items.map((item) => (
              <div key={item.media_id} className="flex items-center gap-3 p-3 rounded-lg bg-zinc-900/60 border border-zinc-800/60 hover:border-zinc-700 cursor-pointer group" onClick={() => viewItem(item)} data-testid={`audio-item-${item.media_id}`}>
                <div className="w-10 h-10 rounded-lg bg-violet-500/10 border border-violet-500/20 flex items-center justify-center flex-shrink-0"><Volume2 className="w-5 h-5 text-violet-400" /></div>
                <div className="flex-1 min-w-0"><p className="text-sm text-zinc-200 line-clamp-1">{item.prompt}</p><div className="flex items-center gap-2 text-[10px] text-zinc-500 mt-0.5"><span>{item.voice}</span><span>{item.model}</span><span>{(item.file_size / 1024).toFixed(0)}KB</span></div></div>
                <button onClick={(e) => { e.stopPropagation(); api.delete(`/media/${item.media_id}`).then(() => { toast.success("Deleted"); fetchItems(); }); }} className="p-1.5 rounded text-zinc-700 hover:text-red-400 opacity-0 group-hover:opacity-100"><Trash2 className="w-3.5 h-3.5" /></button>
              </div>
            ))}
          </div>
        )}
        <Dialog open={!!selectedItem} onOpenChange={(open) => { if (!open) { setSelectedItem(null); setMediaData(null); } }}>
          <DialogContent className="bg-zinc-900 border-zinc-800 max-w-md"><DialogHeader><DialogTitle className="text-zinc-100 text-sm">Audio Player</DialogTitle></DialogHeader>
            {mediaData ? <audio controls className="w-full" src={`data:audio/mp3;base64,${mediaData}`} data-testid="audio-preview" /> : <div className="h-12 bg-zinc-800 rounded-lg flex items-center justify-center"><Loader2 className="w-5 h-5 animate-spin text-zinc-500" /></div>}
            <p className="text-sm text-zinc-400">{selectedItem?.prompt}</p><p className="text-[10px] text-zinc-600">Voice: {selectedItem?.voice} | Model: {selectedItem?.model}</p>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
