import { useState, useEffect, useCallback } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { useConfirm } from "@/components/ConfirmDialog";
import { api } from "@/App";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  Search, Pin, PinOff, Tag, Trash2, FileText, Code, FileJson,
  FileType, Plus, X, ChevronRight, Clock, Edit3, Eye, RotateCcw, GitCompare,
  Image, Paperclip, Download, Upload
} from "lucide-react";

const TYPE_ICONS = {
  text: FileText,
  json: FileJson,
  code: Code,
  markdown: FileType,
  image: Image,
};

const TYPE_COLORS = {
  text: "bg-blue-600/20 text-blue-400",
  json: "bg-amber-600/20 text-amber-400",
  code: "bg-emerald-600/20 text-emerald-400",
  markdown: "bg-purple-600/20 text-purple-400",
  image: "bg-pink-600/20 text-pink-400",
};

export default function ArtifactPanel({ workspaceId }) {
  const { confirm: confirmAction, ConfirmDialog: ConfirmDlg } = useConfirm();
  const [artifacts, setArtifacts] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filterType, setFilterType] = useState("");
  const [filterPinned, setFilterPinned] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [selectedArtifact, setSelectedArtifact] = useState(null);
  const [newName, setNewName] = useState("");
  const [newContent, setNewContent] = useState("");
  const [newType, setNewType] = useState("text");
  const [newTags, setNewTags] = useState("");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState("");

  const fetchArtifacts = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.append("search", search);
      if (filterType) params.append("content_type", filterType);
      if (filterPinned) params.append("pinned", "true");
      const res = await api.get(`/workspaces/${workspaceId}/artifacts?${params}`);
      setArtifacts(res.data.artifacts || []);
      setTotal(res.data.total || 0);
    } catch (err) {
      console.error("Failed to fetch artifacts:", err);
    } finally {
      setLoading(false);
    }
  }, [workspaceId, search, filterType, filterPinned]);

  useEffect(() => {
    fetchArtifacts();
  }, [fetchArtifacts]);

  const createArtifact = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const tags = newTags.split(",").map((t) => t.trim()).filter(Boolean);
      const res = await api.post(`/workspaces/${workspaceId}/artifacts`, {
        name: newName, content: newContent, content_type: newType, tags,
      });
      setArtifacts((prev) => [res.data, ...prev]);
      setShowCreate(false);
      setNewName(""); setNewContent(""); setNewType("text"); setNewTags("");
      toast.success("Artifact created");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to create artifact");
    } finally {
      setCreating(false);
    }
  };

  const viewArtifact = async (artifactId) => {
    try {
      const res = await api.get(`/artifacts/${artifactId}`);
      setSelectedArtifact(res.data);
      setEditContent(res.data.content || "");
    } catch (err) { handleError(err, "ArtifactPanel:op1"); }
  };

  const togglePin = async (artifactId) => {
    try {
      const res = await api.post(`/artifacts/${artifactId}/pin`);
      setArtifacts((prev) =>
        prev.map((a) => (a.artifact_id === artifactId ? { ...a, pinned: res.data.pinned } : a))
      );
      toast.success(res.data.pinned ? "Pinned" : "Unpinned");
    } catch (err) { handleError(err, "ArtifactPanel:op2"); }
  };

  const saveEdit = async () => {
    if (!selectedArtifact) return;
    try {
      const res = await api.put(`/artifacts/${selectedArtifact.artifact_id}`, {
        content: editContent,
      });
      setSelectedArtifact((prev) => ({ ...prev, ...res.data, versions: prev.versions }));
      setArtifacts((prev) =>
        prev.map((a) => (a.artifact_id === selectedArtifact.artifact_id ? { ...a, ...res.data } : a))
      );
      setEditing(false);
      toast.success(`Saved as version ${res.data.version}`);
    } catch (err) { handleError(err, "ArtifactPanel:op3"); }
  };

  const deleteArtifact = async (artifactId) => {
    try {
      await api.delete(`/artifacts/${artifactId}`);
      setArtifacts((prev) => prev.filter((a) => a.artifact_id !== artifactId));
      if (selectedArtifact?.artifact_id === artifactId) setSelectedArtifact(null);
      toast.success("Artifact deleted");
    } catch (err) { handleError(err, "ArtifactPanel:op4"); }
  };

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-zinc-100" data-testid="artifacts-heading">Artifacts</h2>
            <p className="text-sm text-zinc-500 mt-1">Manage versioned outputs, documents, and code snippets</p>
          </div>
          <Button size="sm" onClick={() => setShowCreate(true)} className="bg-zinc-100 text-zinc-900 hover:bg-zinc-200" data-testid="create-artifact-btn">
            <Plus className="w-4 h-4 mr-2" />
            New Artifact
          </Button>
        </div>

        {/* Search & Filters */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <Input placeholder="Search artifacts..." value={search} onChange={(e) => setSearch(e.target.value)}
              className="pl-9 bg-zinc-800/60 border-zinc-700 text-zinc-200 text-sm" data-testid="artifact-search" />
          </div>
          <select value={filterType} onChange={(e) => setFilterType(e.target.value)}
            className="bg-zinc-800/60 border border-zinc-700 rounded-md px-3 py-2 text-xs text-zinc-300" data-testid="artifact-type-filter">
            <option value="">All Types</option>
            <option value="text">Text</option>
            <option value="json">JSON</option>
            <option value="code">Code</option>
            <option value="markdown">Markdown</option>
          </select>
          <button
            onClick={() => setFilterPinned(!filterPinned)}
            className={`flex items-center gap-1 px-3 py-2 text-xs rounded-md border transition-colors ${
              filterPinned ? "bg-amber-600/20 border-amber-600/40 text-amber-400" : "border-zinc-700 text-zinc-500 hover:text-zinc-300"
            }`}
            data-testid="filter-pinned"
          >
            <Pin className="w-3 h-3" />
            Pinned
          </button>
        </div>

        {/* Artifacts List */}
        {loading ? (
          <div className="flex items-center justify-center py-20 text-zinc-500">Loading...</div>
        ) : artifacts.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-zinc-500 space-y-3" data-testid="empty-artifacts">
            <FileText className="w-10 h-10 text-zinc-600" />
            <p className="text-zinc-400">No artifacts yet</p>
            <p className="text-sm">Create artifacts to store workflow outputs and documents</p>
          </div>
        ) : (
          <div className="space-y-2" data-testid="artifacts-list">
            {artifacts.map((art) => {
              const TypeIcon = TYPE_ICONS[art.content_type] || FileText;
              return (
                <div
                  key={art.artifact_id}
                  className="bg-zinc-900/60 border border-zinc-800/60 rounded-lg p-3 hover:border-zinc-700 transition-colors cursor-pointer group flex items-center gap-3"
                  onClick={() => viewArtifact(art.artifact_id)}
                  data-testid={`artifact-row-${art.artifact_id}`}
                >
                  <TypeIcon className="w-5 h-5 text-zinc-500 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm text-zinc-200 truncate">{art.name}</span>
                      {art.pinned && <Pin className="w-3 h-3 text-amber-400 shrink-0" />}
                      <span className={`text-[10px] px-1.5 py-0.5 rounded ${TYPE_COLORS[art.content_type] || "bg-zinc-700 text-zinc-400"}`}>
                        {art.content_type}
                      </span>
                      <span className="text-[10px] text-zinc-600">v{art.version}</span>
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      {art.tags?.map((tag) => (
                        <span key={tag} className="text-[10px] text-zinc-600 bg-zinc-800 px-1.5 py-0.5 rounded">{tag}</span>
                      ))}
                    </div>
                  </div>
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button onClick={(e) => { e.stopPropagation(); togglePin(art.artifact_id); }}
                      className="p-1.5 rounded hover:bg-zinc-800 text-zinc-500 hover:text-amber-400" data-testid={`pin-${art.artifact_id}`}>
                      {art.pinned ? <PinOff className="w-3.5 h-3.5" /> : <Pin className="w-3.5 h-3.5" />}
                    </button>
                    <button onClick={(e) => { e.stopPropagation(); deleteArtifact(art.artifact_id); }}
                      className="p-1.5 rounded hover:bg-zinc-800 text-zinc-500 hover:text-red-400" data-testid={`delete-artifact-${art.artifact_id}`}>
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <ChevronRight className="w-3 h-3 text-zinc-700 group-hover:text-zinc-500 shrink-0" />
                </div>
              );
            })}
          </div>
        )}
        <p className="text-xs text-zinc-600 text-center">{total} artifacts</p>

        {/* Create Dialog */}
        <Dialog open={showCreate} onOpenChange={setShowCreate}>
          <DialogContent className="bg-zinc-900 border-zinc-800 max-w-lg">
            <DialogHeader>
              <DialogTitle className="text-zinc-100">New Artifact</DialogTitle>
              <DialogDescription className="text-zinc-500 text-sm">Store a document, code snippet, or workflow output.</DialogDescription>
            </DialogHeader>
            <div className="space-y-3 mt-2">
              <Input placeholder="Name" value={newName} onChange={(e) => setNewName(e.target.value)}
                className="bg-zinc-800 border-zinc-700 text-zinc-200" data-testid="artifact-name-input" />
              <select value={newType} onChange={(e) => setNewType(e.target.value)}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200" data-testid="artifact-type-input">
                <option value="text">Text</option>
                <option value="json">JSON</option>
                <option value="code">Code</option>
                <option value="markdown">Markdown</option>
              </select>
              <textarea value={newContent} onChange={(e) => setNewContent(e.target.value)}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200 min-h-[120px] font-mono resize-y"
                placeholder="Content..." data-testid="artifact-content-input" />
              <Input placeholder="Tags (comma-separated)" value={newTags} onChange={(e) => setNewTags(e.target.value)}
                className="bg-zinc-800 border-zinc-700 text-zinc-200" data-testid="artifact-tags-input" />
              <Button onClick={createArtifact} disabled={!newName.trim() || creating}
                className="w-full bg-zinc-100 text-zinc-900 hover:bg-zinc-200" data-testid="artifact-submit-btn">
                {creating ? "Creating..." : "Create Artifact"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>

        {/* Detail Dialog */}
        <Dialog open={!!selectedArtifact} onOpenChange={(open) => { if (!open) { setSelectedArtifact(null); setEditing(false); } }}>
          <DialogContent className="bg-zinc-900 border-zinc-800 max-w-2xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="text-zinc-100 flex items-center gap-2">
                {selectedArtifact?.name}
                <span className="text-[10px] text-zinc-500 font-normal">v{selectedArtifact?.version}</span>
              </DialogTitle>
              <DialogDescription className="sr-only">Artifact details and version history</DialogDescription>
            </DialogHeader>
            {selectedArtifact && (
              <div className="space-y-4 mt-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`text-xs px-2 py-0.5 rounded ${TYPE_COLORS[selectedArtifact.content_type] || "bg-zinc-700 text-zinc-400"}`}>
                    {selectedArtifact.content_type}
                  </span>
                  {selectedArtifact.tags?.map((tag) => (
                    <span key={tag} className="text-xs text-zinc-500 bg-zinc-800 px-2 py-0.5 rounded">{tag}</span>
                  ))}
                  {selectedArtifact.pinned && <Pin className="w-3 h-3 text-amber-400" />}
                </div>

                {/* Content */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium text-zinc-400">Content</span>
                    <Button variant="ghost" size="sm" onClick={() => { setEditing(!editing); setEditContent(selectedArtifact.content || ""); }}
                      className="text-xs text-zinc-500 hover:text-zinc-300 h-7" data-testid="edit-artifact-btn">
                      {editing ? <Eye className="w-3 h-3 mr-1" /> : <Edit3 className="w-3 h-3 mr-1" />}
                      {editing ? "Preview" : "Edit"}
                    </Button>
                  </div>
                  {editing ? (
                    <>
                      <textarea value={editContent} onChange={(e) => setEditContent(e.target.value)}
                        className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200 min-h-[200px] font-mono resize-y"
                        data-testid="edit-artifact-content" />
                      <Button onClick={saveEdit} className="mt-2 bg-zinc-100 text-zinc-900 hover:bg-zinc-200 text-sm" data-testid="save-artifact-edit-btn">
                        Save as v{selectedArtifact.version + 1}
                      </Button>
                    </>
                  ) : selectedArtifact.content_type === "image" && selectedArtifact.file_url ? (
                    <div className="rounded-lg overflow-hidden border border-zinc-800" data-testid="artifact-image-preview">
                      <img src={selectedArtifact.file_url} alt={selectedArtifact.name} className="w-full max-h-[400px] object-contain bg-zinc-800" />
                    </div>
                  ) : selectedArtifact.content_type === "code" ? (
                    <div className="relative group">
                      <button onClick={() => { navigator.clipboard.writeText(selectedArtifact.content || ""); toast.success("Copied"); }}
                        className="absolute top-2 right-2 px-2 py-1 rounded bg-zinc-700 text-[10px] text-zinc-300 opacity-0 group-hover:opacity-100 transition-opacity">Copy</button>
                      <pre className="bg-black/40 border border-zinc-800/40 rounded-lg p-4 text-sm text-zinc-300 overflow-auto max-h-[400px] font-mono whitespace-pre-wrap" data-testid="artifact-content-display">
                        {selectedArtifact.content || "(empty)"}
                      </pre>
                    </div>
                  ) : (
                    <pre className="bg-zinc-800/50 rounded-md p-3 text-sm text-zinc-300 overflow-auto max-h-[300px] font-mono whitespace-pre-wrap" data-testid="artifact-content-display">
                      {selectedArtifact.content || "(empty)"}
                    </pre>
                  )}
                </div>

                {/* Version History */}
                {selectedArtifact.versions?.length > 0 && (
                  <div>
                    <span className="text-xs font-medium text-zinc-400 mb-2 block">Version History ({selectedArtifact.versions.length})</span>
                    <div className="space-y-1">
                      {selectedArtifact.versions.map((v) => (
                        <div key={v.version} className="flex items-center gap-3 text-xs text-zinc-500 py-1.5 border-b border-zinc-800/30 group">
                          <span className="text-zinc-300 font-medium w-8">v{v.version}</span>
                          <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{new Date(v.created_at).toLocaleString()}</span>
                          {v.change_summary && (
                            <span className="text-[10px] text-zinc-600">
                              <span className="text-emerald-500">+{v.change_summary.chars_added}</span>
                              <span className="mx-0.5">/</span>
                              <span className="text-red-400">-{v.change_summary.chars_removed}</span>
                            </span>
                          )}
                          {v.restored_from && (
                            <span className="text-[10px] text-amber-400">restored from v{v.restored_from}</span>
                          )}
                          <div className="ml-auto flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            {v.version !== selectedArtifact.version && (
                              <button
                                onClick={async () => {
                                  try {
                                    const res = await api.get(`/artifacts/${selectedArtifact.artifact_id}/diff?v1=${v.version}&v2=${selectedArtifact.version}`);
                                    toast.info(`v${v.version} → v${selectedArtifact.version}: +${res.data.additions} -${res.data.deletions} lines`);
                                  } catch (err) { handleError(err, "ArtifactPanel:op5"); }
                                }}
                                className="p-1 rounded hover:bg-zinc-800 text-zinc-600 hover:text-zinc-300"
                                title="Compare with current"
                                data-testid={`diff-v${v.version}`}
                              >
                                <GitCompare className="w-3 h-3" />
                              </button>
                            )}
                            {v.version !== selectedArtifact.version && (
                              <button
                                onClick={async () => {
                                  const _ok = await confirmAction("Restore Version", `Restore artifact to version ${v.version}?`); if (!_ok) return;
                                  try {
                                    await api.post(`/artifacts/${selectedArtifact.artifact_id}/restore/${v.version}`);
                                    toast.success(`Restored to v${v.version}`);
                                    viewArtifact(selectedArtifact.artifact_id);
                                    fetchArtifacts();
                                  } catch (err) { handleError(err, "ArtifactPanel:op6"); }
                                }}
                                className="p-1 rounded hover:bg-zinc-800 text-zinc-600 hover:text-amber-400"
                                title="Restore this version"
                                data-testid={`restore-v${v.version}`}
                              >
                                <RotateCcw className="w-3 h-3" />
                              </button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Attachments */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium text-zinc-400 flex items-center gap-1"><Paperclip className="w-3 h-3" /> Attachments ({selectedArtifact.attachments?.length || 0})</span>
                    <label className="flex items-center gap-1 px-2 py-1 rounded-md text-[10px] text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 cursor-pointer transition-colors" data-testid="add-attachment-btn">
                      <Upload className="w-3 h-3" /> Add File
                      <input type="file" className="hidden" onChange={async (e) => {
                        const file = e.target.files?.[0];
                        if (!file || !selectedArtifact) return;
                        const formData = new FormData();
                        formData.append("file", file);
                        try {
                          await api.post(`/artifacts/${selectedArtifact.artifact_id}/attachments`, formData, { headers: { "Content-Type": "multipart/form-data" } });
                          toast.success(`Attached "${file.name}"`);
                          viewArtifact(selectedArtifact.artifact_id);
                        } catch (err) { handleError(err, "ArtifactPanel:op7"); }
                        e.target.value = "";
                      }} />
                    </label>
                  </div>
                  {selectedArtifact.attachments?.length > 0 && (
                    <div className="space-y-1.5">
                      {selectedArtifact.attachments.map((att) => {
                        const isImage = att.mime_type?.startsWith("image/");
                        return (
                          <div key={att.attachment_id} className="flex items-center gap-2 p-2 rounded-lg bg-zinc-800/40 border border-zinc-800/30 group" data-testid={`attachment-${att.attachment_id}`}>
                            {isImage ? <Image className="w-4 h-4 text-pink-400 flex-shrink-0" /> : <Paperclip className="w-4 h-4 text-zinc-500 flex-shrink-0" />}
                            <div className="flex-1 min-w-0">
                              <span className="text-xs text-zinc-300 truncate block">{att.filename}</span>
                              <span className="text-[10px] text-zinc-600">{att.size ? `${(att.size / 1024).toFixed(1)}KB` : ""} {att.mime_type}</span>
                            </div>
                            <button
                              onClick={async () => {
                                try {
                                  const res = await api.get(`/artifacts/${selectedArtifact.artifact_id}/attachments/${att.attachment_id}`);
                                  if (res.data.data) {
                                    const link = document.createElement("a");
                                    link.href = `data:${att.mime_type};base64,${res.data.data}`;
                                    link.download = att.filename;
                                    link.click();
                                  }
                                } catch (err) { handleError(err, "ArtifactPanel:op8"); }
                              }}
                              className="p-1 rounded text-zinc-600 hover:text-zinc-300 opacity-0 group-hover:opacity-100 transition-opacity"
                              title="Download"
                            >
                              <Download className="w-3 h-3" />
                            </button>
                            <button
                              onClick={async () => {
                                try {
                                  await api.delete(`/artifacts/${selectedArtifact.artifact_id}/attachments/${att.attachment_id}`);
                                  toast.success("Removed");
                                  viewArtifact(selectedArtifact.artifact_id);
                                } catch (err) { handleError(err, "ArtifactPanel:op9"); }
                              }}
                              className="p-1 rounded text-zinc-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                              title="Remove"
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    <ConfirmDlg />
    </div>
    );
}
