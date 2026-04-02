/**
 * RepoToolbar — Header toolbar for CodeRepoPanel with branch selector,
 * git push/pull, ZIP download/import, links, and close button.
 * Extracted from CodeRepoPanel.js for maintainability.
 */
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { FileCode, Download, Upload, Plus, GitBranch, Link2, X, Loader2 } from "lucide-react";
import { api } from "@/App";
import { toast } from "sonner";

export function RepoToolbar({
  files, currentBranch, branches, setCurrentBranch,
  setBranchDialogOpen, setGitAction, setGitDialogOpen,
  workspaceId, repoId, setLinksOpen,
  onClose, isInline,
}) {
  return (
    <div className="flex-shrink-0 flex items-center justify-between px-4 py-2.5 border-b border-zinc-800/60 bg-zinc-900/80">
      <div className="flex items-center gap-2">
        <FileCode className="w-4 h-4 text-emerald-400" />
        <span className="text-sm font-semibold text-zinc-200" style={{ fontFamily: "Syne, sans-serif" }}>Code Repository</span>
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-500 font-mono">
          {files.filter(f => !f.is_folder).length} files
        </span>
        {/* Branch selector */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex items-center gap-1 px-2 py-0.5 rounded bg-zinc-800 border border-zinc-700/50 text-[10px] text-zinc-300 hover:bg-zinc-700 transition-colors" data-testid="branch-selector">
              <GitBranch className="w-3 h-3" />
              {currentBranch}
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="bg-zinc-900 border-zinc-800" align="start">
            {branches.map(b => (
              <DropdownMenuItem key={b.branch_id || b.name}
                onClick={() => setCurrentBranch(b.name)}
                className={`text-xs cursor-pointer ${currentBranch === b.name ? "bg-zinc-800 text-zinc-100" : "text-zinc-400 hover:bg-zinc-800"}`}>
                <GitBranch className="w-3 h-3 mr-1.5" />{b.name} {b.is_default && <span className="ml-1 text-[9px] text-zinc-600">(default)</span>}
              </DropdownMenuItem>
            ))}
            <DropdownMenuItem onClick={() => setBranchDialogOpen(true)} className="text-emerald-400 hover:bg-zinc-800 cursor-pointer text-xs">
              <Plus className="w-3 h-3 mr-1.5" />New Branch
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <div className="flex items-center gap-1">
        {/* Git push/pull */}
        <Button variant="ghost" size="sm"
          onClick={() => { setGitAction("pull"); setGitDialogOpen(true); }}
          className="text-zinc-400 hover:text-zinc-200 h-7 px-2" title="Pull from GitHub" data-testid="git-pull-btn">
          <Download className="w-3.5 h-3.5" />
        </Button>
        <Button variant="ghost" size="sm"
          onClick={() => { setGitAction("push"); setGitDialogOpen(true); }}
          className="text-zinc-400 hover:text-zinc-200 h-7 px-2" title="Push to GitHub" data-testid="git-push-btn">
          <Upload className="w-3.5 h-3.5" />
        </Button>
        <div className="w-px h-4 bg-zinc-800 mx-0.5" />
        {/* ZIP download */}
        <Button variant="ghost" size="sm"
          onClick={async () => {
            try {
              toast.info("Preparing ZIP download...");
              const res = await api.get(`/workspaces/${workspaceId}/code-repo/download${repoId ? `?repo_id=${repoId}` : ""}`, { responseType: "blob" });
              const blobUrl = URL.createObjectURL(res.data);
              const link = document.createElement("a");
              link.href = blobUrl;
              link.download = `repo-${repoId || "default"}.zip`;
              document.body.appendChild(link);
              link.click();
              document.body.removeChild(link);
              URL.revokeObjectURL(blobUrl);
              toast.success("Downloading repo as ZIP...");
            } catch (err) {
              toast.error("ZIP download failed");
            }
          }}
          className="text-zinc-400 hover:text-zinc-200 h-7 px-2" title="Download repo as ZIP" data-testid="repo-download-btn">
          <Download className="w-3.5 h-3.5" />
        </Button>
        {/* ZIP import */}
        <Button variant="ghost" size="sm"
          onClick={() => {
            const input = document.createElement("input");
            input.type = "file";
            input.accept = ".zip";
            input.onchange = async (e) => {
              const file = e.target.files[0];
              if (!file) return;
              if (file.size > 50 * 1024 * 1024) { toast.error("ZIP file too large (50MB max)"); return; }
              const formData = new FormData();
              formData.append("file", file);
              if (repoId) formData.append("repo_id", repoId);
              try {
                toast.info("Importing ZIP...");
                await api.post(`/workspaces/${workspaceId}/code-repo/import-zip`, formData);
                toast.success("ZIP imported! Refreshing...");
                window.location.reload();
              } catch (err) { toast.error("Import failed"); }
            };
            input.click();
          }}
          className="text-zinc-400 hover:text-zinc-200 h-7 px-2" title="Import ZIP" data-testid="repo-import-btn">
          <Upload className="w-3.5 h-3.5" />
        </Button>
        {/* Links */}
        <Button variant="ghost" size="sm"
          onClick={() => setLinksOpen(true)}
          className="text-zinc-400 hover:text-zinc-200 h-7 px-2" title="Links" data-testid="repo-links-btn">
          <Link2 className="w-3.5 h-3.5" />
        </Button>
        {/* Close */}
        {!isInline && (
          <Button variant="ghost" size="sm" onClick={onClose}
            className="text-zinc-400 hover:text-zinc-200 h-7 px-2" title="Close" data-testid="close-code-repo-btn">
            <X className="w-3.5 h-3.5" />
          </Button>
        )}
      </div>
    </div>
  );
}
