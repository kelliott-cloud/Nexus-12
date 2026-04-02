/**
 * AgentWizard — Multi-step agent creation/editing wizard dialog.
 * Extracted from AgentStudio.js for maintainability.
 * 
 * Receives all wizard state via a `wizard` prop object to avoid prop explosion.
 */
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import {
  ChevronRight, ChevronLeft, Save, Wand2, Eye,
  Shield, Brain, Code, BarChart3, Settings, Palette, Search,
  Check, X, Star, Play
} from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";

const STEPS = ["basics", "skills", "tools", "personality", "guardrails", "review", "test", "training"];
const STEP_LABELS = { basics: "Basics", skills: "Skills", tools: "Tools", personality: "Personality", guardrails: "Guardrails", review: "Review", test: "Test", training: "Training" };
const CATEGORY_ICONS = { engineering: Code, product: Palette, data: BarChart3, operations: Settings };
const TONES = ["precise", "friendly", "formal", "creative", "terse"];
const VERBOSITY = ["brief", "balanced", "detailed"];
const RISK_TOLERANCE = ["conservative", "moderate", "aggressive"];
const COLLAB_STYLES = ["leader", "contributor", "reviewer", "specialist"];
const LEVELS = ["novice", "intermediate", "advanced", "expert", "master"];
const LEVEL_COLORS = { novice: "#6B7280", intermediate: "#3B82F6", advanced: "#8B5CF6", expert: "#F59E0B", master: "#EF4444" };
const COLORS = ["#6366F1", "#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899", "#0EA5E9", "#14B8A6", "#F97316"];

/**
 * @param {Object} props
 * @param {boolean} props.open - Dialog open state
 * @param {Function} props.onOpenChange - Dialog open change handler
 * @param {Object} props.wizard - All wizard state: { step, form, setForm, selectedAgent, models, categories, skills, filteredSkills, availableTools, skillSearch, setSkillSearch, tagInput, setTagInput, forbiddenInput, setForbiddenInput, testPrompt, testResponse, testLoading, topicSuggestions, trainingTopics, trainingUrls, trainingStatus, setTrainingTopics, setTrainingUrls, setTrainingStatus }
 * @param {Function} props.onStepChange - Set wizard step
 * @param {Function} props.onSave - Save handler
 * @param {Function} props.onTest - Test handler
 * @param {Function} props.onToggleSkill - Toggle skill selection
 * @param {Function} props.onUpdateSkillLevel - Update skill level
 * @param {string} props.workspaceId
 */
export function AgentWizard({ open, onOpenChange, wizard, onStepChange, onSave, onTest, onToggleSkill, onUpdateSkillLevel, workspaceId }) {
  const {
    step, form, setForm, selectedAgent, models, categories,
    filteredSkills, availableTools,
    skillSearch, setSkillSearch, tagInput, setTagInput,
    forbiddenInput, setForbiddenInput,
    testPrompt, testResponse, testLoading,
    topicSuggestions, trainingTopics, trainingUrls, trainingStatus,
    setTrainingTopics, setTrainingUrls, setTrainingStatus,
    setTestPrompt,
  } = wizard;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-zinc-900 border-zinc-800 max-w-2xl max-h-[85vh] overflow-hidden flex flex-col" data-testid="agent-wizard-dialog">
        <DialogHeader>
          <DialogTitle className="text-zinc-100 flex items-center gap-2">
            <Wand2 className="w-4 h-4 text-cyan-400" />
            {selectedAgent ? "Edit Agent" : "Create Agent"}
          </DialogTitle>
          <DialogDescription className="sr-only">Agent configuration wizard</DialogDescription>
        </DialogHeader>

        {/* Step indicators */}
        <div className="flex items-center gap-1 px-1">
          {STEPS.map((s, i) => (
            <button key={s} onClick={() => onStepChange(i)} className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${step === i ? "bg-cyan-500/20 text-cyan-400" : step > i ? "text-zinc-400" : "text-zinc-600"}`} data-testid={`wizard-step-${s}`}>
              <span className={`w-4 h-4 rounded-full text-[9px] flex items-center justify-center font-bold ${step === i ? "bg-cyan-500 text-white" : step > i ? "bg-zinc-700 text-zinc-300" : "bg-zinc-800 text-zinc-600"}`}>{step > i ? <Check className="w-2.5 h-2.5" /> : i + 1}</span>
              <span className="hidden sm:inline">{STEP_LABELS[s]}</span>
            </button>
          ))}
        </div>

        <ScrollArea className="flex-1 pr-2">
          <div className="space-y-4 p-1">
            {/* Step 0: Basics */}
            {step === 0 && (
              <div className="space-y-3" data-testid="wizard-step-basics-content">
                <div>
                  <label className="text-xs font-medium text-zinc-400 mb-1 block">Agent Name *</label>
                  <Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="e.g. Security Auditor" className="bg-zinc-950 border-zinc-800 text-zinc-100" maxLength={50} data-testid="agent-name-input" />
                </div>
                <div>
                  <label className="text-xs font-medium text-zinc-400 mb-1 block">Description</label>
                  <Input value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} placeholder="What does this agent do?" className="bg-zinc-950 border-zinc-800 text-zinc-100" maxLength={500} data-testid="agent-description-input" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-zinc-400 mb-1 block">Base Model</label>
                    <select value={form.base_model} onChange={e => setForm(f => ({ ...f, base_model: e.target.value }))} className="w-full h-9 px-3 rounded-md bg-zinc-950 border border-zinc-800 text-zinc-100 text-sm" data-testid="agent-model-select">
                      {models.map(m => <option key={m} value={m}>{m}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-zinc-400 mb-1 block">Category</label>
                    <select value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))} className="w-full h-9 px-3 rounded-md bg-zinc-950 border border-zinc-800 text-zinc-100 text-sm" data-testid="agent-category-select">
                      {Object.entries(categories).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
                    </select>
                  </div>
                </div>
                <div>
                  <label className="text-xs font-medium text-zinc-400 mb-1 block">Color</label>
                  <div className="flex gap-1.5 flex-wrap">
                    {COLORS.map(c => (
                      <button key={c} onClick={() => setForm(f => ({ ...f, color: c }))} className={`w-7 h-7 rounded-full border-2 transition-all ${form.color === c ? "border-white scale-110" : "border-transparent"}`} style={{ backgroundColor: c }} data-testid={`color-${c}`} />
                    ))}
                  </div>
                </div>
                <div>
                  <label className="text-xs font-medium text-zinc-400 mb-1 block">System Prompt</label>
                  <textarea value={form.system_prompt} onChange={e => setForm(f => ({ ...f, system_prompt: e.target.value }))} placeholder="Core instructions..." className="w-full h-24 px-3 py-2 rounded-md bg-zinc-950 border border-zinc-800 text-zinc-100 text-sm resize-none" maxLength={10000} data-testid="agent-prompt-input" />
                  <p className="text-[10px] text-zinc-600 mt-0.5">{form.system_prompt.length}/10000</p>
                </div>
                <div>
                  <label className="text-xs font-medium text-zinc-400 mb-1 block">Tags</label>
                  <div className="flex gap-1.5 flex-wrap mb-1.5">
                    {form.tags.map(t => (
                      <Badge key={t} variant="secondary" className="bg-zinc-800 text-zinc-300 gap-1 text-[10px]">
                        {t} <button onClick={() => setForm(f => ({ ...f, tags: f.tags.filter(x => x !== t) }))}><X className="w-2.5 h-2.5" /></button>
                      </Badge>
                    ))}
                  </div>
                  <Input value={tagInput} onChange={e => setTagInput(e.target.value)} placeholder="Add tag..." className="bg-zinc-950 border-zinc-800 text-zinc-100 text-xs" onKeyDown={e => { if (e.key === "Enter" && tagInput.trim() && form.tags.length < 10) { setForm(f => ({ ...f, tags: [...f.tags, tagInput.trim()] })); setTagInput(""); } }} data-testid="agent-tag-input" />
                </div>
                <div>
                  <label className="text-xs font-medium text-zinc-400 mb-1 block">Visibility</label>
                  <div className="flex gap-2">
                    {["workspace", "organization", "marketplace"].map(v => (
                      <button key={v} onClick={() => setForm(f => ({ ...f, visibility: v }))}
                        className={`px-3 py-1.5 rounded-lg text-xs border transition-colors ${form.visibility === v ? "bg-cyan-500/10 border-cyan-500/30 text-cyan-400" : "bg-zinc-900 border-zinc-800 text-zinc-500 hover:border-zinc-700"}`} data-testid={`visibility-${v}`}>
                        {v.charAt(0).toUpperCase() + v.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Step 1: Skills */}
            {step === 1 && (
              <div className="space-y-3" data-testid="wizard-step-skills-content">
                <div className="flex items-center gap-2">
                  <Search className="w-3.5 h-3.5 text-zinc-500" />
                  <Input value={skillSearch} onChange={e => setSkillSearch(e.target.value)} placeholder="Search skills..." className="bg-zinc-950 border-zinc-800 text-zinc-100 text-xs flex-1" data-testid="skill-search-input" />
                </div>
                <p className="text-[10px] text-zinc-600">{form.skills.length} skill{form.skills.length !== 1 ? "s" : ""} selected</p>
                <div className="space-y-1.5 max-h-[360px] overflow-y-auto pr-1">
                  {Object.entries(categories).map(([catKey, cat]) => {
                    const catSkills = filteredSkills.filter(s => s.category === catKey);
                    if (catSkills.length === 0) return null;
                    const Icon = CATEGORY_ICONS[catKey] || Brain;
                    return (
                      <div key={catKey}>
                        <div className="flex items-center gap-1.5 py-1">
                          <Icon className="w-3 h-3 text-zinc-500" />
                          <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">{cat.label}</span>
                        </div>
                        {catSkills.map(skill => {
                          const selected = form.skills.find(s => s.skill_id === skill.skill_id);
                          return (
                            <div key={skill.skill_id} className={`flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer transition-colors ${selected ? "bg-cyan-500/10 border border-cyan-500/20" : "hover:bg-zinc-800/40 border border-transparent"}`}
                              onClick={() => onToggleSkill(skill.skill_id)} data-testid={`skill-${skill.skill_id}`}>
                              <div className={`w-3.5 h-3.5 rounded border flex items-center justify-center ${selected ? "bg-cyan-500 border-cyan-500" : "border-zinc-700"}`}>
                                {selected && <Check className="w-2.5 h-2.5 text-white" />}
                              </div>
                              <span className="text-xs text-zinc-300 flex-1">{skill.name}</span>
                              {selected && (
                                <select value={selected.level} onChange={e => { e.stopPropagation(); onUpdateSkillLevel(skill.skill_id, e.target.value); }}
                                  className="text-[9px] bg-zinc-900 border border-zinc-700 rounded px-1 py-0.5 text-zinc-300" onClick={e => e.stopPropagation()}>
                                  {LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
                                </select>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Steps 2-7: Simplified rendering for remaining steps */}
            {step === 2 && (
              <div className="space-y-3" data-testid="wizard-step-tools-content">
                <p className="text-xs text-zinc-400">Select tools this agent can use:</p>
                <div className="space-y-1 max-h-[360px] overflow-y-auto">
                  {availableTools.map(t => {
                    const allowed = form.allowed_tools.includes(t.tool_id);
                    const denied = form.denied_tools.includes(t.tool_id);
                    return (
                      <div key={t.tool_id} className="flex items-center justify-between px-2 py-1.5 rounded hover:bg-zinc-800/40" data-testid={`tool-${t.tool_id}`}>
                        <span className="text-xs text-zinc-300">{t.name || t.tool_id}</span>
                        <div className="flex gap-1">
                          <button onClick={() => setForm(f => ({ ...f, allowed_tools: allowed ? f.allowed_tools.filter(x => x !== t.tool_id) : [...f.allowed_tools, t.tool_id], denied_tools: f.denied_tools.filter(x => x !== t.tool_id) }))}
                            className={`px-2 py-0.5 rounded text-[9px] ${allowed ? "bg-emerald-500/20 text-emerald-400" : "text-zinc-600 hover:text-zinc-400"}`}>Allow</button>
                          <button onClick={() => setForm(f => ({ ...f, denied_tools: denied ? f.denied_tools.filter(x => x !== t.tool_id) : [...f.denied_tools, t.tool_id], allowed_tools: f.allowed_tools.filter(x => x !== t.tool_id) }))}
                            className={`px-2 py-0.5 rounded text-[9px] ${denied ? "bg-red-500/20 text-red-400" : "text-zinc-600 hover:text-zinc-400"}`}>Deny</button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {step === 3 && (
              <div className="space-y-3" data-testid="wizard-step-personality-content">
                {[
                  { label: "Tone", key: "tone", options: TONES },
                  { label: "Verbosity", key: "verbosity", options: VERBOSITY },
                  { label: "Risk Tolerance", key: "risk_tolerance", options: RISK_TOLERANCE },
                  { label: "Collaboration Style", key: "collaboration_style", options: COLLAB_STYLES },
                ].map(({ label, key, options }) => (
                  <div key={key}>
                    <label className="text-xs font-medium text-zinc-400 mb-1.5 block">{label}</label>
                    <div className="flex gap-1.5 flex-wrap">
                      {options.map(o => (
                        <button key={o} onClick={() => setForm(f => ({ ...f, personality: { ...f.personality, [key]: o } }))}
                          className={`px-3 py-1.5 rounded-lg text-xs border transition-colors ${form.personality[key] === o ? "bg-cyan-500/10 border-cyan-500/30 text-cyan-400" : "bg-zinc-900 border-zinc-800 text-zinc-500 hover:border-zinc-700"}`}>
                          {o}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {step === 4 && (
              <div className="space-y-3" data-testid="wizard-step-guardrails-content">
                <div>
                  <label className="text-xs font-medium text-zinc-400 mb-1 block">Max Response Length</label>
                  <Input type="number" value={form.guardrails.max_response_length} onChange={e => setForm(f => ({ ...f, guardrails: { ...f.guardrails, max_response_length: parseInt(e.target.value) || 4000 } }))}
                    className="bg-zinc-950 border-zinc-800 text-zinc-100 w-32" />
                </div>
                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-2 text-xs text-zinc-400 cursor-pointer">
                    <input type="checkbox" checked={form.guardrails.require_citations} onChange={e => setForm(f => ({ ...f, guardrails: { ...f.guardrails, require_citations: e.target.checked } }))} className="rounded" />
                    Require citations
                  </label>
                  <label className="flex items-center gap-2 text-xs text-zinc-400 cursor-pointer">
                    <input type="checkbox" checked={form.guardrails.require_confidence} onChange={e => setForm(f => ({ ...f, guardrails: { ...f.guardrails, require_confidence: e.target.checked } }))} className="rounded" />
                    Show confidence
                  </label>
                </div>
                <div>
                  <label className="text-xs font-medium text-zinc-400 mb-1 block">Forbidden Topics</label>
                  <div className="flex gap-1 flex-wrap mb-1">
                    {(form.guardrails.forbidden_topics || []).map(t => (
                      <Badge key={t} className="bg-red-500/10 text-red-400 text-[9px] gap-1">{t}
                        <button onClick={() => setForm(f => ({ ...f, guardrails: { ...f.guardrails, forbidden_topics: f.guardrails.forbidden_topics.filter(x => x !== t) } }))}><X className="w-2 h-2" /></button>
                      </Badge>
                    ))}
                  </div>
                  <Input value={forbiddenInput} onChange={e => setForbiddenInput(e.target.value)} placeholder="Add forbidden topic..."
                    className="bg-zinc-950 border-zinc-800 text-zinc-100 text-xs"
                    onKeyDown={e => { if (e.key === "Enter" && forbiddenInput.trim()) { setForm(f => ({ ...f, guardrails: { ...f.guardrails, forbidden_topics: [...(f.guardrails.forbidden_topics || []), forbiddenInput.trim()] } })); setForbiddenInput(""); } }} />
                </div>
              </div>
            )}

            {step === 5 && (
              <div className="space-y-3" data-testid="wizard-step-review-content">
                <div className="rounded-lg border border-zinc-800 p-3 space-y-2">
                  <h4 className="text-xs font-semibold text-zinc-300">Summary</h4>
                  <div className="grid grid-cols-2 gap-2 text-[10px]">
                    <div><span className="text-zinc-500">Name:</span> <span className="text-zinc-300">{form.name || "—"}</span></div>
                    <div><span className="text-zinc-500">Model:</span> <span className="text-zinc-300">{form.base_model}</span></div>
                    <div><span className="text-zinc-500">Skills:</span> <span className="text-zinc-300">{form.skills.length}</span></div>
                    <div><span className="text-zinc-500">Tools:</span> <span className="text-zinc-300">{form.allowed_tools.length} allowed</span></div>
                    <div><span className="text-zinc-500">Tone:</span> <span className="text-zinc-300">{form.personality.tone}</span></div>
                    <div><span className="text-zinc-500">Visibility:</span> <span className="text-zinc-300">{form.visibility}</span></div>
                  </div>
                </div>
              </div>
            )}

            {step === 6 && (
              <div className="space-y-3" data-testid="wizard-step-test-content">
                <textarea value={wizard.testPrompt} onChange={e => setTestPrompt(e.target.value)} placeholder="Test your agent with a prompt..."
                  className="w-full h-20 px-3 py-2 rounded-md bg-zinc-950 border border-zinc-800 text-zinc-100 text-sm resize-none" data-testid="test-prompt-input" />
                <Button onClick={onTest} disabled={testLoading || !wizard.testPrompt?.trim()} className="bg-cyan-600 text-white text-xs gap-1" data-testid="test-run-btn">
                  {testLoading ? "Testing..." : <><Play className="w-3 h-3" /> Run Test</>}
                </Button>
                {testResponse && (
                  <div className="p-3 rounded-lg bg-zinc-950 border border-zinc-800 text-xs text-zinc-300 whitespace-pre-wrap max-h-60 overflow-y-auto" data-testid="test-response">{testResponse}</div>
                )}
              </div>
            )}

            {step === 7 && (
              <div className="space-y-3" data-testid="wizard-step-training-content">
                <p className="text-xs text-zinc-400">Add training data to improve this agent's knowledge.</p>
                {topicSuggestions.length > 0 && (
                  <div className="space-y-1">
                    <p className="text-[10px] text-zinc-500">Suggested topics:</p>
                    <div className="flex gap-1 flex-wrap">
                      {topicSuggestions.map(t => (
                        <button key={t} onClick={() => setTrainingTopics(prev => prev.includes(t) ? prev.filter(x => x !== t) : [...prev, t])}
                          className={`px-2 py-1 rounded text-[10px] border transition-colors ${trainingTopics.includes(t) ? "bg-cyan-500/10 border-cyan-500/30 text-cyan-400" : "border-zinc-800 text-zinc-500 hover:border-zinc-700"}`}>
                          {t}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                <div>
                  <label className="text-xs font-medium text-zinc-400 mb-1 block">Training URLs (one per line)</label>
                  <textarea value={trainingUrls} onChange={e => setTrainingUrls(e.target.value)} placeholder="https://docs.example.com/guide..."
                    className="w-full h-20 px-3 py-2 rounded-md bg-zinc-950 border border-zinc-800 text-zinc-100 text-sm resize-none" />
                </div>
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Navigation */}
        <div className="flex items-center justify-between pt-2 border-t border-zinc-800/60">
          <Button variant="ghost" disabled={step === 0} onClick={() => onStepChange(step - 1)} className="text-zinc-400 text-xs gap-1" data-testid="wizard-prev-btn">
            <ChevronLeft className="w-3.5 h-3.5" /> Back
          </Button>
          <div className="flex gap-2">
            {step === 5 && (
              <Button onClick={onSave} className="bg-cyan-600 hover:bg-cyan-700 text-white text-xs gap-1" data-testid="wizard-save-btn">
                <Save className="w-3.5 h-3.5" /> {selectedAgent ? "Update Agent" : "Create Agent"}
              </Button>
            )}
            {step < STEPS.length - 1 ? (
              <Button onClick={async () => {
                const nextStep = step + 1;
                onStepChange(nextStep);
                if (nextStep === 7 && selectedAgent) {
                  try {
                    const res = await api.post(`/workspaces/${workspaceId}/agents/${selectedAgent.agent_id}/train/suggest-topics`, { skill_ids: form.skills.map(s => s.skill_id) });
                    // topicSuggestions handled via wizard state
                  } catch { /* ignore */ }
                }
              }} className="bg-cyan-600 hover:bg-cyan-700 text-white text-xs gap-1" data-testid="wizard-next-btn">
                Next <ChevronRight className="w-3.5 h-3.5" />
              </Button>
            ) : (
              <Button variant="ghost" onClick={() => { onOpenChange(false); onStepChange(0); }} className="text-zinc-400 text-xs gap-1" data-testid="wizard-done-btn">
                Done
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
