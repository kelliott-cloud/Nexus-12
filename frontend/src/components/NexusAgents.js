import { useState, useEffect } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { useConfirm } from "@/components/ConfirmDialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Bot, Plus, Pencil, Trash2, Loader2, Sparkles, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/App";

const AGENT_COLORS = [
  "#E11D48", "#DB2777", "#C026D3", "#9333EA", "#7C3AED",
  "#6366F1", "#3B82F6", "#0EA5E9", "#06B6D4", "#14B8A6",
  "#10B981", "#22C55E", "#84CC16", "#EAB308", "#F59E0B",
  "#F97316", "#EF4444", "#78716C", "#64748B", "#6B7280",
];

const DEFAULT_PROMPTS = {
  "code-reviewer": "You are an expert code reviewer. Analyze code for bugs, security issues, performance problems, and best practices. Provide constructive feedback with specific suggestions for improvement.",
  "tech-writer": "You are a technical writer specializing in clear, concise documentation. Help create README files, API documentation, and user guides. Focus on clarity and completeness.",
  "architect": "You are a software architect. Help design system architecture, evaluate trade-offs, and suggest scalable solutions. Consider maintainability, performance, and security.",
  "debugger": "You are a debugging expert. Help identify and fix bugs by analyzing error messages, logs, and code. Explain the root cause and provide tested solutions.",
  "custom": "",
};

export default function NexusAgents({ workspaceId }) {
  const { confirm: confirmAction, ConfirmDialog: ConfirmDlg } = useConfirm();
  const [agents, setAgents] = useState([]);
  const [availableModels, setAvailableModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingAgent, setEditingAgent] = useState(null);
  const [saving, setSaving] = useState(false);
  const [limit, setLimit] = useState(3);
  const [plan, setPlan] = useState("free");

  // Form state
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [baseModel, setBaseModel] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [color, setColor] = useState(AGENT_COLORS[0]);
  const [promptTemplate, setPromptTemplate] = useState("custom");

  useEffect(() => {
    fetchData();
  }, [workspaceId]);

  const fetchData = async () => {
    try {
      const [agentsRes, modelsRes] = await Promise.all([
        api.get(`/workspaces/${workspaceId}/agents`),
        api.get(`/workspaces/${workspaceId}/available-models`),
      ]);
      setAgents(agentsRes.data.agents);
      setLimit(agentsRes.data.limit);
      setPlan(agentsRes.data.plan);
      setAvailableModels(modelsRes.data.models);
    } catch (err) {
      toast.error("Failed to load agents");
    }
    setLoading(false);
  };

  const resetForm = () => {
    setName("");
    setDescription("");
    setBaseModel("");
    setSystemPrompt("");
    setColor(AGENT_COLORS[agents.length % AGENT_COLORS.length]);
    setPromptTemplate("custom");
    setEditingAgent(null);
  };

  const openCreateDialog = () => {
    resetForm();
    setDialogOpen(true);
  };

  const openEditDialog = (agent) => {
    setEditingAgent(agent);
    setName(agent.name);
    setDescription(agent.description || "");
    setBaseModel(agent.base_model);
    setSystemPrompt(agent.system_prompt);
    setColor(agent.color);
    setPromptTemplate("custom");
    setDialogOpen(true);
  };

  const handlePromptTemplate = (template) => {
    setPromptTemplate(template);
    if (template !== "custom") {
      setSystemPrompt(DEFAULT_PROMPTS[template]);
    }
  };

  const handleSave = async () => {
    if (!name.trim() || !baseModel || !systemPrompt.trim()) {
      toast.error("Please fill in all required fields");
      return;
    }

    setSaving(true);
    try {
      if (editingAgent) {
        await api.put(`/workspaces/${workspaceId}/agents/${editingAgent.agent_id}`, {
          name,
          description,
          base_model: baseModel,
          system_prompt: systemPrompt,
          color,
        });
        toast.success("Agent updated");
      } else {
        await api.post(`/workspaces/${workspaceId}/agents`, {
          name,
          description,
          base_model: baseModel,
          system_prompt: systemPrompt,
          color,
        });
        toast.success("Agent created");
      }
      setDialogOpen(false);
      resetForm();
      fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to save agent");
    }
    setSaving(false);
  };

  const handleDelete = async (agentId) => {
    const _ok = await confirmAction("Delete Agent", "Delete this custom agent permanently?"); if (!_ok) return;
    try {
      await api.delete(`/workspaces/${workspaceId}/agents/${agentId}`);
      toast.success("Agent deleted");
      fetchData();
    } catch (err) {
      toast.error("Failed to delete agent");
    }
  };

  const getModelInfo = (modelKey) => {
    return availableModels.find(m => m.key === modelKey);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-zinc-500" />
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="nexus-agents">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-zinc-200 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-amber-400" />
            Nexus Agents
          </h3>
          <p className="text-xs text-zinc-500 mt-1">
            {agents.length}/{limit} custom agents ({plan} plan)
          </p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={(open) => { setDialogOpen(open); if (!open) resetForm(); }}>
          <DialogTrigger asChild>
            <Button
              size="sm"
              onClick={openCreateDialog}
              disabled={agents.length >= limit}
              className="bg-zinc-100 text-zinc-900 hover:bg-zinc-200 text-xs"
              data-testid="create-agent-btn"
            >
              <Plus className="w-3.5 h-3.5 mr-1" />
              New Agent
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-zinc-900 border-zinc-800 max-w-lg max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="text-zinc-100 flex items-center gap-2" style={{ fontFamily: 'Syne, sans-serif' }}>
                <Bot className="w-5 h-5" />
                {editingAgent ? "Edit Nexus Agent" : "Create Nexus Agent"}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-4">
              {/* Name */}
              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Agent Name *</label>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g., Code Reviewer"
                  className="bg-zinc-950 border-zinc-800"
                  maxLength={50}
                  data-testid="agent-name-input"
                />
              </div>

              {/* Description */}
              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Description</label>
                <Input
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Brief description of what this agent does"
                  className="bg-zinc-950 border-zinc-800"
                  maxLength={200}
                  data-testid="agent-desc-input"
                />
              </div>

              {/* Base Model */}
              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Powered By *</label>
                <Select value={baseModel} onValueChange={setBaseModel}>
                  <SelectTrigger className="bg-zinc-950 border-zinc-800" data-testid="agent-model-select">
                    <SelectValue placeholder="Select AI model" />
                  </SelectTrigger>
                  <SelectContent className="bg-zinc-900 border-zinc-800">
                    {availableModels.map((model) => (
                      <SelectItem key={model.key} value={model.key} className="text-sm">
                        <div className="flex items-center gap-2">
                          <div className="w-3 h-3 rounded-full" style={{ backgroundColor: model.color }} />
                          <span>{model.name}</span>
                          {model.requires_user_key && (
                            <span className="text-[10px] text-amber-400">(requires key)</span>
                          )}
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {baseModel && getModelInfo(baseModel)?.requires_user_key && (
                  <p className="text-[10px] text-amber-400 mt-1 flex items-center gap-1">
                    <AlertCircle className="w-3 h-3" />
                    This model requires your API key in Settings
                  </p>
                )}
              </div>

              {/* Color */}
              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Avatar Color</label>
                <div className="flex flex-wrap gap-1.5">
                  {AGENT_COLORS.map((c) => (
                    <button
                      key={c}
                      type="button"
                      onClick={() => setColor(c)}
                      className={`w-6 h-6 rounded-full transition-all ${color === c ? 'ring-2 ring-white ring-offset-2 ring-offset-zinc-900' : 'hover:scale-110'}`}
                      style={{ backgroundColor: c }}
                    />
                  ))}
                </div>
              </div>

              {/* Prompt Template */}
              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Start from template</label>
                <Select value={promptTemplate} onValueChange={handlePromptTemplate}>
                  <SelectTrigger className="bg-zinc-950 border-zinc-800">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-zinc-900 border-zinc-800">
                    <SelectItem value="custom">Custom prompt</SelectItem>
                    <SelectItem value="code-reviewer">Code Reviewer</SelectItem>
                    <SelectItem value="tech-writer">Tech Writer</SelectItem>
                    <SelectItem value="architect">Software Architect</SelectItem>
                    <SelectItem value="debugger">Debugger</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* System Prompt */}
              <div>
                <label className="text-xs text-zinc-400 mb-1 block">System Prompt * <span className="text-zinc-600">({systemPrompt.length}/2000)</span></label>
                <Textarea
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  placeholder="Define the agent's personality, expertise, and behavior..."
                  className="bg-zinc-950 border-zinc-800 min-h-[120px] text-sm"
                  maxLength={2000}
                  data-testid="agent-prompt-input"
                />
              </div>

              {/* Preview */}
              {name && (
                <div className="p-3 rounded-lg bg-zinc-950 border border-zinc-800">
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-2">Preview</p>
                  <div className="flex items-center gap-2">
                    <div
                      className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold text-white"
                      style={{ backgroundColor: color }}
                    >
                      {name.slice(0, 2).toUpperCase()}
                    </div>
                    <div>
                      <span className="text-sm font-medium text-zinc-200">{name}</span>
                      {baseModel && (
                        <span className="text-[10px] text-zinc-500 ml-2">powered by {getModelInfo(baseModel)?.name}</span>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-2 pt-2">
                <Button
                  onClick={handleSave}
                  disabled={saving || !name.trim() || !baseModel || !systemPrompt.trim()}
                  className="flex-1 bg-zinc-100 text-zinc-900 hover:bg-zinc-200"
                  data-testid="save-agent-btn"
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : (editingAgent ? "Update Agent" : "Create Agent")}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Agents list */}
      {agents.length === 0 ? (
        <div className="text-center py-8 px-4 rounded-xl bg-zinc-900/30 border border-zinc-800/40">
          <Bot className="w-8 h-8 text-zinc-600 mx-auto mb-3" />
          <p className="text-sm text-zinc-400">No custom agents yet</p>
          <p className="text-xs text-zinc-600 mt-1">Create a Nexus Agent to add a custom AI collaborator</p>
        </div>
      ) : (
        <div className="space-y-2">
          {agents.map((agent) => {
            const modelInfo = getModelInfo(agent.base_model);
            return (
              <div
                key={agent.agent_id}
                className="p-3 rounded-lg bg-zinc-900/40 border border-zinc-800/60 hover:border-zinc-700 transition-colors group"
                data-testid={`agent-card-${agent.agent_id}`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div
                      className="w-9 h-9 rounded-lg flex items-center justify-center text-xs font-bold text-white"
                      style={{ backgroundColor: agent.color }}
                    >
                      {agent.avatar}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-zinc-200">{agent.name}</span>
                        <Badge className="bg-zinc-800 text-zinc-400 text-[9px] px-1.5">
                          {modelInfo?.name || agent.base_model}
                        </Badge>
                      </div>
                      {agent.description && (
                        <p className="text-xs text-zinc-500 mt-0.5 line-clamp-1">{agent.description}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={() => openEditDialog(agent)}
                      className="p-1.5 rounded text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
                      data-testid={`edit-agent-${agent.agent_id}`}
                    >
                      <Pencil className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => handleDelete(agent.agent_id)}
                      className="p-1.5 rounded text-zinc-500 hover:text-red-400 hover:bg-zinc-800"
                      data-testid={`delete-agent-${agent.agent_id}`}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Upgrade prompt */}
      {agents.length >= limit && (
        <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-center">
          <p className="text-xs text-amber-400">
            You've reached the {limit} agent limit for your {plan} plan.
            <button className="ml-1 underline hover:no-underline">Upgrade</button> to create more.
          </p>
        </div>
      )}
    <ConfirmDlg />
    </div>
    );
}
