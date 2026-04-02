import { useState, useEffect, useCallback } from "react";
import { api } from "@/App";
import { handleError } from "@/lib/errorHandler";
import { toast } from "sonner";
import { CalendarDays, Plus, ChevronLeft, ChevronRight, X, Clock, AlertTriangle, CheckCircle2 } from "lucide-react";

const PRIORITY_COLORS = { high: "#ef4444", medium: "#f59e0b", low: "#3b82f6" };
const STATUS_LABELS = { todo: "To Do", in_progress: "In Progress", done: "Done", completed: "Done" };

export default function PlannerCalendar({ workspaceId }) {
  const [tasks, setTasks] = useState([]);
  const [byDate, setByDate] = useState({});
  const [overdue, setOverdue] = useState([]);
  const [loading, setLoading] = useState(true);
  const [currentDate, setCurrentDate] = useState(new Date());
  const [showCreate, setShowCreate] = useState(null); // date string or null
  const [newTitle, setNewTitle] = useState("");
  const [newPriority, setNewPriority] = useState("medium");
  const [creating, setCreating] = useState(false);

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();
  const monthName = currentDate.toLocaleString("default", { month: "long" });

  const fetchPlanner = useCallback(async () => {
    try {
      setLoading(true);
      const start = new Date(year, month, 1).toISOString().split("T")[0];
      const end = new Date(year, month + 1, 0).toISOString().split("T")[0];
      const { data } = await api.get(`/workspaces/${workspaceId}/planner?start=${start}&end=${end}`);
      setTasks(data.tasks || []);
      setByDate(data.by_date || {});
      setOverdue(data.overdue || []);
    } catch (e) {
      handleError(e, "PlannerCalendar");
    } finally {
      setLoading(false);
    }
  }, [workspaceId, year, month]);

  useEffect(() => { fetchPlanner(); }, [fetchPlanner]);

  const createTask = async () => {
    if (!newTitle.trim() || !showCreate) return;
    setCreating(true);
    try {
      await api.post(`/workspaces/${workspaceId}/tasks`, {
        title: newTitle.trim(),
        due_date: showCreate,
        priority: newPriority,
        status: "todo",
      });
      toast.success("Task created");
      setNewTitle("");
      setShowCreate(null);
      fetchPlanner();
    } catch (e) {
      handleError(e, "PlannerCalendar.createTask");
    } finally {
      setCreating(false);
    }
  };

  const toggleStatus = async (task) => {
    const newStatus = task.status === "done" || task.status === "completed" ? "todo" : "done";
    const collection = task.source === "project" ? "project-tasks" : "tasks";
    const idField = task.task_id;
    try {
      await api.put(`/${collection}/${idField}`, { status: newStatus });
      fetchPlanner();
    } catch (err) {
      // Fallback: try workspace tasks endpoint
      try {
        await api.put(`/tasks/${idField}`, { status: newStatus });
        fetchPlanner();
      } catch (e) {
        handleError(e, "PlannerCalendar.toggleStatus");
      }
    }
  };

  // Calendar grid
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const today = new Date().toISOString().split("T")[0];
  const cells = [];
  for (let i = 0; i < firstDay; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);

  const prevMonth = () => setCurrentDate(new Date(year, month - 1, 1));
  const nextMonth = () => setCurrentDate(new Date(year, month + 1, 1));
  const goToday = () => setCurrentDate(new Date());

  return (
    <div className="h-full flex flex-col" data-testid="planner-calendar">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <CalendarDays size={18} className="text-cyan-400" />
          <h2 className="text-lg font-semibold text-zinc-100">{monthName} {year}</h2>
          <span className="text-xs text-zinc-500">{tasks.length} task{tasks.length !== 1 ? "s" : ""}</span>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={prevMonth} className="p-1.5 rounded hover:bg-zinc-800 text-zinc-400" data-testid="planner-prev">
            <ChevronLeft size={16} />
          </button>
          <button onClick={goToday} className="px-2 py-1 text-xs rounded hover:bg-zinc-800 text-zinc-400" data-testid="planner-today">Today</button>
          <button onClick={nextMonth} className="p-1.5 rounded hover:bg-zinc-800 text-zinc-400" data-testid="planner-next">
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      {/* Overdue banner */}
      {overdue.length > 0 && (
        <div className="mb-3 px-3 py-2 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center gap-2" data-testid="overdue-banner">
          <AlertTriangle size={14} className="text-red-400 flex-shrink-0" />
          <span className="text-xs text-red-300">{overdue.length} overdue task{overdue.length !== 1 ? "s" : ""}</span>
        </div>
      )}

      {/* Day headers */}
      <div className="grid grid-cols-7 gap-px mb-px">
        {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map(d => (
          <div key={d} className="text-[10px] font-medium text-zinc-500 text-center py-1">{d}</div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7 gap-px flex-1 auto-rows-fr" data-testid="planner-grid">
        {cells.map((day, i) => {
          if (!day) return <div key={`e-${i}`} className="bg-zinc-900/30 rounded" />;
          const dateStr = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
          const dayTasks = byDate[dateStr] || [];
          const isToday = dateStr === today;
          const isPast = dateStr < today;
          const hasOverdue = dayTasks.some(t => isPast && t.status !== "done" && t.status !== "completed");

          return (
            <div
              key={dateStr}
              className={`rounded border p-1 min-h-[72px] cursor-pointer transition-colors group
                ${isToday ? "border-cyan-500/40 bg-cyan-500/5" : "border-zinc-800/60 bg-zinc-900/40 hover:border-zinc-700"}
                ${hasOverdue ? "border-red-500/30" : ""}`}
              onClick={() => { setShowCreate(dateStr); setNewTitle(""); }}
              data-testid={`planner-day-${dateStr}`}
            >
              <div className="flex items-center justify-between mb-0.5">
                <span className={`text-[11px] font-medium ${isToday ? "text-cyan-400" : isPast ? "text-zinc-600" : "text-zinc-400"}`}>{day}</span>
                <Plus size={10} className="text-zinc-600 opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
              {dayTasks.slice(0, 3).map(t => (
                <div
                  key={t.task_id}
                  className="text-[10px] leading-tight py-0.5 px-1 mb-0.5 rounded truncate flex items-center gap-1 cursor-pointer"
                  style={{ background: `${PRIORITY_COLORS[t.priority] || "#3b82f6"}15`, color: PRIORITY_COLORS[t.priority] || "#3b82f6" }}
                  onClick={(e) => { e.stopPropagation(); toggleStatus(t); }}
                  title={`${t.title} (${t.status}) — click to toggle`}
                  data-testid={`planner-task-${t.task_id}`}
                >
                  {t.status === "done" || t.status === "completed"
                    ? <CheckCircle2 size={8} className="flex-shrink-0" />
                    : <Clock size={8} className="flex-shrink-0" />}
                  <span className={t.status === "done" || t.status === "completed" ? "line-through opacity-60" : ""}>{t.title}</span>
                </div>
              ))}
              {dayTasks.length > 3 && (
                <div className="text-[9px] text-zinc-500 pl-1">+{dayTasks.length - 3} more</div>
              )}
            </div>
          );
        })}
      </div>

      {/* Empty state */}
      {!loading && tasks.length === 0 && (
        <div className="text-center py-8" data-testid="planner-empty">
          <CalendarDays size={32} className="mx-auto text-zinc-700 mb-3" />
          <p className="text-sm text-zinc-400 mb-1">No tasks scheduled this month</p>
          <p className="text-xs text-zinc-600">Click any day to create a task with a due date</p>
        </div>
      )}

      {/* Quick-create modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowCreate(null)} data-testid="planner-create-modal">
          <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-4 w-80 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-zinc-100">New Task</h3>
              <button onClick={() => setShowCreate(null)} className="text-zinc-500 hover:text-zinc-300"><X size={14} /></button>
            </div>
            <div className="text-xs text-zinc-500 mb-3">Due: {showCreate}</div>
            <input
              autoFocus
              value={newTitle}
              onChange={e => setNewTitle(e.target.value)}
              onKeyDown={e => e.key === "Enter" && createTask()}
              placeholder="Task title..."
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-cyan-500/50 mb-3"
              data-testid="planner-task-title-input"
            />
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs text-zinc-500">Priority:</span>
              {["low", "medium", "high"].map(p => (
                <button
                  key={p}
                  onClick={() => setNewPriority(p)}
                  className={`px-2 py-0.5 text-[10px] font-medium rounded-full border transition-colors ${
                    newPriority === p
                      ? `border-current` : "border-zinc-700 text-zinc-500"}`}
                  style={newPriority === p ? { color: PRIORITY_COLORS[p], borderColor: PRIORITY_COLORS[p] + "60" } : {}}
                  data-testid={`planner-priority-${p}`}
                >
                  {p}
                </button>
              ))}
            </div>
            <button
              onClick={createTask}
              disabled={!newTitle.trim() || creating}
              className="w-full py-2 bg-cyan-500/20 text-cyan-400 text-sm font-medium rounded-lg border border-cyan-500/30 hover:bg-cyan-500/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              data-testid="planner-create-btn"
            >
              {creating ? "Creating..." : "Create Task"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
