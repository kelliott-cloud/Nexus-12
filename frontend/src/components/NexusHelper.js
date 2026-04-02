import { useState, useRef, useEffect } from "react";
import { MessageSquare, X, Minus, Send, Loader2, Trash2, Sparkles, Play, XCircle, Check, AlertTriangle, Shield } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const RISK_COLORS = { read: "bg-zinc-800 text-zinc-400", write: "bg-amber-500/15 text-amber-400", destructive: "bg-red-500/15 text-red-400" };
const STATUS_COLORS = { pending_review: "text-amber-400", running: "text-cyan-400", completed: "text-emerald-400", failed: "text-red-400", dismissed: "text-zinc-600" };

export default function NexusHelper({ open, minimized, messages, loading, context, onToggle, onMinimize, onRestore, onSend, onClear, onApproveAction, onDismissAction }) {
  const [input, setInput] = useState("");
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  const handleSend = () => {
    if (!input.trim()) return;
    onSend(input.trim());
    setInput("");
  };

  // Minimized or closed — rendered in sidebar by Dashboard/WorkspacePage, not here
  if (minimized || !open) {
    return null;
  }

  // Open modal
  return (
    <div className="fixed bottom-6 right-6 z-50 w-96 h-[520px] rounded-2xl bg-zinc-950 border border-zinc-800 shadow-2xl flex flex-col overflow-hidden" data-testid="helper-modal">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800 bg-gradient-to-r from-violet-600/10 to-cyan-600/10">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-cyan-400" />
          <span className="text-sm font-semibold text-zinc-100">Nexus Helper</span>
          {context?.page && <span className="text-[10px] text-zinc-500 bg-zinc-800 px-1.5 py-0.5 rounded">{context.page}</span>}
        </div>
        <div className="flex items-center gap-1">
          <button onClick={onClear} className="p-1 text-zinc-600 hover:text-zinc-400 transition-colors" title="Clear history"><Trash2 className="w-3.5 h-3.5" /></button>
          <button onClick={onMinimize} className="p-1 text-zinc-600 hover:text-zinc-400 transition-colors" title="Minimize"><Minus className="w-3.5 h-3.5" /></button>
          <button onClick={onToggle} className="p-1 text-zinc-600 hover:text-zinc-400 transition-colors" title="Close"><X className="w-3.5 h-3.5" /></button>
        </div>
      </div>

      {/* Context tips */}
      {context?.tips?.length > 0 && messages.length === 0 && (
        <div className="px-4 py-2 border-b border-zinc-800/50 bg-zinc-900/30">
          <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Quick Tips</p>
          {context.tips.map((tip, i) => (
            <p key={i} className="text-[11px] text-zinc-400 leading-relaxed">{tip}</p>
          ))}
        </div>
      )}

      {/* Suggestions */}
      {context?.suggestions?.length > 0 && messages.length === 0 && (
        <div className="px-4 py-2 border-b border-zinc-800/50">
          {context.suggestions.map((s, i) => (
            <button key={i} onClick={() => onSend(s)}
              className="w-full text-left text-xs text-cyan-400 hover:text-cyan-300 py-1 transition-colors">
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {messages.length === 0 && (
          <div className="text-center py-8">
            <Sparkles className="w-8 h-8 text-zinc-700 mx-auto mb-3" />
            <p className="text-sm text-zinc-500">Ask me anything about Nexus</p>
            <p className="text-[11px] text-zinc-600 mt-1">I can help with features, navigation, and troubleshooting</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] rounded-xl px-3 py-2 text-sm ${
              msg.role === "user"
                ? "bg-cyan-600/20 text-cyan-100 rounded-br-sm"
                : msg.error
                  ? "bg-red-500/10 text-red-300 border border-red-500/20 rounded-bl-sm"
                  : "bg-zinc-800/60 text-zinc-300 rounded-bl-sm"
            }`}>
              <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
              {msg.agent && <p className="text-[9px] text-zinc-600 mt-1">{msg.agent}</p>}
            </div>
            {/* Action Cards */}
            {msg.actions && msg.actions.length > 0 && (
              <div className="mt-2 space-y-2 max-w-[85%]">
                {msg.actions.map(action => (
                  <div key={action.action_id} className="rounded-lg border border-zinc-700/50 bg-zinc-900/80 p-2.5 text-xs" data-testid={`action-${action.action_id}`}>
                    <div className="flex items-center gap-2 mb-1.5">
                      <Shield className="w-3 h-3 text-zinc-500" />
                      <span className="font-medium text-zinc-200">{action.title}</span>
                      <Badge className={`text-[8px] ${RISK_COLORS[action.risk_level] || RISK_COLORS.write}`}>{action.risk_level}</Badge>
                      <span className={`text-[9px] ml-auto ${STATUS_COLORS[action.status] || "text-zinc-500"}`}>{action.status?.replace("_", " ")}</span>
                    </div>
                    {action.summary && <p className="text-zinc-400 mb-2">{action.summary}</p>}
                    {action.required_permissions?.length > 0 && (
                      <p className="text-[9px] text-zinc-600 mb-2">Requires: {action.required_permissions.join(", ")}</p>
                    )}
                    {action.status === "pending_review" && (
                      <div className="flex gap-1.5">
                        <button onClick={() => onApproveAction?.(action.action_id)}
                          className="flex items-center gap-1 px-2 py-1 rounded bg-emerald-600/20 text-emerald-400 hover:bg-emerald-600/30 transition-colors text-[10px]">
                          <Play className="w-2.5 h-2.5" /> Run
                        </button>
                        <button onClick={() => onDismissAction?.(action.action_id)}
                          className="flex items-center gap-1 px-2 py-1 rounded bg-zinc-800 text-zinc-500 hover:text-zinc-300 transition-colors text-[10px]">
                          <XCircle className="w-2.5 h-2.5" /> Dismiss
                        </button>
                      </div>
                    )}
                    {action.status === "completed" && action.result && (
                      <p className="text-emerald-400 text-[10px] flex items-center gap-1"><Check className="w-2.5 h-2.5" /> {action.result.summary}</p>
                    )}
                    {action.status === "failed" && (
                      <p className="text-red-400 text-[10px] flex items-center gap-1"><AlertTriangle className="w-2.5 h-2.5" /> {action.error || "Execution failed"}</p>
                    )}
                    {action.status === "running" && (
                      <p className="text-cyan-400 text-[10px] flex items-center gap-1"><Loader2 className="w-2.5 h-2.5 animate-spin" /> Running...</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-zinc-800/60 rounded-xl px-3 py-2 rounded-bl-sm">
              <Loader2 className="w-4 h-4 animate-spin text-cyan-400" />
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="px-3 py-3 border-t border-zinc-800">
        <div className="flex items-center gap-2">
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
            placeholder="Ask about Nexus..."
            className="flex-1 bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-cyan-500/50"
            disabled={loading}
            data-testid="helper-input"
          />
          <Button size="sm" onClick={handleSend} disabled={!input.trim() || loading}
            className="bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg h-9 w-9 p-0" data-testid="helper-send">
            <Send className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
