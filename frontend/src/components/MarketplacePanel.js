import { useState, useEffect, useCallback } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { api } from "@/App";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  Search, Star, Download, Users, Clock, Zap, Filter,
  ChevronRight, Globe, Building2, ArrowRight, Package
} from "lucide-react";

const CATEGORIES = [
  { key: "all", label: "All" },
  { key: "research", label: "Research" },
  { key: "content", label: "Content" },
  { key: "development", label: "Development" },
  { key: "business", label: "Business" },
  { key: "data", label: "Data" },
  { key: "marketing", label: "Marketing" },
  { key: "operations", label: "Operations" },
  { key: "general", label: "General" },
];

const DIFFICULTY_COLORS = {
  beginner: "bg-emerald-600/20 text-emerald-400",
  intermediate: "bg-amber-600/20 text-amber-400",
  advanced: "bg-red-600/20 text-red-400",
};

export default function MarketplacePanel({ workspaceId, orgId }) {
  const [templates, setTemplates] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const [scope, setScope] = useState("global");
  const [sort, setSort] = useState("popular");
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [importing, setImporting] = useState(false);

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (category !== "all") params.append("category", category);
      if (search) params.append("search", search);
      params.append("sort", sort);

      const endpoint = scope === "org" && orgId
        ? `/marketplace/org/${orgId}?${params}`
        : `/marketplace?${params}`;
      const res = await api.get(endpoint);
      setTemplates(res.data.templates || []);
      setTotal(res.data.total || 0);
    } catch (err) {
      console.error("Failed to fetch marketplace:", err);
    } finally {
      setLoading(false);
    }
  }, [category, search, sort, scope, orgId]);

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  const importTemplate = async (templateId) => {
    setImporting(true);
    try {
      await api.post(`/marketplace/${templateId}/import?workspace_id=${workspaceId}`);
      toast.success("Template imported as new workflow");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to import template");
    } finally {
      setImporting(false);
    }
  };

  const rateTemplate = async (templateId, rating) => {
    try {
      const res = await api.post(`/marketplace/${templateId}/rate`, { rating });
      setTemplates((prev) =>
        prev.map((t) =>
          t.marketplace_id === templateId
            ? { ...t, avg_rating: res.data.avg_rating, rating_count: res.data.rating_count }
            : t
        )
      );
      if (selectedTemplate?.marketplace_id === templateId) {
        setSelectedTemplate((prev) => ({
          ...prev,
          avg_rating: res.data.avg_rating,
          rating_count: res.data.rating_count,
        }));
      }
      toast.success("Rating submitted");
    } catch (err) {
      toast.error("Failed to rate template");
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h2 className="text-xl font-semibold text-zinc-100" data-testid="marketplace-heading">
            <Package className="w-5 h-5 inline-block mr-2 -mt-0.5" />
            Workflow Marketplace
          </h2>
          <p className="text-sm text-zinc-500 mt-1">Discover and import workflow templates from the community</p>
        </div>

        {/* Scope Toggle + Search */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex bg-zinc-800/60 rounded-lg p-0.5">
            <button
              onClick={() => setScope("global")}
              className={`px-3 py-1.5 text-xs rounded-md transition-colors ${scope === "global" ? "bg-zinc-700 text-zinc-100" : "text-zinc-500 hover:text-zinc-300"}`}
              data-testid="scope-global"
            >
              <Globe className="w-3 h-3 inline-block mr-1" />
              Global
            </button>
            {orgId && (
              <button
                onClick={() => setScope("org")}
                className={`px-3 py-1.5 text-xs rounded-md transition-colors ${scope === "org" ? "bg-zinc-700 text-zinc-100" : "text-zinc-500 hover:text-zinc-300"}`}
                data-testid="scope-org"
              >
                <Building2 className="w-3 h-3 inline-block mr-1" />
                Organization
              </button>
            )}
          </div>
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <Input
              placeholder="Search templates..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 bg-zinc-800/60 border-zinc-700 text-zinc-200 text-sm"
              data-testid="marketplace-search"
            />
          </div>
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            className="bg-zinc-800/60 border border-zinc-700 rounded-md px-3 py-2 text-xs text-zinc-300"
            data-testid="marketplace-sort"
          >
            <option value="popular">Most Popular</option>
            <option value="rating">Highest Rated</option>
            <option value="newest">Newest</option>
          </select>
        </div>

        {/* Category filters */}
        <div className="flex gap-2 flex-wrap">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.key}
              onClick={() => setCategory(cat.key)}
              className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                category === cat.key
                  ? "bg-zinc-700 border-zinc-600 text-zinc-100"
                  : "border-zinc-800 text-zinc-500 hover:text-zinc-300 hover:border-zinc-700"
              }`}
              data-testid={`cat-filter-${cat.key}`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* Templates Grid */}
        {loading ? (
          <div className="flex items-center justify-center py-20 text-zinc-500">Loading...</div>
        ) : templates.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-zinc-500 space-y-3" data-testid="empty-marketplace">
            <Package className="w-10 h-10 text-zinc-600" />
            <p className="text-zinc-400">No templates found</p>
            <p className="text-sm">Be the first to publish a workflow template!</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="marketplace-grid">
            {templates.map((tpl) => (
              <div
                key={tpl.marketplace_id}
                className="bg-zinc-900/60 border border-zinc-800/60 rounded-lg p-4 hover:border-zinc-700 transition-colors cursor-pointer group"
                onClick={() => setSelectedTemplate(tpl)}
                data-testid={`mkt-card-${tpl.marketplace_id}`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-700 text-zinc-400 uppercase">{tpl.category}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${DIFFICULTY_COLORS[tpl.difficulty] || "bg-zinc-700 text-zinc-400"}`}>
                    {tpl.difficulty}
                  </span>
                </div>
                <h3 className="font-medium text-zinc-200 mb-1">{tpl.name}</h3>
                <p className="text-xs text-zinc-500 mb-3 line-clamp-2">{tpl.description}</p>
                <div className="flex items-center justify-between text-xs text-zinc-600">
                  <div className="flex items-center gap-3">
                    <span className="flex items-center gap-1"><Star className="w-3 h-3" />{tpl.avg_rating || 0}</span>
                    <span className="flex items-center gap-1"><Download className="w-3 h-3" />{tpl.usage_count || 0}</span>
                    <span className="flex items-center gap-1"><Zap className="w-3 h-3" />{tpl.node_count || 0} nodes</span>
                  </div>
                  <ChevronRight className="w-3 h-3 group-hover:text-zinc-400 transition-colors" />
                </div>
                <p className="text-[10px] text-zinc-700 mt-2">by {tpl.publisher_name}</p>
              </div>
            ))}
          </div>
        )}
        <p className="text-xs text-zinc-600 text-center">{total} templates total</p>

        {/* Template Detail Dialog */}
        <Dialog open={!!selectedTemplate} onOpenChange={(open) => { if (!open) setSelectedTemplate(null); }}>
          <DialogContent className="bg-zinc-900 border-zinc-800 max-w-lg">
            <DialogHeader>
              <DialogTitle className="text-zinc-100">{selectedTemplate?.name}</DialogTitle>
              <DialogDescription className="text-zinc-500 text-sm">{selectedTemplate?.description}</DialogDescription>
            </DialogHeader>
            {selectedTemplate && (
              <div className="space-y-4 mt-2">
                <div className="flex items-center gap-3 text-xs text-zinc-400 flex-wrap">
                  <span className="px-2 py-0.5 rounded bg-zinc-800 uppercase">{selectedTemplate.category}</span>
                  <span className={`px-2 py-0.5 rounded ${DIFFICULTY_COLORS[selectedTemplate.difficulty] || "bg-zinc-800"}`}>{selectedTemplate.difficulty}</span>
                  {selectedTemplate.estimated_time && (
                    <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{selectedTemplate.estimated_time}</span>
                  )}
                </div>
                <div className="flex items-center gap-4 text-sm text-zinc-400">
                  <span className="flex items-center gap-1"><Star className="w-4 h-4 text-amber-400" />{selectedTemplate.avg_rating || 0} ({selectedTemplate.rating_count || 0} ratings)</span>
                  <span className="flex items-center gap-1"><Download className="w-4 h-4" />{selectedTemplate.usage_count || 0} imports</span>
                  <span className="flex items-center gap-1"><Zap className="w-4 h-4" />{selectedTemplate.node_count || 0} nodes</span>
                </div>
                <div className="text-xs text-zinc-500">
                  <p>Published by <span className="text-zinc-300">{selectedTemplate.publisher_name}</span></p>
                </div>
                {/* Rate */}
                <div>
                  <p className="text-xs text-zinc-400 mb-1">Rate this template:</p>
                  <div className="flex gap-1">
                    {[1, 2, 3, 4, 5].map((s) => (
                      <button key={s} onClick={() => rateTemplate(selectedTemplate.marketplace_id, s)} className="text-zinc-600 hover:text-amber-400 transition-colors" data-testid={`rate-${s}`}>
                        <Star className={`w-5 h-5 ${s <= (selectedTemplate.avg_rating || 0) ? "fill-amber-400 text-amber-400" : ""}`} />
                      </button>
                    ))}
                  </div>
                </div>
                <Button
                  onClick={() => importTemplate(selectedTemplate.marketplace_id)}
                  disabled={importing}
                  className="w-full bg-zinc-100 text-zinc-900 hover:bg-zinc-200"
                  data-testid="import-template-btn"
                >
                  <ArrowRight className="w-4 h-4 mr-2" />
                  {importing ? "Importing..." : "Import to Workspace"}
                </Button>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
