import { useState, useEffect } from "react";
import {
  Terminal, Search, Wrench, BarChart3, Sparkles, Bot, Settings2,
  ExternalLink, Check, Loader2, ChevronDown, ChevronUp, Info, Key
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { toast } from "sonner";
import { api } from "@/App";

const AI_AGENTS = [
  { key: "claude", name: "Claude", provider: "Anthropic", color: "#D97757" },
  { key: "chatgpt", name: "ChatGPT", provider: "OpenAI", color: "#10A37F" },
  { key: "gemini", name: "Gemini", provider: "Google", color: "#4285F4" },
  { key: "perplexity", name: "Perplexity", provider: "Perplexity AI", color: "#20B2AA" },
  { key: "mistral", name: "Mistral", provider: "Mistral AI", color: "#FF7000" },
  { key: "cohere", name: "Cohere", provider: "Cohere", color: "#39594D" },
  { key: "groq", name: "Groq", provider: "Groq", color: "#F55036" },
  { key: "deepseek", name: "DeepSeek", provider: "DeepSeek", color: "#4D6BFE" },
  { key: "grok", name: "Grok", provider: "xAI", color: "#F5F5F5" },
  { key: "mercury", name: "Mercury 2", provider: "Inception Labs", color: "#00D4FF" },
  { key: "pi", name: "Pi", provider: "Inflection AI", color: "#FF6B35" },
  { key: "manus", name: "Manus", provider: "Manus AI", color: "#6C5CE7" },
  { key: "qwen", name: "Qwen", provider: "Alibaba Cloud", color: "#615EFF" },
  { key: "kimi", name: "Kimi", provider: "Moonshot AI", color: "#000000" },
  { key: "llama", name: "Llama", provider: "Together AI", color: "#0467DF" },
  { key: "glm", name: "GLM", provider: "Zhipu AI", color: "#3D5AFE" },
  { key: "cursor", name: "Cursor", provider: "OpenRouter", color: "#00E5A0" },
  { key: "notebooklm", name: "NotebookLM", provider: "OpenRouter", color: "#FBBC04" },
  { key: "copilot", name: "GitHub Copilot", provider: "OpenRouter", color: "#171515" },
];

const CATEGORY_ICONS = {
  code_execution: Terminal,
  search: Search,
  functions: Wrench,
  analysis: BarChart3,
  generation: Sparkles,
  automation: Bot,
};

const CATEGORY_COLORS = {
  code_execution: { text: "text-emerald-400", bg: "bg-emerald-500/20" },
  search: { text: "text-blue-400", bg: "bg-blue-500/20" },
  functions: { text: "text-amber-400", bg: "bg-amber-500/20" },
  analysis: { text: "text-purple-400", bg: "bg-purple-500/20" },
  generation: { text: "text-pink-400", bg: "bg-pink-500/20" },
  automation: { text: "text-indigo-400", bg: "bg-indigo-500/20" },
};

export default function WorkspaceSkillsTab({ workspaceId }) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState({});
  const [skillsData, setSkillsData] = useState(null);
  const [enabledSkills, setEnabledSkills] = useState({});
  const [expandedModel, setExpandedModel] = useState(null);
  const [apiKeys, setApiKeys] = useState({});

  useEffect(() => {
    fetchData();
  }, [workspaceId]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [skillsRes, keysRes] = await Promise.all([
        api.get(`/workspaces/${workspaceId}/ai-skills`),
        api.get("/settings/ai-keys")
      ]);
      
      setSkillsData(skillsRes.data.available_skills || {});
      setEnabledSkills(skillsRes.data.config?.enabled_skills || {});
      setApiKeys(keysRes.data || {});
    } catch (err) {
      toast.error("Failed to load skills configuration");
    } finally {
      setLoading(false);
    }
  };

  const toggleSkill = async (modelKey, skillId, isAlwaysEnabled) => {
    if (isAlwaysEnabled) {
      toast.info("This skill is always enabled for this AI model");
      return;
    }

    const currentEnabled = enabledSkills[modelKey] || [];
    const newEnabled = currentEnabled.includes(skillId)
      ? currentEnabled.filter(s => s !== skillId)
      : [...currentEnabled, skillId];
    
    // Optimistic update
    setEnabledSkills(prev => ({ ...prev, [modelKey]: newEnabled }));
    
    setSaving(prev => ({ ...prev, [modelKey]: true }));
    try {
      await api.put(`/workspaces/${workspaceId}/ai-skills/${modelKey}`, {
        skill_ids: newEnabled
      });
    } catch (err) {
      // Revert on error
      setEnabledSkills(prev => ({ ...prev, [modelKey]: currentEnabled }));
      toast.error("Failed to update skills");
    } finally {
      setSaving(prev => ({ ...prev, [modelKey]: false }));
    }
  };

  const getEnabledCount = (modelKey) => {
    return (enabledSkills[modelKey] || []).length;
  };

  const getTotalSkillsCount = (modelKey) => {
    return skillsData?.[modelKey]?.skills?.length || 0;
  };

  const hasApiKey = (modelKey) => {
    // All AI models now require user API keys
    return apiKeys[modelKey]?.configured || false;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-zinc-400" />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-6" data-testid="workspace-skills-tab">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h2 className="text-xl font-semibold text-zinc-100 flex items-center gap-2">
            <Settings2 className="w-5 h-5" />
            AI Skills Configuration
          </h2>
          <p className="text-sm text-zinc-500 mt-1">
            Enable vendor-supported skills for each AI model in this workspace.
            Skills are used when AIs participate in collaborations.
          </p>
        </div>

        {/* Info banner */}
        <div className="p-4 rounded-xl bg-blue-500/10 border border-blue-500/30 mb-6 flex items-start gap-3">
          <Info className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-blue-300">
            <p className="font-medium mb-1">How Skills Work</p>
            <p className="text-blue-400/80">
              When enabled, skills like Code Interpreter let AIs execute code, 
              Web Search provides real-time information, and Function Calling enables 
              structured tool use. Skills marked "Always On" are core to that AI's functionality.
            </p>
          </div>
        </div>

        {/* AI Models Grid */}
        <div className="space-y-3">
          {AI_AGENTS.map((agent) => {
            const modelSkills = skillsData?.[agent.key]?.skills || [];
            const isExpanded = expandedModel === agent.key;
            const enabledCount = getEnabledCount(agent.key);
            const totalCount = getTotalSkillsCount(agent.key);
            const hasKey = hasApiKey(agent.key);
            const isSaving = saving[agent.key];

            // Group skills by category
            const skillsByCategory = modelSkills.reduce((acc, skill) => {
              const cat = skill.category || "functions";
              if (!acc[cat]) acc[cat] = [];
              acc[cat].push(skill);
              return acc;
            }, {});

            return (
              <div
                key={agent.key}
                className="border border-zinc-800 rounded-xl overflow-hidden"
                data-testid={`skills-model-${agent.key}`}
              >
                {/* Model Header */}
                <button
                  onClick={() => setExpandedModel(isExpanded ? null : agent.key)}
                  className="w-full flex items-center justify-between px-4 py-3 bg-zinc-900/50 hover:bg-zinc-900 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold"
                      style={{
                        backgroundColor: agent.color,
                        color: ["#F5F5F5", "#FF7000", "#F55036"].includes(agent.color)
                          ? "#09090b"
                          : "#fff",
                      }}
                    >
                      {agent.name.slice(0, 2)}
                    </div>
                    <div className="text-left">
                      <span className="text-sm font-semibold text-zinc-200">{agent.name}</span>
                      <span className="text-xs text-zinc-600 ml-2">by {agent.provider}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {!hasKey && (
                      <Badge className="bg-amber-500/20 text-amber-400 text-[10px]">
                        <Key className="w-3 h-3 mr-1" />
                        No API Key
                      </Badge>
                    )}
                    <Badge className={enabledCount > 0 ? "bg-emerald-500/20 text-emerald-400" : "bg-zinc-800 text-zinc-500"}>
                      {enabledCount}/{totalCount} skills
                    </Badge>
                    {isSaving && <Loader2 className="w-4 h-4 animate-spin text-zinc-400" />}
                    {isExpanded ? (
                      <ChevronUp className="w-4 h-4 text-zinc-500" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-zinc-500" />
                    )}
                  </div>
                </button>

                {/* Skills List */}
                {isExpanded && (
                  <div className="border-t border-zinc-800">
                    {modelSkills.length === 0 ? (
                      <div className="p-6 text-center text-zinc-500 text-sm">
                        No skills available for {agent.name}
                      </div>
                    ) : (
                      Object.entries(skillsByCategory).map(([category, skills]) => {
                        const CategoryIcon = CATEGORY_ICONS[category] || Wrench;
                        const colors = CATEGORY_COLORS[category] || { text: "text-zinc-400", bg: "bg-zinc-500/20" };

                        return (
                          <div key={category}>
                            <div className="px-4 py-2 bg-zinc-950/50 border-b border-zinc-800/50 flex items-center gap-2">
                              <div className={`p-1 rounded ${colors.bg}`}>
                                <CategoryIcon className={`w-3 h-3 ${colors.text}`} />
                              </div>
                              <span className="text-xs font-medium text-zinc-400 uppercase tracking-wider">
                                {category.replace("_", " ")}
                              </span>
                            </div>
                            {skills.map((skill) => {
                              const isEnabled = (enabledSkills[agent.key] || []).includes(skill.id);
                              const isAlwaysEnabled = skill.always_enabled;
                              const isPriority = skill.priority;
                              const isBeta = skill.beta;

                              return (
                                <div
                                  key={skill.id}
                                  className="flex items-start justify-between px-4 py-3 border-b border-zinc-800/30 hover:bg-zinc-800/20 transition-colors"
                                >
                                  <div className="flex-1 pr-4">
                                    <div className="flex items-center gap-2 flex-wrap">
                                      <span className="text-sm text-zinc-200">{skill.name}</span>
                                      {isPriority && (
                                        <Badge className="bg-emerald-500/20 text-emerald-400 text-[9px]">
                                          Recommended
                                        </Badge>
                                      )}
                                      {isBeta && (
                                        <Badge className="bg-amber-500/20 text-amber-400 text-[9px]">
                                          Beta
                                        </Badge>
                                      )}
                                      {isAlwaysEnabled && (
                                        <Badge className="bg-blue-500/20 text-blue-400 text-[9px]">
                                          Always On
                                        </Badge>
                                      )}
                                    </div>
                                    <p className="text-xs text-zinc-500 mt-1">{skill.description}</p>
                                    {skill.docs_url && (
                                      <a
                                        href={skill.docs_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="inline-flex items-center gap-1 text-[10px] text-blue-400 hover:text-blue-300 mt-1.5"
                                        onClick={(e) => e.stopPropagation()}
                                      >
                                        <ExternalLink className="w-3 h-3" />
                                        Documentation
                                      </a>
                                    )}
                                  </div>
                                  <TooltipProvider>
                                    <Tooltip>
                                      <TooltipTrigger asChild>
                                        <div>
                                          <Switch
                                            checked={Boolean(isEnabled || isAlwaysEnabled)}
                                            onCheckedChange={() => toggleSkill(agent.key, skill.id, isAlwaysEnabled)}
                                            disabled={isSaving || isAlwaysEnabled || !hasKey}
                                            className="data-[state=checked]:bg-emerald-500"
                                            data-testid={`skill-${agent.key}-${skill.id}`}
                                          />
                                        </div>
                                      </TooltipTrigger>
                                      {!hasKey && (
                                        <TooltipContent className="bg-zinc-800 border-zinc-700 text-zinc-300">
                                          <p>Add API key in Settings to enable skills</p>
                                        </TooltipContent>
                                      )}
                                      {isAlwaysEnabled && (
                                        <TooltipContent className="bg-zinc-800 border-zinc-700 text-zinc-300">
                                          <p>This skill is always enabled</p>
                                        </TooltipContent>
                                      )}
                                    </Tooltip>
                                  </TooltipProvider>
                                </div>
                              );
                            })}
                          </div>
                        );
                      })
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="mt-6 p-4 rounded-xl bg-zinc-900/30 border border-zinc-800/40 flex items-start gap-3">
          <Info className="w-4 h-4 text-zinc-500 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-zinc-500">
            Skills configuration is workspace-specific. Changes here only affect AI behavior 
            in this workspace. All AI models require your own API key configured in Settings.
          </p>
        </div>
      </div>
    </div>
  );
}
