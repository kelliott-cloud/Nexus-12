import { useState, useEffect } from "react";
import { useConfirm } from "@/components/ConfirmDialog";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Zap, ArrowLeft, Key, Eye, EyeOff, Check, X, Save, Loader2, User, CreditCard, Play, CheckCircle, XCircle, Bug, Copy, ChevronDown, ChevronUp, BarChart3, ExternalLink, Settings, Puzzle, Palette, Shield } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/App";
import { useLanguage } from "@/contexts/LanguageContext";
import { LanguageToggle } from "@/components/LanguageToggle";
import { PlatformIntegrations, CloudStorageConnections } from "@/components/IntegrationSettings";
import { SocialConnectionsPanel } from "@/components/SocialConnectionsPanel";
import DesktopBridgePanel from "@/components/DesktopBridgePanel";
import OpenClawPanel from "@/components/OpenClawPanel";
import ModuleSettingsPanel from "@/components/ModuleSettingsPanel";
import MFASetup from "@/components/MFASetup";
import ManagedKeysUser from "@/components/ManagedKeysUser";

import GlobalHeader from "@/components/GlobalHeader";
const AI_AGENTS = [
  { key: "claude", name: "Claude", provider: "Anthropic", color: "#D97757", placeholder: "Enter API key", helpUrl: "https://console.anthropic.com/settings/keys" },
  { key: "chatgpt", name: "ChatGPT", provider: "OpenAI", color: "#10A37F", placeholder: "Enter API key", helpUrl: "https://platform.openai.com/api-keys" },
  { key: "gemini", name: "Gemini", provider: "Google", color: "#4285F4", placeholder: "Enter API key", helpUrl: "https://aistudio.google.com/apikey" },
  { key: "perplexity", name: "Perplexity", provider: "Perplexity AI", color: "#20B2AA", placeholder: "pplx-...", helpUrl: "https://www.perplexity.ai/pplx-api" },
  { key: "mistral", name: "Mistral", provider: "Mistral AI", color: "#FF7000", placeholder: "...", helpUrl: "https://console.mistral.ai/api-keys" },
  { key: "cohere", name: "Cohere", provider: "Cohere", color: "#39594D", placeholder: "...", helpUrl: "https://dashboard.cohere.com/api-keys" },
  { key: "groq", name: "Groq", provider: "Groq", color: "#F55036", placeholder: "gsk_...", helpUrl: "https://console.groq.com/keys" },
  { key: "deepseek", name: "DeepSeek", provider: "DeepSeek", color: "#4D6BFE", placeholder: "Enter API key", helpUrl: "https://platform.deepseek.com/api_keys" },
  { key: "grok", name: "Grok", provider: "xAI", color: "#F5F5F5", placeholder: "xai-...", helpUrl: "https://console.x.ai/team/default/api-keys" },
  { key: "mercury", name: "Mercury 2", provider: "Inception Labs", color: "#00D4FF", placeholder: "...", helpUrl: "https://platform.inceptionlabs.ai/" },
  { key: "pi", name: "Pi", provider: "OpenRouter", color: "#FF6B35", placeholder: "Enter API key", helpUrl: "https://openrouter.ai/keys" },
  { key: "manus", name: "Manus", provider: "Manus AI", color: "#6C5CE7", placeholder: "...", helpUrl: "https://manus.im/app#settings/integrations/api" },
  { key: "qwen", name: "Qwen", provider: "Alibaba Cloud", color: "#615EFF", placeholder: "Enter API key", helpUrl: "https://modelstudio.console.alibabacloud.com" },
  { key: "kimi", name: "Kimi", provider: "Moonshot AI", color: "#000000", placeholder: "Enter API key", helpUrl: "https://platform.moonshot.ai" },
  { key: "llama", name: "Llama", provider: "Together AI", color: "#0467DF", placeholder: "...", helpUrl: "https://api.together.xyz/settings/api-keys" },
  { key: "glm", name: "GLM", provider: "Zhipu AI", color: "#3D5AFE", placeholder: "...", helpUrl: "https://open.bigmodel.cn" },
  { key: "cursor", name: "Cursor", provider: "OpenRouter", color: "#00E5A0", placeholder: "Enter API key", helpUrl: "https://openrouter.ai/keys" },
  { key: "notebooklm", name: "NotebookLM", provider: "OpenRouter", color: "#FBBC04", placeholder: "Enter API key", helpUrl: "https://openrouter.ai/keys" },
  { key: "copilot", name: "GitHub Copilot", provider: "OpenRouter", color: "#171515", placeholder: "Enter API key", helpUrl: "https://openrouter.ai/keys" },
];

const TIMEZONE_OPTIONS = [
  "America/New_York","America/Chicago","America/Denver","America/Los_Angeles","America/Anchorage","Pacific/Honolulu",
  "Europe/London","Europe/Paris","Europe/Berlin","Europe/Moscow",
  "Asia/Dubai","Asia/Kolkata","Asia/Shanghai","Asia/Tokyo","Asia/Seoul",
  "Australia/Sydney","Pacific/Auckland","UTC"
];

// Debug Log Modal Component
const DebugLogModal = ({ isOpen, onClose, debugData, agentName }) => {
  const [expandedSections, setExpandedSections] = useState({ response: true, headers: false });
  
  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard");
  };

  const toggleSection = (section) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  if (!debugData) return null;

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="bg-zinc-900 border-zinc-800 max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-zinc-100 flex items-center gap-2">
            <Bug className="w-5 h-5 text-amber-400" />
            Debug Logs - {agentName}
          </DialogTitle>
        </DialogHeader>
        
        <div className="flex-1 overflow-y-auto space-y-4 pr-2">
          {/* Summary */}
          <div className="p-3 rounded-lg bg-zinc-950 border border-zinc-800">
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <span className="text-zinc-500">Timestamp:</span>
                <span className="ml-2 text-zinc-300 font-mono">{debugData.timestamp || "N/A"}</span>
              </div>
              <div>
                <span className="text-zinc-500">Status:</span>
                <span className={`ml-2 font-mono ${debugData.response_status === 200 ? 'text-emerald-400' : 'text-red-400'}`}>
                  {debugData.response_status || "N/A"}
                </span>
              </div>
              <div>
                <span className="text-zinc-500">Model:</span>
                <span className="ml-2 text-zinc-300 font-mono">{debugData.model || "N/A"}</span>
              </div>
              <div>
                <span className="text-zinc-500">Error Type:</span>
                <span className="ml-2 text-amber-400 font-mono">{debugData.error_type || "None"}</span>
              </div>
            </div>
          </div>

          {/* Endpoint */}
          <div className="p-3 rounded-lg bg-zinc-950 border border-zinc-800">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-zinc-500 uppercase tracking-wider">API Endpoint</span>
              <button onClick={() => copyToClipboard(debugData.endpoint)} className="text-zinc-500 hover:text-zinc-300">
                <Copy className="w-3.5 h-3.5" />
              </button>
            </div>
            <code className="text-xs text-zinc-300 font-mono break-all">{debugData.endpoint || "N/A"}</code>
          </div>

          {/* Error Message */}
          {debugData.error_message && (
            <div className="p-3 rounded-lg bg-red-950/30 border border-red-900/50">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-red-400 uppercase tracking-wider">Error Message</span>
                <button onClick={() => copyToClipboard(debugData.error_message)} className="text-red-400 hover:text-red-300">
                  <Copy className="w-3.5 h-3.5" />
                </button>
              </div>
              <code className="text-xs text-red-300 font-mono break-all">{debugData.error_message}</code>
            </div>
          )}

          {/* Response Body */}
          {debugData.response_body && (
            <div className="rounded-lg bg-zinc-950 border border-zinc-800 overflow-hidden">
              <button 
                onClick={() => toggleSection('response')}
                className="w-full p-3 flex items-center justify-between text-left hover:bg-zinc-800/50"
              >
                <span className="text-xs text-zinc-500 uppercase tracking-wider">Response Body</span>
                {expandedSections.response ? <ChevronUp className="w-4 h-4 text-zinc-500" /> : <ChevronDown className="w-4 h-4 text-zinc-500" />}
              </button>
              {expandedSections.response && (
                <div className="p-3 pt-0 border-t border-zinc-800">
                  <div className="flex justify-end mb-1">
                    <button onClick={() => copyToClipboard(debugData.response_body)} className="text-zinc-500 hover:text-zinc-300">
                      <Copy className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <pre className="text-xs text-zinc-400 font-mono whitespace-pre-wrap break-all max-h-48 overflow-y-auto bg-zinc-900 p-2 rounded">
                    {debugData.response_body}
                  </pre>
                </div>
              )}
            </div>
          )}

          {/* Response Headers */}
          {debugData.response_headers && (
            <div className="rounded-lg bg-zinc-950 border border-zinc-800 overflow-hidden">
              <button 
                onClick={() => toggleSection('headers')}
                className="w-full p-3 flex items-center justify-between text-left hover:bg-zinc-800/50"
              >
                <span className="text-xs text-zinc-500 uppercase tracking-wider">Response Headers</span>
                {expandedSections.headers ? <ChevronUp className="w-4 h-4 text-zinc-500" /> : <ChevronDown className="w-4 h-4 text-zinc-500" />}
              </button>
              {expandedSections.headers && (
                <div className="p-3 pt-0 border-t border-zinc-800">
                  <pre className="text-xs text-zinc-400 font-mono whitespace-pre-wrap break-all max-h-32 overflow-y-auto bg-zinc-900 p-2 rounded">
                    {JSON.stringify(debugData.response_headers, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

// Theme Selector Component
function ThemeSelector() {
  // Scope theme to current user via user_id in the key
  const getUserThemeKey = () => {
    try {
      const stored = sessionStorage.getItem("nexus_user");
      if (stored) {
        const user = JSON.parse(stored);
        return `nexus_theme_${user.user_id}`;
      }
    } catch (_) {}
    return "nexus_theme";
  };

  const [theme, setTheme] = useState(() => {
    const key = getUserThemeKey();
    return localStorage.getItem(key) || localStorage.getItem("nexus_theme") || "dark";
  });

  const applyTheme = (newTheme) => {
    setTheme(newTheme);
    const key = getUserThemeKey();
    localStorage.setItem(key, newTheme);
    // Also set the generic key for App.js initial load
    localStorage.setItem("nexus_theme", newTheme);
    const root = document.documentElement;
    // Clear all theme classes
    root.className = root.className.replace(/theme-\S+/g, "").trim();
    root.classList.remove("light", "dark");

    const natureThemes = ["beach", "forest", "desert", "river", "mountain", "sunset", "aurora", "tropical", "arctic", "volcano", "cherry-blossom", "lavender", "midnight", "coral-reef", "savanna", "bamboo", "glacier", "autumn", "nebula", "rainforest"];
    if (newTheme === "light") {
      root.classList.add("light");
    } else if (newTheme === "system") {
      root.classList.add(window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    } else if (natureThemes.includes(newTheme)) {
      root.classList.add("dark");
      root.classList.add(`theme-${newTheme}`);
    } else {
      root.classList.add("dark");
    }
    api.put("/user/preferences", { theme: newTheme }).catch(() => {});
    toast.success(`Theme: ${newTheme.charAt(0).toUpperCase() + newTheme.slice(1)}`);
  };

  const themes = [
    { key: "dark", label: "Dark", desc: "Default dark", preview: "bg-zinc-900" },
    { key: "light", label: "Light", desc: "Light mode", preview: "bg-white" },
    { key: "system", label: "System", desc: "Match OS", preview: "bg-gradient-to-r from-zinc-900 to-white" },
  ];
  const natureThemes = [
    { key: "beach", label: "Beach", desc: "Ocean blues & golden sand", img: "/themes/claude.png" },
    { key: "forest", label: "Forest", desc: "Deep greens & earth tones", img: "/themes/forest.png" },
    { key: "desert", label: "Desert", desc: "Warm amber & terracotta", img: "/themes/desert.png" },
    { key: "river", label: "River", desc: "Cool blues & flowing water", img: "/themes/river.png" },
    { key: "mountain", label: "Mountain", desc: "Misty purples & stone", img: "/themes/mountain.png" },
    { key: "sunset", label: "Sunset", desc: "Warm pinks & deep magentas", img: "/themes/sunset.png" },
    { key: "aurora", label: "Aurora", desc: "Northern lights & teal glow", img: "/themes/aurora.png" },
    { key: "tropical", label: "Tropical", desc: "Crystal lagoon & palm trees", img: "/themes/tropical.png" },
    { key: "arctic", label: "Arctic", desc: "Aurora borealis & frozen tundra", img: "/themes/arctic.png" },
    { key: "volcano", label: "Volcano", desc: "Flowing lava & night fire", img: "/themes/volcano.png" },
    { key: "cherry-blossom", label: "Cherry Blossom", desc: "Pink sakura & zen garden", img: "/themes/cherry-blossom.png" },
    { key: "lavender", label: "Lavender", desc: "Purple fields at sunset", img: "/themes/lavender.png" },
    { key: "midnight", label: "Midnight", desc: "Neon city & moonlit sky", img: "/themes/midnight.png" },
    { key: "coral-reef", label: "Coral Reef", desc: "Underwater paradise", img: "/themes/coral-reef.png" },
    { key: "savanna", label: "Savanna", desc: "Golden sunset & acacia trees", img: "/themes/savanna.png" },
    { key: "bamboo", label: "Bamboo", desc: "Zen forest path", img: "/themes/bamboo.png" },
    { key: "glacier", label: "Glacier", desc: "Ice blue formations", img: "/themes/glacier.png" },
    { key: "autumn", label: "Autumn", desc: "Red & gold forest", img: "/themes/autumn.png" },
    { key: "nebula", label: "Nebula", desc: "Cosmic clouds & stars", img: "/themes/nebula.png" },
    { key: "rainforest", label: "Rainforest", desc: "Lush canopy & waterfalls", img: "/themes/rainforest.png" },
  ];

  return (
    <div className="p-6 rounded-xl bg-zinc-900/40 border border-zinc-800/60 space-y-4" data-testid="theme-selector">
      <div>
        <h3 className="text-sm font-semibold text-zinc-300 mb-1">Theme</h3>
        <p className="text-sm text-zinc-500 mb-3">Choose your visual experience</p>
        <div className="flex gap-3 mb-4">
          {themes.map(t => (
            <button key={t.key} onClick={() => applyTheme(t.key)}
              className={`flex-1 p-3 rounded-lg border-2 text-center transition-all ${
                theme === t.key ? "border-emerald-500/50 bg-zinc-800" : "border-zinc-800 bg-zinc-800/30 hover:border-zinc-700"
              }`} data-testid={`theme-${t.key}`}>
              <div className={`w-full h-6 rounded mb-2 ${t.preview}`} />
              <span className={`text-xs font-medium ${theme === t.key ? "text-zinc-200" : "text-zinc-500"}`}>{t.label}</span>
            </button>
          ))}
        </div>
      </div>
      <div>
        <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">Nature & Photo Themes ({natureThemes.length})</h4>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 gap-2">
          {natureThemes.map(t => (
            <button key={t.key} onClick={() => applyTheme(t.key)}
              className={`rounded-lg border-2 overflow-hidden text-center transition-all ${
                theme === t.key ? "border-cyan-500/50 ring-1 ring-cyan-500/30" : "border-zinc-800/60 hover:border-zinc-700"
              }`} data-testid={`theme-${t.key}`}>
              <div className="w-full h-16 bg-zinc-800 relative">
                <img src={t.img} alt={t.label} className="w-full h-full object-cover" loading="lazy" />
                {theme === t.key && <div className="absolute inset-0 bg-cyan-500/20 flex items-center justify-center"><span className="text-white text-sm font-bold bg-black/40 rounded-full w-5 h-5 flex items-center justify-center">✓</span></div>}
              </div>
              <div className="py-1.5 px-1">
                <span className={`text-[10px] font-medium ${theme === t.key ? "text-zinc-200" : "text-zinc-400"}`}>{t.label}</span>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// Workspace Admin Settings Component
function WorkspaceAdminSettings() {
  const [workspaces, setWorkspaces] = useState([]);
  const [selectedWs, setSelectedWs] = useState("");
  const [settings, setSettings] = useState(null);
  const [maxRounds, setMaxRounds] = useState(10);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/workspaces").then(r => {
      const ws = r.data || [];
      setWorkspaces(ws);
      if (ws.length > 0) {
        setSelectedWs(ws[0].workspace_id);
      }
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedWs) return;
    api.get(`/workspaces/${selectedWs}/settings`).then(r => {
      setSettings(r.data);
      setMaxRounds(r.data?.auto_collab_max_rounds || 10);
    }).catch(() => {});
  }, [selectedWs]);

  const saveSettings = async () => {
    setSaving(true);
    try {
      const res = await api.put(`/workspaces/${selectedWs}/settings`, { auto_collab_max_rounds: maxRounds });
      setSettings(res.data);
      toast.success(`Auto-collab rounds set to ${res.data.auto_collab_max_rounds}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to save settings");
    }
    setSaving(false);
  };

  if (workspaces.length === 0) return null;

  return (
    <div className="p-6 rounded-xl bg-zinc-900/40 border border-zinc-800/60" data-testid="workspace-admin-settings">
      <h3 className="text-sm font-semibold text-zinc-300 mb-1">Workspace Settings</h3>
      <p className="text-sm text-zinc-500 mb-4">Admin configuration for your workspaces.</p>
      {workspaces.length > 1 && (
        <select value={selectedWs} onChange={(e) => setSelectedWs(e.target.value)}
          className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200 mb-4" data-testid="ws-settings-select">
          {workspaces.map(ws => <option key={ws.workspace_id} value={ws.workspace_id}>{ws.name}</option>)}
        </select>
      )}
      {workspaces.length === 1 && <p className="text-xs text-zinc-400 mb-4">{workspaces[0].name}</p>}
      <div className="space-y-4">
        <div>
          <label className="text-xs text-zinc-400 mb-2 block">Auto-Collaboration Max Rounds (5 - 50)</label>
          <div className="flex items-center gap-3">
            <input type="range" min={5} max={50} step={1} value={maxRounds} onChange={(e) => setMaxRounds(Number(e.target.value))}
              className="flex-1 accent-emerald-500 h-2" data-testid="max-rounds-slider" />
            <span className="text-lg font-bold text-zinc-200 w-10 text-center" data-testid="max-rounds-value">{maxRounds}</span>
          </div>
          <p className="text-[10px] text-zinc-600 mt-1">Controls how many rounds AI agents collaborate automatically before stopping.</p>
        </div>
        <Button onClick={saveSettings} disabled={saving} size="sm" className="bg-zinc-100 text-zinc-900 hover:bg-zinc-200" data-testid="save-ws-settings-btn">
          {saving ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Save className="w-3 h-3 mr-1" />}
          Save Settings
        </Button>
      </div>
    </div>
  );
}

export default function SettingsPage({ user }) {
  const navigate = useNavigate();
  const { t } = useLanguage();
  const { confirm: confirmAction, ConfirmDialog: ConfirmDlg } = useConfirm();
  const [keys, setKeys] = useState({});
  const [inputs, setInputs] = useState({});
  const [showKeys, setShowKeys] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState({});
  const [testing, setTesting] = useState({});
  const [testResults, setTestResults] = useState({});
  const [testingAll, setTestingAll] = useState(false);
  const [debugModal, setDebugModal] = useState({ open: false, agent: null, data: null });

  useEffect(() => {
    fetchKeys();
  }, []);

  const fetchKeys = async () => {
    try {
      const res = await api.get("/settings/ai-keys");
      setKeys(res.data);
    } catch (err) { handleSilent(err, "SettingsPage:op1"); }
    setLoading(false);
  };

  const testAllKeys = async () => {
    const configuredCount = Object.values(keys).filter(k => k?.configured).length;
    if (configuredCount === 0) {
      toast.error("No API keys configured to test");
      return;
    }
    
    setTestingAll(true);
    setTestResults({});
    
    try {
      const res = await api.post("/settings/ai-keys/test-all");
      const { results, summary } = res.data;
      
      // Update test results for all agents
      setTestResults(results);
      
      // Show summary toast
      if (summary.failed === 0 && summary.passed > 0) {
        toast.success(`All ${summary.passed} keys are valid!`);
      } else if (summary.passed > 0 && summary.failed > 0) {
        toast.warning(`${summary.passed} valid, ${summary.failed} invalid`);
      } else if (summary.failed > 0) {
        toast.error(`${summary.failed} key(s) failed validation`);
      }
    } catch (err) {
      toast.error("Failed to test keys");
    }
    setTestingAll(false);
  };

  const testKey = async (agent, keyValue) => {
    const key = keyValue || inputs[agent];
    if (!key) {
      toast.error("Please enter an API key first");
      return;
    }
    
    setTesting(prev => ({ ...prev, [agent]: true }));
    setTestResults(prev => ({ ...prev, [agent]: null }));
    
    try {
      const res = await api.post("/settings/ai-keys/test", { agent, api_key: key });
      setTestResults(prev => ({ ...prev, [agent]: res.data }));
      if (res.data.success) {
        toast.success(`${AI_AGENTS.find(a => a.key === agent)?.name} key is valid!`);
      } else {
        toast.error(res.data.error || "Key validation failed");
      }
    } catch (err) {
      const errorMsg = err.response?.data?.detail || "Connection test failed";
      setTestResults(prev => ({ ...prev, [agent]: { success: false, error: errorMsg } }));
      toast.error(errorMsg);
    }
    setTesting(prev => ({ ...prev, [agent]: false }));
  };

  const saveKey = async (agent) => {
    const value = inputs[agent];
    if (!value) return;
    setSaving(prev => ({ ...prev, [agent]: true }));
    try {
      const payload = { [agent]: value };
      const res = await api.post("/settings/ai-keys", payload);
      setKeys(res.data);
      setInputs(prev => ({ ...prev, [agent]: "" }));
      setTestResults(prev => ({ ...prev, [agent]: null }));
      toast.success(`${AI_AGENTS.find(a => a.key === agent)?.name} key saved`);
    } catch (err) {
      toast.error("Failed to save key");
    }
    setSaving(prev => ({ ...prev, [agent]: false }));
  };

  const removeKey = async (agent) => {
    try {
      await api.delete(`/settings/ai-keys/${agent}`);
      setKeys(prev => ({ ...prev, [agent]: { configured: false, masked_key: null } }));
      setTestResults(prev => ({ ...prev, [agent]: null }));
      toast.success("Key removed");
    } catch (err) {
      toast.error("Failed to remove key");
    }
  };

  const [activeSection, setActiveSection] = useState(() => new URLSearchParams(window.location.search).get("tab") || "ai-keys");

  const NAV_ITEMS = [
    { type: "label", text: "AI Configuration" },
    { key: "ai-keys", label: "AI Keys", icon: Key, desc: "Your provider API keys" },
    { key: "nexus-keys", label: "Nexus AI", icon: Zap, desc: "Platform-managed keys & budgets" },
    { key: "ai-billing", label: "AI Billing", icon: BarChart3, desc: "Usage & cost tracking" },
    { type: "label", text: "Integrations" },
    { key: "integrations", label: "Integrations", icon: Puzzle, desc: "Cloud, social & services" },
    { type: "label", text: "Account" },
    { key: "profile", label: "Profile", icon: User, desc: "Name, avatar & security" },
    { key: "preferences", label: "Preferences", icon: Palette, desc: "Theme, language & display" },
  ];

  return (
    <div className="h-screen flex bg-[#09090b]" data-testid="settings-page">
      {/* Left Sidebar with Settings Nav */}
      <aside className="w-56 flex-shrink-0 bg-zinc-900/50 border-r border-zinc-800/40 flex flex-col h-screen sticky top-0">
        <div className="px-4 py-4 border-b border-zinc-800/40">
          <div className="flex items-center gap-2.5">
            <img src="/logo.png" alt="Nexus Cloud" className="w-8 h-8 rounded-lg" />
            <span className="font-bold text-sm tracking-tight text-zinc-100" style={{ fontFamily: 'Syne, sans-serif' }}>NEXUS <span className="text-cyan-400">CLOUD</span></span>
          </div>
        </div>
        <div className="px-3 py-3 space-y-0.5">
          <button onClick={() => navigate("/dashboard")} className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50"><ArrowLeft className="w-4 h-4" />Dashboard</button>
          <div className="h-px bg-zinc-800/40 my-2" />
        </div>

        {/* Settings Sub-Navigation */}
        <nav className="flex-1 overflow-y-auto px-3 space-y-0.5">
          {NAV_ITEMS.map((item, i) => {
            if (item.type === "label") {
              return <p key={`label-${item.text}`} className="text-[10px] font-semibold text-zinc-600 uppercase tracking-wider px-3 pt-4 pb-1">{item.text}</p>;
            }
            const Icon = item.icon;
            return (
              <button
                key={item.key}
                onClick={() => setActiveSection(item.key)}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                  activeSection === item.key
                    ? "bg-zinc-800 text-zinc-100 font-medium"
                    : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50"
                }`}
                data-testid={`settings-nav-${item.key}`}
              >
                <Icon className="w-4 h-4 flex-shrink-0" />
                <div className="text-left min-w-0">
                  <span className="block truncate">{item.label}</span>
                </div>
              </button>
            );
          })}
        </nav>

        <div className="border-t border-zinc-800/40 px-3 py-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-indigo-500 flex items-center justify-center text-xs font-bold text-white">{user?.name?.[0] || "U"}</div>
            <div className="min-w-0 flex-1"><p className="text-xs font-medium text-zinc-300 truncate">{user?.name}</p><p className="text-[10px] text-zinc-600 truncate">{user?.email}</p></div>
          </div>
        </div>
      </aside>

      <GlobalHeader user={user} title="Settings" />
      <main className="flex-1 overflow-y-auto h-screen">
        <div className="max-w-3xl mx-auto px-6 sm:px-10 py-8">
        <h1 className="text-2xl font-bold tracking-tight text-zinc-100 mb-1" style={{ fontFamily: 'Syne, sans-serif' }}>
          {NAV_ITEMS.find(i => i.key === activeSection)?.label || "Settings"}
        </h1>
        <p className="text-zinc-500 text-sm mb-8">
          {NAV_ITEMS.find(i => i.key === activeSection)?.desc || "Manage your account and AI connections."}
        </p>

        {/* AI Keys Section */}
        {activeSection === "ai-keys" && (
            <div className="space-y-3" data-testid="ai-keys-section">
              <div className="p-4 rounded-xl bg-zinc-900/30 border border-zinc-800/40 mb-6 flex items-start justify-between gap-4">
                <p className="text-sm text-zinc-400 flex-1">
                  Connect your own AI API keys to use in projects. Keys are encrypted and stored securely.
                  Use <span className="text-emerald-400 font-medium">Test Connection</span> to verify keys before saving.
                  All AI models require your own API key to function.
                </p>
                <Button
                  onClick={testAllKeys}
                  disabled={testingAll || Object.values(keys).filter(k => k?.configured).length === 0}
                  size="sm"
                  variant="outline"
                  className="border-emerald-700 text-emerald-400 hover:bg-emerald-900/30 flex-shrink-0 whitespace-nowrap"
                  data-testid="test-all-keys-btn"
                >
                  {testingAll ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                      Testing...
                    </>
                  ) : (
                    <>
                      <Play className="w-3.5 h-3.5 mr-1.5" />
                      Test All Keys
                    </>
                  )}
                </Button>
              </div>

              <div className="grid gap-3">
                {AI_AGENTS.map((agent) => {
                  const keyInfo = keys[agent.key] || {};
                  const testResult = testResults[agent.key];
                  const isTestingThis = testing[agent.key];
                  const isSavingThis = saving[agent.key];
                  
                  return (
                    <div key={agent.key}
                      className="p-4 rounded-xl bg-zinc-900/40 border border-zinc-800/60 hover:border-zinc-700 transition-colors"
                      data-testid={`ai-key-card-${agent.key}`}
                    >
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold"
                            style={{ backgroundColor: agent.color, color: ['#F5F5F5', '#FF7000', '#F55036'].includes(agent.color) ? '#09090b' : '#fff' }}>
                            {agent.name.slice(0, 2)}
                          </div>
                          <div>
                            <span className="text-sm font-semibold text-zinc-200">{agent.name}</span>
                            <span className="text-xs text-zinc-600 ml-2">by {agent.provider}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {testResult && (
                            <Badge className={testResult.success ? "bg-emerald-500/20 text-emerald-400 text-[10px]" : "bg-red-500/20 text-red-400 text-[10px]"}>
                              {testResult.success ? <CheckCircle className="w-3 h-3 mr-1" /> : <XCircle className="w-3 h-3 mr-1" />}
                              {testResult.success ? "Valid" : "Invalid"}
                            </Badge>
                          )}
                          {keyInfo.configured ? (
                            <Badge className="bg-emerald-500/20 text-emerald-400 text-[10px]">
                              <Check className="w-3 h-3 mr-1" /> Connected
                            </Badge>
                          ) : (
                            <Badge className="bg-zinc-800 text-zinc-500 text-[10px]">Not connected</Badge>
                          )}
                        </div>
                      </div>

                      {keyInfo.configured ? (
                        <div className="flex items-center gap-2">
                          <div className="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm font-mono text-zinc-400">
                            {showKeys[agent.key] ? keyInfo.masked_key : "••••••••••••"}
                          </div>
                          {testResult?.debug && (
                            <button 
                              onClick={() => setDebugModal({ open: true, agent: agent.name, data: testResult.debug })}
                              className="text-amber-500 hover:text-amber-400 p-2"
                              title="View debug logs"
                              data-testid={`debug-btn-${agent.key}`}
                            >
                              <Bug className="w-4 h-4" />
                            </button>
                          )}
                          <button onClick={() => setShowKeys(p => ({ ...p, [agent.key]: !p[agent.key] }))}
                            className="text-zinc-500 hover:text-zinc-300 p-2">
                            {showKeys[agent.key] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          </button>
                          <button onClick={() => removeKey(agent.key)}
                            className="text-zinc-500 hover:text-red-400 p-2" data-testid={`remove-key-${agent.key}`}>
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      ) : keyInfo.error ? (
                        <div className="space-y-2">
                          <p className="text-xs text-amber-400">{keyInfo.error}</p>
                          <div className="flex items-center gap-2">
                            <Input
                              type="password"
                              placeholder={agent.placeholder}
                              value={inputs[agent.key] || ""}
                              onChange={(e) => setInputs(p => ({ ...p, [agent.key]: e.target.value }))}
                              onKeyDown={(e) => e.key === 'Enter' && saveKey(agent.key)}
                              className="bg-zinc-950 border-zinc-800 placeholder:text-zinc-700 font-mono text-sm flex-1"
                            />
                            <Button onClick={() => saveKey(agent.key)} disabled={!inputs[agent.key] || isSavingThis}
                              size="sm" className="bg-zinc-100 text-zinc-900 hover:bg-zinc-200 flex-shrink-0">
                              {isSavingThis ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2">
                          <Input
                            type="password"
                            placeholder={agent.placeholder}
                            value={inputs[agent.key] || ""}
                            onChange={(e) => setInputs(p => ({ ...p, [agent.key]: e.target.value }))}
                            onKeyDown={(e) => e.key === 'Enter' && saveKey(agent.key)}
                            className="bg-zinc-950 border-zinc-800 placeholder:text-zinc-700 font-mono text-sm flex-1"
                            data-testid={`key-input-${agent.key}`}
                          />
                          <Button 
                            onClick={() => testKey(agent.key)} 
                            disabled={!inputs[agent.key] || isTestingThis}
                            size="sm" 
                            variant="outline"
                            className="border-emerald-700 text-emerald-400 hover:bg-emerald-900/30 flex-shrink-0"
                            data-testid={`test-key-${agent.key}`}
                          >
                            {isTestingThis ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                            <span className="ml-1 hidden sm:inline">Test</span>
                          </Button>
                          {testResult?.debug && (
                            <Button 
                              onClick={() => setDebugModal({ open: true, agent: agent.name, data: testResult.debug })}
                              size="sm" 
                              variant="outline"
                              className="border-amber-700 text-amber-400 hover:bg-amber-900/30 flex-shrink-0"
                              data-testid={`debug-key-${agent.key}`}
                            >
                              <Bug className="w-3.5 h-3.5" />
                              <span className="ml-1 hidden sm:inline">Debug</span>
                            </Button>
                          )}
                          <Button 
                            onClick={() => saveKey(agent.key)} 
                            disabled={!inputs[agent.key] || isSavingThis}
                            size="sm" 
                            className="bg-zinc-100 text-zinc-900 hover:bg-zinc-200 flex-shrink-0"
                            data-testid={`save-key-${agent.key}`}
                          >
                            {isSavingThis ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                          </Button>
                          <a href={agent.helpUrl} target="_blank" rel="noopener noreferrer"
                            className="text-xs text-blue-400 hover:text-blue-300 underline underline-offset-2 whitespace-nowrap flex-shrink-0"
                            data-testid={`get-key-${agent.key}`}>Get key</a>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}


          {activeSection === "integrations" && (
            <div className="space-y-6">
              <div className="p-6 rounded-xl bg-zinc-900/40 border border-zinc-800/60">
                <ModuleSettingsPanel workspaceId={user?.workspaces?.[0] || ""} />
              </div>
              <div className="p-6 rounded-xl bg-zinc-900/40 border border-zinc-800/60">
                <DesktopBridgePanel />
              </div>
              <div className="p-6 rounded-xl bg-zinc-900/40 border border-zinc-800/60">
                <OpenClawPanel workspaceId={user?.workspaces?.[0] || ""} />
              </div>
              <PlatformIntegrations />
              <div className="p-6 rounded-xl bg-zinc-900/40 border border-zinc-800/60">
                <SocialConnectionsPanel />
              </div>
              <CloudStorageConnections scope="user" />
            </div>
          )}

          {activeSection === "profile" && (
            <div className="space-y-6">
              <div className="p-6 rounded-xl bg-zinc-900/40 border border-zinc-800/60">
                <h3 className="text-sm font-semibold text-zinc-300 mb-4">Account Information</h3>
                <div className="flex items-center gap-4 mb-6">
                  {user?.picture ? (
                    <img src={user.picture} alt="" className="w-14 h-14 rounded-full" />
                  ) : (
                    <div className="w-14 h-14 rounded-full bg-zinc-800 flex items-center justify-center text-lg font-bold text-zinc-300">
                      {user?.name?.[0]}
                    </div>
                  )}
                  <div>
                    <h3 className="text-lg font-semibold text-zinc-200">{user?.name}</h3>
                    <p className="text-sm text-zinc-500">{user?.email}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 flex-wrap">
                  <Badge className="bg-zinc-800 text-zinc-300" data-testid="plan-badge">{(user?.plan || "free").toUpperCase()} Plan</Badge>
                  {user?.platform_role && (
                    <Badge 
                      className={
                        user.platform_role === "super_admin" ? "bg-red-500/20 text-red-400" :
                        user.platform_role === "admin" ? "bg-amber-500/20 text-amber-400" :
                        user.platform_role === "moderator" ? "bg-blue-500/20 text-blue-400" :
                        "bg-zinc-800 text-zinc-400"
                      }
                      data-testid="role-badge"
                    >
                      {user.platform_role === "super_admin" ? "Super Admin" :
                       user.platform_role === "admin" ? "Admin" :
                       user.platform_role === "moderator" ? "Moderator" : "User"}
                    </Badge>
                  )}
                  <Button variant="outline" size="sm" onClick={() => navigate("/billing")}
                    className="border-zinc-700 text-zinc-400 text-xs" data-testid="goto-billing">
                    <CreditCard className="w-3 h-3 mr-1" /> Manage Billing
                  </Button>
                </div>
              </div>
              <div className="p-6 rounded-xl bg-zinc-900/40 border border-zinc-800/60">
                <h3 className="text-sm font-semibold text-zinc-300 mb-3">Account Details</h3>
                <div className="space-y-4">
                  <div>
                    <label className="text-xs text-zinc-500 block mb-1.5">Display Name</label>
                    <div className="flex items-center gap-2">
                      <Input
                        defaultValue={user?.name || ""}
                        className="bg-zinc-800 border-zinc-700 text-zinc-200 text-sm max-w-xs"
                        data-testid="edit-display-name"
                        onBlur={async (e) => {
                          const newName = e.target.value.trim();
                          if (newName && newName !== user?.name) {
                            try {
                              await api.put("/auth/profile", { name: newName });
                              toast.success("Name updated");
                            } catch (err) { toast.error("Failed to update name"); }
                          }
                        }}
                      />
                    </div>
                  </div>
                  <div><label className="text-xs text-zinc-500 block mb-1">Email</label><p className="text-sm text-zinc-300">{user?.email}</p></div>
                  <div><label className="text-xs text-zinc-500 block mb-1">Auth Method</label><p className="text-sm text-zinc-400">{user?.auth_type === "google" ? "Google OAuth" : "Email / Password"}</p></div>
                  <div>
                    <label className="text-xs text-zinc-500 block mb-1.5">Avatar</label>
                    <div className="flex items-center gap-3">
                      {user?.picture ? (
                        <img src={user.picture} alt="" className="w-10 h-10 rounded-full" />
                      ) : (
                        <div className="w-10 h-10 rounded-full bg-zinc-800 flex items-center justify-center text-sm font-bold text-zinc-300">{user?.name?.[0]}</div>
                      )}
                      <label className="cursor-pointer">
                        <span className="text-xs text-cyan-400 hover:text-cyan-300 transition-colors">Upload new avatar</span>
                        <input type="file" accept="image/*" className="hidden" data-testid="avatar-upload"
                          onChange={async (e) => {
                            const file = e.target.files?.[0];
                            if (!file) return;
                            if (file.size > 2 * 1024 * 1024) { toast.error("Avatar must be under 2MB"); return; }
                            const reader = new FileReader();
                            reader.onload = async () => {
                              try {
                                await api.put("/auth/profile", { picture: reader.result });
                                toast.success("Avatar updated — refresh to see changes");
                              } catch { toast.error("Failed to upload avatar"); }
                            };
                            reader.readAsDataURL(file);
                          }}
                        />
                      </label>
                    </div>
                  </div>
                  <div>
                    <label className="text-xs text-zinc-500 block mb-1.5">Timezone</label>
                    <Select
                      defaultValue={user?.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone}
                      onValueChange={async (value) => {
                        try {
                          await api.put("/auth/profile", { timezone: value });
                          toast.success("Timezone updated");
                        } catch { toast.error("Failed to update timezone"); }
                      }}
                    >
                      <SelectTrigger className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 max-w-xs focus:outline-none focus:border-zinc-500" data-testid="timezone-select">
                        <SelectValue placeholder="Select timezone" />
                      </SelectTrigger>
                      <SelectContent className="bg-zinc-900 border-zinc-800 text-zinc-200">
                        {TIMEZONE_OPTIONS.map((tz) => (
                          <SelectItem key={tz} value={tz}>{tz.replace(/_/g, " ")}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div><label className="text-xs text-zinc-500 block mb-1">Member Since</label><p className="text-sm text-zinc-400">{user?.created_at ? new Date(user.created_at).toLocaleDateString() : "N/A"}</p></div>
                  {user?.tos_version && <div><label className="text-xs text-zinc-500 block mb-1">Terms of Service</label><p className="text-sm text-zinc-400">Accepted v{user.tos_version} {user.tos_accepted_at ? `on ${new Date(user.tos_accepted_at).toLocaleDateString()}` : ""}</p></div>}
                </div>
              </div>
              <MFASetup />
              {/* GDPR: Data Export & Deletion */}
              <div className="p-6 rounded-xl bg-zinc-900/40 border border-zinc-800/60">
                <h3 className="text-sm font-semibold text-zinc-300 mb-3">Data & Privacy</h3>
                <div className="space-y-3">
                  <div>
                    <p className="text-sm text-zinc-500 mb-2">Export all your data including messages, files, tasks, and settings.</p>
                    <Button size="sm" variant="outline" className="border-zinc-700 text-zinc-300" data-testid="export-data-btn"
                      onClick={async () => {
                        try {
                          const res = await api.post("/user/export-data", {}, { responseType: "blob" });
                          const url = window.URL.createObjectURL(new Blob([res.data]));
                          const a = document.createElement("a"); a.href = url; a.download = "nexus_data_export.zip"; a.click();
                          toast.success("Data export downloaded");
                        } catch (err) { toast.error("Export failed"); }
                      }}>
                      Export My Data
                    </Button>
                  </div>
                  <div className="pt-3 border-t border-zinc-800">
                    <p className="text-sm text-red-400/80 mb-2">Permanently delete your account and all data. This action has a 30-day grace period.</p>
                    <Button size="sm" variant="outline" className="border-red-500/30 text-red-400 hover:bg-red-500/10" data-testid="delete-account-btn"
                      onClick={async () => {
                        const ok = await confirmAction("Delete Account", "Are you sure? This will permanently remove all your data after a 30-day grace period. This cannot be undone."); if (!ok) return;
                        try {
                          await api.post("/user/delete-account", { confirm: true });
                          toast.success("Account deletion scheduled. You will be logged out.");
                          setTimeout(() => { window.location.href = "/"; }, 2000);
                        } catch (err) { toast.error(err.response?.data?.detail || "Deletion failed"); }
                      }}>
                      Delete My Account
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeSection === "preferences" && (
            <div className="space-y-6">
              <div className="p-6 rounded-xl bg-zinc-900/40 border border-zinc-800/60">
                <h3 className="text-sm font-semibold text-zinc-300 mb-1">{t("settingsPage.languagePreference")}</h3>
                <p className="text-sm text-zinc-500 mb-4">{t("settingsPage.languageDesc")}</p>
                <LanguageToggle />
              </div>
              <ThemeSelector />
              <WorkspaceAdminSettings />
              <div className="p-6 rounded-xl bg-zinc-900/40 border border-zinc-800/60">
                <h3 className="text-sm font-semibold text-zinc-300 mb-1">Keyboard Shortcuts</h3>
                <p className="text-sm text-zinc-500 mb-3">Quick reference for keyboard navigation.</p>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between"><span className="text-zinc-400">Send message</span><kbd className="bg-zinc-800 px-2 py-0.5 rounded text-zinc-300 font-mono">Ctrl+Enter</kbd></div>
                  <div className="flex justify-between"><span className="text-zinc-400">@mention agent</span><kbd className="bg-zinc-800 px-2 py-0.5 rounded text-zinc-300 font-mono">@ + name</kbd></div>
                  <div className="flex justify-between"><span className="text-zinc-400">Search tasks</span><kbd className="bg-zinc-800 px-2 py-0.5 rounded text-zinc-300 font-mono">in Project view</kbd></div>
                  <div className="flex justify-between"><span className="text-zinc-400">Undo</span><kbd className="bg-zinc-800 px-2 py-0.5 rounded text-zinc-300 font-mono">Ctrl+Z</kbd></div>
                  <div className="flex justify-between"><span className="text-zinc-400">Duplicate node</span><kbd className="bg-zinc-800 px-2 py-0.5 rounded text-zinc-300 font-mono">Ctrl+D</kbd></div>
                  <div className="flex justify-between"><span className="text-zinc-400">Shortcut palette</span><kbd className="bg-zinc-800 px-2 py-0.5 rounded text-zinc-300 font-mono">Ctrl+/</kbd></div>
                </div>
              </div>
              <div className="p-6 rounded-xl bg-zinc-900/40 border border-zinc-800/60">
                <h3 className="text-sm font-semibold text-zinc-300 mb-1">Notifications</h3>
                <p className="text-sm text-zinc-500 mb-3">Control which notifications you receive.</p>
                <div className="space-y-3">
                  <label className="flex items-center justify-between"><span className="text-xs text-zinc-400">AI collaboration completed</span><input type="checkbox" defaultChecked className="rounded border-zinc-600 bg-zinc-800" /></label>
                  <label className="flex items-center justify-between"><span className="text-xs text-zinc-400">Task assigned to me</span><input type="checkbox" defaultChecked className="rounded border-zinc-600 bg-zinc-800" /></label>
                  <label className="flex items-center justify-between"><span className="text-xs text-zinc-400">Workflow run completed</span><input type="checkbox" defaultChecked className="rounded border-zinc-600 bg-zinc-800" /></label>
                  <label className="flex items-center justify-between"><span className="text-xs text-zinc-400">Support ticket replies</span><input type="checkbox" defaultChecked className="rounded border-zinc-600 bg-zinc-800" /></label>
                  <label className="flex items-center justify-between"><span className="text-xs text-zinc-400">Weekly summary email</span><input type="checkbox" className="rounded border-zinc-600 bg-zinc-800" /></label>
                </div>
              </div>
            </div>
          )}

          {activeSection === "ai-billing" && (
            <AiBillingPanel />
          )}

          {activeSection === "nexus-keys" && (
            <ManagedKeysUser />
          )}

        
      </div>
      </main>
      <DebugLogModal 
        isOpen={debugModal.open} 
        onClose={() => setDebugModal({ open: false, agent: null, data: null })}
        debugData={debugModal.data}
        agentName={debugModal.agent}
      />
      <ConfirmDlg />
    </div>
  );
}


function AiBillingPanel() {
  const [billing, setBilling] = useState(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const res = await api.get(`/settings/ai-billing?days=${days}`);
        setBilling(res.data);
      } catch (err) { handleSilent(err, "SettingsPage:op2"); }
      setLoading(false);
    })();
  }, [days]);

  if (loading) return <div className="text-center py-8 text-zinc-500 text-sm">Loading billing data...</div>;
  if (!billing) return <div className="text-center py-8 text-zinc-600 text-sm">No billing data available</div>;

  return (
    <div className="space-y-4" data-testid="ai-billing-panel">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-zinc-200">AI Provider Billing</h3>
          <p className="text-xs text-zinc-500 mt-0.5">Estimated costs based on token usage (last {days} days)</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={days} onChange={(e) => setDays(Number(e.target.value))} className="bg-zinc-900 border border-zinc-800 rounded-md px-2 py-1 text-xs text-zinc-300">
            <option value={7}>7 days</option>
            <option value={30}>30 days</option>
            <option value={90}>90 days</option>
          </select>
          <div className="px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
            <span className="text-sm font-bold text-emerald-400">${billing.total_estimated_cost_usd}</span>
            <span className="text-[10px] text-zinc-500 ml-1">estimated total</span>
          </div>
        </div>
      </div>

      <div className="space-y-2">
        {billing.providers.map((p) => (
          <div key={p.provider} className={`p-4 rounded-xl border transition-colors ${p.has_key ? "bg-zinc-900/50 border-zinc-800/60" : "bg-zinc-900/20 border-zinc-800/30 opacity-60"}`} data-testid={`billing-provider-${p.provider}`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-zinc-800 flex items-center justify-center text-xs font-bold text-zinc-300">{p.name[0]}</div>
                <div>
                  <p className="text-sm font-medium text-zinc-200">{p.name}</p>
                  <p className="text-[10px] text-zinc-600">{p.agents.join(", ")}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                {p.has_key ? (
                  <span className="text-[9px] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">Key configured</span>
                ) : (
                  <span className="text-[9px] px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-500">No key</span>
                )}
                <a href={p.billing_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-[10px] text-blue-400 hover:text-blue-300">
                  Billing <ExternalLink className="w-2.5 h-2.5" />
                </a>
                <a href={p.keys_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-[10px] text-zinc-400 hover:text-zinc-300">
                  API Keys <ExternalLink className="w-2.5 h-2.5" />
                </a>
              </div>
            </div>
            {p.usage && (
              <div className="mt-3 grid grid-cols-4 gap-3">
                <div className="text-center">
                  <p className="text-lg font-bold text-zinc-200">{p.usage.total_tokens.toLocaleString()}</p>
                  <p className="text-[9px] text-zinc-600">Tokens</p>
                </div>
                <div className="text-center">
                  <p className="text-lg font-bold text-emerald-400">${p.usage.estimated_cost_usd}</p>
                  <p className="text-[9px] text-zinc-600">Est. Cost</p>
                </div>
                <div className="text-center">
                  <p className="text-lg font-bold text-zinc-300">{p.usage.events}</p>
                  <p className="text-[9px] text-zinc-600">Requests</p>
                </div>
                <div className="text-center">
                  <p className="text-lg font-bold text-red-400">{p.usage.errors}</p>
                  <p className="text-[9px] text-zinc-600">Errors</p>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
