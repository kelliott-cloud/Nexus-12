import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Command, X } from "lucide-react";

const SHORTCUTS = [
  { keys: ["Ctrl", "K"], action: "search", label: "Quick Search" },
  { keys: ["Ctrl", "N"], action: "new", label: "New Workspace" },
  { keys: ["Ctrl", "B"], action: "billing", label: "Billing" },
  { keys: ["Ctrl", ","], action: "settings", label: "Settings" },
  { keys: ["Ctrl", "/"], action: "shortcuts", label: "Show Shortcuts" },
  { keys: ["Esc"], action: "close", label: "Close Dialog" },
];

export function useKeyboardShortcuts(handlers = {}) {
  const [showPalette, setShowPalette] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e) => {
      // Skip if user is typing in an input
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT") return;

      if (e.ctrlKey || e.metaKey) {
        const key = e.key.toLowerCase();
        if (key === "k" && handlers.search) { e.preventDefault(); handlers.search(); }
        else if (key === "n" && handlers.new) { e.preventDefault(); handlers.new(); }
        else if (key === "b" && handlers.billing) { e.preventDefault(); handlers.billing(); }
        else if (key === "," && handlers.settings) { e.preventDefault(); handlers.settings(); }
        else if (key === "/" || key === "?") { e.preventDefault(); setShowPalette((p) => !p); }
      }
      if (e.key === "Escape") setShowPalette(false);
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handlers]);

  return { showPalette, setShowPalette };
}

export function ShortcutPalette({ open, onClose }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[200] flex items-start justify-center pt-[15vh]" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div className="relative bg-zinc-900 border border-zinc-800 rounded-xl shadow-2xl w-96 p-4" onClick={(e) => e.stopPropagation()} data-testid="shortcut-palette">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2"><Command className="w-4 h-4 text-zinc-400" /><span className="text-sm font-medium text-zinc-200">Keyboard Shortcuts</span></div>
          <button onClick={onClose} className="p-1 rounded hover:bg-zinc-800 text-zinc-500"><X className="w-4 h-4" /></button>
        </div>
        <div className="space-y-1">
          {SHORTCUTS.map((s) => (
            <div key={s.action} className="flex items-center justify-between px-2 py-1.5 rounded-md hover:bg-zinc-800/50">
              <span className="text-sm text-zinc-300">{s.label}</span>
              <div className="flex items-center gap-1">
                {s.keys.map((k) => (
                  <kbd key={k} className="px-1.5 py-0.5 rounded bg-zinc-800 text-[10px] text-zinc-400 font-mono border border-zinc-700">{k}</kbd>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default SHORTCUTS;
