import { useState, useEffect, useCallback, useRef } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Upload, FolderPlus, Trash2, Search, File, Folder, Download, Share2, HardDrive } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/App";

export default function DrivePanel({ workspaceId }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [path, setPath] = useState("/");
  const [storage, setStorage] = useState(null);
  const [search, setSearch] = useState("");
  const fileRef = useRef(null);

  const fetchFiles = useCallback(async () => {
    setLoading(true);
    try {
      const url = search ? `/drive/search?q=${search}&workspace_id=${workspaceId}` : `/drive/list?workspace_id=${workspaceId}&path=${path}`;
      const res = await api.get(url);
      setFiles(res.data.files || []);
    } catch (err) { handleSilent(err, "DrivePanel:op1"); } finally { setLoading(false); }
  }, [workspaceId, path, search]);

  const fetchStorage = useCallback(async () => {
    try { const res = await api.get(`/drive/storage-usage?workspace_id=${workspaceId}`); setStorage(res.data); } catch (err) { handleSilent(err, "DrivePanel:op2"); }
  }, [workspaceId]);

  useEffect(() => { fetchFiles(); fetchStorage(); }, [fetchFiles, fetchStorage]);

  const upload = async (fileList) => {
    for (const file of Array.from(fileList)) {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("workspace_id", workspaceId);
      fd.append("path", path);
      try { await api.post("/drive/upload", fd, { headers: { "Content-Type": "multipart/form-data" } }); toast.success(`Uploaded: ${file.name}`); } catch (err) { handleError(err, "DrivePanel:op1"); }
    }
    fetchFiles(); fetchStorage();
  };

  const createFolder = async () => {
    const name = prompt("Folder name:");
    if (!name) return;
    try { await api.post("/drive/folder", { name, workspace_id: workspaceId, path }); fetchFiles(); toast.success("Folder created"); } catch (err) { handleError(err, "DrivePanel:op2"); }
  };

  const trashFile = async (fileId) => {
    try { await api.delete(`/drive/file/${fileId}`); fetchFiles(); fetchStorage(); toast.success("Moved to trash"); } catch (err) { handleError(err, "DrivePanel:op3"); }
  };

  return (
    <div data-testid="drive-panel">
      {storage && (
        <div className="flex items-center gap-3 p-3 rounded-lg bg-zinc-900/60 border border-zinc-800/40 mb-4">
          <HardDrive className="w-4 h-4 text-zinc-400" />
          <span className="text-xs text-zinc-400">{storage.used_mb}MB / {storage.limit_gb}GB ({storage.usage_pct}%)</span>
          <div className="flex-1 h-1.5 bg-zinc-800 rounded-full"><div className="h-full bg-emerald-500 rounded-full" style={{ width: `${Math.min(storage.usage_pct, 100)}%` }} /></div>
          <span className="text-xs text-zinc-500">{storage.file_count} files</span>
        </div>
      )}
      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-600" />
          <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search files..." className="w-full bg-zinc-900/60 border border-zinc-800/60 rounded-lg pl-9 pr-3 py-2 text-sm text-zinc-300 placeholder:text-zinc-600 focus:outline-none" data-testid="drive-search" />
        </div>
        <Button onClick={createFolder} variant="outline" size="sm" className="border-zinc-700 text-zinc-300 gap-1"><FolderPlus className="w-3.5 h-3.5" /> Folder</Button>
        <Button onClick={() => fileRef.current?.click()} size="sm" className="bg-emerald-500 hover:bg-emerald-400 text-white gap-1"><Upload className="w-3.5 h-3.5" /> Upload</Button>
        <input ref={fileRef} type="file" className="hidden" multiple onChange={(e) => upload(e.target.files)} />
      </div>
      {path !== "/" && <button onClick={() => setPath("/")} className="text-xs text-zinc-500 hover:text-zinc-300 mb-2">← Back to root</button>}
      {loading ? <div className="text-center py-12 text-zinc-500">Loading...</div> : files.length === 0 ? (
        <div className="text-center py-16 border-2 border-dashed border-zinc-800 rounded-xl" onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); upload(e.dataTransfer.files); }}>
          <Upload className="w-10 h-10 text-zinc-700 mx-auto mb-3" /><p className="text-zinc-400">Drop files here or click Upload</p>
        </div>
      ) : (
        <div className="space-y-1">
          {files.map(f => (
            <div key={f.file_id} className="flex items-center gap-3 p-2.5 rounded-lg bg-zinc-900/40 border border-zinc-800/40 hover:border-zinc-700 group" onClick={() => { if (f.type === "folder") setPath(f.path + f.name + "/"); }} data-testid={`drive-file-${f.file_id}`}>
              {f.type === "folder" ? <Folder className="w-5 h-5 text-amber-400" /> : <File className="w-5 h-5 text-zinc-500" />}
              <div className="flex-1 min-w-0"><p className="text-sm text-zinc-200 truncate">{f.name}</p>{f.size && <span className="text-[10px] text-zinc-600">{(f.size / 1024).toFixed(1)}KB</span>}</div>
              <div className="flex gap-1 opacity-0 group-hover:opacity-100">
                <button onClick={(e) => { e.stopPropagation(); trashFile(f.file_id); }} className="p-1 rounded hover:bg-zinc-800 text-zinc-600 hover:text-red-400"><Trash2 className="w-3 h-3" /></button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
