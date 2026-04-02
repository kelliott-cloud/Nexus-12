import { useState, useEffect, useCallback, useRef } from "react";
import { useConfirm } from "@/components/ConfirmDialog";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Search, Upload, Trash2, FolderOpen, FileText, Image, Video, Volume2, File, Eye, Download, Tag, Pencil } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/App";

const PREVIEW_ICONS = { image: Image, pdf: FileText, video: Video, audio: Volume2, text: FileText, document: FileText, none: File };

export default function RepositoryPanel({ orgId }) {
  const { confirm: confirmAction, ConfirmDialog: ConfirmDlg } = useConfirm();
  const [files, setFiles] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [folders, setFolders] = useState([]);
  const [selectedFolder, setSelectedFolder] = useState("");
  const [previewItem, setPreviewItem] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const fileInputRef = useRef(null);

  const fetchFiles = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.append("search", search);
      if (selectedFolder) params.append("folder", selectedFolder);
      const res = await api.get(`/orgs/${orgId}/repository?${params}`);
      setFiles(res.data.files || []);
      setTotal(res.data.total || 0);
    } catch (err) { handleSilent(err, "RepositoryPanel:op1"); } finally { setLoading(false); }
  }, [orgId, search, selectedFolder]);

  const fetchFolders = useCallback(async () => {
    try { const res = await api.get(`/orgs/${orgId}/repository/folders`); setFolders(res.data.folders || []); } catch (err) { handleSilent(err, "RepositoryPanel:op2"); }
  }, [orgId]);

  useEffect(() => { fetchFiles(); fetchFolders(); }, [fetchFiles, fetchFolders]);

  const handleUpload = async (fileList) => {
    for (const file of Array.from(fileList)) {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("folder", selectedFolder || "/");
      try { await api.post(`/orgs/${orgId}/repository/upload`, formData, { headers: { "Content-Type": "multipart/form-data" } }); toast.success(`Uploaded: ${file.name}`); } catch (err) { toast.error(`Failed: ${file.name}`); }
    }
    fetchFiles(); fetchFolders();
  };

  const openPreview = async (file) => {
    setPreviewItem(file); setPreviewData(null);
    try { const res = await api.get(`/repository/${file.file_id}/preview`); setPreviewData(res.data.preview); } catch (err) { handleSilent(err, "RepositoryPanel:op3"); }
  };

  const deleteFile = async (fileId) => {
    const _ok = await confirmAction("Delete File", "Delete this repository file?"); if (!_ok) return;
    await api.delete(`/repository/${fileId}`); fetchFiles(); fetchFolders();
    if (previewItem?.file_id === fileId) setPreviewItem(null);
    toast.success("Deleted");
  };

  return (
    <div className="flex-1 flex min-h-0" data-testid="repository-panel">
      {/* Sidebar — folders */}
      <div className="w-44 flex-shrink-0 border-r border-zinc-800/40 p-3 space-y-1 overflow-y-auto">
        <p className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-2">Folders</p>
        <button onClick={() => setSelectedFolder("")} className={`w-full text-left px-2 py-1.5 rounded text-xs ${!selectedFolder ? "bg-zinc-800 text-zinc-200" : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"}`} data-testid="folder-all">All Files ({total})</button>
        {folders.map(f => (
          <button key={f.folder} onClick={() => setSelectedFolder(f.folder)} className={`w-full text-left px-2 py-1.5 rounded text-xs flex items-center justify-between ${selectedFolder === f.folder ? "bg-zinc-800 text-zinc-200" : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"}`}>
            <span className="flex items-center gap-1.5"><FolderOpen className="w-3 h-3" />{f.folder}</span>
            <Badge className="text-[8px] bg-zinc-700 text-zinc-400">{f.count}</Badge>
          </button>
        ))}
      </div>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="px-4 py-3 border-b border-zinc-800/40 flex items-center gap-3">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-600" />
            <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search files..." className="w-full bg-zinc-900/60 border border-zinc-800/60 rounded-lg pl-9 pr-3 py-2 text-sm text-zinc-300 placeholder:text-zinc-600 focus:outline-none" data-testid="repo-search" />
          </div>
          <Button onClick={() => fileInputRef.current?.click()} size="sm" className="bg-emerald-500 hover:bg-emerald-400 text-white gap-1.5" data-testid="repo-upload-btn"><Upload className="w-3.5 h-3.5" /> Upload</Button>
          <input ref={fileInputRef} type="file" className="hidden" multiple onChange={(e) => handleUpload(e.target.files)} />
        </div>

        <div className="flex-1 overflow-y-auto p-4" onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); handleUpload(e.dataTransfer.files); }}>
          {loading ? <div className="text-center py-12 text-zinc-500">Loading...</div> : files.length === 0 ? (
            <div className="text-center py-16 border-2 border-dashed border-zinc-800 rounded-xl"><Upload className="w-10 h-10 text-zinc-700 mx-auto mb-3" /><p className="text-zinc-400">Drop files here or click Upload</p></div>
          ) : (
            <div className="space-y-1" data-testid="repo-file-list">
              {files.map(f => {
                const Icon = PREVIEW_ICONS[f.preview_type] || File;
                return (
                  <div key={f.file_id} className="flex items-center gap-3 p-2.5 rounded-lg bg-zinc-900/40 border border-zinc-800/40 hover:border-zinc-700 cursor-pointer group" onClick={() => openPreview(f)} data-testid={`repo-file-${f.file_id}`}>
                    <Icon className="w-5 h-5 text-zinc-500 flex-shrink-0" />
                    <div className="flex-1 min-w-0"><p className="text-sm text-zinc-200 truncate">{f.filename}</p><div className="flex items-center gap-2 text-[10px] text-zinc-600"><span>{(f.size / 1024).toFixed(1)}KB</span><span>{f.preview_type}</span><span>{f.folder}</span></div></div>
                    <div className="flex gap-1 opacity-0 group-hover:opacity-100"><button onClick={(e) => { e.stopPropagation(); deleteFile(f.file_id); }} className="p-1 rounded hover:bg-zinc-800 text-zinc-600 hover:text-red-400"><Trash2 className="w-3 h-3" /></button></div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Preview dialog */}
      <Dialog open={!!previewItem} onOpenChange={(open) => { if (!open) { setPreviewItem(null); setPreviewData(null); } }}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-2xl">
          <DialogHeader><DialogTitle className="text-zinc-100 text-sm">{previewItem?.filename}</DialogTitle></DialogHeader>
          {previewData?.type === "image" && <img src={previewData.data_url} alt="" className="w-full rounded-lg max-h-[400px] object-contain" />}
          {previewData?.type === "pdf" && <iframe src={previewData.data_url} className="w-full h-[400px] rounded-lg" title="PDF Preview" />}
          {previewData?.type === "video" && <video controls src={previewData.data_url} className="w-full rounded-lg" />}
          {previewData?.type === "audio" && <audio controls src={previewData.data_url} className="w-full" />}
          {previewData?.type === "text" && <pre className="bg-zinc-800/50 rounded-lg p-4 text-xs text-zinc-300 max-h-[400px] overflow-auto whitespace-pre-wrap font-mono">{previewData.text}</pre>}
          {previewData?.type === "unsupported" && <p className="text-sm text-zinc-500 py-8 text-center">Preview not available for this file type</p>}
          {!previewData && <div className="h-32 bg-zinc-800 rounded-lg flex items-center justify-center text-zinc-500">Loading...</div>}
          <div className="flex items-center justify-between text-xs text-zinc-500">
            <span>{previewItem?.ext} · {previewItem?.size ? `${(previewItem.size / 1024).toFixed(1)}KB` : ""} · {previewItem?.folder}</span>
            <Button variant="outline" size="sm" onClick={() => deleteFile(previewItem?.file_id)} className="border-zinc-700 text-red-400 gap-1"><Trash2 className="w-3 h-3" />Delete</Button>
          </div>
        </DialogContent>
      </Dialog>
    <ConfirmDlg />
    </div>
    );
}
