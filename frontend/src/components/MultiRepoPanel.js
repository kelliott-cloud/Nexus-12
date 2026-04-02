import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Plus, GitBranch, FileCode, Trash2, ArrowLeft, Loader2, Copy, FolderGit2 } from "lucide-react";
import CodeRepoPanel from "@/components/CodeRepoPanel";

export default function MultiRepoPanel({ workspaceId }) {
  const [repos, setRepos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [selectedRepo, setSelectedRepo] = useState(null);
  const [showCreate, setShowCreate] = useState(false);

  const loadRepos = async () => {
    try {
      const r = await api.get(`/workspaces/${workspaceId}/code-repos`);
      setRepos(r.data?.repos || []);
    } catch {}
    setLoading(false);
  };

  useEffect(() => { loadRepos(); }, [workspaceId]);

  const createRepo = async () => {
    if (!newName.trim()) { toast.error("Repository name required"); return; }
    setCreating(true);
    try {
      const r = await api.post(`/workspaces/${workspaceId}/code-repos`, {
        name: newName.trim(), description: newDesc.trim()
      });
      toast.success(`Repository "${r.data.name}" created`);
      setNewName(""); setNewDesc(""); setShowCreate(false);
      loadRepos();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
    setCreating(false);
  };

  const deleteRepo = async (repoId, name) => {
    if (!confirm(`Delete repository "${name}" and ALL its files? This cannot be undone.`)) return;
    try {
      await api.delete(`/workspaces/${workspaceId}/code-repos/${repoId}`);
      toast.success("Repository deleted");
      loadRepos();
    } catch (err) { toast.error("Delete failed"); }
  };

  // If a repo is selected, show its file tree
  if (selectedRepo) {
    return (
      <div className="flex-1 flex flex-col min-h-0">
        <div className="flex items-center gap-3 px-4 py-2.5 border-b border-zinc-800/40">
          <button onClick={() => setSelectedRepo(null)} className="text-zinc-500 hover:text-zinc-200 transition-colors">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <FolderGit2 className="w-4 h-4 text-emerald-400" />
          <span className="text-sm font-semibold text-zinc-200">{selectedRepo.name}</span>
          <Badge className="bg-zinc-800 text-zinc-400 text-[9px]">{selectedRepo.repo_id}</Badge>
          <button onClick={() => { navigator.clipboard.writeText(selectedRepo.repo_id); toast.success("Repo ID copied"); }}
            className="text-zinc-600 hover:text-zinc-300"><Copy className="w-3 h-3" /></button>
        </div>
        <CodeRepoPanel workspaceId={workspaceId} repoId={selectedRepo.repo_id}
          isOpen={true} onClose={() => setSelectedRepo(null)} isInline={true} />
      </div>
    );
  }

  if (loading) return <div className="p-6 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-zinc-600" /></div>;

  return (
    <div className="flex-1 overflow-y-auto p-6" data-testid="multi-repo-panel">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-bold text-zinc-100" style={{ fontFamily: 'Syne, sans-serif' }}>Code Repositories</h2>
            <p className="text-sm text-zinc-500 mt-1">{repos.length} {repos.length === 1 ? 'repository' : 'repositories'}</p>
          </div>
          <Button onClick={() => setShowCreate(true)} size="sm" className="bg-emerald-600 hover:bg-emerald-500 text-white" data-testid="create-repo-btn">
            <Plus className="w-3.5 h-3.5 mr-1.5" /> New Repository
          </Button>
        </div>

        {/* Create form */}
        {showCreate && (
          <div className="p-4 mb-4 rounded-xl bg-zinc-900/60 border border-zinc-800/60 space-y-3">
            <Input placeholder="Repository name" value={newName} onChange={e => setNewName(e.target.value)}
              className="bg-zinc-800 border-zinc-700 text-sm" data-testid="repo-name-input" autoFocus />
            <Input placeholder="Description (optional)" value={newDesc} onChange={e => setNewDesc(e.target.value)}
              className="bg-zinc-800 border-zinc-700 text-sm" />
            <div className="flex gap-2">
              <Button onClick={createRepo} disabled={creating} size="sm" className="bg-emerald-600 hover:bg-emerald-500 text-white">
                {creating ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <Plus className="w-3.5 h-3.5 mr-1" />}
                Create
              </Button>
              <Button onClick={() => { setShowCreate(false); setNewName(""); setNewDesc(""); }} variant="outline" size="sm" className="border-zinc-700 text-zinc-400">Cancel</Button>
            </div>
          </div>
        )}

        {/* Repo list */}
        {repos.length === 0 ? (
          <div className="text-center py-16">
            <FolderGit2 className="w-12 h-12 text-zinc-800 mx-auto mb-3" />
            <p className="text-sm text-zinc-500">No repositories yet</p>
            <p className="text-xs text-zinc-600 mt-1">Create a repository to start managing code</p>
          </div>
        ) : (
          <div className="space-y-2">
            {repos.map(repo => (
              <div key={repo.repo_id}
                className="group flex items-center justify-between p-4 rounded-xl bg-zinc-900/40 border border-zinc-800/50 hover:border-zinc-700 transition-colors cursor-pointer"
                onClick={() => setSelectedRepo(repo)}
                data-testid={`repo-${repo.repo_id}`}>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                    <GitBranch className="w-5 h-5 text-emerald-400" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-zinc-200 group-hover:text-emerald-300 transition-colors">{repo.name}</span>
                      <Badge className="bg-zinc-800 text-zinc-500 text-[8px]">{repo.default_branch || "main"}</Badge>
                    </div>
                    {repo.description && <p className="text-[11px] text-zinc-600 mt-0.5">{repo.description}</p>}
                    <div className="flex items-center gap-3 mt-1">
                      <span className="text-[10px] text-zinc-600"><FileCode className="w-3 h-3 inline mr-0.5" />{repo.file_count || 0} files</span>
                      <span className="text-[10px] text-zinc-700">{repo.repo_id}</span>
                    </div>
                  </div>
                </div>
                <button onClick={e => { e.stopPropagation(); deleteRepo(repo.repo_id, repo.name); }}
                  className="opacity-0 group-hover:opacity-100 p-1.5 rounded hover:bg-zinc-800 text-zinc-600 hover:text-red-400 transition-all">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
