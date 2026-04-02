import { useState, useEffect } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { api } from "@/App";
import { Button } from "@/components/ui/button";
import { Shield, Cookie, AlertTriangle } from "lucide-react";

// Cookie Consent Banner
export function CookieConsentBanner() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    const consent = localStorage.getItem("nexus_cookie_consent");
    if (!consent) setShow(true);
  }, []);

  const accept = (level) => {
    localStorage.setItem("nexus_cookie_consent", level);
    api.post("/legal/cookie-consent", { consent: level }).catch(() => {});
    setShow(false);
  };

  if (!show) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-[100] p-4 bg-zinc-900 border-t border-zinc-800 shadow-2xl" data-testid="cookie-banner">
      <div className="max-w-4xl mx-auto flex items-center gap-4">
        <Cookie className="w-5 h-5 text-amber-400 flex-shrink-0" />
        <p className="text-sm text-zinc-400 flex-1">
          We use essential cookies for authentication. By continuing, you accept our{" "}
          <a href="/privacy" className="text-emerald-400 hover:underline">Privacy Policy</a> and{" "}
          <a href="/terms" className="text-emerald-400 hover:underline">Terms of Service</a>.
        </p>
        <div className="flex gap-2 flex-shrink-0">
          <Button size="sm" variant="outline" onClick={() => accept("essential")} className="border-zinc-700 text-zinc-300 text-xs" data-testid="cookie-essential">Essential Only</Button>
          <Button size="sm" onClick={() => accept("all")} className="bg-emerald-500 hover:bg-emerald-400 text-white text-xs" data-testid="cookie-accept">Accept All</Button>
        </div>
      </div>
    </div>
  );
}

// Beta Banner (persistent in-app)
export function BetaBanner() {
  const [dismissed, setDismissed] = useState(() => sessionStorage.getItem("nexus_beta_dismissed") === "1");

  if (dismissed) return null;

  return (
    <div className="flex-shrink-0 bg-amber-500/10 border-b border-amber-500/20 px-4 py-1.5 flex items-center justify-center gap-2" data-testid="beta-banner">
      <AlertTriangle className="w-3 h-3 text-amber-400" />
      <span className="text-[11px] text-amber-400">BETA — This platform is in active development. Features may change and data may be reset.</span>
      <button onClick={() => { setDismissed(true); sessionStorage.setItem("nexus_beta_dismissed", "1"); }} className="text-amber-400/60 hover:text-amber-400 text-xs ml-2">dismiss</button>
    </div>
  );
}

// ToS Acceptance Modal (blocks app if ToS needs re-acceptance)
export function TosAcceptanceModal({ user, onAccepted }) {
  const [loading, setLoading] = useState(false);

  if (!user?.tos_needs_acceptance) return null;

  const handleAccept = async () => {
    setLoading(true);
    try {
      await api.post("/legal/accept-tos", { beta_accepted: true });
      onAccepted();
    } catch (err) { handleSilent(err, "LegalComponents:op1"); }
    setLoading(false);
  };

  return (
    <div className="fixed inset-0 z-[200] bg-black/80 flex items-center justify-center p-6" data-testid="tos-modal">
      <div className="bg-zinc-900 rounded-2xl border border-zinc-800 max-w-md w-full p-6">
        <Shield className="w-8 h-8 text-emerald-400 mx-auto mb-4" />
        <h2 className="text-lg font-bold text-zinc-100 text-center mb-2" style={{ fontFamily: "Syne, sans-serif" }}>Updated Terms of Service</h2>
        <p className="text-sm text-zinc-400 text-center mb-4">Our Terms of Service have been updated. Please review and accept to continue using Nexus.</p>
        <div className="space-y-2 mb-4">
          <a href="/terms" target="_blank" className="block text-sm text-emerald-400 hover:underline">Terms of Service</a>
          <a href="/privacy" target="_blank" className="block text-sm text-emerald-400 hover:underline">Privacy Policy</a>
          <a href="/acceptable-use" target="_blank" className="block text-sm text-emerald-400 hover:underline">Acceptable Use Policy</a>
        </div>
        <Button onClick={handleAccept} disabled={loading} className="w-full bg-emerald-500 hover:bg-emerald-400 text-white" data-testid="accept-tos-btn">
          {loading ? "Accepting..." : "I Accept the Terms of Service"}
        </Button>
      </div>
    </div>
  );
}

// AI Output Disclaimer (shown once per session in chat)
export function AiDisclaimer() {
  const [dismissed, setDismissed] = useState(() => sessionStorage.getItem("nexus_ai_disclaimer") === "1");

  if (dismissed) return null;

  return (
    <div className="mx-6 mt-2 mb-1 px-3 py-2 rounded-lg bg-blue-500/5 border border-blue-500/15 flex items-center gap-2" data-testid="ai-disclaimer">
      <Shield className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />
      <p className="text-[11px] text-blue-400/80 flex-1">AI-generated content may contain errors. Verify before relying on outputs.</p>
      <button onClick={() => { setDismissed(true); sessionStorage.setItem("nexus_ai_disclaimer", "1"); }} className="text-blue-400/40 hover:text-blue-400 text-[10px]">dismiss</button>
    </div>
  );
}
