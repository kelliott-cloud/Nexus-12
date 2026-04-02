import { useState, useRef } from "react";
import { Play, Pause, Volume2, VolumeX, Download, Film, Music, AudioWaveform, Loader2 } from "lucide-react";
import { api } from "@/App";
import { toast } from "sonner";

const MEDIA_TYPE_CONFIG = {
  video: { icon: Film, label: "Video", color: "text-violet-400", bg: "bg-violet-500/10", border: "border-violet-500/20" },
  music: { icon: Music, label: "Music", color: "text-pink-400", bg: "bg-pink-500/10", border: "border-pink-500/20" },
  sfx: { icon: AudioWaveform, label: "Sound Effect", color: "text-cyan-400", bg: "bg-cyan-500/10", border: "border-cyan-500/20" },
  audio: { icon: Volume2, label: "Audio", color: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/20" },
};

export const InlineMediaPlayer = ({ mediaId, mediaType = "audio", prompt = "", duration }) => {
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [muted, setMuted] = useState(false);
  const [progress, setProgress] = useState(0);
  const audioRef = useRef(null);
  const config = MEDIA_TYPE_CONFIG[mediaType] || MEDIA_TYPE_CONFIG.audio;
  const Icon = config.icon;

  const loadAndPlay = async () => {
    if (loaded && audioRef.current) {
      if (playing) {
        audioRef.current.pause();
        setPlaying(false);
      } else {
        audioRef.current.play();
        setPlaying(true);
      }
      return;
    }

    setLoading(true);
    try {
      const res = await api.get(`/media/${mediaId}/data`);
      const data = res.data?.data;
      if (!data) { toast.error("No media data available"); setLoading(false); return; }

      const mime = mediaType === "video" ? "video/mp4" : "audio/mpeg";
      const audio = new Audio(`data:${mime};base64,${data}`);
      audioRef.current = audio;

      audio.onended = () => { setPlaying(false); setProgress(0); };
      audio.ontimeupdate = () => {
        if (audio.duration) setProgress((audio.currentTime / audio.duration) * 100);
      };

      setLoaded(true);
      audio.play();
      setPlaying(true);
    } catch (err) {
      toast.error("Failed to load media");
    }
    setLoading(false);
  };

  const toggleMute = () => {
    if (audioRef.current) {
      audioRef.current.muted = !muted;
      setMuted(!muted);
    }
  };

  const handleDownload = async () => {
    try {
      const res = await api.get(`/media/${mediaId}/data`);
      const data = res.data?.data;
      if (!data) return;
      const ext = mediaType === "video" ? "mp4" : "mp3";
      const mime = mediaType === "video" ? "video/mp4" : "audio/mpeg";
      const link = document.createElement("a");
      link.href = `data:${mime};base64,${data}`;
      link.download = `nexus_${mediaType}_${mediaId}.${ext}`;
      link.click();
    } catch {
      toast.error("Download failed");
    }
  };

  return (
    <div
      className={`mt-2 rounded-xl ${config.bg} border ${config.border} p-3 max-w-sm`}
      data-testid={`media-player-${mediaId}`}
    >
      <div className="flex items-center gap-3">
        {/* Play/Pause button */}
        <button
          onClick={loadAndPlay}
          disabled={loading}
          className={`w-10 h-10 rounded-full flex items-center justify-center transition-all shrink-0 ${
            playing
              ? "bg-zinc-100 text-zinc-900"
              : `${config.bg} ${config.color} hover:scale-105`
          }`}
          data-testid={`media-play-${mediaId}`}
        >
          {loading ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : playing ? (
            <Pause className="w-5 h-5" />
          ) : (
            <Play className="w-5 h-5 ml-0.5" />
          )}
        </button>

        {/* Info + progress */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <Icon className={`w-3.5 h-3.5 ${config.color} shrink-0`} />
            <span className={`text-xs font-medium ${config.color}`}>{config.label}</span>
            {duration && <span className="text-[10px] text-zinc-500">{duration}s</span>}
          </div>
          {prompt && (
            <p className="text-[11px] text-zinc-400 truncate mt-0.5">{prompt}</p>
          )}
          {/* Progress bar */}
          {loaded && (
            <div className="mt-1.5 h-1 bg-zinc-800 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-300"
                style={{ width: `${progress}%`, backgroundColor: config.color.includes("violet") ? "#8b5cf6" : config.color.includes("pink") ? "#ec4899" : config.color.includes("cyan") ? "#06b6d4" : "#f59e0b" }}
              />
            </div>
          )}
        </div>

        {/* Controls */}
        <div className="flex items-center gap-1 shrink-0">
          {loaded && (
            <button
              onClick={toggleMute}
              className="p-1.5 rounded-md text-zinc-500 hover:text-zinc-300 transition-colors"
              data-testid={`media-mute-${mediaId}`}
            >
              {muted ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
            </button>
          )}
          <button
            onClick={handleDownload}
            className="p-1.5 rounded-md text-zinc-500 hover:text-zinc-300 transition-colors"
            title="Download"
            data-testid={`media-download-${mediaId}`}
          >
            <Download className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default InlineMediaPlayer;
