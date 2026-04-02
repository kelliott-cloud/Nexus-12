import { useState, useEffect, useCallback, useMemo } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ChevronLeft, ChevronRight, ChevronDown, Diamond, FolderKanban, BarChart3, Filter, Check } from "lucide-react";
import { api } from "@/App";

const STATUS_COLORS = {
  todo: "#71717a", in_progress: "#3b82f6", review: "#f59e0b", done: "#22c55e",
};
const NAME_COL = 320;

export default function GanttChart({ workspaceId }) {
  const [portfolio, setPortfolio] = useState(null);
  const [loading, setLoading] = useState(true);
  const [zoomLevel, setZoomLevel] = useState("week");
  const [startOffset, setStartOffset] = useState(0);
  const [expandedProjects, setExpandedProjects] = useState({});
  const [selectedProjects, setSelectedProjects] = useState(null); // null = all
  const [showFilter, setShowFilter] = useState(false);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const res = await api.get(`/workspaces/${workspaceId}/portfolio`);
        setPortfolio(res.data);
        const expanded = {};
        (res.data?.projects || []).forEach(p => { expanded[p.project_id] = false; }); // Start collapsed
        setExpandedProjects(expanded);
      } catch (err) { handleSilent(err, "GanttChart:op1"); }
      setLoading(false);
    })();
  }, [workspaceId]);

  const cfg = useMemo(() => ({
    day: { unitDays: 1, units: 30, unitWidth: 32 },
    week: { unitDays: 7, units: 12, unitWidth: 80 },
    month: { unitDays: 30, units: 6, unitWidth: 160 },
  })[zoomLevel], [zoomLevel]);

  const totalWidth = cfg.units * cfg.unitWidth;
  const now = new Date();
  const startDate = useMemo(() => {
    const d = new Date(now);
    d.setDate(d.getDate() - cfg.unitDays * 2 + startOffset * cfg.unitDays * 3);
    d.setHours(0, 0, 0, 0);
    return d;
  }, [startOffset, cfg.unitDays]);

  const headers = useMemo(() => {
    const h = [];
    for (let i = 0; i < cfg.units; i++) {
      const d = new Date(startDate);
      d.setDate(d.getDate() + i * cfg.unitDays);
      h.push(d);
    }
    return h;
  }, [startDate, cfg]);

  const todayOffset = (now - startDate) / (1000 * 60 * 60 * 24) * (cfg.unitWidth / cfg.unitDays);

  const formatHeader = (d) => {
    if (zoomLevel === "day") return d.getDate();
    if (zoomLevel === "week") return d.toLocaleDateString([], { month: "short", day: "numeric" });
    return d.toLocaleDateString([], { month: "short", year: "2-digit" });
  };

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

  // Get project date range for rollup bar
  const getProjectBar = (tasks) => {
    if (!tasks.length) return null;
    const dates = tasks.filter(t => t.due_date || t.created_at).map(t => {
      const created = t.created_at ? new Date(t.created_at) : new Date();
      const due = t.due_date ? new Date(t.due_date) : created;
      return { start: Math.min(created.getTime(), due.getTime()), end: due.getTime() };
    });
    if (!dates.length) return null;
    const earliest = new Date(Math.min(...dates.map(d => d.start)));
    const latest = new Date(Math.max(...dates.map(d => d.end)));
    const leftDays = (earliest - startDate) / (1000 * 60 * 60 * 24);
    const widthDays = Math.max(1, (latest - earliest) / (1000 * 60 * 60 * 24));
    const pxPerDay = cfg.unitWidth / cfg.unitDays;
    return { left: leftDays * pxPerDay, width: Math.max(widthDays * pxPerDay, 20) };
  };

  const toggleProject = (pid) => setExpandedProjects(prev => ({ ...prev, [pid]: !prev[pid] }));
  const toggleFilter = (pid) => {
    setSelectedProjects(prev => {
      if (!prev) { const s = new Set(portfolio.projects.map(p => p.project_id)); s.delete(pid); return s; }
      const next = new Set(prev);
      if (next.has(pid)) next.delete(pid); else next.add(pid);
      if (next.size === portfolio.projects.length) return null; // All selected = no filter
      return next;
    });
  };

  if (loading) return <div className="flex items-center justify-center py-16"><BarChart3 className="w-8 h-8 text-zinc-700 animate-pulse" /></div>;
  if (!portfolio || !portfolio.total_projects) return (
    <div className="flex items-center justify-center py-16 text-center" data-testid="gantt-empty">
      <div>
        <BarChart3 className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
        <p className="text-sm text-zinc-400 mb-1">No projects with tasks yet</p>
        <p className="text-xs text-zinc-600">Create a project in the Projects tab, then add tasks with due dates to see them here</p>
      </div>
    </div>
  );

  const tasksByProject = {};
  (portfolio.gantt?.tasks || []).forEach(t => {
    const pid = t.project_id || "unknown";
    if (!tasksByProject[pid]) tasksByProject[pid] = [];
    tasksByProject[pid].push(t);
  });

  const visibleProjects = portfolio.projects.filter(p => !selectedProjects || selectedProjects.has(p.project_id));

  // Full timeline rollup
  const allVisibleTasks = visibleProjects.flatMap(p => tasksByProject[p.project_id] || []);
  const fullTimelineBar = getProjectBar(allVisibleTasks);
  const totalProgress = allVisibleTasks.length > 0 ? Math.round(allVisibleTasks.filter(t => t.status === "done").length / allVisibleTasks.length * 100) : 0;

  return (
    <div className="flex flex-col h-full" data-testid="portfolio-gantt">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-zinc-800/40 bg-zinc-900/30 flex-shrink-0">
        <FolderKanban className="w-4 h-4 text-purple-400" />
        <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">Portfolio</span>
        <Badge className="bg-purple-500/15 text-purple-400 text-[9px]">{visibleProjects.length}/{portfolio.total_projects} projects</Badge>
        <Badge className="bg-zinc-800 text-zinc-400 text-[9px]">{allVisibleTasks.length} tasks</Badge>
        <div className="flex-1" />

        {/* Project filter */}
        <div className="relative">
          <button onClick={() => setShowFilter(!showFilter)} className={`flex items-center gap-1 px-2 py-1 rounded text-[10px] transition-colors ${selectedProjects ? "bg-purple-500/15 text-purple-400" : "text-zinc-500 hover:text-zinc-300 bg-zinc-800/40"}`} data-testid="gantt-filter-btn">
            <Filter className="w-3 h-3" /> {selectedProjects ? `${selectedProjects.size} selected` : "All projects"}
          </button>
          {showFilter && (
            <div className="absolute top-full right-0 mt-1 w-56 bg-zinc-900 border border-zinc-800 rounded-lg shadow-xl z-50 py-1" data-testid="gantt-filter-dropdown">
              {portfolio.projects.map(p => {
                const isSelected = !selectedProjects || selectedProjects.has(p.project_id);
                return (
                  <button key={p.project_id} onClick={() => toggleFilter(p.project_id)}
                    className="w-full text-left px-3 py-1.5 flex items-center gap-2 text-xs hover:bg-zinc-800 transition-colors">
                    <div className={`w-3.5 h-3.5 rounded border flex items-center justify-center ${isSelected ? "bg-purple-500 border-purple-500" : "border-zinc-700"}`}>
                      {isSelected && <Check className="w-2.5 h-2.5 text-white" />}
                    </div>
                    <span className={isSelected ? "text-zinc-300" : "text-zinc-600"}>{p.name}</span>
                    <span className="text-[9px] text-zinc-600 ml-auto">{p.tasks_done}/{p.task_count}</span>
                  </button>
                );
              })}
              <div className="border-t border-zinc-800 mt-1 pt-1 px-3 pb-1">
                <button onClick={() => { setSelectedProjects(null); setShowFilter(false); }} className="text-[10px] text-zinc-500 hover:text-zinc-300">Show all</button>
              </div>
            </div>
          )}
        </div>

        <button onClick={() => setStartOffset(o => o - 3)} className="p-1 rounded hover:bg-zinc-800 text-zinc-400"><ChevronLeft className="w-4 h-4" /></button>
        <button onClick={() => setStartOffset(0)} className="text-[10px] text-zinc-500 hover:text-zinc-300 px-2 py-0.5 rounded bg-zinc-800/40">Today</button>
        <button onClick={() => setStartOffset(o => o + 3)} className="p-1 rounded hover:bg-zinc-800 text-zinc-400"><ChevronRight className="w-4 h-4" /></button>
        <div className="flex gap-1 ml-1">
          {["day", "week", "month"].map(z => (
            <button key={z} onClick={() => setZoomLevel(z)} className={`text-[10px] px-2 py-0.5 rounded capitalize ${zoomLevel === z ? "bg-zinc-700 text-zinc-200" : "text-zinc-500 hover:text-zinc-300"}`}>{z}</button>
          ))}
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div style={{ minWidth: totalWidth + NAME_COL }}>
          {/* Column headers */}
          <div className="flex border-b border-zinc-800/40 sticky top-0 bg-zinc-950 z-10">
            <div className="flex-shrink-0 px-3 py-1.5 text-[10px] text-zinc-500 font-semibold uppercase tracking-wider" style={{ width: NAME_COL }}>Project / Task</div>
            <div className="flex-1 flex relative">
              {headers.map((h, i) => (
                <div key={i} className="text-[9px] text-zinc-600 text-center border-l border-zinc-800/20 py-1.5" style={{ width: cfg.unitWidth }}>{formatHeader(h)}</div>
              ))}
            </div>
          </div>

          {/* Full timeline rollup bar */}
          {fullTimelineBar && (
            <div className="flex items-center border-b border-purple-500/20 h-7 bg-purple-500/5">
              <div className="flex-shrink-0 px-3 flex items-center gap-2" style={{ width: NAME_COL }}>
                <FolderKanban className="w-3 h-3 text-purple-400" />
                <span className="text-[10px] font-bold text-purple-400">Full Timeline</span>
                <span className="text-[9px] text-zinc-500">{totalProgress}% complete</span>
              </div>
              <div className="flex-1 relative h-full">
                {headers.map((_, i) => <div key={i} className="absolute top-0 bottom-0 border-l border-zinc-800/10" style={{ left: i * cfg.unitWidth }} />)}
                {todayOffset > 0 && todayOffset < totalWidth && <div className="absolute top-0 bottom-0 w-px bg-emerald-500/50" style={{ left: todayOffset }} />}
                <div className="absolute top-1/2 -translate-y-1/2 h-3 rounded-full bg-purple-500/30 border border-purple-500/40"
                  style={{ left: Math.max(0, fullTimelineBar.left), width: fullTimelineBar.width }}>
                  <div className="h-full rounded-full bg-purple-500/50" style={{ width: `${totalProgress}%` }} />
                </div>
              </div>
            </div>
          )}

          {/* Projects */}
          {visibleProjects.map(proj => {
            const tasks = tasksByProject[proj.project_id] || [];
            const isExpanded = expandedProjects[proj.project_id];
            const projBar = getProjectBar(tasks);

            return (
              <div key={proj.project_id}>
                {/* Project header with rollup bar */}
                <div className="flex items-center border-b border-zinc-800/30 h-8 bg-zinc-900/50 cursor-pointer hover:bg-zinc-800/30"
                  onClick={() => toggleProject(proj.project_id)} data-testid={`portfolio-project-${proj.project_id}`}>
                  <div className="flex-shrink-0 px-3 flex items-center gap-2 min-w-0" style={{ width: NAME_COL }}>
                    <ChevronDown className={`w-3 h-3 text-zinc-500 transition-transform flex-shrink-0 ${isExpanded ? "" : "-rotate-90"}`} />
                    <div className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ backgroundColor: proj.status === "active" ? "#8b5cf6" : "#22c55e" }} />
                    <span className="text-[11px] font-semibold text-zinc-300 truncate">{proj.name}</span>
                    <span className="text-[9px] text-zinc-600 flex-shrink-0">{proj.tasks_done}/{proj.task_count}</span>
                    <div className="w-10 h-1 rounded-full bg-zinc-800 overflow-hidden flex-shrink-0">
                      <div className="h-full bg-emerald-500/60" style={{ width: `${proj.progress}%` }} />
                    </div>
                  </div>
                  <div className="flex-1 relative h-full">
                    {headers.map((_, i) => <div key={i} className="absolute top-0 bottom-0 border-l border-zinc-800/10" style={{ left: i * cfg.unitWidth }} />)}
                    {todayOffset > 0 && todayOffset < totalWidth && <div className="absolute top-0 bottom-0 w-px bg-emerald-500/50" style={{ left: todayOffset }} />}
                    {/* Project rollup bar (visible when collapsed) */}
                    {!isExpanded && projBar && (
                      <div className="absolute top-1/2 -translate-y-1/2 h-3 rounded-sm bg-purple-500/20 border border-purple-500/30"
                        style={{ left: Math.max(0, projBar.left), width: projBar.width }}>
                        <div className="h-full rounded-sm bg-purple-500/40" style={{ width: `${proj.progress}%` }} />
                        <span className="absolute inset-0 flex items-center justify-center text-[7px] text-purple-300/80 font-medium">{proj.task_count} tasks</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Expanded tasks */}
                {isExpanded && tasks.map(task => {
                  const pos = getBarPos(task);
                  const color = STATUS_COLORS[task.status] || "#555";
                  const progress = task.status === "done" ? 100 : task.status === "in_progress" ? 50 : task.status === "review" ? 75 : 0;
                  return (
                    <div key={task.task_id} className="flex items-center border-b border-zinc-800/10 h-7 hover:bg-zinc-800/20">
                      <div className="flex-shrink-0 px-3 pl-9 flex items-center gap-1.5 min-w-0" style={{ width: NAME_COL }}>
                        <span className={`text-[10px] truncate ${task.status === "done" ? "text-zinc-600 line-through" : "text-zinc-400"}`}>{task.title}</span>
                      </div>
                      <div className="flex-1 relative h-full">
                        {headers.map((_, i) => <div key={i} className="absolute top-0 bottom-0 border-l border-zinc-800/10" style={{ left: i * cfg.unitWidth }} />)}
                        {todayOffset > 0 && todayOffset < totalWidth && <div className="absolute top-0 bottom-0 w-px bg-emerald-500/50" style={{ left: todayOffset }} />}
                        <div className="absolute top-1/2 -translate-y-1/2 h-4 rounded-sm" style={{ left: Math.max(0, pos.left), width: pos.width, backgroundColor: color, opacity: task.status === "done" ? 0.4 : 0.8 }}>
                          <div className="h-full rounded-sm bg-white/20" style={{ width: `${progress}%` }} />
                          {pos.width > 80 && <span className="absolute inset-0 flex items-center px-1.5 text-[8px] text-white font-medium truncate pointer-events-none">{task.title}</span>}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </ScrollArea>

      {/* Legend */}
      <div className="flex items-center gap-4 px-4 py-1.5 border-t border-zinc-800/40 flex-shrink-0 bg-zinc-900/30">
        {Object.entries(STATUS_COLORS).map(([s, c]) => (
          <div key={s} className="flex items-center gap-1"><div className="w-3 h-1.5 rounded-sm" style={{ backgroundColor: c }} /><span className="text-[9px] text-zinc-500 capitalize">{s.replace("_", " ")}</span></div>
        ))}
        <div className="flex items-center gap-1"><div className="w-3 h-1.5 rounded-sm bg-purple-500/40 border border-purple-500/30" /><span className="text-[9px] text-zinc-500">Project rollup</span></div>
        <div className="flex items-center gap-1"><div className="w-px h-3 bg-emerald-500" /><span className="text-[9px] text-zinc-500">Today</span></div>
      </div>
    </div>
  );
}
