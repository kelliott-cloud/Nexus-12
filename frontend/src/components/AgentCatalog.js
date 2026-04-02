import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { handleSilent } from "@/lib/errorHandler";
import { toast } from "sonner";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import {
  Search, Download, Star, Code, Palette, BarChart3, Settings, Brain,
  Shield, Zap, Eye, Copy, ChevronRight, Users, TrendingUp
} from "lucide-react";

const CATEGORY_ICONS = { engineering: Code, product: Palette, data: BarChart3, operations: Settings };
const CATEGORY_COLORS = { engineering: "#3B82F6", product: "#8B5CF6", data: "#10B981", operations: "#F59E0B" };

export default function AgentCatalog({ workspaceId }) {
  const [templates, setTemplates] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [detailTemplate, setDetailTemplate] = useState(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  const fetchTemplates = useCallback(async () => {
    try {
      const res = await api.get("/catalog/templates", { params: selectedCategory ? { category: selectedCategory } : {} });
      setTemplates(res.data.templates || []);
    } catch (err) { handleSilent(err, "AgentCatalog:fetch"); }
    setLoading(false);
  }, [selectedCategory]);

  useEffect(() => { fetchTemplates(); }, [fetchTemplates]);

  const handleClone = async (template) => {
    try {
      await api.post(`/workspaces/${workspaceId}/agents/studio`, {
        name: template.name,
        description: template.description,
        base_model: template.recommended_model || "claude",
        system_prompt: template.system_prompt || "",
        color: CATEGORY_COLORS[template.category] || "#6366F1",
        category: template.category || "custom",
        tags: template.tags || [],
        skills: template.skills || [],
        allowed_tools: template.allowed_tools || [],
        denied_tools: template.denied_tools || [],
        personality: template.personality || {},
        guardrails: template.guardrails || {},
        preferred_role: template.preferred_role || "contributor",
      });
      toast.success(`${template.name} added to workspace`);
    } catch (err) { toast.error("Failed to add template"); }
  };

  const openDetail = (tpl) => { setDetailTemplate(tpl); setDetailOpen(true); };

  const filtered = templates.filter(t =>
    !searchQuery || t.name?.toLowerCase().includes(searchQuery.toLowerCase()) || t.description?.toLowerCase().includes(searchQuery.toLowerCase()) || t.tags?.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const allCategories = [...new Set(templates.map(t => t.category))];

  if (loading) return <div className="flex-1 flex items-center justify-center"><div className="text-zinc-500 text-sm">Loading catalog...</div></div>;

  return (
    <div className="flex-1 flex flex-col overflow-hidden" data-testid="agent-catalog">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-zinc-800/60">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100" style={{ fontFamily: "Syne, sans-serif" }}>Agent Templates</h2>
            <p className="text-xs text-zinc-500 mt-0.5">{templates.length} pre-built agent configurations</p>
          </div>
        </div>
        <div className="flex items-center gap-2 mt-3">
          <div className="relative flex-1 max-w-xs">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-500" />
            <Input value={searchQuery} onChange={e => setSearchQuery(e.target.value)} placeholder="Search templates..." className="pl-8 bg-zinc-950 border-zinc-800 text-zinc-100 text-xs" data-testid="catalog-search" />
          </div>
          <div className="flex gap-1">
            <button onClick={() => setSelectedCategory(null)} className={`px-2.5 py-1.5 rounded-md text-[10px] font-medium transition-colors ${!selectedCategory ? "bg-zinc-700 text-zinc-100" : "text-zinc-500 hover:text-zinc-300"}`} data-testid="catalog-filter-all">
              All
            </button>
            {allCategories.map(cat => {
              const Icon = CATEGORY_ICONS[cat] || Brain;
              return (
                <button key={cat} onClick={() => setSelectedCategory(cat === selectedCategory ? null : cat)} className={`px-2.5 py-1.5 rounded-md text-[10px] font-medium transition-colors flex items-center gap-1 ${selectedCategory === cat ? "bg-zinc-700 text-zinc-100" : "text-zinc-500 hover:text-zinc-300"}`} data-testid={`catalog-filter-${cat}`}>
                  <Icon className="w-3 h-3" /> {cat}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {filtered.map(tpl => (
              <TemplateCard key={tpl.template_id} template={tpl} onUse={() => handleClone(tpl)} onDetail={() => openDetail(tpl)} />
            ))}
          </div>
          {filtered.length === 0 && (
            <div className="text-center py-16">
              <Brain className="w-10 h-10 text-zinc-700 mx-auto mb-2" />
              <p className="text-sm text-zinc-500">No templates match your search</p>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Detail Dialog */}
      <Dialog open={detailOpen} onOpenChange={setDetailOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-lg max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-zinc-100">{detailTemplate?.name}</DialogTitle>
            <DialogDescription className="sr-only">Template details</DialogDescription>
          </DialogHeader>
          {detailTemplate && (
            <div className="space-y-4">
              <p className="text-xs text-zinc-400">{detailTemplate.description}</p>

              {/* Skills */}
              <div>
                <p className="text-[10px] font-semibold text-zinc-500 uppercase mb-1.5">Skills</p>
                <div className="flex gap-1.5 flex-wrap">
                  {detailTemplate.skills?.map(s => (
                    <Badge key={s.skill_id} variant="secondary" className="bg-zinc-800 text-zinc-300 text-[10px]">
                      {s.skill_id.replace(/_/g, " ")} ({s.level})
                    </Badge>
                  ))}
                </div>
              </div>

              {/* Personality */}
              {detailTemplate.personality && (
                <div>
                  <p className="text-[10px] font-semibold text-zinc-500 uppercase mb-1.5">Personality</p>
                  <div className="grid grid-cols-2 gap-2 text-xs text-zinc-400">
                    <span>Tone: {detailTemplate.personality.tone}</span>
                    <span>Verbosity: {detailTemplate.personality.verbosity}</span>
                    <span>Risk: {detailTemplate.personality.risk_tolerance}</span>
                    <span>Style: {detailTemplate.personality.collaboration_style}</span>
                  </div>
                </div>
              )}

              {/* Tools */}
              <div className="grid grid-cols-2 gap-3">
                {detailTemplate.allowed_tools?.length > 0 && (
                  <div>
                    <p className="text-[10px] font-semibold text-emerald-500 uppercase mb-1">Allowed Tools</p>
                    <div className="flex gap-1 flex-wrap">
                      {detailTemplate.allowed_tools.map(t => (
                        <Badge key={t} variant="secondary" className="bg-emerald-500/10 text-emerald-400 text-[9px]">{t}</Badge>
                      ))}
                    </div>
                  </div>
                )}
                {detailTemplate.denied_tools?.length > 0 && (
                  <div>
                    <p className="text-[10px] font-semibold text-red-500 uppercase mb-1">Denied Tools</p>
                    <div className="flex gap-1 flex-wrap">
                      {detailTemplate.denied_tools.map(t => (
                        <Badge key={t} variant="secondary" className="bg-red-500/10 text-red-400 text-[9px]">{t}</Badge>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Tags */}
              {detailTemplate.tags?.length > 0 && (
                <div className="flex gap-1 flex-wrap">
                  {detailTemplate.tags.map(t => <Badge key={t} variant="secondary" className="bg-zinc-800 text-zinc-500 text-[9px]">{t}</Badge>)}
                </div>
              )}

              <Button onClick={() => { handleClone(detailTemplate); setDetailOpen(false); }} className="w-full bg-cyan-600 hover:bg-cyan-700 text-white gap-1.5 text-xs" data-testid="use-template-btn">
                <Download className="w-3.5 h-3.5" /> Use This Template
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function TemplateCard({ template, onUse, onDetail }) {
  const Icon = CATEGORY_ICONS[template.category] || Brain;
  const color = CATEGORY_COLORS[template.category] || "#6366F1";

  return (
    <div className="bg-zinc-900/50 border border-zinc-800/60 rounded-xl p-4 hover:border-zinc-700/60 transition-all group cursor-pointer" onClick={onDetail} data-testid={`template-card-${template.template_id}`}>
      <div className="flex items-start justify-between mb-2.5">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ backgroundColor: color + "15", color }}>
            <Icon className="w-4 h-4" />
          </div>
          <div>
            <p className="text-sm font-medium text-zinc-100">{template.name}</p>
            <p className="text-[10px] text-zinc-600">{template.recommended_model} / {template.category}</p>
          </div>
        </div>
        {template.avg_rating > 0 && (
          <div className="flex items-center gap-0.5 text-amber-400">
            <Star className="w-3 h-3 fill-current" />
            <span className="text-[10px]">{template.avg_rating}</span>
          </div>
        )}
      </div>

      <p className="text-xs text-zinc-500 mb-3 line-clamp-2">{template.description}</p>

      {/* Skill pills */}
      {template.skills?.length > 0 && (
        <div className="flex gap-1 flex-wrap mb-3">
          {template.skills.slice(0, 3).map(s => (
            <Badge key={s.skill_id} variant="secondary" className="text-[9px] bg-zinc-800 text-zinc-400 px-1.5 py-0">
              {s.skill_id.replace(/_/g, " ")}
            </Badge>
          ))}
          {template.skills.length > 3 && <Badge variant="secondary" className="text-[9px] bg-zinc-800 text-zinc-500 px-1.5 py-0">+{template.skills.length - 3}</Badge>}
        </div>
      )}

      <div className="flex items-center justify-between">
        <div className="flex gap-3 text-[10px] text-zinc-600">
          {template.popularity > 0 && <span className="flex items-center gap-0.5"><Users className="w-2.5 h-2.5" />{template.popularity.toLocaleString()}</span>}
        </div>
        <Button variant="ghost" size="sm" onClick={e => { e.stopPropagation(); onUse(); }} className="text-cyan-400 hover:text-cyan-300 hover:bg-cyan-500/10 text-[10px] h-7 px-2 opacity-0 group-hover:opacity-100 transition-opacity" data-testid={`use-template-${template.template_id}`}>
          <Download className="w-3 h-3 mr-1" /> Use
        </Button>
      </div>
    </div>
  );
}
