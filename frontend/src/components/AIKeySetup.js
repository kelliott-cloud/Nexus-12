import { useState, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Check, Key } from "lucide-react";
import { api } from "@/App";

const AI_AGENTS = [
  { key: "claude", name: "Claude", provider: "Anthropic", color: "#D97757", placeholder: "Enter API key" },
  { key: "chatgpt", name: "ChatGPT", provider: "OpenAI", color: "#10A37F", placeholder: "Enter API key" },
  { key: "gemini", name: "Gemini", provider: "Google", color: "#4285F4", placeholder: "Enter API key" },
  { key: "perplexity", name: "Perplexity", provider: "Perplexity AI", color: "#20B2AA", placeholder: "pplx-..." },
  { key: "mistral", name: "Mistral", provider: "Mistral AI", color: "#FF7000", placeholder: "..." },
  { key: "cohere", name: "Cohere", provider: "Cohere", color: "#39594D", placeholder: "..." },
  { key: "groq", name: "Groq", provider: "Groq", color: "#F55036", placeholder: "gsk_..." },
  { key: "deepseek", name: "DeepSeek", provider: "DeepSeek", color: "#4D6BFE", placeholder: "Enter API key" },
  { key: "grok", name: "Grok", provider: "xAI", color: "#F5F5F5", placeholder: "xai-..." },
  { key: "mercury", name: "Mercury 2", provider: "Inception Labs", color: "#00D4FF", placeholder: "..." },
  { key: "pi", name: "Pi", provider: "Inflection AI", color: "#FF6B35", placeholder: "..." },
  { key: "manus", name: "Manus", provider: "Manus AI", color: "#6C5CE7", placeholder: "..." },
  { key: "qwen", name: "Qwen", provider: "Alibaba Cloud", color: "#615EFF", placeholder: "Enter API key" },
  { key: "kimi", name: "Kimi", provider: "Moonshot AI", color: "#000000", placeholder: "Enter API key" },
  { key: "llama", name: "Llama", provider: "Together AI", color: "#0467DF", placeholder: "..." },
  { key: "glm", name: "GLM", provider: "Zhipu AI", color: "#3D5AFE", placeholder: "..." },
  { key: "cursor", name: "Cursor", provider: "OpenRouter", color: "#00E5A0", placeholder: "Enter API key" },
  { key: "notebooklm", name: "NotebookLM", provider: "OpenRouter", color: "#FBBC04", placeholder: "Enter API key" },
  { key: "copilot", name: "GitHub Copilot", provider: "OpenRouter", color: "#171515", placeholder: "Enter API key" },
];

/**
 * AI Key Setup component for workspace creation/configuration
 * @param {Object} config - Current AI config: { claude: { enabled, key_source, api_key }, ... }
 * @param {Function} onChange - Called with updated config
 * @param {Object} accountKeys - Account-level key status: { claude: { configured }, ... }
 */
export const AIKeySetup = ({ config, onChange, accountKeys }) => {
  const updateAgent = (agent, updates) => {
    onChange({
      ...config,
      [agent]: { ...(config[agent] || {}), ...updates },
    });
  };

  return (
    <div className="space-y-3" data-testid="ai-key-setup">
      <div className="flex items-center gap-2 mb-2">
        <Key className="w-3.5 h-3.5 text-zinc-500" />
        <span className="text-xs font-mono uppercase tracking-wider text-zinc-500">AI Agent Configuration</span>
      </div>

      {AI_AGENTS.map((agent) => {
        const agentConfig = config[agent.key] || { enabled: false, key_source: "account", api_key: "" };
        const hasAccountKey = accountKeys?.[agent.key]?.configured;

        return (
          <div key={agent.key}
            className={`p-3 rounded-lg border transition-colors ${agentConfig.enabled ? 'bg-zinc-900/60 border-zinc-700' : 'bg-zinc-900/20 border-zinc-800/40'}`}
            data-testid={`setup-agent-${agent.key}`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-6 h-6 rounded flex items-center justify-center text-[10px] font-bold"
                  style={{ backgroundColor: agent.color, color: agent.color === '#F5F5F5' ? '#09090b' : '#fff', opacity: agentConfig.enabled ? 1 : 0.4 }}>
                  {agent.name[0]}
                </div>
                <div>
                  <span className={`text-sm font-medium ${agentConfig.enabled ? 'text-zinc-200' : 'text-zinc-500'}`}>{agent.name}</span>
                  <span className="text-[10px] text-zinc-600 ml-1.5">{agent.provider}</span>
                </div>
              </div>
              <Switch
                checked={agentConfig.enabled}
                onCheckedChange={(checked) => updateAgent(agent.key, { enabled: checked })}
                data-testid={`toggle-${agent.key}`}
              />
            </div>

            {agentConfig.enabled && (
              <div className="mt-3 space-y-2 pl-8">
                <Select
                  value={agentConfig.key_source || "account"}
                  onValueChange={(v) => updateAgent(agent.key, { key_source: v })}
                >
                  <SelectTrigger className="h-8 bg-zinc-950 border-zinc-800 text-xs" data-testid={`source-${agent.key}`}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-zinc-900 border-zinc-800">
                    {hasAccountKey && (
                      <SelectItem value="account" className="text-xs">
                        Account Key {hasAccountKey && <Check className="w-3 h-3 inline ml-1 text-emerald-400" />}
                      </SelectItem>
                    )}
                    <SelectItem value="project" className="text-xs">Project-Specific Key</SelectItem>
                  </SelectContent>
                </Select>

                {agentConfig.key_source === "project" && (
                  <Input
                    type="password"
                    placeholder={agent.placeholder}
                    value={agentConfig.api_key || ""}
                    onChange={(e) => updateAgent(agent.key, { api_key: e.target.value })}
                    className="h-8 bg-zinc-950 border-zinc-800 text-xs font-mono placeholder:text-zinc-700"
                    data-testid={`project-key-${agent.key}`}
                  />
                )}

                {agentConfig.key_source === "account" && !hasAccountKey && (
                  <p className="text-[10px] text-amber-400">No account key configured. Go to Settings to add one.</p>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default AIKeySetup;
