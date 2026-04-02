import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Search, MessageSquare, FolderKanban, FileCode, BookOpen, Settings, Zap, CheckCircle2, Target, Globe, BarChart3, FileText, Loader2 } from "lucide-react";
import { handleSilent } from "@/lib/errorHandler";
import { api } from "@/App";

const COMMANDS = [
  { id: "chat", label: "Chat", desc: "Go to chat", icon: MessageSquare, tab: "chat" },
  { id: "projects", label: "Projects", desc: "Manage projects", icon: FolderKanban, tab: "projects" },
  { id: "tasks", label: "Tasks", desc: "View task board", icon: CheckCircle2, tab: "tasks" },
  { id: "docs", label: "Docs / Wiki", desc: "Documentation", icon: BookOpen, tab: "docs" },
  { id: "code", label: "Code Repository", desc: "Open code editor", icon: FileCode, tab: "code" },
  { id: "guide", label: "Guide Me", desc: "AI-guided browsing", icon: Globe, tab: "guide" },
  { id: "workflows", label: "Workflows", desc: "Automation builder", icon: Zap, tab: "workflows" },
  { id: "directives", label: "Directives", desc: "Directive dashboard", icon: Target, tab: "directives" },
  { id: "gantt", label: "Gantt Chart", desc: "Timeline view", icon: BarChart3, tab: "gantt" },
  { id: "planner", label: "Planner Calendar", desc: "Calendar planner", icon: BarChart3, tab: "planner" },
  { id: "ideation", label: "Ideation", desc: "Brainstorm and prototype", icon: BarChart3, tab: "ideation" },
  { id: "knowledge", label: "Knowledge Base", desc: "Workspace memory", icon: BookOpen, tab: "knowledge" },
  { id: "settings", label: "Settings", desc: "AI keys, preferences", icon: Settings, path: "/settings" },
];

const TYPE_ICONS = { message: MessageSquare, project: FolderKanban, task: CheckCircle2, wiki: BookOpen, artifact: FileText };
const TYPE_COLORS = { message: "text-blue-400", project: "text-emerald-400", task: "text-amber-400", wiki: "text-purple-400", artifact: "text-cyan-400" };

export default function CommandPalette({ onNavigate }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [mode, setMode] = useState("commands");
  const inputRef = useRef(null);
  const debounceRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen(prev => !prev);
      }
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);

  useEffect(() => {
    if (open) {
      setQuery("");
      setSearchResults([]);
      setMode("commands");
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  const doSearch = useCallback(async (q) => {
    if (!q || q.length < 2) { setSearchResults([]); setSearching(false); return; }
    setSearching(true);
    try {
      const res = await api.get(`/search?q=${encodeURIComponent(q)}&limit=15`);
      setSearchResults(res.data?.results || []);
    } catch (err) { handleSilent(err, "CommandPalette:search"); }
    setSearching(false);
  }, []);

  const handleQueryChange = (val) => {
    setQuery(val);
    if (val.length >= 2) {
      setMode("search");
      clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => doSearch(val), 300);
    } else {
      setMode("commands");
      setSearchResults([]);
    }
  };

  const filtered = mode === "commands"
    ? (query ? COMMANDS.filter(c => c.label.toLowerCase().includes(query.toLowerCase()) || c.desc.toLowerCase().includes(query.toLowerCase())) : COMMANDS)
    : [];

  const select = (cmd) => {
    setOpen(false);
    if (cmd.path) navigate(cmd.path);
    else if (cmd.tab && onNavigate) onNavigate(cmd.tab);
  };

  const selectResult = (result) => {
    setOpen(false);
    if (result.type === "message" && result.channel_id && onNavigate) onNavigate("chat");
    else if (result.type === "project" && onNavigate) onNavigate("projects");
    else if (result.type === "task" && onNavigate) onNavigate("tasks");
    else if (result.type === "wiki" && onNavigate) onNavigate("docs");
    else if (result.type === "artifact" && onNavigate) onNavigate("projects");
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[300] flex items-start justify-center pt-[20vh]" data-testid="command-palette">
      <div className="absolute inset-0 bg-black/60" onClick={() => setOpen(false)} />
      <div className="relative w-full max-w-lg bg-zinc-900 border border-zinc-800 rounded-xl shadow-2xl overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-zinc-800">
          <Search className="w-4 h-4 text-zinc-500" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => handleQueryChange(e.target.value)}
            placeholder="Search everything or type a command..."
            className="flex-1 bg-transparent text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none"
            data-testid="command-input"
          />
          {searching && <Loader2 className="w-3.5 h-3.5 animate-spin text-zinc-500" />}
          <kbd className="text-[9px] text-zinc-600 bg-zinc-800 px-1.5 py-0.5 rounded">ESC</kbd>
        </div>

        {/* Mode tabs */}
        {query.length >= 2 && (
          <div className="flex gap-1 px-3 py-1.5 border-b border-zinc-800/50">
            <button onClick={() => setMode("commands")} className={`px-2 py-0.5 text-[10px] rounded ${mode === "commands" ? "bg-zinc-700 text-zinc-200" : "text-zinc-500 hover:text-zinc-300"}`} data-testid="cmd-mode-commands">Commands</button>
            <button onClick={() => { setMode("search"); doSearch(query); }} className={`px-2 py-0.5 text-[10px] rounded ${mode === "search" ? "bg-zinc-700 text-zinc-200" : "text-zinc-500 hover:text-zinc-300"}`} data-testid="cmd-mode-search">Search All</button>
          </div>
        )}

        <div className="max-h-[300px] overflow-y-auto py-1">
          {mode === "commands" && (
            <>
              {filtered.length === 0 && <p className="text-sm text-zinc-600 text-center py-4">No commands match</p>}
              {filtered.map((cmd) => {
                const Icon = cmd.icon;
                return (
                  <button key={cmd.id} onClick={() => select(cmd)} className="w-full flex items-center gap-3 px-4 py-2.5 text-left hover:bg-zinc-800/60 transition-colors" data-testid={`cmd-${cmd.id}`}>
                    <Icon className="w-4 h-4 text-zinc-500" />
                    <div className="flex-1">
                      <span className="text-sm text-zinc-200">{cmd.label}</span>
                      <span className="text-xs text-zinc-600 ml-2">{cmd.desc}</span>
                    </div>
                  </button>
                );
              })}
            </>
          )}

          {mode === "search" && (
            <>
              {searching && <div className="py-6 text-center"><Loader2 className="w-4 h-4 animate-spin text-zinc-500 mx-auto" /></div>}
              {!searching && searchResults.length === 0 && query.length >= 2 && (
                <p className="text-sm text-zinc-600 text-center py-4">No results for "{query}"</p>
              )}
              {searchResults.map((r, i) => {
                const Icon = TYPE_ICONS[r.type] || FileText;
                const color = TYPE_COLORS[r.type] || "text-zinc-400";
                return (
                  <button key={`${r.type}-${r.id}-${i}`} onClick={() => selectResult(r)} className="w-full flex items-center gap-3 px-4 py-2.5 text-left hover:bg-zinc-800/60 transition-colors" data-testid={`search-result-${i}`}>
                    <Icon className={`w-4 h-4 ${color}`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-zinc-200 truncate">{r.title}</span>
                        <span className={`text-[9px] px-1.5 py-0.5 rounded ${color} bg-zinc-800`}>{r.type}</span>
                      </div>
                      {r.snippet && <p className="text-xs text-zinc-500 truncate mt-0.5">{r.snippet.substring(0, 120)}</p>}
                    </div>
                  </button>
                );
              })}
            </>
          )}
        </div>

        <div className="px-4 py-2 border-t border-zinc-800 flex items-center gap-4 text-[10px] text-zinc-600">
          <span><kbd className="bg-zinc-800 px-1 rounded">↑↓</kbd> Navigate</span>
          <span><kbd className="bg-zinc-800 px-1 rounded">↵</kbd> Select</span>
          <span><kbd className="bg-zinc-800 px-1 rounded">Esc</kbd> Close</span>
          <span className="ml-auto">Type 2+ chars to search across workspace</span>
        </div>
      </div>
    </div>
  );
}
