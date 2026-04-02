import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";

const ModuleContext = createContext({
  enabledModules: new Set(), enabledNavKeys: new Set(), enabledAIModels: [],
  isModuleEnabled: () => true, isNavKeyEnabled: () => true, moduleConfig: null, registry: {},
  loading: true, refresh: () => {},
});

export function ModuleProvider({ workspaceId, children }) {
  const [state, setState] = useState({
    enabledModules: new Set(), enabledNavKeys: new Set(), enabledAIModels: [],
    moduleConfig: null, registry: {}, loading: true,
  });

  const refresh = useCallback(async () => {
    if (!workspaceId) return;
    try {
      const [modRes, regRes] = await Promise.all([
        api.get(`/workspaces/${workspaceId}/modules`),
        api.get("/modules/registry"),
      ]);
      const config = modRes.data;
      const registry = regRes.data?.modules || {};
      const enabledModules = new Set();
      const enabledNavKeys = new Set(config.enabled_nav_keys || []);

      if (config.modules) {
        for (const [mid, mc] of Object.entries(config.modules)) {
          if (mc?.enabled || registry[mid]?.always_on) enabledModules.add(mid);
        }
      } else {
        Object.keys(registry).forEach(mid => enabledModules.add(mid));
      }

      // If no nav keys from server, compute from enabled modules
      if (enabledNavKeys.size === 0) {
        for (const mid of enabledModules) {
          (registry[mid]?.nav_keys || []).forEach(k => enabledNavKeys.add(k));
        }
      }

      setState({
        enabledModules, enabledNavKeys,
        enabledAIModels: config.ai_models || [],
        moduleConfig: config, registry, loading: false,
      });
    } catch (err) {
      // Backward compat: if endpoint fails, enable everything
      setState(prev => ({ ...prev, loading: false }));
    }
  }, [workspaceId]);

  useEffect(() => { refresh(); }, [refresh]);

  const isModuleEnabled = (moduleId) => state.enabledModules.size === 0 || state.enabledModules.has(moduleId);
  const isNavKeyEnabled = (navKey) => state.enabledNavKeys.size === 0 || state.enabledNavKeys.has(navKey);

  return (
    <ModuleContext.Provider value={{ ...state, isModuleEnabled, isNavKeyEnabled, refresh }}>
      {children}
    </ModuleContext.Provider>
  );
}

export function useModules() { return useContext(ModuleContext); }
