import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Zap, Lock, Eye, AlertCircle } from "lucide-react";
import MessageBubble from "@/components/MessageBubble";
import axios from "axios";

const API = (window.location.hostname !== "localhost")
  ? "/api"
  : `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ReplayPage() {
  const { shareId } = useParams();
  const [shareInfo, setShareInfo] = useState(null);
  const [replay, setReplay] = useState(null);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [needsPassword, setNeedsPassword] = useState(false);

  useEffect(() => {
    fetchShareInfo();
  }, [shareId]);

  const fetchShareInfo = async () => {
    try {
      const res = await axios.get(`${API}/shares/${shareId}`);
      setShareInfo(res.data);
      if (res.data.is_public) {
        loadReplay();
      } else {
        setNeedsPassword(true);
        setLoading(false);
      }
    } catch (err) {
      setError(err.response?.status === 410 ? "This share link has expired." : "Share not found.");
      setLoading(false);
    }
  };

  const loadReplay = async (pw) => {
    try {
      const res = await axios.post(`${API}/replay/${shareId}`, { password: pw || null });
      setReplay(res.data);
      setNeedsPassword(false);
    } catch (err) {
      if (err.response?.status === 403) {
        setError("Invalid password");
      } else {
        setError("Failed to load replay");
      }
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordSubmit = () => {
    setError("");
    setLoading(true);
    loadReplay(password);
  };

  if (error && !needsPassword) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center px-4" data-testid="replay-error">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-zinc-300 mb-2" style={{ fontFamily: 'Syne, sans-serif' }}>{error}</h2>
          <a href="/" className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors">Back to Nexus</a>
        </div>
      </div>
    );
  }

  if (needsPassword && !replay) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center px-4" data-testid="replay-password">
        <div className="w-full max-w-sm">
          <div className="flex items-center gap-3 mb-8 justify-center">
            <div className="w-8 h-8 rounded-md overflow-hidden">
              <img src="/logo.png" alt="Nexus Cloud" className="w-8 h-8" />
            </div>
            <span className="font-bold text-lg" style={{ fontFamily: 'Syne, sans-serif' }}>NEXUS CLOUD REPLAY</span>
          </div>
          <div className="p-6 rounded-xl bg-zinc-900/40 border border-zinc-800/60">
            <Lock className="w-8 h-8 text-zinc-500 mx-auto mb-4" />
            <h3 className="text-center text-zinc-300 font-medium mb-4">This replay is password protected</h3>
            <div className="space-y-3">
              <Input type="password" placeholder="Enter password" value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handlePasswordSubmit()}
                className="bg-zinc-950 border-zinc-800" data-testid="replay-password-input" />
              {error && <p className="text-xs text-red-400">{error}</p>}
              <Button onClick={handlePasswordSubmit} disabled={!password || loading}
                className="w-full bg-zinc-100 text-zinc-900 hover:bg-zinc-200" data-testid="replay-password-submit">
                {loading ? "Loading..." : "View Replay"}
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (loading || !replay) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="flex gap-2">
          {[0, 150, 300, 450].map((d, i) => (
            <div key={i} className="w-2 h-2 rounded-full bg-zinc-600 animate-bounce" style={{ animationDelay: `${d}ms` }} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950" data-testid="replay-page">
      {/* Header */}
      <header className="sticky top-0 z-40 glass-panel px-6 py-3">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-md overflow-hidden">
              <img src="/logo.png" alt="Nexus Cloud" className="w-7 h-7" />
            </div>
            <span className="font-bold" style={{ fontFamily: 'Syne, sans-serif' }}>NEXUS CLOUD REPLAY</span>
          </div>
          <div className="flex items-center gap-3 text-xs text-zinc-500">
            <Eye className="w-3.5 h-3.5" />
            <span>{replay.share?.views} views</span>
            {replay.workspace?.name && (
              <span className="text-zinc-600">| {replay.workspace.name}</span>
            )}
          </div>
        </div>
      </header>

      {/* Channel info */}
      <div className="max-w-4xl mx-auto px-6 py-4">
        <h1 className="text-xl font-bold text-zinc-200" style={{ fontFamily: 'Syne, sans-serif' }}>
          #{replay.channel?.name}
        </h1>
        {replay.channel?.description && (
          <p className="text-sm text-zinc-500 mt-1">{replay.channel.description}</p>
        )}
      </div>

      {/* Messages */}
      <ScrollArea className="max-w-4xl mx-auto px-6">
        <div className="space-y-1 pb-12">
          {replay.messages?.map((msg) => (
            <MessageBubble key={msg.message_id} message={msg} isOwn={false} />
          ))}
        </div>
      </ScrollArea>

      {/* Footer */}
      <div className="fixed bottom-0 left-0 right-0 glass-panel border-t border-zinc-800/60 py-3 text-center">
        <a href="/" className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors">
          Powered by <span className="font-bold">NEXUS CLOUD</span> - Multi-AI Collaboration Platform
        </a>
      </div>
    </div>
  );
}
