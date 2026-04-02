import { useState, useEffect, useCallback } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { BarChart3, Users, CheckCircle2, Clock, AlertTriangle, Activity, Loader2, RefreshCw, Brain, ListTodo } from "lucide-react";
import { SkeletonDashboardStats, SkeletonProjectCard } from "@/components/Skeletons";
import { api } from "@/App";
import { toast } from "sonner";

const STATUS_COLORS = {
  active: "bg-emerald-500", planning: "bg-blue-500", in_progress: "bg-cyan-500",
  completed: "bg-zinc-600", paused: "bg-amber-500", blocked: "bg-red-500",
  pending: "bg-zinc-500", todo: "bg-zinc-500", done: "bg-emerald-500",
};

export default function ProjectsDashboard({ workspaceId }) {
  const [projects, setProjects] = useState([]);
  const [coordination, setCoordination] = useState(null);
  const [selectedProject, setSelectedProject] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tasksLoading, setTasksLoading] = useState(false);

  const load = useCallback(async () => {
    try {
      const [projRes, coordRes] = await Promise.all([
        api.get(`/workspaces/${workspaceId}/projects`),
        api.get(`/workspaces/${workspaceId}/coordination-status`),
      ]);
      setProjects(projRes.data || []);
      setCoordination(coordRes.data);
    } catch (err) { handleError(err, "ProjectsDashboard:op1"); }
    finally { setLoading(false); }
  }, [workspaceId]);

  useEffect(() => { load(); }, [load]);

  const loadTasks = async (projectId) => {
    setTasksLoading(true);
    try {
      const res = await api.get(`/projects/${projectId}/tasks`);
      setTasks(res.data || []);
    } catch (err) { handleSilent(err, "ProjectsDashboard:op2"); setTasks([]); }
    setTasksLoading(false);
  };

  const selectProject = (proj) => {
    setSelectedProject(proj);
    loadTasks(proj.project_id);
  };

  // Workspace-level stats
  const totalProjects = projects.length;
  const activeProjects = projects.filter(p => p.status === "active" || p.status === "in_progress").length;
  const completedProjects = projects.filter(p => p.status === "completed" || p.status === "done").length;
  const pendingAssignments = coordination?.pending_assignments?.length || 0;
  const agentStates = coordination?.agent_states || {};

  if (loading) return (
    <div className="flex-1 flex flex-col min-h-0 p-6 space-y-4" data-testid="projects-dashboard-skeleton">
      <SkeletonDashboardStats />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {Array.from({ length: 6 }).map((_, i) => <SkeletonProjectCard key={i} />)}
      </div>
    </div>
  );

  return (
    <div className="flex-1 flex flex-col min-h-0" data-testid="projects-dashboard">
      {/* Workspace Rollup Stats */}
      <div className="px-6 py-4 border-b border-zinc-800/40">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-zinc-100 flex items-center gap-2" style={{ fontFamily: "Syne, sans-serif" }}>
            <BarChart3 className="w-5 h-5 text-cyan-400" /> Projects Dashboard
          </h2>
          <Button size="sm" variant="ghost" onClick={load} className="text-zinc-400 h-7"><RefreshCw className="w-3.5 h-3.5" /></Button>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3 rounded-lg bg-zinc-900/80 border border-zinc-800/40">
            <div className="text-2xl font-bold text-zinc-100">{totalProjects}</div>
            <div className="text-[10px] text-zinc-500 flex items-center gap-1"><ListTodo className="w-3 h-3" /> Total Projects</div>
          </div>
          <div className="p-3 rounded-lg bg-zinc-900/80 border border-emerald-500/20">
            <div className="text-2xl font-bold text-emerald-400">{activeProjects}</div>
            <div className="text-[10px] text-zinc-500 flex items-center gap-1"><Activity className="w-3 h-3 text-emerald-500" /> Active</div>
          </div>
          <div className="p-3 rounded-lg bg-zinc-900/80 border border-zinc-700/30">
            <div className="text-2xl font-bold text-zinc-400">{completedProjects}</div>
            <div className="text-[10px] text-zinc-500 flex items-center gap-1"><CheckCircle2 className="w-3 h-3" /> Completed</div>
          </div>
          <div className="p-3 rounded-lg bg-zinc-900/80 border border-amber-500/20">
            <div className="text-2xl font-bold text-amber-400">{pendingAssignments}</div>
            <div className="text-[10px] text-zinc-500 flex items-center gap-1"><Clock className="w-3 h-3 text-amber-500" /> Pending Tasks</div>
          </div>
        </div>
      </div>

      <div className="flex-1 flex min-h-0">
        {/* Left: Agent States + Project List */}
        <div className="w-96 border-r border-zinc-800/60 flex flex-col">
          {/* Agent Coordination Status */}
          {Object.keys(agentStates).length > 0 && (
            <div className="p-3 border-b border-zinc-800/40">
              <p className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-2 flex items-center gap-1"><Brain className="w-3 h-3" /> Agent States</p>
              <div className="space-y-1">
                {Object.entries(agentStates).map(([key, state]) => (
                  <div key={key} className="p-1.5 rounded bg-zinc-900/50 text-[10px]">
                    <span className="text-cyan-400 font-medium">{key.replace("state:", "")}</span>
                    <p className="text-zinc-500 truncate mt-0.5">{typeof state.value === "string" ? state.value.substring(0, 80) : ""}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Work Queue */}
          {coordination?.in_progress?.length > 0 && (
            <div className="p-3 border-b border-zinc-800/40">
              <p className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-2">In Progress</p>
              {coordination.in_progress.map(item => (
                <div key={item.item_id} className="p-1.5 rounded bg-blue-500/5 border border-blue-500/10 text-[10px] mb-1">
                  <span className="text-zinc-300">{item.title}</span>
                  <span className="text-zinc-600 ml-1">({item.assigned_to})</span>
                </div>
              ))}
            </div>
          )}

          {/* Project List */}
          <ScrollArea className="flex-1">
            <div className="p-3">
              <p className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-2">All Projects</p>
              {projects.length === 0 ? (
                <p className="text-xs text-zinc-600 text-center py-4">No projects yet</p>
              ) : (
                <div className="space-y-1">
                  {projects.map(proj => (
                    <button key={proj.project_id} onClick={() => selectProject(proj)}
                      className={`w-full text-left p-2.5 rounded-lg border transition-all ${
                        selectedProject?.project_id === proj.project_id
                          ? "border-cyan-500/40 bg-cyan-500/5"
                          : "border-zinc-800/40 hover:border-zinc-700 bg-zinc-900/20"
                      }`} data-testid={`proj-${proj.project_id}`}>
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium text-zinc-300 truncate">{proj.name}</span>
                        <Badge className={`text-[8px] ${STATUS_COLORS[proj.status] || "bg-zinc-600"} text-white`}>{proj.status}</Badge>
                      </div>
                      {proj.tasks && <div className="text-[10px] text-zinc-600 mt-0.5">{proj.tasks.done}/{proj.tasks.total} tasks done</div>}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </ScrollArea>
        </div>

        {/* Right: Project Detail */}
        <div className="flex-1 overflow-hidden">
          {!selectedProject ? (
            <div className="flex-1 flex items-center justify-center h-full text-center p-8">
              <div>
                <BarChart3 className="w-12 h-12 text-zinc-800 mx-auto mb-3" />
                <p className="text-sm text-zinc-400 mb-1">Select a project to view details</p>
                <p className="text-xs text-zinc-600">View tasks, assignees, and progress</p>
              </div>
            </div>
          ) : (
            <ScrollArea className="h-full">
              <div className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="text-lg font-semibold text-zinc-100">{selectedProject.name}</h3>
                    <p className="text-xs text-zinc-500">{selectedProject.status}{selectedProject.created_at ? ` | Created ${new Date(selectedProject.created_at).toLocaleDateString()}` : ""}</p>
                  </div>
                  <Badge className={`text-xs ${STATUS_COLORS[selectedProject.status] || "bg-zinc-600"} text-white`}>{selectedProject.status}</Badge>
                </div>

                {selectedProject.description && (
                  <p className="text-sm text-zinc-400 mb-4">{selectedProject.description}</p>
                )}

                {/* Task Summary Stats */}
                <div className="grid grid-cols-3 gap-3 mb-4">
                  <div className="p-2 rounded-lg bg-zinc-900/50 border border-zinc-800/40 text-center">
                    <div className="text-lg font-bold text-zinc-100">{tasks.length}</div>
                    <div className="text-[9px] text-zinc-500">Total Tasks</div>
                  </div>
                  <div className="p-2 rounded-lg bg-zinc-900/50 border border-zinc-800/40 text-center">
                    <div className="text-lg font-bold text-emerald-400">{tasks.filter(t => t.status === "done" || t.status === "completed").length}</div>
                    <div className="text-[9px] text-zinc-500">Done</div>
                  </div>
                  <div className="p-2 rounded-lg bg-zinc-900/50 border border-zinc-800/40 text-center">
                    <div className="text-lg font-bold text-amber-400">{tasks.filter(t => t.status === "in_progress").length}</div>
                    <div className="text-[9px] text-zinc-500">In Progress</div>
                  </div>
                </div>

                {/* Progress Bar */}
                {tasks.length > 0 && (
                  <div className="mb-4">
                    <div className="flex items-center justify-between text-[10px] text-zinc-500 mb-1">
                      <span>Progress</span>
                      <span>{Math.round((tasks.filter(t => t.status === "done" || t.status === "completed").length / tasks.length) * 100)}%</span>
                    </div>
                    <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
                      <div className="h-full bg-cyan-500 rounded-full transition-all" style={{ width: `${(tasks.filter(t => t.status === "done" || t.status === "completed").length / tasks.length) * 100}%` }} />
                    </div>
                  </div>
                )}

                {/* Tasks List */}
                <h4 className="text-sm font-semibold text-zinc-300 mb-2">Tasks</h4>
                {tasksLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin text-zinc-500 mx-auto" />
                ) : tasks.length === 0 ? (
                  <p className="text-xs text-zinc-600 text-center py-4">No tasks in this project</p>
                ) : (
                  <div className="space-y-1.5">
                    {tasks.map(task => (
                      <div key={task.task_id} className="p-2.5 rounded-lg border border-zinc-800/30 bg-zinc-900/30" data-testid={`task-${task.task_id}`}>
                        <div className="flex items-center justify-between mb-0.5">
                          <span className="text-xs text-zinc-300">{task.title}</span>
                          <div className="flex items-center gap-1.5">
                            {task.assigned_to && <span className="text-[9px] text-cyan-400">{task.assigned_to}</span>}
                            <Badge className={`text-[8px] ${STATUS_COLORS[task.status] || "bg-zinc-600"} text-white`}>{task.status}</Badge>
                          </div>
                        </div>
                        {task.priority && (
                          <span className={`text-[9px] ${task.priority === "critical" || task.priority === "high" ? "text-red-400" : "text-zinc-600"}`}>{task.priority}</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </ScrollArea>
          )}
        </div>
      </div>
    </div>
  );
}
