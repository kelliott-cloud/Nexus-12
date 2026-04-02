import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { handleSilent } from "@/lib/errorHandler";
import { toast } from "sonner";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Search, Star, Filter, SlidersHorizontal, Download, Loader2, ArrowUpDown
} from "lucide-react";
import { FeatureHelp, FEATURE_HELP } from "@/components/FeatureHelp";

export default function MarketplaceAdvancedSearch() {
  const [templates, setTemplates] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [sort, setSort] = useState("popular");
  const [minRating, setMinRating] = useState("");
  const [showFilters, setShowFilters] = useState(false);

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    try {
      let url = `/marketplace?sort=${sort}&limit=20`;
      if (search) url += `&search=${encodeURIComponent(search)}`;
      if (category) url += `&category=${encodeURIComponent(category)}`;
      const res = await api.get(url);
      let list = res.data.templates || [];
      if (minRating) list = list.filter(t => (t.avg_rating || 0) >= parseFloat(minRating));
      setTemplates(list);
      setTotal(res.data.total || list.length);
    } catch (err) { handleSilent(err, "MAS:list"); }
    setLoading(false);
  }, [search, category, sort, minRating]);

  useEffect(() => { const t = setTimeout(fetchTemplates, 300); return () => clearTimeout(t); }, [fetchTemplates]);

  const categories = ["workflow", "agent", "template", "tool", "integration"];

  return (
    <div className="flex-1 overflow-y-auto p-6" data-testid="marketplace-search-panel">
      <div className="max-w-5xl mx-auto space-y-6">
        <FeatureHelp featureId="marketplace-search" {...FEATURE_HELP["marketplace-search"]} />
        <div>
          <h2 className="text-lg font-semibold text-zinc-100">Marketplace</h2>
          <p className="text-sm text-zinc-500 mt-1">Discover and install agent templates, workflows, and tools</p>
        </div>

        {/* Search + Filter Bar */}
        <div className="space-y-3">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
              <Input placeholder="Search marketplace..." value={search} onChange={e => setSearch(e.target.value)} className="bg-zinc-800 border-zinc-700 pl-10" data-testid="mas-search" />
            </div>
            <Button variant="outline" size="sm" onClick={() => setShowFilters(!showFilters)} className={`border-zinc-700 ${showFilters ? "bg-zinc-800" : ""}`} data-testid="mas-filter-toggle">
              <SlidersHorizontal className="w-4 h-4 mr-1" /> Filters
            </Button>
            <Select value={sort} onValueChange={setSort}>
              <SelectTrigger className="w-36 bg-zinc-800 border-zinc-700" data-testid="mas-sort">
                <ArrowUpDown className="w-3 h-3 mr-1" /><SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="popular">Most Popular</SelectItem>
                <SelectItem value="rating">Highest Rated</SelectItem>
                <SelectItem value="recent">Most Recent</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {showFilters && (
            <div className="flex gap-3 items-center p-3 bg-zinc-900 border border-zinc-800 rounded-lg" data-testid="mas-filters">
              <Select value={category} onValueChange={setCategory}>
                <SelectTrigger className="w-40 bg-zinc-800 border-zinc-700 h-8 text-xs"><SelectValue placeholder="All Categories" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="">All Categories</SelectItem>
                  {categories.map(c => <SelectItem key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</SelectItem>)}
                </SelectContent>
              </Select>
              <Select value={minRating} onValueChange={setMinRating}>
                <SelectTrigger className="w-32 bg-zinc-800 border-zinc-700 h-8 text-xs"><SelectValue placeholder="Min Rating" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="">Any Rating</SelectItem>
                  <SelectItem value="4">4+ Stars</SelectItem>
                  <SelectItem value="3">3+ Stars</SelectItem>
                  <SelectItem value="2">2+ Stars</SelectItem>
                </SelectContent>
              </Select>
              {(category || minRating) && (
                <Button variant="ghost" size="sm" onClick={() => { setCategory(""); setMinRating(""); }} className="text-xs text-zinc-500 h-7">Clear</Button>
              )}
              <span className="text-xs text-zinc-500 ml-auto">{total} result{total !== 1 ? "s" : ""}</span>
            </div>
          )}
        </div>

        {/* Results */}
        {loading ? (
          <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-zinc-500" /></div>
        ) : templates.length === 0 ? (
          <Card className="bg-zinc-900 border-zinc-800"><CardContent className="py-12 text-center text-zinc-500">No templates found matching your criteria.</CardContent></Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {templates.map(tpl => (
              <Card key={tpl.marketplace_id} className="bg-zinc-900 border-zinc-800 hover:border-zinc-700 transition-colors" data-testid={`mas-card-${tpl.marketplace_id}`}>
                <CardContent className="py-4 space-y-2">
                  <div className="flex items-start justify-between">
                    <h3 className="text-sm font-medium text-zinc-100 leading-tight">{tpl.name}</h3>
                    {tpl.avg_rating > 0 && (
                      <div className="flex items-center gap-1 flex-shrink-0">
                        <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                        <span className="text-xs text-zinc-300">{tpl.avg_rating?.toFixed(1)}</span>
                      </div>
                    )}
                  </div>
                  <p className="text-xs text-zinc-500 line-clamp-2">{tpl.description || "No description"}</p>
                  <div className="flex items-center justify-between pt-1">
                    <div className="flex gap-1">
                      {tpl.category && <Badge variant="outline" className="text-xs border-zinc-700 py-0">{tpl.category}</Badge>}
                      {(tpl.tags || []).slice(0, 2).map(t => <Badge key={t} variant="outline" className="text-xs border-zinc-700/50 py-0">{t}</Badge>)}
                    </div>
                    <span className="text-xs text-zinc-600">{tpl.usage_count || 0} uses</span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
