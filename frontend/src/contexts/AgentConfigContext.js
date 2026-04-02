import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";

const AgentConfigContext = createContext(null);

export function AgentConfigProvider({ children }) {
  const [models, setModels] = useState({});
  const [loaded, setLoaded] = useState(false);

  const fetchModels = useCallback(async () => {
    try {
      const res = await api.get("/ai-models");
      setModels(res.data?.models || res.data || {});
    } catch { /* silent */ }
    setLoaded(true);
  }, []);

  useEffect(() => { fetchModels(); }, [fetchModels]);

  const getModelName = useCallback((key) => {
    if (!key) return "Unknown";
    return key.charAt(0).toUpperCase() + key.slice(1);
  }, []);

  const getModelColor = useCallback((key) => {
    const colors = {
      claude: "#D97706", chatgpt: "#10B981", gemini: "#3B82F6", deepseek: "#6366F1",
      grok: "#EF4444", perplexity: "#0EA5E9", mistral: "#F59E0B", cohere: "#8B5CF6",
      groq: "#EC4899", mercury: "#14B8A6", pi: "#F97316", manus: "#6D28D9",
      qwen: "#2563EB", kimi: "#7C3AED", llama: "#059669", glm: "#DC2626",
      cursor: "#0891B2", notebooklm: "#4F46E5", copilot: "#1D4ED8",
    };
    return colors[key] || "#6366F1";
  }, []);

  const getModelVariants = useCallback((key) => {
    return models[key] || [];
  }, [models]);

  const getDefaultModel = useCallback((key) => {
    const variants = models[key] || [];
    const def = variants.find(v => v.default);
    return def?.id || variants[0]?.id || "";
  }, [models]);

  const getAllModelKeys = useCallback(() => Object.keys(models), [models]);

  return (
    <AgentConfigContext.Provider value={{ models, loaded, getModelName, getModelColor, getModelVariants, getDefaultModel, getAllModelKeys, refresh: fetchModels }}>
      {children}
    </AgentConfigContext.Provider>
  );
}

export function useAgentConfig() {
  const ctx = useContext(AgentConfigContext);
  if (!ctx) throw new Error("useAgentConfig must be used within AgentConfigProvider");
  return ctx;
}
