import { useState, useEffect } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Zap, Check, ArrowLeft, CreditCard, Loader2, Crown, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/App";
import GlobalHeader from "@/components/GlobalHeader";

const PLAN_ICONS = { free: Zap, starter: Zap, pro: Crown, team: Crown, enterprise: Sparkles };

export default function BillingPage({ user }) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [plans, setPlans] = useState({});
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState("");
  const [polling, setPolling] = useState(false);
  const [isAnnual, setIsAnnual] = useState(false);

  useEffect(() => {
    fetchData();
    const sessionId = searchParams.get("session_id");
    if (sessionId) {
      setPolling(true);
      pollPaymentStatus(sessionId, 0);
    }
  }, []);

  const fetchData = async () => {
    try {
      const [plansRes, subRes, v2Res] = await Promise.all([
        api.get("/billing/plans"),
        api.get("/billing/subscription"),
        api.get("/billing/plans-v2").catch(() => null),
      ]);
      // Use v2 plans if available, fall back to v1
      if (v2Res && v2Res.data && v2Res.data.plans) {
        const v2Plans = {};
        v2Res.data.plans.forEach(p => {
          v2Plans[p.plan] = {
            name: p.plan.charAt(0).toUpperCase() + p.plan.slice(1),
            price: p.price,
            price_label: p.price_label,
            features: p.features,
            credits: p.credits,
          };
        });
        setPlans(v2Plans);
      } else {
        const rawPlans = plansRes.data?.plans || plansRes.data || {};
        setPlans(rawPlans);
      }
      setSubscription(subRes.data);
    } catch (err) {
      toast.error("Failed to load billing info");
    } finally {
      setLoading(false);
    }
  };

  const pollPaymentStatus = async (sessionId, attempts) => {
    if (attempts >= 8) {
      setPolling(false);
      toast.error("Payment status check timed out");
      return;
    }
    try {
      const res = await api.get(`/billing/checkout/status/${sessionId}`);
      if (res.data.payment_status === "paid") {
        setPolling(false);
        toast.success("Payment successful! Plan upgraded.");
        fetchData();
        window.history.replaceState({}, "", "/billing");
        return;
      }
    } catch (err) { handleSilent(err, "BillingPage:op1"); }
    setTimeout(() => pollPaymentStatus(sessionId, attempts + 1), 2500);
  };

  const handleUpgrade = async (planId) => {
    setUpgrading(planId);
    try {
      const res = await api.post("/billing/checkout", {
        plan_id: planId,
        origin_url: window.location.origin,
      });
      if (res.data.url) {
        window.location.href = res.data.url;
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to start checkout");
    } finally {
      setUpgrading("");
    }
  };

  const currentPlan = subscription?.plan || "free";
  const usage = subscription?.usage || {};
  const planInfo = subscription?.plan_info || {};
  const maxCollabs = planInfo.ai_collaboration_per_month || planInfo.ai_collaboration_limit || 5;
  const usedCollabs = usage.ai_collaboration || 0;

  return (
    <div className="min-h-screen bg-zinc-950" data-testid="billing-page">
      <GlobalHeader user={user} title="Billing" />
      {/* Header */}
      <header className="sticky top-0 z-40 glass-panel px-6 py-3">
        <div className="max-w-5xl mx-auto flex items-center">
          <div className="flex items-center gap-2 text-sm">
            <button onClick={() => navigate("/dashboard")} className="text-zinc-500 hover:text-zinc-300 transition-colors" data-testid="back-dashboard">Dashboard</button>
            <span className="text-zinc-700">/</span>
            <span className="text-zinc-300 font-medium">Billing</span>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-6 sm:py-12">
        <h1 className="text-3xl font-bold tracking-tight text-zinc-100 mb-2" style={{ fontFamily: 'Syne, sans-serif' }}>Billing & Plans</h1>
        <p className="text-zinc-500 text-sm mb-6">Choose the plan that fits your collaboration needs.</p>

        {/* Annual/Monthly Toggle */}
        <div className="flex items-center justify-center gap-3 mb-8" data-testid="billing-toggle">
          <span className={`text-sm ${!isAnnual ? 'text-zinc-100 font-medium' : 'text-zinc-500'}`}>Monthly</span>
          <button
            onClick={() => setIsAnnual(!isAnnual)}
            className={`relative w-12 h-6 rounded-full transition-colors ${isAnnual ? 'bg-cyan-500' : 'bg-zinc-700'}`}
            data-testid="annual-toggle"
          >
            <div className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-transform ${isAnnual ? 'translate-x-6' : 'translate-x-0.5'}`} />
          </button>
          <span className={`text-sm ${isAnnual ? 'text-zinc-100 font-medium' : 'text-zinc-500'}`}>Annual</span>
          {isAnnual && <span className="text-xs text-emerald-400 font-medium bg-emerald-400/10 px-2 py-0.5 rounded-full">Save 20%</span>}
        </div>

        {polling && (
          <div className="flex items-center gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 mb-8" data-testid="payment-processing">
            <Loader2 className="w-5 h-5 animate-spin text-amber-500" />
            <span className="text-sm text-amber-400">Processing your payment...</span>
          </div>
        )}

        {/* Usage */}
        {!loading && (
          <div className="p-6 rounded-xl bg-zinc-900/40 border border-zinc-800/60 mb-8" data-testid="usage-section">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm text-zinc-400">AI Collaborations This Month</span>
              <Badge variant="secondary" className="bg-zinc-800 text-zinc-300">
                {currentPlan.toUpperCase()} PLAN
              </Badge>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-zinc-400 to-zinc-200 transition-all duration-500"
                  style={{ width: maxCollabs < 0 ? '10%' : `${Math.min((usedCollabs / maxCollabs) * 100, 100)}%` }}
                />
              </div>
              <span className="text-sm font-mono text-zinc-300">
                {usedCollabs} / {maxCollabs < 0 ? "Unlimited" : maxCollabs}
              </span>
            </div>
          </div>
        )}

        {/* Plans */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
            {[1, 2, 3, 4, 5].map(i => <div key={i} className="h-80 rounded-xl bg-zinc-900/50 animate-pulse" />)}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-5" data-testid="plans-grid">
            {Object.entries(plans).map(([key, plan]) => {
              const Icon = PLAN_ICONS[key] || Zap;
              const isCurrent = currentPlan === key;
              const isPopular = key === "pro" || plan.popular;
              const featureList = Array.isArray(plan.features) ? plan.features : Object.entries(plan.features || {}).map(([k, v]) => {
                if (typeof v === "boolean") return v ? k.replace(/_/g, " ") : null;
                if (v === -1) return `Unlimited ${k.replace(/_/g, " ")}`;
                return `${v} ${k.replace(/_/g, " ")}`;
              }).filter(Boolean);
              const priceLabel = key === "enterprise" ? "Custom" : isAnnual
                ? (plan.price > 0 ? `$${Math.round(plan.price * 0.8)}/mo` : "$0/mo")
                : (plan.price_label || (plan.price > 0 ? `$${(plan.price || 0).toFixed(0)}/mo` : "$0/mo"));
              return (
                <div key={key} className={`p-5 rounded-xl border transition-colors relative ${isPopular ? 'bg-zinc-900 border-cyan-500/50 ring-1 ring-cyan-500/20' : isCurrent ? 'bg-zinc-900 border-emerald-500/40' : 'bg-zinc-900/40 border-zinc-800/60 hover:border-zinc-700'}`} data-testid={`plan-card-${key}`}>
                  {isPopular && <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 bg-cyan-500 text-zinc-950 text-[10px] font-bold rounded-full uppercase tracking-wider">Most Popular</div>}
                  <div className="flex items-center gap-2 mb-3">
                    <Icon className="w-4 h-4 text-zinc-300" />
                    <span className="font-semibold text-zinc-200 text-sm">{plan.name}</span>
                    {isCurrent && <Badge className="bg-emerald-500/15 text-emerald-400 text-[9px]">CURRENT</Badge>}
                  </div>
                  <div className="mb-4">
                    <span className={`font-bold text-zinc-100 ${priceLabel === "Custom" ? "text-xl" : "text-2xl"}`}>{priceLabel}</span>
                    {plan.credits && <p className="text-[11px] text-zinc-400 mt-0.5">{plan.credits.toLocaleString()} credits/mo</p>}
                    {isAnnual && plan.price > 0 && key !== "enterprise" && (
                      <p className="text-[10px] text-emerald-400 mt-0.5">Billed annually (${Math.round(plan.price * 0.8 * 12)}/yr)</p>
                    )}
                  </div>
                  <ul className="space-y-2 mb-5">
                    {featureList.slice(0, 10).map((f, i) => (
                      <li key={i} className="flex items-start gap-2 text-[13px] leading-snug text-zinc-300">
                        <Check className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0 mt-0.5" /> <span>{f}</span>
                      </li>
                    ))}
                  </ul>
                  {isCurrent ? (
                    <div className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                      <Check className="w-4 h-4 text-emerald-400" />
                      <span className="text-sm font-medium text-emerald-400">Your current plan</span>
                    </div>
                  ) : key === "enterprise" ? (
                    <Button
                      onClick={() => window.open("mailto:sales@nexuscloud.ai?subject=Enterprise Plan Inquiry", "_blank")}
                      className="w-full bg-zinc-800 text-zinc-200 hover:bg-zinc-700 font-medium border border-zinc-700"
                      data-testid="contact-sales-btn"
                    >
                      Contact Sales
                    </Button>
                  ) : (
                    <Button
                      onClick={() => handleUpgrade(key)}
                      disabled={!!upgrading}
                      className="w-full bg-zinc-100 text-zinc-900 hover:bg-zinc-200 font-medium"
                      data-testid={`upgrade-${key}-btn`}
                    >
                      {upgrading === key ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                      {upgrading === key ? "Redirecting..." : `Upgrade to ${plan.name}`}
                    </Button>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* PayPal note */}
        <div className="mt-8 p-4 rounded-xl bg-zinc-900/30 border border-zinc-800/40 text-center">
          <p className="text-xs text-zinc-600">Secure payments powered by Stripe.</p>
        </div>

        {/* Payment history */}
        {subscription?.transactions?.length > 0 && (
          <div className="mt-8" data-testid="payment-history">
            <h3 className="text-lg font-semibold text-zinc-200 mb-4" style={{ fontFamily: 'Syne, sans-serif' }}>Payment History</h3>
            <div className="space-y-2">
              {subscription.transactions.map((txn) => (
                <div key={txn.transaction_id} className="flex items-center justify-between p-3 rounded-lg bg-zinc-900/40 border border-zinc-800/40">
                  <div>
                    <span className="text-sm text-zinc-300">{txn.plan_id?.toUpperCase()} Plan</span>
                    <span className="text-xs text-zinc-600 ml-2">{new Date(txn.created_at).toLocaleDateString()}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-mono text-zinc-300">${txn.amount}</span>
                    <Badge className={txn.payment_status === 'paid' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-zinc-700 text-zinc-400'}>
                      {txn.payment_status}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
