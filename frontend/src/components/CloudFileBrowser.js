import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Cloud, FolderOpen, File, Download, Search, ArrowLeft, Loader2, RefreshCw } from "lucide-react";
import { api } from "@/App";
import { toast } from "sonner";

export default function CloudFileBrowser({ workspaceId }) {
  const [connections, setConnections] = useState([]);
  const [selectedConn, setSelectedConn] = useState(null);
  const [files, setFiles] = useState([]);
  const [path, setPath] = useState("");
  const [pathHistory, setPathHistory] = useState([""]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(null);
  const [connsLoading, setConnsLoading] = useState(true);

  useEffect(() => {
    api.get("/cloud-storage/connections").then(r => {
      const active = (r.data || []).filter(c => c.status === "active");
      setConnections(active);
    }).catch(() => {}).finally(() => setConnsLoading(false));
  }, []);

  const browse = async (connId, browsePath = "", searchQuery = "") => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (browsePath) params.set("path", browsePath);
      if (searchQuery) params.set("search", searchQuery);
      const res = await api.get(`/cloud-storage/connections/${connId}/files?${params}`);
      setFiles(res.data?.files || res.data || []);
      setPath(browsePath);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to browse files");
      setFiles([]);
    }
    setLoading(false);
  };

  const selectConnection = (conn) => {
    setSelectedConn(conn);
    setPath("");
    setPathHistory([""]);
    browse(conn.connection_id);
  };

  const openFolder = (folder) => {
    const newPath = folder.id || folder.path || folder.name;
    setPathHistory(prev => [...prev, newPath]);
    browse(selectedConn.connection_id, newPath);
  };

  const goBack = () => {
    if (pathHistory.length <= 1) return;
    const newHistory = pathHistory.slice(0, -1);
    setPathHistory(newHistory);
    browse(selectedConn.connection_id, newHistory[newHistory.length - 1]);
  };

  const importFile = async (file) => {
    if (!selectedConn || !workspaceId) return;
    setImporting(file.id || file.name);
    try {
      await api.post(`/cloud-storage/connections/${selectedConn.connection_id}/import`, {
        file_id: file.id || file.path,
        file_name: file.name,
        workspace_id: workspaceId,
      });
      toast.success(`Imported: ${file.name}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Import failed");
    }
    setImporting(null);
  };

  const doSearch = () => {
    if (selectedConn && search.trim()) {
      browse(selectedConn.connection_id, "", search.trim());
    }
  };

  const formatSize = (bytes) => {
    if (!bytes) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
  };

  if (connsLoading) return <div className="p-4"><Loader2 className="w-4 h-4 animate-spin text-zinc-500" /></div>;

  return (
    <div className="flex flex-col h-full" data-testid="cloud-file-browser">
      {!selectedConn ? (
        <div className="p-4">
          <h3 className="text-sm font-semibold text-zinc-300 mb-3 flex items-center gap-2">
            <Cloud className="w-4 h-4 text-cyan-400" /> Cloud Storage
          </h3>
          {connections.length === 0 ? (
            <p className="text-xs text-zinc-500">No cloud storage connected. Go to Settings to connect Google Drive, Dropbox, OneDrive, or Box.</p>
          ) : (
            <div className="space-y-2">
              {connections.map(conn => (
                <button key={conn.connection_id} onClick={() => selectConnection(conn)}
                  className="w-full text-left p-3 rounded-lg border border-zinc-800/40 bg-zinc-900/30 hover:border-zinc-700 transition-colors"
                  data-testid={`cloud-conn-${conn.connection_id}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Cloud className="w-4 h-4 text-cyan-400" />
                      <span className="text-sm text-zinc-300">{conn.provider}</span>
                    </div>
                    <Badge className="text-[8px] bg-emerald-500/20 text-emerald-400">Connected</Badge>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      ) : (
        <>
          {/* Header */}
          <div className="px-4 py-2 border-b border-zinc-800/40 flex items-center gap-2">
            <Button size="sm" variant="ghost" onClick={() => { setSelectedConn(null); setFiles([]); }} className="h-7 px-2 text-zinc-400">
              <ArrowLeft className="w-3.5 h-3.5" />
            </Button>
            <Cloud className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-xs font-medium text-zinc-300">{selectedConn.provider}</span>
            {pathHistory.length > 1 && (
              <Button size="sm" variant="ghost" onClick={goBack} className="h-6 px-1.5 text-zinc-500 text-[10px]">
                <ArrowLeft className="w-3 h-3 mr-1" /> Back
              </Button>
            )}
            <div className="flex-1" />
            <Button size="sm" variant="ghost" onClick={() => browse(selectedConn.connection_id, path)} className="h-7 px-2 text-zinc-500">
              <RefreshCw className="w-3 h-3" />
            </Button>
          </div>

          {/* Search */}
          <div className="px-4 py-2 flex gap-2">
            <Input value={search} onChange={e => setSearch(e.target.value)} onKeyDown={e => e.key === "Enter" && doSearch()}
              placeholder="Search files..." className="bg-zinc-950 border-zinc-800 h-8 text-xs" />
            <Button size="sm" onClick={doSearch} className="h-8 px-3 bg-zinc-800 text-zinc-300"><Search className="w-3 h-3" /></Button>
          </div>

          {/* Files */}
          <ScrollArea className="flex-1 px-4">
            {loading ? (
              <div className="py-8 text-center"><Loader2 className="w-4 h-4 animate-spin text-zinc-500 mx-auto" /></div>
            ) : files.length === 0 ? (
              <p className="text-xs text-zinc-500 text-center py-8">No files found</p>
            ) : (
              <div className="space-y-1 pb-4">
                {files.map((file, i) => (
                  <div key={file.id || file.name || i}
                    className="flex items-center gap-3 p-2 rounded-lg hover:bg-zinc-800/30 transition-colors group">
                    {file.is_folder || file.type === "folder" ? (
                      <button onClick={() => openFolder(file)} className="flex items-center gap-3 flex-1 min-w-0 text-left">
                        <FolderOpen className="w-4 h-4 text-amber-400 flex-shrink-0" />
                        <span className="text-xs text-zinc-300 truncate">{file.name}</span>
                      </button>
                    ) : (
                      <>
                        <File className="w-4 h-4 text-zinc-500 flex-shrink-0" />
                        <span className="text-xs text-zinc-300 truncate flex-1">{file.name}</span>
                        <span className="text-[10px] text-zinc-600">{formatSize(file.size)}</span>
                        <Button size="sm" onClick={() => importFile(file)} disabled={importing === (file.id || file.name)}
                          className="h-6 px-2 text-[10px] bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30 opacity-0 group-hover:opacity-100 transition-opacity">
                          {importing === (file.id || file.name) ? <Loader2 className="w-3 h-3 animate-spin" /> : <><Download className="w-3 h-3 mr-1" /> Import</>}
                        </Button>
                      </>
                    )}
                  </div>
                ))}
              </div>
            )}
          </ScrollArea>
        </>
      )}
    </div>
  );
}
