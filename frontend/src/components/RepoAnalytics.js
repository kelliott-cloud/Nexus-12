import { useState, useEffect } from "react";
import { api } from "@/App";
import { Badge } from "@/components/ui/badge";
import { GitCommit, FileCode, GitBranch, Eye, Users, Code2 } from "lucide-react";

export default function RepoAnalytics({ workspaceId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!workspaceId) return;
    api.get(`/workspaces/${workspaceId}/code-repo/analytics`)
      .then(r => setData(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspaceId]);

  if (loading) return <div className="text-center py-8 text-zinc-500 text-sm">Loading analytics...</div>;
  if (!data || data.file_count === 0) return (
    <div className="text-center py-8">
      <Code2 className="w-8 h-8 text-zinc-800 mx-auto mb-2" />
      <p className="text-sm text-zinc-500">No code repo activity yet</p>
    </div>
  );

  const maxLangCount = Math.max(...(data.language_stats || []).map(l => l.count), 1);

  return (
    <div className="space-y-4" data-testid="repo-analytics">
      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
        {[
          { label: "Files", value: data.file_count, icon: FileCode, color: "text-blue-400" },
          { label: "Commits", value: data.commit_count, icon: GitCommit, color: "text-emerald-400" },
          { label: "Branches", value: data.branch_count, icon: GitBranch, color: "text-purple-400" },
          { label: "Reviews", value: data.review_count, icon: Eye, color: "text-amber-400" },
          { label: "Folders", value: data.folder_count, icon: FileCode, color: "text-zinc-400" },
        ].map(s => {
          const Icon = s.icon;
          return (
            <div key={s.label} className="p-3 rounded-lg bg-zinc-800/30 border border-zinc-800/40 text-center">
              <Icon className={`w-4 h-4 ${s.color} mx-auto mb-1`} />
              <p className="text-lg font-bold text-zinc-200">{s.value}</p>
              <p className="text-[10px] text-zinc-500">{s.label}</p>
            </div>
          );
        })}
      </div>

      {/* Language breakdown */}
      {data.language_stats?.length > 0 && (
        <div className="p-4 rounded-lg bg-zinc-800/20 border border-zinc-800/40">
          <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">Languages</h4>
          <div className="space-y-2">
            {data.language_stats.map(l => (
              <div key={l.language} className="flex items-center gap-2">
                <span className="text-xs text-zinc-300 w-20 truncate">{l.language}</span>
                <div className="flex-1 h-3 bg-zinc-800 rounded-full overflow-hidden">
                  <div className="h-full bg-emerald-500/60 rounded-full transition-all" style={{ width: `${(l.count / maxLangCount) * 100}%` }} />
                </div>
                <span className="text-[10px] text-zinc-500 w-8 text-right">{l.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Top contributors */}
      {data.contributors?.length > 0 && (
        <div className="p-4 rounded-lg bg-zinc-800/20 border border-zinc-800/40">
          <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-1"><Users className="w-3 h-3" /> Contributors</h4>
          <div className="space-y-1.5">
            {data.contributors.map((c, i) => (
              <div key={c.name} className="flex items-center gap-2">
                <span className="text-[10px] text-zinc-600 w-4">{i + 1}.</span>
                <span className="text-xs text-zinc-300 flex-1">{c.name}</span>
                <Badge className="bg-zinc-800 text-zinc-400 text-[10px]">{c.commits} commits</Badge>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent commits */}
      {data.recent_commits?.length > 0 && (
        <div className="p-4 rounded-lg bg-zinc-800/20 border border-zinc-800/40">
          <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-1"><GitCommit className="w-3 h-3" /> Recent Commits</h4>
          <div className="space-y-1.5">
            {data.recent_commits.slice(0, 10).map(c => (
              <div key={c.commit_id} className="flex items-center gap-2 text-xs">
                <span className={`px-1 py-0.5 rounded text-[9px] font-mono ${
                  c.action === "create" ? "bg-emerald-500/15 text-emerald-400" :
                  c.action === "delete" ? "bg-red-500/15 text-red-400" :
                  c.action === "merge" ? "bg-purple-500/15 text-purple-400" :
                  "bg-blue-500/15 text-blue-400"
                }`}>{c.action}</span>
                <span className="text-zinc-300 truncate flex-1">{c.file_path}</span>
                <span className="text-zinc-600 text-[10px] flex-shrink-0">{c.author_name}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
