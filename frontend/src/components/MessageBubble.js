import { useMemo, useState } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import DOMPurify from "dompurify";
import { FileText, Image, Code, File, Download, Wrench, CheckCircle2, AlertCircle, ArrowRightLeft, Bookmark, ThumbsUp, ThumbsDown, Volume2, MessageSquare } from "lucide-react";
import { api } from "@/App";
import { toast } from "sonner";
import { ProviderIcon } from "@/components/ProviderIcons";
import InlineMediaPlayer from "@/components/InlineMediaPlayer";

// Lazy mermaid renderer
function MermaidDiagram({ code, id }) {
  const [svg, setSvg] = useState("");
  const [error, setError] = useState(null);
  useMemo(() => {
    let cancelled = false;
    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({ startOnLoad: false, theme: "dark", themeVariables: { primaryColor: "#0891b2", primaryTextColor: "#e4e4e7", lineColor: "#52525b", primaryBorderColor: "#3f3f46" }});
        const { svg: rendered } = await mermaid.render(`mermaid-${id}`, code.trim());
        if (!cancelled) setSvg(rendered);
      } catch (e) {
        if (!cancelled) setError(e.message || "Invalid diagram");
      }
    })();
    return () => { cancelled = true; };
  }, [code, id]);
  if (error) return <pre className="text-xs text-red-400 bg-red-500/10 p-2 rounded">{error}</pre>;
  if (!svg) return <div className="text-xs text-zinc-500 p-2">Rendering diagram...</div>;
  return <div className="my-2 bg-zinc-900/50 rounded-lg p-3 border border-zinc-700/30 overflow-x-auto" dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(svg, { USE_PROFILES: { svg: true } }) }} data-testid="mermaid-diagram" />;
}

const AI_COLORS = {
  claude: "#D97757",
  chatgpt: "#10A37F",
  deepseek: "#4D6BFE",
  grok: "#F5F5F5",
  gemini: "#4285F4",
  perplexity: "#20B2AA",
  mistral: "#FF7000",
  cohere: "#39594D",
  groq: "#F55036",
  mercury: "#00D4FF",
  pi: "#FF6B35",
  manus: "#6C5CE7",
  qwen: "#615EFF",
  kimi: "#000000",
  llama: "#0467DF",
  glm: "#3D5AFE",
  cursor: "#00E5A0",
  notebooklm: "#FBBC04",
  copilot: "#171515",
};

const AI_INITIALS = {
  claude: "C",
  chatgpt: "G",
  deepseek: "D",
  grok: "X",
  gemini: "Ge",
  perplexity: "P",
  mistral: "M",
  cohere: "Co",
  groq: "Gq",
  mercury: "Me",
  pi: "Pi",
  manus: "Ma",
  qwen: "Qw",
  kimi: "Ki",
  llama: "Ll",
  glm: "GL",
  cursor: "Cu",
  notebooklm: "NL",
  copilot: "GC",
};

const MENTION_PATTERN = /@(\w+)/g;

// Simple markdown renderer for code blocks, bold, inline code
function renderContent(text) {
  if (!text || typeof text !== "string") return null;

  try {
    const parts = text.split(/(```[\s\S]*?```)/g);

  return parts.map((part, i) => {
    // Code block with copy button
    if (part.startsWith("```") && part.endsWith("```")) {
      const lines = part.slice(3, -3);
      const firstNewline = lines.indexOf("\n");
      const lang = firstNewline > 0 ? lines.slice(0, firstNewline).trim() : "";
      const code = firstNewline > 0 ? lines.slice(firstNewline + 1) : lines;

      // Mermaid diagram rendering
      if (lang === "mermaid") {
        return <MermaidDiagram key={i} code={code} id={`${i}-${Date.now()}`} />;
      }

      return (
        <div key={i} className="my-3 relative group">
          <div className="flex items-center justify-between px-3 py-1 bg-zinc-800/80 rounded-t-lg border border-zinc-700/30 border-b-0">
            <span className="text-[10px] text-zinc-500 font-mono">{lang || "code"}</span>
            <button onClick={() => { navigator.clipboard.writeText(code.trim()); toast.success("Copied!"); }}
              className="text-[10px] text-zinc-500 hover:text-zinc-300 opacity-0 group-hover:opacity-100 transition-opacity px-1.5 py-0.5 rounded bg-zinc-700/50">Copy</button>
          </div>
          <pre className="bg-black/50 border border-zinc-700/30 rounded-b-lg px-3 py-2 overflow-x-auto max-h-[300px] overflow-y-auto">
            <code className="text-[12px] leading-relaxed text-zinc-300 font-mono">{code.trim()}</code>
          </pre>
        </div>
      );
    }

    // Inline image reference [image:url] or base64 data or markdown images
    if (part.match(/!\[.*?\]\(data:image/) || part.match(/!\[.*?\]\(https?:\/\//)) {
      const imgMatch = part.match(/!\[([^\]]*)\]\(((?:data:image|https?:\/\/)[^)]+)\)/);
      if (imgMatch) {
        return (
          <div key={i} className="my-2">
            <img src={imgMatch[2]} alt={imgMatch[1] || "Generated image"} className="max-h-[400px] rounded-lg border border-zinc-700/30" loading="lazy" />
            {imgMatch[1] && <p className="text-[10px] text-zinc-500 mt-1">{imgMatch[1]}</p>}
          </div>
        );
      }
    }

    // Standalone image URLs on their own line
    if (part.trim().match(/^https?:\/\/\S+\.(png|jpg|jpeg|gif|webp|svg)(\?[^\s]*)?$/i)) {
      return (
        <div key={i} className="my-2">
          <img src={part.trim()} alt="Inline image" className="max-h-[400px] rounded-lg border border-zinc-700/30" loading="lazy" />
        </div>
      );
    }

    // Download links: [Download: filename](url) pattern
    if (part.match(/\[Download:\s*([^\]]+)\]\((https?:\/\/[^)]+)\)/)) {
      const dlMatch = part.match(/\[Download:\s*([^\]]+)\]\((https?:\/\/[^)]+)\)/);
      if (dlMatch) {
        return (
          <a key={i} href={dlMatch[2]} download={dlMatch[1]} target="_blank" rel="noopener noreferrer"
            className="my-2 inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 hover:bg-cyan-500/20 transition-colors text-sm"
            data-testid="inline-download-link">
            <Download className="w-4 h-4" />
            <span>{dlMatch[1]}</span>
          </a>
        );
      }
    }

    // Regular text with inline formatting
    return (
      <span key={i}>
        {part.split("\n").map((line, j) => (
          <span key={j}>
            {j > 0 && <br />}
            {renderInline(line)}
          </span>
        ))}
      </span>
    );
  });
  } catch (err) {
    return <span className="text-zinc-400">{String(text)}</span>;
  }
}

function renderInline(text) {
  if (!text || typeof text !== "string") return text;
  try {
  // Handle bold, inline code, italic, and @mentions
  const parts = text.split(/(\*\*.*?\*\*|`[^`]+`|_[^_]+_|@\w+)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i} className="font-semibold text-zinc-100">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code key={i} className="bg-zinc-800/60 text-zinc-300 px-1.5 py-0.5 rounded text-[12px] font-mono">
          {part.slice(1, -1)}
        </code>
      );
    }
    if (part.startsWith("_") && part.endsWith("_")) {
      return <em key={i} className="italic text-zinc-400">{part.slice(1, -1)}</em>;
    }
    // @mention highlighting
    if (part.startsWith("@")) {
      const mentionName = part.slice(1).toLowerCase();
      const color = AI_COLORS[mentionName] || (mentionName === "everyone" ? "#F59E0B" : "#818CF8");
      return (
        <span
          key={i}
          className="inline-flex items-center px-1.5 py-0.5 rounded-md text-[12px] font-semibold"
          style={{
            backgroundColor: `${color}18`,
            color: color,
            border: `1px solid ${color}30`,
          }}
          data-testid={`mention-${mentionName}`}
        >
          @{part.slice(1)}
        </span>
      );
    }
    return part;
  });
  } catch (err) { handleSilent(err, "MessageBubble:op2"); return text; }
}

export const MessageBubble = ({ message, isOwn, workspaceId, onPlayAudio, onStartThread }) => {
  const isAI = message?.sender_type === "ai";
  const isTool = message?.sender_type === "tool";
  const isHandoff = message?.sender_type === "handoff";
  const agentKey = message?.ai_model || "";
  const color = (isAI || isTool || isHandoff) ? AI_COLORS[agentKey] || "#666" : null;
  const initial = (isAI || isTool || isHandoff) ? AI_INITIALS[agentKey] || "?" : null;
  const [rated, setRated] = useState(null);
  const [saving, setSaving] = useState(false);

  const timeStr = useMemo(() => {
    try {
      if (!message?.created_at) return "";
      const d = new Date(message.created_at);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch (err) { handleSilent(err, "MessageBubble:op3"); return ""; }
  }, [message?.created_at]);

  if (!message) return null;

  // Handoff message - styled context transfer card
  if (isHandoff && message.handoff) {
    const ho = message.handoff;
    const fromColor = AI_COLORS[ho.from_agent] || "#666";
    const toColor = AI_COLORS[ho.to_agent] || "#818CF8";
    return (
      <div className="py-2" data-testid={`handoff-msg-${message.message_id}`}>
        <div className="max-w-3xl ml-11">
          <div className="rounded-lg border border-indigo-500/20 bg-indigo-950/20 p-3">
            <div className="flex items-center gap-2 mb-2">
              <ArrowRightLeft className="w-4 h-4 text-indigo-400" />
              <span className="text-xs font-semibold text-indigo-300">HANDOFF</span>
              <span className="text-[11px] font-mono" style={{ color: fromColor }}>{ho.from_agent}</span>
              <span className="text-zinc-600">→</span>
              <span className="text-[11px] font-mono" style={{ color: toColor }}>{ho.to_agent}</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-900/40 text-indigo-400 border border-indigo-800/30 ml-1">{ho.context_type}</span>
              <span className="text-[10px] text-zinc-600 font-mono ml-auto">{timeStr}</span>
            </div>
            <p className="text-sm font-medium text-zinc-200 mb-1">{ho.title}</p>
            <div className="text-sm text-zinc-400 leading-relaxed">{renderContent(message.content?.replace(`**Handoff to ${ho.to_agent}**: ${ho.title}\n\n`, ''))}</div>
          </div>
        </div>
      </div>
    );
  }

  // Tool result message - compact activity card
  if (isTool) {
    const toolResult = message.tool_result || {};
    const isSuccess = toolResult.status === "success";
    return (
      <div className="py-1.5" data-testid={`tool-msg-${message.message_id}`}>
        <div className="flex items-start gap-2.5 max-w-3xl ml-11">
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-zinc-900/60 border border-zinc-800/40 text-xs w-full">
            <div className="flex items-center gap-1.5 flex-shrink-0">
              {isSuccess ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              ) : (
                <AlertCircle className="w-3.5 h-3.5 text-red-400" />
              )}
              <Wrench className="w-3 h-3 text-zinc-500" />
            </div>
            <span className="text-zinc-400 font-mono text-[11px]" style={{ color: color }}>
              {message.sender_name}
            </span>
            <span className="text-zinc-500">|</span>
            <span className="text-zinc-300 flex-1">{renderContent(message.content)}</span>
            <span className="text-[10px] text-zinc-600 font-mono flex-shrink-0">{timeStr}</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className="py-2 group"
      data-testid={`message-${message.message_id}`}
    >
      <div className="flex items-start gap-3 max-w-4xl">
        {/* Avatar */}
        {isAI ? (
          <ProviderIcon provider={agentKey} size={32} color={agentKey === "grok" ? "#09090b" : "#fff"} bgColor={color} />
        ) : (
          <div className="w-8 h-8 rounded-lg bg-zinc-700 flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5 text-zinc-200">
            {message.sender_name?.[0] || "U"}
          </div>
        )}

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2 mb-1">
            <span
              className="text-sm font-semibold"
              style={{ color: isAI ? color : "#e4e4e7" }}
            >
              {message.sender_name}
            </span>
            {isAI && agentKey && (
              <span
                className="text-[10px] font-mono px-1.5 py-0.5 rounded border"
                style={{
                  borderColor: `${color}30`,
                  color: color,
                  opacity: 0.7,
                }}
              >
                {agentKey.toUpperCase()}
              </span>
            )}
            <span className="text-[10px] text-zinc-600 font-mono">{timeStr}</span>
          </div>
          <div className="message-content text-sm text-zinc-300 leading-relaxed">
            {renderContent(message.content)}
          </div>
          {/* Tool call indicators */}
          {message.tool_calls && message.tool_calls.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2" data-testid="tool-call-indicators">
              {message.tool_calls.map((tc, idx) => (
                <span
                  key={idx}
                  className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-mono bg-zinc-800/60 border border-zinc-700/30 text-zinc-400"
                >
                  <Wrench className="w-3 h-3" />
                  {tc.tool}
                </span>
              ))}
            </div>
          )}
          {/* File attachment */}
          {message.file_attachment && (
            <FileAttachmentInline file={message.file_attachment} />
          )}
          {/* Inline media player for generated media */}
          {message.media_attachment && (
            <InlineMediaPlayer
              mediaId={message.media_attachment.media_id}
              mediaType={message.media_attachment.type || "audio"}
              prompt={message.media_attachment.prompt || ""}
              duration={message.media_attachment.duration}
            />
          )}
          {/* Auto-detect media IDs in message content */}
          {!message.media_attachment && message.content && (() => {
            const mediaMatch = message.content.match(/media_id[:\s]+(vid_[a-f0-9]+|mus_[a-f0-9]+|sfx_[a-f0-9]+|aud_[a-f0-9]+)/i);
            if (!mediaMatch) return null;
            const id = mediaMatch[1];
            const type = id.startsWith("vid_") ? "video" : id.startsWith("mus_") ? "music" : id.startsWith("sfx_") ? "sfx" : "audio";
            return <InlineMediaPlayer mediaId={id} mediaType={type} />;
          })()}
          {/* AI message actions: Save as Artifact + Quick Rate */}
          {isAI && (
            <div className="flex items-center gap-1 mt-2 opacity-0 group-hover:opacity-100 transition-opacity" data-testid={`msg-actions-${message.message_id}`}>
              <button
                onClick={async () => {
                  if (!workspaceId || saving) return;
                  setSaving(true);
                  try {
                    const title = `${message.sender_name} — ${(message.content || "").substring(0, 50)}`;
                    await api.post(`/workspaces/${workspaceId}/artifacts`, {
                      name: title, content: message.content || "",
                      content_type: message.content?.includes("```") ? "code" : "text",
                      tags: ["from-chat", agentKey || "ai"],
                    });
                    toast.success("Saved as artifact");
                  } catch (err) { handleError(err, "MessageBubble:op1"); }
                  setSaving(false);
                }}
                className="flex items-center gap-1 px-2 py-1 rounded-md text-[10px] text-zinc-500 hover:text-amber-400 hover:bg-zinc-800 transition-colors"
                title="Save as Artifact"
                data-testid={`save-artifact-${message.message_id}`}
              >
                <Bookmark className="w-3 h-3" />
                <span>Save</span>
              </button>
              <button
                onClick={() => { setRated("up"); toast.success("Rated helpful"); }}
                className={`p-1 rounded-md transition-colors ${rated === "up" ? "text-emerald-400 bg-emerald-500/10" : "text-zinc-600 hover:text-emerald-400 hover:bg-zinc-800"}`}
                title="Helpful"
                data-testid={`rate-up-${message.message_id}`}
              >
                <ThumbsUp className="w-3 h-3" />
              </button>
              <button
                onClick={() => { setRated("down"); toast.success("Rated not helpful"); }}
                className={`p-1 rounded-md transition-colors ${rated === "down" ? "text-red-400 bg-red-500/10" : "text-zinc-600 hover:text-red-400 hover:bg-zinc-800"}`}
                title="Not helpful"
                data-testid={`rate-down-${message.message_id}`}
              >
                <ThumbsDown className="w-3 h-3" />
              </button>
              {onPlayAudio && (
                <button
                  onClick={() => onPlayAudio(message.content)}
                  className="p-1 rounded-md text-zinc-600 hover:text-violet-400 hover:bg-zinc-800 transition-colors"
                  title="Listen (TTS)"
                  data-testid={`play-audio-${message.message_id}`}
                >
                  <Volume2 className="w-3 h-3" />
                </button>
              )}
              {onStartThread && (
                <button
                  onClick={() => onStartThread(message)}
                  className="p-1 rounded-md text-zinc-600 hover:text-cyan-400 hover:bg-cyan-500/10 transition-colors"
                  title="Reply in thread"
                  aria-label="Reply in thread"
                  data-testid={`thread-reply-${message.message_id}`}
                >
                  <MessageSquare className="w-3 h-3" />
                </button>
              )}
            </div>
          )}
          {message.thread_count > 0 && (
            <button onClick={() => onStartThread?.(message)}
              className="flex items-center gap-1 mt-1 text-[10px] text-cyan-400 hover:text-cyan-300 px-2 py-0.5 rounded-md bg-cyan-500/10 w-fit"
              aria-label={`${message.thread_count} thread replies`}
              data-testid={`thread-count-${message.message_id}`}>
              <MessageSquare className="w-3 h-3" />
              {message.thread_count} {message.thread_count === 1 ? "reply" : "replies"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

// Inline file attachment display
function FileAttachmentInline({ file }) {
  const ext = file.extension || file.name?.split(".").pop() || "";
  const isImage = ["png", "jpg", "jpeg", "gif", "webp"].includes(ext.toLowerCase());
  
  const formatSize = (bytes) => {
    if (!bytes) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const handleDownload = () => {
    window.open(`${api.defaults.baseURL}/files/${file.file_id}/download`, "_blank");
  };

  return (
    <div 
      className="mt-2 inline-flex items-center gap-2 px-3 py-2 bg-zinc-800/50 rounded-lg border border-zinc-700/50 cursor-pointer hover:bg-zinc-800 transition-colors group"
      onClick={handleDownload}
      data-testid={`file-attachment-${file.file_id || file.name}`}
    >
      {isImage ? (
        <Image className="w-4 h-4 text-blue-400" />
      ) : ext.match(/^(py|js|ts|jsx|tsx|html|css|json)$/) ? (
        <Code className="w-4 h-4 text-emerald-400" />
      ) : ext.match(/^(pdf|doc|docx|txt|md|csv|xlsx)$/) ? (
        <FileText className="w-4 h-4 text-amber-400" />
      ) : (
        <File className="w-4 h-4 text-zinc-400" />
      )}
      <span className="text-sm text-zinc-300">{file.name}</span>
      <span className="text-xs text-zinc-500">{formatSize(file.size)}</span>
      {file.has_extracted_text && (
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">AI readable</span>
      )}
      <Download className="w-3 h-3 text-zinc-500 opacity-0 group-hover:opacity-100 transition-opacity" />
    </div>
  );
}

export default MessageBubble;
