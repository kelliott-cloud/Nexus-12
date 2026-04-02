import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Zap, Key, ToggleLeft, ToggleRight, Lock, TrendingUp, Loader2, Check, Settings2, Play, Copy, ExternalLink, ChevronDown, ChevronUp, CheckCircle, X } from "lucide-react";
import NexusAIBudgetCenter from "@/components/NexusAIBudgetCenter";

const PROVIDERS = [
  // Tier 1: Premium AI
  { key: "chatgpt", name: "ChatGPT", provider: "OpenAI", color: "#10A37F", helpUrl: "https://platform.openai.com/api-keys", tier: "Premium AI" },
  { key: "claude", name: "Claude", provider: "Anthropic", color: "#D97757", helpUrl: "https://console.anthropic.com/settings/keys", tier: "Premium AI" },
  { key: "grok", name: "Grok", provider: "xAI", color: "#888888", helpUrl: "https://console.x.ai/team/default/api-keys", tier: "Premium AI" },
  // Tier 2: Standard AI
  { key: "gemini", name: "Gemini", provider: "Google", color: "#4285F4", helpUrl: "https://aistudio.google.com/apikey", tier: "Standard AI" },
  { key: "mistral", name: "Mistral", provider: "Mistral AI", color: "#FF7000", helpUrl: "https://console.mistral.ai/api-keys", tier: "Standard AI" },
  { key: "perplexity", name: "Perplexity", provider: "Perplexity AI", color: "#20B2AA", helpUrl: "https://www.perplexity.ai/pplx-api", tier: "Standard AI" },
  { key: "deepseek", name: "DeepSeek", provider: "DeepSeek", color: "#4D6BFE", helpUrl: "https://platform.deepseek.com/api_keys", tier: "Standard AI" },
  { key: "cohere", name: "Cohere", provider: "Cohere", color: "#39594D", helpUrl: "https://dashboard.cohere.com/api-keys", tier: "Standard AI" },
  { key: "qwen", name: "Qwen", provider: "Alibaba Cloud", color: "#615EFF", helpUrl: "https://modelstudio.console.alibabacloud.com", tier: "Standard AI" },
  { key: "kimi", name: "Kimi", provider: "Moonshot AI", color: "#000000", helpUrl: "https://platform.moonshot.ai", tier: "Standard AI" },
  { key: "manus", name: "Manus", provider: "Manus AI", color: "#6C5CE7", helpUrl: "https://manus.im/app#settings/integrations/api", tier: "Standard AI" },
  // Tier 3: Economy AI
  { key: "groq", name: "Groq", provider: "Groq", color: "#F55036", helpUrl: "https://console.groq.com/keys", tier: "Economy AI" },
  { key: "mercury", name: "Mercury 2", provider: "Inception Labs", color: "#00D4FF", helpUrl: "https://platform.inceptionlabs.ai/", tier: "Economy AI" },
  { key: "llama", name: "Llama", provider: "Together AI", color: "#0467DF", helpUrl: "https://api.together.xyz/settings/api-keys", tier: "Economy AI" },
  { key: "glm", name: "GLM", provider: "Zhipu AI", color: "#3D5AFE", helpUrl: "https://open.bigmodel.cn", tier: "Economy AI" },
  // Tier 4: OpenRouter
  { key: "pi", name: "Pi", provider: "OpenRouter", color: "#FF6B35", helpUrl: "https://openrouter.ai/keys", tier: "OpenRouter" },
  { key: "cursor", name: "Cursor", provider: "OpenRouter", color: "#00E5A0", helpUrl: "https://openrouter.ai/keys", tier: "OpenRouter" },
  { key: "notebooklm", name: "NotebookLM", provider: "OpenRouter", color: "#FBBC04", helpUrl: "https://openrouter.ai/keys", tier: "OpenRouter" },
  { key: "copilot", name: "GitHub Copilot", provider: "OpenRouter", color: "#171515", helpUrl: "https://openrouter.ai/keys", tier: "OpenRouter" },
  // Cloud Storage
  { key: "google_drive", name: "Google Drive", provider: "Google", color: "#4285F4", helpUrl: "https://console.cloud.google.com/apis/credentials", tier: "Cloud Storage", multiKey: true },
  { key: "onedrive", name: "OneDrive", provider: "Microsoft", color: "#0078D4", helpUrl: "https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps", tier: "Cloud Storage", multiKey: true },
  { key: "dropbox", name: "Dropbox", provider: "Dropbox", color: "#0061FF", helpUrl: "https://www.dropbox.com/developers/apps", tier: "Cloud Storage", multiKey: true },
  // Social & Messaging
  { key: "telegram", name: "Telegram Bot", provider: "Telegram", color: "#26A5E4", helpUrl: "https://t.me/BotFather", tier: "Social & Messaging" },
  { key: "twitter", name: "Twitter/X", provider: "X Corp", color: "#1DA1F2", helpUrl: "https://developer.x.com/en/portal/dashboard", tier: "Social & Messaging", multiKey: true },
  { key: "linkedin", name: "LinkedIn", provider: "Microsoft", color: "#0A66C2", helpUrl: "https://www.linkedin.com/developers/apps", tier: "Social & Messaging", multiKey: true },
  // Infrastructure
  { key: "cloudflare_r2", name: "Cloudflare R2", provider: "Cloudflare", color: "#F38020", helpUrl: "https://dash.cloudflare.com", tier: "Infrastructure", multiKey: true },
  { key: "cloudflare_kv", name: "Cloudflare KV", provider: "Cloudflare", color: "#F38020", helpUrl: "https://dash.cloudflare.com", tier: "Infrastructure", multiKey: true },
  { key: "cloudflare_ai_gateway", name: "CF AI Gateway", provider: "Cloudflare", color: "#F38020", helpUrl: "https://dash.cloudflare.com", tier: "Infrastructure", multiKey: true },
  // Developer
  { key: "github", name: "GitHub", provider: "GitHub", color: "#171515", helpUrl: "https://github.com/settings/developers", tier: "Developer", multiKey: true },
];

export default function ManagedKeysUser() {
  const [settings, setSettings] = useState(null);
  const [credits, setCredits] = useState(null);
  const [adminKeys, setAdminKeys] = useState(null);
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);
  const [toggling, setToggling] = useState("");
  const [loading, setLoading] = useState(true);
  const [keyInputs, setKeyInputs] = useState({});
  const [savingKeys, setSavingKeys] = useState(false);
  const [showSetup, setShowSetup] = useState(false);
  const [expandedCard, setExpandedCard] = useState(null);
  const [testingKey, setTestingKey] = useState("");
  const [testResults, setTestResults] = useState({});

  useEffect(() => {
    const load = async () => {
      try {
        const [settingsRes, creditsRes] = await Promise.all([
          api.get("/settings/managed-keys"),
          api.get("/settings/managed-keys/credits"),
        ]);
        setSettings(settingsRes.data);
        setCredits(creditsRes.data);

        // Check if super admin — try to load admin keys
        try {
          const adminRes = await api.get("/admin/managed-keys");
          setAdminKeys(adminRes.data?.providers || {});
          setIsSuperAdmin(true);
          // Auto-show setup if no keys configured
          const configured = Object.values(adminRes.data?.providers || {}).some(p => p.configured);
          if (!configured) setShowSetup(true);
        } catch { /* not admin */ }
      } catch {}
      setLoading(false);
    };
    load();
  }, []);

  const toggle = async (provider, enabled) => {
    setToggling(provider);
    try {
      await api.post("/settings/managed-keys/toggle", { provider, enabled });
      setSettings(prev => ({
        ...prev,
        providers: { ...prev.providers, [provider]: { ...prev.providers[provider], opted_in: enabled } },
      }));
      toast.success(`${PROVIDERS.find(p => p.key === provider)?.name || provider} ${enabled ? 'enabled' : 'disabled'}`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
    setToggling("");
  };

  const saveAdminKeys = async () => {
    const toSave = {};
    for (const [k, v] of Object.entries(keyInputs)) {
      if (v && v.trim()) toSave[k] = v.trim();
    }
    if (!Object.keys(toSave).length) { toast.error("Enter at least one API key"); return; }
    setSavingKeys(true);
    try {
      await api.post("/admin/managed-keys", { keys: toSave });
      toast.success("Platform keys saved! Providers are now available.");
      // Reload settings
      const [s, a] = await Promise.all([
        api.get("/settings/managed-keys"),
        api.get("/admin/managed-keys"),
      ]);
      setSettings(s.data);
      setAdminKeys(a.data?.providers || {});
      setKeyInputs({});
      setShowSetup(false);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to save keys");
    }
    setSavingKeys(false);
  };

  const testKey = async (provider) => {
    setTestingKey(provider);
    setTestResults(prev => ({ ...prev, [provider]: null }));
    try {
      const res = await api.post("/settings/ai-keys/test", { agent: provider });
      setTestResults(prev => ({ ...prev, [provider]: res.data?.success ? "ok" : "fail" }));
      toast.success(res.data?.success ? `${provider} key is healthy` : `${provider} key test failed`);
    } catch {
      setTestResults(prev => ({ ...prev, [provider]: "fail" }));
      toast.error(`Failed to test ${provider} key`);
    }
    setTestingKey("");
  };

  if (loading) return <div className="p-6 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-zinc-500" /></div>;
  if (!settings) return null;

  const usagePercent = credits ? Math.min((credits.credits_used / Math.max(credits.credits_total, 1)) * 100, 100) : 0;
  const anyConfigured = settings.providers && Object.values(settings.providers).some(p => p.available);

  return (
    <div className="space-y-6" data-testid="managed-keys-user">
      {/* Credit Balance */}
      {credits && credits.credits_total > 0 && (
        <div className="p-5 rounded-xl bg-zinc-900/40 border border-zinc-800/60">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-cyan-400" />
              <span className="text-sm font-medium text-zinc-200">Nexus AI Credits</span>
            </div>
            <Badge className="bg-zinc-800 text-zinc-300 text-[10px]">{credits.plan?.toUpperCase()} PLAN</Badge>
          </div>
          <Progress value={usagePercent} className="h-2 mb-2" />
          <div className="flex items-center justify-between text-xs text-zinc-500">
            <span>{credits.credits_used?.toFixed(0) || 0} / {credits.credits_total?.toLocaleString()} credits used</span>
            <span>{credits.credits_remaining?.toFixed(0) || 0} remaining</span>
          </div>
          {credits.overage_cost_usd > 0 && (
            <div className="mt-2 flex items-center gap-1.5 text-xs text-amber-400">
              <TrendingUp className="w-3 h-3" />
              <span>Overage charges: ${credits.overage_cost_usd.toFixed(2)}</span>
            </div>
          )}
        </div>
      )}

      {/* Super Admin: Platform Key Setup */}
      {isSuperAdmin && !anyConfigured && (
        <div className="p-5 rounded-xl bg-amber-500/10 border border-amber-500/20">
          <div className="flex items-center gap-2 mb-2">
            <Settings2 className="w-4 h-4 text-amber-400" />
            <span className="text-sm font-semibold text-amber-300">Setup Required — Add Platform API Keys</span>
          </div>
          <p className="text-xs text-zinc-400 mb-3">
            As Super Admin, you need to add API keys for the AI providers your tenants will use. These keys power the "Nexus AI" feature across all organizations.
          </p>
          {!showSetup && (
            <Button onClick={() => setShowSetup(true)} size="sm" className="bg-amber-500 hover:bg-amber-400 text-zinc-950 font-medium">
              <Key className="w-3.5 h-3.5 mr-1.5" /> Configure Platform Keys
            </Button>
          )}
        </div>
      )}

      {isSuperAdmin && (showSetup || anyConfigured) && (
        <div className="p-5 rounded-xl bg-zinc-900/40 border border-zinc-800/60">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Key className="w-4 h-4 text-cyan-400" />
              <span className="text-sm font-semibold text-zinc-200">Platform API Keys (Admin)</span>
            </div>
            {!showSetup && (
              <Button variant="outline" size="sm" onClick={() => setShowSetup(!showSetup)} className="text-[10px] border-zinc-700 text-zinc-400 h-7">
                Edit Keys
              </Button>
            )}
          </div>

          {showSetup ? (
            <div className="space-y-2">
              {PROVIDERS.map(p => {
                const status = adminKeys?.[p.key];
                return (
                  <div key={p.key} className="flex items-center gap-3 p-2.5 rounded-lg bg-zinc-950/50 border border-zinc-800/40">
                    <div className="w-7 h-7 rounded-md flex items-center justify-center" style={{ backgroundColor: p.color + '15' }}>
                      <Key className="w-3.5 h-3.5" style={{ color: p.color }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium text-zinc-200">{p.name}</span>
                        {status?.configured && <Badge className="bg-emerald-500/15 text-emerald-400 text-[8px]">Active</Badge>}
                      </div>
                      {status?.configured && <p className="text-[9px] text-zinc-600">{status.masked}</p>}
                    </div>
                    <Input
                      placeholder={status?.configured ? "Replace key..." : "Paste API key"}
                      type="password"
                      value={keyInputs[p.key] || ""}
                      onChange={e => setKeyInputs({ ...keyInputs, [p.key]: e.target.value })}
                      className="w-48 bg-zinc-800 border-zinc-700 text-xs h-7"
                      data-testid={`platform-key-${p.key}`}
                    />
                    <a href={p.helpUrl} target="_blank" rel="noopener noreferrer" className="text-[9px] text-cyan-500 hover:underline whitespace-nowrap">Get key</a>
                  </div>
                );
              })}
              <Button onClick={saveAdminKeys} disabled={savingKeys} size="sm" className="mt-2 bg-cyan-600 hover:bg-cyan-500 text-white">
                {savingKeys ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <Check className="w-3.5 h-3.5 mr-1.5" />}
                Save Platform Keys
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {PROVIDERS.map(p => {
                const status = adminKeys?.[p.key];
                return (
                  <div key={p.key} className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${status?.configured ? 'border-emerald-500/20 bg-emerald-500/5' : 'border-zinc-800/40 bg-zinc-950/30'}`}>
                    <div className="w-6 h-6 rounded-md flex items-center justify-center text-[10px] font-bold shrink-0"
                      style={{ backgroundColor: p.color, color: ['#000000', '#171515'].includes(p.color) ? '#fff' : (parseInt(p.color.slice(1), 16) > 0x808080 ? '#09090b' : '#fff') }}>
                      {p.name[0]}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs text-zinc-300 truncate">{p.name}</p>
                      <p className="text-[9px] text-zinc-600">{p.provider}</p>
                    </div>
                    {status?.configured ? (
                      <CheckCircle className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                    ) : (
                      <X className="w-3.5 h-3.5 text-zinc-700 shrink-0" />
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Provider toggles */}
      <div className="p-5 rounded-xl bg-zinc-900/40 border border-zinc-800/60">
        <h3 className="text-sm font-semibold text-zinc-200 mb-1">Use Nexus AI Keys</h3>
        <p className="text-xs text-zinc-500 mb-5">
          Toggle providers on to use platform-provided keys instead of your own. Usage deducts from your credit balance.
        </p>
        {["Premium AI", "Standard AI", "Economy AI", "OpenRouter", "Cloud Storage", "Social & Messaging", "Infrastructure", "Developer"].map(tier => {
          const tierProviders = PROVIDERS.filter(p => p.tier === tier);
          return (
            <div key={tier} className="mb-5">
              <p className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-3">{tier}</p>
              <div className="space-y-3">
                {tierProviders.map(p => {
                  const info = settings.providers?.[p.key] || {};
                  const isToggling = toggling === p.key;
                  const isExpanded = expandedCard === p.key;
                  const isTesting = testingKey === p.key;
                  const testResult = testResults[p.key];
                  const isConnected = info.available && info.opted_in;
                  const isAvailable = info.available;

                  return (
                    <div
                      key={p.key}
                      className={`rounded-xl border transition-all ${
                        isConnected
                          ? "border-emerald-500/20 bg-zinc-950/70"
                          : isAvailable
                          ? "border-zinc-800/60 bg-zinc-950/50"
                          : "border-zinc-800/30 bg-zinc-950/30"
                      }`}
                      data-testid={`provider-card-${p.key}`}
                    >
                      {/* Card Header */}
                      <div
                        className="flex items-center gap-4 p-4 cursor-pointer"
                        onClick={() => setExpandedCard(isExpanded ? null : p.key)}
                        data-testid={`provider-header-${p.key}`}
                      >
                        {/* Icon */}
                        <div
                          className="w-10 h-10 rounded-xl flex items-center justify-center text-base font-bold shrink-0"
                          style={{
                            backgroundColor: p.color,
                            color: ["#000000", "#171515"].includes(p.color) ? "#fff" : (parseInt(p.color.slice(1), 16) > 0x808080 ? "#09090b" : "#fff"),
                          }}
                        >
                          {p.name[0]}
                        </div>

                        {/* Name + Provider */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-sm font-semibold text-zinc-100">{p.name}</span>
                            <span className="text-[10px] text-zinc-500 font-mono uppercase">{p.provider}</span>
                          </div>
                          {p.multiKey && (
                            <span className="text-[9px] text-zinc-600">Multi-key integration</span>
                          )}
                        </div>

                        {/* Status Badge + Toggle */}
                        <div className="flex items-center gap-3 shrink-0">
                          {isConnected ? (
                            <Badge className="bg-emerald-500/15 text-emerald-400 border border-emerald-500/20 text-[10px] px-2.5 py-1" data-testid={`status-${p.key}`}>
                              Connected
                            </Badge>
                          ) : isAvailable ? (
                            <Badge className="bg-zinc-800/80 text-zinc-400 border border-zinc-700/40 text-[10px] px-2.5 py-1" data-testid={`status-${p.key}`}>
                              Available
                            </Badge>
                          ) : (
                            <Badge className="bg-zinc-900/60 text-zinc-600 border border-zinc-800/30 text-[10px] px-2.5 py-1" data-testid={`status-${p.key}`}>
                              Not configured
                            </Badge>
                          )}

                          {info.opted_in && (
                            <Badge className="bg-cyan-500/15 text-cyan-400 text-[9px] px-2 py-0.5">ON</Badge>
                          )}

                          {!info.eligible ? (
                            <Lock className="w-4 h-4 text-zinc-700" title="Requires paid plan" />
                          ) : !isAvailable ? (
                            <span className="w-5" />
                          ) : (
                            <button
                              onClick={(e) => { e.stopPropagation(); toggle(p.key, !info.opted_in); }}
                              disabled={isToggling}
                              className="text-zinc-400 hover:text-zinc-200 transition-colors"
                              data-testid={`toggle-${p.key}`}
                            >
                              {isToggling ? (
                                <Loader2 className="w-5 h-5 animate-spin" />
                              ) : info.opted_in ? (
                                <ToggleRight className="w-6 h-6 text-cyan-400" />
                              ) : (
                                <ToggleLeft className="w-6 h-6" />
                              )}
                            </button>
                          )}

                          {isAvailable && (
                            <button onClick={(e) => { e.stopPropagation(); setExpandedCard(isExpanded ? null : p.key); }} className="text-zinc-600 hover:text-zinc-400 transition-colors">
                              {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Expanded Details */}
                      {isExpanded && isAvailable && (
                        <div className="px-4 pb-4 pt-0 border-t border-zinc-800/40 mt-0" data-testid={`provider-details-${p.key}`}>
                          <div className="flex items-center gap-3 mt-3 flex-wrap">
                            {/* Masked key display */}
                            <div className="flex-1 min-w-[200px]">
                              <Input
                                type="password"
                                value="••••••••••••••••"
                                readOnly
                                className="bg-zinc-900/80 border-zinc-800/60 text-xs h-9 font-mono text-zinc-400"
                                data-testid={`masked-key-${p.key}`}
                              />
                            </div>

                            {/* Test button */}
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={isTesting}
                              onClick={(e) => { e.stopPropagation(); testKey(p.key); }}
                              className={`h-9 text-xs border-zinc-700 ${
                                testResult === "ok" ? "border-emerald-500/30 text-emerald-400" :
                                testResult === "fail" ? "border-red-500/30 text-red-400" :
                                "text-zinc-400"
                              }`}
                              data-testid={`test-key-${p.key}`}
                            >
                              {isTesting ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
                              ) : (
                                <Play className="w-3 h-3 mr-1" />
                              )}
                              {testResult === "ok" ? "Healthy" : testResult === "fail" ? "Failed" : "Test"}
                            </Button>

                            {/* Copy button */}
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={(e) => {
                                e.stopPropagation();
                                navigator.clipboard.writeText(`Platform key for ${p.name}`);
                                toast.success("Key reference copied");
                              }}
                              className="h-9 px-2.5 border-zinc-700 text-zinc-400"
                              data-testid={`copy-key-${p.key}`}
                            >
                              <Copy className="w-3.5 h-3.5" />
                            </Button>

                            {/* Get key link */}
                            <a
                              href={p.helpUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-xs text-cyan-500 hover:text-cyan-400 underline underline-offset-2 transition-colors"
                              onClick={(e) => e.stopPropagation()}
                              data-testid={`get-key-${p.key}`}
                            >
                              Get key <ExternalLink className="w-3 h-3" />
                            </a>
                          </div>

                          {/* Credit rate info */}
                          {settings.credit_rates?.[p.key] && (
                            <p className="text-[10px] text-zinc-600 mt-2.5">
                              Credit rate: {settings.credit_rates[p.key].input} in / {settings.credit_rates[p.key].output} out per 1K tokens
                            </p>
                          )}
                          {settings.integration_rates?.[p.key] && (
                            <p className="text-[10px] text-zinc-600 mt-2.5">
                              Credit rate: {settings.integration_rates[p.key]} per API call
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      <NexusAIBudgetCenter />
    </div>
  );
}
