import { useState, useEffect, useCallback } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Plus, Trash2, CheckCircle2, Clock, Circle, AlertCircle,
  FolderKanban, User, Bot, Play, Pause, Ban, ChevronDown,
  ChevronRight, Filter, Zap, GitBranch, Link2, Milestone, X,
  ArrowRight, ArrowLeft, Activity,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/App";

const STATUS_CONFIG = {
  todo: { label: "To Do", icon: Circle, color: "text-zinc-400", bg: "bg-zinc-800/40", border: "border-zinc-700/30" },
  in_progress: { label: "In Progress", icon: Clock, color: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/20" },
  review: { label: "Review", icon: AlertCircle, color: "text-blue-400", bg: "bg-blue-500/10", border: "border-blue-500/20" },
  done: { label: "Done", icon: CheckCircle2, color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/20" },
  on_hold: { label: "On Hold", icon: Pause, color: "text-orange-400", bg: "bg-orange-500/10", border: "border-orange-500/20" },
  wont_do: { label: "Won't Do", icon: Ban, color: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/20" },
};

const PRIORITY_CONFIG = {
  critical: { label: "Critical", color: "text-red-400", bg: "bg-red-500/15" },
  high: { label: "High", color: "text-orange-400", bg: "bg-orange-500/15" },
  medium: { label: "Medium", color: "text-amber-400", bg: "bg-amber-500/15" },
  low: { label: "Low", color: "text-zinc-400", bg: "bg-zinc-700" },
};

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

const AGENT_MAP = Object.fromEntries(AI_AGENTS.map(a => [a.key, a]));

function AssigneeBadge({ task }) {
  const assignee = task.assigned_to || task.assignee_id || task.assignee_name;
  const type = task.assigned_type || task.assignee_type || "human";
  if (!assignee) return <span className="text-[10px] text-zinc-600">Unassigned</span>;

  const agent = AGENT_MAP[assignee];
  if (agent || type === "ai") {
    return (
      <div className="flex items-center gap-1">
        <Bot className="w-3 h-3 text-zinc-500" />
        <div className="w-3.5 h-3.5 rounded-full flex items-center justify-center text-[7px] font-bold"
          style={{ backgroundColor: agent?.color || "#666", color: agent?.color === '#F5F5F5' ? '#09090b' : '#fff' }}>
          {(agent?.name || assignee)[0]}
        </div>
        <span className="text-[10px] text-zinc-400">{agent?.name || assignee}</span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-1">
      <User className="w-3 h-3 text-zinc-500" />
      <span className="text-[10px] text-zinc-400">{task.assignee_name || assignee}</span>
    </div>
  );
}

function TaskCard({ task, onMove, onDelete, onPromptAgent, isProjectTask, onClickDetail }) {
  const status = task.status || "todo";
  const priority = task.priority || "medium";
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.todo;
  const priCfg = PRIORITY_CONFIG[priority] || PRIORITY_CONFIG.medium;
  const isAI = (task.assigned_type === "ai" || task.assignee_type === "ai") && (task.assigned_to || task.assignee_id);
  const taskId = task.task_id;

  return (
    <div
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData("taskId", taskId);
        e.dataTransfer.setData("projectId", isProjectTask ? (task.project_id || "") : "");
        e.dataTransfer.setData("isProject", isProjectTask ? "1" : "0");
        e.currentTarget.style.opacity = "0.4";
      }}
      onDragEnd={(e) => { e.currentTarget.style.opacity = "1"; }}
      className={`p-3 rounded-lg border ${cfg.border} ${cfg.bg} hover:border-zinc-600 transition-colors group cursor-grab active:cursor-grabbing border-l-2`}
      style={{ borderLeftColor: priority === "critical" ? "#ef4444" : priority === "high" ? "#f97316" : priority === "medium" ? "#eab308" : "#71717a" }}
      data-testid={`task-card-${taskId}`}
    >
      {/* Header: title + actions */}
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <button onClick={() => onClickDetail(taskId)} className="text-sm font-medium text-zinc-200 line-clamp-2 text-left hover:text-emerald-400 transition-colors cursor-pointer" data-testid={`task-title-${taskId}`}>
          {task.title}
        </button>
        <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
          {isAI && status === "todo" && (
            <button
              onClick={() => onPromptAgent(taskId)}
              className="p-1 rounded text-emerald-500 hover:bg-emerald-500/10"
              title="Prompt agent to work on this"
              data-testid={`prompt-agent-${taskId}`}
            >
              <Zap className="w-3 h-3" />
            </button>
          )}
          <button
            onClick={() => onDelete(taskId, isProjectTask ? task.project_id : null)}
            className="p-1 rounded text-zinc-600 hover:text-red-400"
            data-testid={`delete-task-${taskId}`}
          >
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      </div>

      {/* Description */}
      {task.description && (
        <p className="text-xs text-zinc-500 mb-2 line-clamp-2">{task.description}</p>
      )}

      {/* Meta row: status, priority, assignee */}
      <div className="flex items-center gap-2 flex-wrap">
        <Badge className={`text-[9px] px-1.5 py-0 h-4 ${cfg.bg} ${cfg.color} border-0`}>
          {cfg.label}
        </Badge>
        <Badge className={`text-[9px] px-1.5 py-0 h-4 ${priCfg.bg} ${priCfg.color} border-0`}>
          {priCfg.label}
        </Badge>
        {task.item_type && task.item_type !== "task" && (
          <Badge className="text-[9px] px-1.5 py-0 h-4 bg-zinc-800 text-zinc-400 border-0">{task.item_type}</Badge>
        )}
        <div className="ml-auto">
          <AssigneeBadge task={task} />
        </div>
      </div>

      {/* Progress bar */}
      {(task.subtask_total > 0 || task.progress > 0) && (
        <div className="flex items-center gap-2 mt-1.5">
          <div className="flex-1 h-1.5 rounded-full bg-zinc-800 overflow-hidden">
            <div className="h-full rounded-full transition-all" style={{
              width: `${task.progress || 0}%`,
              backgroundColor: (task.progress || 0) === 100 ? "#10b981" : (task.progress || 0) > 50 ? "#3b82f6" : "#f59e0b",
            }} />
          </div>
          <span className="text-[9px] text-zinc-600 flex-shrink-0">
            {task.subtask_total > 0 ? `${task.subtasks_done}/${task.subtask_total}` : `${task.progress || 0}%`}
          </span>
        </div>
      )}

      {/* Quick status move buttons */}
      <div className="flex items-center gap-1 mt-2 pt-2 border-t border-zinc-800/30">
        {Object.entries(STATUS_CONFIG).filter(([s]) => s !== status).slice(0, 3).map(([s, c]) => {
          const Icon = c.icon;
          return (
            <button
              key={s}
              onClick={() => onMove(taskId, s, isProjectTask ? task.project_id : null)}
              className={`text-[9px] px-1.5 py-0.5 rounded flex items-center gap-1 ${c.color} hover:${c.bg} transition-colors`}
              title={`Move to ${c.label}`}
              data-testid={`move-task-${taskId}-${s}`}
            >
              <Icon className="w-2.5 h-2.5" />{c.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export const TaskBoard = ({ workspaceId, tasks, onRefresh }) => {
  const [groups, setGroups] = useState([]);
  const [totalTasks, setTotalTasks] = useState(0);
  const [loading, setLoading] = useState(true);
  const [expandedGroups, setExpandedGroups] = useState({});
  const [statusFilter, setStatusFilter] = useState("all");
  const [viewMode, setViewMode] = useState("grouped"); // "grouped" or "kanban"
  const [dialogOpen, setDialogOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [assignedTo, setAssignedTo] = useState("");
  const [priority, setPriority] = useState("medium");
  const [creating, setCreating] = useState(false);
  const [prompting, setPrompting] = useState({});
  const [detailTask, setDetailTask] = useState(null);
  const [detailData, setDetailData] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [subtaskTitle, setSubtaskTitle] = useState("");
  const [relType, setRelType] = useState("relates_to");
  const [relTargetId, setRelTargetId] = useState("");

  const fetchGroupedTasks = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/all-tasks`);
      const data = res.data;
      setGroups(data.groups || []);
      setTotalTasks(data.total_tasks || 0);
      // Auto-expand all groups
      const exp = {};
      (data.groups || []).forEach(g => { exp[g.project_id || "_ws"] = true; });
      setExpandedGroups(prev => ({ ...exp, ...prev }));
    } catch (err) {
      console.error("Failed to fetch all-tasks:", err);
      // fallback to simple tasks
      setGroups([{ project_id: null, project_name: "Workspace Tasks", project_status: "active", tasks: tasks || [] }]);
      setTotalTasks((tasks || []).length);
    } finally {
      setLoading(false);
    }
  }, [workspaceId, tasks]);

  useEffect(() => { fetchGroupedTasks(); }, [fetchGroupedTasks]);

  const toggleGroup = (key) => {
    setExpandedGroups(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const createTask = async () => {
    if (!title.trim()) return;
    setCreating(true);
    try {
      await api.post(`/workspaces/${workspaceId}/tasks`, {
        title, description,
        assigned_to: assignedTo && assignedTo !== "unassigned" ? assignedTo : "",
        assigned_type: assignedTo && assignedTo !== "unassigned" ? "ai" : "human",
        priority,
      });
      setDialogOpen(false);
      setTitle(""); setDescription(""); setAssignedTo(""); setPriority("medium");
      fetchGroupedTasks();
      if (onRefresh) onRefresh();
      toast.success("Task created");
    } catch (err) { handleError(err, "TaskBoard:op1"); } finally {
      setCreating(false);
    }
  };

  const moveTask = async (taskId, newStatus, projectId) => {
    try {
      if (projectId) {
        await api.put(`/projects/${projectId}/tasks/${taskId}`, { status: newStatus });
      } else {
        await api.put(`/tasks/${taskId}`, { status: newStatus });
      }
      fetchGroupedTasks();
      if (onRefresh) onRefresh();
    } catch (err) { handleError(err, "TaskBoard:op2"); }
  };

  const deleteTask = async (taskId, projectId) => {
    try {
      if (projectId) {
        await api.delete(`/projects/${projectId}/tasks/${taskId}`);
      } else {
        await api.delete(`/tasks/${taskId}`);
      }
      fetchGroupedTasks();
      if (onRefresh) onRefresh();
      toast.success("Task deleted");
    } catch (err) { handleError(err, "TaskBoard:op3"); }
  };

  const promptAgent = async (taskId) => {
    setPrompting(p => ({ ...p, [taskId]: true }));
    try {
      const res = await api.post(`/tasks/${taskId}/prompt-agent`);
      toast.success(`Agent prompted in #${res.data.channel_id?.slice(-6) || "channel"}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to prompt agent");
    } finally {
      setPrompting(p => ({ ...p, [taskId]: false }));
    }
  };

  const openTaskDetail = async (taskId) => {
    setDetailLoading(true);
    setDetailTask(taskId);
    try {
      const res = await api.get(`/tasks/${taskId}/detail`);
      setDetailData(res.data);
    } catch (err) { handleSilent(err, "TaskBoard:op5"); toast.error("Failed to load task details");
      setDetailTask(null); } finally {
      setDetailLoading(false);
    }
  };

  const closeDetail = () => { setDetailTask(null); setDetailData(null); };

  const createSubtask = async () => {
    if (!subtaskTitle.trim() || !detailData?.task) return;
    const projectId = detailData.task.project_id;
    if (!projectId) { toast.error("Can only add subtasks to project tasks"); return; }
    try {
      await api.post(`/projects/${projectId}/tasks`, {
        title: subtaskTitle, description: "", status: "todo", priority: "medium",
        item_type: "subtask", parent_task_id: detailTask,
      });
      setSubtaskTitle("");
      openTaskDetail(detailTask); // Refresh detail
      fetchGroupedTasks();
      toast.success("Subtask created");
    } catch (err) { handleError(err, "TaskBoard:op4"); }
  };

  const addRelationship = async () => {
    if (!relTargetId.trim() || !detailTask) return;
    try {
      await api.post(`/tasks/${detailTask}/relationships`, { type: relType, target_id: relTargetId });
      setRelTargetId("");
      openTaskDetail(detailTask); // Refresh
      toast.success("Relationship added");
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  const filterTasks = (taskList) => {
    if (statusFilter === "all") return taskList;
    return taskList.filter(t => t.status === statusFilter);
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center" data-testid="task-board-loading">
        <div className="flex gap-2">
          <div className="w-2 h-2 rounded-full bg-zinc-600 animate-bounce" style={{ animationDelay: "0ms" }} />
          <div className="w-2 h-2 rounded-full bg-zinc-600 animate-bounce" style={{ animationDelay: "150ms" }} />
          <div className="w-2 h-2 rounded-full bg-zinc-600 animate-bounce" style={{ animationDelay: "300ms" }} />
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col" data-testid="task-board">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800/60">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-zinc-200" style={{ fontFamily: "Syne, sans-serif" }}>Task Board</h2>
          <span className="text-xs text-zinc-600 font-mono">{totalTasks} tasks</span>
        </div>
        <div className="flex items-center gap-2">
          {/* View mode toggle */}
          <div className="flex items-center bg-zinc-900 rounded-lg border border-zinc-800 p-0.5">
            <button
              onClick={() => setViewMode("grouped")}
              className={`px-2 py-1 text-[10px] rounded-md transition-colors ${viewMode === "grouped" ? "bg-zinc-800 text-zinc-200" : "text-zinc-500 hover:text-zinc-300"}`}
              data-testid="view-grouped"
            >
              By Project
            </button>
            <button
              onClick={() => setViewMode("kanban")}
              className={`px-2 py-1 text-[10px] rounded-md transition-colors ${viewMode === "kanban" ? "bg-zinc-800 text-zinc-200" : "text-zinc-500 hover:text-zinc-300"}`}
              data-testid="view-kanban"
            >
              Kanban
            </button>
          </div>
          {/* Status filter */}
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="bg-zinc-900 border-zinc-800 h-8 text-xs w-32" data-testid="status-filter">
              <Filter className="w-3 h-3 mr-1" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-zinc-900 border-zinc-800">
              <SelectItem value="all">All Statuses</SelectItem>
              {Object.entries(STATUS_CONFIG).map(([k, v]) => (
                <SelectItem key={k} value={k}>{v.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {/* Create task */}
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button size="sm" className="bg-zinc-100 text-zinc-900 hover:bg-zinc-200" data-testid="create-task-btn">
                <Plus className="w-3.5 h-3.5 mr-1" /> New Task
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-zinc-900 border-zinc-800">
              <DialogHeader>
                <DialogTitle className="text-zinc-100" style={{ fontFamily: "Syne, sans-serif" }}>Create Task</DialogTitle>
                <DialogDescription className="text-zinc-500 text-sm">Create a new workspace task</DialogDescription>
              </DialogHeader>
              <div className="space-y-3 mt-2">
                <Input placeholder="Task title" value={title} onChange={(e) => setTitle(e.target.value)}
                  className="bg-zinc-950 border-zinc-800 placeholder:text-zinc-600" data-testid="task-title-input" autoFocus />
                <Input placeholder="Description (optional)" value={description} onChange={(e) => setDescription(e.target.value)}
                  className="bg-zinc-950 border-zinc-800 placeholder:text-zinc-600" data-testid="task-desc-input" />
                <div className="grid grid-cols-2 gap-2">
                  <Select value={assignedTo} onValueChange={setAssignedTo}>
                    <SelectTrigger className="bg-zinc-950 border-zinc-800" data-testid="task-assignee-select">
                      <SelectValue placeholder="Assign to..." />
                    </SelectTrigger>
                    <SelectContent className="bg-zinc-900 border-zinc-800">
                      <SelectItem value="unassigned">Unassigned</SelectItem>
                      {AI_AGENTS.map(a => (
                        <SelectItem key={a.key} value={a.key}>{a.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Select value={priority} onValueChange={setPriority}>
                    <SelectTrigger className="bg-zinc-950 border-zinc-800" data-testid="task-priority-select">
                      <SelectValue placeholder="Priority" />
                    </SelectTrigger>
                    <SelectContent className="bg-zinc-900 border-zinc-800">
                      {Object.entries(PRIORITY_CONFIG).map(([k, v]) => (
                        <SelectItem key={k} value={k}>{v.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Button type="button" onClick={createTask} disabled={!title.trim() || creating}
                  className="w-full bg-zinc-100 text-zinc-900 hover:bg-zinc-200" data-testid="task-submit-btn">
                  {creating ? "Creating..." : "Create Task"}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Task content */}
      <ScrollArea className="flex-1">
        {viewMode === "kanban" ? (
          /* === KANBAN VIEW with drag-and-drop columns === */
          <div className="grid grid-cols-4 gap-3 p-6 min-h-[400px]" data-testid="kanban-view">
            {["todo", "in_progress", "review", "done"].map((colStatus) => {
              const cfg = STATUS_CONFIG[colStatus];
              const Icon = cfg.icon;
              const allTasks = groups.flatMap(g => (g.tasks || []).map(t => ({ ...t, _projectId: g.project_id, _isProject: !!g.project_id })));
              const colTasks = allTasks.filter(t => t.status === colStatus);
              return (
                <div
                  key={colStatus}
                  className="flex flex-col rounded-lg"
                  data-testid={`kanban-col-${colStatus}`}
                  onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add("ring-1", "ring-zinc-600"); }}
                  onDragLeave={(e) => { e.currentTarget.classList.remove("ring-1", "ring-zinc-600"); }}
                  onDrop={(e) => {
                    e.preventDefault();
                    e.currentTarget.classList.remove("ring-1", "ring-zinc-600");
                    const taskId = e.dataTransfer.getData("taskId");
                    const projectId = e.dataTransfer.getData("projectId");
                    const isProject = e.dataTransfer.getData("isProject") === "1";
                    if (taskId) moveTask(taskId, colStatus, isProject ? projectId : null);
                  }}
                >
                  <div className="flex items-center gap-2 mb-3 px-2">
                    <Icon className={`w-4 h-4 ${cfg.color}`} />
                    <span className="text-xs font-mono uppercase tracking-wider text-zinc-500">{cfg.label}</span>
                    <span className="text-[10px] bg-zinc-800 px-1.5 py-0.5 rounded text-zinc-500">{colTasks.length}</span>
                  </div>
                  <div className="space-y-2 flex-1 min-h-[200px]">
                    {colTasks.map((task) => (
                      <TaskCard
                        key={task.task_id}
                        task={task}
                        onMove={moveTask}
                        onDelete={deleteTask}
                        onPromptAgent={promptAgent}
                        isProjectTask={task._isProject}
                        onClickDetail={openTaskDetail}
                      />
                    ))}
                    {colTasks.length === 0 && (
                      <div className="flex items-center justify-center h-20 border border-dashed border-zinc-800/40 rounded-lg">
                        <span className="text-[10px] text-zinc-700 font-mono">Drop tasks here</span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          /* === GROUPED BY PROJECT VIEW === */
          <div className="p-6 space-y-4" data-testid="grouped-view">
          {groups.length === 0 && (
            <div className="text-center py-16" data-testid="empty-task-board">
              <FolderKanban className="w-12 h-12 text-zinc-800 mx-auto mb-4" />
              <h3 className="text-base font-semibold text-zinc-300 mb-2" style={{ fontFamily: "Syne, sans-serif" }}>No tasks yet</h3>
              <p className="text-sm text-zinc-500 max-w-md mx-auto mb-6">
                Tasks from all your projects will appear here, grouped by project.
                Create a task below or add tasks in the Projects tab.
              </p>
              <div className="flex items-center justify-center gap-3">
                <Button size="sm" onClick={() => setDialogOpen(true)} className="bg-zinc-100 text-zinc-900 hover:bg-zinc-200 gap-1.5" data-testid="empty-create-task-btn">
                  <Plus className="w-3.5 h-3.5" /> Create a Task
                </Button>
              </div>
              <div className="mt-8 max-w-sm mx-auto space-y-2 text-left bg-zinc-900/60 rounded-lg p-4 border border-zinc-800/40">
                <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold mb-2">How it works</p>
                <div className="flex items-center gap-2 text-xs text-zinc-400">
                  <span className="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-[10px] font-bold flex-shrink-0">1</span>
                  Create a project in the Projects tab
                </div>
                <div className="flex items-center gap-2 text-xs text-zinc-400">
                  <span className="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-[10px] font-bold flex-shrink-0">2</span>
                  Add tasks to the project and assign AI agents
                </div>
                <div className="flex items-center gap-2 text-xs text-zinc-400">
                  <span className="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-[10px] font-bold flex-shrink-0">3</span>
                  All tasks appear here grouped by project
                </div>
              </div>
            </div>
          )}

          {groups.map((group) => {
            const groupKey = group.project_id || "_ws";
            const isExpanded = expandedGroups[groupKey] !== false;
            const filteredTasks = filterTasks(group.tasks || []);
            const isProjectGroup = !!group.project_id;
            const taskCount = (group.tasks || []).length;
            const doneCount = (group.tasks || []).filter(t => t.status === "done").length;

            return (
              <div key={groupKey} className="rounded-xl border border-zinc-800/60 overflow-hidden" data-testid={`task-group-${groupKey}`}>
                <button
                  onClick={() => toggleGroup(groupKey)}
                  className="w-full flex items-center gap-3 px-4 py-3 bg-zinc-900/60 hover:bg-zinc-900/80 transition-colors text-left"
                  data-testid={`group-header-${groupKey}`}
                >
                  {isExpanded ? <ChevronDown className="w-4 h-4 text-zinc-500" /> : <ChevronRight className="w-4 h-4 text-zinc-500" />}
                  {isProjectGroup ? (
                    <FolderKanban className="w-4 h-4 text-purple-400" />
                  ) : (
                    <Zap className="w-4 h-4 text-zinc-500" />
                  )}
                  <span className="text-sm font-medium text-zinc-200">{group.project_name}</span>
                  <span className="text-[10px] text-zinc-600 font-mono ml-1">{doneCount}/{taskCount}</span>
                  {taskCount > 0 && (
                    <div className="ml-auto flex items-center gap-1.5">
                      {Object.entries(STATUS_CONFIG).map(([s, c]) => {
                        const count = (group.tasks || []).filter(t => t.status === s).length;
                        if (!count) return null;
                        const SIcon = c.icon;
                        return <span key={s} className={`text-[9px] flex items-center gap-0.5 ${c.color}`}><SIcon className="w-2.5 h-2.5" />{count}</span>;
                      })}
                    </div>
                  )}
                </button>
                {isExpanded && (
                  <div className="p-3 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                    {filteredTasks.length === 0 ? (
                      <div className="col-span-full text-center py-6">
                        <p className="text-xs text-zinc-600">
                          {statusFilter !== "all" ? `No ${STATUS_CONFIG[statusFilter]?.label || statusFilter} tasks` : "No tasks in this project"}
                        </p>
                      </div>
                    ) : (
                      filteredTasks.map((task) => (
                        <TaskCard key={task.task_id} task={task} onMove={moveTask} onDelete={deleteTask} onPromptAgent={promptAgent} isProjectTask={isProjectGroup} onClickDetail={openTaskDetail} />
                      ))
                    )}
                  </div>
                )}
              </div>
            );
          })}
          </div>
        )}
      </ScrollArea>

      {/* Task Detail Modal */}
      <Dialog open={!!detailTask} onOpenChange={(open) => { if (!open) closeDetail(); }}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="text-zinc-100 flex items-center gap-2" style={{ fontFamily: "Syne, sans-serif" }}>
              {detailData?.task?.title || "Loading..."}
            </DialogTitle>
            <DialogDescription className="sr-only">Task details</DialogDescription>
          </DialogHeader>
          {detailLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="flex gap-2">
                <div className="w-2 h-2 rounded-full bg-zinc-600 animate-bounce" />
                <div className="w-2 h-2 rounded-full bg-zinc-600 animate-bounce" style={{ animationDelay: "150ms" }} />
              </div>
            </div>
          ) : detailData?.task ? (
            <ScrollArea className="flex-1 mt-2">
              <div className="space-y-4 pr-2">
                {/* Status + Priority + Assignee */}
                <div className="flex items-center gap-2 flex-wrap">
                  {(() => { const s = detailData.task.status || "todo"; const c = STATUS_CONFIG[s] || STATUS_CONFIG.todo; return <Badge className={`text-xs ${c.bg} ${c.color} border-0`}>{c.label}</Badge>; })()}
                  {(() => { const p = detailData.task.priority || "medium"; const c = PRIORITY_CONFIG[p] || PRIORITY_CONFIG.medium; return <Badge className={`text-xs ${c.bg} ${c.color} border-0`}>{c.label}</Badge>; })()}
                  {detailData.task.item_type && <Badge className="text-xs bg-zinc-800 text-zinc-400 border-0">{detailData.task.item_type}</Badge>}
                  <div className="ml-auto"><AssigneeBadge task={detailData.task} /></div>
                </div>

                {/* Description */}
                {detailData.task.description && (
                  <div className="p-3 rounded-lg bg-zinc-800/30 border border-zinc-800/40">
                    <p className="text-sm text-zinc-300 whitespace-pre-wrap">{detailData.task.description}</p>
                  </div>
                )}

                {/* Due date + Story points */}
                <div className="flex items-center gap-4 text-xs text-zinc-500">
                  {detailData.task.due_date && <span>Due: <span className="text-zinc-300">{detailData.task.due_date}</span></span>}
                  {detailData.task.story_points && <span>Points: <span className="text-zinc-300">{detailData.task.story_points}</span></span>}
                  {detailData.task.labels?.length > 0 && (
                    <div className="flex gap-1">{detailData.task.labels.map(l => <span key={l} className="px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 text-[10px]">{l}</span>)}</div>
                  )}
                </div>

                {/* Milestone */}
                {detailData.milestone && (
                  <div className="p-3 rounded-lg bg-purple-500/5 border border-purple-500/20">
                    <div className="flex items-center gap-2">
                      <Milestone className="w-4 h-4 text-purple-400" />
                      <span className="text-sm font-medium text-purple-300">{detailData.milestone.name}</span>
                      <Badge className="text-[9px] bg-purple-500/15 text-purple-400 border-0">{detailData.milestone.status}</Badge>
                    </div>
                    {detailData.milestone.due_date && <p className="text-[10px] text-zinc-500 mt-1">Due: {detailData.milestone.due_date}</p>}
                  </div>
                )}

                {/* Relationships */}
                {detailData.relationships?.length > 0 && (
                  <div>
                    <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold mb-2 flex items-center gap-1"><Link2 className="w-3 h-3" /> Relationships</p>
                    <div className="space-y-1">
                      {detailData.relationships.map((r, i) => {
                        const otherId = r.task_id === detailTask ? r.target_task_id : r.task_id;
                        const otherTask = detailData.related_tasks?.[otherId];
                        const isSource = r.task_id === detailTask;
                        return (
                          <div key={r.relationship_id || i} className="flex items-center gap-2 px-3 py-1.5 rounded bg-zinc-800/30 text-xs">
                            <span className={`px-1.5 py-0.5 rounded font-mono text-[9px] ${
                              r.relationship_type === "blocks" ? "bg-red-500/15 text-red-400" :
                              r.relationship_type === "depends_on" ? "bg-amber-500/15 text-amber-400" :
                              r.relationship_type === "parent" ? "bg-blue-500/15 text-blue-400" :
                              "bg-purple-500/15 text-purple-400"
                            }`}>{r.relationship_type}</span>
                            {isSource ? <ArrowRight className="w-3 h-3 text-zinc-600" /> : <ArrowLeft className="w-3 h-3 text-zinc-600" />}
                            <span className="text-zinc-300">{otherTask?.title || otherId || r.milestone_id || "Unknown"}</span>
                            {otherTask?.status && <Badge className="text-[8px] bg-zinc-800 text-zinc-500 border-0 ml-auto">{otherTask.status}</Badge>}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Progress bar in detail */}
                {detailData.subtasks?.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[10px] text-zinc-500">Progress</span>
                      <span className="text-[10px] text-zinc-400 font-medium">
                        {detailData.subtasks.filter(s => s.status === "done").length}/{detailData.subtasks.length}
                      </span>
                    </div>
                    <div className="w-full h-2 rounded-full bg-zinc-800 overflow-hidden">
                      <div className="h-full rounded-full bg-emerald-500 transition-all" style={{
                        width: `${Math.round(detailData.subtasks.filter(s => s.status === "done").length / detailData.subtasks.length * 100)}%`,
                      }} />
                    </div>
                  </div>
                )}

                {/* Subtasks */}
                <div>
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold mb-2">
                    Subtasks {detailData.subtasks?.length > 0 ? `(${detailData.subtasks.length})` : ""}
                  </p>
                  {detailData.subtasks?.length > 0 && (
                    <div className="space-y-1 mb-2">
                      {detailData.subtasks.map(st => (
                        <button key={st.task_id} onClick={() => openTaskDetail(st.task_id)}
                          className="w-full flex items-center gap-2 px-3 py-1.5 rounded bg-zinc-800/30 text-xs hover:bg-zinc-800/50">
                          {st.status === "done" ? <CheckCircle2 className="w-3 h-3 text-emerald-400" /> : <Circle className="w-3 h-3 text-zinc-500" />}
                          <span className={`flex-1 text-left ${st.status === "done" ? "text-zinc-500 line-through" : "text-zinc-300"}`}>{st.title}</span>
                          {st.priority && <span className="text-[8px] text-zinc-600">{st.priority}</span>}
                        </button>
                      ))}
                    </div>
                  )}
                  {/* Create subtask inline */}
                  <div className="flex gap-1">
                    <input value={subtaskTitle} onChange={(e) => setSubtaskTitle(e.target.value)}
                      placeholder="Add subtask..." className="flex-1 bg-zinc-800/30 border border-zinc-800 rounded px-2 py-1 text-xs text-zinc-300 placeholder:text-zinc-600"
                      onKeyDown={(e) => e.key === "Enter" && createSubtask()} />
                    <button onClick={createSubtask} disabled={!subtaskTitle.trim()}
                      className="px-2 py-1 rounded bg-zinc-800 text-zinc-400 hover:text-zinc-200 text-xs disabled:opacity-30">+</button>
                  </div>
                </div>

                {/* Add Relationship */}
                <div>
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold mb-2 flex items-center gap-1"><Link2 className="w-3 h-3" /> Add Relationship</p>
                  <div className="flex gap-1">
                    <select value={relType} onChange={(e) => setRelType(e.target.value)}
                      className="bg-zinc-800/30 border border-zinc-800 rounded px-2 py-1 text-[10px] text-zinc-300">
                      <option value="relates_to">Relates to</option>
                      <option value="blocks">Blocks</option>
                      <option value="depends_on">Depends on</option>
                      <option value="parent">Parent of</option>
                    </select>
                    <input value={relTargetId} onChange={(e) => setRelTargetId(e.target.value)}
                      placeholder="Task ID (ptask_...)" className="flex-1 bg-zinc-800/30 border border-zinc-800 rounded px-2 py-1 text-xs text-zinc-300 placeholder:text-zinc-600 font-mono" />
                    <button onClick={addRelationship} disabled={!relTargetId.trim()}
                      className="px-2 py-1 rounded bg-zinc-800 text-zinc-400 hover:text-zinc-200 text-xs disabled:opacity-30">Link</button>
                  </div>
                </div>

                {/* Activity */}
                {detailData.activity?.length > 0 && (
                  <div>
                    <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold mb-2 flex items-center gap-1"><Activity className="w-3 h-3" /> Activity</p>
                    <div className="space-y-1">
                      {detailData.activity.map((a, i) => (
                        <div key={a.activity_id || i} className="flex items-center gap-2 px-3 py-1.5 text-[11px] text-zinc-500">
                          <span className="text-zinc-400 font-medium">{a.actor_name || "System"}</span>
                          <span>{a.action}</span>
                          {a.details?.changes && <span className="text-zinc-600">{a.details.changes.join(", ")}</span>}
                          <span className="ml-auto text-zinc-700 text-[10px]">{a.timestamp ? new Date(a.timestamp).toLocaleString() : ""}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </ScrollArea>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default TaskBoard;
