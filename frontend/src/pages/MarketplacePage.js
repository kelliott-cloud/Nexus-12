import React, { useState, useEffect, useCallback } from "react";
import { Star, Download, Search, Plus, ArrowLeft, Filter, TrendingUp, X, Send } from "lucide-react";
import { api } from "@/lib/api";
import { handleSilent } from "@/lib/errorHandler";
import { toast } from "sonner";

const CATEGORIES = [
  { key: "all", label: "All", icon: "grid" },
  { key: "coding", label: "Coding", icon: "code" },
  { key: "research", label: "Research", icon: "search" },
  { key: "creative", label: "Creative", icon: "palette" },
  { key: "business", label: "Business", icon: "briefcase" },
  { key: "productivity", label: "Productivity", icon: "zap" },
  { key: "data", label: "Data", icon: "database" },
  { key: "custom", label: "Custom", icon: "settings" },
];

const BASE_MODELS = [
  "claude", "chatgpt", "gemini", "deepseek", "grok", "mistral", "groq",
  "perplexity", "cohere", "mercury", "pi", "manus",
  "qwen", "kimi", "llama", "glm", "cursor", "notebooklm", "copilot",
];

const SORT_OPTIONS = [
  { key: "popular", label: "Most Popular" },
  { key: "top_rated", label: "Top Rated" },
  { key: "newest", label: "Newest" },
  { key: "name", label: "A-Z" },
];

function StarRating({ rating, size = 14 }) {
  return (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((i) => (
        <Star key={i} size={size} className={i <= Math.round(rating) ? "text-amber-400 fill-amber-400" : "text-zinc-700"} />
      ))}
    </div>
  );
}

function AgentCard({ agent, onView, onInstall }) {
  return (
    <div
      data-testid={`marketplace-agent-${agent.agent_id}`}
      className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5 hover:border-zinc-600 transition-all cursor-pointer group"
      onClick={() => onView(agent)}
    >
      <div className="flex items-start gap-3 mb-3">
        <div
          className="w-10 h-10 rounded-lg flex items-center justify-center text-sm font-bold shrink-0"
          style={{ backgroundColor: agent.color || "#6366f1", color: "#fff" }}
        >
          {agent.icon || agent.name?.[0]}
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-zinc-100 truncate group-hover:text-cyan-400 transition-colors">{agent.name}</h3>
          <p className="text-xs text-zinc-500 truncate">{agent.creator_name}</p>
        </div>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-400 border border-zinc-700 shrink-0">{agent.category}</span>
      </div>
      <p className="text-xs text-zinc-400 line-clamp-2 mb-3 min-h-[2rem]">{agent.description || "No description"}</p>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <StarRating rating={agent.avg_rating || 0} size={11} />
          <span className="text-[10px] text-zinc-500">({agent.rating_count || 0})</span>
        </div>
        <div className="flex items-center gap-1 text-[10px] text-zinc-500">
          <Download size={10} />
          {agent.installs || 0}
        </div>
      </div>
      {agent.tags?.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-3">
          {agent.tags.slice(0, 3).map((t) => (
            <span key={t} className="text-[9px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-500">{t}</span>
          ))}
        </div>
      )}
    </div>
  );
}

function AgentDetail({ agent, onBack, onInstall, onRate, workspaceId }) {
  const [rating, setRating] = useState(0);
  const [review, setReview] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleRate = async () => {
    if (!rating) return;
    setSubmitting(true);
    try {
      await onRate(agent.agent_id, rating, review);
      setReview("");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div data-testid="marketplace-agent-detail">
      <button onClick={onBack} className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 mb-5 transition-colors" data-testid="marketplace-back-btn">
        <ArrowLeft size={14} /> Back to marketplace
      </button>
      <div className="flex items-start gap-4 mb-6">
        <div className="w-14 h-14 rounded-xl flex items-center justify-center text-lg font-bold shrink-0" style={{ backgroundColor: agent.color || "#6366f1", color: "#fff" }}>
          {agent.icon || agent.name?.[0]}
        </div>
        <div className="flex-1 min-w-0">
          <h2 className="text-xl font-bold text-zinc-100">{agent.name}</h2>
          <p className="text-sm text-zinc-400 mt-1">by {agent.creator_name} &middot; {agent.base_model}</p>
          <div className="flex items-center gap-3 mt-2">
            <div className="flex items-center gap-1.5">
              <StarRating rating={agent.avg_rating || 0} />
              <span className="text-xs text-zinc-500">{agent.avg_rating || 0} ({agent.rating_count || 0} reviews)</span>
            </div>
            <span className="text-xs text-zinc-600">&middot;</span>
            <span className="text-xs text-zinc-500 flex items-center gap-1"><Download size={12} />{agent.installs || 0} {(agent.installs || 0) === 1 ? 'install' : 'installs'}</span>
          </div>
        </div>
        <button
          onClick={() => onInstall(agent.agent_id)}
          disabled={!workspaceId}
          className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white text-sm font-medium rounded-lg transition-colors"
          data-testid="marketplace-install-btn"
        >
          Install
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-zinc-300 mb-2">Description</h3>
            <p className="text-sm text-zinc-400 whitespace-pre-wrap">{agent.description || "No description provided."}</p>
          </div>
          <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-zinc-300 mb-2">System Prompt</h3>
            <p className="text-xs text-zinc-600 italic bg-zinc-950 rounded-lg p-3 border border-zinc-800">System prompt hidden to protect agent creator IP. Install to use.</p>
          </div>

          {/* Reviews */}
          <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-zinc-300 mb-3">Reviews</h3>
            {(agent.ratings || []).length === 0 ? (
              <p className="text-xs text-zinc-600">No reviews yet. Be the first!</p>
            ) : (
              <div className="space-y-3 max-h-60 overflow-y-auto">
                {(agent.ratings || []).map((r, i) => (
                  <div key={r.user_id || `review-${i}`} className="border-b border-zinc-800 pb-3 last:border-0">
                    <div className="flex items-center gap-2">
                      <StarRating rating={r.rating} size={10} />
                      <span className="text-[10px] text-zinc-500">{r.user_name}</span>
                    </div>
                    {r.review && <p className="text-xs text-zinc-400 mt-1">{r.review}</p>}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="space-y-4">
          <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-zinc-300 mb-3">Info</h3>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between"><span className="text-zinc-500">Category</span><span className="text-zinc-300 capitalize">{agent.category}</span></div>
              <div className="flex justify-between"><span className="text-zinc-500">Base Model</span><span className="text-zinc-300">{agent.base_model}</span></div>
              <div className="flex justify-between"><span className="text-zinc-500">Created</span><span className="text-zinc-300">{agent.created_at?.slice(0, 10)}</span></div>
            </div>
            {agent.tags?.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-3 pt-3 border-t border-zinc-800">
                {agent.tags.map((t) => (
                  <span key={t} className="text-[10px] px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-400">{t}</span>
                ))}
              </div>
            )}
          </div>

          <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-zinc-300 mb-3">Rate this Agent</h3>
            <div className="flex items-center gap-1 mb-3">
              {[1, 2, 3, 4, 5].map((i) => (
                <button key={i} onClick={() => setRating(i)} className="p-0.5" data-testid={`rate-star-${i}`}>
                  <Star size={20} className={i <= rating ? "text-amber-400 fill-amber-400" : "text-zinc-700 hover:text-zinc-500"} />
                </button>
              ))}
            </div>
            <textarea
              value={review}
              onChange={(e) => setReview(e.target.value)}
              placeholder="Write a review (optional)..."
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2 text-xs text-zinc-300 placeholder-zinc-600 resize-none h-16 focus:outline-none focus:border-zinc-600"
              data-testid="marketplace-review-input"
            />
            <button
              onClick={handleRate}
              disabled={!rating || submitting}
              className="mt-2 w-full py-1.5 bg-amber-600/20 hover:bg-amber-600/30 disabled:opacity-40 text-amber-400 text-xs font-medium rounded-lg border border-amber-600/30 transition-colors flex items-center justify-center gap-1"
              data-testid="marketplace-submit-review-btn"
            >
              <Send size={12} /> Submit Review
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function PublishModal({ onClose, onPublish }) {
  const [form, setForm] = useState({ name: "", description: "", category: "custom", base_model: "claude", system_prompt: "", tags: "", color: "#6366f1" });
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!form.name || !form.system_prompt) return;
    setLoading(true);
    try {
      await onPublish({ ...form, tags: form.tags.split(",").map((t) => t.trim()).filter(Boolean) });
      onClose();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-zinc-900 border border-zinc-700 rounded-xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()} data-testid="publish-agent-modal">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-bold text-zinc-100">Publish Agent</h2>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300"><X size={18} /></button>
        </div>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-zinc-400 block mb-1">Name *</label>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-zinc-600" placeholder="My Custom Agent" data-testid="publish-name-input" />
          </div>
          <div>
            <label className="text-xs text-zinc-400 block mb-1">Description</label>
            <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 resize-none h-20 focus:outline-none focus:border-zinc-600" placeholder="What does this agent do?" data-testid="publish-description-input" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-zinc-400 block mb-1">Category</label>
              <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none" data-testid="publish-category-select">
                {CATEGORIES.filter((c) => c.key !== "all").map((c) => (
                  <option key={c.key} value={c.key}>{c.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-zinc-400 block mb-1">Base Model</label>
              <select value={form.base_model} onChange={(e) => setForm({ ...form, base_model: e.target.value })} className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none" data-testid="publish-model-select">
                {BASE_MODELS.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="text-xs text-zinc-400 block mb-1">System Prompt *</label>
            <textarea value={form.system_prompt} onChange={(e) => setForm({ ...form, system_prompt: e.target.value })} className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 resize-none h-32 font-mono focus:outline-none focus:border-zinc-600" placeholder="You are a specialized AI agent that..." data-testid="publish-prompt-input" />
          </div>
          <div>
            <label className="text-xs text-zinc-400 block mb-1">Tags (comma-separated)</label>
            <input value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-zinc-600" placeholder="python, code-review, debugging" data-testid="publish-tags-input" />
          </div>
          <div>
            <label className="text-xs text-zinc-400 block mb-1">Color</label>
            <input type="color" value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })} className="w-8 h-8 rounded cursor-pointer border-0 bg-transparent" />
          </div>
          <button
            onClick={handleSubmit}
            disabled={!form.name || !form.system_prompt || loading}
            className="w-full py-2.5 bg-cyan-600 hover:bg-cyan-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white text-sm font-medium rounded-lg transition-colors mt-2"
            data-testid="publish-submit-btn"
          >
            {loading ? "Publishing..." : "Publish to Marketplace"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function MarketplacePage({ user, workspaceId }) {
  const [agents, setAgents] = useState([]);
  const [stats, setStats] = useState(null);
  const [category, setCategory] = useState("all");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("popular");
  const [loading, setLoading] = useState(true);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [showPublish, setShowPublish] = useState(false);

  const fetchAgents = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ sort, limit: "24" });
      if (category !== "all") params.set("category", category);
      if (search) params.set("search", search);
      const res = await api.get(`/marketplace/agents?${params}`);
      setAgents(res.data?.agents || []);
    } catch (err) {
      handleSilent(err, "Marketplace:fetchAgents");
    } finally {
      setLoading(false);
    }
  }, [category, search, sort]);

  const fetchStats = useCallback(async () => {
    try {
      const res = await api.get("/marketplace/agent-stats");
      setStats(res.data);
    } catch (err) { handleSilent(err, "Marketplace:fetchStats"); }
  }, []);

  useEffect(() => { fetchAgents(); }, [fetchAgents]);
  useEffect(() => { fetchStats(); }, [fetchStats]);

  const handleViewDetail = async (agent) => {
    try {
      const res = await api.get(`/marketplace/agents/${agent.agent_id}`);
      setSelectedAgent(res.data);
    } catch (err) { handleSilent(err, "Marketplace:viewDetail"); }
  };

  const handleInstall = async (agentId) => {
    if (!workspaceId) return;
    try {
      await api.post(`/marketplace/agents/${agentId}/install?workspace_id=${workspaceId}`);
      toast.success("Agent installed");
      fetchAgents();
      fetchStats();
    } catch (err) { handleSilent(err, "Marketplace:install"); }
  };

  const handleRate = async (agentId, rating, review) => {
    try {
      const res = await api.post(`/marketplace/agents/${agentId}/rate`, { rating, review });
      setSelectedAgent((prev) => prev ? { ...prev, avg_rating: res.data.avg_rating, rating_count: res.data.rating_count } : prev);
      fetchAgents();
    } catch (err) { handleSilent(err, "Marketplace:rate"); }
  };

  const handlePublish = async (data) => {
    try {
      await api.post("/marketplace/agents", data);
      toast.success("Agent published");
      fetchAgents();
      fetchStats();
    } catch (err) { handleSilent(err, "Marketplace:publish"); }
  };

  if (selectedAgent) {
    return (
      <div className="h-full overflow-y-auto p-6" data-testid="marketplace-page">
        <AgentDetail agent={selectedAgent} onBack={() => setSelectedAgent(null)} onInstall={handleInstall} onRate={handleRate} workspaceId={workspaceId} />
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto" data-testid="marketplace-page">
      <div className="max-w-6xl mx-auto p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-zinc-100">Agent Marketplace</h1>
            <p className="text-xs text-zinc-500 mt-1">Discover, rate, and install custom AI agent configurations</p>
          </div>
          <button
            onClick={() => setShowPublish(true)}
            className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-1.5"
            data-testid="publish-agent-btn"
          >
            <Plus size={14} /> Publish Agent
          </button>
        </div>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-3 gap-3 mb-6">
            <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-4 text-center">
              <div className="text-2xl font-bold text-cyan-400">{stats.total_agents}</div>
              <div className="text-[10px] text-zinc-500 mt-0.5">Published Agents</div>
            </div>
            <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-4 text-center">
              <div className="text-2xl font-bold text-emerald-400">{stats.total_installs}</div>
              <div className="text-[10px] text-zinc-500 mt-0.5">Total Installs</div>
            </div>
            <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-4 text-center">
              <div className="text-2xl font-bold text-amber-400">{Object.keys(stats.categories || {}).filter((k) => stats.categories[k] > 0).length}</div>
              <div className="text-[10px] text-zinc-500 mt-0.5">Active Categories</div>
            </div>
          </div>
        )}

        {/* Search + Filters */}
        <div className="flex items-center gap-3 mb-4">
          <div className="flex-1 relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-600" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search agents..."
              className="w-full bg-zinc-900 border border-zinc-800 rounded-lg pl-9 pr-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-600"
              data-testid="marketplace-search-input"
            />
          </div>
          <div className="flex items-center gap-1">
            <Filter size={12} className="text-zinc-600" />
            <select value={sort} onChange={(e) => setSort(e.target.value)} className="bg-zinc-900 border border-zinc-800 rounded-lg px-2 py-2 text-xs text-zinc-300 focus:outline-none" data-testid="marketplace-sort-select">
              {SORT_OPTIONS.map((s) => (
                <option key={s.key} value={s.key}>{s.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Categories */}
        <div className="flex gap-2 mb-6 overflow-x-auto pb-1">
          {CATEGORIES.map((c) => (
            <button
              key={c.key}
              onClick={() => setCategory(c.key)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${category === c.key ? "bg-cyan-600/20 text-cyan-400 border border-cyan-600/30" : "bg-zinc-900 text-zinc-500 border border-zinc-800 hover:text-zinc-300"}`}
              data-testid={`marketplace-cat-${c.key}`}
            >
              {c.label}
            </button>
          ))}
        </div>

        {/* Agent Grid */}
        {loading ? (
          <div className="text-center py-20 text-zinc-600 text-sm">Loading agents...</div>
        ) : agents.length === 0 ? (
          <div className="text-center py-20">
            <TrendingUp size={32} className="mx-auto text-zinc-700 mb-3" />
            <p className="text-sm text-zinc-500">No agents found</p>
            <p className="text-xs text-zinc-600 mt-1">Be the first to publish an agent!</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="marketplace-agent-grid">
            {agents.map((a) => (
              <AgentCard key={a.agent_id} agent={a} onView={handleViewDetail} onInstall={handleInstall} />
            ))}
          </div>
        )}
      </div>

      {showPublish && <PublishModal onClose={() => setShowPublish(false)} onPublish={handlePublish} />}
    </div>
  );
}
