import { useState } from "react";
import { AlertTriangle, KeyRound, Shield, X, ExternalLink } from "lucide-react";

export const ChatAIKeyHealthBanner = ({ health, user }) => {
  const [dismissed, setDismissed] = useState(() => {
    try {
      const key = `nexus_ai_health_dismissed_${health?.workspace_id || ""}`;
      const stored = localStorage.getItem(key);
      if (!stored) return false;
      const { ts } = JSON.parse(stored);
      // Auto-expire dismissal after 24 hours
      return Date.now() - ts < 86400000;
    } catch { return false; }
  });

  if (dismissed || !health?.has_warning || !(health.warnings || []).length) return null;

  const handleDismiss = () => {
    try {
      const key = `nexus_ai_health_dismissed_${health?.workspace_id || ""}`;
      localStorage.setItem(key, JSON.stringify({ ts: Date.now() }));
    } catch {}
    setDismissed(true);
  };

  const warnings = health.warnings || [];
  const providers = warnings.map((item) => item.provider);

  return (
    <div className="mx-6 mt-3 rounded-xl border border-amber-500/25 bg-amber-500/8 px-4 py-3 text-sm relative" data-testid="chat-ai-key-health-banner">
      <button
        onClick={handleDismiss}
        className="absolute top-2 right-2 p-1 rounded-md text-amber-500/60 hover:text-amber-300 hover:bg-amber-500/10 transition-colors"
        title="Dismiss for 24 hours"
        data-testid="dismiss-ai-key-health-banner"
      >
        <X className="w-3.5 h-3.5" />
      </button>
      <div className="flex items-start gap-3 pr-6">
        <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-medium text-amber-300">AI key attention needed</p>
            <span className="text-[10px] uppercase tracking-wider text-amber-500/80">Workspace chat health</span>
          </div>
          <p className="mt-1 text-xs text-amber-100/85" data-testid="chat-ai-key-health-message">
            This workspace is relying on placeholder or invalid platform keys for: <span className="font-semibold">{providers.join(", ")}</span>. Agents may stop responding or fall back unpredictably until the keys are updated.
          </p>
          <div className="mt-3 flex items-center gap-2 flex-wrap text-xs">
            {/* Per-provider "Fix now" deep-links */}
            {warnings.slice(0, 3).map((w) => (
              <a
                key={w.provider}
                href={`/settings?tab=ai-keys&fix=${encodeURIComponent(w.provider)}`}
                className="inline-flex items-center gap-1 rounded-lg border border-amber-500/25 bg-zinc-950/60 px-3 py-1.5 text-amber-200 hover:bg-zinc-900 transition-colors"
                data-testid={`fix-now-${w.provider}`}
              >
                <ExternalLink className="w-3 h-3" /> Fix {w.provider}
              </a>
            ))}
            {warnings.length > 3 && (
              <a
                href="/settings?tab=ai-keys"
                className="inline-flex items-center gap-1 rounded-lg border border-amber-500/25 bg-zinc-950/60 px-3 py-1.5 text-amber-200 hover:bg-zinc-900 transition-colors"
                data-testid="chat-ai-key-health-user-link"
              >
                <KeyRound className="w-3 h-3" /> +{warnings.length - 3} more
              </a>
            )}
            <a
              href="/settings?tab=ai-keys"
              className="inline-flex items-center gap-1 rounded-lg border border-amber-500/25 bg-zinc-950/60 px-3 py-1.5 text-amber-200 hover:bg-zinc-900 transition-colors"
              data-testid="chat-ai-key-health-all-keys"
            >
              <KeyRound className="w-3 h-3" /> AI Keys
            </a>
            {user?.platform_role === "super_admin" && (
              <a
                href={`/admin?tab=managed-keys&fix=${encodeURIComponent(providers[0] || "")}`}
                className="inline-flex items-center gap-1 rounded-lg border border-amber-500/25 bg-zinc-950/60 px-3 py-1.5 text-amber-200 hover:bg-zinc-900 transition-colors"
                data-testid="chat-ai-key-health-admin-link"
              >
                <Shield className="w-3 h-3" /> Platform Keys
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatAIKeyHealthBanner;
