import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { handleSilent } from "@/lib/errorHandler";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import {
  Plus, ChevronRight, ChevronLeft, Save, Wand2, Eye, Copy, Trash2,
  Shield, Brain, Code, BarChart3, Settings, Palette, Search, Zap,
  Check, X, ArrowUpDown, GitBranch, Star, RotateCcw, Play
} from "lucide-react";
import { AgentWizard } from "@/components/studio/AgentWizard";

const STEPS = ["basics", "skills", "tools", "personality", "guardrails", "review", "test", "training"];
const STEP_LABELS = { basics: "Basics", skills: "Skills", tools: "Tools", personality: "Personality", guardrails: "Guardrails", review: "Review", test: "Test", training: "Training" };
const CATEGORY_ICONS = { engineering: Code, product: Palette, data: BarChart3, operations: Settings };
const TONES = ["precise", "friendly", "formal", "creative", "terse"];
const VERBOSITY = ["brief", "balanced", "detailed"];
const RISK_TOLERANCE = ["conservative", "moderate", "aggressive"];
const COLLAB_STYLES = ["leader", "contributor", "reviewer", "specialist"];
const LEVELS = ["novice", "intermediate", "advanced", "expert", "master"];
const LEVEL_COLORS = { novice: "#6B7280", intermediate: "#3B82F6", advanced: "#8B5CF6", expert: "#F59E0B", master: "#EF4444" };

export default function AgentStudio({ workspaceId }) {
  const [agents, setAgents] = useState([]);
  const [skills, setSkills] = useState([]);
  const [categories, setCategories] = useState({});
  const [models, setModels] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [step, setStep] = useState(0);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewData, setPreviewData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [availableTools, setAvailableTools] = useState([]);

  // Wizard form state
  const [form, setForm] = useState({
    name: "", description: "", base_model: "claude", system_prompt: "",
    color: "#6366F1", category: "engineering", tags: [],
    skills: [], allowed_tools: [], denied_tools: [],
    personality: { tone: "balanced", verbosity: "balanced", risk_tolerance: "moderate", collaboration_style: "contributor" },
    guardrails: { max_response_length: 4000, require_citations: false, require_confidence: true, forbidden_topics: [], escalation_threshold: 0.4 },
    preferred_role: "contributor",
    visibility: "workspace",
  });
  const [tagInput, setTagInput] = useState("");
  const [forbiddenInput, setForbiddenInput] = useState("");
  const [skillSearch, setSkillSearch] = useState("");
  const [testPrompt, setTestPrompt] = useState("");
  const [testResponse, setTestResponse] = useState("");
  const [testLoading, setTestLoading] = useState(false);
  const [topicSuggestions, setTopicSuggestions] = useState([]);
  const [trainingTopics, setTrainingTopics] = useState([]);
  const [trainingUrls, setTrainingUrls] = useState("");
  const [trainingStatus, setTrainingStatus] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const [agentsRes, skillsRes, modelsRes, toolsRes] = await Promise.all([
        api.get(`/workspaces/${workspaceId}/agents`),
        api.get("/skills"),
        api.get("/ai-models"),
        api.get(`/workspaces/${workspaceId}/tools`).catch(() => ({ data: { tools: [] } })),
      ]);
      setAgents(agentsRes.data.agents || []);
      setSkills(skillsRes.data.skills || []);
      setCategories(skillsRes.data.categories || {});
      setModels(Object.keys(modelsRes.data || {}));
      setAvailableTools(toolsRes.data.tools || []);
    } catch (err) { handleSilent(err, "AgentStudio:fetch"); }
    setLoading(false);
  }, [workspaceId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const resetForm = () => {
    setForm({
      name: "", description: "", base_model: "claude", system_prompt: "",
      color: "#6366F1", category: "engineering", tags: [],
      skills: [], allowed_tools: [], denied_tools: [],
      personality: { tone: "balanced", verbosity: "balanced", risk_tolerance: "moderate", collaboration_style: "contributor" },
      guardrails: { max_response_length: 4000, require_citations: false, require_confidence: true, forbidden_topics: [], escalation_threshold: 0.4 },
      preferred_role: "contributor",
      visibility: "workspace",
    });
    setStep(0);
    setSelectedAgent(null);
    setTagInput("");
    setForbiddenInput("");
  };

  const openWizard = (agent = null) => {
    if (agent) {
      setSelectedAgent(agent);
      setForm({
        name: agent.name || "", description: agent.description || "",
        base_model: agent.base_model || "claude", system_prompt: agent.system_prompt || "",
        color: agent.color || "#6366F1", category: agent.category || "engineering",
        tags: agent.tags || [], skills: agent.skills || [],
        allowed_tools: agent.allowed_tools || [], denied_tools: agent.denied_tools || [],
        personality: agent.personality || { tone: "balanced", verbosity: "balanced", risk_tolerance: "moderate", collaboration_style: "contributor" },
        guardrails: agent.guardrails || { max_response_length: 4000, require_citations: false, require_confidence: true, forbidden_topics: [], escalation_threshold: 0.4 },
        preferred_role: agent.preferred_role || "contributor",
      });
    } else {
      resetForm();
    }
    setStep(0);
    setWizardOpen(true);
  };

  const handleSave = async () => {
    if (!form.name.trim()) { toast.error("Agent name is required"); return; }
    try {
      if (selectedAgent) {
        await api.put(`/workspaces/${workspaceId}/agents/${selectedAgent.agent_id}/studio`, form);
        toast.success("Agent updated");
      } else {
        await api.post(`/workspaces/${workspaceId}/agents/studio`, form);
        toast.success("Agent created");
      }
      setWizardOpen(false);
      resetForm();
      fetchData();
    } catch (err) { toast.error(err?.response?.data?.detail || "Save failed"); }
  };

  const handleClone = async (agentId) => {
    try {
      await api.post(`/workspaces/${workspaceId}/agents/${agentId}/clone`);
      toast.success("Agent cloned");
      fetchData();
    } catch (err) { toast.error("Clone failed"); }
  };

  const handleStatusChange = async (agentId, status) => {
    try {
      await api.patch(`/workspaces/${workspaceId}/agents/${agentId}/status`, { status });
      toast.success(`Agent ${status}`);
      fetchData();
    } catch (err) { toast.error("Status update failed"); }
  };

  const handlePreview = async (agentId) => {
    try {
      const res = await api.post(`/workspaces/${workspaceId}/agents/${agentId}/preview`, { prompt: "Introduce yourself." });
      setPreviewData(res.data);
      setPreviewOpen(true);
    } catch (err) { toast.error("Preview failed"); }
  };

  const toggleSkill = (skillId) => {
    setForm(prev => {
      const existing = prev.skills.find(s => s.skill_id === skillId);
      if (existing) {
        return { ...prev, skills: prev.skills.filter(s => s.skill_id !== skillId) };
      }
      return { ...prev, skills: [...prev.skills, { skill_id: skillId, level: "intermediate", priority: 2, custom_instructions: "" }] };
    });
  };

  const updateSkillLevel = (skillId, level) => {
    setForm(prev => ({
      ...prev,
      skills: prev.skills.map(s => s.skill_id === skillId ? { ...s, level } : s),
    }));
  };

  const filteredSkills = skills.filter(s =>
    !skillSearch || s.name?.toLowerCase().includes(skillSearch.toLowerCase()) || s.category?.toLowerCase().includes(skillSearch.toLowerCase())
  );

  const COLORS = ["#6366F1", "#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899", "#0EA5E9", "#14B8A6", "#F97316"];

  if (loading) return <div className="flex-1 flex items-center justify-center"><div className="text-zinc-500 text-sm">Loading studio...</div></div>;

  return (
    <div className="flex-1 flex flex-col overflow-hidden" data-testid="agent-studio">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-zinc-800/60">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-zinc-100" style={{ fontFamily: "Syne, sans-serif" }}>Agent Creator Studio</h1>
            <p className="text-xs text-zinc-500 mt-0.5">{agents.length} agent{agents.length !== 1 ? "s" : ""} configured</p>
          </div>
          <Button onClick={() => openWizard()} className="bg-cyan-600 hover:bg-cyan-700 text-white gap-1.5 text-xs" data-testid="create-agent-btn">
            <Plus className="w-3.5 h-3.5" /> New Agent
          </Button>
        </div>
      </div>

      {/* Agent Grid */}
      <ScrollArea className="flex-1">
        <div className="p-6">
          {agents.length === 0 ? (
            <div className="text-center py-16">
              <Brain className="w-12 h-12 text-zinc-700 mx-auto mb-3" />
              <p className="text-zinc-400 text-sm mb-1">No custom agents yet</p>
              <p className="text-zinc-600 text-xs mb-4">Create your first AI agent with custom skills, personality, and guardrails</p>
              <Button onClick={() => openWizard()} variant="outline" className="border-zinc-700 text-zinc-300 gap-1.5 text-xs" data-testid="create-first-agent-btn">
                <Wand2 className="w-3.5 h-3.5" /> Create Agent
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {agents.map(agent => (
                <AgentCard
                  key={agent.agent_id}
                  agent={agent}
                  onEdit={() => openWizard(agent)}
                  onClone={() => handleClone(agent.agent_id)}
                  onPreview={() => handlePreview(agent.agent_id)}
                  onStatusChange={(s) => handleStatusChange(agent.agent_id, s)}
                />
              ))}
            </div>
          )}
        </div>
      </ScrollArea>

      <AgentWizard
        open={wizardOpen}
        onOpenChange={setWizardOpen}
        wizard={{
          step, form, setForm, selectedAgent, models, categories,
          filteredSkills, availableTools,
          skillSearch, setSkillSearch, tagInput, setTagInput,
          forbiddenInput, setForbiddenInput,
          testPrompt, testResponse, testLoading,
          topicSuggestions, trainingTopics, trainingUrls, trainingStatus,
          setTrainingTopics, setTrainingUrls, setTrainingStatus,
          setTestPrompt: setTestPrompt,
        }}
        onStepChange={setStep}
        onSave={handleSave}
        onTest={async () => {
          if (!testPrompt.trim() || !selectedAgent) return;
          setTestLoading(true);
          try {
            const res = await api.post(`/workspaces/${workspaceId}/agents/${selectedAgent.agent_id}/test`, { prompt: testPrompt });
            setTestResponse(res.data.response || res.data.output || JSON.stringify(res.data));
          } catch (err) { setTestResponse(`Error: ${err.response?.data?.detail || err.message}`); }
          setTestLoading(false);
        }}
        onToggleSkill={toggleSkill}
        onUpdateSkillLevel={updateSkillLevel}
        workspaceId={workspaceId}
      />

      {/* Preview Dialog */}
      <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-zinc-100 flex items-center gap-2"><Eye className="w-4 h-4 text-cyan-400" /> Prompt Preview</DialogTitle>
            <DialogDescription className="sr-only">Preview assembled system prompt</DialogDescription>
          </DialogHeader>
          {previewData && (
            <div className="space-y-3">
              <div className="bg-zinc-950 rounded-lg p-3 max-h-64 overflow-y-auto">
                <pre className="text-xs text-zinc-300 whitespace-pre-wrap font-mono">{previewData.assembled_prompt_preview}</pre>
              </div>
              <p className="text-[10px] text-zinc-600">Prompt length: {previewData.prompt_length} chars</p>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function AgentCard({ agent, onEdit, onClone, onPreview, onStatusChange }) {
  const statusColors = { active: "bg-emerald-500", paused: "bg-amber-500", draft: "bg-zinc-500", archived: "bg-zinc-700" };
  return (
    <div className="bg-zinc-900/50 border border-zinc-800/60 rounded-xl p-4 hover:border-zinc-700/60 transition-colors group" data-testid={`agent-card-${agent.agent_id}`}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg flex items-center justify-center text-xs font-bold text-white" style={{ backgroundColor: agent.color || "#6366F1" }}>
            {agent.avatar || agent.name?.slice(0, 2).toUpperCase()}
          </div>
          <div>
            <p className="text-sm font-medium text-zinc-100">{agent.name}</p>
            <div className="flex items-center gap-1.5">
              <span className={`w-1.5 h-1.5 rounded-full ${statusColors[agent.status] || "bg-zinc-500"}`} />
              <span className="text-[10px] text-zinc-500">{agent.base_model} / v{agent.version || 1}</span>
            </div>
          </div>
        </div>
        {agent.forked_from && <GitBranch className="w-3 h-3 text-zinc-600" title="Forked agent" />}
      </div>

      {agent.description && <p className="text-xs text-zinc-500 mb-2 line-clamp-2">{agent.description}</p>}

      {/* Skills badges */}
      {agent.skills?.length > 0 && (
        <div className="flex gap-1 flex-wrap mb-3">
          {agent.skills.slice(0, 4).map(s => (
            <Badge key={s.skill_id} variant="secondary" className="text-[9px] bg-zinc-800 text-zinc-400 px-1.5 py-0">
              {s.skill_id.replace(/_/g, " ")} <span style={{ color: LEVEL_COLORS[s.level] }} className="ml-0.5">{s.level?.[0]?.toUpperCase()}</span>
            </Badge>
          ))}
          {agent.skills.length > 4 && <Badge variant="secondary" className="text-[9px] bg-zinc-800 text-zinc-500 px-1.5 py-0">+{agent.skills.length - 4}</Badge>}
        </div>
      )}

      {/* Stats */}
      {agent.stats && (
        <div className="flex gap-3 mb-3 text-[10px] text-zinc-600">
          <span>{agent.stats.total_messages || 0} msgs</span>
          <span>{agent.stats.total_tool_calls || 0} tools</span>
          {agent.evaluation?.overall_score > 0 && (
            <span className="flex items-center gap-0.5"><Star className="w-2.5 h-2.5 text-amber-500" />{agent.evaluation.overall_score}</span>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
        <Button variant="ghost" size="sm" onClick={onEdit} className="text-zinc-400 hover:text-zinc-100 text-[10px] h-7 px-2" data-testid={`edit-agent-${agent.agent_id}`}>
          <Settings className="w-3 h-3 mr-1" /> Edit
        </Button>
        <Button variant="ghost" size="sm" onClick={onPreview} className="text-zinc-400 hover:text-cyan-400 text-[10px] h-7 px-2" data-testid={`preview-agent-${agent.agent_id}`}>
          <Eye className="w-3 h-3 mr-1" /> Preview
        </Button>
        <Button variant="ghost" size="sm" onClick={onClone} className="text-zinc-400 hover:text-violet-400 text-[10px] h-7 px-2" data-testid={`clone-agent-${agent.agent_id}`}>
          <Copy className="w-3 h-3 mr-1" /> Clone
        </Button>
        {agent.status === "active" ? (
          <Button variant="ghost" size="sm" onClick={() => onStatusChange("paused")} className="text-zinc-400 hover:text-amber-400 text-[10px] h-7 px-2" data-testid={`pause-agent-${agent.agent_id}`}>Pause</Button>
        ) : (
          <Button variant="ghost" size="sm" onClick={() => onStatusChange("active")} className="text-zinc-400 hover:text-emerald-400 text-[10px] h-7 px-2" data-testid={`activate-agent-${agent.agent_id}`}>Activate</Button>
        )}
      </div>
    </div>
  );
}
