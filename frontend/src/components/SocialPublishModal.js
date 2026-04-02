import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Send, Loader2, Sparkles, Youtube, Hash } from "lucide-react";
import { api } from "@/App";
import { toast } from "sonner";

export default function SocialPublishModal({ open, onOpenChange, mediaId, mediaName, workspaceId }) {
  const [connections, setConnections] = useState([]);
  const [selectedConn, setSelectedConn] = useState("");
  const [title, setTitle] = useState(mediaName || "");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState("");
  const [privacy, setPrivacy] = useState("public");
  const [publishing, setPublishing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (open) {
      setTitle(mediaName || "");
      api.get("/social/connections").then(r => {
        const active = (r.data || []).filter(c => c.status === "active");
        setConnections(active);
        if (active.length > 0) setSelectedConn(active[0].connection_id);
      }).catch(() => {}).finally(() => setLoading(false));
    }
  }, [open, mediaName]);

  const generateCaption = async () => {
    if (!description && !title) { toast.error("Enter a description first"); return; }
    setGenerating(true);
    try {
      const platform = connections.find(c => c.connection_id === selectedConn)?.provider || "instagram";
      const res = await api.post("/content/social-caption", {
        description: description || title,
        platform,
        tone: "casual",
        workspace_id: workspaceId,
      });
      const variants = res.data?.variants || [];
      if (variants.length > 0) {
        setDescription(variants[0].caption || "");
        if (variants[0].hashtags) setTags(variants[0].hashtags.join(", "));
        if (variants[0].title && !title) setTitle(variants[0].title);
        toast.success("Caption generated!");
      }
    } catch (err) { toast.error("Caption generation failed"); }
    setGenerating(false);
  };

  const publish = async () => {
    if (!selectedConn || !mediaId) return;
    setPublishing(true);
    try {
      const res = await api.post(`/media/${mediaId}/publish`, {
        connection_id: selectedConn,
        title,
        description,
        tags: tags.split(",").map(t => t.trim()).filter(Boolean),
        privacy,
      });
      toast.success(`Publishing started: ${res.data?.job_id}`);
      onOpenChange(false);
    } catch (err) { toast.error(err.response?.data?.detail || "Publish failed"); }
    setPublishing(false);
  };

  const selectedPlatform = connections.find(c => c.connection_id === selectedConn)?.provider;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-zinc-900 border-zinc-800 max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-zinc-100 flex items-center gap-2"><Send className="w-4 h-4 text-cyan-400" /> Publish to Social Media</DialogTitle>
          <DialogDescription className="text-zinc-500">Share your content to connected platforms</DialogDescription>
        </DialogHeader>
        
        {loading ? (
          <div className="py-8 text-center"><Loader2 className="w-5 h-5 animate-spin text-zinc-500 mx-auto" /></div>
        ) : connections.length === 0 ? (
          <div className="py-8 text-center">
            <p className="text-sm text-zinc-400 mb-2">No social accounts connected</p>
            <p className="text-xs text-zinc-600">Go to Settings to connect YouTube, TikTok, or Instagram</p>
          </div>
        ) : (
          <div className="space-y-3 mt-2">
            <div>
              <label className="text-xs text-zinc-500 mb-1 block">Platform</label>
              <select value={selectedConn} onChange={e => setSelectedConn(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-md px-3 py-2 text-sm text-zinc-200" data-testid="publish-platform-select">
                {connections.map(c => (
                  <option key={c.connection_id} value={c.connection_id}>
                    {c.provider} {c.account_name ? `(${c.account_name})` : ""}
                  </option>
                ))}
              </select>
            </div>

            <Input value={title} onChange={e => setTitle(e.target.value)} placeholder="Title" className="bg-zinc-950 border-zinc-800" data-testid="publish-title" />

            <div className="relative">
              <textarea value={description} onChange={e => setDescription(e.target.value)} placeholder="Description / Caption"
                className="w-full bg-zinc-950 border border-zinc-800 rounded-md px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 min-h-[80px] pr-10" data-testid="publish-description" />
              <Button size="sm" onClick={generateCaption} disabled={generating}
                className="absolute top-2 right-2 h-6 px-2 bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30 text-[10px]" title="Generate AI caption">
                {generating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
              </Button>
            </div>

            <Input value={tags} onChange={e => setTags(e.target.value)} placeholder="Tags (comma-separated)" className="bg-zinc-950 border-zinc-800" data-testid="publish-tags" />

            <div>
              <label className="text-xs text-zinc-500 mb-1 block">Privacy</label>
              <select value={privacy} onChange={e => setPrivacy(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-md px-3 py-2 text-sm text-zinc-200">
                <option value="public">Public</option>
                <option value="unlisted">Unlisted</option>
                <option value="private">Private</option>
              </select>
            </div>

            {selectedPlatform && (
              <div className="p-2 rounded-lg bg-zinc-800/30 text-[10px] text-zinc-500">
                {selectedPlatform === "youtube" && "YouTube: Max 100 char title, 5000 char description"}
                {selectedPlatform === "tiktok" && "TikTok: 9:16 vertical, max 150 char title, 3s-10min"}
                {selectedPlatform === "instagram" && "Instagram: 9:16 for Reels, max 2200 char caption"}
              </div>
            )}

            <Button onClick={publish} disabled={publishing || !selectedConn}
              className="w-full bg-cyan-500 hover:bg-cyan-400 text-white" data-testid="publish-submit">
              {publishing ? <><Loader2 className="w-4 h-4 animate-spin mr-2" /> Publishing...</> : <><Send className="w-4 h-4 mr-2" /> Publish</>}
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
