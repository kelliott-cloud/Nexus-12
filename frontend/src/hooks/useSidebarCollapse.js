import { useState, useCallback } from "react";

/**
 * Shared hook for sidebar collapse state.
 * Persists to localStorage so it carries across all pages and sessions.
 */
export function useSidebarCollapse() {
  const [collapsed, setCollapsedState] = useState(() => {
    return localStorage.getItem("nexus_sidebar_collapsed") === "true";
  });

  const setCollapsed = useCallback((val) => {
    const next = typeof val === "function" ? val(collapsed) : val;
    setCollapsedState(next);
    localStorage.setItem("nexus_sidebar_collapsed", String(next));
  }, [collapsed]);

  const toggle = useCallback(() => {
    setCollapsed(prev => !prev);
  }, [setCollapsed]);

  return { collapsed, setCollapsed, toggle };
}
