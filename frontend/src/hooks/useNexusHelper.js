import { useState, useCallback, useRef, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { api } from "@/App";

function detectPage(pathname) {
  if (pathname.startsWith("/admin")) return "admin";
  if (pathname.startsWith("/settings")) return "settings";
  if (pathname.startsWith("/billing")) return "billing";
  return "dashboard";
}

export function useNexusHelper() {
  const [open, setOpen] = useState(false);
  const [minimized, setMinimized] = useState(false);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [context, setContext] = useState(null);

  const pageRef = useRef("dashboard");
  const wsRef = useRef("");
  const location = useLocation();

  useEffect(() => {
    api.get("/helper/history").then(r => setMessages(r.data?.messages || [])).catch(() => {});
  }, []);

  useEffect(() => {
    const page = detectPage(location.pathname);
    if (page !== pageRef.current) {
      pageRef.current = page;
      api.get(`/helper/context?page=${page}`).then(r => setContext(r.data)).catch(() => {});
    }
  }, [location.pathname]);

  const setPageContext = useCallback((tab, workspaceId = "") => {
    pageRef.current = tab;
    wsRef.current = workspaceId;
    const params = new URLSearchParams({ page: tab });
    if (workspaceId) params.set("workspace_id", workspaceId);
    api.get(`/helper/context?${params}`).then(r => setContext(r.data)).catch(() => {});
  }, []);

  const sendMessage = useCallback(async (text, errorContext = null) => {
    if (!text.trim() || loading) return;
    setMessages(prev => [...prev, { role: "user", content: text, ts: new Date().toISOString() }]);
    setLoading(true);
    try {
      const res = await api.post("/helper/chat", {
        message: text,
        page_context: pageRef.current,
        workspace_id: wsRef.current || undefined,
        error_context: errorContext || undefined,
      });
      setMessages(prev => [...prev, {
        role: "assistant", content: res.data.response, agent: res.data.agent,
        actions: res.data.actions || [], ts: new Date().toISOString()
      }]);
    } catch (e) {
      const errMsg = e.response?.data?.detail || "Helper unavailable. Please try again.";
      setMessages(prev => [...prev, { role: "assistant", content: errMsg, error: true, ts: new Date().toISOString() }]);
    }
    setLoading(false);
  }, [loading]);

  const approveAction = useCallback(async (actionId) => {
    try {
      const res = await api.post(`/helper/actions/${actionId}/approve`);
      setMessages(prev => prev.map(m => ({
        ...m,
        actions: (m.actions || []).map(a => a.action_id === actionId ? { ...a, status: res.data.status || "completed", result: res.data.result } : a)
      })));
      return res.data;
    } catch (e) {
      return { error: e.response?.data?.detail || "Approval failed" };
    }
  }, []);

  const dismissAction = useCallback(async (actionId) => {
    try {
      await api.post(`/helper/actions/${actionId}/dismiss`);
      setMessages(prev => prev.map(m => ({
        ...m,
        actions: (m.actions || []).map(a => a.action_id === actionId ? { ...a, status: "dismissed" } : a)
      })));
    } catch {}
  }, []);

  const clearHistory = useCallback(async () => {
    await api.delete("/helper/history").catch(() => {});
    setMessages([]);
  }, []);

  const toggle = useCallback(() => {
    if (minimized) { setMinimized(false); setOpen(true); }
    else setOpen(prev => !prev);
  }, [minimized]);

  const minimize = useCallback(() => { setOpen(false); setMinimized(true); }, []);
  const restore = useCallback(() => { setMinimized(false); setOpen(true); }, []);

  return { open, minimized, messages, loading, context, toggle, minimize, restore, sendMessage, clearHistory, setPageContext, approveAction, dismissAction };
}
