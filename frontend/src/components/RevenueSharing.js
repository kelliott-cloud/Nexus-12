import { useState, useEffect, useCallback } from "react";
import { api } from "@/App";
import { handleSilent } from "@/lib/errorHandler";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { DollarSign, TrendingUp, ShoppingCart, Users, ArrowUpRight } from "lucide-react";

export default function RevenueSharing() {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/marketplace/revenue/dashboard");
      setDashboard(res.data);
    } catch (err) { handleSilent(err, "Revenue:fetch"); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center text-zinc-500 text-sm" data-testid="revenue-loading">
        Loading revenue data...
      </div>
    );
  }

  const creator = dashboard?.creator || {};
  const buyer = dashboard?.buyer || {};
  const hasEarnings = creator.total_sales > 0;
  const hasPurchases = buyer.total_purchases > 0;

  return (
    <ScrollArea className="flex-1">
      <div className="p-6 space-y-6 max-w-5xl mx-auto" data-testid="revenue-sharing">
        <div>
          <h2 className="text-lg font-semibold text-zinc-100">Marketplace Revenue</h2>
          <p className="text-xs text-zinc-500 mt-0.5">Earnings from your published agents and purchase history</p>
        </div>

        {/* Creator Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Card className="bg-zinc-900/60 border-zinc-800/60">
            <CardContent className="p-4">
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-lg bg-emerald-400/10">
                  <DollarSign className="w-4 h-4 text-emerald-400" />
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-zinc-500">Earnings</p>
                  <p className="text-xl font-bold text-emerald-400 mt-0.5" data-testid="revenue-total-earnings">
                    ${creator.total_earnings_usd || 0}
                  </p>
                  <p className="text-[10px] text-zinc-500 mt-0.5">{100 - (creator.platform_fee_pct || 20)}% of revenue</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="bg-zinc-900/60 border-zinc-800/60">
            <CardContent className="p-4">
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-lg bg-cyan-400/10">
                  <TrendingUp className="w-4 h-4 text-cyan-400" />
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-zinc-500">Total Sales</p>
                  <p className="text-xl font-bold text-zinc-100 mt-0.5" data-testid="revenue-total-sales">
                    {creator.total_sales || 0}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="bg-zinc-900/60 border-zinc-800/60">
            <CardContent className="p-4">
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-lg bg-amber-400/10">
                  <Users className="w-4 h-4 text-amber-400" />
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-zinc-500">Platform Fee</p>
                  <p className="text-xl font-bold text-zinc-100 mt-0.5">{creator.platform_fee_pct || 20}%</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="bg-zinc-900/60 border-zinc-800/60">
            <CardContent className="p-4">
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-lg bg-violet-400/10">
                  <ShoppingCart className="w-4 h-4 text-violet-400" />
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-zinc-500">Purchases</p>
                  <p className="text-xl font-bold text-zinc-100 mt-0.5" data-testid="revenue-total-purchases">
                    {buyer.total_purchases || 0}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Per-Agent Revenue */}
        {(creator.per_agent || []).length > 0 && (
          <Card className="bg-zinc-900/60 border-zinc-800/60" data-testid="revenue-per-agent">
            <CardHeader className="p-3 pb-1">
              <CardTitle className="text-xs text-zinc-500">Revenue by Agent</CardTitle>
            </CardHeader>
            <CardContent className="p-3 pt-0">
              <div className="space-y-2">
                {creator.per_agent.map(a => (
                  <div key={a.agent_id} className="flex items-center gap-3 py-1.5 border-b border-zinc-800/30 last:border-0">
                    <span className="text-xs text-zinc-300 font-medium w-32 truncate">{a.agent_name}</span>
                    <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-emerald-400 rounded-full"
                        style={{ width: `${Math.min((a.creator_earnings_usd / Math.max(creator.total_earnings_usd, 1)) * 100, 100)}%` }}
                      />
                    </div>
                    <span className="text-xs font-mono text-emerald-400 w-20 text-right">${a.creator_earnings_usd}</span>
                    <Badge variant="secondary" className="text-[9px] bg-zinc-800 text-zinc-400">{a.sales_count} sales</Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Recent Transactions */}
        {(creator.recent_transactions || []).length > 0 && (
          <Card className="bg-zinc-900/60 border-zinc-800/60" data-testid="revenue-transactions">
            <CardHeader className="p-3 pb-1">
              <CardTitle className="text-xs text-zinc-500">Recent Sales</CardTitle>
            </CardHeader>
            <CardContent className="p-3 pt-0">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-zinc-600 border-b border-zinc-800/60">
                    <th className="text-left py-1.5 font-medium">Agent</th>
                    <th className="text-right py-1.5 font-medium">Amount</th>
                    <th className="text-right py-1.5 font-medium">Fee</th>
                    <th className="text-right py-1.5 font-medium">Earned</th>
                    <th className="text-right py-1.5 font-medium">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {creator.recent_transactions.map(t => (
                    <tr key={t.transaction_id} className="border-b border-zinc-800/30 text-zinc-300">
                      <td className="py-1.5 font-medium">{t.agent_name}</td>
                      <td className="text-right font-mono">${t.amount_usd}</td>
                      <td className="text-right font-mono text-zinc-500">-${t.platform_fee_usd}</td>
                      <td className="text-right font-mono text-emerald-400">${t.creator_earnings_usd}</td>
                      <td className="text-right text-zinc-500">{t.completed_at?.slice(0, 10)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        )}

        {/* Empty states */}
        {!hasEarnings && !hasPurchases && (
          <Card className="bg-zinc-900/60 border-zinc-800/60">
            <CardContent className="p-8 text-center">
              <DollarSign className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
              <p className="text-sm text-zinc-400">No revenue activity yet</p>
              <p className="text-xs text-zinc-600 mt-1">Publish agents to the marketplace with pricing to start earning. Purchase agents from other creators to see them here.</p>
            </CardContent>
          </Card>
        )}

        {/* Purchases History */}
        {hasPurchases && (
          <Card className="bg-zinc-900/60 border-zinc-800/60" data-testid="revenue-purchases">
            <CardHeader className="p-3 pb-1">
              <CardTitle className="text-xs text-zinc-500">Your Purchases</CardTitle>
            </CardHeader>
            <CardContent className="p-3 pt-0">
              <div className="space-y-1.5">
                {buyer.purchases.map((p, i) => (
                  <div key={i} className="flex items-center justify-between py-1 border-b border-zinc-800/30 last:border-0 text-xs">
                    <span className="text-zinc-300">{p.agent_id}</span>
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-zinc-400">${p.amount_usd}</span>
                      <span className="text-zinc-600">{p.purchased_at?.slice(0, 10)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </ScrollArea>
  );
}
