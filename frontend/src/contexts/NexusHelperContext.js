import { createContext, useContext } from "react";
import { useNexusHelper } from "@/hooks/useNexusHelper";

const NexusHelperContext = createContext(null);

export function NexusHelperProvider({ children }) {
  const helper = useNexusHelper();
  return (
    <NexusHelperContext.Provider value={helper}>
      {children}
    </NexusHelperContext.Provider>
  );
}

export function useHelper() {
  const ctx = useContext(NexusHelperContext);
  if (!ctx) throw new Error("useHelper must be used within NexusHelperProvider");
  return ctx;
}
