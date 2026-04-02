import { useState, useEffect, useCallback } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { useConfirm } from "@/components/ConfirmDialog";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  FolderKanban, Plus, ArrowLeft, Pencil, Trash2, ChevronRight,
  CheckCircle2, Circle, Clock, Pause, Archive, ListTodo, Paperclip,
  User, Bot, AlertTriangle, ArrowUp, ArrowDown, Minus, List, Columns3, GripVertical,
  Search, CheckSquare, Square, X as XIcon, Diamond, MoreVertical, BarChart3
} from "lucide-react";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const STATUS_CONFIG = {
  active: { label: "Active", color: "bg-emerald-500/20 text-emerald-400", icon: CheckCircle2 },
  on_hold: { label: "On Hold", color: "bg-amber-500/20 text-amber-400", icon: Pause },
  completed: { label: "Completed", color: "bg-blue-500/20 text-blue-400", icon: CheckCircle2 },
  archived: { label: "Archived", color: "bg-zinc-500/20 text-zinc-400", icon: Archive },
};

const TASK_STATUS_CONFIG = {
  todo: { label: "To Do", color: "bg-zinc-500/20 text-zinc-400", icon: Circle },
  in_progress: { label: "In Progress", color: "bg-blue-500/20 text-blue-400", icon: Clock },
  review: { label: "Review", color: "bg-amber-500/20 text-amber-400", icon: AlertTriangle },
  done: { label: "Done", color: "bg-emerald-500/20 text-emerald-400", icon: CheckCircle2 },
};

const PRIORITY_CONFIG = {
  low: { label: "Low", color: "text-zinc-400", icon: ArrowDown },
  medium: { label: "Medium", color: "text-blue-400", icon: Minus },
  high: { label: "High", color: "text-amber-400", icon: ArrowUp },
  critical: { label: "Critical", color: "text-red-400", icon: AlertTriangle },
};

const AI_AGENTS = [
  { key: "claude", name: "Claude" }, { key: "chatgpt", name: "ChatGPT" },
  { key: "gemini", name: "Gemini" }, { key: "perplexity", name: "Perplexity" },
  { key: "mistral", name: "Mistral" }, { key: "cohere", name: "Cohere" },
  { key: "groq", name: "Groq" }, { key: "deepseek", name: "DeepSeek" },
  { key: "grok", name: "Grok" }, { key: "mercury", name: "Mercury 2" },
  { key: "pi", name: "Pi" }, { key: "manus", name: "Manus" },
  { key: "qwen", name: "Qwen" }, { key: "kimi", name: "Kimi" },
  { key: "llama", name: "Llama" }, { key: "glm", name: "GLM" },
  { key: "cursor", name: "Cursor" }, { key: "notebooklm", name: "NotebookLM" },
  { key: "copilot", name: "GitHub Copilot" },
];

// =================== Project List ===================
function ProjectList({ projects, onSelect, onCreate, loading, onOpenGantt }) {
  const [editProject, setEditProject] = useState(null);
  const [editOpen, setEditOpen] = useState(false);

  const handleDelete = async (project, e) => {
    e.stopPropagation();
    const ok = await confirmAction("Delete Project", `Delete "${project.name}" and all its tasks? This cannot be undone.`); if (!ok) return;
    try {
      await api.delete(`/projects/${project.project_id}`);
      toast.success("Project deleted");
      window.location.reload();
    } catch (err) { handleError(err, "ProjectPanel:op1"); }
  };
  return (
    <div className="flex-1 flex flex-col min-h-0" data-testid="project-list">
      <div className="px-6 py-4 border-b border-zinc-800/60 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FolderKanban className="w-5 h-5 text-zinc-400" />
          <h2 className="text-lg font-semibold text-zinc-100" style={{ fontFamily: 'Syne, sans-serif' }}>Projects</h2>
          <Badge className="bg-zinc-800 text-zinc-400 text-[10px]">{projects.length}</Badge>
        </div>
        <Button size="sm" onClick={onCreate} className="bg-zinc-100 text-zinc-900 hover:bg-zinc-200 gap-1.5" data-testid="create-project-btn">
          <Plus className="w-3.5 h-3.5" /> New Project
        </Button>
      </div>
      <ScrollArea className="flex-1">
        {loading ? (
          <div className="p-6 text-center text-zinc-500 text-sm">Loading projects...</div>
        ) : projects.length === 0 ? (
          <div className="p-12 text-center">
            <FolderKanban className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
            <p className="text-sm text-zinc-500">No projects yet</p>
            <p className="text-xs text-zinc-600 mt-1">Create your first project to get started</p>
          </div>
        ) : (
          <div className="p-3 space-y-2">
            {projects.map((p) => {
              const sc = STATUS_CONFIG[p.status] || STATUS_CONFIG.active;
              const Icon = sc.icon;
              const progress = p.task_count > 0 ? Math.round((p.tasks_done / p.task_count) * 100) : 0;
              return (
                <button
                  key={p.project_id}
                  onClick={() => onSelect(p)}
                  className="w-full text-left p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/60 hover:border-zinc-700 transition-all group"
                  data-testid={`project-card-${p.project_id}`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="text-sm font-semibold text-zinc-200 group-hover:text-zinc-100 truncate pr-2">{p.name}</h3>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <Badge className={`${sc.color} text-[10px] gap-1`}>
                        <Icon className="w-3 h-3" /> {sc.label}
                      </Badge>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <span onClick={(e) => e.stopPropagation()} className="p-1 rounded text-zinc-600 hover:text-zinc-300 cursor-pointer" data-testid={`project-menu-${p.project_id}`}>
                            <MoreVertical className="w-3.5 h-3.5" />
                          </span>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent className="bg-zinc-900 border-zinc-800" align="end">
                          <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onSelect(p); }} className="text-zinc-300 hover:bg-zinc-800 cursor-pointer text-xs">
                            <ChevronRight className="w-3.5 h-3.5 mr-2" /> View Details
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onOpenGantt(p); }} className="text-zinc-300 hover:bg-zinc-800 cursor-pointer text-xs" data-testid={`project-gantt-${p.project_id}`}>
                            <BarChart3 className="w-3.5 h-3.5 mr-2" /> Gantt Chart
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={(e) => { e.stopPropagation(); setEditProject(p); setEditOpen(true); }} className="text-zinc-300 hover:bg-zinc-800 cursor-pointer text-xs">
                            <Pencil className="w-3.5 h-3.5 mr-2" /> Edit
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={(e) => handleDelete(p, e)} className="text-red-400 hover:bg-zinc-800 cursor-pointer text-xs">
                            <Trash2 className="w-3.5 h-3.5 mr-2" /> Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>
                  {p.description && <p className="text-xs text-zinc-500 line-clamp-2 mb-3">{p.description}</p>}
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-1.5 text-xs text-zinc-500">
                      <ListTodo className="w-3 h-3" />
                      <span>{p.tasks_done}/{p.task_count} tasks</span>
                    </div>
                    {p.task_count > 0 && (
                      <div className="flex-1 h-1.5 rounded-full bg-zinc-800 overflow-hidden">
                        <div className="h-full rounded-full bg-emerald-500/60 transition-all" style={{ width: `${progress}%` }} />
                      </div>
                    )}
                    <span onClick={(e) => { e.stopPropagation(); onOpenGantt(p); }}
                      className="flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] text-emerald-400/70 hover:text-emerald-400 hover:bg-emerald-500/10 border border-emerald-500/20 cursor-pointer transition-colors"
                      data-testid={`project-gantt-quick-${p.project_id}`}>
                      <BarChart3 className="w-3 h-3" /> Gantt
                    </span>
                    <ChevronRight className="w-4 h-4 text-zinc-600 group-hover:text-zinc-400 transition-colors" />
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </ScrollArea>
      {editProject && (
        <EditProjectDialog open={editOpen} onOpenChange={setEditOpen} project={editProject} channels={[]} onDone={() => window.location.reload()} />
      )}
    </div>
  );
}

// =================== Kanban Board ===================
function KanbanBoard({ tasks, projectId, onEdit, onDelete, onRefresh }) {
  const [draggedTask, setDraggedTask] = useState(null);
  const [dragOverCol, setDragOverCol] = useState(null);

  const columns = Object.entries(TASK_STATUS_CONFIG);

  const handleDragStart = (e, task) => {
    setDraggedTask(task);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", task.task_id);
    e.currentTarget.style.opacity = "0.4";
  };

  const handleDragEnd = (e) => {
    e.currentTarget.style.opacity = "1";
    setDraggedTask(null);
    setDragOverCol(null);
  };

  const handleDragOver = (e, status) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDragOverCol(status);
  };

  const handleDragLeave = () => {
    setDragOverCol(null);
  };

  const handleDrop = async (e, newStatus) => {
    e.preventDefault();
    setDragOverCol(null);
    if (!draggedTask || draggedTask.status === newStatus) return;
    try {
      await api.put(`/projects/${projectId}/tasks/${draggedTask.task_id}`, { status: newStatus });
      onRefresh();
    } catch (err) { handleError(err, "ProjectPanel:op2"); }
  };

  return (
    <div className="flex-1 overflow-x-auto overflow-y-hidden" data-testid="kanban-board">
      <div className="flex gap-3 p-4 min-w-max h-full">
        {columns.map(([status, config]) => {
          const Icon = config.icon;
          const colTasks = tasks.filter(t => t.status === status);
          const isOver = dragOverCol === status;
          return (
            <div
              key={status}
              className={`w-72 flex-shrink-0 flex flex-col rounded-xl border transition-colors ${
                isOver ? "border-zinc-600 bg-zinc-800/30" : "border-zinc-800/50 bg-zinc-900/30"
              }`}
              onDragOver={(e) => handleDragOver(e, status)}
              onDragLeave={handleDragLeave}
              onDrop={(e) => handleDrop(e, status)}
              data-testid={`kanban-col-${status}`}
            >
              {/* Column header */}
              <div className="px-3 py-2.5 border-b border-zinc-800/40 flex items-center gap-2">
                <Icon className={`w-3.5 h-3.5 ${config.color.split(' ')[1]}`} />
                <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">{config.label}</span>
                <span className="ml-auto text-[10px] text-zinc-600 bg-zinc-800/60 px-1.5 py-0.5 rounded-full">{colTasks.length}</span>
              </div>

              {/* Column body */}
              <div className="flex-1 overflow-y-auto p-2 space-y-2 min-h-[100px]">
                {colTasks.length === 0 && (
                  <div className={`rounded-lg border-2 border-dashed py-8 text-center transition-colors ${
                    isOver ? "border-zinc-500 bg-zinc-800/20" : "border-zinc-800/30"
                  }`}>
                    <p className="text-[11px] text-zinc-600">Drop here</p>
                  </div>
                )}
                {colTasks.map((t) => {
                  const pc = PRIORITY_CONFIG[t.priority] || PRIORITY_CONFIG.medium;
                  const PIcon = pc.icon;
                  return (
                    <div
                      key={t.task_id}
                      draggable
                      onDragStart={(e) => handleDragStart(e, t)}
                      onDragEnd={handleDragEnd}
                      className="group p-3 rounded-lg bg-zinc-900/80 border border-zinc-800/50 hover:border-zinc-700 cursor-grab active:cursor-grabbing transition-all hover:shadow-lg hover:shadow-black/20"
                      data-testid={`kanban-card-${t.task_id}`}
                    >
                      <div className="flex items-start justify-between gap-2 mb-1.5">
                        <div className="flex items-center gap-1.5 min-w-0">
                          <GripVertical className="w-3 h-3 text-zinc-700 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                          <span className={`text-sm font-medium leading-tight ${t.status === 'done' ? 'text-zinc-500 line-through' : 'text-zinc-200'}`}>
                            {t.title}
                          </span>
                        </div>
                        <div className="flex items-center gap-0.5 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button onClick={() => onEdit(t)} className="p-1 rounded text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800" data-testid={`kanban-edit-${t.task_id}`}>
                            <Pencil className="w-2.5 h-2.5" />
                          </button>
                          <button onClick={() => onDelete(t.task_id)} className="p-1 rounded text-zinc-500 hover:text-red-400 hover:bg-zinc-800" data-testid={`kanban-delete-${t.task_id}`}>
                            <Trash2 className="w-2.5 h-2.5" />
                          </button>
                        </div>
                      </div>
                      {t.description && <p className="text-[11px] text-zinc-500 line-clamp-2 mb-2 pl-[18px]">{t.description}</p>}
                      <div className="flex items-center gap-2 pl-[18px]">
                        <Badge className={`${pc.color} bg-transparent text-[9px] px-0 gap-0.5`}>
                          <PIcon className="w-2.5 h-2.5" /> {pc.label}
                        </Badge>
                        {t.assignee_name && (
                          <div className="flex items-center gap-1 ml-auto">
                            {t.assignee_type === "ai" ? <Bot className="w-3 h-3 text-zinc-600" /> : <User className="w-3 h-3 text-zinc-600" />}
                            <span className="text-[10px] text-zinc-500">{t.assignee_name}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// =================== Project Gantt Chart ===================
function ProjectGantt({ projectId, tasks, milestones: milestoneProp }) {
  const [zoomLevel, setZoomLevel] = useState("week");
  const [startOffset, setStartOffset] = useState(0);
  const [expandedGroups, setExpandedGroups] = useState({});
  const [hoveredTask, setHoveredTask] = useState(null);
  const [projectMilestones, setProjectMilestones] = useState([]);
  const [dependencies, setDependencies] = useState([]);
  const [dragging, setDragging] = useState(null); // {taskId, edge: 'left'|'right', startX}

  useEffect(() => {
    // Fetch milestones and dependencies for this project
    Promise.all([
      api.get(`/projects/${projectId}/milestones`).catch(() => ({ data: { milestones: [] } })),
      api.get(`/projects/${projectId}/dependencies`).catch(() => ({ data: { dependencies: [] } })),
    ]).then(([msRes, depRes]) => {
      setProjectMilestones(msRes.data?.milestones || []);
      setDependencies(depRes.data?.dependencies || []);
    });
  }, [projectId]);

  // Group tasks by status
  const grouped = {};
  const statusOrder = ["in_progress", "todo", "review", "done"];
  statusOrder.forEach(s => { grouped[s] = []; });
  tasks.forEach(t => {
    const s = t.status || "todo";
    if (!grouped[s]) grouped[s] = [];
    grouped[s].push(t);
  });

  // Config per zoom level
  const zoomConfig = {
    day: { unitDays: 1, units: 30, unitWidth: 32, format: (d) => d.getDate() },
    week: { unitDays: 7, units: 12, unitWidth: 80, format: (d) => d.toLocaleDateString([], { month: "short", day: "numeric" }) },
    month: { unitDays: 30, units: 6, unitWidth: 160, format: (d) => d.toLocaleDateString([], { month: "short", year: "2-digit" }) },
  };
  const cfg = zoomConfig[zoomLevel];
  const totalWidth = cfg.units * cfg.unitWidth;

  // Date range
  const now = new Date();
  const startDate = new Date(now);
  startDate.setDate(startDate.getDate() - cfg.unitDays * 2 + startOffset * cfg.unitDays * 3);
  startDate.setHours(0, 0, 0, 0);

  const headers = [];
  for (let i = 0; i < cfg.units; i++) {
    const d = new Date(startDate);
    d.setDate(d.getDate() + i * cfg.unitDays);
    headers.push(d);
  }

  // Today line position
  const todayOffset = (now - startDate) / (1000 * 60 * 60 * 24) * (cfg.unitWidth / cfg.unitDays);

  const getBarPos = (task) => {
    const due = task.due_date ? new Date(task.due_date) : null;
    const created = task.created_at ? new Date(task.created_at) : new Date();
    const start = due ? new Date(Math.min(created.getTime(), due.getTime() - 3 * 86400000)) : created;
    const end = due || new Date(start.getTime() + 7 * 86400000);
    const leftDays = (start - startDate) / (1000 * 60 * 60 * 24);
    const widthDays = Math.max(1, (end - start) / (1000 * 60 * 60 * 24));
    const pxPerDay = cfg.unitWidth / cfg.unitDays;
    return { left: leftDays * pxPerDay, width: Math.max(widthDays * pxPerDay, 16) };
  };

  const statusColors = { todo: "#71717a", in_progress: "#3b82f6", review: "#f59e0b", done: "#22c55e" };
  const priorityIcons = { critical: "!", high: "^", medium: "-", low: "v" };
  const statusLabels = { todo: "To Do", in_progress: "In Progress", review: "Review", done: "Done" };

  const toggleGroup = (key) => setExpandedGroups(prev => ({ ...prev, [key]: !prev[key] }));

  // Calculate progress per task (subtasks done / total)
  const getProgress = (task) => {
    if (task.subtasks?.length > 0) {
      const done = task.subtasks.filter(s => s.done || s.status === "done").length;
      return Math.round((done / task.subtasks.length) * 100);
    }
    if (task.status === "done") return 100;
    if (task.status === "in_progress") return 50;
    if (task.status === "review") return 75;
    return 0;
  };

  // Critical path: tasks with no slack (due date = latest possible)
  const isCritical = (task) => {
    if (!task.due_date) return false;
    const due = new Date(task.due_date);
    const daysLeft = (due - now) / (1000 * 60 * 60 * 24);
    return daysLeft < 3 && task.status !== "done";
  };

  if (tasks.length === 0) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="text-center">
          <BarChart3 className="w-8 h-8 text-zinc-700 mx-auto mb-2" />
          <p className="text-sm text-zinc-500">No tasks with dates to display</p>
          <p className="text-xs text-zinc-600 mt-1">Add due dates to tasks to see them on the Gantt chart</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full" data-testid="project-gantt"
      onMouseMove={(e) => {
        if (!dragging) return;
        const dx = e.clientX - dragging.startX;
        const daysDelta = Math.round(dx / (cfg.unitWidth / cfg.unitDays));
        if (daysDelta !== 0) {
          setDragging(prev => ({ ...prev, daysDelta }));
        }
      }}
      onMouseUp={async () => {
        if (!dragging || !dragging.daysDelta) { setDragging(null); return; }
        const task = tasks.find(t => t.task_id === dragging.taskId);
        if (task?.due_date) {
          const due = new Date(task.due_date);
          if (dragging.edge === "right") {
            due.setDate(due.getDate() + dragging.daysDelta);
          }
          try {
            await api.put(`/projects/${projectId}/tasks/${dragging.taskId}`, { due_date: due.toISOString().split("T")[0] });
          } catch (err) { handleSilent(err, "ProjectPanel:op1"); }
        }
        setDragging(null);
      }}
      onMouseLeave={() => setDragging(null)}
    >
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-zinc-800/40 flex-shrink-0">
        <div className="flex items-center gap-2">
          <button onClick={() => setStartOffset(o => o - 3)} className="p-1 rounded hover:bg-zinc-800 text-zinc-400" data-testid="gantt-prev">
            <ChevronRight className="w-4 h-4 rotate-180" />
          </button>
          <span className="text-xs text-zinc-400 min-w-[140px] text-center">
            {headers[0]?.toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" })} — {headers[headers.length - 1]?.toLocaleDateString([], { month: "short", day: "numeric" })}
          </span>
          <button onClick={() => setStartOffset(o => o + 3)} className="p-1 rounded hover:bg-zinc-800 text-zinc-400" data-testid="gantt-next">
            <ChevronRight className="w-4 h-4" />
          </button>
          <button onClick={() => setStartOffset(0)} className="text-[10px] text-zinc-500 hover:text-zinc-300 px-2 py-0.5 rounded bg-zinc-800/40" data-testid="gantt-today">Today</button>
        </div>
        <div className="flex items-center gap-1">
          {["day", "week", "month"].map(z => (
            <button key={z} onClick={() => setZoomLevel(z)}
              className={`text-[10px] px-2 py-0.5 rounded capitalize ${zoomLevel === z ? "bg-zinc-700 text-zinc-200" : "text-zinc-500 hover:text-zinc-300"}`}
              data-testid={`gantt-zoom-${z}`}>
              {z}
            </button>
          ))}
        </div>
      </div>

      {/* Chart area */}
      <div className="flex-1 overflow-auto">
        <div style={{ minWidth: totalWidth + 260 }}>
          {/* Column headers */}
          <div className="flex border-b border-zinc-800/40 sticky top-0 bg-zinc-950 z-10">
            <div className="w-[260px] flex-shrink-0 px-3 py-1.5 text-[10px] text-zinc-500 font-semibold uppercase tracking-wider">Task</div>
            <div className="flex-1 flex relative">
              {headers.map((h, i) => (
                <div key={i} className="text-[9px] text-zinc-600 text-center border-l border-zinc-800/20 py-1.5" style={{ width: cfg.unitWidth }}>
                  {cfg.format(h)}
                </div>
              ))}
            </div>
          </div>

          {/* Milestones row */}
          {projectMilestones.length > 0 && (
            <div className="flex items-center border-b border-zinc-800/20 h-8 bg-zinc-900/30">
              <div className="w-[260px] flex-shrink-0 px-3 text-[10px] text-amber-400 font-semibold flex items-center gap-1.5">
                <Diamond className="w-3 h-3" /> Milestones
              </div>
              <div className="flex-1 relative h-full">
                {headers.map((_, i) => <div key={i} className="absolute top-0 bottom-0 border-l border-zinc-800/10" style={{ left: i * cfg.unitWidth }} />)}
                {todayOffset > 0 && todayOffset < totalWidth && <div className="absolute top-0 bottom-0 w-px bg-emerald-500/50 z-10" style={{ left: todayOffset }} />}
                {projectMilestones.map(ms => {
                  if (!ms.due_date) return null;
                  const d = new Date(ms.due_date);
                  const offset = ((d - startDate) / (1000 * 60 * 60 * 24)) * (cfg.unitWidth / cfg.unitDays);
                  return <div key={ms.milestone_id} className="absolute top-1/2 -translate-y-1/2" style={{ left: offset }} title={`${ms.name} — ${ms.due_date}`}>
                    <Diamond className="w-4 h-4 text-amber-400 fill-amber-400/80" />
                  </div>;
                })}
              </div>
            </div>
          )}

          {/* Task groups by status */}
          {statusOrder.filter(s => grouped[s]?.length > 0).map(status => {
            const isExpanded = expandedGroups[status] !== false; // default expanded
            return (
              <div key={status}>
                {/* Group header */}
                <div className="flex items-center border-b border-zinc-800/30 h-7 bg-zinc-900/50 cursor-pointer hover:bg-zinc-800/30"
                  onClick={() => toggleGroup(status)} data-testid={`gantt-group-${status}`}>
                  <div className="w-[260px] flex-shrink-0 px-3 flex items-center gap-2">
                    <ChevronRight className={`w-3 h-3 text-zinc-600 transition-transform ${isExpanded ? "rotate-90" : ""}`} />
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: statusColors[status] }} />
                    <span className="text-[10px] font-semibold text-zinc-400">{statusLabels[status] || status}</span>
                    <span className="text-[9px] text-zinc-600">{grouped[status].length}</span>
                  </div>
                  <div className="flex-1 relative h-full">
                    {headers.map((_, i) => <div key={i} className="absolute top-0 bottom-0 border-l border-zinc-800/10" style={{ left: i * cfg.unitWidth }} />)}
                    {todayOffset > 0 && todayOffset < totalWidth && <div className="absolute top-0 bottom-0 w-px bg-emerald-500/50" style={{ left: todayOffset }} />}
                  </div>
                </div>

                {/* Tasks in group */}
                {isExpanded && grouped[status].map(task => {
                  const pos = getBarPos(task);
                  const color = statusColors[task.status] || "#555";
                  const progress = getProgress(task);
                  const critical = isCritical(task);
                  const isHovered = hoveredTask === task.task_id;

                  return (
                    <div key={task.task_id}
                      className={`flex items-center border-b border-zinc-800/10 h-9 transition-colors ${critical ? "bg-red-500/5" : isHovered ? "bg-zinc-800/20" : ""}`}
                      onMouseEnter={() => setHoveredTask(task.task_id)}
                      onMouseLeave={() => setHoveredTask(null)}
                      data-testid={`gantt-task-${task.task_id}`}>
                      {/* Task label */}
                      <div className="w-[260px] flex-shrink-0 px-3 pl-8 flex items-center gap-2 min-w-0">
                        <span className={`text-[10px] ${critical ? "text-red-400" : "text-zinc-500"}`}>{priorityIcons[task.priority] || ""}</span>
                        <span className={`text-xs truncate ${task.status === "done" ? "text-zinc-600 line-through" : "text-zinc-300"}`}>{task.title}</span>
                        {task.assigned_to && <span className="text-[8px] text-zinc-600 truncate">{task.assigned_to}</span>}
                      </div>
                      {/* Bar area */}
                      <div className="flex-1 relative h-full">
                        {headers.map((_, i) => <div key={i} className="absolute top-0 bottom-0 border-l border-zinc-800/10" style={{ left: i * cfg.unitWidth }} />)}
                        {todayOffset > 0 && todayOffset < totalWidth && <div className="absolute top-0 bottom-0 w-px bg-emerald-500/50" style={{ left: todayOffset }} />}
                        {/* Task bar with drag-to-resize handles */}
                        <div
                          className={`absolute top-1/2 -translate-y-1/2 h-5 rounded-sm transition-colors group/bar ${critical ? "ring-1 ring-red-500/40" : ""}`}
                          style={{ left: Math.max(0, pos.left), width: pos.width, backgroundColor: color, opacity: task.status === "done" ? 0.5 : 0.85 }}
                          title={`${task.title}\nStatus: ${task.status}\nProgress: ${progress}%${task.due_date ? `\nDue: ${task.due_date}` : ""}\nDrag edges to resize`}
                        >
                          {/* Left resize handle */}
                          <div className="absolute left-0 top-0 bottom-0 w-1.5 cursor-ew-resize opacity-0 group-hover/bar:opacity-100 bg-white/30 rounded-l-sm"
                            onMouseDown={(e) => {
                              e.stopPropagation();
                              setDragging({ taskId: task.task_id, edge: "left", startX: e.clientX, origPos: pos });
                            }} />
                          {/* Progress fill */}
                          <div className="h-full rounded-sm bg-white/20" style={{ width: `${progress}%` }} />
                          {/* Label on bar */}
                          {pos.width > 70 && <span className="absolute inset-0 flex items-center px-2 text-[9px] text-white font-medium truncate pointer-events-none">{task.title}</span>}
                          {/* Progress text */}
                          {pos.width > 40 && progress > 0 && <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[8px] text-white/70 pointer-events-none">{progress}%</span>}
                          {/* Right resize handle */}
                          <div className="absolute right-0 top-0 bottom-0 w-1.5 cursor-ew-resize opacity-0 group-hover/bar:opacity-100 bg-white/30 rounded-r-sm"
                            onMouseDown={(e) => {
                              e.stopPropagation();
                              setDragging({ taskId: task.task_id, edge: "right", startX: e.clientX, origPos: pos });
                            }} />
                        </div>
                        {/* Dependency lines */}
                        {dependencies.filter(d => d.task_id === task.task_id || d.target_task_id === task.task_id).map((dep, di) => {
                          const targetTask = tasks.find(t => t.task_id === dep.target_task_id);
                          if (!targetTask || dep.task_id !== task.task_id) return null;
                          const targetPos = getBarPos(targetTask);
                          return <svg key={di} className="absolute top-0 left-0 w-full h-full pointer-events-none" style={{ overflow: "visible" }}>
                            <line x1={pos.left + pos.width} y1={18} x2={targetPos.left} y2={18} stroke="#666" strokeWidth={1} strokeDasharray="4,2" markerEnd="url(#gantt-arrow)" />
                          </svg>;
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 px-4 py-1.5 border-t border-zinc-800/40 flex-shrink-0 bg-zinc-900/30">
        {Object.entries(statusColors).map(([s, c]) => (
          <div key={s} className="flex items-center gap-1">
            <div className="w-3 h-1.5 rounded-sm" style={{ backgroundColor: c }} />
            <span className="text-[9px] text-zinc-500 capitalize">{s.replace("_", " ")}</span>
          </div>
        ))}
        <div className="flex items-center gap-1">
          <Diamond className="w-3 h-3 text-amber-400" />
          <span className="text-[9px] text-zinc-500">Milestone</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-px h-3 bg-emerald-500" />
          <span className="text-[9px] text-zinc-500">Today</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-1.5 rounded-sm bg-red-500/30 ring-1 ring-red-500/40" />
          <span className="text-[9px] text-zinc-500">Critical</span>
        </div>
      </div>

      {/* Arrow marker */}
      <svg width="0" height="0"><defs><marker id="gantt-arrow" markerWidth="6" markerHeight="4" refX="6" refY="2" orient="auto"><path d="M0,0 L6,2 L0,4" fill="#666" /></marker></defs></svg>
    </div>
  );
}

// =================== Project Detail ===================
function ProjectDetail({ project, channels, onBack, onRefresh, workspaceId, members, initialViewMode }) {
  const [tasks, setTasks] = useState([]);
  const [taskDialogOpen, setTaskDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [taskToEdit, setTaskToEdit] = useState(null);
  const [editProjectOpen, setEditProjectOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState(() => initialViewMode || localStorage.getItem("nexus_task_view") || "kanban");
  const [selectedTasks, setSelectedTasks] = useState(new Set());
  const [filterStatus, setFilterStatus] = useState("");
  const [filterPriority, setFilterPriority] = useState("");
  const [filterAssignee, setFilterAssignee] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [milestones, setMilestones] = useState([]);
  const [msDialogOpen, setMsDialogOpen] = useState(false);
  const [msName, setMsName] = useState("");
  const [msDueDate, setMsDueDate] = useState("");
  const [msDesc, setMsDesc] = useState("");

  const fetchTasks = useCallback(async () => {
    try {
      const res = await api.get(`/projects/${project.project_id}/tasks`);
      setTasks(res.data);
    } catch (err) { handleSilent(err, "ProjectPanel:op2"); } finally { setLoading(false); }
  }, [project.project_id]);

  const fetchMilestones = useCallback(async () => {
    try {
      const res = await api.get(`/projects/${project.project_id}/milestones`);
      setMilestones(res.data.milestones || []);
    } catch (err) { handleSilent(err, "ProjectPanel:op3"); }
  }, [project.project_id]);

  useEffect(() => { fetchTasks(); fetchMilestones(); }, [fetchTasks, fetchMilestones]);

  const createMilestone = async () => {
    if (!msName.trim()) return;
    try {
      await api.post(`/projects/${project.project_id}/milestones`, { name: msName, description: msDesc, due_date: msDueDate || null });
      toast.success("Milestone created");
      setMsDialogOpen(false); setMsName(""); setMsDueDate(""); setMsDesc("");
      fetchMilestones();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  const updateMilestoneStatus = async (msId, status) => {
    try {
      await api.put(`/projects/${project.project_id}/milestones/${msId}`, { status });
      fetchMilestones();
    } catch (err) { handleError(err, "ProjectPanel:op3"); }
  };

  const deleteMilestone = async (msId) => {
    try {
      await api.delete(`/projects/${project.project_id}/milestones/${msId}`);
      toast.success("Milestone deleted");
      fetchMilestones();
    } catch (err) { handleError(err, "ProjectPanel:op4"); }
  };

  const handleDeleteProject = async () => {
    const ok2 = await confirmAction("Delete Project", `Delete "${project.name}"? All tasks will be lost.`); if (!ok2) return;
    try {
      await api.delete(`/projects/${project.project_id}`);
      toast.success("Project deleted");
      onBack();
      onRefresh();
    } catch (err) { handleError(err, "ProjectPanel:op5"); }
  };

  const handleStatusChange = async (status) => {
    try {
      await api.put(`/projects/${project.project_id}`, { status });
      toast.success("Status updated");
      onRefresh();
    } catch (err) { handleError(err, "ProjectPanel:op6"); }
  };

  const handleDeleteTask = async (taskId) => {
    try {
      await api.delete(`/projects/${project.project_id}/tasks/${taskId}`);
      toast.success("Task deleted");
      fetchTasks();
      onRefresh();
    } catch (err) { handleError(err, "ProjectPanel:op7"); }
  };

  const handleQuickStatus = async (taskId, newStatus) => {
    try {
      await api.put(`/projects/${project.project_id}/tasks/${taskId}`, { status: newStatus });
      fetchTasks();
      onRefresh();
    } catch (err) { handleSilent(err, "ProjectPanel:op4"); }
  };

  const toggleTaskSelect = (taskId) => {
    setSelectedTasks(prev => {
      const next = new Set(prev);
      next.has(taskId) ? next.delete(taskId) : next.add(taskId);
      return next;
    });
  };

  const selectAll = () => {
    if (selectedTasks.size === filteredTasks.length) {
      setSelectedTasks(new Set());
    } else {
      setSelectedTasks(new Set(filteredTasks.map(t => t.task_id)));
    }
  };

  const handleBulkUpdate = async (updates) => {
    if (selectedTasks.size === 0) return;
    try {
      await api.post(`/projects/${project.project_id}/tasks/bulk-update`, {
        task_ids: Array.from(selectedTasks),
        ...updates,
      });
      toast.success(`Updated ${selectedTasks.size} tasks`);
      setSelectedTasks(new Set());
      fetchTasks();
      onRefresh();
    } catch (err) { handleError(err, "ProjectPanel:op8"); }
  };

  const handleBulkDelete = async () => {
    if (selectedTasks.size === 0) return;
    const ok3 = await confirmAction("Delete Tasks", `Delete ${selectedTasks.size} tasks? This cannot be undone.`); if (!ok3) return;
    try {
      await api.post(`/projects/${project.project_id}/tasks/bulk-delete`, {
        task_ids: Array.from(selectedTasks),
      });
      toast.success(`Deleted ${selectedTasks.size} tasks`);
      setSelectedTasks(new Set());
      fetchTasks();
      onRefresh();
    } catch (err) { handleError(err, "ProjectPanel:op9"); }
  };

  // Filter tasks
  const filteredTasks = tasks.filter(t => {
    if (filterStatus && t.status !== filterStatus) return false;
    if (filterPriority && t.priority !== filterPriority) return false;
    if (filterAssignee && t.assignee_id !== filterAssignee) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      if (!t.title.toLowerCase().includes(q) && !(t.description || "").toLowerCase().includes(q)) return false;
    }
    return true;
  });

  const sc = STATUS_CONFIG[project.status] || STATUS_CONFIG.active;
  const StatusIcon = sc.icon;

  const linkedChannelNames = (project.linked_channels || []).map(cid => {
    const ch = channels.find(c => c.channel_id === cid);
    return ch ? ch.name : cid;
  });

  return (
    <div className="flex-1 flex flex-col min-h-0" data-testid="project-detail">
      {/* Header */}
      <div className="px-6 py-4 border-b border-zinc-800/60 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={onBack} className="text-zinc-400 hover:text-zinc-100 -ml-2" data-testid="project-back-btn">
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold text-zinc-100" style={{ fontFamily: 'Syne, sans-serif' }}>{project.name}</h2>
              <Badge className={`${sc.color} text-[10px] gap-1`}><StatusIcon className="w-3 h-3" />{sc.label}</Badge>
            </div>
            {project.description && <p className="text-xs text-zinc-500 mt-0.5">{project.description}</p>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Select value={project.status} onValueChange={handleStatusChange}>
            <SelectTrigger className="w-[130px] h-8 bg-zinc-900 border-zinc-800 text-xs" data-testid="project-status-select">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-zinc-900 border-zinc-800">
              {Object.entries(STATUS_CONFIG).map(([k, v]) => (
                <SelectItem key={k} value={k} className="text-zinc-300 text-xs">{v.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="ghost" size="sm" onClick={() => setEditProjectOpen(true)} className="text-zinc-400 hover:text-zinc-100" data-testid="edit-project-btn">
            <Pencil className="w-3.5 h-3.5" />
          </Button>
          <Button variant="ghost" size="sm" onClick={handleDeleteProject} className="text-red-400 hover:text-red-300" data-testid="delete-project-btn">
            <Trash2 className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>

      {/* Linked channels */}
      {linkedChannelNames.length > 0 && (
        <div className="px-6 py-2 border-b border-zinc-800/40 flex items-center gap-2">
          <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-600">Linked Channels:</span>
          {linkedChannelNames.map((n, i) => (
            <Badge key={i} className="bg-zinc-800 text-zinc-400 text-[10px]">#{n}</Badge>
          ))}
        </div>
      )}

      {/* Milestones section */}
      <div className="px-6 py-3 border-b border-zinc-800/40">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
            <Diamond className="w-3.5 h-3.5 text-amber-400" /> Milestones
            <Badge className="bg-zinc-800 text-zinc-500 text-[9px]">{milestones.length}</Badge>
          </span>
          <Button size="sm" variant="ghost" onClick={() => setMsDialogOpen(true)} className="text-zinc-400 hover:text-zinc-200 h-6 px-2 text-[10px]" data-testid="add-milestone-btn">
            <Plus className="w-3 h-3 mr-1" />Milestone
          </Button>
        </div>
        {milestones.length > 0 && (
          <div className="space-y-1.5">
            {milestones.map(m => (
              <div key={m.milestone_id} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-zinc-800/20 border border-zinc-800/30 group" data-testid={`milestone-${m.milestone_id}`}>
                <Diamond className={`w-3 h-3 flex-shrink-0 ${m.status === "completed" ? "text-emerald-400" : m.status === "in_progress" ? "text-amber-400" : "text-zinc-500"}`} />
                <span className="text-xs text-zinc-300 font-medium flex-1">{m.name}</span>
                {m.due_date && <span className="text-[10px] text-zinc-600">{m.due_date}</span>}
                <span className="text-[10px] text-zinc-500">{m.done_tasks}/{m.linked_tasks}</span>
                {m.linked_tasks > 0 && (
                  <div className="w-16 h-1.5 rounded-full bg-zinc-800 overflow-hidden">
                    <div className="h-full rounded-full bg-emerald-500 transition-all" style={{ width: `${m.progress}%` }} />
                  </div>
                )}
                <select
                  value={m.status}
                  onChange={(e) => updateMilestoneStatus(m.milestone_id, e.target.value)}
                  className="bg-transparent text-[9px] text-zinc-500 border-0 p-0 h-auto opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                >
                  <option value="open">Open</option>
                  <option value="in_progress">In Progress</option>
                  <option value="completed">Completed</option>
                </select>
                <button onClick={() => deleteMilestone(m.milestone_id)} className="text-zinc-700 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity" data-testid={`delete-ms-${m.milestone_id}`}>
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Milestone create dialog */}
      <Dialog open={msDialogOpen} onOpenChange={setMsDialogOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-zinc-100 flex items-center gap-2"><Diamond className="w-4 h-4 text-amber-400" />New Milestone</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 mt-2">
            <Input value={msName} onChange={(e) => setMsName(e.target.value)} placeholder="Milestone name" className="bg-zinc-950 border-zinc-800" autoFocus data-testid="ms-name-input" />
            <Input value={msDesc} onChange={(e) => setMsDesc(e.target.value)} placeholder="Description (optional)" className="bg-zinc-950 border-zinc-800" />
            <Input type="date" value={msDueDate} onChange={(e) => setMsDueDate(e.target.value)} className="bg-zinc-950 border-zinc-800 text-zinc-300" data-testid="ms-date-input" />
            <Button onClick={createMilestone} disabled={!msName.trim()} className="w-full bg-zinc-100 text-zinc-900 hover:bg-zinc-200" data-testid="ms-submit-btn">Create Milestone</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Tasks section with search/filter */}
      <div className="px-6 py-3 border-b border-zinc-800/40 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ListTodo className="w-4 h-4 text-zinc-400" />
            <span className="text-sm font-medium text-zinc-300">Tasks</span>
            <Badge className="bg-zinc-800 text-zinc-400 text-[10px]">{filteredTasks.length}{filteredTasks.length !== tasks.length ? `/${tasks.length}` : ""}</Badge>
          </div>
          <div className="flex items-center gap-2">
            {/* View toggle */}
            <div className="flex items-center rounded-lg bg-zinc-800/60 p-0.5" data-testid="view-toggle">
              {/* View mode toggle — segmented control with labels */}
              <div className="flex items-center bg-zinc-900 rounded-lg border border-zinc-800/50 p-0.5">
                <button
                  onClick={() => { setViewMode("list"); localStorage.setItem("nexus_task_view", "list"); }}
                  className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${viewMode === "list" ? "bg-zinc-700 text-zinc-100" : "text-zinc-500 hover:text-zinc-300"}`}
                  data-testid="view-toggle-list"
                >
                  <List className="w-3 h-3" /> List
                </button>
                <button
                  onClick={() => { setViewMode("kanban"); localStorage.setItem("nexus_task_view", "kanban"); }}
                  className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${viewMode === "kanban" ? "bg-zinc-700 text-zinc-100" : "text-zinc-500 hover:text-zinc-300"}`}
                  data-testid="view-toggle-kanban"
                >
                  <Columns3 className="w-3 h-3" /> Board
                </button>
                <button
                  onClick={() => { setViewMode("gantt"); localStorage.setItem("nexus_task_view", "gantt"); }}
                  className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${viewMode === "gantt" ? "bg-emerald-600 text-white" : "text-zinc-500 hover:text-zinc-300"}`}
                  data-testid="view-toggle-gantt"
                >
                  <BarChart3 className="w-3 h-3" /> Gantt
                </button>
              </div>
            </div>
            <Button size="sm" variant="outline" onClick={() => { setTaskToEdit(null); setTaskDialogOpen(true); }} className="border-zinc-700 text-zinc-300 hover:bg-zinc-800 gap-1.5 h-7 text-xs" data-testid="add-task-btn">
              <Plus className="w-3 h-3" /> Add Task
            </Button>
          </div>
        </div>

        {/* Search and filters */}
        {tasks.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap" data-testid="task-filters">
            <div className="relative flex-1 min-w-[180px] max-w-xs">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-zinc-500" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search tasks..."
                className="w-full bg-zinc-900 border border-zinc-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-700"
                data-testid="task-search-input"
              />
            </div>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="bg-zinc-900 border border-zinc-800 rounded-lg px-2 py-1.5 text-xs text-zinc-300 focus:outline-none focus:ring-1 focus:ring-zinc-700"
              data-testid="filter-status"
            >
              <option value="">All Status</option>
              {Object.entries(TASK_STATUS_CONFIG).map(([k, v]) => (
                <option key={k} value={k}>{v.label}</option>
              ))}
            </select>
            <select
              value={filterPriority}
              onChange={(e) => setFilterPriority(e.target.value)}
              className="bg-zinc-900 border border-zinc-800 rounded-lg px-2 py-1.5 text-xs text-zinc-300 focus:outline-none focus:ring-1 focus:ring-zinc-700"
              data-testid="filter-priority"
            >
              <option value="">All Priority</option>
              {Object.entries(PRIORITY_CONFIG).map(([k, v]) => (
                <option key={k} value={k}>{v.label}</option>
              ))}
            </select>
            {(filterStatus || filterPriority || filterAssignee || searchQuery) && (
              <button
                onClick={() => { setFilterStatus(""); setFilterPriority(""); setFilterAssignee(""); setSearchQuery(""); }}
                className="text-xs text-zinc-500 hover:text-zinc-300 flex items-center gap-1"
                data-testid="clear-filters"
              >
                <XIcon className="w-3 h-3" /> Clear
              </button>
            )}
          </div>
        )}

        {/* Bulk action bar */}
        {selectedTasks.size > 0 && viewMode === "list" && (
          <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-zinc-800/80 border border-zinc-700/60" data-testid="bulk-actions">
            <span className="text-xs text-zinc-300 font-medium">{selectedTasks.size} selected</span>
            <div className="h-3 w-px bg-zinc-700" />
            <select
              onChange={(e) => { if (e.target.value) { handleBulkUpdate({ status: e.target.value }); e.target.value = ""; } }}
              className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-[10px] text-zinc-300"
              data-testid="bulk-status-select"
            >
              <option value="">Set Status...</option>
              {Object.entries(TASK_STATUS_CONFIG).map(([k, v]) => (
                <option key={k} value={k}>{v.label}</option>
              ))}
            </select>
            <select
              onChange={(e) => { if (e.target.value) { handleBulkUpdate({ priority: e.target.value }); e.target.value = ""; } }}
              className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-[10px] text-zinc-300"
              data-testid="bulk-priority-select"
            >
              <option value="">Set Priority...</option>
              {Object.entries(PRIORITY_CONFIG).map(([k, v]) => (
                <option key={k} value={k}>{v.label}</option>
              ))}
            </select>
            <button
              onClick={handleBulkDelete}
              className="ml-auto text-[10px] text-red-400 hover:text-red-300 flex items-center gap-1 px-2 py-1 rounded hover:bg-red-900/20"
              data-testid="bulk-delete-btn"
            >
              <Trash2 className="w-3 h-3" /> Delete
            </button>
            <button
              onClick={() => setSelectedTasks(new Set())}
              className="text-[10px] text-zinc-500 hover:text-zinc-300 px-1"
            >
              <XIcon className="w-3 h-3" />
            </button>
          </div>
        )}
      </div>

      {/* Task content - List or Kanban */}
      {loading ? (
        <div className="p-6 text-center text-sm text-zinc-500">Loading tasks...</div>
      ) : filteredTasks.length === 0 ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <ListTodo className="w-8 h-8 text-zinc-700 mx-auto mb-2" />
            <p className="text-sm text-zinc-500">{tasks.length === 0 ? "No tasks yet" : "No tasks match filters"}</p>
            <p className="text-xs text-zinc-600 mt-1">{tasks.length === 0 ? "Add a task to get started" : "Try adjusting your search or filters"}</p>
          </div>
        </div>
      ) : viewMode === "gantt" ? (
        <div className="flex-1 overflow-auto" data-testid="gantt-view">
          <ProjectGantt projectId={project.project_id} tasks={filteredTasks} milestones={[]} />
        </div>
      ) : viewMode === "kanban" ? (
        <KanbanBoard
          tasks={filteredTasks}
          projectId={project.project_id}
          onEdit={(t) => { setTaskToEdit(t); setTaskDialogOpen(true); }}
          onDelete={handleDeleteTask}
          onRefresh={() => { fetchTasks(); onRefresh(); }}
        />
      ) : (
        <ScrollArea className="flex-1">
          <div className="p-3 space-y-1.5">
            {/* Select all header */}
            {filteredTasks.length > 1 && (
              <div className="flex items-center gap-2 px-3 py-1">
                <button onClick={selectAll} className="flex-shrink-0" data-testid="select-all-tasks">
                  {selectedTasks.size === filteredTasks.length ? (
                    <CheckSquare className="w-4 h-4 text-blue-400" />
                  ) : (
                    <Square className="w-4 h-4 text-zinc-600" />
                  )}
                </button>
                <span className="text-[10px] text-zinc-500 font-mono">{selectedTasks.size === filteredTasks.length ? "Deselect all" : "Select all"}</span>
              </div>
            )}
            {filteredTasks.map((t) => {
              const ts = TASK_STATUS_CONFIG[t.status] || TASK_STATUS_CONFIG.todo;
              const TIcon = ts.icon;
              const pc = PRIORITY_CONFIG[t.priority] || PRIORITY_CONFIG.medium;
              const PIcon = pc.icon;
              const statusKeys = Object.keys(TASK_STATUS_CONFIG);
              const nextIdx = (statusKeys.indexOf(t.status) + 1) % statusKeys.length;
              const isSelected = selectedTasks.has(t.task_id);
              return (
                <div key={t.task_id} className={`flex items-center gap-3 p-3 rounded-lg border group transition-colors ${isSelected ? "bg-zinc-800/60 border-zinc-600" : "bg-zinc-900/40 border-zinc-800/40 hover:border-zinc-700/60"}`} data-testid={`task-row-${t.task_id}`}>
                  <button onClick={() => toggleTaskSelect(t.task_id)} className="flex-shrink-0" data-testid={`task-select-${t.task_id}`}>
                    {isSelected ? <CheckSquare className="w-4 h-4 text-blue-400" /> : <Square className="w-4 h-4 text-zinc-700 group-hover:text-zinc-500" />}
                  </button>
                  <button onClick={() => handleQuickStatus(t.task_id, statusKeys[nextIdx])} className="flex-shrink-0" title={`Click to change to ${TASK_STATUS_CONFIG[statusKeys[nextIdx]].label}`}>
                    <TIcon className={`w-4 h-4 ${ts.color.split(' ')[1]}`} />
                  </button>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`text-sm font-medium ${t.status === 'done' ? 'text-zinc-500 line-through' : 'text-zinc-200'}`}>{t.title}</span>
                      <PIcon className={`w-3 h-3 ${pc.color} flex-shrink-0`} />
                    </div>
                    {t.assignee_name && (
                      <div className="flex items-center gap-1 mt-0.5">
                        {t.assignee_type === "ai" ? <Bot className="w-3 h-3 text-zinc-600" /> : <User className="w-3 h-3 text-zinc-600" />}
                        <span className="text-[11px] text-zinc-500">{t.assignee_name}</span>
                      </div>
                    )}
                  </div>
                  <Badge className={`${ts.color} text-[9px] flex-shrink-0`}>{ts.label}</Badge>
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button onClick={() => { setTaskToEdit(t); setTaskDialogOpen(true); }} className="p-1 rounded text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800" data-testid={`edit-task-${t.task_id}`}>
                      <Pencil className="w-3 h-3" />
                    </button>
                    <button onClick={() => handleDeleteTask(t.task_id)} className="p-1 rounded text-zinc-500 hover:text-red-400 hover:bg-zinc-800" data-testid={`delete-task-${t.task_id}`}>
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </ScrollArea>
      )}

      {/* Task Create/Edit Dialog */}
      <TaskDialog
        open={taskDialogOpen}
        onOpenChange={setTaskDialogOpen}
        projectId={project.project_id}
        task={taskToEdit}
        members={members}
        onDone={() => { fetchTasks(); onRefresh(); }}
      />

      {/* Edit Project Dialog */}
      <EditProjectDialog
        open={editProjectOpen}
        onOpenChange={setEditProjectOpen}
        project={project}
        channels={channels}
        onDone={onRefresh}
      />
    </div>
  );
}

// =================== Task Dialog ===================
function TaskDialog({ open, onOpenChange, projectId, task, members, onDone }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState("todo");
  const [priority, setPriority] = useState("medium");
  const [assigneeType, setAssigneeType] = useState("");
  const [assigneeId, setAssigneeId] = useState("");
  const [assigneeName, setAssigneeName] = useState("");

  useEffect(() => {
    if (task) {
      setTitle(task.title); setDescription(task.description || "");
      setStatus(task.status); setPriority(task.priority);
      setAssigneeType(task.assignee_type || ""); setAssigneeId(task.assignee_id || "");
      setAssigneeName(task.assignee_name || "");
    } else {
      setTitle(""); setDescription(""); setStatus("todo"); setPriority("medium");
      setAssigneeType(""); setAssigneeId(""); setAssigneeName("");
    }
  }, [task, open]);

  const handleSubmit = async () => {
    if (!title.trim()) return;
    const payload = {
      title: title.trim(), description: description.trim(),
      status, priority,
      assignee_type: assigneeType || null,
      assignee_id: assigneeId || null,
      assignee_name: assigneeName || null,
    };
    try {
      if (task) {
        await api.put(`/projects/${projectId}/tasks/${task.task_id}`, payload);
        toast.success("Task updated");
      } else {
        await api.post(`/projects/${projectId}/tasks`, payload);
        toast.success("Task created");
      }
      onOpenChange(false);
      onDone();
    } catch (err) { handleError(err, "ProjectPanel:op10"); }
  };

  const handleAssigneeSelect = (type, id, name) => {
    setAssigneeType(type); setAssigneeId(id); setAssigneeName(name);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-zinc-900 border-zinc-800 max-w-md">
        <DialogHeader>
          <DialogTitle className="text-zinc-100">{task ? "Edit Task" : "New Task"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 mt-2">
          <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Task title" className="bg-zinc-950 border-zinc-800" data-testid="task-title-input" autoFocus />
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Description (optional)" rows={3} className="w-full rounded-md bg-zinc-950 border border-zinc-800 text-sm text-zinc-200 px-3 py-2 placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600" data-testid="task-desc-input" />

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 mb-1 block">Status</label>
              <Select value={status} onValueChange={setStatus}>
                <SelectTrigger className="bg-zinc-950 border-zinc-800 text-xs h-8" data-testid="task-status-select"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-zinc-900 border-zinc-800">
                  {Object.entries(TASK_STATUS_CONFIG).map(([k, v]) => (
                    <SelectItem key={k} value={k} className="text-zinc-300 text-xs">{v.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 mb-1 block">Priority</label>
              <Select value={priority} onValueChange={setPriority}>
                <SelectTrigger className="bg-zinc-950 border-zinc-800 text-xs h-8" data-testid="task-priority-select"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-zinc-900 border-zinc-800">
                  {Object.entries(PRIORITY_CONFIG).map(([k, v]) => (
                    <SelectItem key={k} value={k} className="text-zinc-300 text-xs">{v.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Assignee */}
          <div>
            <label className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 mb-1.5 block">Assign To</label>
            <div className="flex gap-2 mb-2">
              <button onClick={() => handleAssigneeSelect("", "", "")} className={`px-2.5 py-1 rounded text-xs transition-colors ${!assigneeType ? 'bg-zinc-700 text-zinc-200' : 'bg-zinc-900 text-zinc-500 hover:bg-zinc-800'}`}>None</button>
              <button onClick={() => setAssigneeType("human")} className={`px-2.5 py-1 rounded text-xs transition-colors flex items-center gap-1 ${assigneeType === 'human' ? 'bg-zinc-700 text-zinc-200' : 'bg-zinc-900 text-zinc-500 hover:bg-zinc-800'}`}><User className="w-3 h-3" />Human</button>
              <button onClick={() => setAssigneeType("ai")} className={`px-2.5 py-1 rounded text-xs transition-colors flex items-center gap-1 ${assigneeType === 'ai' ? 'bg-zinc-700 text-zinc-200' : 'bg-zinc-900 text-zinc-500 hover:bg-zinc-800'}`}><Bot className="w-3 h-3" />AI Agent</button>
            </div>
            {assigneeType === "human" && members && (
              <Select value={assigneeId} onValueChange={(v) => { setAssigneeId(v); setAssigneeName(members.find(m => m.user_id === v)?.name || v); }}>
                <SelectTrigger className="bg-zinc-950 border-zinc-800 text-xs h-8" data-testid="task-human-assignee"><SelectValue placeholder="Select member" /></SelectTrigger>
                <SelectContent className="bg-zinc-900 border-zinc-800">
                  {(members || []).map(m => (
                    <SelectItem key={m.user_id} value={m.user_id} className="text-zinc-300 text-xs">{m.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            {assigneeType === "ai" && (
              <Select value={assigneeId} onValueChange={(v) => { setAssigneeId(v); setAssigneeName(AI_AGENTS.find(a => a.key === v)?.name || v); }}>
                <SelectTrigger className="bg-zinc-950 border-zinc-800 text-xs h-8" data-testid="task-ai-assignee"><SelectValue placeholder="Select AI agent" /></SelectTrigger>
                <SelectContent className="bg-zinc-900 border-zinc-800">
                  {AI_AGENTS.map(a => (
                    <SelectItem key={a.key} value={a.key} className="text-zinc-300 text-xs">{a.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>

          <Button onClick={handleSubmit} disabled={!title.trim()} className="w-full bg-zinc-100 text-zinc-900 hover:bg-zinc-200 font-medium" data-testid="task-submit-btn">
            {task ? "Update Task" : "Create Task"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// =================== Edit Project Dialog ===================
function EditProjectDialog({ open, onOpenChange, project, channels, onDone }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [linked, setLinked] = useState([]);

  useEffect(() => {
    if (project) {
      setName(project.name); setDescription(project.description || "");
      setLinked(project.linked_channels || []);
    }
  }, [project, open]);

  const toggleChannel = (cid) => {
    setLinked(prev => prev.includes(cid) ? prev.filter(c => c !== cid) : [...prev, cid]);
  };

  const handleSubmit = async () => {
    if (!name.trim()) return;
    try {
      await api.put(`/projects/${project.project_id}`, { name: name.trim(), description: description.trim(), linked_channels: linked });
      toast.success("Project updated");
      onOpenChange(false);
      onDone();
    } catch (err) { handleError(err, "ProjectPanel:op11"); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-zinc-900 border-zinc-800 max-w-md">
        <DialogHeader>
          <DialogTitle className="text-zinc-100">Edit Project</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 mt-2">
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Project name" className="bg-zinc-950 border-zinc-800" data-testid="edit-project-name" autoFocus />
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Description" rows={3} className="w-full rounded-md bg-zinc-950 border border-zinc-800 text-sm text-zinc-200 px-3 py-2 placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600" data-testid="edit-project-desc" />
          <div>
            <label className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 mb-1.5 block">Link Channels</label>
            <div className="max-h-32 overflow-y-auto space-y-1">
              {(channels || []).map(ch => (
                <label key={ch.channel_id} className="flex items-center gap-2 p-1.5 rounded hover:bg-zinc-800/50 cursor-pointer text-xs text-zinc-300">
                  <input type="checkbox" checked={linked.includes(ch.channel_id)} onChange={() => toggleChannel(ch.channel_id)} className="accent-zinc-400" />
                  <span>#{ch.name}</span>
                </label>
              ))}
            </div>
          </div>
          <Button onClick={handleSubmit} disabled={!name.trim()} className="w-full bg-zinc-100 text-zinc-900 hover:bg-zinc-200 font-medium" data-testid="edit-project-submit">Save</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// =================== Create Project Dialog ===================
function CreateProjectDialog({ open, onOpenChange, workspaceId, channels, onDone }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [linked, setLinked] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [creatingFromTemplate, setCreatingFromTemplate] = useState(false);

  useEffect(() => {
    if (open) {
      setName(""); setDescription(""); setLinked([]);
      api.get("/project-templates").then(r => setTemplates(r.data.templates || [])).catch(() => {});
    }
  }, [open]);

  const toggleChannel = (cid) => {
    setLinked(prev => prev.includes(cid) ? prev.filter(c => c !== cid) : [...prev, cid]);
  };

  const handleSubmit = async () => {
    if (!name.trim()) return;
    try {
      await api.post(`/workspaces/${workspaceId}/projects`, { name: name.trim(), description: description.trim(), linked_channels: linked });
      toast.success("Project created");
      onOpenChange(false);
      onDone();
    } catch (err) { handleError(err, "ProjectPanel:op12"); }
  };

  const handleCreateFromTemplate = async (templateId) => {
    setCreatingFromTemplate(true);
    try {
      const res = await api.post(`/workspaces/${workspaceId}/projects/from-template`, {
        template_id: templateId, name: name.trim() || undefined,
      });
      toast.success(`Project created with ${res.data.milestones_created} milestones and ${res.data.tasks_created} tasks`);
      onOpenChange(false);
      onDone();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
    setCreatingFromTemplate(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-zinc-900 border-zinc-800 max-w-md">
        <DialogHeader>
          <DialogTitle className="text-zinc-100" style={{ fontFamily: 'Syne, sans-serif' }}>New Project</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 mt-2">
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Project name" className="bg-zinc-950 border-zinc-800" data-testid="new-project-name" autoFocus />
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Description (optional)" rows={3} className="w-full rounded-md bg-zinc-950 border border-zinc-800 text-sm text-zinc-200 px-3 py-2 placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600" data-testid="new-project-desc" />
          {(channels || []).length > 0 && (
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 mb-1.5 block">Link Channels (optional)</label>
              <div className="max-h-32 overflow-y-auto space-y-1">
                {channels.map(ch => (
                  <label key={ch.channel_id} className="flex items-center gap-2 p-1.5 rounded hover:bg-zinc-800/50 cursor-pointer text-xs text-zinc-300">
                    <input type="checkbox" checked={linked.includes(ch.channel_id)} onChange={() => toggleChannel(ch.channel_id)} className="accent-zinc-400" />
                    <span>#{ch.name}</span>
                  </label>
                ))}
              </div>
            </div>
          )}
          <Button onClick={handleSubmit} disabled={!name.trim()} className="w-full bg-zinc-100 text-zinc-900 hover:bg-zinc-200 font-medium" data-testid="new-project-submit">Create Project</Button>
          {templates.length > 0 && (
            <div className="pt-3 border-t border-zinc-800">
              <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold mb-2">Or start from a template</p>
              <div className="space-y-1.5">
                {templates.map(t => (
                  <button key={t.template_id} onClick={() => handleCreateFromTemplate(t.template_id)} disabled={creatingFromTemplate}
                    className="w-full text-left px-3 py-2 rounded-lg bg-zinc-800/30 border border-zinc-800/40 hover:border-zinc-700 transition-colors" data-testid={`template-${t.template_id}`}>
                    <span className="text-xs text-zinc-200 font-medium">{t.name}</span>
                    <span className="text-[10px] text-zinc-500 ml-2">{t.milestone_count} milestones, {t.task_count} tasks</span>
                    <p className="text-[10px] text-zinc-600 mt-0.5">{t.description}</p>
                  </button>
                ))}
              </div>
            </div>
          )}
    </div>
      </DialogContent>
    </Dialog>
  );
}

// =================== Main Export ===================
export default function ProjectPanel({ workspaceId, channels, members, onProjectChange }) {
  const { confirm: confirmAction, ConfirmDialog: ConfirmDlg } = useConfirm();
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [initialView, setInitialView] = useState(null);

  const fetchProjects = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/projects`);
      setProjects(res.data);
      if (selectedProject) {
        const updated = res.data.find(p => p.project_id === selectedProject.project_id);
        if (updated) setSelectedProject(updated);
        else setSelectedProject(null);
      }
      if (onProjectChange) onProjectChange();
    } catch (err) { handleSilent(err, "ProjectPanel:op5"); } finally { setLoading(false); }
  }, [workspaceId]);

  useEffect(() => { fetchProjects(); }, [fetchProjects]);

  if (selectedProject) {
    return (
      <ProjectDetail
        project={selectedProject}
        channels={channels}
        onBack={() => { setSelectedProject(null); setInitialView(null); }}
        onRefresh={fetchProjects}
        workspaceId={workspaceId}
        members={members}
        initialViewMode={initialView}
      />
    );
  }

  return (
    <>
      <ProjectList
        projects={projects}
        loading={loading}
        onSelect={(p) => { setInitialView(null); setSelectedProject(p); }}
        onCreate={() => setCreateOpen(true)}
        onOpenGantt={(p) => { setInitialView("gantt"); setSelectedProject(p); }}
      />
      <CreateProjectDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        workspaceId={workspaceId}
        channels={channels}
        onDone={fetchProjects}
      />
      <ConfirmDlg />
    </>
  );
}
