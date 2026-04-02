import { useState, useEffect, useCallback, useRef } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { useConfirm } from "@/components/ConfirmDialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Brain, Plus, Search, Trash2, Pencil, Tag, BookOpen, Lightbulb, FileCheck, Link2, MessageSquare, Bold, Italic, Code, List, Paperclip, Upload } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/App";

const CATEGORY_CONFIG = {
  general: { icon: BookOpen, color: "text-zinc-400 bg-zinc-500/10 border-zinc-500/20" },
  insight: { icon: Lightbulb, color: "text-amber-400 bg-amber-500/10 border-amber-500/20" },
  decision: { icon: FileCheck, color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20" },
  reference: { icon: Link2, color: "text-blue-400 bg-blue-500/10 border-blue-500/20" },
  context: { icon: MessageSquare, color: "text-purple-400 bg-purple-500/10 border-purple-500/20" },
};

export default function KnowledgeBasePanel({ workspaceId }) {
  const { confirm: confirmAction, ConfirmDialog: ConfirmDlg } = useConfirm();
  const [entries, setEntries] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filterCategory, setFilterCategory] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [editEntry, setEditEntry] = useState(null);
  const [formKey, setFormKey] = useState("");
  const [formValue, setFormValue] = useState("");
  const [formCategory, setFormCategory] = useState("general");
  const [formTags, setFormTags] = useState("");
  const editorRef = useRef(null);

  const insertMarkdown = (before, after) => {
    const el = editorRef.current;
    if (!el) return;
    const start = el.selectionStart;
    const end = el.selectionEnd;
    const selected = formValue.substring(start, end);
    const newText = formValue.substring(0, start) + before + (selected || "text") + after + formValue.substring(end);
    setFormValue(newText);
    setTimeout(() => {
      el.focus();
      const cursorPos = start + before.length + (selected ? selected.length : 4) + after.length;
      el.setSelectionRange(cursorPos, cursorPos);
    }, 0);
  };

  const fetchEntries = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.append("search", search);
      if (filterCategory) params.append("category", filterCategory);
      const res = await api.get(`/workspaces/${workspaceId}/memory?${params}`);
      const data = res.data;
      setEntries(Array.isArray(data.entries) ? data.entries : Array.isArray(data) ? data : []);
      setTotal(data.total || (Array.isArray(data.entries) ? data.entries.length : 0));
    } catch (err) {
      console.error("KB fetch error:", err);
      setEntries([]);
    }
    setLoading(false);
  }, [workspaceId, search, filterCategory]);

  useEffect(() => { fetchEntries(); }, [fetchEntries]);

  const handleSave = async () => {
    if (!formKey.trim() || !formValue.trim()) return;
    try {
      if (editEntry) {
        await api.put(`/memory/${editEntry.memory_id}`, {
          value: formValue, category: formCategory,
          tags: formTags ? formTags.split(",").map(t => t.trim()).filter(Boolean) : [],
        });
        toast.success("Entry updated");
      } else {
        await api.post(`/workspaces/${workspaceId}/memory`, {
          key: formKey, value: formValue, category: formCategory,
          tags: formTags ? formTags.split(",").map(t => t.trim()).filter(Boolean) : [],
        });
        toast.success("Entry saved");
      }
      setCreateOpen(false);
      setEditEntry(null);
      resetForm();
      fetchEntries();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed to save"); }
  };

  const handleDelete = async (memoryId) => {
    const _ok = await confirmAction("Delete Entry", "Delete this knowledge base entry?"); if (!_ok) return;
    try {
      await api.delete(`/memory/${memoryId}`);
      toast.success("Deleted");
      fetchEntries();
    } catch (err) { toast.error("Failed to delete"); }
  };

  const openEdit = (entry) => {
    setEditEntry(entry);
    setFormKey(entry.key);
    setFormValue(entry.value);
    setFormCategory(entry.category || "general");
    setFormTags((entry.tags || []).join(", "));
    setCreateOpen(true);
  };

  const resetForm = () => { setFormKey(""); setFormValue(""); setFormCategory("general"); setFormTags(""); };

  return (
    <div className="flex-1 overflow-y-auto p-6" data-testid="knowledge-base-panel">
      <div className="max-w-3xl mx-auto space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100 flex items-center gap-2" style={{ fontFamily: "Syne, sans-serif" }}>
              <Brain className="w-5 h-5 text-purple-400" /> Knowledge Base
            </h2>
            <p className="text-sm text-zinc-500 mt-0.5">Persistent workspace memory — AI agents can read and write here</p>
          </div>
          <Button onClick={() => { setEditEntry(null); resetForm(); setCreateOpen(true); }} className="bg-emerald-500 hover:bg-emerald-400 text-white font-semibold gap-2 shadow-lg shadow-emerald-500/20" data-testid="create-memory-btn">
            <Plus className="w-4 h-4" /> Add Entry
          </Button>
        </div>

        {/* Search + filter */}
        <div className="flex items-center gap-2 flex-wrap">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <Input placeholder="Search memory..." value={search} onChange={(e) => setSearch(e.target.value)}
              className="pl-9 bg-zinc-800/60 border-zinc-700 text-zinc-200 text-sm" data-testid="memory-search" />
          </div>
          <select value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)}
            className="bg-zinc-800/60 border border-zinc-700 rounded-md px-3 py-2 text-xs text-zinc-300" data-testid="memory-category-filter">
            <option value="">All Categories</option>
            {Object.entries(CATEGORY_CONFIG).map(([k]) => (
              <option key={k} value={k}>{k.charAt(0).toUpperCase() + k.slice(1)}</option>
            ))}
          </select>
        </div>

        {/* Entries */}
        {loading ? (
          <div className="text-center py-16 text-zinc-500">Loading...</div>
        ) : entries.length === 0 ? (
          <div className="text-center py-16" data-testid="empty-memory">
            <Brain className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
            <p className="text-zinc-400 font-medium">No entries yet</p>
            <p className="text-sm text-zinc-600 mt-1">Add knowledge manually or let AI agents save insights automatically</p>
          </div>
        ) : (
          <div className="space-y-2" data-testid="memory-entries">
            {entries.map((entry) => {
              const cat = CATEGORY_CONFIG[entry.category] || CATEGORY_CONFIG.general;
              const CatIcon = cat.icon;
              return (
                <div key={entry.memory_id} className="rounded-lg bg-zinc-900/60 border border-zinc-800/60 p-3 hover:border-zinc-700 transition-colors group" data-testid={`memory-${entry.memory_id}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-2.5 min-w-0 flex-1">
                      <div className={`w-7 h-7 rounded-md flex items-center justify-center border flex-shrink-0 mt-0.5 ${cat.color}`}>
                        <CatIcon className="w-3.5 h-3.5" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-medium text-zinc-200">{entry.key}</span>
                          <span className="text-[10px] text-zinc-600 font-mono">v{entry.version || 1}</span>
                        </div>
                        <p className="text-sm text-zinc-400 mt-1 whitespace-pre-wrap line-clamp-3">{entry.value}</p>
                        {entry.tags?.length > 0 && (
                          <div className="flex items-center gap-1 mt-1.5">
                            <Tag className="w-3 h-3 text-zinc-600" />
                            {entry.tags.map((tag) => (
                              <span key={tag} className="text-[10px] text-zinc-500 bg-zinc-800 px-1.5 py-0.5 rounded">{tag}</span>
                            ))}
                          </div>
                        )}
                        <span className="text-[10px] text-zinc-600 mt-1 block">
                          Updated {new Date(entry.updated_at).toLocaleDateString()} by {entry.updated_by || "unknown"}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                      <button onClick={() => openEdit(entry)} className="p-1.5 rounded hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300" data-testid={`edit-memory-${entry.memory_id}`}>
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                      <button onClick={() => handleDelete(entry.memory_id)} className="p-1.5 rounded hover:bg-zinc-800 text-zinc-500 hover:text-red-400" data-testid={`delete-memory-${entry.memory_id}`}>
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
            <p className="text-xs text-zinc-600 text-center">{total} entries</p>
          </div>
        )}

        {/* Create/Edit Dialog — rich editor */}
        <Dialog open={createOpen} onOpenChange={(open) => { if (!open) { setCreateOpen(false); setEditEntry(null); } }}>
          <DialogContent className="bg-zinc-900 border-zinc-800 max-w-2xl">
            <DialogHeader>
              <DialogTitle className="text-zinc-100 flex items-center gap-2">
                <Brain className="w-5 h-5 text-purple-400" />
                {editEntry ? "Edit Entry" : "Add to Knowledge Base"}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-2">
              {/* Key */}
              <div>
                <label className="text-xs text-zinc-400 mb-1.5 block font-medium">Key</label>
                <Input placeholder="e.g., api_architecture, user_preferences, project_goals" value={formKey} onChange={(e) => setFormKey(e.target.value)}
                  className="bg-zinc-800 border-zinc-700 text-zinc-200" disabled={!!editEntry} data-testid="memory-key-input" />
              </div>

              {/* Rich text toolbar + editor */}
              <div>
                <label className="text-xs text-zinc-400 mb-1.5 block font-medium">Content</label>
                <div className="border border-zinc-700 rounded-lg overflow-hidden bg-zinc-800">
                  {/* Toolbar */}
                  <div className="flex items-center gap-0.5 px-2 py-1.5 border-b border-zinc-700/60 bg-zinc-800/80">
                    <button type="button" onClick={() => insertMarkdown("**", "**")} className="p-1.5 rounded hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors" title="Bold">
                      <Bold className="w-3.5 h-3.5" />
                    </button>
                    <button type="button" onClick={() => insertMarkdown("_", "_")} className="p-1.5 rounded hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors" title="Italic">
                      <Italic className="w-3.5 h-3.5" />
                    </button>
                    <button type="button" onClick={() => insertMarkdown("`", "`")} className="p-1.5 rounded hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors" title="Inline code">
                      <Code className="w-3.5 h-3.5" />
                    </button>
                    <button type="button" onClick={() => insertMarkdown("```\n", "\n```")} className="p-1.5 rounded hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors" title="Code block">
                      <span className="text-[10px] font-mono font-bold">{"{}"}</span>
                    </button>
                    <button type="button" onClick={() => insertMarkdown("- ", "")} className="p-1.5 rounded hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors" title="List item">
                      <List className="w-3.5 h-3.5" />
                    </button>
                    <button type="button" onClick={() => insertMarkdown("[", "](url)")} className="p-1.5 rounded hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors" title="Link">
                      <Link2 className="w-3.5 h-3.5" />
                    </button>
                    <div className="w-px h-4 bg-zinc-700 mx-1" />
                    <label className="p-1.5 rounded hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer" title="Attach file reference">
                      <Paperclip className="w-3.5 h-3.5" />
                      <input type="file" className="hidden" onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) {
                          const ref = `[Attached: ${file.name} (${(file.size / 1024).toFixed(1)}KB)]`;
                          setFormValue(prev => prev ? prev + "\n" + ref : ref);
                          toast.success(`Reference to "${file.name}" added`);
                        }
                        e.target.value = "";
                      }} />
                    </label>
                    <span className="ml-auto text-[10px] text-zinc-600">Markdown supported</span>
                  </div>
                  {/* Editor */}
                  <textarea
                    ref={editorRef}
                    value={formValue}
                    onChange={(e) => setFormValue(e.target.value)}
                    className="w-full bg-zinc-800 px-4 py-3 text-sm text-zinc-200 min-h-[200px] resize-y focus:outline-none font-mono leading-relaxed"
                    placeholder="Write your knowledge entry here...&#10;&#10;Supports **bold**, _italic_, `code`, and ```code blocks```"
                    data-testid="memory-value-input"
                  />
                </div>
              </div>

              {/* Category + Tags row */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-zinc-400 mb-1.5 block font-medium">Category</label>
                  <select value={formCategory} onChange={(e) => setFormCategory(e.target.value)}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200" data-testid="memory-category-input">
                    {Object.entries(CATEGORY_CONFIG).map(([k]) => (
                      <option key={k} value={k}>{k.charAt(0).toUpperCase() + k.slice(1)}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-zinc-400 mb-1.5 block font-medium">Tags</label>
                  <Input placeholder="Comma-separated tags" value={formTags} onChange={(e) => setFormTags(e.target.value)}
                    className="bg-zinc-800 border-zinc-700 text-zinc-200" data-testid="memory-tags-input" />
                </div>
              </div>

              <Button onClick={handleSave} disabled={!formKey.trim() || !formValue.trim()}
                className="w-full bg-emerald-500 hover:bg-emerald-400 text-white font-semibold" data-testid="memory-save-btn">
                {editEntry ? "Update Entry" : "Save to Knowledge Base"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    <ConfirmDlg />
    </div>
    );
}
