import { useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  MessageSquare, Kanban, Bot, GitBranch, Code, Image, BarChart3, Shield,
  ChevronRight, ChevronLeft, Check, Sparkles, Rocket, Loader2
} from "lucide-react";

const ICONS = { "message-square": MessageSquare, kanban: Kanban, bot: Bot, "git-branch": GitBranch, code: Code, image: Image, "bar-chart-3": BarChart3, shield: Shield };

const PERSONAS = [
  { id: "solo_creator", name: "Solo Creator", desc: "Individual creators and freelancers", icon: Sparkles, modules: ["core", "plan_track"] },
  { id: "developer", name: "Developer", desc: "Software developers and engineers", icon: Code, modules: ["core", "build_code", "plan_track"] },
  { id: "content_team", name: "Content Team", desc: "Content and marketing teams", icon: Image, modules: ["core", "media_studio", "plan_track", "insights"] },
  { id: "ai_power_user", name: "AI Power User", desc: "AI enthusiasts and researchers", icon: Bot, modules: ["core", "agent_builder", "orchestration", "insights"] },
  { id: "engineering_team", name: "Engineering Team", desc: "Engineering and product teams", icon: GitBranch, modules: ["core", "build_code", "plan_track", "agent_builder", "insights"] },
  { id: "everything", name: "Everything", desc: "All modules", icon: Rocket, modules: ["core", "plan_track", "agent_builder", "orchestration", "build_code", "media_studio", "insights"] },
];

const AI_MODELS = [
  { key: "claude", name: "Claude" }, { key: "chatgpt", name: "ChatGPT" }, { key: "gemini", name: "Gemini" },
  { key: "deepseek", name: "DeepSeek" }, { key: "mistral", name: "Mistral" }, { key: "grok", name: "Grok" },
  { key: "cohere", name: "Cohere" }, { key: "perplexity", name: "Perplexity" }, { key: "groq", name: "Groq" },
  { key: "mercury", name: "Mercury" }, { key: "pi", name: "Pi" }, { key: "manus", name: "Manus" },
  { key: "qwen", name: "Qwen" }, { key: "kimi", name: "Kimi" }, { key: "llama", name: "Llama" },
  { key: "glm", name: "GLM" }, { key: "cursor", name: "Cursor" }, { key: "notebooklm", name: "NotebookLM" },
  { key: "copilot", name: "Copilot" },
];

export default function WorkspaceWizard({ workspaceId, registry, onComplete, onSkip }) {
  const [step, setStep] = useState(0);
  const [persona, setPersona] = useState("");
  const [modules, setModules] = useState({});
  const [aiModels, setAiModels] = useState(["claude", "chatgpt", "gemini"]);
  const [saving, setSaving] = useState(false);

  const selectPersona = (p) => {
    setPersona(p.id);
    const mods = {};
    Object.keys(registry).forEach(mid => { mods[mid] = p.modules.includes(mid); });
    setModules(mods);
  };

  const toggleModule = (mid) => {
    if (registry[mid]?.always_on) return;
    setModules(prev => ({ ...prev, [mid]: !prev[mid] }));
  };

  const toggleModel = (key) => {
    setAiModels(prev => prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]);
  };

  const enabledCount = Object.values(modules).filter(Boolean).length;
  const totalPrice = Object.entries(modules).reduce((sum, [mid, on]) => on ? sum + (registry[mid]?.monthly_price || 0) : sum, 0);

  const save = async () => {
    setSaving(true);
    try {
      await api.post(`/workspaces/${workspaceId}/modules/wizard`, { persona, modules, ai_models: aiModels });
      toast.success("Workspace configured!");
      onComplete?.();
    } catch (err) { toast.error(err?.response?.data?.detail || "Failed to save"); }
    setSaving(false);
  };

  const steps = [
    // Step 0: Persona
    <div key="persona" className="space-y-4">
      <h2 className="text-xl font-bold text-zinc-100 text-center">What are you building?</h2>
      <p className="text-sm text-zinc-400 text-center">Choose a starting point — you can customize everything next.</p>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 max-w-3xl mx-auto">
        {PERSONAS.map(p => {
          const Icon = p.icon;
          return (
            <button key={p.id} onClick={() => { selectPersona(p); setStep(1); }}
              className={`p-4 rounded-xl border text-left transition-all ${persona === p.id ? "bg-cyan-950/30 border-cyan-500/50" : "bg-zinc-900/50 border-zinc-800 hover:border-zinc-700"}`}>
              <Icon className="w-6 h-6 text-cyan-400 mb-2" />
              <div className="text-sm font-medium text-zinc-100">{p.name}</div>
              <div className="text-xs text-zinc-500 mt-1">{p.desc}</div>
            </button>
          );
        })}
      </div>
    </div>,

    // Step 1: Modules
    <div key="modules" className="space-y-4">
      <h2 className="text-xl font-bold text-zinc-100 text-center">Fine-tune your modules</h2>
      <p className="text-sm text-zinc-400 text-center">{enabledCount} modules enabled · ${totalPrice}/mo in add-ons</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-4xl mx-auto">
        {Object.entries(registry).map(([mid, mod]) => {
          const Icon = ICONS[mod.icon] || MessageSquare;
          const enabled = mod.always_on || modules[mid];
          return (
            <div key={mid} className={`p-3 rounded-lg border transition-all ${enabled ? "bg-zinc-900/70 border-zinc-700" : "bg-zinc-900/20 border-zinc-800/50 opacity-60"}`}>
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <Icon className="w-4 h-4 text-cyan-400" />
                  <span className="text-sm font-medium text-zinc-100">{mod.name}</span>
                  {mod.always_on && <Badge className="text-[8px] bg-zinc-700 text-zinc-300">Always On</Badge>}
                  {mod.monthly_price > 0 && <Badge className="text-[8px] bg-emerald-500/20 text-emerald-400">+${mod.monthly_price}/mo</Badge>}
                </div>
                {!mod.always_on && <Switch checked={!!modules[mid]} onCheckedChange={() => toggleModule(mid)} />}
              </div>
              <p className="text-xs text-zinc-500">{mod.description}</p>
              <div className="flex flex-wrap gap-1 mt-1.5">
                {(mod.nav_keys || []).slice(0, 6).map(k => <Badge key={k} variant="outline" className="text-[8px] border-zinc-700 py-0">{k}</Badge>)}
                {(mod.nav_keys || []).length > 6 && <Badge variant="outline" className="text-[8px] border-zinc-700 py-0">+{mod.nav_keys.length - 6}</Badge>}
              </div>
            </div>
          );
        })}
      </div>
    </div>,

    // Step 2: AI Models
    <div key="models" className="space-y-4">
      <h2 className="text-xl font-bold text-zinc-100 text-center">Pick your AI models</h2>
      <p className="text-sm text-zinc-400 text-center">{aiModels.length} selected</p>
      <div className="grid grid-cols-3 md:grid-cols-5 gap-2 max-w-3xl mx-auto">
        {AI_MODELS.map(m => (
          <button key={m.key} onClick={() => toggleModel(m.key)}
            className={`p-3 rounded-lg border text-center transition-all ${aiModels.includes(m.key) ? "bg-cyan-950/30 border-cyan-500/50" : "bg-zinc-900/50 border-zinc-800 hover:border-zinc-700"}`}>
            <div className="text-sm font-medium text-zinc-200">{m.name}</div>
            {aiModels.includes(m.key) && <Check className="w-3 h-3 text-cyan-400 mx-auto mt-1" />}
          </button>
        ))}
      </div>
    </div>,

    // Step 3: API Key Setup
    <div key="keys" className="space-y-4 max-w-3xl mx-auto">
      <h2 className="text-xl font-bold text-zinc-100 text-center">Set up your API keys</h2>
      <p className="text-sm text-zinc-400 text-center">Add API keys for your selected AI models. You can skip this and add them later in Settings.</p>
      <div className="space-y-2">
        {aiModels.map(modelKey => {
          const keyMap = { claude: "ANTHROPIC_API_KEY", chatgpt: "OPENAI_API_KEY", gemini: "GOOGLE_AI_KEY", deepseek: "DEEPSEEK_API_KEY", mistral: "MISTRAL_API_KEY", grok: "GROK_API_KEY", cohere: "COHERE_API_KEY", perplexity: "PERPLEXITY_API_KEY", groq: "GROQ_API_KEY" };
          const envVar = keyMap[modelKey];
          if (!envVar) return null;
          return (
            <div key={modelKey} className="flex items-center gap-3 p-3 bg-zinc-900 border border-zinc-800 rounded-lg">
              <span className="text-sm text-zinc-200 w-24">{modelKey}</span>
              <Input placeholder={`${envVar} (paste key here)`} className="bg-zinc-800 border-zinc-700 flex-1 text-xs font-mono" type="password" />
              <span className="text-[9px] text-zinc-600">optional</span>
            </div>
          );
        })}
      </div>
      <button onClick={() => setStep(step + 1)} className="text-sm text-cyan-400 hover:text-cyan-300 underline block mx-auto">Skip for now — I'll add keys later</button>
    </div>,

    // Step 4: Summary & Launch
    <div key="summary" className="space-y-4 max-w-2xl mx-auto">
      <h2 className="text-xl font-bold text-zinc-100 text-center">Ready to launch!</h2>
      <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800 space-y-3">
        <div className="flex justify-between text-sm"><span className="text-zinc-400">Persona</span><span className="text-zinc-200">{PERSONAS.find(p => p.id === persona)?.name || "Custom"}</span></div>
        <div className="flex justify-between text-sm"><span className="text-zinc-400">Modules</span><span className="text-zinc-200">{enabledCount} enabled</span></div>
        <div className="flex justify-between text-sm"><span className="text-zinc-400">AI Models</span><span className="text-zinc-200">{aiModels.length} selected</span></div>
        <div className="flex justify-between text-sm"><span className="text-zinc-400">Add-on cost</span><span className="text-emerald-400 font-bold">${totalPrice}/mo</span></div>
        <div className="flex flex-wrap gap-1 pt-2 border-t border-zinc-800">
          {Object.entries(modules).filter(([_, on]) => on).map(([mid]) => (
            <Badge key={mid} className="text-[9px] bg-cyan-500/15 text-cyan-400">{registry[mid]?.name || mid}</Badge>
          ))}
        </div>
      </div>
      <Button onClick={save} disabled={saving} className="w-full bg-cyan-600 hover:bg-cyan-700 h-12 text-base">
        {saving ? <Loader2 className="w-5 h-5 animate-spin mr-2" /> : <Rocket className="w-5 h-5 mr-2" />}
        Launch Workspace
      </Button>
    </div>,
  ];

  return (
    <div className="fixed inset-0 bg-zinc-950 z-50 flex flex-col" data-testid="workspace-wizard">
      {/* Step indicator */}
      <div className="flex items-center justify-center gap-2 py-4 border-b border-zinc-800">
        {["Persona", "Modules", "AI Models", "API Keys", "Launch"].map((label, i) => (
          <div key={i} className="flex items-center gap-1">
            <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${i <= step ? "bg-cyan-600 text-white" : "bg-zinc-800 text-zinc-500"}`}>{i + 1}</div>
            <span className={`text-xs ${i <= step ? "text-zinc-200" : "text-zinc-600"}`}>{label}</span>
            {i < 4 && <ChevronRight className="w-3 h-3 text-zinc-700 mx-1" />}
          </div>
        ))}
        {onSkip && <Button variant="ghost" onClick={onSkip} className="ml-4 text-xs text-zinc-500">Skip</Button>}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {steps[step]}
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between px-6 py-3 border-t border-zinc-800">
        <Button variant="ghost" onClick={() => setStep(Math.max(0, step - 1))} disabled={step === 0} className="text-zinc-400">
          <ChevronLeft className="w-4 h-4 mr-1" /> Back
        </Button>
        {step < 4 && (
          <Button onClick={() => setStep(step + 1)} className="bg-cyan-600 hover:bg-cyan-700">
            Continue <ChevronRight className="w-4 h-4 ml-1" />
          </Button>
        )}
      </div>
    </div>
  );
}
