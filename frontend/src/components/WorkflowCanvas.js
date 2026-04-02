import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import * as RF from "reactflow";
import "reactflow/dist/style.css";
import { api } from "@/App";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { ArrowLeft, Save, Play, Pause, Trash2, Zap, Upload, Undo2, Redo2, Copy, Search, Filter, History, AlertTriangle } from "lucide-react";
import FlowNode, { NODE_COLORS } from "./FlowNode";
import NodeConfigPanel from "./NodeConfigPanel";
import RunMonitor from "./RunMonitor";

const { default: ReactFlow, addEdge, applyNodeChanges, applyEdgeChanges, Background, Controls, MiniMap, Panel, MarkerType } = RF;

const nodeTypes = { custom: FlowNode };

const defaultEdgeOptions = {
  type: "smoothstep",
  animated: true,
  markerEnd: { type: MarkerType.ArrowClosed, color: "#666" },
  style: { stroke: "#555", strokeWidth: 2, strokeDasharray: "none" },
};

export default function WorkflowCanvas({ workflow, onBack, onStatusChange, workspaceId }) {
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [dbNodes, setDbNodes] = useState([]);
  const [selectedNode, setSelectedNode] = useState(null);
  const [saving, setSaving] = useState(false);
  const [showRunMonitor, setShowRunMonitor] = useState(false);
  const [activeRunId, setActiveRunId] = useState(null);
  const [showInputDialog, setShowInputDialog] = useState(false);
  const [showPublish, setShowPublish] = useState(false);
  const [undoStack, setUndoStack] = useState([]);
  const [redoStack, setRedoStack] = useState([]);
  const [contextMenu, setContextMenu] = useState(null); // {x, y, nodeId?}
  const [validationIssues, setValidationIssues] = useState([]);
  const [showHistory, setShowHistory] = useState(false);
  const [runHistory, setRunHistory] = useState([]);
  const reactFlowWrapper = useRef(null);

  // Load workflow nodes and edges
  const loadCanvas = useCallback(async () => {
    try {
      const res = await api.get(`/workflows/${workflow.workflow_id}`);
      const wfData = res.data;
      const flowNodes = (wfData.nodes || []).map((n) => ({
        id: n.node_id,
        type: "custom",
        position: { x: n.position_x || 0, y: n.position_y || 0 },
        data: { ...n, nodeType: n.type, nodeId: n.node_id },
      }));
      const flowEdges = (wfData.edges || []).map((e) => ({
        id: e.edge_id,
        source: e.source_node_id,
        target: e.target_node_id,
        type: "smoothstep",
        animated: true,
        markerEnd: { type: MarkerType.ArrowClosed, color: "#666" },
        style: { stroke: "#555", strokeWidth: 2 },
        label: e.label || undefined,
        data: { edge_type: e.edge_type },
      }));
      setNodes(flowNodes);
      setEdges(flowEdges);
      setDbNodes(wfData.nodes || []);
    } catch (err) {
      console.error("Failed to load canvas:", err);
      toast.error("Failed to load workflow canvas");
    }
  }, [workflow.workflow_id]);

  useEffect(() => {
    loadCanvas();
  }, [loadCanvas]);

  const onNodesChange = useCallback(
    (changes) => setNodes((nds) => applyNodeChanges(changes, nds)),
    []
  );
  const onEdgesChange = useCallback(
    (changes) => setEdges((eds) => applyEdgeChanges(changes, eds)),
    []
  );
  const onConnect = useCallback(
    (params) => {
      const newEdge = {
        ...params,
        id: `we_${Date.now()}`,
        type: "smoothstep",
        animated: true,
        markerEnd: { type: MarkerType.ArrowClosed, color: "#666" },
        style: { stroke: "#555", strokeWidth: 2 },
      };
      setEdges((eds) => addEdge(newEdge, eds));
    },
    []
  );

  const onNodeClick = useCallback((_, node) => {
    setSelectedNode(node);
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  // Add node
  const addNode = useCallback(async (type) => {
    const label =
      type === "ai_agent" ? "AI Agent" :
      type === "human_review" ? "Human Review" :
      type === "condition" ? "Condition" :
      type === "merge" ? "Merge" :
      type === "input" ? "Input" :
      type === "trigger" ? "Trigger" :
      type === "output" ? "Output" : type.replace(/_/g, " ");
    try {
      const res = await api.post(`/workflows/${workflow.workflow_id}/nodes`, {
        type,
        label,
        position_x: 250 + Math.random() * 200,
        position_y: 100 + nodes.length * 120,
      });
      const n = res.data;
      setNodes((prev) => [
        ...prev,
        {
          id: n.node_id,
          type: "custom",
          position: { x: n.position_x, y: n.position_y },
          data: { ...n, nodeType: n.type, nodeId: n.node_id },
        },
      ]);
      setDbNodes((prev) => [...prev, n]);
      toast.success(`${label} node added`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to add node");
    }
  }, [workflow.workflow_id, nodes.length]);

  // Delete selected node
  const deleteSelectedNode = useCallback(async () => {
    if (!selectedNode) return;
    try {
      await api.delete(`/workflows/${workflow.workflow_id}/nodes/${selectedNode.id}`);
      setNodes((prev) => prev.filter((n) => n.id !== selectedNode.id));
      setEdges((prev) => prev.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id));
      setDbNodes((prev) => prev.filter((n) => n.node_id !== selectedNode.id));
      setSelectedNode(null);
      toast.success("Node deleted");
    } catch (err) {
      toast.error("Failed to delete node");
    }
  }, [selectedNode, workflow.workflow_id]);

  // Save canvas (positions + edges)
  const saveCanvas = useCallback(async () => {
    setSaving(true);
    try {
      const nodeData = nodes.map((n) => ({
        node_id: n.id,
        position_x: n.position.x,
        position_y: n.position.y,
      }));
      const edgeData = edges.map((e) => ({
        edge_id: e.id,
        source_node_id: e.source,
        target_node_id: e.target,
        edge_type: e.data?.edge_type || "default",
        label: e.label || null,
      }));
      await api.put(`/workflows/${workflow.workflow_id}/canvas`, {
        nodes: nodeData,
        edges: edgeData,
      });
      toast.success("Canvas saved");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to save canvas");
    } finally {
      setSaving(false);
    }
  }, [nodes, edges, workflow.workflow_id]);

  // Run workflow
  const runWorkflow = useCallback(async (inputData) => {
    try {
      // Save canvas first
      await saveCanvas();
      const res = await api.post(`/workflows/${workflow.workflow_id}/run`, {
        input: inputData || {},
      });
      setActiveRunId(res.data.run_id);
      setShowRunMonitor(true);
      toast.success("Workflow started");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to run workflow");
    }
  }, [workflow.workflow_id, saveCanvas]);

  // Update node config
  const updateNodeConfig = useCallback(async (nodeId, updates) => {
    try {
      const res = await api.put(`/workflows/${workflow.workflow_id}/nodes/${nodeId}`, updates);
      const updated = res.data;
      setNodes((prev) =>
        prev.map((n) =>
          n.id === nodeId
            ? { ...n, data: { ...updated, nodeType: updated.type, nodeId: updated.node_id } }
            : n
        )
      );
      setDbNodes((prev) => prev.map((n) => (n.node_id === nodeId ? updated : n)));
      toast.success("Node updated");
    } catch (err) {
      toast.error("Failed to update node");
    }
  }, [workflow.workflow_id]);

  // Input dialog for running workflows
  const inputSchema = useMemo(() => {
    const inputNode = dbNodes.find((n) => n.type === "input");
    return inputNode?.input_schema || {};
  }, [dbNodes]);

  // Undo/Redo
  const pushUndo = useCallback(() => {
    setUndoStack(prev => [...prev.slice(-20), { nodes: JSON.parse(JSON.stringify(nodes)), edges: JSON.parse(JSON.stringify(edges)) }]);
    setRedoStack([]);
  }, [nodes, edges]);

  const undo = useCallback(() => {
    if (undoStack.length === 0) return;
    const prev = undoStack[undoStack.length - 1];
    setRedoStack(r => [...r, { nodes: JSON.parse(JSON.stringify(nodes)), edges: JSON.parse(JSON.stringify(edges)) }]);
    setUndoStack(u => u.slice(0, -1));
    setNodes(prev.nodes);
    setEdges(prev.edges);
  }, [undoStack, nodes, edges]);

  const redo = useCallback(() => {
    if (redoStack.length === 0) return;
    const next = redoStack[redoStack.length - 1];
    setUndoStack(u => [...u, { nodes: JSON.parse(JSON.stringify(nodes)), edges: JSON.parse(JSON.stringify(edges)) }]);
    setRedoStack(r => r.slice(0, -1));
    setNodes(next.nodes);
    setEdges(next.edges);
  }, [redoStack, nodes, edges]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKey = (e) => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT") return;
      if ((e.ctrlKey || e.metaKey) && e.key === "z" && !e.shiftKey) { e.preventDefault(); undo(); }
      else if ((e.ctrlKey || e.metaKey) && e.key === "z" && e.shiftKey) { e.preventDefault(); redo(); }
      else if ((e.ctrlKey || e.metaKey) && e.key === "Z") { e.preventDefault(); redo(); }
      else if ((e.ctrlKey || e.metaKey) && e.key === "d") { e.preventDefault(); duplicateNode(); }
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [undo, redo]);

  // Duplicate selected node
  const duplicateNode = useCallback(async () => {
    if (!selectedNode) { toast.info("Select a node first"); return; }
    const original = dbNodes.find(n => n.node_id === selectedNode.id);
    if (!original) return;
    try {
      const res = await api.post(`/workflows/${workflow.workflow_id}/nodes`, {
        type: original.type,
        label: `${original.label} (copy)`,
        position_x: (selectedNode.position?.x || 0) + 50,
        position_y: (selectedNode.position?.y || 0) + 80,
        ai_model: original.ai_model,
        system_prompt: original.system_prompt,
        user_prompt_template: original.user_prompt_template,
        temperature: original.temperature,
        max_tokens: original.max_tokens,
        condition_logic: original.condition_logic,
        merge_strategy: original.merge_strategy,
      });
      const n = res.data;
      pushUndo();
      setNodes(prev => [...prev, { id: n.node_id, type: "custom", position: { x: n.position_x, y: n.position_y }, data: { ...n, nodeType: n.type, nodeId: n.node_id } }]);
      setDbNodes(prev => [...prev, n]);
      toast.success("Node duplicated");
    } catch (err) { toast.error("Failed to duplicate"); }
  }, [selectedNode, dbNodes, workflow.workflow_id, pushUndo]);

  // Validate workflow before activation
  const validateWorkflow = useCallback(() => {
    const issues = [];
    const nodeIds = new Set(nodes.map(n => n.id));
    const hasInput = dbNodes.some(n => n.type === "input");
    const hasOutput = dbNodes.some(n => n.type === "output");
    if (!hasInput) issues.push({ level: "error", msg: "Missing Input node" });
    if (!hasOutput) issues.push({ level: "error", msg: "Missing Output node" });
    if (nodes.length === 0) issues.push({ level: "error", msg: "Workflow has no nodes" });

    // Check orphaned nodes (no connections)
    for (const node of nodes) {
      const hasIncoming = edges.some(e => e.target === node.id);
      const hasOutgoing = edges.some(e => e.source === node.id);
      const db = dbNodes.find(n => n.node_id === node.id);
      if (db?.type !== "input" && !hasIncoming) issues.push({ level: "warning", msg: `"${db?.label || node.id}" has no incoming connections`, nodeId: node.id });
      if (db?.type !== "output" && !hasOutgoing) issues.push({ level: "warning", msg: `"${db?.label || node.id}" has no outgoing connections`, nodeId: node.id });
      // Check required config
      if (db?.type === "condition" && !db?.condition_logic?.field) issues.push({ level: "error", msg: `Condition "${db.label}" has no field configured`, nodeId: node.id });
      if (db?.type === "ai_agent" && (!db?.system_prompt || db.system_prompt.length < 5)) issues.push({ level: "warning", msg: `AI Agent "${db.label}" has default/empty prompt`, nodeId: node.id });
    }
    setValidationIssues(issues);
    return issues.filter(i => i.level === "error").length === 0;
  }, [nodes, edges, dbNodes]);

  // Handle activation with validation
  const handleActivate = useCallback(async () => {
    const valid = validateWorkflow();
    if (!valid) {
      toast.error("Fix validation errors before activating");
      return;
    }
    onStatusChange("active");
  }, [validateWorkflow, onStatusChange]);

  // Context menu
  const handleContextMenu = useCallback((e, node) => {
    e.preventDefault();
    setContextMenu({ x: e.clientX, y: e.clientY, nodeId: node?.id || null });
  }, []);

  const closeContextMenu = useCallback(() => setContextMenu(null), []);

  // Load run history
  const loadRunHistory = useCallback(async () => {
    try {
      const res = await api.get(`/workflows/${workflow.workflow_id}/runs`);
      setRunHistory(res.data || []);
      setShowHistory(true);
    } catch (err) { toast.error("Failed to load history"); }
  }, [workflow.workflow_id]);

  return (
    <div className="flex-1 flex flex-col h-full bg-zinc-950" data-testid="workflow-canvas">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-zinc-800/60 bg-zinc-900/80">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={onBack} className="text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800" data-testid="canvas-back-btn">
            <ArrowLeft className="w-4 h-4 mr-1" />
            Back
          </Button>
          <div className="h-5 w-px bg-zinc-700" />
          <h3 className="text-sm font-medium text-zinc-200">{workflow.name}</h3>
          <span className={`text-[10px] px-1.5 py-0.5 rounded uppercase font-medium ${
            workflow.status === "active" ? "bg-emerald-600/20 text-emerald-400" :
            workflow.status === "paused" ? "bg-amber-600/20 text-amber-400" :
            "bg-zinc-700/50 text-zinc-400"
          }`}>
            {workflow.status}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={undo} disabled={undoStack.length === 0} className="text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 px-2" title="Undo (Ctrl+Z)" data-testid="undo-btn">
            <Undo2 className="w-3.5 h-3.5" />
          </Button>
          <Button variant="ghost" size="sm" onClick={redo} disabled={redoStack.length === 0} className="text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 px-2" title="Redo (Ctrl+Shift+Z)" data-testid="redo-btn">
            <Redo2 className="w-3.5 h-3.5" />
          </Button>
          {selectedNode && (
            <Button variant="ghost" size="sm" onClick={duplicateNode} className="text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 px-2" title="Duplicate (Ctrl+D)" data-testid="duplicate-btn">
              <Copy className="w-3.5 h-3.5" />
            </Button>
          )}
          <div className="h-5 w-px bg-zinc-700" />
          <Button variant="outline" size="sm" onClick={loadRunHistory} className="border-zinc-700 text-zinc-300 hover:bg-zinc-800 text-xs" data-testid="run-history-btn">
            <History className="w-3 h-3 mr-1" />
            History
          </Button>
          <Button variant="outline" size="sm" onClick={saveCanvas} disabled={saving} className="border-zinc-700 text-zinc-300 hover:bg-zinc-800 text-xs" data-testid="save-canvas-btn">
            <Save className="w-3 h-3 mr-1" />
            {saving ? "Saving..." : "Save"}
          </Button>
          <Button variant="outline" size="sm" onClick={() => setShowPublish(true)} className="border-zinc-700 text-zinc-300 hover:bg-zinc-800 text-xs" data-testid="publish-workflow-btn">
            <Upload className="w-3 h-3 mr-1" />
            Publish
          </Button>
          {workflow.status === "draft" && (
            <Button size="sm" onClick={handleActivate} className="bg-emerald-600 hover:bg-emerald-700 text-xs" data-testid="activate-btn">
              <Play className="w-3 h-3 mr-1" />
              Activate
            </Button>
          )}
          {workflow.status === "active" && (
            <>
              <Button size="sm" onClick={() => setShowInputDialog(true)} className="bg-emerald-600 hover:bg-emerald-700 text-xs" data-testid="run-workflow-btn">
                <Play className="w-3 h-3 mr-1" />
                Run
              </Button>
              <Button variant="outline" size="sm" onClick={() => onStatusChange("paused")} className="border-zinc-700 text-amber-400 hover:bg-zinc-800 text-xs">
                <Pause className="w-3 h-3 mr-1" />
                Pause
              </Button>
            </>
          )}
          {workflow.status === "paused" && (
            <Button size="sm" onClick={() => onStatusChange("active")} className="bg-emerald-600 hover:bg-emerald-700 text-xs">
              <Play className="w-3 h-3 mr-1" />
              Resume
            </Button>
          )}
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Node palette */}
        <div className="w-14 border-r border-zinc-800/60 bg-zinc-900/40 flex flex-col items-center py-3 gap-2">
          {Object.entries(NODE_COLORS).map(([type, colors]) => {
            const Icon = colors.icon;
            return (
              <button
                key={type}
                onClick={() => addNode(type)}
                className="w-10 h-10 rounded-lg flex items-center justify-center hover:bg-zinc-800 transition-colors group"
                title={type.replace("_", " ")}
                data-testid={`add-node-${type}`}
              >
                <Icon className="w-4 h-4 group-hover:scale-110 transition-transform" style={{ color: colors.border }} />
              </button>
            );
          })}
          <div className="h-px w-6 bg-zinc-800 my-1" />
          {selectedNode && (
            <button
              onClick={deleteSelectedNode}
              className="w-10 h-10 rounded-lg flex items-center justify-center hover:bg-red-900/30 transition-colors text-red-400"
              title="Delete selected"
              data-testid="delete-selected-node"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* React Flow Canvas */}
        <div className="flex-1" ref={reactFlowWrapper}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={(changes) => { pushUndo(); onNodesChange(changes); }}
            onEdgesChange={(changes) => { pushUndo(); onEdgesChange(changes); }}
            onConnect={(params) => { pushUndo(); onConnect(params); }}
            onNodeClick={onNodeClick}
            onPaneClick={() => { onPaneClick(); closeContextMenu(); }}
            onNodeContextMenu={(e, node) => handleContextMenu(e, node)}
            onPaneContextMenu={(e) => handleContextMenu(e, null)}
            nodeTypes={nodeTypes}
            defaultEdgeOptions={defaultEdgeOptions}
            fitView
            proOptions={{ hideAttribution: true }}
            className="bg-zinc-950"
          >
            <Background color="#333" gap={20} size={1} />
            <Controls className="bg-zinc-800 border-zinc-700 [&>button]:bg-zinc-800 [&>button]:border-zinc-700 [&>button]:text-zinc-300 [&>button:hover]:bg-zinc-700" />
            <MiniMap
              nodeColor={(n) => NODE_COLORS[n.data?.nodeType]?.border || "#666"}
              maskColor="rgba(0,0,0,0.8)"
              className="bg-zinc-900 border border-zinc-800"
            />
            {nodes.length === 0 && (
              <Panel position="top-center">
                <div className="bg-zinc-900/90 border border-zinc-800 rounded-lg px-6 py-4 text-center mt-20">
                  <Zap className="w-8 h-8 text-zinc-600 mx-auto mb-2" />
                  <p className="text-sm text-zinc-400">Click nodes in the left palette to start building</p>
                  <p className="text-xs text-zinc-600 mt-1">Drag to connect nodes together</p>
                </div>
              </Panel>
            )}
          </ReactFlow>
        </div>

        {/* Right panel - Node config */}
        {selectedNode && (
          <NodeConfigPanel
            node={selectedNode}
            dbNode={dbNodes.find((n) => n.node_id === selectedNode.id)}
            onUpdate={(updates) => updateNodeConfig(selectedNode.id, updates)}
            onClose={() => setSelectedNode(null)}
          />
        )}
      </div>

      {/* Run Monitor Modal */}
      {showRunMonitor && activeRunId && (
        <RunMonitor
          runId={activeRunId}
          workflowId={workflow.workflow_id}
          workspaceId={workspaceId}
          onClose={() => { setShowRunMonitor(false); setActiveRunId(null); }}
        />
      )}

      {/* Input Dialog for running */}
      {showInputDialog && (
        <RunInputDialog
          inputSchema={inputSchema}
          templateNodes={dbNodes}
          onRun={(inputData) => { setShowInputDialog(false); runWorkflow(inputData); }}
          onClose={() => setShowInputDialog(false)}
        />
      )}

      {/* Publish Dialog */}
      {showPublish && (
        <PublishDialog
          workflowId={workflow.workflow_id}
          defaultName={workflow.name}
          onClose={() => setShowPublish(false)}
        />
      )}

      {/* Context Menu */}
      {contextMenu && (
        <div className="fixed z-[200] bg-zinc-900 border border-zinc-700 rounded-lg shadow-xl py-1 min-w-[160px]" style={{ left: contextMenu.x, top: contextMenu.y }} onClick={closeContextMenu} data-testid="context-menu">
          {contextMenu.nodeId ? (
            <>
              <button className="w-full text-left px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-800" onClick={() => { setSelectedNode(nodes.find(n => n.id === contextMenu.nodeId)); }}>Configure</button>
              <button className="w-full text-left px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-800" onClick={duplicateNode}>Duplicate (Ctrl+D)</button>
              <button className="w-full text-left px-3 py-1.5 text-xs text-red-400 hover:bg-zinc-800" onClick={deleteSelectedNode}>Delete</button>
            </>
          ) : (
            <>
              {Object.keys(NODE_COLORS).slice(0, 6).map(type => (
                <button key={type} className="w-full text-left px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-800" onClick={() => addNode(type)}>Add {type.replace(/_/g, " ")}</button>
              ))}
            </>
          )}
        </div>
      )}

      {/* Validation Issues */}
      {validationIssues.length > 0 && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 bg-zinc-900 border border-zinc-700 rounded-xl p-4 max-w-md shadow-2xl" data-testid="validation-panel">
          <div className="flex items-center gap-2 mb-2"><AlertTriangle className="w-4 h-4 text-amber-400" /><span className="text-sm font-medium text-zinc-200">Validation Issues</span>
            <button onClick={() => setValidationIssues([])} className="ml-auto text-zinc-500 hover:text-zinc-300 text-xs">Dismiss</button>
          </div>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {validationIssues.map((issue, i) => (
              <div key={`val-${issue.level}-${i}-${issue.msg?.slice(0,20)}`} className={`flex items-center gap-2 text-xs px-2 py-1 rounded ${issue.level === "error" ? "text-red-400 bg-red-500/10" : "text-amber-400 bg-amber-500/10"}`}>
                <span>{issue.level === "error" ? "ERROR" : "WARN"}</span>
                <span>{issue.msg}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Run History Panel */}
      {showHistory && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center" onClick={() => setShowHistory(false)}>
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-6 max-w-lg w-full mx-4 max-h-[70vh] overflow-y-auto" onClick={e => e.stopPropagation()} data-testid="run-history-panel">
            <h3 className="text-lg font-medium text-zinc-100 mb-4">Run History</h3>
            {runHistory.length === 0 ? <p className="text-sm text-zinc-500">No runs yet</p> : (
              <div className="space-y-2">
                {runHistory.map(run => (
                  <div key={run.run_id} className="flex items-center justify-between p-3 rounded-lg bg-zinc-800/40 border border-zinc-800/40">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className={`text-xs font-medium ${run.status === "completed" ? "text-emerald-400" : run.status === "failed" ? "text-red-400" : "text-zinc-400"}`}>{run.status}</span>
                        <span className="text-[10px] text-zinc-600 font-mono">{run.run_id}</span>
                      </div>
                      <span className="text-[10px] text-zinc-500">{run.created_at ? new Date(run.created_at).toLocaleString() : ""}</span>
                    </div>
                    <div className="text-right text-[10px] text-zinc-500">
                      <div>{run.total_tokens || 0} tokens</div>
                      <div>${(run.total_cost_usd || 0).toFixed(4)}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <Button variant="outline" size="sm" onClick={() => setShowHistory(false)} className="mt-4 border-zinc-700 text-zinc-300">Close</Button>
          </div>
        </div>
      )}
    </div>
  );
}

function RunInputDialog({ inputSchema, templateNodes, onRun, onClose }) {
  const [inputData, setInputData] = useState({});

  // Build input fields from template's input node or schema
  const fields = useMemo(() => {
    if (inputSchema && Object.keys(inputSchema).length > 0) {
      return Object.entries(inputSchema).map(([key, cfg]) => ({
        key,
        label: cfg.label || key,
        type: cfg.type || "string",
        required: cfg.required || false,
      }));
    }
    // Default: single text input
    return [{ key: "input", label: "Input", type: "string", required: true }];
  }, [inputSchema]);

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center" onClick={onClose}>
      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-6 max-w-lg w-full mx-4 space-y-4" onClick={(e) => e.stopPropagation()} data-testid="run-input-dialog">
        <h3 className="text-lg font-medium text-zinc-100">Run Workflow</h3>
        <p className="text-sm text-zinc-500">Provide input data for this workflow run.</p>
        {fields.map((f) => (
          <div key={f.key}>
            <label className="text-xs font-medium text-zinc-400 mb-1 block">
              {f.label} {f.required && <span className="text-red-400">*</span>}
            </label>
            {f.type === "text" ? (
              <textarea
                className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200 min-h-[100px]"
                value={inputData[f.key] || ""}
                onChange={(e) => setInputData((prev) => ({ ...prev, [f.key]: e.target.value }))}
                data-testid={`run-input-${f.key}`}
              />
            ) : (
              <input
                className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200"
                value={inputData[f.key] || ""}
                onChange={(e) => setInputData((prev) => ({ ...prev, [f.key]: e.target.value }))}
                data-testid={`run-input-${f.key}`}
              />
            )}
          </div>
        ))}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" onClick={onClose} className="border-zinc-700 text-zinc-300">Cancel</Button>
          <Button size="sm" onClick={() => onRun(inputData)} className="bg-emerald-600 hover:bg-emerald-700" data-testid="confirm-run-btn">
            <Play className="w-3 h-3 mr-1" />
            Start Run
          </Button>
        </div>
      </div>
    </div>
  );
}


function PublishDialog({ workflowId, defaultName, onClose }) {
  const [name, setName] = useState(defaultName || "");
  const [desc, setDesc] = useState("");
  const [category, setCategory] = useState("general");
  const [difficulty, setDifficulty] = useState("intermediate");
  const [estTime, setEstTime] = useState("");
  const [scope, setScope] = useState("global");
  const [publishing, setPublishing] = useState(false);

  const handlePublish = async () => {
    if (!name.trim()) return;
    setPublishing(true);
    try {
      await api.post("/marketplace/publish", {
        workflow_id: workflowId, name, description: desc,
        category, difficulty, estimated_time: estTime, scope,
      });
      toast.success("Published to marketplace!");
      onClose();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to publish");
    } finally {
      setPublishing(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center" onClick={onClose}>
      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-6 max-w-md w-full mx-4 space-y-3" onClick={(e) => e.stopPropagation()} data-testid="publish-dialog">
        <h3 className="text-lg font-medium text-zinc-100">Publish to Marketplace</h3>
        <p className="text-sm text-zinc-500">Share this workflow template with the community.</p>
        <input className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200" placeholder="Template Name" value={name} onChange={(e) => setName(e.target.value)} data-testid="publish-name" />
        <textarea className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200 min-h-[60px]" placeholder="Description" value={desc} onChange={(e) => setDesc(e.target.value)} data-testid="publish-desc" />
        <div className="grid grid-cols-2 gap-3">
          <select value={category} onChange={(e) => setCategory(e.target.value)} className="bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200" data-testid="publish-category">
            <option value="general">General</option>
            <option value="research">Research</option>
            <option value="content">Content</option>
            <option value="development">Development</option>
            <option value="business">Business</option>
            <option value="data">Data</option>
            <option value="marketing">Marketing</option>
            <option value="operations">Operations</option>
          </select>
          <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)} className="bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200" data-testid="publish-difficulty">
            <option value="beginner">Beginner</option>
            <option value="intermediate">Intermediate</option>
            <option value="advanced">Advanced</option>
          </select>
        </div>
        <input className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200" placeholder="Estimated time (e.g. 2-3 min)" value={estTime} onChange={(e) => setEstTime(e.target.value)} />
        <div className="flex gap-2">
          <button onClick={() => setScope("global")} className={`flex-1 py-2 text-xs rounded-md border ${scope === "global" ? "bg-zinc-700 border-zinc-600 text-zinc-100" : "border-zinc-800 text-zinc-500"}`}>Global</button>
          <button onClick={() => setScope("org")} className={`flex-1 py-2 text-xs rounded-md border ${scope === "org" ? "bg-zinc-700 border-zinc-600 text-zinc-100" : "border-zinc-800 text-zinc-500"}`}>Organization Only</button>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" onClick={onClose} className="border-zinc-700 text-zinc-300">Cancel</Button>
          <Button size="sm" onClick={handlePublish} disabled={!name.trim() || publishing} className="bg-zinc-100 text-zinc-900 hover:bg-zinc-200" data-testid="confirm-publish-btn">
            <Upload className="w-3 h-3 mr-1" />
            {publishing ? "Publishing..." : "Publish"}
          </Button>
        </div>
      </div>
    </div>
  );
}
