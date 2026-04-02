import { useState, useEffect, useRef } from "react";
import { useConfirm } from "@/components/ConfirmDialog";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { 
  Plus, X, Send, Loader2, Bot, ChevronUp, ChevronDown, 
  History, CheckCircle, PauseCircle, PlayCircle, Trash2,
  MessageSquare, Minimize2, Maximize2
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/App";

const AI_AGENTS = [
  { key: "claude", name: "Claude", color: "#D97757" },
  { key: "chatgpt", name: "ChatGPT", color: "#10A37F" },
  { key: "gemini", name: "Gemini", color: "#4285F4" },
  { key: "perplexity", name: "Perplexity", color: "#20B2AA" },
  { key: "mistral", name: "Mistral", color: "#FF7000" },
  { key: "cohere", name: "Cohere", color: "#39594D" },
  { key: "groq", name: "Groq", color: "#F55036" },
  { key: "deepseek", name: "DeepSeek", color: "#4D6BFE" },
  { key: "grok", name: "Grok", color: "#F5F5F5" },
  { key: "mercury", name: "Mercury 2", color: "#00D4FF" },
  { key: "pi", name: "Pi", color: "#FF6B35" },
  { key: "manus", name: "Manus", color: "#6C5CE7" },
  { key: "qwen", name: "Qwen", color: "#615EFF" },
  { key: "kimi", name: "Kimi", color: "#000000" },
  { key: "llama", name: "Llama", color: "#0467DF" },
  { key: "glm", name: "GLM", color: "#3D5AFE" },
  { key: "cursor", name: "Cursor", color: "#00E5A0" },
  { key: "notebooklm", name: "NotebookLM", color: "#FBBC04" },
  { key: "copilot", name: "GitHub Copilot", color: "#171515" },
];

export default function TaskPanel({ workspaceId, embedded = false }) {
  const { confirm: confirmAction, ConfirmDialog: ConfirmDlg } = useConfirm();
  const [isExpanded, setIsExpanded] = useState(embedded ? true : false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [taskSessions, setTaskSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [nexusAgents, setNexusAgents] = useState([]);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [historyDialogOpen, setHistoryDialogOpen] = useState(false);
  const [showQueue, setShowQueue] = useState(false);
  const [queue, setQueue] = useState({ queued: [], completed: [] });
  
  // Create form
  const [newTitle, setNewTitle] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newAgent, setNewAgent] = useState("");
  const [newPrompt, setNewPrompt] = useState("");
  const [newDueDate, setNewDueDate] = useState("");
  const [newScheduled, setNewScheduled] = useState(false);
  const [creating, setCreating] = useState(false);
  
  // Draggable position
  const [panelY, setPanelY] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const dragRef = useRef(null);
  
  const messagesEndRef = useRef(null);
  const pollRef = useRef(null);

  useEffect(() => {
    fetchTaskSessions();
    fetchNexusAgents();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [workspaceId]);

  useEffect(() => {
    if (activeSession) {
      fetchMessages();
      startPolling();
    } else {
      setMessages([]);
      if (pollRef.current) clearInterval(pollRef.current);
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [activeSession?.session_id]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const startPolling = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(() => {
      if (activeSession) {
        fetchMessages();
        checkStatus();
      }
    }, 2000);
  };

  const fetchTaskSessions = async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/task-sessions`);
      setTaskSessions(res.data);
    } catch (err) { handleSilent(err, "TaskPanel:op1"); }
  };

  const fetchNexusAgents = async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/agents`);
      setNexusAgents(res.data.agents || []);
    } catch (err) { handleSilent(err, "TaskPanel:op2"); }
  };

  const fetchMessages = async () => {
    if (!activeSession) return;
    try {
      const res = await api.get(`/task-sessions/${activeSession.session_id}/messages`);
      setMessages(res.data);
    } catch (err) { handleSilent(err, "TaskPanel:op3"); }
  };

  const checkStatus = async () => {
    if (!activeSession) return;
    try {
      const res = await api.get(`/task-sessions/${activeSession.session_id}/status`);
      setIsThinking(res.data.is_thinking);
    } catch (err) { handleSilent(err, "TaskPanel:op4"); }
  };

  const createTask = async () => {
    if (!newTitle.trim() || !newAgent || !newPrompt.trim()) {
      toast.error("Please fill all required fields");
      return;
    }
    setCreating(true);
    try {
      const res = await api.post(`/workspaces/${workspaceId}/task-sessions`, {
        title: newTitle,
        description: newDesc,
        assigned_agent: newAgent,
        initial_prompt: newPrompt,
        due_date: newDueDate || null,
        scheduled: newScheduled,
      });
      setTaskSessions([res.data, ...taskSessions]);
      if (!newScheduled) setActiveSession(res.data);
      setCreateDialogOpen(false);
      setNewTitle(""); setNewDesc(""); setNewAgent(""); setNewPrompt(""); setNewDueDate(""); setNewScheduled(false);
      setIsExpanded(true);
      toast.success(newScheduled ? "Task queued" : "Task created");
      
      // Trigger agent to respond (only if not scheduled for later)
      if (!newScheduled) {
        await api.post(`/task-sessions/${res.data.session_id}/run`);
      }
      fetchQueue();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to create task");
    }
    setCreating(false);
  };

  const fetchQueue = async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/task-queue`);
      setQueue(res.data);
    } catch (err) { handleSilent(err, "TaskPanel:op5"); }
  };

  useEffect(() => { if (showQueue) fetchQueue(); }, [showQueue, workspaceId]);

  // Drag handling
  const handleDragStart = (e) => {
    setIsDragging(true);
    const startY = e.clientY || e.touches?.[0]?.clientY;
    const startPos = panelY || (window.innerHeight - 500);
    
    const handleMove = (ev) => {
      const y = ev.clientY || ev.touches?.[0]?.clientY;
      const newY = Math.max(100, Math.min(window.innerHeight - 200, startPos + (y - startY)));
      setPanelY(newY);
    };
    const handleEnd = () => {
      setIsDragging(false);
      document.removeEventListener("mousemove", handleMove);
      document.removeEventListener("mouseup", handleEnd);
      document.removeEventListener("touchmove", handleMove);
      document.removeEventListener("touchend", handleEnd);
    };
    document.addEventListener("mousemove", handleMove);
    document.addEventListener("mouseup", handleEnd);
    document.addEventListener("touchmove", handleMove);
    document.addEventListener("touchend", handleEnd);
  };



  const sendMessage = async () => {
    if (!input.trim() || !activeSession || sending) return;
    setSending(true);
    try {
      await api.post(`/task-sessions/${activeSession.session_id}/messages`, {
        content: input,
      });
      setInput("");
      fetchMessages();
      
      // Trigger agent to respond
      await api.post(`/task-sessions/${activeSession.session_id}/run`);
    } catch (err) {
      toast.error("Failed to send message");
    }
    setSending(false);
  };

  const completeTask = async (session) => {
    try {
      const res = await api.put(`/task-sessions/${session.session_id}/complete`);
      setTaskSessions(taskSessions.map(s => s.session_id === session.session_id ? res.data : s));
      if (activeSession?.session_id === session.session_id) {
        setActiveSession(res.data);
      }
      toast.success("Task completed");
    } catch (err) {
      toast.error("Failed to complete task");
    }
  };

  const deleteTask = async (session) => {
    const _ok = await confirmAction("Delete Task", `Delete "${session.title}"? This cannot be undone.`); if (!_ok) return;
    try {
      await api.delete(`/task-sessions/${session.session_id}`);
      setTaskSessions(taskSessions.filter(s => s.session_id !== session.session_id));
      if (activeSession?.session_id === session.session_id) {
        setActiveSession(null);
      }
      toast.success("Task deleted");
    } catch (err) {
      toast.error("Failed to delete task");
    }
  };

  const activeSessions = taskSessions.filter(s => s.status === "active");
  const completedSessions = taskSessions.filter(s => s.status === "completed");

  if (isMinimized && !embedded) {
    return (
      <div className="fixed right-4 top-1/2 -translate-y-1/2 z-50">
        <Button
          onClick={() => setIsMinimized(false)}
          className="bg-zinc-800 hover:bg-zinc-700 text-zinc-100 shadow-lg rounded-full p-3"
        >
          <Bot className="w-5 h-5 mr-2" />
          Tasks ({activeSessions.length})
          <Maximize2 className="w-4 h-4 ml-2" />
        </Button>
      </div>
    );
  }

  return (
    <div 
      className={embedded 
        ? "h-full flex flex-col bg-zinc-900"
        : `fixed right-0 z-50 transition-all duration-300 ${isExpanded ? 'w-[420px] h-[70vh]' : 'w-[360px]'}`
      }
      style={embedded ? {} : { top: panelY ? `${panelY}px` : '50%', transform: panelY ? 'none' : 'translateY(-50%)' }}
      data-testid="task-panel"
    >
      {/* Task tabs bar */}
      <div className={embedded ? "flex flex-col h-full" : "bg-zinc-900 border-t border-l border-b border-zinc-800 rounded-l-xl shadow-2xl"}>
        {/* Drag handle - only for floating mode */}
        {!embedded && (
        <div
          ref={dragRef}
          onMouseDown={handleDragStart}
          onTouchStart={handleDragStart}
          className="flex items-center justify-center py-1 cursor-grab active:cursor-grabbing border-b border-zinc-800/40"
          data-testid="task-panel-drag"
        >
          <div className="w-8 h-1 rounded-full bg-zinc-700" />
        </div>
        )}
        {/* Header */}
        <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800">
          <div className="flex items-center gap-2">
            <Bot className="w-4 h-4 text-amber-400" />
            <span className="text-sm font-medium text-zinc-200">Task Sessions</span>
            <Badge className="bg-zinc-800 text-zinc-400 text-[10px]">{activeSessions.length}</Badge>
          </div>
          <div className="flex items-center gap-1">
            {/* Queue toggle */}
            <button
              onClick={() => setShowQueue(!showQueue)}
              className={`p-1.5 rounded text-xs font-medium ${showQueue ? "bg-amber-500/20 text-amber-400" : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"}`}
              title="Task Queue"
              data-testid="queue-toggle"
            >
              Q
            </button>
            <Dialog open={historyDialogOpen} onOpenChange={setHistoryDialogOpen}>
              <DialogTrigger asChild>
                <button className="p-1.5 rounded text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800" title="View task history">
                  <History className="w-4 h-4" />
                </button>
              </DialogTrigger>
              <DialogContent className="bg-zinc-900 border-zinc-800 max-w-md max-h-[70vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle className="text-zinc-100">Task History</DialogTitle>
                </DialogHeader>
                <div className="space-y-2 mt-4">
                  {completedSessions.length === 0 ? (
                    <p className="text-sm text-zinc-500 text-center py-4">No completed tasks yet</p>
                  ) : (
                    completedSessions.map(session => (
                      <div 
                        key={session.session_id}
                        className="p-3 rounded-lg bg-zinc-950 border border-zinc-800 cursor-pointer hover:border-zinc-700"
                        onClick={() => {
                          setActiveSession(session);
                          setIsExpanded(true);
                          setHistoryDialogOpen(false);
                        }}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-sm text-zinc-200">{session.title}</span>
                          <Badge className="bg-emerald-500/20 text-emerald-400 text-[9px]">
                            <CheckCircle className="w-3 h-3 mr-1" />
                            Done
                          </Badge>
                        </div>
                        <p className="text-xs text-zinc-500 mt-1">{session.message_count} messages</p>
                      </div>
                    ))
                  )}
                </div>
              </DialogContent>
            </Dialog>
            <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
              <DialogTrigger asChild>
                <button className="p-1.5 rounded text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800" title="Create new task">
                  <Plus className="w-4 h-4" />
                </button>
              </DialogTrigger>
              <DialogContent className="bg-zinc-900 border-zinc-800 max-w-md">
                <DialogHeader>
                  <DialogTitle className="text-zinc-100 flex items-center gap-2">
                    <Bot className="w-5 h-5 text-amber-400" />
                    New Task
                  </DialogTitle>
                </DialogHeader>
                <div className="space-y-4 mt-4">
                  <div>
                    <label className="text-xs text-zinc-400 mb-1 block">Task Title *</label>
                    <Input
                      value={newTitle}
                      onChange={(e) => setNewTitle(e.target.value)}
                      placeholder="e.g., Review authentication code"
                      className="bg-zinc-950 border-zinc-800"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-zinc-400 mb-1 block">Description</label>
                    <Input
                      value={newDesc}
                      onChange={(e) => setNewDesc(e.target.value)}
                      placeholder="Brief description of the task"
                      className="bg-zinc-950 border-zinc-800"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-zinc-400 mb-1 block">Assign Agent *</label>
                    <Select value={newAgent} onValueChange={setNewAgent}>
                      <SelectTrigger className="bg-zinc-950 border-zinc-800">
                        <SelectValue placeholder="Select an AI agent" />
                      </SelectTrigger>
                      <SelectContent className="bg-zinc-900 border-zinc-800 max-h-60">
                        {nexusAgents.length > 0 && (
                          <>
                            <div className="px-2 py-1 text-[10px] text-amber-400 uppercase">Your Agents</div>
                            {nexusAgents.map(agent => (
                              <SelectItem key={agent.agent_id} value={agent.agent_id}>
                                <div className="flex items-center gap-2">
                                  <div className="w-3 h-3 rounded" style={{ backgroundColor: agent.color }} />
                                  {agent.name}
                                </div>
                              </SelectItem>
                            ))}
                            <div className="border-t border-zinc-800 my-1" />
                          </>
                        )}
                        <div className="px-2 py-1 text-[10px] text-zinc-500 uppercase">Built-in Models</div>
                        {AI_AGENTS.map(agent => (
                          <SelectItem key={agent.key} value={agent.key}>
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: agent.color }} />
                              {agent.name}
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <label className="text-xs text-zinc-400 mb-1 block">Initial Prompt *</label>
                    <Textarea
                      value={newPrompt}
                      onChange={(e) => setNewPrompt(e.target.value)}
                      placeholder="Describe what you want the agent to do..."
                      className="bg-zinc-950 border-zinc-800 min-h-[100px]"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-zinc-400 mb-1 block">Due Date & Time</label>
                    <Input
                      type="datetime-local"
                      value={newDueDate}
                      onChange={(e) => setNewDueDate(e.target.value)}
                      className="bg-zinc-950 border-zinc-800 text-zinc-300"
                      data-testid="task-due-date"
                    />
                  </div>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" checked={newScheduled} onChange={(e) => setNewScheduled(e.target.checked)} className="accent-amber-500" data-testid="task-scheduled" />
                    <span className="text-xs text-zinc-400">Schedule — queue and auto-run at due time</span>
                  </label>
                  <Button
                    onClick={createTask}
                    disabled={creating || !newTitle.trim() || !newAgent || !newPrompt.trim()}
                    className="w-full bg-zinc-100 text-zinc-900 hover:bg-zinc-200"
                  >
                    {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : "Create Task"}
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
            <button 
              onClick={() => setIsExpanded(!isExpanded)}
              className="p-1.5 rounded text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
            >
              {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
            </button>
            <button 
              onClick={() => setIsMinimized(true)}
              className="p-1.5 rounded text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
            >
              <Minimize2 className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Queue View */}
        {showQueue && (
          <div className="overflow-y-auto" style={{ maxHeight: isExpanded ? "60vh" : "300px" }}>
            <div className="p-2">
              <p className="text-[9px] text-zinc-500 uppercase tracking-wider font-semibold px-2 mb-1">Queued / Active</p>
              {queue.queued.length === 0 ? (
                <p className="text-xs text-zinc-600 px-2 py-3 text-center">No tasks in queue</p>
              ) : queue.queued.map(t => (
                <div key={t.session_id} className="px-2 py-2 rounded-lg hover:bg-zinc-800/40 mb-0.5" data-testid={`queue-item-${t.session_id}`}>
                  <div className="flex items-center gap-2">
                    <div className="w-5 h-5 rounded-full flex items-center justify-center text-[8px] font-bold" style={{ backgroundColor: t.agent?.color || "#666", color: "#fff" }}>
                      {(t.agent?.name || "?")[0]}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-zinc-200 truncate">{t.title}</p>
                      <div className="flex items-center gap-2">
                        <span className={`text-[9px] px-1 py-0.5 rounded ${t.status === "queued" ? "bg-amber-500/15 text-amber-400" : "bg-blue-500/15 text-blue-400"}`}>{t.status}</span>
                        {t.due_date && <span className="text-[9px] text-zinc-600">{new Date(t.due_date).toLocaleString()}</span>}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
              {queue.completed.length > 0 && (
                <>
                  <p className="text-[9px] text-zinc-500 uppercase tracking-wider font-semibold px-2 mb-1 mt-3">Recently Completed</p>
                  {queue.completed.map(t => (
                    <div key={t.session_id} className="px-2 py-2 rounded-lg hover:bg-zinc-800/40 mb-0.5 opacity-60" data-testid={`completed-item-${t.session_id}`}>
                      <div className="flex items-center gap-2">
                        <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <p className="text-xs text-zinc-400 truncate">{t.title}</p>
                          <span className="text-[9px] text-zinc-600">{t.completed_at ? new Date(t.completed_at).toLocaleString() : ""}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </>
              )}
            </div>
          </div>
        )}

        {/* Task tabs */}
        {!showQueue && activeSessions.length > 0 && (
          <div className="flex items-center gap-1 px-2 py-1.5 overflow-x-auto border-b border-zinc-800">
            {activeSessions.map(session => (
              <div
                key={session.session_id}
                onClick={() => {
                  setActiveSession(session);
                  setIsExpanded(true);
                }}
                className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs whitespace-nowrap transition-colors cursor-pointer ${
                  activeSession?.session_id === session.session_id
                    ? 'bg-zinc-800 text-zinc-100'
                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50'
                }`}
              >
                <div 
                  className="w-2 h-2 rounded-full" 
                  style={{ backgroundColor: session.agent.color }}
                />
                <span className="max-w-[100px] truncate">{session.title}</span>
                <span
                  onClick={(e) => { e.stopPropagation(); completeTask(session); }}
                  className="ml-1 p-0.5 rounded hover:bg-zinc-700 cursor-pointer"
                  title="Complete task"
                >
                  <CheckCircle className="w-3 h-3 text-emerald-400" />
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Expanded content */}
        {!showQueue && isExpanded && activeSession && (
          <div className="flex flex-col h-[calc(70vh-60px)]">
            {/* Task header */}
            <div className="px-3 py-2 border-b border-zinc-800 bg-zinc-950/50">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div 
                    className="w-6 h-6 rounded flex items-center justify-center text-[10px] font-bold text-white"
                    style={{ backgroundColor: activeSession.agent.color }}
                  >
                    {activeSession.agent.avatar}
                  </div>
                  <div>
                    <h4 className="text-sm font-medium text-zinc-200">{activeSession.title}</h4>
                    <p className="text-[10px] text-zinc-500">{activeSession.agent.name}</p>
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  {activeSession.status === "completed" ? (
                    <Badge className="bg-emerald-500/20 text-emerald-400 text-[9px]">Completed</Badge>
                  ) : (
                    <button
                      onClick={() => completeTask(activeSession)}
                      className="p-1 rounded text-emerald-400 hover:bg-zinc-800"
                      title="Mark as complete"
                    >
                      <CheckCircle className="w-4 h-4" />
                    </button>
                  )}
                  <button
                    onClick={() => deleteTask(activeSession)}
                    className="p-1 rounded text-red-400 hover:bg-zinc-800"
                    title="Delete task"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-3 space-y-3">
              {messages.map(msg => (
                <div 
                  key={msg.message_id}
                  className={`flex ${msg.sender_type === 'human' ? 'justify-end' : 'justify-start'}`}
                >
                  <div className={`max-w-[85%] rounded-lg px-3 py-2 ${
                    msg.sender_type === 'human' 
                      ? 'bg-zinc-700 text-zinc-100' 
                      : msg.sender_type === 'system'
                        ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                        : 'bg-zinc-800 text-zinc-200'
                  }`}>
                    {msg.sender_type === 'ai' && (
                      <p className="text-[10px] text-zinc-500 mb-1">{msg.sender_name}</p>
                    )}
                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                  </div>
                </div>
              ))}
              {isThinking && (
                <div className="flex justify-start">
                  <div className="bg-zinc-800 rounded-lg px-3 py-2 flex items-center gap-2">
                    <Loader2 className="w-3 h-3 animate-spin text-zinc-400" />
                    <span className="text-xs text-zinc-400">Thinking...</span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            {activeSession.status === "active" && (
              <div className="p-3 border-t border-zinc-800">
                <div className="flex gap-2">
                  <Input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => {
                      // Only submit on Ctrl+Enter or Cmd+Enter (like Slack)
                      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                        e.preventDefault();
                        sendMessage();
                      }
                    }}
                    placeholder="Type message... (Ctrl+Enter to send)"
                    className="bg-zinc-950 border-zinc-800 text-sm"
                    disabled={sending}
                  />
                  <Button
                    onClick={sendMessage}
                    disabled={!input.trim() || sending}
                    size="sm"
                    className="bg-zinc-100 text-zinc-900 hover:bg-zinc-200"
                  >
                    {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                  </Button>
                </div>
                <p className="text-[10px] text-zinc-600 mt-1 text-right">Ctrl+Enter to send</p>
              </div>
            )}
          </div>
        )}

        {/* Empty state when expanded but no active session */}
        {!showQueue && isExpanded && !activeSession && (
          <div className="h-[300px] flex items-center justify-center">
            <div className="text-center">
              <MessageSquare className="w-8 h-8 text-zinc-600 mx-auto mb-2" />
              <p className="text-sm text-zinc-400">No active task selected</p>
              <p className="text-xs text-zinc-600 mt-1">Create a new task or select from tabs</p>
            </div>
          </div>
        )}
      </div>
    <ConfirmDlg />
    </div>
    );
}
