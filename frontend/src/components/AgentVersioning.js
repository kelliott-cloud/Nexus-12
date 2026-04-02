import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { handleSilent } from "@/lib/errorHandler";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  GitBranch, RotateCcw, Plus, Trash2, ChevronDown, ChevronRight, Clock, Loader2, BookOpen, Shield
} from "lucide-react";

export default function AgentVersioning({ workspaceId, agentId, agentName }) {
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [rollingBack, setRollingBack] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [label, setLabel] = useState("");
  const [description, setDescription] = useState("");
  const [includeKnowledge, setIncludeKnowledge] = useState(true);

  const fetchVersions = useCallback(async () => {
    if (!agentId) return;
    try {
      const res = await api.get(`/workspaces/${workspaceId}/agents/${agentId}/versions`);
      setVersions(res.data.versions || []);
    } catch (err) { handleSilent(err, "Versions:fetch"); }
    setLoading(false);
  }, [workspaceId, agentId]);

  useEffect(() => { fetchVersions(); }, [fetchVersions]);

  const createVersion = async () => {
    setCreating(true);
    try {
      await api.post(`/workspaces/${workspaceId}/agents/${agentId}/versions`, {
        label, description, include_knowledge: includeKnowledge,
      });
      toast.success("Version snapshot created");
      setShowCreate(false);
      setLabel(""); setDescription("");
      fetchVersions();
    } catch (err) { toast.error("Failed to create version"); handleSilent(err, "Versions:create"); }
    setCreating(false);
  };

  const rollback = async (versionId, versionLabel) => {
    if (!confirm(`Rollback to "${versionLabel}"? Current state will be auto-saved first.`)) return;
    setRollingBack(versionId);
    try {
      const res = await api.post(`/workspaces/${workspaceId}/agents/${agentId}/versions/${versionId}/rollback`);
      toast.success(`Rolled back to ${res.data.label}. ${res.data.knowledge_restored} knowledge chunks restored.`);
      fetchVersions();
    } catch (err) { toast.error("Rollback failed"); handleSilent(err, "Versions:rollback"); }
    setRollingBack(null);
  };

  const deleteVersion = async (versionId) => {
    try {
      await api.delete(`/workspaces/${workspaceId}/agents/${agentId}/versions/${versionId}`);
      setVersions(prev => prev.filter(v => v.version_id !== versionId));
      toast.success("Version deleted");
    } catch { toast.error("Delete failed"); }
  };

  if (!agentId) return null;

  return (
    <div className="space-y-4" data-testid="agent-versioning">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-300 flex items-center gap-1.5">
          <GitBranch className="w-4 h-4 text-violet-400" /> Version History
        </h3>
        <Button onClick={() => setShowCreate(!showCreate)} variant="outline"
          className="text-xs h-7 border-zinc-700 text-zinc-400 gap-1" data-testid="create-version-btn">
          <Plus className="w-3 h-3" /> Snapshot
        </Button>
      </div>

      {/* Create Form */}
      {showCreate && (
        <Card className="bg-zinc-900/60 border-zinc-800/60">
          <CardContent className="p-3 space-y-2">
            <Input value={label} onChange={e => setLabel(e.target.value)} placeholder="Version label (e.g., v2.0 - Added security training)"
              className="bg-zinc-950 border-zinc-800 text-zinc-200 text-xs" data-testid="version-label" />
            <Input value={description} onChange={e => setDescription(e.target.value)} placeholder="Description (optional)"
              className="bg-zinc-950 border-zinc-800 text-zinc-200 text-xs" data-testid="version-description" />
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 text-[10px] text-zinc-400 cursor-pointer">
                <input type="checkbox" checked={includeKnowledge} onChange={e => setIncludeKnowledge(e.target.checked)}
                  className="rounded border-zinc-700" data-testid="version-include-knowledge" />
                Include knowledge chunk IDs
              </label>
              <Button onClick={createVersion} disabled={creating}
                className="bg-violet-600 hover:bg-violet-700 text-white text-xs h-7 gap-1" data-testid="save-version-btn">
                {creating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
                Create Snapshot
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Version List */}
      {loading ? (
        <div className="flex items-center justify-center py-8"><Loader2 className="w-5 h-5 animate-spin text-zinc-500" /></div>
      ) : versions.length === 0 ? (
        <Card className="bg-zinc-900/60 border-zinc-800/60">
          <CardContent className="p-6 text-center">
            <GitBranch className="w-8 h-8 text-zinc-700 mx-auto mb-2" />
            <p className="text-xs text-zinc-400">No versions yet</p>
            <p className="text-[10px] text-zinc-600 mt-0.5">Create a snapshot to save the current agent state</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-1.5">
          {versions.map((v, i) => {
            const isExpanded = expanded === v.version_id;
            const isLatest = i === 0;
            return (
              <div key={v.version_id} className={`bg-zinc-900/40 border rounded-lg overflow-hidden ${isLatest ? "border-violet-500/20" : "border-zinc-800/40"}`} data-testid={`version-${v.version_id}`}>
                <div className="flex items-center gap-3 p-2.5 cursor-pointer hover:bg-zinc-800/20 transition-colors"
                  onClick={() => setExpanded(isExpanded ? null : v.version_id)}>
                  <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold ${isLatest ? "bg-violet-500/10 text-violet-400" : "bg-zinc-800 text-zinc-500"}`}>
                    {v.version_number}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-zinc-300">{v.label}</span>
                      {isLatest && <Badge variant="secondary" className="text-[8px] bg-violet-500/10 text-violet-400">Latest</Badge>}
                    </div>
                    <div className="flex gap-3 text-[9px] text-zinc-600 mt-0.5">
                      <span>{v.snapshot?.model || "—"}</span>
                      <span>{v.knowledge_count || 0} chunks</span>
                      <span>{new Date(v.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                  <ChevronDown className={`w-3.5 h-3.5 text-zinc-600 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                </div>
                {isExpanded && (
                  <div className="px-2.5 pb-2.5 border-t border-zinc-800/30 pt-2 space-y-2">
                    {v.description && <p className="text-[10px] text-zinc-500">{v.description}</p>}
                    <div className="flex gap-3 text-[9px] text-zinc-600">
                      <span>Name: {v.snapshot?.name || "—"}</span>
                      <span>Model: {v.snapshot?.model || "—"}</span>
                      <span>Knowledge: {v.knowledge_count || 0} chunks</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Button variant="outline" size="sm" onClick={() => rollback(v.version_id, v.label)}
                        disabled={rollingBack === v.version_id}
                        className="text-[10px] h-6 px-2 border-zinc-700 text-amber-400 hover:text-amber-300 gap-1" data-testid={`rollback-${v.version_id}`}>
                        {rollingBack === v.version_id ? <Loader2 className="w-2.5 h-2.5 animate-spin" /> : <RotateCcw className="w-2.5 h-2.5" />}
                        Rollback
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => deleteVersion(v.version_id)}
                        className="text-[10px] h-6 px-2 text-zinc-600 hover:text-red-400 gap-1" data-testid={`delete-version-${v.version_id}`}>
                        <Trash2 className="w-2.5 h-2.5" /> Delete
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
