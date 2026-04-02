import { useState, useEffect } from "react";
import { api } from "@/App";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Zap, Shield, Bot, FileCode, Plus, Trash2, ChevronDown, ChevronRight, Target, CheckCircle2, Upload, FileText, Pencil } from "lucide-react";

const AI_COLORS = {
  claude: "#D97757", chatgpt: "#10A37F", gemini: "#4285F4", deepseek: "#4D6BFE",
  grok: "#F5F5F5", groq: "#F55036", perplexity: "#20B2AA", mistral: "#FF7000",
  cohere: "#39594D", mercury: "#00D4FF", pi: "#FF6B35", manus: "#6C5CE7",
  qwen: "#615EFF", kimi: "#000000", llama: "#0467DF", glm: "#3D5AFE",
  cursor: "#00E5A0", notebooklm: "#FBBC04", copilot: "#171515",
};
const AI_NAMES = {
  claude: "Claude", chatgpt: "ChatGPT", gemini: "Gemini", deepseek: "DeepSeek",
  grok: "Grok", groq: "Groq", perplexity: "Perplexity", mistral: "Mistral",
  cohere: "Cohere", mercury: "Mercury 2", pi: "Pi", manus: "Manus",
  qwen: "Qwen", kimi: "Kimi", llama: "Llama", glm: "GLM",
  cursor: "Cursor", notebooklm: "NotebookLM", copilot: "GitHub Copilot",
};

export default function DirectiveSetup({ channel, open, onOpenChange }) {
  const [step, setStep] = useState(0); // 0=project, 1=agents, 2=rules, 3=phases
  const [projectName, setProjectName] = useState("");
  const [description, setDescription] = useState("");
  const [goal, setGoal] = useState("");
  const [agentConfigs, setAgentConfigs] = useState({});
  const [rules, setRules] = useState({
    full_file_context: true,
    additive_only: true,
    max_retries: 3,
    prohibited_patterns: [],
    max_parallel_tasks: 5,
  });
  const [newPattern, setNewPattern] = useState("");
  const [phases, setPhases] = useState([{ name: "Phase 1", gate: "", tasks: [{ title: "", description: "", assigned_agent: "", target_file: "" }] }]);
  const [creating, setCreating] = useState(false);
  const [activeDirective, setActiveDirective] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [uploadedDoc, setUploadedDoc] = useState(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    if (open && channel) {
      // Check for existing directive
      api.get(`/channels/${channel.channel_id}/directive`)
        .then(r => setActiveDirective(r.data?.directive))
        .catch(() => {});
      // Pre-fill agent configs from channel agents
      const configs = {};
      (channel.ai_agents || []).forEach(key => {
        configs[key] = { display_name: AI_NAMES[key] || key, role: "contributor", prompt_constraints: [] };
      });
      setAgentConfigs(configs);
      setProjectName(channel.name || "");
    }
  }, [open, channel]);

  const addPhase = () => {
    setPhases([...phases, { name: `Phase ${phases.length + 1}`, gate: "", tasks: [{ title: "", description: "", assigned_agent: "", target_file: "" }] }]);
  };

  const addTask = (phaseIdx) => {
    const p = [...phases];
    p[phaseIdx].tasks.push({ title: "", description: "", assigned_agent: "", target_file: "" });
    setPhases(p);
  };

  const updatePhase = (idx, field, value) => {
    const p = [...phases];
    p[idx][field] = value;
    setPhases(p);
  };

  const updateTask = (phaseIdx, taskIdx, field, value) => {
    const p = [...phases];
    p[phaseIdx].tasks[taskIdx][field] = value;
    setPhases(p);
  };

  const removeTask = (phaseIdx, taskIdx) => {
    const p = [...phases];
    p[phaseIdx].tasks.splice(taskIdx, 1);
    setPhases(p);
  };

  const handleCreate = async () => {
    if (!projectName.trim()) { toast.error("Project name required"); return; }
    setCreating(true);
    try {
      const payload = {
        project_name: projectName,
        description: description + (uploadedDoc ? `\n\n--- Uploaded Document: ${uploadedDoc.filename} ---\n${uploadedDoc.content}` : ""),
        goal,
        agents: agentConfigs,
        universal_rules: rules,
        phases: phases.filter(p => p.tasks.some(t => t.title.trim())),
      };
      
      let res;
      if (isEditing) {
        res = await api.put(`/channels/${channel.channel_id}/directive`, payload);
        toast.success("Directive updated!");
      } else {
        res = await api.post(`/channels/${channel.channel_id}/directive`, payload);
        toast.success("Directive activated!");
      }
      setActiveDirective(res.data);
      setIsEditing(false);
      onOpenChange(false);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to create directive");
    }
    setCreating(false);
  };

  const steps = ["Project", "Agents", "Rules", "Phases"];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-zinc-900 border-zinc-800 max-w-2xl max-h-[85vh] overflow-hidden flex flex-col" style={{ zIndex: 200 }}>
        <DialogHeader>
          <DialogTitle className="text-zinc-100 flex items-center gap-2" style={{ fontFamily: "Syne, sans-serif" }}>
            <Target className="w-5 h-5 text-amber-400" />
            {activeDirective ? "Active Directive" : isEditing ? "Edit Directive" : "Setup Directive"}
          </DialogTitle>
          <DialogDescription className="text-zinc-500 text-sm">
            {activeDirective ? `"${activeDirective.project_name}" is active` : isEditing ? "Modify the active directive" : "Define goals, configure agents, and set rules for this channel"}
          </DialogDescription>
        </DialogHeader>

        {/* Active directive view */}
        {activeDirective ? (
          <div className="space-y-3 mt-2">
            <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
              <p className="text-sm text-emerald-400 font-medium">{activeDirective.project_name}</p>
              {activeDirective.goal && <p className="text-xs text-zinc-400 mt-1">{activeDirective.goal}</p>}
              {activeDirective.description && <p className="text-xs text-zinc-500 mt-1 line-clamp-2">{activeDirective.description}</p>}
              <div className="flex items-center gap-2 mt-2">
                <Badge className="bg-emerald-500/20 text-emerald-400 text-[10px]">Active</Badge>
                <span className="text-[10px] text-zinc-500">{Object.keys(activeDirective.agents || {}).length} agents configured</span>
                {activeDirective.phases?.length > 0 && (
                  <span className="text-[10px] text-zinc-500">{activeDirective.phases.length} phases</span>
                )}
              </div>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => {
                // Pre-fill form with existing directive data for editing
                setProjectName(activeDirective.project_name || "");
                setDescription(activeDirective.description || "");
                setGoal(activeDirective.goal || "");
                if (activeDirective.agents) {
                  setAgentConfigs(activeDirective.agents);
                }
                if (activeDirective.universal_rules) {
                  setRules({
                    full_file_context: activeDirective.universal_rules.full_file_context ?? true,
                    additive_only: activeDirective.universal_rules.additive_only ?? true,
                    max_retries: activeDirective.universal_rules.max_retries_on_validation_fail ?? 3,
                    prohibited_patterns: activeDirective.universal_rules.prohibited_patterns || [],
                    max_parallel_tasks: activeDirective.universal_rules.max_parallel_tasks ?? 5,
                  });
                }
                if (activeDirective.phases?.length > 0) {
                  setPhases(activeDirective.phases);
                }
                setActiveDirective(null);
                setIsEditing(true);
                setStep(0);
              }} className="flex-1 border-zinc-700 text-zinc-300" data-testid="edit-directive-btn">
                <Pencil className="w-3 h-3 mr-1.5" />
                Edit Directive
              </Button>
              <Button variant="outline" onClick={() => { setActiveDirective(null); setIsEditing(false); setStep(0); }} className="flex-1 border-zinc-700 text-zinc-300" data-testid="new-directive-btn">
                <Plus className="w-3 h-3 mr-1.5" />
                New Directive
              </Button>
            </div>
          </div>
        ) : (
          <>
            {/* Step indicators */}
            <div className="flex items-center gap-1 mt-2">
              {steps.map((s, i) => (
                <button key={s} onClick={() => setStep(i)}
                  className={`flex-1 py-1.5 text-[10px] font-medium rounded-md transition-colors ${
                    step === i ? "bg-amber-500/20 text-amber-400" : i < step ? "bg-emerald-500/10 text-emerald-400" : "bg-zinc-800 text-zinc-600"
                  }`}>
                  {i < step ? <CheckCircle2 className="w-3 h-3 inline mr-0.5" /> : null}{s}
                </button>
              ))}
            </div>

            <ScrollArea className="flex-1 mt-2">
              {/* Step 0: Project */}
              {step === 0 && (
                <div className="space-y-3">
                  <div>
                    <label className="text-xs text-zinc-400 block mb-1">Project Name *</label>
                    <Input value={projectName} onChange={(e) => setProjectName(e.target.value)}
                      placeholder="My AI Project" className="bg-zinc-950 border-zinc-800" data-testid="directive-name" />
                  </div>
                  <div>
                    <label className="text-xs text-zinc-400 block mb-1">Goal</label>
                    <Input value={goal} onChange={(e) => setGoal(e.target.value)}
                      placeholder="What should the agents accomplish?" className="bg-zinc-950 border-zinc-800" data-testid="directive-goal" />
                  </div>
                  <div>
                    <label className="text-xs text-zinc-400 block mb-1">Description</label>
                    <textarea value={description} onChange={(e) => setDescription(e.target.value)}
                      placeholder="Detailed project context..." rows={3}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-md px-3 py-2 text-sm text-zinc-200 resize-none" />
                  </div>
                  {/* File Upload */}
                  <div>
                    <label className="text-xs text-zinc-400 block mb-1">Upload Reference Document</label>
                    <p className="text-[10px] text-zinc-600 mb-2">Upload a .txt, .md, .pdf, or .docx file to provide context to the AI agents.</p>
                    {uploadedDoc ? (
                      <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                        <div className="flex items-center gap-2">
                          <FileText className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                          <div className="flex-1 min-w-0">
                            <p className="text-xs text-emerald-400 font-medium truncate">{uploadedDoc.filename}</p>
                            <p className="text-[10px] text-zinc-500">{uploadedDoc.char_count.toLocaleString()} characters extracted</p>
                          </div>
                          <button onClick={() => setUploadedDoc(null)} className="text-zinc-500 hover:text-red-400 text-xs">Remove</button>
                        </div>
                        {uploadedDoc.preview && (
                          <p className="text-[10px] text-zinc-500 mt-2 line-clamp-3 bg-zinc-900/50 rounded p-2">{uploadedDoc.preview.substring(0, 300)}...</p>
                        )}
                      </div>
                    ) : (
                      <label className="flex items-center justify-center gap-2 px-4 py-3 rounded-lg border border-dashed border-zinc-700 hover:border-zinc-500 cursor-pointer transition-colors bg-zinc-900/30" data-testid="directive-upload">
                        <Upload className={`w-4 h-4 ${uploading ? "animate-spin text-amber-400" : "text-zinc-500"}`} />
                        <span className="text-xs text-zinc-400">{uploading ? "Parsing..." : "Click to upload (.txt, .pdf, .docx)"}</span>
                        <input type="file" className="hidden" accept=".txt,.md,.pdf,.docx,.doc"
                          onChange={async (e) => {
                            const file = e.target.files?.[0];
                            if (!file) return;
                            setUploading(true);
                            try {
                              const formData = new FormData();
                              formData.append("file", file);
                              const res = await api.post("/directives/upload-document", formData, {
                                headers: { "Content-Type": "multipart/form-data" },
                              });
                              setUploadedDoc(res.data);
                              toast.success(`Parsed: ${res.data.char_count.toLocaleString()} characters from ${file.name}`);
                            } catch (err) {
                              toast.error(err.response?.data?.detail || "Upload failed");
                            }
                            setUploading(false);
                            e.target.value = "";
                          }}
                        />
                      </label>
                    )}
                  </div>
                </div>
              )}

              {/* Step 1: Agent Configuration */}
              {step === 1 && (
                <div className="space-y-2">
                  <p className="text-xs text-zinc-500 mb-2">Configure each agent's role and constraints for this directive.</p>
                  {Object.entries(agentConfigs).map(([key, cfg]) => (
                    <div key={key} className="p-3 rounded-lg bg-zinc-800/30 border border-zinc-800/40 space-y-2">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-full flex items-center justify-center text-[9px] font-bold"
                          style={{ backgroundColor: AI_COLORS[key] || "#666", color: key === "grok" ? "#09090b" : "#fff" }}>
                          {(AI_NAMES[key] || key)[0]}
                        </div>
                        <span className="text-xs font-medium text-zinc-200">{AI_NAMES[key] || key}</span>
                        <select value={cfg.role} onChange={(e) => setAgentConfigs(prev => ({ ...prev, [key]: { ...prev[key], role: e.target.value } }))}
                          className="ml-auto bg-zinc-900 border border-zinc-700 rounded px-2 py-0.5 text-[10px] text-zinc-300">
                          <option value="contributor">Contributor</option>
                          <option value="reviewer">Reviewer</option>
                          <option value="lead">Lead</option>
                          <option value="specialist">Specialist</option>
                        </select>
                      </div>
                      <Input placeholder="Custom constraints (e.g., Focus on security)"
                        value={cfg.prompt_constraints?.join(", ") || ""}
                        onChange={(e) => setAgentConfigs(prev => ({ ...prev, [key]: { ...prev[key], prompt_constraints: e.target.value ? e.target.value.split(", ") : [] } }))}
                        className="bg-zinc-950 border-zinc-800 text-xs h-7" />
                    </div>
                  ))}
                </div>
              )}

              {/* Step 2: Rules */}
              {step === 2 && (
                <div className="space-y-3">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" checked={rules.full_file_context} onChange={(e) => setRules(r => ({ ...r, full_file_context: e.target.checked }))} className="accent-amber-500" />
                    <span className="text-xs text-zinc-300">Require full file context (agents see complete files)</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" checked={rules.additive_only} onChange={(e) => setRules(r => ({ ...r, additive_only: e.target.checked }))} className="accent-amber-500" />
                    <span className="text-xs text-zinc-300">Additive only (agents can't delete existing code)</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" checked={rules.require_dual_review} onChange={(e) => setRules(r => ({ ...r, require_dual_review: e.target.checked }))} className="accent-amber-500" />
                    <span className="text-xs text-zinc-300">Require dual review before merge</span>
                  </label>
                  <div>
                    <label className="text-xs text-zinc-400 block mb-1">Max retries on validation fail</label>
                    <Input type="number" min={1} max={5} value={rules.max_retries}
                      onChange={(e) => setRules(r => ({ ...r, max_retries: parseInt(e.target.value) || 3 }))}
                      className="bg-zinc-950 border-zinc-800 w-20 h-7 text-xs" />
                  </div>
                  <div>
                    <label className="text-xs text-zinc-400 block mb-1">Prohibited patterns</label>
                    <div className="flex gap-1 mb-1 flex-wrap">
                      {rules.prohibited_patterns.map((p, i) => (
                        <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/15 text-red-400 flex items-center gap-1">
                          {p}
                          <button onClick={() => setRules(r => ({ ...r, prohibited_patterns: r.prohibited_patterns.filter((_, j) => j !== i) }))} className="text-red-400/60 hover:text-red-400">&times;</button>
                        </span>
                      ))}
                    </div>
                    <div className="flex gap-1">
                      <Input value={newPattern} onChange={(e) => setNewPattern(e.target.value)}
                        placeholder="e.g., omitted for brevity" className="bg-zinc-950 border-zinc-800 text-xs h-7 flex-1"
                        onKeyDown={(e) => { if (e.key === "Enter" && newPattern.trim()) { setRules(r => ({ ...r, prohibited_patterns: [...r.prohibited_patterns, newPattern.trim()] })); setNewPattern(""); } }} />
                      <Button size="sm" onClick={() => { if (newPattern.trim()) { setRules(r => ({ ...r, prohibited_patterns: [...r.prohibited_patterns, newPattern.trim()] })); setNewPattern(""); } }}
                        className="h-7 px-2 bg-zinc-800 text-zinc-300"><Plus className="w-3 h-3" /></Button>
                    </div>
                  </div>
                </div>
              )}

              {/* Step 3: Phases & Tasks */}
              {step === 3 && (
                <div className="space-y-3">
                  {phases.map((phase, pi) => (
                    <div key={pi} className="p-3 rounded-lg bg-zinc-800/20 border border-zinc-800/40 space-y-2">
                      <div className="flex items-center gap-2">
                        <Input value={phase.name} onChange={(e) => updatePhase(pi, "name", e.target.value)}
                          className="bg-zinc-950 border-zinc-800 text-xs h-7 font-medium" placeholder="Phase name" />
                        <Input value={phase.gate} onChange={(e) => updatePhase(pi, "gate", e.target.value)}
                          className="bg-zinc-950 border-zinc-800 text-xs h-7 flex-1" placeholder="Gate condition (e.g., all tests pass)" />
                      </div>
                      {phase.tasks.map((task, ti) => (
                        <div key={ti} className="pl-3 border-l-2 border-zinc-800 space-y-1">
                          <div className="flex gap-1">
                            <Input value={task.title} onChange={(e) => updateTask(pi, ti, "title", e.target.value)}
                              className="bg-zinc-950 border-zinc-800 text-xs h-7 flex-1" placeholder="Task title" />
                            <select value={task.assigned_agent} onChange={(e) => updateTask(pi, ti, "assigned_agent", e.target.value)}
                              className="bg-zinc-950 border border-zinc-800 rounded text-[10px] text-zinc-300 px-1.5">
                              <option value="">Agent...</option>
                              {Object.keys(agentConfigs).map(k => <option key={k} value={k}>{AI_NAMES[k] || k}</option>)}
                            </select>
                            <button onClick={() => removeTask(pi, ti)} className="p-1 text-zinc-600 hover:text-red-400"><Trash2 className="w-3 h-3" /></button>
                          </div>
                          <Input value={task.description} onChange={(e) => updateTask(pi, ti, "description", e.target.value)}
                            className="bg-zinc-950 border-zinc-800 text-[10px] h-6" placeholder="Description (optional)" />
                          <Input value={task.target_file} onChange={(e) => updateTask(pi, ti, "target_file", e.target.value)}
                            className="bg-zinc-950 border-zinc-800 text-[10px] h-6 font-mono" placeholder="Target file (e.g., src/main.py)" />
                        </div>
                      ))}
                      <button onClick={() => addTask(pi)} className="text-[10px] text-emerald-400 hover:text-emerald-300 flex items-center gap-1 pl-3">
                        <Plus className="w-3 h-3" /> Add Task
                      </button>
                    </div>
                  ))}
                  <button onClick={addPhase} className="text-xs text-amber-400 hover:text-amber-300 flex items-center gap-1">
                    <Plus className="w-3.5 h-3.5" /> Add Phase
                  </button>
                </div>
              )}
            </ScrollArea>

            {/* Navigation */}
            <div className="flex items-center justify-between mt-3 pt-3 border-t border-zinc-800">
              {step > 0 ? (
                <Button variant="outline" size="sm" onClick={() => setStep(step - 1)} className="border-zinc-700 text-zinc-300">Back</Button>
              ) : <div />}
              {step < 3 ? (
                <Button size="sm" onClick={() => setStep(step + 1)} className="bg-zinc-100 text-zinc-900">
                  Next
                </Button>
              ) : (
                <Button size="sm" onClick={handleCreate} disabled={creating || !projectName.trim()} className="bg-amber-500 hover:bg-amber-400 text-white" data-testid="activate-directive-btn">
                  {creating ? (isEditing ? "Updating..." : "Activating...") : isEditing ? "Update Directive" : "Activate Directive"}
                </Button>
              )}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
