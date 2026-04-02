import { useState, useEffect } from "react";
import { api } from "@/App";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Loader2, Brain, Search, ThumbsUp, ThumbsDown, RefreshCw, GitBranch, Eye } from "lucide-react";
import { toast } from "sonner";

const TYPE_COLORS = {
  decision: "bg-violet-500/15 text-violet-400", fact: "bg-cyan-500/15 text-cyan-400",
  concept: "bg-blue-500/15 text-blue-400", person: "bg-pink-500/15 text-pink-400",
  tool: "bg-amber-500/15 text-amber-400", process: "bg-emerald-500/15 text-emerald-400",
  preference: "bg-orange-500/15 text-orange-400",
};

export default function KnowledgeExplorer({ workspaceId }) {
  const [entities, setEntities] = useState([]);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [neighborhood, setNeighborhood] = useState(null);

  useEffect(() => { loadEntities(); }, [workspaceId, typeFilter]);

  const loadEntities = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: "100" });
      if (typeFilter) params.set("entity_type", typeFilter);
      if (search) params.set("search", search);
      const r = await api.get(`/workspaces/${workspaceId}/knowledge?${params}`);
      setEntities(r.data?.entities || []);
    } catch {}
    setLoading(false);
  };

  const loadNeighborhood = async (entityId) => {
    try {
      const r = await api.get(`/workspaces/${workspaceId}/knowledge/${entityId}/neighborhood?depth=2`);
      setNeighborhood(r.data);
    } catch { setNeighborhood(null); }
  };

  const feedback = async (entityId, action) => {
    try {
      await api.post(`/workspaces/${workspaceId}/knowledge/${entityId}/feedback`, { action });
      toast.success(action === "upvote" ? "Boosted" : "Updated");
      loadEntities();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  return (
    <div className="p-6 space-y-6" data-testid="knowledge-explorer">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-violet-600 flex items-center justify-center">
            <Brain className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-zinc-100" style={{ fontFamily: 'Syne, sans-serif' }}>Knowledge Graph</h2>
            <p className="text-xs text-zinc-500">Institutional knowledge that compounds over time from all workspace activity</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={loadEntities} className="border-zinc-700 text-zinc-400">
          <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Refresh
        </Button>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex-1 relative">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-zinc-600" />
          <Input value={search} onChange={e => setSearch(e.target.value)} onKeyDown={e => e.key === "Enter" && loadEntities()}
            placeholder="Search knowledge..." className="pl-10 bg-zinc-900 border-zinc-800 text-sm" />
        </div>
        <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}
          className="bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-300">
          <option value="">All types</option>
          {["decision","fact","concept","person","tool","process","preference"].map(t =>
            <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      {loading ? <div className="py-12 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-zinc-500" /></div> : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
            {entities.length === 0 ? (
              <div className="text-center py-12 text-zinc-500 text-sm">
                <Brain className="w-10 h-10 mx-auto mb-3 text-zinc-700" />
                No knowledge entities yet. Start conversations and the graph grows automatically.
              </div>
            ) : entities.map(e => (
              <div key={e.entity_id} className={`p-3 rounded-xl border cursor-pointer transition-colors ${
                selected?.entity_id === e.entity_id ? "border-cyan-500/30 bg-cyan-500/5" : "border-zinc-800/40 bg-zinc-950/50 hover:border-zinc-700"
              }`} onClick={() => { setSelected(e); loadNeighborhood(e.entity_id); }}>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <Badge className={`text-[9px] ${TYPE_COLORS[e.entity_type] || TYPE_COLORS.fact}`}>{e.entity_type}</Badge>
                      <span className="text-sm font-medium text-zinc-200 truncate">{e.name}</span>
                    </div>
                    <p className="text-xs text-zinc-500 mt-1 line-clamp-2">{e.description}</p>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <button onClick={ev => { ev.stopPropagation(); feedback(e.entity_id, "upvote"); }} className="p-1 text-zinc-600 hover:text-emerald-400"><ThumbsUp className="w-3 h-3" /></button>
                    <button onClick={ev => { ev.stopPropagation(); feedback(e.entity_id, "downvote"); }} className="p-1 text-zinc-600 hover:text-red-400"><ThumbsDown className="w-3 h-3" /></button>
                  </div>
                </div>
                <div className="flex items-center gap-3 mt-2 text-[10px] text-zinc-600">
                  <span>Confidence: {((e.confidence || 0) * 100).toFixed(0)}%</span>
                  <span>Accessed: {e.access_count || 0}x</span>
                </div>
              </div>
            ))}
          </div>
          <div className="space-y-3">
            {selected ? (
              <>
                <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/40">
                  <Badge className={`text-[9px] ${TYPE_COLORS[selected.entity_type] || TYPE_COLORS.fact}`}>{selected.entity_type}</Badge>
                  <h3 className="text-sm font-semibold text-zinc-100 mt-1">{selected.name}</h3>
                  <p className="text-xs text-zinc-400 mt-1">{selected.description}</p>
                </div>
                {neighborhood && neighborhood.nodes?.length > 1 && (
                  <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/40">
                    <p className="text-xs font-medium text-zinc-300 mb-2 flex items-center gap-1.5"><GitBranch className="w-3.5 h-3.5" /> Connected ({neighborhood.nodes.length - 1})</p>
                    <div className="space-y-1.5 max-h-[300px] overflow-y-auto">
                      {neighborhood.nodes.filter(n => n.entity_id !== selected.entity_id).map(n => (
                        <div key={n.entity_id} className="flex items-center gap-2 p-2 rounded-lg bg-zinc-950/50 border border-zinc-800/30 cursor-pointer hover:border-zinc-700"
                          onClick={() => { setSelected(n); loadNeighborhood(n.entity_id); }}>
                          <Badge className={`text-[8px] ${TYPE_COLORS[n.entity_type] || TYPE_COLORS.fact}`}>{n.entity_type}</Badge>
                          <span className="text-xs text-zinc-300 truncate">{n.name}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="text-center py-16 text-zinc-600 text-sm">
                <Eye className="w-8 h-8 mx-auto mb-3 text-zinc-700" />
                Select an entity to explore relationships
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
