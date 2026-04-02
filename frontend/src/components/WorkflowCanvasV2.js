import { useState, useCallback, useRef, useEffect } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Plus, Play, Trash2, Zap, Settings, ArrowRight, Save, Loader2, GripVertical } from "lucide-react";
import { api } from "@/App";
import { toast } from "sonner";

const NODE_TYPES = {
  agent: { label: "AI Agent", color: "#06b6d4", icon: "A" },
  condition: { label: "Condition", color: "#f59e0b", icon: "?" },
  transform: { label: "Transform", color: "#8b5cf6", icon: "T" },
  output: { label: "Output", color: "#10b981", icon: "O" },
  input: { label: "Input", color: "#3b82f6", icon: "I" },
  human: { label: "Human Check", color: "#ef4444", icon: "H" },
};

const AGENT_OPTIONS = [
  { key: "chatgpt", name: "ChatGPT" },
  { key: "claude", name: "Claude" },
  { key: "gemini", name: "Gemini" },
  { key: "deepseek", name: "DeepSeek" },
  { key: "grok", name: "Grok" },
  { key: "mistral", name: "Mistral" },
  { key: "manus", name: "Manus" },
];

export default function WorkflowCanvasV2({ workflowId, workspaceId, nodes: initialNodes, edges: initialEdges, onSave }) {
  const [nodes, setNodes] = useState(initialNodes || []);
  const [edges, setEdges] = useState(initialEdges || []);
  const [selectedNode, setSelectedNode] = useState(null);
  const [addNodeOpen, setAddNodeOpen] = useState(false);
  const [configOpen, setConfigOpen] = useState(false);
  const [dragging, setDragging] = useState(null);
  const [saving, setSaving] = useState(false);
  const canvasRef = useRef(null);
  const [canvasOffset, setCanvasOffset] = useState({ x: 0, y: 0 });
  const [connecting, setConnecting] = useState(null);

  const addNode = (type) => {
    const id = `node_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    const newNode = {
      id, type, label: NODE_TYPES[type].label,
      x: 200 + Math.random() * 300, y: 100 + Math.random() * 200,
      config: type === "agent" ? { agent_key: "chatgpt", prompt: "" } : {},
    };
    setNodes(prev => [...prev, newNode]);
    setAddNodeOpen(false);
    setSelectedNode(newNode);
    setConfigOpen(true);
  };

  const removeNode = (nodeId) => {
    setNodes(prev => prev.filter(n => n.id !== nodeId));
    setEdges(prev => prev.filter(e => e.source !== nodeId && e.target !== nodeId));
    if (selectedNode?.id === nodeId) { setSelectedNode(null); setConfigOpen(false); }
  };

  const updateNodeConfig = (nodeId, config) => {
    setNodes(prev => prev.map(n => n.id === nodeId ? { ...n, config: { ...n.config, ...config }, label: config.label || n.label } : n));
  };

  const addEdge = (sourceId, targetId) => {
    if (sourceId === targetId) return;
    if (edges.some(e => e.source === sourceId && e.target === targetId)) return;
    setEdges(prev => [...prev, { id: `edge_${Date.now()}`, source: sourceId, target: targetId }]);
  };

  const removeEdge = (edgeId) => { setEdges(prev => prev.filter(e => e.id !== edgeId)); };

  const handleMouseDown = (e, nodeId) => {
    if (e.shiftKey) { setConnecting(nodeId); return; }
    const rect = canvasRef.current.getBoundingClientRect();
    const node = nodes.find(n => n.id === nodeId);
    setDragging({ nodeId, offsetX: e.clientX - rect.left - node.x, offsetY: e.clientY - rect.top - node.y });
  };

  const handleMouseMove = useCallback((e) => {
    if (!dragging || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    setNodes(prev => prev.map(n => n.id === dragging.nodeId ? { ...n, x: Math.max(0, e.clientX - rect.left - dragging.offsetX), y: Math.max(0, e.clientY - rect.top - dragging.offsetY) } : n));
  }, [dragging]);

  const handleMouseUp = useCallback((e, nodeId) => {
    if (connecting && nodeId && connecting !== nodeId) addEdge(connecting, nodeId);
    setDragging(null); setConnecting(null);
  }, [connecting, edges]);

  useEffect(() => {
    const up = () => { setDragging(null); setConnecting(null); };
    window.addEventListener('mouseup', up);
    return () => window.removeEventListener('mouseup', up);
  }, []);

  const saveWorkflow = async () => {
    setSaving(true);
    try {
      if (onSave) await onSave({ nodes, edges });
      else if (workflowId) await api.put(`/workflows/${workflowId}`, { nodes, edges });
      toast.success("Workflow saved");
    } catch (err) { handleError(err, "WorkflowCanvasV2:op1"); }
    setSaving(false);
  };

  return (
    <div className="flex-1 flex flex-col min-h-0" data-testid="workflow-canvas-v2">
      <div className="px-4 py-2 border-b border-zinc-800/40 flex items-center gap-2">
        <Button size="sm" onClick={() => setAddNodeOpen(true)} className="h-7 text-xs bg-cyan-500 hover:bg-cyan-400 text-white gap-1"><Plus className="w-3 h-3" /> Add Node</Button>
        <Button size="sm" onClick={saveWorkflow} disabled={saving} className="h-7 text-xs bg-zinc-800 text-zinc-300 gap-1">{saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />} Save</Button>
        <span className="text-[10px] text-zinc-600 ml-2">{nodes.length} nodes, {edges.length} edges | Shift+click to connect | Double-click to configure</span>
      </div>

      <div ref={canvasRef} className="flex-1 relative overflow-auto bg-zinc-950/50"
        onMouseMove={(e) => { handleMouseMove(e); if (connecting && canvasRef.current) { const r = canvasRef.current.getBoundingClientRect(); setCanvasOffset({ x: e.clientX - r.left, y: e.clientY - r.top }); } }}
        style={{ backgroundImage: "radial-gradient(circle, #27272a 1px, transparent 1px)", backgroundSize: "20px 20px" }}>
        
        <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ zIndex: 0 }}>
          <defs><marker id="ah" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#52525b" /></marker></defs>
          {edges.map(edge => {
            const s = nodes.find(n => n.id === edge.source), t = nodes.find(n => n.id === edge.target);
            if (!s || !t) return null;
            return <line key={edge.id} x1={s.x+80} y1={s.y+30} x2={t.x+80} y2={t.y+30} stroke="#52525b" strokeWidth={2} markerEnd="url(#ah)" className="pointer-events-auto cursor-pointer hover:stroke-red-400" onClick={() => removeEdge(edge.id)} />;
          })}
        </svg>

        {nodes.map(node => {
          const nt = NODE_TYPES[node.type] || NODE_TYPES.agent;
          return (
            <div key={node.id} className={`absolute w-40 rounded-lg border-2 cursor-move select-none ${selectedNode?.id === node.id ? "border-cyan-400 shadow-lg shadow-cyan-500/20" : "border-zinc-700 hover:border-zinc-600"}`}
              style={{ left: node.x, top: node.y, zIndex: dragging?.nodeId === node.id ? 10 : 1 }}
              onMouseDown={(e) => handleMouseDown(e, node.id)} onMouseUp={(e) => handleMouseUp(e, node.id)}
              onClick={(e) => { if (!e.shiftKey) setSelectedNode(node); }} onDoubleClick={() => { setSelectedNode(node); setConfigOpen(true); }}>
              <div className="px-3 py-2 rounded-t-lg text-xs font-medium flex items-center gap-2" style={{ backgroundColor: nt.color + "20", color: nt.color }}>
                <span className="w-5 h-5 rounded flex items-center justify-center text-[10px] font-bold" style={{ backgroundColor: nt.color + "30" }}>{nt.icon}</span>
                <span className="truncate flex-1">{node.label}</span>
                <button onClick={(e) => { e.stopPropagation(); removeNode(node.id); }} className="text-zinc-600 hover:text-red-400"><Trash2 className="w-3 h-3" /></button>
              </div>
              <div className="px-3 py-1.5 bg-zinc-900 rounded-b-lg">
                <p className="text-[9px] text-zinc-500 truncate">{node.type === "agent" ? (node.config?.agent_key || "chatgpt") : node.type}</p>
              </div>
            </div>
          );
        })}

        {nodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center"><Zap className="w-10 h-10 text-zinc-800 mx-auto mb-3" /><p className="text-sm text-zinc-500">Click "Add Node" to start</p><p className="text-xs text-zinc-600 mt-1">Shift+click to connect | Double-click to configure</p></div>
          </div>
        )}
      </div>

      <Dialog open={addNodeOpen} onOpenChange={setAddNodeOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-sm">
          <DialogHeader><DialogTitle className="text-zinc-100">Add Node</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-2 mt-2">
            {Object.entries(NODE_TYPES).map(([type, info]) => (
              <button key={type} onClick={() => addNode(type)} className="p-3 rounded-lg border border-zinc-800 hover:border-zinc-600 bg-zinc-900/50 text-left">
                <span className="w-6 h-6 rounded flex items-center justify-center text-xs font-bold mb-1" style={{ backgroundColor: info.color + "20", color: info.color }}>{info.icon}</span>
                <span className="text-xs text-zinc-300 block">{info.label}</span>
              </button>
            ))}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={configOpen} onOpenChange={setConfigOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-md">
          <DialogHeader><DialogTitle className="text-zinc-100">Configure: {selectedNode?.label}</DialogTitle></DialogHeader>
          {selectedNode && (
            <div className="space-y-3 mt-2">
              <Input value={selectedNode.label} onChange={e => updateNodeConfig(selectedNode.id, { label: e.target.value })} placeholder="Node label" className="bg-zinc-950 border-zinc-800" />
              {selectedNode.type === "agent" && (
                <>
                  <select value={selectedNode.config?.agent_key || "chatgpt"} onChange={e => updateNodeConfig(selectedNode.id, { agent_key: e.target.value })} className="w-full bg-zinc-950 border border-zinc-800 rounded-md px-3 py-2 text-sm text-zinc-200">
                    {AGENT_OPTIONS.map(a => <option key={a.key} value={a.key}>{a.name}</option>)}
                  </select>
                  <textarea value={selectedNode.config?.prompt || ""} onChange={e => updateNodeConfig(selectedNode.id, { prompt: e.target.value })} placeholder="System prompt..." className="w-full bg-zinc-950 border border-zinc-800 rounded-md px-3 py-2 text-sm text-zinc-200 min-h-[80px]" />
                </>
              )}
              {selectedNode.type === "condition" && <textarea value={selectedNode.config?.expression || ""} onChange={e => updateNodeConfig(selectedNode.id, { expression: e.target.value })} placeholder="Condition expression..." className="w-full bg-zinc-950 border border-zinc-800 rounded-md px-3 py-2 text-sm text-zinc-200 min-h-[60px]" />}
              {selectedNode.type === "transform" && <textarea value={selectedNode.config?.transform || ""} onChange={e => updateNodeConfig(selectedNode.id, { transform: e.target.value })} placeholder="Transform template..." className="w-full bg-zinc-950 border border-zinc-800 rounded-md px-3 py-2 text-sm text-zinc-200 min-h-[60px]" />}
              <Button onClick={() => setConfigOpen(false)} className="w-full bg-cyan-500 hover:bg-cyan-400 text-white">Done</Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
