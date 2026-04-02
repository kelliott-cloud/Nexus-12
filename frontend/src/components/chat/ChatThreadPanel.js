/**
 * ChatThreadPanel — Thread side panel for replying to specific messages.
 * Extracted from ChatPanel.js for maintainability.
 */

export function ChatThreadPanel({ activeThread, threadReplies, onClose, onSendReply }) {
  if (!activeThread) return null;

  return (
    <div className="w-80 flex-shrink-0 border-l border-zinc-800/60 flex flex-col bg-zinc-950/95 backdrop-blur" data-testid="thread-panel">
      <div className="px-4 py-3 border-b border-zinc-800/60 flex items-center justify-between flex-shrink-0">
        <span className="text-sm font-medium text-zinc-200">Thread</span>
        <button onClick={onClose}
          className="text-zinc-500 hover:text-zinc-300 p-1 rounded hover:bg-zinc-800" aria-label="Close thread">
          <span className="text-lg leading-none">&times;</span>
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2 min-h-0">
        <div className="p-3 rounded-lg bg-zinc-900/60 border border-zinc-800/40">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-medium text-cyan-400">{activeThread.sender_name}</span>
            <span className="text-[9px] text-zinc-600">{activeThread.created_at ? new Date(activeThread.created_at).toLocaleTimeString() : ""}</span>
          </div>
          <p className="text-sm text-zinc-300 whitespace-pre-wrap">{activeThread.content?.substring(0, 500)}</p>
        </div>
        {threadReplies.length === 0 ? (
          <p className="text-xs text-zinc-600 text-center py-4">No replies yet. Type below to start the thread.</p>
        ) : threadReplies.map(reply => (
          <div key={reply.message_id} className="p-2.5 rounded-lg bg-zinc-900/30 border border-zinc-800/20">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-medium text-zinc-400">{reply.sender_name}</span>
              <span className="text-[9px] text-zinc-600">{reply.created_at ? new Date(reply.created_at).toLocaleTimeString() : ""}</span>
            </div>
            <p className="text-sm text-zinc-400 whitespace-pre-wrap">{reply.content}</p>
          </div>
        ))}
      </div>
      <div className="p-3 border-t border-zinc-800/60 flex-shrink-0">
        <input type="text" placeholder="Reply in thread..."
          className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-cyan-500/50"
          data-testid="thread-reply-input"
          onKeyDown={(e) => { if (e.key === "Enter" && e.target.value.trim()) { onSendReply(e.target.value); e.target.value = ""; } }} />
      </div>
    </div>
  );
}
