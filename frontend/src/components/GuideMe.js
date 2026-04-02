import { useState, useEffect, useRef } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { api } from "@/App";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Globe, Send, Loader2, Power, AlertTriangle, ExternalLink,
  ArrowLeft, ArrowRight, RefreshCw, Shield, Bot,
} from "lucide-react";

const AI_COLORS = {
  claude: "#D97757", chatgpt: "#10A37F", gemini: "#4285F4", deepseek: "#4D6BFE",
  grok: "#F5F5F5", groq: "#F55036", perplexity: "#20B2AA", mistral: "#FF7000",
  cohere: "#39594D", mercury: "#00D4FF", pi: "#FF6B35", manus: "#6C5CE7",
  qwen: "#615EFF", kimi: "#000000", llama: "#0467DF", glm: "#3D5AFE",
  cursor: "#00E5A0", notebooklm: "#FBBC04", copilot: "#171515",
};
const AI_NAMES = {
  claude: "Claude", chatgpt: "ChatGPT", gemini: "Gemini", deepseek: "DeepSeek",
  grok: "Grok", groq: "Groq", perplexity: "Perplexity", mistral: "Mistral",
  cohere: "Cohere", mercury: "Mercury 2", pi: "Pi", manus: "Manus",
  qwen: "Qwen", kimi: "Kimi", llama: "Llama", glm: "GLM",
  cursor: "Cursor", notebooklm: "NotebookLM", copilot: "GitHub Copilot",
};

const CAPABLE_AGENTS = new Set(["claude", "chatgpt", "gemini", "deepseek", "groq", "mistral", "cohere", "grok"]);

export default function GuideMe({ workspaceId }) {
  const [url, setUrl] = useState("");
  const [loadedUrl, setLoadedUrl] = useState("");
  const [activeAgent, setActiveAgent] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [sending, setSending] = useState(false);
  const [bannerDismissed, setBannerDismissed] = useState(false);
  const iframeRef = useRef(null);
  const chatEndRef = useRef(null);

  const allAgents = Object.keys(AI_NAMES);

  const navigate = (targetUrl) => {
    let full = targetUrl;
    if (!full.startsWith("http")) full = "https://" + full;
    setLoadedUrl(full);
    setUrl(full);
  };

  const selectAgent = async (agentKey) => {
    if (!CAPABLE_AGENTS.has(agentKey)) return;
    if (activeAgent === agentKey) {
      // Deselect
      if (sessionId) {
        try { await api.delete(`/guide-me/${sessionId}`); } catch (err) { handleSilent(err, "GuideMe:op1"); }
      }
      setActiveAgent(null);
      setSessionId(null);
      setChatMessages([]);
      return;
    }
    // Start new session
    try {
      const res = await api.post("/guide-me/session", {
        agent: agentKey, url: loadedUrl, workspace_id: workspaceId,
      });
      setActiveAgent(agentKey);
      setSessionId(res.data.session_id);
      setChatMessages([{
        role: "assistant",
        content: `Hi! I'm ${AI_NAMES[agentKey]}. I'll help guide you through this page. What would you like help with?\n\n**Note:** I cannot enter usernames, passwords, or create logins for security reasons.`,
      }]);
      toast.success(`${AI_NAMES[agentKey]} is now guiding you`);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to start session");
    }
  };

  const sendChat = async () => {
    if (!chatInput.trim() || !sessionId || sending) return;
    const msg = chatInput;
    setChatInput("");
    setChatMessages(prev => [...prev, { role: "user", content: msg }]);
    setSending(true);
    try {
      await api.post(`/guide-me/${sessionId}/message`, {
        content: msg, current_url: loadedUrl,
      });
      // Simulate agent response (in a real implementation, this would call the AI API)
      const agentResponse = {
        role: "assistant",
        content: `I can see you're on ${loadedUrl || "a page"}. ${msg.includes("?") ? "Let me help you with that." : "I'll guide you through this."}\n\nLook for the relevant section on the page. I can help you navigate — just describe what you're trying to do and I'll point you in the right direction.`,
      };
      setChatMessages(prev => [...prev, agentResponse]);
    } catch (err) { toast.error("Failed to send"); }
    setSending(false);
    setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
  };

  return (
    <div className="flex-1 flex flex-col" data-testid="guide-me">
      {/* Disclaimer banner */}
      {!bannerDismissed && (
        <div className="flex-shrink-0 bg-amber-500/10 border-b border-amber-500/20 px-4 py-2 flex items-center gap-2" data-testid="guide-banner">
          <Shield className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
          <p className="text-[11px] text-amber-400/90 flex-1">
            <strong>Limitations:</strong> Many sites block iframe embedding (Google, GitHub, AWS, most SaaS dashboards, banking sites). 
            This feature works best with documentation sites, internal tools, and sites that allow embedding. 
            AI agents <strong>cannot</strong> enter passwords or create logins.
          </p>
          <button onClick={() => setBannerDismissed(true)} className="text-amber-400/60 hover:text-amber-400 text-xs flex-shrink-0">dismiss</button>
        </div>
      )}

      {/* Header with URL bar */}
      <div className="flex-shrink-0 px-4 py-2 border-b border-zinc-800/60 flex items-center gap-2">
        <Globe className="w-4 h-4 text-blue-400 flex-shrink-0" />
        <h2 className="text-sm font-semibold text-zinc-200 flex-shrink-0" style={{ fontFamily: "Syne, sans-serif" }}>Guide Me</h2>
        <div className="flex-1 flex items-center gap-1 bg-zinc-900 rounded-lg border border-zinc-800 px-2">
          <button onClick={() => window.history.back()} className="p-1 text-zinc-600 hover:text-zinc-300"><ArrowLeft className="w-3 h-3" /></button>
          <button onClick={() => window.history.forward()} className="p-1 text-zinc-600 hover:text-zinc-300"><ArrowRight className="w-3 h-3" /></button>
          <button onClick={() => { if (loadedUrl) navigate(loadedUrl); }} className="p-1 text-zinc-600 hover:text-zinc-300"><RefreshCw className="w-3 h-3" /></button>
          <input
            type="text" value={url} onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") navigate(url); }}
            placeholder="Enter a URL (e.g., docs.example.com)"
            className="flex-1 bg-transparent text-xs text-zinc-200 placeholder:text-zinc-600 py-1.5 focus:outline-none font-mono"
            data-testid="guide-url-input"
          />
          <button onClick={() => navigate(url)} className="p-1 text-zinc-500 hover:text-zinc-300"><ExternalLink className="w-3 h-3" /></button>
        </div>
      </div>

      {/* Main content: Browser + Agent Panel */}
      <div className="flex-1 flex min-h-0">
        {/* Browser iframe */}
        <div className="flex-1 min-w-0 bg-zinc-950">
          {loadedUrl ? (
            <iframe
              ref={iframeRef}
              src={loadedUrl}
              className="w-full h-full border-0"
              sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
              title="Guide Me Browser"
              data-testid="guide-iframe"
            />
          ) : (
            <div className="flex items-center justify-center h-full">
              <div className="text-center max-w-md">
                <Globe className="w-12 h-12 text-zinc-800 mx-auto mb-4" />
                <h3 className="text-base font-semibold text-zinc-400 mb-2">Enter a URL to get started</h3>
                <p className="text-sm text-zinc-600 mb-4">Type a URL in the address bar above, then select an AI agent to guide you through the page.</p>
                <div className="flex flex-wrap gap-2 justify-center">
                  {["docs.python.org", "developer.mozilla.org", "tailwindcss.com/docs"].map(site => (
                    <button key={site} onClick={() => navigate(`https://${site}`)}
                      className="px-3 py-1.5 rounded-lg bg-zinc-800/40 border border-zinc-800 text-xs text-zinc-400 hover:text-zinc-200 hover:border-zinc-700">
                      {site}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Agent panel + Chat (right side) */}
        <div className="w-72 flex-shrink-0 border-l border-zinc-800/60 flex flex-col bg-zinc-900/30">
          {/* Agent selector */}
          <div className="flex-shrink-0 p-2 border-b border-zinc-800/40">
            <p className="text-[9px] text-zinc-500 uppercase tracking-wider font-semibold mb-2 px-1">Select AI Guide (1 at a time)</p>
            <div className="grid grid-cols-3 gap-1">
              {allAgents.map(key => {
                const capable = CAPABLE_AGENTS.has(key);
                const isActive = activeAgent === key;
                return (
                  <button
                    key={key}
                    onClick={() => capable && selectAgent(key)}
                    disabled={!capable}
                    className={`flex flex-col items-center gap-0.5 p-1.5 rounded-lg transition-all ${
                      isActive ? "bg-emerald-500/20 border border-emerald-500/40" :
                      capable ? "hover:bg-zinc-800/60 border border-transparent" :
                      "opacity-30 cursor-not-allowed border border-transparent"
                    }`}
                    title={capable ? AI_NAMES[key] : `${AI_NAMES[key]} — not available for guidance`}
                    data-testid={`guide-agent-${key}`}
                  >
                    <div className="w-6 h-6 rounded-full flex items-center justify-center text-[8px] font-bold"
                      style={{ backgroundColor: capable ? AI_COLORS[key] : "#27272a", color: key === "grok" ? "#09090b" : "#fff" }}>
                      {AI_NAMES[key][0]}
                    </div>
                    <span className={`text-[8px] truncate w-full text-center ${isActive ? "text-emerald-400" : capable ? "text-zinc-500" : "text-zinc-700"}`}>
                      {AI_NAMES[key]}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Chat area */}
          <ScrollArea className="flex-1">
            <div className="p-2 space-y-2">
              {!activeAgent ? (
                <div className="text-center py-8">
                  <Bot className="w-6 h-6 text-zinc-800 mx-auto mb-2" />
                  <p className="text-[10px] text-zinc-600">Select an agent above to start guidance</p>
                </div>
              ) : (
                chatMessages.map((msg, i) => (
                  <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[90%] rounded-xl px-3 py-2 text-xs ${
                      msg.role === "user" ? "bg-emerald-500/20 text-zinc-200" : "bg-zinc-800/60 text-zinc-300"
                    }`}>
                      {msg.role === "assistant" && (
                        <div className="flex items-center gap-1 mb-1">
                          <div className="w-4 h-4 rounded-full flex items-center justify-center text-[7px] font-bold"
                            style={{ backgroundColor: AI_COLORS[activeAgent], color: activeAgent === "grok" ? "#09090b" : "#fff" }}>
                            {AI_NAMES[activeAgent][0]}
                          </div>
                          <span className="text-[9px] text-zinc-500">{AI_NAMES[activeAgent]}</span>
                        </div>
                      )}
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  </div>
                ))
              )}
              <div ref={chatEndRef} />
            </div>
          </ScrollArea>

          {/* Chat input */}
          {activeAgent && (
            <div className="flex-shrink-0 p-2 border-t border-zinc-800/40">
              <div className="flex gap-1">
                <input
                  value={chatInput} onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && sendChat()}
                  placeholder="Ask for guidance..."
                  className="flex-1 bg-zinc-900 border border-zinc-800 rounded-lg px-2.5 py-1.5 text-xs text-zinc-200 placeholder:text-zinc-600 focus:outline-none"
                  data-testid="guide-chat-input"
                />
                <Button size="sm" onClick={sendChat} disabled={!chatInput.trim() || sending}
                  className="bg-emerald-500 hover:bg-emerald-400 text-white h-7 w-7 p-0">
                  {sending ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />}
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
