import { useState, useEffect, useCallback, useRef } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { api } from "@/App";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Activity, FolderKanban, FileCode, BookOpen, Brain, Code2,
  CheckCircle2, GitCommit, Zap, ChevronRight, ChevronDown, X,
  AlertTriangle, MessageSquare, GitBranch, Filter, Clock,
} from "lucide-react";

const MODULE_ICONS = {
  projects: FolderKanban,
  tasks: CheckCircle2,
  code_repo: GitCommit,
  wiki: BookOpen,
  knowledge: Brain,
  artifacts: FileCode,
  code: Code2,
  collaboration: Zap,
  context: GitBranch,
  other: Activity,
};

const MODULE_COLORS = {
  projects: "text-purple-400 bg-purple-500/15",
  tasks: "text-amber-400 bg-amber-500/15",
  code_repo: "text-emerald-400 bg-emerald-500/15",
  wiki: "text-blue-400 bg-blue-500/15",
  knowledge: "text-cyan-400 bg-cyan-500/15",
  artifacts: "text-orange-400 bg-orange-500/15",
  code: "text-green-400 bg-green-500/15",
  collaboration: "text-pink-400 bg-pink-500/15",
  context: "text-indigo-400 bg-indigo-500/15",
  other: "text-zinc-400 bg-zinc-500/15",
};

const ACTION_TYPE_CONFIG = {
  ai_response: { label: "Response", icon: MessageSquare, color: "text-emerald-400" },
  tool_call: { label: "Tool", icon: Zap, color: "text-amber-400" },
  error: { label: "Error", icon: AlertTriangle, color: "text-red-400" },
  context_switch: { label: "Context", icon: GitBranch, color: "text-indigo-400" },
};

const AI_COLORS = {
  claude: "#D97757", chatgpt: "#10A37F", gemini: "#4285F4", deepseek: "#4D6BFE",
  grok: "#F5F5F5", groq: "#F55036", perplexity: "#20B2AA", mistral: "#FF7000",
  cohere: "#39594D", mercury: "#00D4FF", pi: "#FF6B35", manus: "#6C5CE7",
  qwen: "#615EFF", kimi: "#000000", llama: "#0467DF", glm: "#3D5AFE",
  cursor: "#00E5A0", notebooklm: "#FBBC04", copilot: "#171515",
};

export default function AgentActivityPanel({ workspaceId, channelId, isOpen, onClose, onNewActivity }) {
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterType, setFilterType] = useState("");
  const [expanded, setExpanded] = useState({});
  const [total, setTotal] = useState(0);
  const prevCountRef = useRef(0);
  const scrollRef = useRef(null);

  const fetchActivities = useCallback(async () => {
    try {
      let params = `?limit=100`;
      if (channelId) params += `&channel_id=${channelId}`;
      if (filterType) params += `&action_type=${filterType}`;
      const res = await api.get(`/workspaces/${workspaceId}/activities${params}`);
      const newActivities = res.data?.activities || [];
      const newTotal = res.data?.total || 0;
      
      // Notify on new activity
      if (prevCountRef.current > 0 && newTotal > prevCountRef.current && onNewActivity) {
        onNewActivity(newActivities[0]);
      }
      prevCountRef.current = newTotal;
      
      setActivities(newActivities);
      setTotal(newTotal);
    } catch (err) { handleSilent(err, "AgentActivityPanel:op1"); }
    setLoading(false);
  }, [workspaceId, channelId, filterType, onNewActivity]);

  useEffect(() => {
    if (isOpen) {
      fetchActivities();
    }
  }, [isOpen, workspaceId, channelId, filterType]);

  // Poll every 2 seconds for near-real-time updates
  useEffect(() => {
    if (!isOpen) return;
    const interval = setInterval(fetchActivities, 2000);
    return () => clearInterval(interval);
  }, [isOpen, fetchActivities]);

  const toggleExpand = (id) => {
    setExpanded(prev => ({ ...prev, [id]: !prev[id] }));
  };

  if (!isOpen) return null;

  return (
    <div className="w-80 flex-shrink-0 border-l border-zinc-800/60 flex flex-col bg-zinc-900/30" data-testid="agent-activity-panel">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800/40">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-emerald-400" />
          <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">Agent Actions</span>
          <Badge className="bg-zinc-800 text-zinc-500 text-[9px]">{total}</Badge>
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" title="Live updates" />
        </div>
        <button onClick={onClose} className="p-1 text-zinc-600 hover:text-zinc-300" data-testid="close-activity-panel">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Filter bar */}
      <div className="px-2 py-1.5 border-b border-zinc-800/30 flex items-center gap-1">
        <Filter className="w-3 h-3 text-zinc-600" />
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="bg-transparent text-[10px] text-zinc-400 border-0 p-0 cursor-pointer flex-1"
          data-testid="activity-filter-type"
        >
          <option value="" className="bg-zinc-900">All Actions</option>
          <option value="ai_response" className="bg-zinc-900">AI Responses</option>
          <option value="tool_call" className="bg-zinc-900">Tool Calls</option>
          <option value="error" className="bg-zinc-900">Errors</option>
        </select>
      </div>

      {/* Activity feed */}
      <ScrollArea className="flex-1" ref={scrollRef}>
        <div className="p-2 space-y-0.5">
          {loading ? (
            <div className="text-center py-8 text-zinc-600 text-xs">Loading...</div>
          ) : activities.length === 0 ? (
            <div className="text-center py-8">
              <Activity className="w-6 h-6 text-zinc-800 mx-auto mb-2" />
              <p className="text-[10px] text-zinc-600">No agent activity yet</p>
              <p className="text-[9px] text-zinc-700 mt-1">Activities appear here as agents respond, use tools, and switch context</p>
            </div>
          ) : (
            activities.map((act) => {
              const Icon = MODULE_ICONS[act.module] || Activity;
              const colorClass = MODULE_COLORS[act.module] || MODULE_COLORS.other;
              const agentColor = AI_COLORS[act.agent_key] || AI_COLORS[act.agent?.toLowerCase()] || "#666";
              const timeDiff = getTimeDiff(act.timestamp);
              const isExpanded = expanded[act.activity_id];
              const actionCfg = ACTION_TYPE_CONFIG[act.action_type] || {};
              const ActionIcon = actionCfg.icon || Activity;
              const isError = act.status === "error" || act.action_type === "error";
              
              return (
                <div
                  key={act.activity_id}
                  className={`px-2 py-1.5 rounded-lg transition-colors cursor-pointer ${
                    isError ? "bg-red-500/5 hover:bg-red-500/10 border border-red-500/10" : "hover:bg-zinc-800/30"
                  }`}
                  onClick={() => toggleExpand(act.activity_id)}
                  data-testid={`activity-${act.activity_id}`}
                >
                  <div className="flex items-start gap-2">
                    {/* Agent avatar */}
                    <div className="w-5 h-5 rounded-full flex items-center justify-center text-[8px] font-bold flex-shrink-0 mt-0.5"
                      style={{ backgroundColor: agentColor, color: act.agent_key === "grok" ? "#09090b" : "#fff" }}>
                      {(act.agent || "?")[0]}
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      {/* Agent + action type + tool */}
                      <div className="flex items-center gap-1 mb-0.5 flex-wrap">
                        <span className="text-[10px] font-medium text-zinc-300">{act.agent}</span>
                        <ActionIcon className={`w-2.5 h-2.5 ${actionCfg.color || "text-zinc-500"}`} />
                        {act.tool && (
                          <>
                            <ChevronRight className="w-2 h-2 text-zinc-700" />
                            <span className={`text-[9px] px-1 py-0 rounded ${colorClass}`}>
                              {act.tool?.replace(/_/g, " ")}
                            </span>
                          </>
                        )}
                        {act.action_type === "ai_response" && !act.tool && (
                          <span className="text-[9px] px-1 py-0 rounded bg-emerald-500/10 text-emerald-400">responded</span>
                        )}
                        {isError && (
                          <span className="text-[9px] px-1 py-0 rounded bg-red-500/15 text-red-400">error</span>
                        )}
                      </div>
                      
                      {/* Summary (collapsed = 1 line, expanded = full) */}
                      <p className={`text-[10px] text-zinc-500 leading-tight ${isExpanded ? "" : "line-clamp-1"}`}>
                        {stripMarkdown(act.summary || "")}
                      </p>
                      
                      {/* Expanded details */}
                      {isExpanded && (
                        <div className="mt-1.5 space-y-1 text-[9px]">
                          {act.response_time_ms && (
                            <div className="flex items-center gap-1 text-zinc-600">
                              <Clock className="w-2.5 h-2.5" /> {act.response_time_ms}ms
                            </div>
                          )}
                          {act.has_tool_calls && <p className="text-amber-500/70">Contains tool calls</p>}
                          {act.has_violations && <p className="text-red-400/70">Directive violation detected</p>}
                          {act.params && Object.keys(act.params).length > 0 && (
                            <div className="bg-zinc-800/50 rounded p-1.5 text-[9px] text-zinc-500 font-mono">
                              {Object.entries(act.params).map(([k, v]) => (
                                <div key={k}><span className="text-zinc-600">{k}:</span> {String(v).substring(0, 80)}</div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                      
                      {/* Time + expand indicator */}
                      <div className="flex items-center gap-1 mt-0.5">
                        <span className="text-[9px] text-zinc-700">{timeDiff}</span>
                        {isExpanded ? <ChevronDown className="w-2.5 h-2.5 text-zinc-700" /> : <ChevronRight className="w-2.5 h-2.5 text-zinc-700" />}
                      </div>
                    </div>
                    
                    {/* Module icon */}
                    <Icon className={`w-3 h-3 flex-shrink-0 mt-0.5 ${colorClass.split(" ")[0]}`} />
                  </div>
                </div>
              );
            })
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

function stripMarkdown(text) {
  return text.replace(/\*\*/g, "").replace(/`/g, "").replace(/\n/g, " ").substring(0, 300);
}

function getTimeDiff(timestamp) {
  if (!timestamp) return "";
  try {
    const diff = Date.now() - new Date(timestamp).getTime();
    if (diff < 5000) return "just now";
    if (diff < 60000) return `${Math.floor(diff / 1000)}s ago`;
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return `${Math.floor(diff / 86400000)}d ago`;
  } catch (err) { return ""; }
}
