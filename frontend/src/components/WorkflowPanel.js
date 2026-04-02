import { useState, useEffect, useCallback } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { api } from "@/App";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Plus, Play, Pause, Trash2, Clock, Zap, ChevronRight, LayoutGrid, FileText, ArrowRight, Search, Filter } from "lucide-react";
import WorkflowCanvas from "./WorkflowCanvas";

const STATUS_COLORS = {
  draft: "bg-zinc-600",
  active: "bg-emerald-600",
  paused: "bg-amber-600",
  archived: "bg-zinc-700",
};

export default function WorkflowPanel({ workspaceId }) {
  const [workflows, setWorkflows] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [sortBy, setSortBy] = useState("newest");
  const [showCreate, setShowCreate] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [selectedWorkflow, setSelectedWorkflow] = useState(null);
  const [creating, setCreating] = useState(false);

  const fetchWorkflows = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/workflows`);
      setWorkflows(res.data);
    } catch (err) {
      console.error("Failed to fetch workflows:", err);
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  const fetchTemplates = useCallback(async () => {
    try {
      const res = await api.get("/templates");
      setTemplates(res.data);
    } catch (err) {
      console.error("Failed to fetch templates:", err);
    }
  }, []);

  useEffect(() => {
    fetchWorkflows();
    fetchTemplates();
  }, [fetchWorkflows, fetchTemplates]);

  const createWorkflow = async (templateId) => {
    if (!newName.trim() && !templateId) return;
    setCreating(true);
    try {
      const body = templateId
        ? { name: newName.trim() || "Untitled Workflow", description: newDesc, template_id: templateId }
        : { name: newName.trim(), description: newDesc };
      const res = await api.post(`/workspaces/${workspaceId}/workflows`, body);
      setWorkflows((prev) => [res.data, ...prev]);
      setShowCreate(false);
      setShowTemplates(false);
      setNewName("");
      setNewDesc("");
      toast.success("Workflow created");
      setSelectedWorkflow(res.data);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to create workflow");
    } finally {
      setCreating(false);
    }
  };

  const deleteWorkflow = async (wfId) => {
    try {
      await api.delete(`/workflows/${wfId}`);
      setWorkflows((prev) => prev.filter((w) => w.workflow_id !== wfId));
      if (selectedWorkflow?.workflow_id === wfId) setSelectedWorkflow(null);
      toast.success("Workflow deleted");
    } catch (err) {
      toast.error("Failed to delete workflow");
    }
  };

  const updateStatus = async (wfId, status) => {
    try {
      await api.put(`/workflows/${wfId}`, { status });
      setWorkflows((prev) =>
        prev.map((w) => (w.workflow_id === wfId ? { ...w, status } : w))
      );
      if (selectedWorkflow?.workflow_id === wfId) {
        setSelectedWorkflow((prev) => ({ ...prev, status }));
      }
      toast.success(`Workflow ${status}`);
    } catch (err) {
      toast.error("Failed to update status");
    }
  };

  // If a workflow is selected, show the canvas editor
  if (selectedWorkflow) {
    return (
      <WorkflowCanvas
        workflow={selectedWorkflow}
        workspaceId={workspaceId}
        onBack={() => {
          setSelectedWorkflow(null);
          fetchWorkflows();
        }}
        onStatusChange={(status) => updateStatus(selectedWorkflow.workflow_id, status)}
      />
    );
  }

  const CATEGORY_ICONS = { research: "magnifying-glass", content: "edit-3", development: "code", business: "bar-chart-2" };

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-zinc-100" data-testid="workflows-heading">Workflows</h2>
            <p className="text-sm text-zinc-500 mt-1">Build and run multi-agent automation pipelines</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => setShowTemplates(true)} className="border-zinc-700 text-zinc-300 hover:bg-zinc-800" data-testid="browse-templates-btn">
              <LayoutGrid className="w-4 h-4 mr-2" />
              Templates
            </Button>
            <Button size="sm" onClick={() => setShowCreate(true)} className="bg-zinc-100 text-zinc-900 hover:bg-zinc-200" data-testid="create-workflow-btn">
              <Plus className="w-4 h-4 mr-2" />
              New Workflow
            </Button>
          </div>
        </div>

        {/* Info banner */}
        <div className="p-3 rounded-lg bg-blue-500/5 border border-blue-500/15 flex items-start gap-3 mb-4">
          <Zap className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-zinc-400 leading-relaxed">Workflows let you chain multiple AI agents into automated pipelines. Design visually, add conditions and checkpoints, then run with one click.</p>
        </div>

        {/* Search/Filter/Sort (#17) */}
        {workflows.length > 0 && (
          <div className="flex items-center gap-3 flex-wrap">
            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-600" />
              <input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="Search workflows..." className="w-full bg-zinc-900/60 border border-zinc-800/60 rounded-lg pl-9 pr-3 py-2 text-sm text-zinc-300 placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-700" data-testid="workflow-search" />
            </div>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="bg-zinc-900/60 border border-zinc-800/60 rounded-lg px-3 py-2 text-xs text-zinc-400" data-testid="workflow-status-filter">
              <option value="">All Status</option>
              <option value="draft">Draft</option>
              <option value="active">Active</option>
              <option value="paused">Paused</option>
            </select>
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} className="bg-zinc-900/60 border border-zinc-800/60 rounded-lg px-3 py-2 text-xs text-zinc-400" data-testid="workflow-sort">
              <option value="newest">Newest</option>
              <option value="name">Name</option>
              <option value="status">Status</option>
            </select>
          </div>
        )}

        {/* Workflows Grid */}
        {loading ? (
          <div className="flex items-center justify-center py-20 text-zinc-500">Loading workflows...</div>
        ) : workflows.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-zinc-500 space-y-4 max-w-md mx-auto" data-testid="empty-workflows">
            <div className="w-16 h-16 rounded-2xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center mb-2">
              <Zap className="w-7 h-7 text-blue-400" />
            </div>
            <p className="text-lg font-semibold text-zinc-300">Build your first workflow</p>
            <p className="text-sm text-center leading-relaxed text-zinc-500">Design multi-step AI workflows with a visual canvas. Chain agents together, add conditions, and automate complex tasks.</p>
            <div className="flex gap-3 mt-2">
              <Button variant="outline" size="sm" onClick={() => setShowTemplates(true)} className="border-zinc-700 text-zinc-300 hover:bg-zinc-800">
                Browse Templates
              </Button>
              <Button size="sm" onClick={() => setShowCreate(true)} className="bg-emerald-500 hover:bg-emerald-400 text-white">
                Create Blank
              </Button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="workflows-grid">
            {workflows
              .filter(wf => {
                if (searchQuery && !wf.name.toLowerCase().includes(searchQuery.toLowerCase()) && !(wf.description || "").toLowerCase().includes(searchQuery.toLowerCase())) return false;
                if (statusFilter && wf.status !== statusFilter) return false;
                return true;
              })
              .sort((a, b) => {
                if (sortBy === "name") return a.name.localeCompare(b.name);
                if (sortBy === "status") return (a.status || "").localeCompare(b.status || "");
                return (b.created_at || "").localeCompare(a.created_at || "");
              })
              .map((wf) => (
              <div
                key={wf.workflow_id}
                className="bg-zinc-900/60 border border-zinc-800/60 rounded-lg p-4 hover:border-zinc-700 transition-colors cursor-pointer group"
                onClick={() => setSelectedWorkflow(wf)}
                data-testid={`workflow-card-${wf.workflow_id}`}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Zap className="w-4 h-4 text-zinc-400" />
                    <span className={`text-[10px] font-medium uppercase px-1.5 py-0.5 rounded ${STATUS_COLORS[wf.status] || "bg-zinc-700"} text-white`}>
                      {wf.status}
                    </span>
                  </div>
                  <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    {wf.status === "draft" && (
                      <Button variant="ghost" size="icon" className="h-7 w-7 text-emerald-400 hover:bg-zinc-800" onClick={(e) => { e.stopPropagation(); updateStatus(wf.workflow_id, "active"); }} data-testid={`activate-workflow-${wf.workflow_id}`}>
                        <Play className="w-3 h-3" />
                      </Button>
                    )}
                    {wf.status === "active" && (
                      <Button variant="ghost" size="icon" className="h-7 w-7 text-amber-400 hover:bg-zinc-800" onClick={(e) => { e.stopPropagation(); updateStatus(wf.workflow_id, "paused"); }}>
                        <Pause className="w-3 h-3" />
                      </Button>
                    )}
                    <Button variant="ghost" size="icon" className="h-7 w-7 text-red-400 hover:bg-zinc-800" onClick={(e) => { e.stopPropagation(); deleteWorkflow(wf.workflow_id); }} data-testid={`delete-workflow-${wf.workflow_id}`}>
                      <Trash2 className="w-3 h-3" />
                    </Button>
                  </div>
                </div>
                <h3 className="font-medium text-zinc-200 mb-1 truncate">{wf.name}</h3>
                <p className="text-xs text-zinc-500 mb-3 line-clamp-2">{wf.description || "No description"}</p>
                <div className="flex items-center justify-between text-xs text-zinc-600">
                  <div className="flex items-center gap-3">
                    <span>{wf.node_count || 0} nodes</span>
                    <span>{wf.run_count || 0} runs</span>
                  </div>
                  <ChevronRight className="w-3 h-3 text-zinc-600 group-hover:text-zinc-400 transition-colors" />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Create Workflow Dialog */}
        <Dialog open={showCreate} onOpenChange={setShowCreate}>
          <DialogContent className="bg-zinc-900 border-zinc-800 max-w-md">
            <DialogHeader>
              <DialogTitle className="text-zinc-100">New Workflow</DialogTitle>
              <DialogDescription className="text-zinc-500 text-sm">Create a blank workflow to build your automation pipeline.</DialogDescription>
            </DialogHeader>
            <div className="space-y-3 mt-2">
              <Input placeholder="Workflow name" value={newName} onChange={(e) => setNewName(e.target.value)} className="bg-zinc-800 border-zinc-700 text-zinc-200" data-testid="workflow-name-input" />
              <Input placeholder="Description (optional)" value={newDesc} onChange={(e) => setNewDesc(e.target.value)} className="bg-zinc-800 border-zinc-700 text-zinc-200" data-testid="workflow-desc-input" />
              <Button onClick={() => createWorkflow(null)} disabled={!newName.trim() || creating} className="w-full bg-zinc-100 text-zinc-900 hover:bg-zinc-200" data-testid="workflow-submit-btn">
                {creating ? "Creating..." : "Create Workflow"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>

        {/* Templates Dialog */}
        <Dialog open={showTemplates} onOpenChange={setShowTemplates}>
          <DialogContent className="bg-zinc-900 border-zinc-800 max-w-2xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="text-zinc-100">Workflow Templates</DialogTitle>
              <DialogDescription className="text-zinc-500 text-sm">Start with a pre-built template and customize it to your needs.</DialogDescription>
            </DialogHeader>
            <div className="space-y-3 mt-2">
              {templates.map((tpl) => (
                <div key={tpl.template_id} className="bg-zinc-800/50 border border-zinc-700/50 rounded-lg p-4 hover:border-zinc-600 transition-colors" data-testid={`template-card-${tpl.template_id}`}>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-medium text-zinc-200">{tpl.name}</h3>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-700 text-zinc-400 uppercase">{tpl.category}</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-700 text-zinc-400">{tpl.difficulty}</span>
                      </div>
                      <p className="text-xs text-zinc-500 mb-2">{tpl.description}</p>
                      <div className="flex items-center gap-3 text-xs text-zinc-600">
                        <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{tpl.estimated_time}</span>
                        <span>{tpl.nodes?.length || 0} nodes</span>
                      </div>
                    </div>
                    <Button size="sm" variant="outline" className="border-zinc-600 text-zinc-300 hover:bg-zinc-700 ml-4 shrink-0"
                      onClick={() => { setNewName(tpl.name); createWorkflow(tpl.template_id); }}
                      data-testid={`use-template-${tpl.template_id}`}
                    >
                      <ArrowRight className="w-3 h-3 mr-1" />
                      Use
                    </Button>
                  </div>
                </div>
              ))}
              {templates.length === 0 && (
                <p className="text-zinc-500 text-center py-8">No templates available</p>
              )}
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
