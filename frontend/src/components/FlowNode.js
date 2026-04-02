import React, { memo } from "react";
import { Handle, Position } from "reactflow";
import { Bot, User, GitBranch, Merge, LogIn, LogOut, Crosshair, Video, Volume2, Globe } from "lucide-react";

const NODE_COLORS = {
  input: { bg: "#1e3a5f", border: "#3b82f6", icon: LogIn },
  output: { bg: "#1e3f2f", border: "#22c55e", icon: LogOut },
  ai_agent: { bg: "#3f1e5f", border: "#a855f7", icon: Bot },
  human_review: { bg: "#5f3f1e", border: "#f59e0b", icon: User },
  condition: { bg: "#1e4f5f", border: "#06b6d4", icon: GitBranch },
  merge: { bg: "#3f3f1e", border: "#eab308", icon: Merge },
  trigger: { bg: "#1e5f3f", border: "#10b981", icon: Globe },
  text_to_video: { bg: "#5f1e2f", border: "#ef4444", icon: Video },
  text_to_speech: { bg: "#3f1e4f", border: "#8b5cf6", icon: Volume2 },
  text_to_music: { bg: "#3f1e4f", border: "#8b5cf6", icon: Volume2 },
  transcribe: { bg: "#1e3f4f", border: "#14b8a6", icon: Globe },
  video_compose: { bg: "#5f1e2f", border: "#ef4444", icon: Video },
  media_publish: { bg: "#1e3f2f", border: "#22c55e", icon: Globe },
};

export { NODE_COLORS };

function FlowNode({ data, selected }) {
  const colors = NODE_COLORS[data.nodeType] || NODE_COLORS.input;
  const Icon = colors.icon;
  const isCondition = data.nodeType === "condition";
  const isMerge = data.nodeType === "merge";

  return (
    <div
      className={`rounded-lg border-2 px-4 py-3 min-w-[180px] transition-shadow relative ${selected ? "shadow-lg shadow-white/10" : ""}`}
      style={{ backgroundColor: colors.bg, borderColor: selected ? "#fff" : colors.border }}
      data-testid={`flow-node-${data.nodeId}`}
    >
      {/* Target handle(s) */}
      {data.nodeType !== "input" && (
        <Handle type="target" position={Position.Top} style={{ background: "#666", border: "2px solid #444", width: 10, height: 10 }} />
      )}

      {/* Node content */}
      <div className="flex items-center gap-2 mb-1">
        <Icon className="w-4 h-4" style={{ color: colors.border }} />
        <span className="text-xs font-medium uppercase tracking-wider" style={{ color: colors.border }}>
          {data.nodeType?.replace(/_/g, " ")}
        </span>
      </div>
      <p className="text-sm font-medium text-zinc-100 truncate">{data.label}</p>
      {data.ai_model && (
        <p className="text-[10px] text-zinc-400 mt-1">{data.ai_model}</p>
      )}
      {data.merge_strategy && (
        <p className="text-[10px] text-zinc-400 mt-1">Strategy: {data.merge_strategy}</p>
      )}
      {/* Execution status indicator */}
      {data.execStatus && (
        <div className={`absolute top-1 right-1 w-2.5 h-2.5 rounded-full ${
          data.execStatus === "completed" ? "bg-emerald-400" :
          data.execStatus === "running" ? "bg-blue-400 animate-pulse" :
          data.execStatus === "failed" ? "bg-red-400" : "bg-zinc-600"
        }`} />
      )}

      {/* Source handle(s) */}
      {isCondition ? (
        <>
          {/* True handle (right side, green) */}
          <Handle
            type="source"
            position={Position.Right}
            id="true"
            style={{ background: "#22c55e", border: "2px solid #166534", width: 10, height: 10, top: "50%" }}
          />
          <span className="absolute right-[-8px] top-[35%] text-[8px] text-emerald-400 font-bold">T</span>
          {/* False handle (bottom, red) */}
          <Handle
            type="source"
            position={Position.Bottom}
            id="false"
            style={{ background: "#ef4444", border: "2px solid #991b1b", width: 10, height: 10 }}
          />
          <span className="absolute bottom-[-14px] left-1/2 -translate-x-1/2 text-[8px] text-red-400 font-bold">F</span>
        </>
      ) : data.nodeType !== "output" ? (
        <Handle type="source" position={Position.Bottom} style={{ background: "#666", border: "2px solid #444", width: 10, height: 10 }} />
      ) : null}
    </div>
  );
}

export default memo(FlowNode);
