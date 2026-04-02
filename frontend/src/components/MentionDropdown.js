import { useState, useEffect, useRef, useCallback } from "react";
import { AtSign, Users } from "lucide-react";

const AI_COLORS = {
  claude: "#D97757",
  chatgpt: "#10A37F",
  gemini: "#4285F4",
  perplexity: "#20B2AA",
  mistral: "#FF7000",
  cohere: "#39594D",
  groq: "#F55036",
  deepseek: "#4D6BFE",
  grok: "#F5F5F5",
  mercury: "#00D4FF",
  pi: "#FF6B35",
  manus: "#6C5CE7",
  qwen: "#615EFF",
  kimi: "#000000",
  llama: "#0467DF",
  glm: "#3D5AFE",
  cursor: "#00E5A0",
  notebooklm: "#FBBC04",
  copilot: "#171515",
};

export const MentionDropdown = ({ agents, query, onSelect, position }) => {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const listRef = useRef(null);

  const filtered = agents.filter((a) =>
    a.name.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        if (filtered[selectedIndex]) {
          onSelect(filtered[selectedIndex]);
        }
      } else if (e.key === "Escape") {
        onSelect(null);
      }
    },
    [filtered, selectedIndex, onSelect]
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  if (filtered.length === 0) return null;

  return (
    <div
      className="absolute z-[100] bg-zinc-900 border border-zinc-700/60 rounded-lg shadow-2xl py-1 w-56 max-h-52 overflow-y-auto"
      style={{ bottom: position?.bottom || "100%", left: position?.left || 0, marginBottom: 8 }}
      ref={listRef}
      data-testid="mention-dropdown"
    >
      <div className="px-3 py-1.5 text-[10px] font-mono text-zinc-500 uppercase tracking-wider">
        Mention
      </div>
      {filtered.map((agent, i) => {
        const isSpecial = agent.type === "special";
        const color = AI_COLORS[agent.key] || agent.color || "#6B7280";
        return (
          <button
            key={agent.key}
            className={`w-full flex items-center gap-2.5 px-3 py-2 text-left transition-colors ${
              i === selectedIndex
                ? "bg-zinc-800 text-zinc-100"
                : "text-zinc-300 hover:bg-zinc-800/60"
            }`}
            onClick={() => onSelect(agent)}
            onMouseEnter={() => setSelectedIndex(i)}
            data-testid={`mention-option-${agent.key}`}
          >
            {isSpecial ? (
              <div className="w-6 h-6 rounded-md bg-amber-500/20 flex items-center justify-center">
                <Users className="w-3.5 h-3.5 text-amber-400" />
              </div>
            ) : (
              <div
                className="w-6 h-6 rounded-md flex items-center justify-center text-[10px] font-bold"
                style={{
                  backgroundColor: color,
                  color: agent.key === "grok" ? "#09090b" : "#fff",
                }}
              >
                {agent.name?.[0]?.toUpperCase()}
              </div>
            )}
            <span className="text-sm font-medium truncate">
              {isSpecial ? "@everyone" : agent.name}
            </span>
            {agent.type === "nexus" && (
              <span className="ml-auto text-[9px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-500 border border-zinc-700/40">
                Custom
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};

export default MentionDropdown;
