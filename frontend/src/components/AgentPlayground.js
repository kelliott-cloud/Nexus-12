import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { api } from "@/lib/api";
import { handleSilent } from "@/lib/errorHandler";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import {
  Play, Send, Trash2, Plus, Brain, Loader2, MessageSquare, Clock, Zap, Users
} from "lucide-react";

export default function AgentPlayground({ workspaceId }) {
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState("single"); // single | multi
  const [multiAgents, setMultiAgents] = useState([]);
  const [multiTopic, setMultiTopic] = useState("");
  const [multiRounds, setMultiRounds] = useState(3);
  const [multiConversation, setMultiConversation] = useState([]);
  const [multiRunning, setMultiRunning] = useState(false);
  const scrollRef = useRef(null);

  const fetchAgents = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/agents`);
      setAgents(res.data.agents || []);
    } catch (err) { handleSilent(err, "Playground:fetchAgents"); }
    setLoading(false);
  }, [workspaceId]);

  useEffect(() => { fetchAgents(); }, [fetchAgents]);

  const loadSessions = async (agentId) => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/agents/${agentId}/playground-sessions`);
      setSessions(res.data.sessions || []);
    } catch { /* silent */ }
  };

  const selectAgent = (agent) => {
    setSelectedAgent(agent);
    setSessionId(null);
    setMessages([]);
    loadSessions(agent.agent_id);
  };

  const loadSession = async (sid) => {
    setSessionId(sid);
    try {
      const res = await api.get(`/workspaces/${workspaceId}/agents/${selectedAgent.agent_id}/playground/${sid}`);
      setMessages(res.data.messages || []);
    } catch { toast.error("Failed to load session"); }
  };

  const newSession = () => {
    setSessionId(null);
    setMessages([]);
  };

  const sendMessage = async () => {
    if (!input.trim() || !selectedAgent || sending) return;
    const userMsg = input.trim();
    setInput("");
    setMessages(prev => [...prev, { role: "user", content: userMsg, created_at: new Date().toISOString() }]);
    setSending(true);

    try {
      const res = await api.post(`/workspaces/${workspaceId}/agents/${selectedAgent.agent_id}/playground`, {
        content: userMsg, session_id: sessionId,
      });
      setSessionId(res.data.session_id);
      setMessages(prev => [...prev, {
        role: "assistant", content: res.data.response,
        model: res.data.model, created_at: new Date().toISOString(),
      }]);
      loadSessions(selectedAgent.agent_id);
    } catch (err) {
      setMessages(prev => [...prev, { role: "assistant", content: "[Error] " + (err.response?.data?.detail || "Failed"), created_at: new Date().toISOString() }]);
    } finally { setSending(false); }
  };

  const deleteSession = async (sid) => {
    try {
      await api.delete(`/workspaces/${workspaceId}/agents/${selectedAgent.agent_id}/playground/${sid}`);
      if (sessionId === sid) { setSessionId(null); setMessages([]); }
      loadSessions(selectedAgent.agent_id);
    } catch { toast.error("Delete failed"); }
  };

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  if (loading) return <div className="flex-1 flex items-center justify-center"><Loader2 className="w-5 h-5 animate-spin text-zinc-500" /></div>;

  return (
    <div className="flex-1 flex flex-col min-h-0" data-testid="agent-playground">
      {/* Mode toggle */}
      <div className="flex-shrink-0 px-4 pt-3 pb-2">
        <div className="flex gap-0.5 bg-zinc-800 rounded-lg p-0.5 w-fit">
          <button onClick={() => setMode("single")}
            className={`px-3 py-1 rounded-md text-[10px] font-medium transition-colors ${mode === "single" ? "bg-zinc-700 text-zinc-100" : "text-zinc-500"}`}
            data-testid="pg-mode-single">Single Agent</button>
          <button onClick={() => setMode("multi")}
            className={`px-3 py-1 rounded-md text-[10px] font-medium transition-colors flex items-center gap-1 ${mode === "multi" ? "bg-zinc-700 text-zinc-100" : "text-zinc-500"}`}
            data-testid="pg-mode-multi"><Users className="w-3 h-3" /> Multi-Agent</button>
        </div>
      </div>
      <div className="flex-1 flex min-h-0">
      {mode === "single" && (<>
      {/* Agent Selector + Sessions */}
      <div className="w-56 flex-shrink-0 border-r border-zinc-800/60 flex flex-col">
        <div className="p-3 border-b border-zinc-800/40">
          <p className="text-[10px] font-semibold text-zinc-500 uppercase">Select Agent</p>
        </div>
        <ScrollArea className="flex-1">
          <div className="p-2 space-y-1">
            {agents.map(a => (
              <button key={a.agent_id} onClick={() => selectAgent(a)}
                className={`w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-left transition-colors ${selectedAgent?.agent_id === a.agent_id ? "bg-cyan-500/10 border border-cyan-500/30" : "hover:bg-zinc-800/40 border border-transparent"}`}
                data-testid={`pg-agent-${a.agent_id}`}>
                <div className="w-6 h-6 rounded flex items-center justify-center text-[9px] font-bold text-white" style={{ backgroundColor: a.color || "#6366f1" }}>
                  {a.name?.slice(0, 2).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-zinc-300 truncate">{a.name}</p>
                  <p className="text-[9px] text-zinc-600">{a.base_model} / {a.skills?.length || 0} skills</p>
                </div>
              </button>
            ))}
            {agents.length === 0 && <p className="text-xs text-zinc-600 text-center py-4">No agents. Create one in the Studio tab.</p>}
          </div>
        </ScrollArea>

        {selectedAgent && (
          <div className="border-t border-zinc-800/40">
            <div className="p-2 flex items-center justify-between">
              <p className="text-[9px] text-zinc-600">Sessions</p>
              <Button size="sm" variant="ghost" onClick={newSession} className="h-5 w-5 p-0 text-zinc-500" data-testid="pg-new-session"><Plus className="w-3 h-3" /></Button>
            </div>
            <ScrollArea className="max-h-32">
              <div className="px-2 pb-2 space-y-0.5">
                {sessions.map(s => (
                  <div key={s.session_id} className={`flex items-center gap-1 px-2 py-1 rounded text-[9px] cursor-pointer group ${sessionId === s.session_id ? "bg-zinc-800 text-zinc-300" : "text-zinc-600 hover:bg-zinc-800/40"}`} onClick={() => loadSession(s.session_id)} data-testid={`pg-session-${s.session_id}`}>
                    <MessageSquare className="w-2.5 h-2.5 flex-shrink-0" />
                    <span className="flex-1 truncate">{s.message_count} msgs</span>
                    <Button variant="ghost" size="sm" onClick={e => { e.stopPropagation(); deleteSession(s.session_id); }} className="h-4 w-4 p-0 opacity-0 group-hover:opacity-100 text-zinc-600 hover:text-red-400">
                      <Trash2 className="w-2.5 h-2.5" />
                    </Button>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </div>
        )}
      </div>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col min-h-0">
        {!selectedAgent ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <Play className="w-10 h-10 text-zinc-700 mx-auto mb-2" />
              <p className="text-sm text-zinc-400">Select an agent to start testing</p>
              <p className="text-xs text-zinc-600 mt-1">The playground uses the agent's full configuration including skills, personality, guardrails, and training data</p>
            </div>
          </div>
        ) : (
          <>
            <div className="px-4 py-2.5 border-b border-zinc-800/40 flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center text-[10px] font-bold text-white" style={{ backgroundColor: selectedAgent.color || "#6366f1" }}>
                {selectedAgent.name?.slice(0, 2).toUpperCase()}
              </div>
              <div>
                <p className="text-sm font-medium text-zinc-200">{selectedAgent.name}</p>
                <div className="flex gap-2 text-[9px] text-zinc-600">
                  <span>{selectedAgent.base_model}</span>
                  <span>{selectedAgent.skills?.length || 0} skills</span>
                  {sessionId && <span className="text-cyan-500">Session active</span>}
                </div>
              </div>
              <Badge variant="secondary" className="ml-auto bg-amber-500/10 text-amber-400 text-[9px]">
                <Zap className="w-2.5 h-2.5 mr-0.5" /> Sandbox
              </Badge>
            </div>

            <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
              {messages.length === 0 && (
                <div className="text-center py-12">
                  <Brain className="w-8 h-8 text-zinc-700 mx-auto mb-2" />
                  <p className="text-xs text-zinc-500">Send a message to test this agent</p>
                </div>
              )}
              {messages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`} data-testid={`pg-msg-${i}`}>
                  <div className={`max-w-[75%] rounded-xl px-3.5 py-2.5 ${msg.role === "user" ? "bg-cyan-500/15 text-cyan-100" : "bg-zinc-800/60 text-zinc-300"}`}>
                    <p className="text-xs whitespace-pre-wrap">{msg.content}</p>
                    {msg.model && <p className="text-[8px] text-zinc-600 mt-1">{msg.model}</p>}
                  </div>
                </div>
              ))}
              {sending && (
                <div className="flex justify-start">
                  <div className="bg-zinc-800/60 rounded-xl px-4 py-3">
                    <Loader2 className="w-4 h-4 animate-spin text-zinc-500" />
                  </div>
                </div>
              )}
            </div>

            <div className="p-3 border-t border-zinc-800/40">
              <div className="flex gap-2">
                <Input value={input} onChange={e => setInput(e.target.value)} placeholder="Type a message to test the agent..."
                  className="bg-zinc-950 border-zinc-800 text-zinc-200 text-xs flex-1"
                  onKeyDown={e => e.key === "Enter" && !e.shiftKey && sendMessage()}
                  disabled={sending}
                  data-testid="pg-input" />
                <Button onClick={sendMessage} disabled={sending || !input.trim()} className="bg-cyan-600 hover:bg-cyan-700 text-white" data-testid="pg-send-btn">
                  <Send className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
      </>)}

      {/* Multi-Agent Sandbox Panel */}
      {mode === "multi" && (
        <div className="flex-1 flex flex-col bg-zinc-950/50 rounded-xl border border-zinc-800/40 overflow-hidden">
          <div className="p-4 border-b border-zinc-800/40">
            <h3 className="text-sm font-semibold text-zinc-200 flex items-center gap-2">
              <Users className="w-4 h-4 text-violet-400" /> Agent-to-Agent Sandbox
            </h3>
            <p className="text-[10px] text-zinc-500 mt-0.5">Select 2-3 agents and a topic — watch them discuss</p>
          </div>

          <div className="p-4 space-y-3">
            <div>
              <label className="text-[10px] text-zinc-500 font-medium">Select Agents (2-3)</label>
              <div className="grid grid-cols-2 gap-1.5 mt-1">
                {agents.map(a => {
                  const selected = multiAgents.includes(a.agent_id);
                  return (
                    <button key={a.agent_id}
                      onClick={() => {
                        if (selected) setMultiAgents(p => p.filter(id => id !== a.agent_id));
                        else if (multiAgents.length < 3) setMultiAgents(p => [...p, a.agent_id]);
                      }}
                      className={`flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-left transition-colors border text-[10px] ${selected ? "bg-violet-500/10 border-violet-500/30 text-violet-300" : "bg-zinc-900/40 border-zinc-800/40 text-zinc-500"}`}
                      data-testid={`multi-select-${a.agent_id}`}>
                      <div className="w-4 h-4 rounded flex items-center justify-center text-[7px] font-bold text-white" style={{ backgroundColor: a.color || "#6366f1" }}>
                        {a.name?.slice(0, 2).toUpperCase()}
                      </div>
                      {a.name}
                    </button>
                  );
                })}
              </div>
            </div>

            <Input value={multiTopic} onChange={e => setMultiTopic(e.target.value)}
              placeholder="Discussion topic..."
              className="bg-zinc-950 border-zinc-800 text-zinc-200 text-xs"
              data-testid="multi-topic-input" />

            <div className="flex items-center gap-2">
              <label className="text-[10px] text-zinc-500">Rounds:</label>
              <Input type="number" value={multiRounds} onChange={e => setMultiRounds(Math.min(5, Math.max(1, parseInt(e.target.value) || 1)))}
                className="bg-zinc-950 border-zinc-800 text-zinc-200 text-xs w-16 h-7" />
              <Button onClick={async () => {
                if (multiAgents.length < 2 || !multiTopic.trim()) return;
                setMultiRunning(true);
                setMultiConversation([]);
                try {
                  const res = await api.post(`/workspaces/${workspaceId}/playground/multi-agent`, {
                    agent_ids: multiAgents, topic: multiTopic, rounds: multiRounds
                  });
                  setMultiConversation(res.data.conversation || []);
                  toast.success(`${res.data.rounds} rounds completed`);
                } catch (err) { toast.error("Multi-agent session failed"); handleSilent(err, "PG:multi"); }
                setMultiRunning(false);
              }} disabled={multiRunning || multiAgents.length < 2 || !multiTopic.trim()}
                className="bg-violet-600 hover:bg-violet-700 text-white text-xs gap-1 flex-1" data-testid="start-multi-btn">
                {multiRunning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                {multiRunning ? "Running..." : "Start Discussion"}
              </Button>
            </div>
          </div>

          <ScrollArea className="flex-1 p-4">
            <div className="space-y-2">
              {multiConversation.filter(m => m.role !== "system").map((m, i) => {
                const agentInfo = agents.find(a => a.name === m.agent);
                return (
                  <div key={i} className="p-2.5 rounded-lg bg-zinc-900/40 border border-zinc-800/30" data-testid={`multi-msg-${i}`}>
                    <div className="flex items-center gap-2 mb-1">
                      {agentInfo && (
                        <div className="w-4 h-4 rounded flex items-center justify-center text-[7px] font-bold text-white" style={{ backgroundColor: agentInfo.color || "#6366f1" }}>
                          {agentInfo.name?.slice(0, 2).toUpperCase()}
                        </div>
                      )}
                      <span className="text-[10px] font-medium text-zinc-300">{m.agent}</span>
                      {m.round && <Badge variant="secondary" className="text-[7px] bg-zinc-800 text-zinc-500">Round {m.round}</Badge>}
                    </div>
                    <p className="text-xs text-zinc-400 whitespace-pre-wrap">{m.content}</p>
                  </div>
                );
              })}
            </div>
          </ScrollArea>
        </div>
      )}
      </div>
    </div>
  );
}
