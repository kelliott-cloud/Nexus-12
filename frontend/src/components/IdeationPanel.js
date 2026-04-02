import React, { useState, useEffect, useCallback, useRef } from "react";
import { useConfirm } from "@/components/ConfirmDialog";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { api } from "@/App";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { toast } from "sonner";
import {
  Lightbulb, Plus, ArrowLeft, Pencil, Trash2, Send, Copy,
  Target, Users, Tag, ChevronRight, FileText, Layers, Zap,
  CheckSquare, Star, Layout, ExternalLink,
} from "lucide-react";

const STATUS_CONFIG = {
  concept: { label: "Concept", color: "bg-zinc-600" },
  exploring: { label: "Exploring", color: "bg-blue-500" },
  "spec-ready": { label: "Spec Ready", color: "bg-amber-500" },
  building: { label: "Building", color: "bg-emerald-500" },
  done: { label: "Done", color: "bg-purple-500" },
};

export default function IdeationPanel({ workspaceId, channels }) {
  const { confirm: confirmAction, ConfirmDialog: ConfirmDlg } = useConfirm();
  const [ideas, setIdeas] = useState([]);
  const [selectedIdea, setSelectedIdea] = useState(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [templates, setTemplates] = useState([]);
  const [view, setView] = useState("list"); // list, detail, brief

  const fetchIdeas = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/ideas`);
      setIdeas(res.data?.ideas || []);
    } catch (err) { handleSilent(err, "IdeationPanel:op1"); }
    setLoading(false);
  }, [workspaceId]);

  useEffect(() => { fetchIdeas(); }, [fetchIdeas]);

  const createIdea = async () => {
    if (!newTitle.trim()) return;
    try {
      const res = await api.post(`/workspaces/${workspaceId}/ideas`, { title: newTitle, status: "concept" });
      setIdeas([res.data, ...ideas]);
      setNewTitle("");
      setCreating(false);
      setSelectedIdea(res.data);
      setView("detail");
      toast.success("Idea created!");
    } catch (err) { toast.error("Failed to create idea"); }
  };

  const deleteIdea = async (ideaId) => {
    const _ok = await confirmAction("Delete Idea", "Delete this idea and all specs? Cannot be undone."); if (!_ok) return;
    await api.delete(`/ideas/${ideaId}`);
    setIdeas(ideas.filter(i => i.idea_id !== ideaId));
    if (selectedIdea?.idea_id === ideaId) { setSelectedIdea(null); setView("list"); }
    toast.success("Deleted");
  };

  if (view === "detail" && selectedIdea) {
    return <IdeaDetail idea={selectedIdea} onBack={() => { setView("list"); fetchIdeas(); }} channels={channels} />;
  }

  return (
    <div className="flex flex-col h-full" data-testid="ideation-panel">
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800/40">
        <div className="flex items-center gap-2">
          <Lightbulb className="w-5 h-5 text-amber-400" />
          <h2 className="text-sm font-semibold text-zinc-200">Ideation</h2>
          <Badge className="bg-zinc-800 text-zinc-500 text-[9px]">{ideas.length}</Badge>
        </div>
        <Button size="sm" onClick={() => setCreating(true)} className="bg-amber-500 hover:bg-amber-400 text-white gap-1 h-7 text-xs" data-testid="new-idea-btn">
          <Plus className="w-3 h-3" /> New Idea
        </Button>
      </div>

      {creating && (
        <div className="px-4 py-3 border-b border-zinc-800/30 flex gap-2">
          <Input value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="What do you want to build?" className="h-8 text-sm bg-zinc-900 border-zinc-800" autoFocus onKeyDown={(e) => e.key === "Enter" && createIdea()} data-testid="idea-title-input" />
          <Button size="sm" onClick={createIdea} className="h-8 bg-amber-500 text-white text-xs">Create</Button>
          <Button size="sm" variant="ghost" onClick={() => setCreating(false)} className="h-8 text-zinc-500 text-xs">Cancel</Button>
        </div>
      )}

      <ScrollArea className="flex-1">
        {loading ? (
          <div className="text-center py-12 text-zinc-600 text-sm">Loading ideas...</div>
        ) : ideas.length === 0 ? (
          <div className="text-center py-16">
            <Lightbulb className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
            <p className="text-sm text-zinc-400">Start prototyping your next creation</p>
            <p className="text-xs text-zinc-600 mt-1">Create an idea, define features, sketch wireframes, then send to AI agents</p>
            <Button size="sm" onClick={() => setCreating(true)} className="mt-4 bg-amber-500 text-white text-xs">
              <Plus className="w-3 h-3 mr-1" /> Create First Idea
            </Button>
          </div>
        ) : (
          <div className="p-3 space-y-2">
            {ideas.map(idea => {
              const sc = STATUS_CONFIG[idea.status] || STATUS_CONFIG.concept;
              return (
                <div key={idea.idea_id} className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/50 hover:border-zinc-700 cursor-pointer transition-colors group"
                  onClick={() => { setSelectedIdea(idea); setView("detail"); }} data-testid={`idea-card-${idea.idea_id}`}>
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="text-sm font-medium text-zinc-200 truncate">{idea.title}</h3>
                        <div className={`w-2 h-2 rounded-full ${sc.color}`} title={sc.label} />
                      </div>
                      {idea.description && <p className="text-xs text-zinc-500 line-clamp-2 mb-2">{idea.description}</p>}
                      <div className="flex items-center gap-2 flex-wrap">
                        <Badge className="bg-zinc-800 text-zinc-500 text-[8px]">{sc.label}</Badge>
                        {idea.tags?.map(t => <Badge key={t} className="bg-zinc-800/50 text-zinc-600 text-[8px]">{t}</Badge>)}
                        {idea.goals?.length > 0 && <span className="text-[9px] text-zinc-600">{idea.goals.length} goals</span>}
                      </div>
                    </div>
                    <div className="flex gap-1 opacity-0 group-hover:opacity-100">
                      <button onClick={(e) => { e.stopPropagation(); deleteIdea(idea.idea_id); }} className="p-1 text-zinc-600 hover:text-red-400"><Trash2 className="w-3 h-3" /></button>
                      <ChevronRight className="w-4 h-4 text-zinc-600" />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}

function IdeaDetail({ idea: initialIdea, onBack, channels }) {
  const [idea, setIdea] = useState(initialIdea);
  const [specs, setSpecs] = useState([]);
  const [wireframes, setWireframes] = useState([]);
  const [brief, setBrief] = useState(null);
  const [editing, setEditing] = useState(false);
  const [editData, setEditData] = useState({});
  const [addingSpec, setAddingSpec] = useState(false);
  const [newSpec, setNewSpec] = useState({ title: "", features: [{ name: "", description: "", priority: "must", acceptance_criteria: [] }], user_stories: [], tech_requirements: [], constraints: [] });
  const [addingStory, setAddingStory] = useState(false);
  const [newStory, setNewStory] = useState({ as_a: "", i_want: "", so_that: "" });
  const [sendChannel, setSendChannel] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get(`/ideas/${idea.idea_id}`);
        setIdea(res.data);
        setSpecs(res.data.specs || []);
        setWireframes(res.data.wireframes || []);
      } catch (err) { handleSilent(err, "IdeationPanel:op2"); }
    })();
  }, [idea.idea_id]);

  const updateIdea = async (updates) => {
    const res = await api.put(`/ideas/${idea.idea_id}`, updates);
    setIdea(res.data);
    setEditing(false);
  };

  const addFeatureToSpec = () => {
    setNewSpec(s => ({ ...s, features: [...s.features, { name: "", description: "", priority: "must", acceptance_criteria: [] }] }));
  };

  const saveSpec = async () => {
    if (!newSpec.title.trim()) { toast.error("Spec title required"); return; }
    const res = await api.post(`/ideas/${idea.idea_id}/specs`, newSpec);
    setSpecs([...specs, res.data]);
    setAddingSpec(false);
    setNewSpec({ title: "", features: [{ name: "", description: "", priority: "must", acceptance_criteria: [] }], user_stories: [], tech_requirements: [], constraints: [] });
    toast.success("Spec added!");
  };

  const generateBrief = async () => {
    const res = await api.post(`/ideas/${idea.idea_id}/generate-brief`);
    setBrief(res.data.brief);
  };

  const sendToChannel = async () => {
    if (!sendChannel) { toast.error("Select a channel"); return; }
    await api.post(`/ideas/${idea.idea_id}/send-to-channel`, { channel_id: sendChannel });
    toast.success("Brief sent to channel! AI agents can now work on it.");
  };

  const sc = STATUS_CONFIG[idea.status] || STATUS_CONFIG.concept;

  return (
    <div className="flex flex-col h-full" data-testid="idea-detail">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-zinc-800/40">
        <button onClick={onBack} className="p-1 text-zinc-500 hover:text-zinc-300"><ArrowLeft className="w-4 h-4" /></button>
        <Lightbulb className="w-4 h-4 text-amber-400" />
        <h2 className="text-sm font-semibold text-zinc-200 truncate flex-1">{idea.title}</h2>
        <div className={`px-2 py-0.5 rounded-full text-[9px] text-white ${sc.color}`}>{sc.label}</div>
        <select value={idea.status} onChange={(e) => updateIdea({ status: e.target.value })} className="bg-zinc-900 border border-zinc-800 rounded text-[10px] text-zinc-400 px-2 py-0.5">
          {Object.entries(STATUS_CONFIG).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-4 space-y-6">
          {/* Description + Goals */}
          <div className="space-y-3">
            <div>
              <label className="text-[10px] text-zinc-600 uppercase tracking-wider">Description</label>
              <textarea value={idea.description || ""} onChange={(e) => setIdea({ ...idea, description: e.target.value })}
                onBlur={() => updateIdea({ description: idea.description })}
                className="w-full mt-1 bg-zinc-900 border border-zinc-800 rounded-lg p-3 text-sm text-zinc-300 min-h-[60px]"
                placeholder="Describe your idea..." />
            </div>
            <div>
              <label className="text-[10px] text-zinc-600 uppercase tracking-wider">Target Audience</label>
              <Input value={idea.target_audience || ""} onChange={(e) => setIdea({ ...idea, target_audience: e.target.value })}
                onBlur={() => updateIdea({ target_audience: idea.target_audience })}
                className="mt-1 h-8 text-sm bg-zinc-900 border-zinc-800" placeholder="Who is this for?" />
            </div>
            <div>
              <label className="text-[10px] text-zinc-600 uppercase tracking-wider">Goals</label>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {(idea.goals || []).map((g, i) => (
                  <Badge key={i} className="bg-emerald-500/10 text-emerald-400 text-[10px] border border-emerald-500/20 gap-1">
                    <Target className="w-2.5 h-2.5" />{g}
                    <button onClick={() => { const goals = [...idea.goals]; goals.splice(i, 1); updateIdea({ goals }); }} className="ml-0.5 hover:text-red-400">×</button>
                  </Badge>
                ))}
                <Input className="h-6 w-32 text-[10px] bg-zinc-900 border-zinc-800" placeholder="+ Add goal"
                  onKeyDown={(e) => { if (e.key === "Enter" && e.target.value.trim()) { updateIdea({ goals: [...(idea.goals || []), e.target.value.trim()] }); e.target.value = ""; } }} />
              </div>
            </div>
          </div>

          {/* Feature Specs */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-semibold text-zinc-300 flex items-center gap-1.5"><CheckSquare className="w-3.5 h-3.5 text-blue-400" /> Feature Specs</h3>
              <Button size="sm" variant="ghost" onClick={() => setAddingSpec(true)} className="h-6 text-[10px] text-blue-400"><Plus className="w-3 h-3 mr-1" /> Add Spec</Button>
            </div>
            {specs.map(spec => (
              <div key={spec.spec_id} className="p-3 rounded-lg bg-zinc-900/50 border border-zinc-800/40 mb-2">
                <p className="text-xs font-medium text-zinc-300 mb-1">{spec.title}</p>
                {spec.user_stories?.map((s, i) => (
                  <p key={i} className="text-[10px] text-zinc-500 mb-0.5">As a <b className="text-zinc-400">{s.as_a}</b>, I want <b className="text-zinc-400">{s.i_want}</b>, so that <b className="text-zinc-400">{s.so_that}</b></p>
                ))}
                {spec.features?.map((f, i) => (
                  <div key={i} className="flex items-center gap-2 mt-1">
                    <Badge className={`text-[8px] ${f.priority === "must" ? "bg-red-500/15 text-red-400" : f.priority === "nice" ? "bg-amber-500/15 text-amber-400" : "bg-zinc-700 text-zinc-400"}`}>{f.priority}</Badge>
                    <span className="text-[10px] text-zinc-300">{f.name}</span>
                    {f.description && <span className="text-[10px] text-zinc-600">— {f.description}</span>}
                  </div>
                ))}
              </div>
            ))}

            {addingSpec && (
              <div className="p-3 rounded-lg bg-blue-500/5 border border-blue-500/20 space-y-2">
                <Input value={newSpec.title} onChange={(e) => setNewSpec({ ...newSpec, title: e.target.value })} placeholder="Spec title" className="h-7 text-xs bg-zinc-900 border-zinc-800" />
                <p className="text-[10px] text-zinc-500">Features:</p>
                {newSpec.features.map((f, i) => (
                  <div key={i} className="flex gap-2">
                    <select value={f.priority} onChange={(e) => { const fs = [...newSpec.features]; fs[i].priority = e.target.value; setNewSpec({ ...newSpec, features: fs }); }}
                      className="bg-zinc-900 border border-zinc-800 rounded text-[10px] px-1 w-16">{["must", "nice", "future"].map(p => <option key={p} value={p}>{p}</option>)}</select>
                    <Input value={f.name} onChange={(e) => { const fs = [...newSpec.features]; fs[i].name = e.target.value; setNewSpec({ ...newSpec, features: fs }); }} placeholder="Feature name" className="h-6 text-[10px] bg-zinc-900 border-zinc-800 flex-1" />
                    <Input value={f.description} onChange={(e) => { const fs = [...newSpec.features]; fs[i].description = e.target.value; setNewSpec({ ...newSpec, features: fs }); }} placeholder="Description" className="h-6 text-[10px] bg-zinc-900 border-zinc-800 flex-1" />
                  </div>
                ))}
                <div className="flex gap-2">
                  <Button size="sm" variant="ghost" onClick={addFeatureToSpec} className="h-6 text-[9px] text-zinc-500"><Plus className="w-2.5 h-2.5 mr-1" /> Feature</Button>
                  <div className="flex-1" />
                  <Button size="sm" variant="ghost" onClick={() => setAddingSpec(false)} className="h-6 text-[9px] text-zinc-500">Cancel</Button>
                  <Button size="sm" onClick={saveSpec} className="h-6 text-[9px] bg-blue-500 text-white">Save Spec</Button>
                </div>
              </div>
            )}
          </div>

          {/* Wireframes — Interactive Canvas */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-semibold text-zinc-300 flex items-center gap-1.5"><Layout className="w-3.5 h-3.5 text-purple-400" /> Wireframes</h3>
              <Button size="sm" variant="ghost" onClick={async () => {
                const res = await api.post(`/ideas/${idea.idea_id}/wireframes`, { name: `Screen ${wireframes.length + 1}`, screen_type: "page", components: [] });
                setWireframes([...wireframes, res.data]);
              }} className="h-6 text-[10px] text-purple-400"><Plus className="w-3 h-3 mr-1" /> Add Screen</Button>
            </div>
            {wireframes.map((wf, wfIdx) => (
              <WireframeCanvas key={wf.wireframe_id} wireframe={wf} onUpdate={async (updated) => {
                const res = await api.put(`/wireframes/${wf.wireframe_id}`, updated);
                const newWfs = [...wireframes]; newWfs[wfIdx] = res.data; setWireframes(newWfs);
              }} onDelete={async () => {
                await api.delete(`/wireframes/${wf.wireframe_id}`);
                setWireframes(wireframes.filter(w => w.wireframe_id !== wf.wireframe_id));
              }} />
            ))}
            {wireframes.length === 0 && (
              <div className="p-6 rounded-lg border border-dashed border-zinc-800 text-center">
                <Layout className="w-6 h-6 text-zinc-700 mx-auto mb-1" />
                <p className="text-[10px] text-zinc-600">Add screens to sketch your UI wireframes</p>
              </div>
            )}
          </div>

          {/* Generate Brief + Send to Channel */}
          <div className="p-4 rounded-xl bg-amber-500/5 border border-amber-500/20 space-y-3">
            <h3 className="text-xs font-semibold text-amber-400 flex items-center gap-1.5"><Zap className="w-3.5 h-3.5" /> Ready to Build?</h3>
            <div className="flex gap-2">
              <Button size="sm" onClick={generateBrief} className="bg-amber-500/20 text-amber-400 border border-amber-500/30 text-xs h-7 hover:bg-amber-500/30" data-testid="generate-brief-btn">
                <FileText className="w-3 h-3 mr-1" /> Generate Brief
              </Button>
              <select value={sendChannel} onChange={(e) => setSendChannel(e.target.value)} className="bg-zinc-900 border border-zinc-800 rounded text-[10px] text-zinc-400 px-2 flex-1">
                <option value="">Select channel...</option>
                {(channels || []).map(ch => <option key={ch.channel_id} value={ch.channel_id}>#{ch.name}</option>)}
              </select>
              <Button size="sm" onClick={sendToChannel} disabled={!sendChannel} className="bg-emerald-500 text-white text-xs h-7 hover:bg-emerald-400" data-testid="send-to-channel-btn">
                <Send className="w-3 h-3 mr-1" /> Send
              </Button>
            </div>
            {brief && (
              <pre className="mt-2 p-3 bg-zinc-900 rounded-lg text-[10px] text-zinc-400 whitespace-pre-wrap max-h-60 overflow-auto">{brief}</pre>
            )}
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}

const COMPONENT_TYPES = [
  { type: "header", label: "Header", w: 360, h: 40, color: "#3b82f6" },
  { type: "nav", label: "Nav Bar", w: 360, h: 32, color: "#8b5cf6" },
  { type: "button", label: "Button", w: 100, h: 32, color: "#22c55e" },
  { type: "input", label: "Input Field", w: 200, h: 32, color: "#f59e0b" },
  { type: "card", label: "Card", w: 180, h: 120, color: "#06b6d4" },
  { type: "list", label: "List", w: 200, h: 140, color: "#ec4899" },
  { type: "image", label: "Image", w: 160, h: 100, color: "#a855f7" },
  { type: "text", label: "Text Block", w: 200, h: 60, color: "#71717a" },
  { type: "table", label: "Table", w: 300, h: 120, color: "#14b8a6" },
  { type: "sidebar", label: "Sidebar", w: 80, h: 300, color: "#6366f1" },
  { type: "form", label: "Form", w: 240, h: 180, color: "#f97316" },
  { type: "modal", label: "Modal", w: 280, h: 200, color: "#ef4444" },
];

function WireframeCanvas({ wireframe, onUpdate, onDelete }) {
  const [components, setComponents] = useState(wireframe.components || []);
  const [dragging, setDragging] = useState(null);
  const [selected, setSelected] = useState(null);
  const [editingName, setEditingName] = useState(false);
  const [name, setName] = useState(wireframe.name);
  const canvasRef = useRef(null);

  const addComponent = (type) => {
    const tpl = COMPONENT_TYPES.find(t => t.type === type);
    const comp = { id: `c_${Date.now()}`, type, label: tpl.label, x: 20 + components.length * 10, y: 20 + components.length * 10, w: tpl.w, h: tpl.h };
    const updated = [...components, comp];
    setComponents(updated);
    onUpdate({ components: updated });
  };

  const handleMouseDown = (e, compId) => {
    e.stopPropagation();
    setSelected(compId);
    const comp = components.find(c => c.id === compId);
    if (!comp) return;
    const rect = canvasRef.current.getBoundingClientRect();
    setDragging({ id: compId, offsetX: e.clientX - rect.left - comp.x, offsetY: e.clientY - rect.top - comp.y });
  };

  const handleMouseMove = (e) => {
    if (!dragging) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = Math.max(0, e.clientX - rect.left - dragging.offsetX);
    const y = Math.max(0, e.clientY - rect.top - dragging.offsetY);
    setComponents(prev => prev.map(c => c.id === dragging.id ? { ...c, x, y } : c));
  };

  const handleMouseUp = () => {
    if (dragging) {
      onUpdate({ components });
      setDragging(null);
    }
  };

  const deleteComponent = (id) => {
    const updated = components.filter(c => c.id !== id);
    setComponents(updated);
    setSelected(null);
    onUpdate({ components: updated });
  };

  return (
    <div className="mb-4 rounded-xl border border-zinc-800/60 overflow-hidden" data-testid={`wireframe-${wireframe.wireframe_id}`}>
      {/* Wireframe header */}
      <div className="flex items-center gap-2 px-3 py-1.5 bg-zinc-900/70 border-b border-zinc-800/40">
        <Layout className="w-3.5 h-3.5 text-purple-400" />
        {editingName ? (
          <Input value={name} onChange={(e) => setName(e.target.value)} onBlur={() => { setEditingName(false); onUpdate({ name }); }}
            onKeyDown={(e) => { if (e.key === "Enter") { setEditingName(false); onUpdate({ name }); } }}
            className="h-5 text-[10px] bg-zinc-800 border-zinc-700 w-32" autoFocus />
        ) : (
          <span className="text-[11px] font-medium text-zinc-300 cursor-pointer" onClick={() => setEditingName(true)}>{name}</span>
        )}
        <Badge className="bg-zinc-800 text-zinc-600 text-[8px]">{wireframe.screen_type}</Badge>
        <span className="text-[9px] text-zinc-600">{components.length} components</span>
        <div className="flex-1" />
        <button onClick={onDelete} className="text-zinc-600 hover:text-red-400 p-0.5"><Trash2 className="w-3 h-3" /></button>
      </div>

      {/* Component palette */}
      <div className="flex items-center gap-1 px-2 py-1.5 bg-zinc-900/40 border-b border-zinc-800/30 overflow-x-auto">
        {COMPONENT_TYPES.map(t => (
          <button key={t.type} onClick={() => addComponent(t.type)}
            className="flex items-center gap-1 px-2 py-1 rounded text-[9px] text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 whitespace-nowrap flex-shrink-0 transition-colors"
            data-testid={`add-comp-${t.type}`}>
            <div className="w-2 h-2 rounded-sm" style={{ backgroundColor: t.color }} />
            {t.label}
          </button>
        ))}
      </div>

      {/* Canvas */}
      <div ref={canvasRef} className="relative bg-zinc-950 overflow-auto cursor-crosshair" style={{ height: 360 }}
        onMouseMove={handleMouseMove} onMouseUp={handleMouseUp} onMouseLeave={handleMouseUp}
        onClick={() => setSelected(null)}>
        {/* Grid */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ minWidth: 400, minHeight: 360 }}>
          <defs><pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M 20 0 L 0 0 0 20" fill="none" stroke="#27272a" strokeWidth="0.5" /></pattern></defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
        </svg>
        {/* Components */}
        {components.map(comp => {
          const tpl = COMPONENT_TYPES.find(t => t.type === comp.type);
          const isSelected = selected === comp.id;
          return (
            <div key={comp.id} className={`absolute rounded border cursor-move transition-shadow ${isSelected ? "ring-2 ring-purple-500 shadow-lg" : "hover:ring-1 hover:ring-zinc-600"}`}
              style={{ left: comp.x, top: comp.y, width: comp.w, height: comp.h, borderColor: tpl?.color || "#555", backgroundColor: (tpl?.color || "#555") + "15" }}
              onMouseDown={(e) => handleMouseDown(e, comp.id)}
              data-testid={`comp-${comp.id}`}>
              <div className="flex items-center justify-between px-1.5 py-0.5" style={{ backgroundColor: (tpl?.color || "#555") + "30" }}>
                <span className="text-[8px] font-medium" style={{ color: tpl?.color }}>{comp.label}</span>
                {isSelected && <button onClick={(e) => { e.stopPropagation(); deleteComponent(comp.id); }} className="text-red-400 hover:text-red-300"><Trash2 className="w-2.5 h-2.5" /></button>}
              </div>
              {comp.type === "button" && <div className="flex items-center justify-center h-full text-[9px] text-zinc-400">Click Me</div>}
              {comp.type === "input" && <div className="mx-1.5 mt-1 h-5 rounded bg-zinc-800/50 border border-zinc-700/50" />}
              {comp.type === "list" && [0,1,2,3].map(i => <div key={i} className="mx-1.5 mt-1 h-4 rounded bg-zinc-800/30 border border-zinc-700/30" />)}
              {comp.type === "table" && (
                <div className="p-1">{[0,1,2].map(i => <div key={i} className="flex gap-0.5 mb-0.5">{[0,1,2].map(j => <div key={j} className="flex-1 h-3 rounded-sm bg-zinc-800/40" />)}</div>)}</div>
              )}
              {comp.type === "image" && <div className="flex items-center justify-center h-full text-zinc-700"><Layers className="w-6 h-6" /></div>}
              {comp.type === "card" && <div className="p-1.5"><div className="h-8 rounded bg-zinc-800/30 mb-1" /><div className="h-3 rounded bg-zinc-800/20 w-3/4" /></div>}
            </div>
          );
        })}
        {components.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-zinc-700 text-xs">Click components above to add them to the canvas</div>
        )}
      </div>
    <ConfirmDlg />
    </div>
    );
}


