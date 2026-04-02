import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { handleSilent } from "@/lib/errorHandler";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import {
  Star, TrendingUp, BarChart3, ThumbsUp, ThumbsDown, Minus, Loader2
} from "lucide-react";
import { FeatureHelp, FEATURE_HELP } from "@/components/FeatureHelp";

export default function ReviewAnalyticsPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchAnalytics = useCallback(async () => {
    try {
      const res = await api.get("/marketplace/review-analytics");
      setData(res.data);
    } catch (err) { handleSilent(err, "RA:fetch"); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchAnalytics(); }, [fetchAnalytics]);

  if (loading) return <div className="flex-1 flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-zinc-500" /></div>;
  if (!data) return <div className="flex-1 flex items-center justify-center text-zinc-500">No review data available</div>;

  const { stats, trend, top_reviewed, sentiment } = data;

  return (
    <div className="flex-1 overflow-y-auto p-6" data-testid="review-analytics-panel">
      <div className="max-w-5xl mx-auto space-y-6">
        <FeatureHelp featureId="review-analytics" {...FEATURE_HELP["review-analytics"]} />
        <div>
          <h2 className="text-lg font-semibold text-zinc-100">Review Analytics</h2>
          <p className="text-sm text-zinc-500 mt-1">Marketplace review trends, sentiment, and top-rated templates</p>
        </div>

        {/* Overview Cards */}
        <div className="grid grid-cols-4 gap-4">
          {[
            { label: "Total Reviews", value: stats.total, icon: Star },
            { label: "Avg Rating", value: stats.avg_rating?.toFixed(1) || "0.0", icon: TrendingUp },
            { label: "Positive", value: `${sentiment.positive_pct}%`, icon: ThumbsUp, color: "text-emerald-400" },
            { label: "Negative", value: `${sentiment.negative_pct}%`, icon: ThumbsDown, color: "text-red-400" },
          ].map(({ label, value, icon: Icon, color }) => (
            <Card key={label} className="bg-zinc-900 border-zinc-800">
              <CardContent className="py-4 text-center">
                <Icon className={`w-5 h-5 mx-auto mb-2 ${color || "text-zinc-400"}`} />
                <div className={`text-2xl font-bold ${color || "text-zinc-100"}`}>{value}</div>
                <div className="text-xs text-zinc-500 mt-1">{label}</div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Rating Distribution */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader><CardTitle className="text-sm text-zinc-100">Rating Distribution</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {[5, 4, 3, 2, 1].map(star => {
              const count = stats[["", "one", "two", "three", "four", "five"][star]] || 0;
              const pct = stats.total > 0 ? (count / stats.total) * 100 : 0;
              return (
                <div key={star} className="flex items-center gap-3">
                  <div className="flex items-center gap-1 w-12">
                    <span className="text-sm text-zinc-300">{star}</span>
                    <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                  </div>
                  <div className="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden">
                    <div className="h-full bg-amber-400 rounded-full transition-all" style={{ width: `${pct}%` }} />
                  </div>
                  <span className="text-xs text-zinc-500 w-12 text-right">{count} ({pct.toFixed(0)}%)</span>
                </div>
              );
            })}
          </CardContent>
        </Card>

        {/* Sentiment Gauge */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader><CardTitle className="text-sm text-zinc-100">Sentiment Overview</CardTitle></CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 h-6 rounded-full overflow-hidden">
              <div className="h-full bg-emerald-500 rounded-l-full transition-all" style={{ width: `${sentiment.positive_pct}%` }} />
              <div className="h-full bg-zinc-600 transition-all" style={{ width: `${sentiment.neutral_pct}%` }} />
              <div className="h-full bg-red-500 rounded-r-full transition-all" style={{ width: `${sentiment.negative_pct}%` }} />
            </div>
            <div className="flex justify-between mt-2 text-xs">
              <span className="text-emerald-400">Positive {sentiment.positive_pct}%</span>
              <span className="text-zinc-500">Neutral {sentiment.neutral_pct}%</span>
              <span className="text-red-400">Negative {sentiment.negative_pct}%</span>
            </div>
          </CardContent>
        </Card>

        {/* Rating Trend */}
        {trend.length > 0 && (
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader><CardTitle className="text-sm text-zinc-100">30-Day Rating Trend</CardTitle></CardHeader>
            <CardContent>
              <div className="flex items-end gap-1 h-24">
                {trend.map((t, i) => (
                  <div key={i} className="flex-1 flex flex-col items-center gap-0.5">
                    <span className="text-xs text-zinc-400">{t.avg_rating}</span>
                    <div className="w-full bg-zinc-800 rounded-sm" style={{ height: `${(t.avg_rating / 5) * 100}%` }}>
                      <div className={`w-full h-full rounded-sm ${t.avg_rating >= 4 ? "bg-emerald-500" : t.avg_rating >= 3 ? "bg-amber-500" : "bg-red-500"}`} />
                    </div>
                    <span className="text-xs text-zinc-600 -rotate-45 origin-top-left">{t.date.slice(5)}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Top Reviewed */}
        {top_reviewed.length > 0 && (
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader><CardTitle className="text-sm text-zinc-100">Most Reviewed Templates</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {top_reviewed.map((t, i) => (
                <div key={t.template_id} className="flex items-center justify-between py-2 border-b border-zinc-800/50 last:border-0">
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-zinc-600 w-6">#{i+1}</span>
                    <span className="text-sm text-zinc-300 font-mono">{t.template_id}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-1">
                      <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                      <span className="text-sm text-zinc-200">{t.avg_rating}</span>
                    </div>
                    <Badge variant="outline" className="text-xs border-zinc-700">{t.review_count} reviews</Badge>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
