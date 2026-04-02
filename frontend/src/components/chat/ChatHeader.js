/**
 * ChatHeader — Channel header toolbar extracted from ChatPanel.js
 * Contains: channel name, agent panel toggle, pins, directive, activity, browser,
 * docs, error log, search, transcript, code repo, share dialog, pause/resume, auto-collab.
 */
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Hash, Loader2, Share2, Copy, Check, Upload, Code2, RotateCw, AlertTriangle, Download, Users, Target, Activity, Search, Pin, PinOff, Gavel } from "lucide-react";
import { api } from "@/App";
import { toast } from "sonner";
import { handleError } from "@/lib/errorHandler";

export function ChatHeader({
  channel, agentStatus,
  agentPanelOpen, setAgentPanelOpen,
  pinnedPanels, togglePin, setPinnedPanels,
  setDirectiveOpen,
  activityPanelOpen, setActivityPanelOpen,
  browserOpen, setBrowserOpen,
  docsPreviewOpen, setDocsPreviewOpen,
  auditLogOpen, setAuditLogOpen,
  msgSearchOpen, setMsgSearchOpen,
  onToggleCodeRepo, codeRepoOpen,
  shareOpen, setShareOpen, isPublic, setIsPublic, sharePassword, setSharePassword,
  shareLink, setShareLink, copied, setCopied,
  handleShare, copyLink,
  autoCollab, toggleAutoCollab, autoCollabInfo,
}) {
  return (
    <div className="px-6 py-3 border-b border-zinc-800/60 glass-panel" style={{ minWidth: 0 }}>
      <div className="flex items-center justify-between gap-2" style={{ minWidth: 0 }}>
        <div className="flex items-center gap-3 flex-shrink-0">
          <Hash className="w-4 h-4 text-zinc-500" />
          <span className="font-semibold text-zinc-200" data-testid="channel-name">{channel.name}</span>
        </div>
        <button
          onClick={() => setAgentPanelOpen(!agentPanelOpen)}
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border transition-all cursor-pointer flex-shrink-0 ${
            agentPanelOpen ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400" : "bg-zinc-900/60 border-zinc-800/40 text-zinc-400 hover:border-zinc-700"
          }`}
          title="Agent Panel" data-testid="agent-panel-toggle"
        >
          <Users className="w-3.5 h-3.5" />
          <span className="text-[10px] font-medium">{(channel.ai_agents || []).length} Agents</span>
          {(channel.ai_agents || []).some(a => agentStatus[a] === "thinking") && (
            <Loader2 className="w-3 h-3 animate-spin text-amber-400" />
          )}
        </button>
        {/* Pin buttons */}
        <div className="flex items-center gap-0.5 flex-shrink-0">
          <button onClick={() => togglePin("agents")}
            className={`p-1 rounded transition-colors ${pinnedPanels.agents ? "text-amber-400" : "text-zinc-700 hover:text-zinc-400"}`}
            title={pinnedPanels.agents ? "Unpin Agent Panel" : "Pin Agent Panel"}
            data-testid="pin-agents" aria-label="Pin agents panel">
            {pinnedPanels.agents ? <PinOff className="w-3 h-3" /> : <Pin className="w-3 h-3" />}
          </button>
        </div>
        {/* Action buttons */}
        <div className="flex items-center gap-1 flex-shrink-0">
          {/* Directive */}
          <button onClick={() => setDirectiveOpen(true)}
            className="p-1.5 rounded-md text-zinc-500 hover:text-amber-400 hover:bg-amber-500/10 transition-colors"
            title="Directive Engine" data-testid="directive-btn">
            <Target className="w-3.5 h-3.5" />
          </button>
          {/* Activity */}
          <button onClick={() => setActivityPanelOpen(!activityPanelOpen)}
            className={`p-1.5 rounded-md transition-colors ${activityPanelOpen ? "text-emerald-400 bg-emerald-500/10" : "text-zinc-500 hover:text-emerald-400 hover:bg-emerald-500/10"}`}
            title="Agent Actions" data-testid="activity-panel-btn">
            <Activity className="w-3.5 h-3.5" />
          </button>
          {/* Browser */}
          <button onClick={() => setBrowserOpen(!browserOpen)}
            className={`p-1.5 rounded-md transition-colors ${browserOpen ? "text-violet-400 bg-violet-500/10" : "text-zinc-500 hover:text-violet-400 hover:bg-violet-500/10"}`}
            title="Browser" data-testid="browser-panel-btn">
            <Search className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => togglePin("activity")}
            className={`p-0.5 rounded transition-colors ${pinnedPanels.activity ? "text-amber-400" : "text-zinc-700 hover:text-zinc-400"}`}
            data-testid="pin-activity">
            {pinnedPanels.activity ? <PinOff className="w-2.5 h-2.5" /> : <Pin className="w-2.5 h-2.5" />}
          </button>
          {/* Docs */}
          <button onClick={() => setDocsPreviewOpen(!docsPreviewOpen)}
            className={`p-1.5 rounded-md transition-colors ${docsPreviewOpen ? "text-amber-400 bg-amber-500/10" : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"}`}
            title="Documents" data-testid="docs-preview-btn">
            <Upload className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => togglePin("docs")}
            className={`p-0.5 rounded transition-colors ${pinnedPanels.docs ? "text-amber-400" : "text-zinc-700 hover:text-zinc-400"}`}
            data-testid="pin-docs">
            {pinnedPanels.docs ? <PinOff className="w-2.5 h-2.5" /> : <Pin className="w-2.5 h-2.5" />}
          </button>
          {/* Error Log */}
          <div className="relative">
            <button onClick={() => setAuditLogOpen(!auditLogOpen)}
              className={`p-1.5 rounded-md transition-colors ${auditLogOpen ? "text-amber-400 bg-amber-500/10" : "text-zinc-500 hover:text-red-400 hover:bg-red-500/10"}`}
              title="Agent Errors & Disagreements" data-testid="error-log-btn">
              <AlertTriangle className="w-3.5 h-3.5" />
            </button>
            {auditLogOpen && (
              <div className="absolute top-full right-0 mt-1 bg-zinc-900 border border-zinc-800 rounded-lg shadow-xl py-1 min-w-[200px] z-50">
                <button onClick={async () => {
                  setAuditLogOpen(false);
                  try {
                    const res = await api.get(`/channels/${channel.channel_id}/error-log`);
                    if ((res.data?.errors || []).length === 0) { toast.info("No errors logged"); return; }
                    const csvRes = await api.get(`/channels/${channel.channel_id}/error-log/export?format=csv`, { responseType: "blob" });
                    const url = URL.createObjectURL(new Blob([csvRes.data], { type: "text/csv" }));
                    const a = document.createElement("a"); a.href = url; a.download = `error_log_${channel.channel_id}.csv`; a.click();
                    URL.revokeObjectURL(url);
                  } catch (err) { handleError(err, "ChatHeader:errorLog"); }
                }} className="w-full text-left px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 flex items-center gap-2" data-testid="download-error-log">
                  <Download className="w-3 h-3" /> Download Error Log
                </button>
                <button onClick={() => {
                  setAuditLogOpen(false);
                  setPinnedPanels(p => ({ ...p, audit: !p.audit }));
                }} className="w-full text-left px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 flex items-center gap-2" data-testid="disagreement-audit-btn">
                  <Gavel className="w-3 h-3" /> Disagreement Audit Log
                </button>
              </div>
            )}
          </div>
          {/* Search */}
          <button onClick={() => setMsgSearchOpen(!msgSearchOpen)}
            className={`p-1.5 rounded-md transition-colors ${msgSearchOpen ? "text-blue-400 bg-blue-500/10" : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"}`}
            title="Search messages (Ctrl+F)" data-testid="msg-search-btn">
            <Search className="w-3.5 h-3.5" />
          </button>
          {/* Transcript */}
          <button onClick={async () => {
            try {
              const res = await api.get(`/channels/${channel.channel_id}/transcript`, { responseType: "blob" });
              const blobUrl = URL.createObjectURL(res.data);
              const link = document.createElement("a"); link.href = blobUrl; link.download = `${channel.name || "transcript"}.txt`;
              document.body.appendChild(link); link.click(); document.body.removeChild(link);
              URL.revokeObjectURL(blobUrl);
              toast.success("Downloading transcript...");
            } catch { toast.error("Transcript download failed"); }
          }} className="p-1.5 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
            title="Download chat transcript" data-testid="download-transcript-btn">
            <Download className="w-3.5 h-3.5" />
          </button>
          {/* Code Repo */}
          {onToggleCodeRepo && (
            <button onClick={onToggleCodeRepo}
              className={`p-1.5 rounded-md transition-colors ${codeRepoOpen ? "text-emerald-400 bg-emerald-500/10" : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"}`}
              title={codeRepoOpen ? "Close Code Repo" : "Open Code Repo"} data-testid="toggle-code-repo-btn">
              <Code2 className="w-3.5 h-3.5" />
            </button>
          )}
          {onToggleCodeRepo && (
            <button onClick={() => togglePin("code_repo")}
              className={`p-0.5 rounded transition-colors ${pinnedPanels.code_repo ? "text-amber-400" : "text-zinc-700 hover:text-zinc-400"}`}
              title={pinnedPanels.code_repo ? "Unpin Code Repo" : "Pin Code Repo"} data-testid="pin-code-repo">
              {pinnedPanels.code_repo ? <PinOff className="w-2.5 h-2.5" /> : <Pin className="w-2.5 h-2.5" />}
            </button>
          )}
          {/* Share Dialog */}
          <Dialog open={shareOpen} onOpenChange={setShareOpen}>
            <DialogTrigger asChild>
              <button className="ml-2 p-1.5 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors" data-testid="share-btn">
                <Share2 className="w-3.5 h-3.5" />
              </button>
            </DialogTrigger>
            <DialogContent className="bg-zinc-900 border-zinc-800">
              <DialogHeader>
                <DialogTitle className="text-zinc-100" style={{ fontFamily: 'Syne, sans-serif' }}>Share Conversation</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 mt-2">
                <div className="flex items-center gap-4">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="radio" checked={isPublic} onChange={() => setIsPublic(true)} className="accent-zinc-100" />
                    <span className="text-sm text-zinc-300">Public (anyone with link)</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="radio" checked={!isPublic} onChange={() => setIsPublic(false)} className="accent-zinc-100" />
                    <span className="text-sm text-zinc-300">Password protected</span>
                  </label>
                </div>
                {!isPublic && (
                  <Input placeholder="Set password" value={sharePassword} onChange={(e) => setSharePassword(e.target.value)}
                    className="bg-zinc-950 border-zinc-800 placeholder:text-zinc-600" data-testid="share-password-input" />
                )}
                {!shareLink ? (
                  <Button onClick={handleShare} className="w-full bg-zinc-100 text-zinc-900 hover:bg-zinc-200" data-testid="create-share-btn">
                    Create Share Link
                  </Button>
                ) : (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <Input value={shareLink} readOnly className="bg-zinc-950 border-zinc-800 text-xs font-mono" data-testid="share-link-input" />
                      <Button onClick={copyLink} size="sm" variant="outline" className="border-zinc-700 flex-shrink-0" data-testid="copy-share-btn">
                        {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                      </Button>
                    </div>
                    <p className="text-xs text-zinc-500">Link expires in 7 days</p>
                  </div>
                )}
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>
    </div>
  );
}
