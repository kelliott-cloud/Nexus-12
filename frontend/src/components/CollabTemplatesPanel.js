import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { handleSilent } from "@/lib/errorHandler";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  BookTemplate, Download, Search, Tag, Network, Loader2, ArrowRight, Zap
} from "lucide-react";
import { FeatureHelp, FEATURE_HELP } from "@/components/FeatureHelp";

export default function CollabTemplatesPanel({ workspaceId }) {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");
  const [installing, setInstalling] = useState(null);

  const fetchTemplates = useCallback(async () => {
    try {
      const res = await api.get("/orchestration-templates");
      setTemplates(res.data.templates || []);
    } catch (err) { handleSilent(err, "CT:list"); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchTemplates(); }, [fetchTemplates]);

  const installTemplate = async (tplId) => {
    setInstalling(tplId);
    try {
      const res = await api.post(`/workspaces/${workspaceId}/orchestration-templates/${tplId}/install`);
      toast.success(`Installed as "${res.data.name}"`);
      fetchTemplates();
    } catch (err) { toast.error(err?.response?.data?.detail || "Install failed"); handleSilent(err, "CT:install"); }
    setInstalling(null);
  };

  const catColors = { research: "border-blue-800 text-blue-400", content: "border-purple-800 text-purple-400", analysis: "border-amber-800 text-amber-400", development: "border-emerald-800 text-emerald-400", knowledge: "border-cyan-800 text-cyan-400" };
  const filtered = templates.filter(t => !filter || t.name.toLowerCase().includes(filter.toLowerCase()) || (t.tags || []).some(tag => tag.includes(filter.toLowerCase())));

  if (loading) return <div className="flex-1 flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-zinc-500" /></div>;

  return (
    <div className="flex-1 overflow-y-auto p-6" data-testid="collab-templates-panel">
      <div className="max-w-5xl mx-auto space-y-6">
        <FeatureHelp featureId="collab-templates" {...FEATURE_HELP["collab-templates"]} />
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100">Collaboration Templates</h2>
            <p className="text-sm text-zinc-500 mt-1">Pre-built multi-agent orchestration workflows you can install with one click</p>
          </div>
        </div>

        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
          <Input placeholder="Search templates..." value={filter} onChange={e => setFilter(e.target.value)} className="bg-zinc-800 border-zinc-700 pl-10" data-testid="ct-search" />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered.map(tpl => (
            <Card key={tpl.template_id} className="bg-zinc-900 border-zinc-800 hover:border-zinc-700 transition-colors" data-testid={`ct-card-${tpl.template_id}`}>
              <CardContent className="py-5 space-y-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-9 h-9 rounded-lg bg-indigo-600/15 flex items-center justify-center">
                      <Network className="w-4 h-4 text-indigo-400" />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-zinc-100">{tpl.name}</div>
                      <Badge variant="outline" className={`text-xs mt-0.5 ${catColors[tpl.category] || "border-zinc-700"}`}>{tpl.category}</Badge>
                    </div>
                  </div>
                  {tpl.usage_count > 0 && <span className="text-xs text-zinc-600">{tpl.usage_count} installs</span>}
                </div>
                <p className="text-xs text-zinc-400 leading-relaxed">{tpl.description}</p>
                <div className="flex items-center gap-1.5 flex-wrap">
                  {(tpl.steps || []).map((s, i) => (
                    <div key={i} className="flex items-center gap-1">
                      <span className="px-2 py-0.5 bg-zinc-800 rounded text-xs text-zinc-300 border border-zinc-700/50">{s.step_id}</span>
                      {i < (tpl.steps?.length || 0) - 1 && <ArrowRight className="w-3 h-3 text-zinc-600" />}
                    </div>
                  ))}
                </div>
                <div className="flex items-center justify-between pt-1">
                  <div className="flex gap-1">{(tpl.tags || []).map(tag => <Badge key={tag} variant="outline" className="text-xs border-zinc-700/50 py-0">{tag}</Badge>)}</div>
                  <Button size="sm" onClick={() => installTemplate(tpl.template_id)} disabled={installing === tpl.template_id} className="bg-emerald-600 hover:bg-emerald-700 text-xs h-7" data-testid={`ct-install-${tpl.template_id}`}>
                    {installing === tpl.template_id ? <Loader2 className="w-3 h-3 animate-spin" /> : <><Download className="w-3 h-3 mr-1" /> Install</>}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
