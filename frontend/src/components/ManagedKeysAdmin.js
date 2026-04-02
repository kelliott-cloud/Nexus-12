import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Key, Check, Loader2, Shield } from "lucide-react";

const PROVIDERS = [
  { key: "chatgpt", name: "ChatGPT", provider: "OpenAI", color: "#10A37F" },
  { key: "claude", name: "Claude", provider: "Anthropic", color: "#D97757" },
  { key: "grok", name: "Grok", provider: "xAI", color: "#888888" },
  { key: "gemini", name: "Gemini", provider: "Google", color: "#4285F4" },
  { key: "mistral", name: "Mistral", provider: "Mistral AI", color: "#FF7000" },
  { key: "perplexity", name: "Perplexity", provider: "Perplexity AI", color: "#20B2AA" },
  { key: "deepseek", name: "DeepSeek", provider: "DeepSeek", color: "#4D6BFE" },
  { key: "cohere", name: "Cohere", provider: "Cohere", color: "#39594D" },
  { key: "groq", name: "Groq", provider: "Groq", color: "#F55036" },
  { key: "qwen", name: "Qwen", provider: "Alibaba Cloud", color: "#615EFF" },
  { key: "kimi", name: "Kimi", provider: "Moonshot AI", color: "#000000" },
  { key: "mercury", name: "Mercury 2", provider: "Inception Labs", color: "#00D4FF" },
  { key: "llama", name: "Llama", provider: "Together AI", color: "#0467DF" },
  { key: "glm", name: "GLM", provider: "Zhipu AI", color: "#3D5AFE" },
  { key: "manus", name: "Manus", provider: "Manus AI", color: "#6C5CE7" },
  { key: "pi", name: "Pi", provider: "OpenRouter", color: "#FF6B35" },
  { key: "cursor", name: "Cursor", provider: "OpenRouter", color: "#00E5A0" },
  { key: "notebooklm", name: "NotebookLM", provider: "OpenRouter", color: "#FBBC04" },
  { key: "copilot", name: "GitHub Copilot", provider: "OpenRouter", color: "#171515" },
  // Non-AI integrations
  { key: "google_drive", name: "Google Drive", provider: "Google", color: "#4285F4" },
  { key: "onedrive", name: "OneDrive", provider: "Microsoft", color: "#0078D4" },
  { key: "dropbox", name: "Dropbox", provider: "Dropbox", color: "#0061FF" },
  { key: "telegram", name: "Telegram Bot", provider: "Telegram", color: "#26A5E4" },
  { key: "twitter", name: "Twitter/X", provider: "X Corp", color: "#1DA1F2" },
  { key: "linkedin", name: "LinkedIn", provider: "Microsoft", color: "#0A66C2" },
  { key: "cloudflare_r2", name: "Cloudflare R2", provider: "Cloudflare", color: "#F38020" },
  { key: "cloudflare_kv", name: "Cloudflare KV", provider: "Cloudflare", color: "#F38020" },
  { key: "cloudflare_ai_gateway", name: "CF AI Gateway", provider: "Cloudflare", color: "#F38020" },
  { key: "github", name: "GitHub", provider: "GitHub", color: "#171515" },
];

export default function ManagedKeysAdmin() {
  const [keys, setKeys] = useState({});
  const [configured, setConfigured] = useState({});
  const [health, setHealth] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/admin/managed-keys").then(r => {
      setConfigured(r.data?.providers || {});
    }).catch(() => {});
    api.get("/admin/managed-keys/health").then(r => {
      setHealth(r.data?.health || {});
    }).catch(() => {});
  }, []);

  const save = async () => {
    const toSave = {};
    for (const [k, v] of Object.entries(keys)) {
      if (v && v.trim() && !v.startsWith("****")) toSave[k] = v.trim();
    }
    if (!Object.keys(toSave).length) { toast.error("Enter at least one key"); return; }
    setSaving(true);
    try {
      await api.post("/admin/managed-keys", { keys: toSave });
      toast.success("Platform keys updated");
      const r = await api.get("/admin/managed-keys");
      setConfigured(r.data?.providers || {});
      const hr = await api.get("/admin/managed-keys/health");
      setHealth(hr.data?.health || {});
      setKeys({});
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to save");
    }
    setSaving(false);
  };

  return (
    <div className="p-6 max-w-2xl" data-testid="managed-keys-admin">
      <div className="flex items-center gap-3 mb-1">
        <Shield className="w-5 h-5 text-cyan-400" />
        <h2 className="text-lg font-semibold text-zinc-100">Platform AI Keys</h2>
      </div>
      <p className="text-sm text-zinc-500 mb-6">
        Set API keys that tenants can opt into using instead of their own. Credits are deducted from their plan allocation.
      </p>
      <div className="space-y-3">
        {PROVIDERS.map(p => {
          const status = configured[p.key];
          const healthStatus = health[p.key];
          return (
            <div key={p.key} className="flex items-center gap-3 p-3 rounded-lg bg-zinc-900/50 border border-zinc-800/50">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ backgroundColor: p.color + '20' }}>
                <Key className="w-4 h-4" style={{ color: p.color }} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-zinc-200">{p.name}</span>
                  <span className="text-xs text-zinc-600">{p.provider}</span>
                  {status?.configured && <Badge className="bg-emerald-500/15 text-emerald-400 text-[9px]">Active</Badge>}
                  {healthStatus?.status === "healthy" && <Badge className="bg-emerald-500/15 text-emerald-400 text-[9px]">Healthy</Badge>}
                  {healthStatus?.status === "invalid" && <Badge className="bg-red-500/15 text-red-400 text-[9px]">Invalid</Badge>}
                  {healthStatus?.status === "placeholder" && <Badge className="bg-amber-500/15 text-amber-400 text-[9px]">Placeholder</Badge>}
                </div>
                {status?.configured && <p className="text-[10px] text-zinc-600 mt-0.5">Key: {status.masked}</p>}
                {healthStatus?.message && <p className={`text-[10px] mt-0.5 ${healthStatus.status === 'healthy' ? 'text-emerald-400/80' : healthStatus.status === 'placeholder' ? 'text-amber-400/80' : 'text-red-400/80'}`}>{healthStatus.message}</p>}
              </div>
              <Input
                placeholder="Enter API key"
                type="password"
                value={keys[p.key] || ""}
                onChange={e => setKeys({ ...keys, [p.key]: e.target.value })}
                className="w-56 bg-zinc-800 border-zinc-700 text-xs h-8"
                data-testid={`platform-key-${p.key}`}
              />
            </div>
          );
        })}
      </div>
      <Button onClick={save} disabled={saving} className="mt-4 bg-cyan-600 hover:bg-cyan-500 text-white">
        {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Check className="w-4 h-4 mr-2" />}
        Save Platform Keys
      </Button>
    </div>
  );
}
