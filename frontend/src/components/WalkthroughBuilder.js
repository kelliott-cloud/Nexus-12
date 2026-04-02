import { useState, useEffect, useCallback } from "react";
import { useConfirm } from "@/components/ConfirmDialog";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import {
  Plus, Trash2, Pencil, Play, Pause, Eye, Archive, ChevronRight, Settings,
  MousePointer, MessageSquare, Maximize, Crosshair, GripVertical, ArrowUp, ArrowDown,
  Globe, Clock, Users, Palette, BarChart3, Copy, RotateCcw, Check
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/App";

const STEP_ICONS = { tooltip: MessageSquare, modal: Maximize, spotlight: Crosshair, action: MousePointer };
const STEP_COLORS = { tooltip: "text-blue-400 bg-blue-500/10", modal: "text-purple-400 bg-purple-500/10", spotlight: "text-amber-400 bg-amber-500/10", action: "text-emerald-400 bg-emerald-500/10" };
const STATUS_STYLES = { draft: "bg-zinc-700 text-zinc-300", published: "bg-emerald-500/20 text-emerald-400", archived: "bg-zinc-800 text-zinc-500" };

export default function WalkthroughBuilderPage() {
  const { confirm: confirmAction, ConfirmDialog: ConfirmDlg } = useConfirm();
  const [walkthroughs, setWalkthroughs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [editingStep, setEditingStep] = useState(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [configTab, setConfigTab] = useState("steps"); // steps, trigger, targeting, theme, analytics
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newCategory, setNewCategory] = useState("onboarding");
  const [config, setConfig] = useState(null);

  const fetchAll = useCallback(async () => {
    try {
      const [wRes, cRes] = await Promise.all([api.get("/walkthroughs"), api.get("/walkthroughs/config")]);
      setWalkthroughs(wRes.data.walkthroughs || []);
      setConfig(cRes.data);
    } catch (err) { handleError(err, "WalkthroughBuilder:op1"); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const createWalkthrough = async () => {
    if (!newName.trim()) return;
    try {
      const res = await api.post("/walkthroughs", { name: newName, description: newDesc, category: newCategory });
      setCreateOpen(false); setNewName(""); setNewDesc("");
      setSelected(res.data);
      fetchAll();
      toast.success("Walkthrough created");
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  const selectWalkthrough = async (wtId) => {
    try {
      const res = await api.get(`/walkthroughs/${wtId}`);
      setSelected(res.data);
      setConfigTab("steps");
    } catch (err) { handleError(err, "WalkthroughBuilder:op2"); }
  };

  const publishWalkthrough = async () => {
    if (!selected) return;
    try {
      const res = await api.post(`/walkthroughs/${selected.walkthrough_id}/publish`);
      setSelected(res.data); fetchAll(); toast.success("Published!");
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  const archiveWalkthrough = async () => {
    if (!selected) return;
    try { await api.post(`/walkthroughs/${selected.walkthrough_id}/archive`); fetchAll(); setSelected(null); toast.success("Archived"); }
    catch (err) { handleError(err, "WalkthroughBuilder:op3"); }
  };

  const deleteWalkthrough = async () => {
    const _ok = await confirmAction("Delete Walkthrough", "Delete this walkthrough permanently?"); if (!_ok) return;
    try { await api.delete(`/walkthroughs/${selected.walkthrough_id}`); fetchAll(); setSelected(null); toast.success("Deleted"); }
    catch (err) { handleError(err, "WalkthroughBuilder:op4"); }
  };

  const addStep = async (stepType = "tooltip") => {
    if (!selected) return;
    try {
      const res = await api.post(`/walkthroughs/${selected.walkthrough_id}/steps`, {
        step_type: stepType, selector_primary: "", selector_css: "",
        content: { title: `Step ${(selected.steps?.length || 0) + 1}`, body: "Describe this step...", cta_label: "Next", dismissible: true, show_progress: true },
        behavior: { advance_on: "click_cta", placement: "bottom", highlight_padding: 8, scroll_to: true, wait_for_element: true, wait_timeout: 5000 },
      });
      await selectWalkthrough(selected.walkthrough_id);
      setEditingStep(res.data.step_id);
      toast.success("Step added");
    } catch (err) { handleError(err, "WalkthroughBuilder:op5"); }
  };

  const updateStep = async (stepId, updates) => {
    if (!selected) return;
    try {
      await api.put(`/walkthroughs/${selected.walkthrough_id}/steps/${stepId}`, updates);
      await selectWalkthrough(selected.walkthrough_id);
    } catch (err) { handleError(err, "WalkthroughBuilder:op6"); }
  };

  const deleteStep = async (stepId) => {
    if (!selected) return;
    try { await api.delete(`/walkthroughs/${selected.walkthrough_id}/steps/${stepId}`); setEditingStep(null); await selectWalkthrough(selected.walkthrough_id); toast.success("Step deleted"); }
    catch (err) { handleError(err, "WalkthroughBuilder:op7"); }
  };

  const moveStep = async (index, direction) => {
    if (!selected) return;
    const steps = [...(selected.steps || [])];
    const newIdx = index + direction;
    if (newIdx < 0 || newIdx >= steps.length) return;
    [steps[index], steps[newIdx]] = [steps[newIdx], steps[index]];
    try {
      await api.put(`/walkthroughs/${selected.walkthrough_id}/steps/reorder`, { step_ids: steps.map(s => s.step_id) });
      await selectWalkthrough(selected.walkthrough_id);
    } catch (err) { handleSilent(err, "WalkthroughBuilder:op1"); }
  };

  const updateConfig = async (updates) => {
    if (!selected) return;
    try { const res = await api.put(`/walkthroughs/${selected.walkthrough_id}`, updates); setSelected(res.data); }
    catch (err) { handleError(err, "WalkthroughBuilder:op8"); }
  };

  const currentStep = selected?.steps?.find(s => s.step_id === editingStep);

  if (loading) return <div className="flex-1 flex items-center justify-center p-8"><div className="w-6 h-6 border-2 border-zinc-700 border-t-emerald-400 rounded-full animate-spin" /></div>;

  return (
    <div className="flex-1 flex h-full" data-testid="walkthrough-builder">
      {/* Left: Walkthrough List */}
      <div className="w-64 flex-shrink-0 border-r border-zinc-800/40 flex flex-col bg-zinc-900/30">
        <div className="px-4 py-3 border-b border-zinc-800/40 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-zinc-200">Walkthroughs</h3>
          <button onClick={() => setCreateOpen(true)} className="p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200" data-testid="create-walkthrough-btn"><Plus className="w-4 h-4" /></button>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {walkthroughs.length === 0 && <p className="text-xs text-zinc-600 text-center py-8">No walkthroughs yet</p>}
          {walkthroughs.map(wt => (
            <button key={wt.walkthrough_id} onClick={() => selectWalkthrough(wt.walkthrough_id)}
              className={`w-full text-left p-3 rounded-lg transition-colors ${selected?.walkthrough_id === wt.walkthrough_id ? "bg-zinc-800 border border-zinc-700" : "hover:bg-zinc-800/50 border border-transparent"}`}
              data-testid={`wt-item-${wt.walkthrough_id}`}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-zinc-200 truncate">{wt.name}</span>
                <Badge className={`text-[8px] ${STATUS_STYLES[wt.status]}`}>{wt.status}</Badge>
              </div>
              <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                <span>{wt.steps?.length || 0} steps</span>
                <span>{wt.category}</span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Main: Editor */}
      {selected ? (
        <div className="flex-1 flex flex-col min-w-0">
          {/* Toolbar */}
          <div className="px-5 py-2.5 border-b border-zinc-800/40 flex items-center justify-between bg-zinc-900/50">
            <div>
              <h2 className="text-base font-semibold text-zinc-100">{selected.name}</h2>
              <p className="text-[11px] text-zinc-500">{selected.steps?.length || 0} steps · v{selected.version} · {selected.status}</p>
            </div>
            <div className="flex items-center gap-2">
              {selected.status === "draft" && (
                <Button size="sm" onClick={publishWalkthrough} className="bg-emerald-500 hover:bg-emerald-400 text-white gap-1.5" data-testid="publish-walkthrough-btn"><Play className="w-3.5 h-3.5" /> Publish</Button>
              )}
              {selected.status === "published" && (
                <Button size="sm" variant="outline" onClick={archiveWalkthrough} className="border-zinc-700 text-zinc-400 gap-1.5"><Archive className="w-3.5 h-3.5" /> Archive</Button>
              )}
              <Button size="sm" variant="outline" onClick={deleteWalkthrough} className="border-zinc-700 text-red-400 hover:text-red-300"><Trash2 className="w-3.5 h-3.5" /></Button>
            </div>
          </div>

          {/* Config Tabs */}
          <div className="flex items-center border-b border-zinc-800/40 bg-zinc-900/30 px-2">
            {[
              { key: "steps", label: "Steps", icon: MessageSquare },
              { key: "trigger", label: "Trigger", icon: Globe },
              { key: "targeting", label: "Audience", icon: Users },
              { key: "theme", label: "Theme", icon: Palette },
              { key: "analytics", label: "Analytics", icon: BarChart3 },
            ].map(tab => (
              <button key={tab.key} onClick={() => setConfigTab(tab.key)}
                className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors border-b-2 ${configTab === tab.key ? "text-zinc-100 border-emerald-400" : "text-zinc-500 hover:text-zinc-300 border-transparent"}`}
                data-testid={`wt-tab-${tab.key}`}>
                <tab.icon className="w-3.5 h-3.5" />{tab.label}
              </button>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto p-5">
            {/* Steps Tab */}
            {configTab === "steps" && (
              <div className="max-w-2xl space-y-3">
                {(selected.steps || []).map((step, idx) => {
                  const Icon = STEP_ICONS[step.type] || MessageSquare;
                  const colorClass = STEP_COLORS[step.type] || STEP_COLORS.tooltip;
                  const isEditing = editingStep === step.step_id;
                  return (
                    <div key={step.step_id} className={`rounded-xl border p-4 transition-all ${isEditing ? "border-emerald-500/40 bg-zinc-900/80" : "border-zinc-800/50 bg-zinc-900/40 hover:border-zinc-700"}`} data-testid={`step-card-${step.step_id}`}>
                      <div className="flex items-center gap-3">
                        <div className="flex flex-col gap-0.5">
                          <button onClick={() => moveStep(idx, -1)} disabled={idx === 0} className="p-0.5 text-zinc-600 hover:text-zinc-300 disabled:opacity-20"><ArrowUp className="w-3 h-3" /></button>
                          <button onClick={() => moveStep(idx, 1)} disabled={idx === (selected.steps?.length || 0) - 1} className="p-0.5 text-zinc-600 hover:text-zinc-300 disabled:opacity-20"><ArrowDown className="w-3 h-3" /></button>
                        </div>
                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${colorClass}`}><Icon className="w-4 h-4" /></div>
                        <div className="flex-1 min-w-0">
                          <span className="text-sm font-medium text-zinc-200">{step.content?.title || `Step ${idx + 1}`}</span>
                          <div className="flex items-center gap-2 text-[10px] text-zinc-500"><Badge className={`text-[8px] ${colorClass} border-0`}>{step.type}</Badge><span>{step.behavior?.advance_on}</span></div>
                        </div>
                        <div className="flex items-center gap-1">
                          <button onClick={() => setEditingStep(isEditing ? null : step.step_id)} className={`p-1.5 rounded-md ${isEditing ? "bg-emerald-500/20 text-emerald-400" : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"}`} data-testid={`edit-step-${step.step_id}`}><Pencil className="w-3.5 h-3.5" /></button>
                          <button onClick={() => deleteStep(step.step_id)} className="p-1.5 rounded-md text-zinc-600 hover:text-red-400 hover:bg-zinc-800"><Trash2 className="w-3.5 h-3.5" /></button>
                        </div>
                      </div>

                      {/* Inline Step Editor */}
                      {isEditing && currentStep && (
                        <div className="mt-4 pt-4 border-t border-zinc-800/40 space-y-4">
                          <div className="grid grid-cols-2 gap-3">
                            <div><label className="text-[10px] text-zinc-500 mb-1 block">Type</label>
                              <select value={currentStep.type} onChange={(e) => updateStep(step.step_id, { type: e.target.value })} className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-2 py-1.5 text-xs text-zinc-200" data-testid="step-type-select">
                                {config?.step_types?.map(t => <option key={t} value={t}>{t}</option>)}
                              </select>
                            </div>
                            <div><label className="text-[10px] text-zinc-500 mb-1 block">Placement</label>
                              <select value={currentStep.behavior?.placement || "bottom"} onChange={(e) => updateStep(step.step_id, { behavior: { ...currentStep.behavior, placement: e.target.value } })} className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-2 py-1.5 text-xs text-zinc-200">
                                {config?.placements?.map(p => <option key={p} value={p}>{p}</option>)}
                              </select>
                            </div>
                          </div>
                          <div><label className="text-[10px] text-zinc-500 mb-1 block">Title</label>
                            <Input value={currentStep.content?.title || ""} onChange={(e) => updateStep(step.step_id, { content: { ...currentStep.content, title: e.target.value } })} className="bg-zinc-800 border-zinc-700 text-sm text-zinc-200" data-testid="step-title-input" />
                          </div>
                          <div><label className="text-[10px] text-zinc-500 mb-1 block">Body</label>
                            <textarea value={currentStep.content?.body || ""} onChange={(e) => updateStep(step.step_id, { content: { ...currentStep.content, body: e.target.value } })} className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-xs text-zinc-200 min-h-[80px] resize-y" data-testid="step-body-input" />
                          </div>
                          <div className="grid grid-cols-2 gap-3">
                            <div><label className="text-[10px] text-zinc-500 mb-1 block">CTA Label</label>
                              <Input value={currentStep.content?.cta_label || "Next"} onChange={(e) => updateStep(step.step_id, { content: { ...currentStep.content, cta_label: e.target.value } })} className="bg-zinc-800 border-zinc-700 text-xs text-zinc-200" />
                            </div>
                            <div><label className="text-[10px] text-zinc-500 mb-1 block">Advance On</label>
                              <select value={currentStep.behavior?.advance_on || "click_cta"} onChange={(e) => updateStep(step.step_id, { behavior: { ...currentStep.behavior, advance_on: e.target.value } })} className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-2 py-1.5 text-xs text-zinc-200">
                                {config?.advance_conditions?.map(c => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}
                              </select>
                            </div>
                          </div>
                          <div><label className="text-[10px] text-zinc-500 mb-1 block">Target Selector (data-testid or CSS)</label>
                            <Input value={currentStep.selector?.primary || currentStep.selector?.css || ""} onChange={(e) => updateStep(step.step_id, { selector: { ...currentStep.selector, primary: e.target.value, css: e.target.value, resilience: e.target.value ? "high" : "low" } })} className="bg-zinc-800 border-zinc-700 text-xs text-zinc-200 font-mono" placeholder="data-testid='login-btn' or .my-button" data-testid="step-selector-input" />
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}

                {/* Add Step */}
                <div className="flex items-center gap-2">
                  {(config?.step_types || ["tooltip", "modal", "spotlight", "action"]).map(type => {
                    const Icon = STEP_ICONS[type] || MessageSquare;
                    return (
                      <button key={type} onClick={() => addStep(type)} className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-dashed border-zinc-800 text-xs text-zinc-500 hover:text-zinc-300 hover:border-zinc-600 transition-colors" data-testid={`add-step-${type}`}>
                        <Plus className="w-3 h-3" /><Icon className="w-3.5 h-3.5" /> {type}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Trigger Tab */}
            {configTab === "trigger" && (
              <div className="max-w-md space-y-4">
                <div><label className="text-xs text-zinc-400 mb-1.5 block">Trigger Type</label>
                  <select value={selected.trigger?.type || "page_load"} onChange={(e) => updateConfig({ trigger_type: e.target.value })} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200" data-testid="trigger-type-select">
                    {config?.trigger_types?.map(t => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
                  </select>
                </div>
                <div><label className="text-xs text-zinc-400 mb-1.5 block">URL Pattern (glob)</label>
                  <Input value={selected.trigger?.url_pattern || ""} onChange={(e) => updateConfig({ trigger_url_pattern: e.target.value })} placeholder="/dashboard/** or /workspace/*" className="bg-zinc-800 border-zinc-700 text-zinc-200 font-mono" data-testid="trigger-url-input" />
                </div>
                <div><label className="text-xs text-zinc-400 mb-1.5 block">Frequency</label>
                  <select value={selected.frequency?.rule || "once"} onChange={(e) => updateConfig({ frequency_rule: e.target.value })} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200" data-testid="frequency-select">
                    {config?.frequency_rules?.map(r => <option key={r} value={r}>{r.replace(/_/g, " ")}</option>)}
                  </select>
                </div>
              </div>
            )}

            {/* Targeting Tab */}
            {configTab === "targeting" && (
              <div className="max-w-md space-y-4">
                <p className="text-sm text-zinc-400">Define who sees this walkthrough based on user properties.</p>
                {(selected.targeting?.audiences || []).map((rule, i) => (
                  <div key={i} className="flex items-center gap-2 p-3 rounded-lg bg-zinc-800/40 border border-zinc-800/40">
                    <Input value={rule.field || ""} placeholder="user.role" className="bg-zinc-800 border-zinc-700 text-xs flex-1" readOnly />
                    <span className="text-xs text-zinc-500">{rule.operator}</span>
                    <Input value={Array.isArray(rule.value) ? rule.value.join(",") : rule.value || ""} className="bg-zinc-800 border-zinc-700 text-xs flex-1" readOnly />
                  </div>
                ))}
                <p className="text-[10px] text-zinc-600">Audience targeting coming in Phase 2. Currently shows to all users.</p>
              </div>
            )}

            {/* Theme Tab */}
            {configTab === "theme" && (
              <div className="max-w-md space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div><label className="text-xs text-zinc-400 mb-1.5 block">Primary Color</label>
                    <div className="flex items-center gap-2"><input type="color" value={selected.theme?.primary_color || "#10B981"} onChange={(e) => updateConfig({ theme: { ...selected.theme, primary_color: e.target.value } })} className="w-8 h-8 rounded cursor-pointer" /><span className="text-xs text-zinc-400 font-mono">{selected.theme?.primary_color}</span></div>
                  </div>
                  <div><label className="text-xs text-zinc-400 mb-1.5 block">Background</label>
                    <div className="flex items-center gap-2"><input type="color" value={selected.theme?.background_color || "#18181b"} onChange={(e) => updateConfig({ theme: { ...selected.theme, background_color: e.target.value } })} className="w-8 h-8 rounded cursor-pointer" /><span className="text-xs text-zinc-400 font-mono">{selected.theme?.background_color}</span></div>
                  </div>
                </div>
                <div><label className="text-xs text-zinc-400 mb-1.5 block">Border Radius (px)</label>
                  <input type="range" min={0} max={24} value={selected.theme?.border_radius || 12} onChange={(e) => updateConfig({ theme: { ...selected.theme, border_radius: parseInt(e.target.value) } })} className="w-full" />
                  <span className="text-xs text-zinc-500">{selected.theme?.border_radius || 12}px</span>
                </div>
                <div><label className="text-xs text-zinc-400 mb-1.5 block">Overlay Blur (px)</label>
                  <input type="range" min={0} max={20} value={selected.theme?.overlay_blur || 4} onChange={(e) => updateConfig({ theme: { ...selected.theme, overlay_blur: parseInt(e.target.value) } })} className="w-full" />
                  <span className="text-xs text-zinc-500">{selected.theme?.overlay_blur || 4}px</span>
                </div>
              </div>
            )}

            {/* Analytics Tab */}
            {configTab === "analytics" && <WalkthroughAnalytics walkthroughId={selected.walkthrough_id} />}
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center max-w-sm">
            <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mx-auto mb-4"><MousePointer className="w-6 h-6 text-emerald-400" /></div>
            <h3 className="text-lg font-semibold text-zinc-300 mb-2" style={{ fontFamily: 'Syne, sans-serif' }}>Walkthrough Builder</h3>
            <p className="text-sm text-zinc-500 mb-4">Create guided product tours for your users. Add steps, configure triggers, and publish.</p>
            <Button onClick={() => setCreateOpen(true)} className="bg-emerald-500 hover:bg-emerald-400 text-white gap-2" data-testid="empty-create-walkthrough"><Plus className="w-4 h-4" /> Create Walkthrough</Button>
          </div>
        </div>
      )}

      {/* Create Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-md">
          <DialogHeader><DialogTitle className="text-zinc-100">Create Walkthrough</DialogTitle></DialogHeader>
          <div className="space-y-3 mt-2">
            <Input placeholder="Walkthrough name" value={newName} onChange={(e) => setNewName(e.target.value)} className="bg-zinc-800 border-zinc-700 text-zinc-200" data-testid="wt-name-input" />
            <Input placeholder="Description (optional)" value={newDesc} onChange={(e) => setNewDesc(e.target.value)} className="bg-zinc-800 border-zinc-700 text-zinc-200" />
            <select value={newCategory} onChange={(e) => setNewCategory(e.target.value)} className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200" data-testid="wt-category-select">
              {(config?.categories || ["onboarding", "feature", "setup"]).map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            <Button onClick={createWalkthrough} disabled={!newName.trim()} className="w-full bg-emerald-500 hover:bg-emerald-400 text-white" data-testid="wt-create-submit">Create</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function WalkthroughAnalytics({ walkthroughId }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    api.get(`/walkthroughs/${walkthroughId}/analytics`).then(r => setData(r.data)).catch(() => {});
  }, [walkthroughId]);
  if (!data) return <div className="text-sm text-zinc-500">Loading analytics...</div>;
  const s = data.summary;
  return (
    <div className="space-y-4 max-w-lg" data-testid="wt-analytics">
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: "Starts", value: s.total_starts, color: "text-blue-400" },
          { label: "Completions", value: s.total_completions, color: "text-emerald-400" },
          { label: "Dismissed", value: s.total_dismissed, color: "text-amber-400" },
          { label: "Completion Rate", value: `${(s.completion_rate * 100).toFixed(0)}%`, color: "text-zinc-200" },
        ].map(m => (
          <div key={m.label} className="p-3 rounded-lg bg-zinc-800/40 border border-zinc-800/30 text-center">
            <p className={`text-lg font-bold ${m.color}`}>{m.value}</p>
            <p className="text-[10px] text-zinc-500">{m.label}</p>
          </div>
        ))}
      </div>
      {data.funnel?.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-zinc-400 mb-2">Step Funnel</h4>
          <div className="space-y-1">
            {data.funnel.map(f => (
              <div key={f.step_id} className="flex items-center gap-3 text-xs text-zinc-400 py-1.5 border-b border-zinc-800/30">
                <span className="w-6 text-zinc-500 font-mono">{f.step_order + 1}.</span>
                <span className="flex-1 text-zinc-300">{f.title || `Step ${f.step_order + 1}`}</span>
                <span>{f.viewed} viewed</span>
                <span>{f.completed} completed</span>
                <span className="text-red-400">{(f.drop_off_rate * 100).toFixed(0)}% drop</span>
              </div>
            ))}
          </div>
        </div>
      )}
    <ConfirmDlg />
    </div>
    );
}
