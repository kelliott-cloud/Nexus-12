import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Building2, BarChart3, MessageSquare, Cpu, Loader2, Hash, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/App";
import { toast } from "sonner";

const MODEL_COLORS = {
  claude: "#D97706", chatgpt: "#10B981", deepseek: "#6366F1",
  grok: "#EF4444", gemini: "#3B82F6", perplexity: "#8B5CF6",
  mistral: "#EC4899", cohere: "#14B8A6", groq: "#F59E0B"
};

export default function OrgAnalytics() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const orgRes = await api.get(`/orgs/by-slug/${slug}`);
        const res = await api.get(`/orgs/${orgRes.data.org_id}/admin/analytics`);
        setAnalytics(res.data);
      } catch (err) {
        toast.error("Failed to load analytics");
        navigate(`/org/${slug}/dashboard`);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [slug, navigate]);

  if (loading) return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
      <Loader2 className="w-8 h-8 animate-spin text-zinc-500" />
    </div>
  );

  const totalModelMsgs = Object.values(analytics?.model_usage || {}).reduce((a, b) => a + b, 0);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100" data-testid="org-analytics-page">
      <header className="border-b border-zinc-800 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate(`/org/${slug}/dashboard`)}
            className="text-zinc-400 hover:text-zinc-100" data-testid="analytics-back-btn">
            <ArrowLeft className="w-4 h-4 mr-2" /> Back
          </Button>
          <BarChart3 className="w-5 h-5 text-blue-400" />
          <h1 className="text-lg font-semibold" style={{ fontFamily: 'Syne, sans-serif' }}>Organization Analytics</h1>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {[
            { label: "Total Messages", value: analytics?.total_messages || 0, icon: MessageSquare, color: "text-blue-400" },
            { label: "AI Messages", value: analytics?.ai_messages || 0, icon: Cpu, color: "text-emerald-400" },
            { label: "Workspaces", value: analytics?.workspaces || 0, icon: Hash, color: "text-amber-400" },
            { label: "Channels", value: analytics?.channels || 0, icon: Users, color: "text-purple-400" },
          ].map(s => (
            <div key={s.label} className="p-5 rounded-xl bg-zinc-900/50 border border-zinc-800">
              <div className="flex items-center gap-2 mb-2">
                <s.icon className={`w-4 h-4 ${s.color}`} />
                <p className="text-xs text-zinc-500 uppercase tracking-wider">{s.label}</p>
              </div>
              <p className={`text-3xl font-bold ${s.color}`}>{s.value}</p>
            </div>
          ))}
        </div>

        <div className="p-6 rounded-xl bg-zinc-900/50 border border-zinc-800">
          <h3 className="text-base font-semibold mb-4">AI Model Usage</h3>
          {Object.keys(analytics?.model_usage || {}).length === 0 ? (
            <p className="text-sm text-zinc-500">No AI usage data yet. Start collaborating with AI agents to see analytics.</p>
          ) : (
            <div className="space-y-3">
              {Object.entries(analytics.model_usage)
                .sort((a, b) => b[1] - a[1])
                .map(([model, count]) => {
                  const pct = totalModelMsgs > 0 ? (count / totalModelMsgs) * 100 : 0;
                  return (
                    <div key={model} className="flex items-center gap-4" data-testid={`model-usage-${model}`}>
                      <span className="text-sm text-zinc-300 w-24 capitalize">{model}</span>
                      <div className="flex-1 h-6 bg-zinc-800 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{
                            width: `${Math.max(pct, 2)}%`,
                            backgroundColor: MODEL_COLORS[model] || "#71717a"
                          }}
                        />
                      </div>
                      <span className="text-xs text-zinc-400 w-16 text-right">{count} msgs</span>
                      <span className="text-xs text-zinc-500 w-12 text-right">{pct.toFixed(0)}%</span>
                    </div>
                  );
                })}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
