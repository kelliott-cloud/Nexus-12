/**
 * RepoDialogs — All modal dialogs for CodeRepoPanel.
 * Includes: New File, Rename, History, Commit Detail, Links, Branch, Git Push/Pull, Merge.
 * Extracted from CodeRepoPanel.js (~320 lines) for maintainability.
 */
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { FilePlus, FolderPlus, History, GitBranch, GitCommit, Loader2, Link2, Trash2 } from "lucide-react";

export function RepoDialogs({
  // New File
  newFileDialog, setNewFileDialog, newFileIsFolder, newFilePath, setNewFilePath, handleCreateFile,
  // Rename
  renameDialog, setRenameDialog, renamePath, setRenamePath, handleRenameFile,
  // History
  historyOpen, setHistoryOpen, fileHistory, commitDetail, setCommitDetail, handleRevert,
  // Links
  linksOpen, setLinksOpen, repoLinks, channels, projects, handleAddLink, handleRemoveLink,
  // Branch
  branchDialogOpen, setBranchDialogOpen, newBranchName, setNewBranchName, handleCreateBranch,
  currentBranch, branches, handleMergeBranch,
  // Git
  gitDialogOpen, setGitDialogOpen, gitAction, gitUrl, setGitUrl, gitPat, setGitPat, gitBranch, setGitBranch,
  gitLoading, handleGitAction,
  // Merge
  mergePreview, setMergePreview, merging, confirmMerge,
}) {
  return (
    <>
      {/* New File Dialog */}
      <Dialog open={newFileDialog} onOpenChange={setNewFileDialog}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-zinc-100 flex items-center gap-2">
              {newFileIsFolder ? <FolderPlus className="w-4 h-4 text-amber-400" /> : <FilePlus className="w-4 h-4 text-emerald-400" />}
              {newFileIsFolder ? "New Folder" : "New File"}
            </DialogTitle>
            <DialogDescription className="text-zinc-500 text-sm">Enter the full path (e.g., src/components/App.js)</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 mt-2">
            <Input value={newFilePath} onChange={(e) => setNewFilePath(e.target.value)}
              placeholder={newFileIsFolder ? "src/components" : "src/main.py"}
              className="bg-zinc-950 border-zinc-800 font-mono text-sm"
              onKeyDown={(e) => e.key === "Enter" && handleCreateFile()} autoFocus data-testid="new-file-path-input" />
            <Button onClick={handleCreateFile} disabled={!newFilePath.trim()}
              className="w-full bg-zinc-100 text-zinc-900 hover:bg-zinc-200" data-testid="create-file-submit-btn">Create</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Rename Dialog */}
      <Dialog open={renameDialog} onOpenChange={setRenameDialog}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-zinc-100">Rename</DialogTitle>
            <DialogDescription className="sr-only">Rename file or folder</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 mt-2">
            <Input value={renamePath} onChange={(e) => setRenamePath(e.target.value)}
              className="bg-zinc-950 border-zinc-800 font-mono text-sm"
              onKeyDown={(e) => e.key === "Enter" && handleRenameFile()} autoFocus data-testid="rename-path-input" />
            <Button onClick={handleRenameFile} disabled={!renamePath.trim()}
              className="w-full bg-zinc-100 text-zinc-900 hover:bg-zinc-200" data-testid="rename-submit-btn">Rename</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* History Dialog */}
      <Dialog open={historyOpen} onOpenChange={setHistoryOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-lg max-h-[70vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="text-zinc-100 flex items-center gap-2"><History className="w-4 h-4 text-zinc-400" /> Version History</DialogTitle>
            <DialogDescription className="sr-only">File version history</DialogDescription>
          </DialogHeader>
          <ScrollArea className="flex-1 mt-2">
            {commitDetail ? (
              <div className="space-y-3 p-1">
                <div className="flex items-center justify-between">
                  <button onClick={() => setCommitDetail(null)} className="text-xs text-cyan-400 hover:text-cyan-300">Back to history</button>
                  <Badge className="bg-zinc-800 text-zinc-400 text-[9px]">v{commitDetail.version}</Badge>
                </div>
                <pre className="text-xs text-zinc-300 bg-zinc-950 rounded-lg p-3 whitespace-pre-wrap font-mono max-h-80 overflow-y-auto">{commitDetail.content}</pre>
                <Button onClick={() => handleRevert(commitDetail)} className="w-full bg-amber-500/20 text-amber-400 hover:bg-amber-500/30 text-xs" data-testid="revert-btn">Revert to this version</Button>
              </div>
            ) : (
              <div className="space-y-1 p-1">
                {fileHistory.map(v => (
                  <button key={v.version_id || v.version} onClick={() => setCommitDetail(v)}
                    className="w-full text-left p-2.5 rounded-lg border border-zinc-800/30 hover:border-zinc-700 bg-zinc-950/50 transition-colors" data-testid={`history-v${v.version}`}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium text-zinc-300">Version {v.version}</span>
                      <span className="text-[9px] text-zinc-600">{v.created_at ? new Date(v.created_at).toLocaleString() : ""}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <GitCommit className="w-3 h-3 text-zinc-600" />
                      <span className="text-[10px] text-zinc-500">{v.commit_message || "No message"}</span>
                    </div>
                  </button>
                ))}
                {fileHistory.length === 0 && <p className="text-xs text-zinc-600 text-center py-4">No version history yet</p>}
              </div>
            )}
          </ScrollArea>
        </DialogContent>
      </Dialog>

      {/* Links Dialog */}
      <Dialog open={linksOpen} onOpenChange={setLinksOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-md">
          <DialogHeader>
            <DialogTitle className="text-zinc-100 flex items-center gap-2"><Link2 className="w-4 h-4 text-cyan-400" /> Repository Links</DialogTitle>
            <DialogDescription className="sr-only">Manage repository links</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            {/* Current links */}
            <div>
              <p className="text-xs font-medium text-zinc-400 mb-2">Current Links</p>
              {repoLinks.length === 0 ? (
                <p className="text-[10px] text-zinc-600">No links configured</p>
              ) : (
                <div className="space-y-1">
                  {repoLinks.map(link => (
                    <div key={link.link_id} className="flex items-center justify-between px-2 py-1.5 rounded bg-zinc-950 border border-zinc-800/30">
                      <span className="text-xs text-zinc-300">{link.target_type}: {link.target_name || link.target_id}</span>
                      <button onClick={() => handleRemoveLink(link.link_id)} className="text-zinc-600 hover:text-red-400"><Trash2 className="w-3 h-3" /></button>
                    </div>
                  ))}
                </div>
              )}
            </div>
            {/* Add Channel link */}
            <div>
              <p className="text-xs font-medium text-zinc-400 mb-1">Link to Channel</p>
              <div className="flex gap-1 flex-wrap">
                {(channels || []).map(ch => (
                  <button key={ch.channel_id} onClick={() => handleAddLink("channel", ch.channel_id)}
                    className="px-2 py-1 rounded text-[10px] bg-zinc-800 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-700">#{ch.name}</button>
                ))}
              </div>
            </div>
            {/* Add Project link */}
            <div>
              <p className="text-xs font-medium text-zinc-400 mb-1">Link to Project</p>
              <div className="flex gap-1 flex-wrap">
                {(projects || []).map(p => (
                  <button key={p.project_id} onClick={() => handleAddLink("project", p.project_id)}
                    className="px-2 py-1 rounded text-[10px] bg-zinc-800 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-700">{p.name}</button>
                ))}
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Branch Dialog */}
      <Dialog open={branchDialogOpen} onOpenChange={setBranchDialogOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-zinc-100 flex items-center gap-2"><GitBranch className="w-4 h-4 text-purple-400" /> Create Branch</DialogTitle>
            <DialogDescription className="text-zinc-500 text-sm">Branch from: {currentBranch}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 mt-2">
            <Input value={newBranchName} onChange={(e) => setNewBranchName(e.target.value)} placeholder="feature/my-branch"
              className="bg-zinc-950 border-zinc-800 font-mono text-sm" autoFocus data-testid="new-branch-input"
              onKeyDown={(e) => e.key === "Enter" && handleCreateBranch()} />
            <Button onClick={handleCreateBranch} disabled={!newBranchName.trim()} className="w-full bg-purple-500 hover:bg-purple-400 text-white" data-testid="create-branch-btn">Create Branch</Button>
            {branches.length > 1 && (
              <div className="border-t border-zinc-800 pt-3">
                <p className="text-xs text-zinc-500 mb-2">Merge branch into {currentBranch}:</p>
                <div className="flex gap-1 flex-wrap">
                  {branches.filter(b => b.name !== currentBranch).map(b => (
                    <button key={b.name} onClick={() => handleMergeBranch(b.name)}
                      className="px-2 py-1 rounded text-[10px] bg-zinc-800 text-zinc-400 hover:bg-purple-500/20 hover:text-purple-400">{b.name}</button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Git Push/Pull Dialog */}
      <Dialog open={gitDialogOpen} onOpenChange={setGitDialogOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-md">
          <DialogHeader>
            <DialogTitle className="text-zinc-100 flex items-center gap-2"><GitBranch className="w-4 h-4 text-emerald-400" /> Git {gitAction === "pull" ? "Pull" : "Push"}</DialogTitle>
            <DialogDescription className="text-zinc-500 text-sm">{gitAction === "pull" ? "Pull code from a GitHub repository" : "Push code to a GitHub repository"}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 mt-2">
            <div>
              <label className="text-xs font-medium text-zinc-400 mb-1 block">Repository URL</label>
              <Input value={gitUrl} onChange={(e) => setGitUrl(e.target.value)} placeholder="https://github.com/user/repo"
                className="bg-zinc-950 border-zinc-800 font-mono text-sm" data-testid="git-url-input" />
            </div>
            <div>
              <label className="text-xs font-medium text-zinc-400 mb-1 block">Personal Access Token (optional for public repos)</label>
              <Input value={gitPat} onChange={(e) => setGitPat(e.target.value)} placeholder="ghp_..." type="password"
                className="bg-zinc-950 border-zinc-800 font-mono text-sm" data-testid="git-pat-input" />
            </div>
            <div>
              <label className="text-xs font-medium text-zinc-400 mb-1 block">Branch</label>
              <Input value={gitBranch} onChange={(e) => setGitBranch(e.target.value)} placeholder="main"
                className="bg-zinc-950 border-zinc-800 font-mono text-sm" data-testid="git-branch-input" />
            </div>
            <Button onClick={handleGitAction} disabled={gitLoading || !gitUrl.trim()}
              className="w-full bg-emerald-500 hover:bg-emerald-400 text-white" data-testid="git-action-btn">
              {gitLoading ? <><Loader2 className="w-3 h-3 animate-spin mr-1" /> Processing...</> : `${gitAction === "pull" ? "Pull" : "Push"}`}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Merge Preview Dialog */}
      {mergePreview && (
        <Dialog open={!!mergePreview} onOpenChange={() => setMergePreview(null)}>
          <DialogContent className="bg-zinc-900 border-zinc-800 max-w-md">
            <DialogHeader>
              <DialogTitle className="text-zinc-100 flex items-center gap-2"><GitBranch className="w-4 h-4 text-purple-400" /> Merge Preview</DialogTitle>
              <DialogDescription className="sr-only">Preview merge changes</DialogDescription>
            </DialogHeader>
            <div className="space-y-3 mt-2">
              <p className="text-xs text-zinc-400">Merging <span className="text-purple-400 font-mono">{mergePreview.source}</span> into <span className="text-emerald-400 font-mono">{mergePreview.target}</span></p>
              <div className="p-3 rounded-lg bg-zinc-950 border border-zinc-800">
                <p className="text-xs text-zinc-300 mb-1">{mergePreview.files_to_merge || 0} files to merge</p>
                <p className="text-xs text-zinc-500">{mergePreview.new_files || 0} new files, {mergePreview.modified_files || 0} modified</p>
              </div>
              <div className="text-[10px] text-zinc-600">
                <p className="font-medium mb-1">This will:</p>
                <ul className="list-disc pl-4 space-y-0.5">
                  <li>Overwrite existing files with the same path</li>
                  <li>Create new files that don't exist in target</li>
                  <li>Create merge commits for each file</li>
                </ul>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setMergePreview(null)} className="flex-1 border-zinc-700 text-zinc-400">Cancel</Button>
                <Button onClick={confirmMerge} disabled={merging} className="flex-1 bg-purple-500 hover:bg-purple-400 text-white" data-testid="confirm-merge-btn">
                  {merging ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <GitBranch className="w-3 h-3 mr-1" />}
                  Merge
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </>
  );
}
