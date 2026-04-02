import { BarChart3, MessageSquare, Code2, CheckCircle2, Users } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";

const AI_COLORS = {
  claude: "#D97757",
  chatgpt: "#10A37F",
  deepseek: "#4D6BFE",
  grok: "#F5F5F5",
  gemini: "#4285F4",
  perplexity: "#20B2AA",
  mistral: "#FF7000",
  cohere: "#39594D",
  groq: "#F55036",
  mercury: "#00D4FF",
  pi: "#FF6B35",
  manus: "#6C5CE7",
  qwen: "#615EFF",
  kimi: "#000000",
  llama: "#0467DF",
  glm: "#3D5AFE",
  cursor: "#00E5A0",
  notebooklm: "#FBBC04",
  copilot: "#171515",
};

const AI_NAMES = {
  claude: "Claude",
  chatgpt: "ChatGPT",
  deepseek: "DeepSeek",
  grok: "Grok",
  gemini: "Gemini",
  perplexity: "Perplexity",
  mistral: "Mistral",
  cohere: "Cohere",
  groq: "Groq",
  mercury: "Mercury 2",
  pi: "Pi",
  manus: "Manus",
  qwen: "Qwen",
  kimi: "Kimi",
  llama: "Llama",
  glm: "GLM",
  cursor: "Cursor",
  notebooklm: "NotebookLM",
  copilot: "GitHub Copilot",
};

export const Reports = ({ reports }) => {
  if (!reports) return (
    <div className="flex items-center justify-center h-64 text-zinc-600 text-sm">Loading reports...</div>
  );

  const { agent_stats, task_stats, total_messages, total_human_messages, total_ai_messages, channels_count, recent_activity } = reports;

  const maxMessages = Math.max(...Object.values(agent_stats).map(s => s.messages), 1);

  return (
    <div className="h-full flex flex-col" data-testid="reports-panel">
      <div className="px-6 py-4 border-b border-zinc-800/60">
        <h2 className="text-lg font-semibold text-zinc-200" style={{ fontFamily: 'Syne, sans-serif' }}>
          Project Reports
        </h2>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-6 space-y-8">
          {/* Overview Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="overview-stats">
            <StatCard icon={MessageSquare} label="Total Messages" value={total_messages} />
            <StatCard icon={Users} label="Human Messages" value={total_human_messages} />
            <StatCard icon={BarChart3} label="AI Messages" value={total_ai_messages} />
            <StatCard icon={CheckCircle2} label="Channels" value={channels_count} />
          </div>

          {/* Task Stats */}
          <div className="p-5 rounded-xl bg-zinc-900/40 border border-zinc-800/60" data-testid="task-stats">
            <h3 className="text-sm font-semibold text-zinc-300 mb-4" style={{ fontFamily: 'Syne, sans-serif' }}>Task Progress</h3>
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-zinc-300" style={{ fontFamily: 'Syne, sans-serif' }}>{task_stats.todo}</div>
                <div className="text-xs text-zinc-600 font-mono">TO DO</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-amber-400" style={{ fontFamily: 'Syne, sans-serif' }}>{task_stats.in_progress}</div>
                <div className="text-xs text-zinc-600 font-mono">IN PROGRESS</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-emerald-400" style={{ fontFamily: 'Syne, sans-serif' }}>{task_stats.done}</div>
                <div className="text-xs text-zinc-600 font-mono">DONE</div>
              </div>
            </div>
            {task_stats.total > 0 && (
              <div className="mt-4 h-2 bg-zinc-800 rounded-full overflow-hidden flex">
                <div className="bg-zinc-500 h-full" style={{ width: `${(task_stats.todo / task_stats.total) * 100}%` }} />
                <div className="bg-amber-500 h-full" style={{ width: `${(task_stats.in_progress / task_stats.total) * 100}%` }} />
                <div className="bg-emerald-500 h-full" style={{ width: `${(task_stats.done / task_stats.total) * 100}%` }} />
              </div>
            )}
          </div>

          {/* Agent Contributions */}
          <div className="p-5 rounded-xl bg-zinc-900/40 border border-zinc-800/60" data-testid="agent-contributions">
            <h3 className="text-sm font-semibold text-zinc-300 mb-4" style={{ fontFamily: 'Syne, sans-serif' }}>Agent Contributions</h3>
            {Object.keys(agent_stats).length === 0 ? (
              <p className="text-xs text-zinc-600">No AI activity yet. Start a collaboration to see stats.</p>
            ) : (
              <div className="space-y-4">
                {Object.entries(agent_stats).map(([key, stats]) => (
                  <div key={key} className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold"
                          style={{ backgroundColor: AI_COLORS[key] || '#666', color: key === 'grok' ? '#09090b' : '#fff' }}>
                          {(AI_NAMES[key] || key)[0]}
                        </div>
                        <span className="text-sm text-zinc-300">{AI_NAMES[key] || key}</span>
                      </div>
                      <div className="flex items-center gap-4 text-xs text-zinc-500 font-mono">
                        <span>{stats.messages} msgs</span>
                        <span>{stats.code_blocks} code</span>
                        <span>{Math.round(stats.total_chars / 1000)}k chars</span>
                      </div>
                    </div>
                    <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                      <div className="h-full rounded-full transition-all duration-500"
                        style={{ width: `${(stats.messages / maxMessages) * 100}%`, backgroundColor: AI_COLORS[key] || '#666' }} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Recent Activity */}
          {recent_activity?.length > 0 && (
            <div className="p-5 rounded-xl bg-zinc-900/40 border border-zinc-800/60" data-testid="recent-activity">
              <h3 className="text-sm font-semibold text-zinc-300 mb-4" style={{ fontFamily: 'Syne, sans-serif' }}>Recent Activity</h3>
              <div className="space-y-2">
                {recent_activity.slice(0, 10).map((msg, i) => (
                  <div key={i} className="flex items-center gap-3 py-1.5">
                    {msg.sender_type === "ai" ? (
                      <div className="w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold flex-shrink-0"
                        style={{ backgroundColor: AI_COLORS[msg.ai_model] || '#666', color: msg.ai_model === 'grok' ? '#09090b' : '#fff' }}>
                        {(AI_NAMES[msg.ai_model] || '?')[0]}
                      </div>
                    ) : (
                      <div className="w-5 h-5 rounded-full bg-zinc-700 flex items-center justify-center text-[9px] font-bold flex-shrink-0 text-zinc-300">
                        {(msg.sender_name || 'U')[0]}
                      </div>
                    )}
                    <span className="text-xs text-zinc-300 truncate flex-1">{msg.sender_name}: {msg.content?.slice(0, 80)}</span>
                    <span className="text-[10px] text-zinc-600 font-mono flex-shrink-0">
                      {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
};

const StatCard = ({ icon: Icon, label, value }) => (
  <div className="p-4 rounded-xl bg-zinc-900/40 border border-zinc-800/60">
    <Icon className="w-4 h-4 text-zinc-500 mb-2" />
    <div className="text-2xl font-bold text-zinc-200" style={{ fontFamily: 'Syne, sans-serif' }}>{value}</div>
    <div className="text-[10px] text-zinc-600 font-mono uppercase tracking-wider">{label}</div>
  </div>
);

export default Reports;
