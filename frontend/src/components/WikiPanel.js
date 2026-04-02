import { useState, useEffect, useCallback, useRef } from "react";
import { useConfirm } from "@/components/ConfirmDialog";
import { handleError, handleSilent } from "@/lib/errorHandler";
import DOMPurify from "dompurify";
import Editor from "@monaco-editor/react";
import { api } from "@/App";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import {
  FileText, Plus, Search, Trash2, History, ChevronRight, ChevronDown,
  Pin, PinOff, Save, Eye, Pencil, BookOpen, Clock,
} from "lucide-react";

// Page tree is rendered inline in the main component below

export default function WikiPanel({ workspaceId }) {
  const { confirm: confirmAction, ConfirmDialog: ConfirmDlg } = useConfirm();
  const [pages, setPages] = useState([]);
  const [selectedPageId, setSelectedPageId] = useState(null);
  const [page, setPage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState("");
  const [editTitle, setEditTitle] = useState("");
  const [saving, setSaving] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [newPageOpen, setNewPageOpen] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newParentId, setNewParentId] = useState("");
  const [historyOpen, setHistoryOpen] = useState(false);
  const [versions, setVersions] = useState([]);
  const [wikiTemplates, setWikiTemplates] = useState([]);
  const editorRef = useRef(null);

  const fetchPages = useCallback(async () => {
    try {
      const url = searchQuery
        ? `/workspaces/${workspaceId}/wiki?search=${encodeURIComponent(searchQuery)}`
        : `/workspaces/${workspaceId}/wiki`;
      const res = await api.get(url);
      setPages(res.data.pages || []);
    } catch (err) { handleSilent(err, "WikiPanel:op1"); }
  }, [workspaceId, searchQuery]);

  useEffect(() => { fetchPages(); }, [fetchPages]);

  const selectPage = async (pageId) => {
    setSelectedPageId(pageId);
    setLoading(true);
    setEditing(false);
    try {
      const res = await api.get(`/workspaces/${workspaceId}/wiki/${pageId}`);
      setPage(res.data);
      setEditContent(res.data.content || "");
      setEditTitle(res.data.title || "");
    } catch (err) {
      toast.error("Failed to load page");
    } finally {
      setLoading(false);
    }
  };

  const createPage = async () => {
    if (!newTitle.trim()) return;
    try {
      const res = await api.post(`/workspaces/${workspaceId}/wiki`, {
        title: newTitle,
        content: "",
        parent_id: newParentId || null,
      });
      toast.success("Page created");
      setNewPageOpen(false);
      setNewTitle("");
      setNewParentId("");
      fetchPages();
      selectPage(res.data.page_id);
      setEditing(true);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    }
  };

  const createFromTemplate = async (templateId) => {
    try {
      const res = await api.post(`/workspaces/${workspaceId}/wiki/from-template`, {
        template_id: templateId, title: newTitle || undefined, parent_id: newParentId || null,
      });
      toast.success("Page created from template");
      setNewPageOpen(false);
      setNewTitle("");
      fetchPages();
      selectPage(res.data.page_id);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    }
  };

  const savePage = async () => {
    if (!page) return;
    setSaving(true);
    try {
      await api.put(`/workspaces/${workspaceId}/wiki/${page.page_id}`, {
        title: editTitle,
        content: editContent,
      });
      toast.success("Saved");
      setPage(prev => ({ ...prev, title: editTitle, content: editContent, version: (prev.version || 0) + 1 }));
      setEditing(false);
      fetchPages();
    } catch (err) {
      toast.error("Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const deletePage = async (pageId) => {
    const _ok = await confirmAction("Delete Page", "Delete this wiki page permanently?"); if (!_ok) return;
    try {
      await api.delete(`/workspaces/${workspaceId}/wiki/${pageId}`);
      toast.success("Deleted");
      if (selectedPageId === pageId) { setSelectedPageId(null); setPage(null); }
      fetchPages();
    } catch (err) { toast.error("Failed"); }
  };

  const togglePin = async () => {
    if (!page) return;
    try {
      await api.put(`/workspaces/${workspaceId}/wiki/${page.page_id}`, { pinned: !page.pinned });
      setPage(prev => ({ ...prev, pinned: !prev.pinned }));
      fetchPages();
    } catch (err) { handleSilent(err, "WikiPanel:op2"); }
  };

  const loadHistory = async () => {
    if (!page) return;
    try {
      const res = await api.get(`/workspaces/${workspaceId}/wiki/${page.page_id}/history`);
      setVersions(res.data.versions || []);
      setHistoryOpen(true);
    } catch (err) { toast.error("Failed to load history"); }
  };

  const restoreVersion = async (v) => {
    setEditContent(v.content);
    setEditTitle(v.title);
    setEditing(true);
    setHistoryOpen(false);
    toast.info(`Restored v${v.version} — save to apply`);
  };

  // Render markdown preview (simple)
  const renderMarkdown = (text) => {
    if (!text) return "";
    const html = text
      .replace(/^### (.+)$/gm, '<h3 class="text-base font-semibold text-zinc-200 mt-4 mb-2">$1</h3>')
      .replace(/^## (.+)$/gm, '<h2 class="text-lg font-semibold text-zinc-100 mt-5 mb-2">$1</h2>')
      .replace(/^# (.+)$/gm, '<h1 class="text-xl font-bold text-zinc-100 mt-6 mb-3">$1</h1>')
      .replace(/\*\*(.+?)\*\*/g, '<strong class="text-zinc-200">$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code class="px-1 py-0.5 rounded bg-zinc-800 text-emerald-400 text-xs font-mono">$1</code>')
      .replace(/^- (.+)$/gm, '<li class="ml-4 text-zinc-400 text-sm">$1</li>')
      .replace(/^(\d+)\. (.+)$/gm, '<li class="ml-4 text-zinc-400 text-sm">$1. $2</li>')
      .replace(/\n/g, '<br/>');
    // Sanitize to prevent XSS
    return DOMPurify.sanitize(html, { ALLOWED_TAGS: ["h1","h2","h3","strong","em","code","li","br","ul","ol","p","a","span","div"], ALLOWED_ATTR: ["class","href"] });
  };

  const filteredPages = pages;
  const pinnedPages = filteredPages.filter(p => p.pinned);
  const rootPages = filteredPages.filter(p => !p.parent_id);
  const childPages = (pid) => filteredPages.filter(p => p.parent_id === pid);

  return (
    <div className="flex-1 flex flex-col" data-testid="wiki-panel">
      {/* Header */}
      <div className="flex-shrink-0 flex items-center justify-between px-6 py-4 border-b border-zinc-800/60">
        <div className="flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-blue-400" />
          <h2 className="text-lg font-semibold text-zinc-200" style={{ fontFamily: "Syne, sans-serif" }}>Docs</h2>
          <Badge className="bg-zinc-800 text-zinc-500 text-[10px]">{pages.length} pages</Badge>
        </div>
        <Button size="sm" onClick={() => setNewPageOpen(true)} className="bg-zinc-100 text-zinc-900 hover:bg-zinc-200" data-testid="new-wiki-page-btn">
          <Plus className="w-3.5 h-3.5 mr-1" /> New Page
        </Button>
      </div>

      <div className="flex-1 flex min-h-0">
        {/* Sidebar - Page Tree */}
        <div className="w-56 flex-shrink-0 border-r border-zinc-800/60 flex flex-col bg-zinc-900/40">
          <div className="p-2">
            <div className="relative">
              <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-zinc-600" />
              <input
                type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search docs..." className="w-full bg-transparent text-xs text-zinc-300 placeholder:text-zinc-600 pl-6 pr-2 py-1.5 rounded border border-transparent focus:border-zinc-700 focus:outline-none"
                data-testid="wiki-search"
              />
            </div>
          </div>
          <ScrollArea className="flex-1">
            <div className="px-1 pb-2">
              {/* Pinned pages */}
              {pinnedPages.length > 0 && (
                <div className="mb-2">
                  <p className="text-[9px] text-zinc-600 uppercase tracking-wider px-2 mb-1 font-semibold">Pinned</p>
                  {pinnedPages.map(p => (
                    <button key={p.page_id} onClick={() => selectPage(p.page_id)}
                      className={`w-full flex items-center gap-1.5 px-2 py-1.5 text-left rounded-md text-xs transition-colors ${
                        selectedPageId === p.page_id ? "bg-zinc-800 text-zinc-100" : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40"
                      }`} data-testid={`wiki-pinned-${p.page_id}`}>
                      <Pin className="w-3 h-3 text-amber-400 flex-shrink-0" />
                      <span className="truncate">{p.icon ? `${p.icon} ` : ""}{p.title}</span>
                    </button>
                  ))}
                  <div className="border-b border-zinc-800/40 mx-2 my-1" />
                </div>
              )}
              {/* Page tree */}
              {rootPages.map(p => {
                const kids = childPages(p.page_id);
                const isSelected = selectedPageId === p.page_id;
                return (
                  <div key={p.page_id}>
                    <button onClick={() => selectPage(p.page_id)}
                      className={`w-full flex items-center gap-1.5 px-2 py-1.5 text-left rounded-md text-xs transition-colors ${
                        isSelected ? "bg-zinc-800 text-zinc-100" : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40"
                      }`} data-testid={`wiki-page-${p.page_id}`}>
                      {kids.length > 0 ? <ChevronDown className="w-3 h-3 flex-shrink-0" /> : <span className="w-3" />}
                      <FileText className="w-3.5 h-3.5 flex-shrink-0 text-blue-400/60" />
                      <span className="truncate">{p.icon ? `${p.icon} ` : ""}{p.title}</span>
                    </button>
                    {kids.map(child => (
                      <button key={child.page_id} onClick={() => selectPage(child.page_id)}
                        className={`w-full flex items-center gap-1.5 px-2 py-1.5 text-left rounded-md text-xs transition-colors ${
                          selectedPageId === child.page_id ? "bg-zinc-800 text-zinc-100" : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40"
                        }`} style={{ paddingLeft: "24px" }} data-testid={`wiki-page-${child.page_id}`}>
                        <FileText className="w-3 h-3 flex-shrink-0 text-blue-400/40" />
                        <span className="truncate">{child.icon ? `${child.icon} ` : ""}{child.title}</span>
                      </button>
                    ))}
                  </div>
                );
              })}
              {pages.length === 0 && (
                <div className="px-3 py-8 text-center">
                  <BookOpen className="w-8 h-8 text-zinc-800 mx-auto mb-2" />
                  <p className="text-[11px] text-zinc-600">No docs yet</p>
                  <button onClick={() => setNewPageOpen(true)} className="text-[11px] text-blue-400 hover:text-blue-300 mt-1" data-testid="empty-new-page-btn">
                    Create your first page
                  </button>
                </div>
              )}
            </div>
          </ScrollArea>
        </div>

        {/* Content Area */}
        <div className="flex-1 flex flex-col min-w-0">
          {page ? (
            <>
              {/* Page header */}
              <div className="flex-shrink-0 flex items-center justify-between px-5 py-2.5 border-b border-zinc-800/40">
                <div className="flex items-center gap-2 min-w-0">
                  {editing ? (
                    <Input value={editTitle} onChange={(e) => setEditTitle(e.target.value)}
                      className="bg-transparent border-zinc-700 text-zinc-200 font-semibold h-8 text-sm" data-testid="wiki-edit-title" />
                  ) : (
                    <h3 className="text-sm font-semibold text-zinc-200 truncate">{page.icon ? `${page.icon} ` : ""}{page.title}</h3>
                  )}
                  <span className="text-[10px] text-zinc-600 font-mono">v{page.version}</span>
                  <span className="text-[10px] text-zinc-600">{page.word_count} words</span>
                </div>
                <div className="flex items-center gap-1">
                  {editing ? (
                    <>
                      <Button size="sm" onClick={savePage} disabled={saving} className="bg-emerald-500 hover:bg-emerald-400 text-white h-7 px-3 text-xs" data-testid="wiki-save-btn">
                        <Save className="w-3 h-3 mr-1" />{saving ? "Saving..." : "Save"}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => { setEditing(false); setEditContent(page.content); setEditTitle(page.title); }} className="text-zinc-400 h-7 px-2 text-xs">Cancel</Button>
                    </>
                  ) : (
                    <Button size="sm" variant="ghost" onClick={() => setEditing(true)} className="text-zinc-400 hover:text-zinc-200 h-7 px-2 text-xs" data-testid="wiki-edit-btn">
                      <Pencil className="w-3 h-3 mr-1" />Edit
                    </Button>
                  )}
                  <Button size="sm" variant="ghost" onClick={togglePin} className="text-zinc-400 hover:text-zinc-200 h-7 px-2" title={page.pinned ? "Unpin" : "Pin"}>
                    {page.pinned ? <PinOff className="w-3.5 h-3.5" /> : <Pin className="w-3.5 h-3.5" />}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={loadHistory} className="text-zinc-400 hover:text-zinc-200 h-7 px-2" data-testid="wiki-history-btn">
                    <History className="w-3.5 h-3.5" />
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => deletePage(page.page_id)} className="text-red-400 hover:text-red-300 h-7 px-2" data-testid="wiki-delete-btn">
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </div>
              {/* Editor or Preview */}
              <div className="flex-1 min-h-0">
                {loading ? (
                  <div className="flex items-center justify-center h-full text-zinc-500 text-sm">Loading...</div>
                ) : editing ? (
                  <Editor
                    height="100%"
                    language="markdown"
                    value={editContent}
                    onChange={(v) => setEditContent(v || "")}
                    onMount={(editor) => {
                      editorRef.current = editor;
                      editor.addCommand(2097, savePage);
                    }}
                    theme="vs-dark"
                    options={{
                      fontSize: 14, fontFamily: "'JetBrains Mono', 'Consolas', monospace",
                      wordWrap: "on", lineNumbers: "off", minimap: { enabled: false },
                      scrollBeyondLastLine: false, padding: { top: 16, bottom: 16 },
                      renderLineHighlight: "none", smoothScrolling: true,
                      automaticLayout: true,
                    }}
                  />
                ) : (
                  <ScrollArea className="h-full">
                    <div className="px-8 py-6 max-w-3xl mx-auto prose-invert">
                      {page.content ? (
                        <div className="text-sm text-zinc-300 leading-relaxed" dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(renderMarkdown(page.content)) }} />
                      ) : (
                        <div className="text-center py-12">
                          <FileText className="w-10 h-10 text-zinc-800 mx-auto mb-3" />
                          <p className="text-sm text-zinc-500">Empty page</p>
                          <button onClick={() => setEditing(true)} className="text-xs text-blue-400 hover:text-blue-300 mt-1">Start writing</button>
                        </div>
                      )}
                      {/* Child pages */}
                      {page.children?.length > 0 && (
                        <div className="mt-8 pt-4 border-t border-zinc-800/40">
                          <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold mb-2">Sub-pages</p>
                          <div className="space-y-1">
                            {page.children.map(c => (
                              <button key={c.page_id} onClick={() => selectPage(c.page_id)}
                                className="w-full text-left px-3 py-2 rounded-lg hover:bg-zinc-800/40 text-sm text-zinc-300 flex items-center gap-2">
                                <FileText className="w-3.5 h-3.5 text-blue-400/60" />
                                {c.icon ? `${c.icon} ` : ""}{c.title}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                      {/* Page meta */}
                      <div className="mt-8 pt-4 border-t border-zinc-800/40 flex items-center gap-4 text-[10px] text-zinc-600">
                        <span>Last updated by {page.updated_by_name}</span>
                        <span>{page.updated_at ? new Date(page.updated_at).toLocaleString() : ""}</span>
                        <span>v{page.version}</span>
                      </div>
                    </div>
                  </ScrollArea>
                )}
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <BookOpen className="w-14 h-14 text-zinc-800 mx-auto mb-4" />
                <h3 className="text-base font-semibold text-zinc-400 mb-1">Workspace Docs</h3>
                <p className="text-sm text-zinc-600 max-w-sm">Create and organize documentation for your workspace. AI agents can also read and write docs.</p>
                <Button size="sm" onClick={() => setNewPageOpen(true)} className="mt-4 bg-zinc-100 text-zinc-900 hover:bg-zinc-200" data-testid="empty-create-page-btn">
                  <Plus className="w-3.5 h-3.5 mr-1" /> Create First Page
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* New Page Dialog */}
      <Dialog open={newPageOpen} onOpenChange={setNewPageOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-zinc-100 flex items-center gap-2"><FileText className="w-4 h-4 text-blue-400" />New Page</DialogTitle>
            <DialogDescription className="sr-only">Create a new wiki page</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 mt-2">
            <Input value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="Page title"
              className="bg-zinc-950 border-zinc-800" onKeyDown={(e) => e.key === "Enter" && createPage()} autoFocus data-testid="wiki-new-title" />
            {pages.length > 0 && (
              <select value={newParentId} onChange={(e) => setNewParentId(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-md text-sm text-zinc-300 px-3 py-2" data-testid="wiki-parent-select">
                <option value="">No parent (root page)</option>
                {pages.filter(p => !p.parent_id).map(p => (
                  <option key={p.page_id} value={p.page_id}>{p.title}</option>
                ))}
              </select>
            )}
            <Button onClick={createPage} disabled={!newTitle.trim()} className="w-full bg-zinc-100 text-zinc-900 hover:bg-zinc-200" data-testid="wiki-create-btn">
              Create Page
            </Button>
            <div className="pt-3 border-t border-zinc-800">
              <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold mb-2">Or start from a template</p>
              <div className="grid grid-cols-2 gap-1.5">
                {[
                  { id: "tpl_meeting_notes", name: "Meeting Notes" },
                  { id: "tpl_decision_log", name: "Decision Log" },
                  { id: "tpl_runbook", name: "Runbook" },
                  { id: "tpl_api_docs", name: "API Docs" },
                ].map(t => (
                  <button key={t.id} onClick={() => createFromTemplate(t.id)}
                    className="px-2 py-1.5 rounded-lg bg-zinc-800/30 border border-zinc-800/40 hover:border-zinc-700 text-[11px] text-zinc-300 text-left"
                    data-testid={`wiki-tpl-${t.id}`}>{t.name}</button>
                ))}
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* History Dialog */}
      <Dialog open={historyOpen} onOpenChange={setHistoryOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-lg max-h-[70vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="text-zinc-100 flex items-center gap-2"><History className="w-4 h-4" />Version History</DialogTitle>
            <DialogDescription className="sr-only">Page version history</DialogDescription>
          </DialogHeader>
          <ScrollArea className="flex-1 mt-2">
            {versions.length === 0 ? (
              <p className="text-sm text-zinc-500 text-center py-8">No history</p>
            ) : (
              <div className="space-y-1">
                {versions.map(v => (
                  <button key={v.version_id} onClick={() => restoreVersion(v)}
                    className="w-full text-left px-3 py-2 rounded-lg hover:bg-zinc-800/60 transition-colors" data-testid={`wiki-version-${v.version}`}>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-zinc-300">v{v.version} — {v.title}</span>
                      <span className="text-[10px] text-zinc-600">{v.author_name}</span>
                    </div>
                    <span className="text-[10px] text-zinc-700">{v.created_at ? new Date(v.created_at).toLocaleString() : ""}</span>
                  </button>
                ))}
              </div>
            )}
          </ScrollArea>
        </DialogContent>
      </Dialog>
    <ConfirmDlg />
    </div>
    );
}
