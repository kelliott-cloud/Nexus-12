import { useState, useEffect, useCallback, useRef } from "react";
import { useConfirm } from "@/components/ConfirmDialog";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import {
  Search, Upload, Trash2, Tag, FolderOpen, Video, Volume2, Image,
  Download, MoreVertical, Grid3X3, List, Star, Clock, Filter, X,
  Share2, Eye, Pencil, ChevronRight, BarChart3, HardDrive
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/App";
import SocialPublishModal from "@/components/SocialPublishModal";

const TYPE_ICONS = { video: Video, audio: Volume2, image: Image };
const TYPE_COLORS = { video: "text-red-400 bg-red-500/10", audio: "text-violet-400 bg-violet-500/10", image: "text-pink-400 bg-pink-500/10" };

export default function MediaLibraryPanel({ workspaceId }) {
  const { confirm: confirmAction, ConfirmDialog: ConfirmDlg } = useConfirm();
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [viewMode, setViewMode] = useState("grid");
  const [smartFolders, setSmartFolders] = useState([]);
  const [storage, setStorage] = useState(null);
  const [selected, setSelected] = useState(new Set());
  const [detailItem, setDetailItem] = useState(null);
  const [detailData, setDetailData] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [publishOpen, setPublishOpen] = useState(false);
  const [publishMediaId, setPublishMediaId] = useState("");
  const [publishMediaName, setPublishMediaName] = useState("");
  const fileInputRef = useRef(null);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.append("search", search);
      if (typeFilter) params.append("media_type", typeFilter);
      const res = await api.get(`/workspaces/${workspaceId}/media?${params}`);
      setItems(res.data.items || []);
      setTotal(res.data.total || 0);
    } catch (err) { handleSilent(err, "MediaLibrary:op1"); } finally { setLoading(false); }
  }, [workspaceId, search, typeFilter]);

  const fetchMeta = useCallback(async () => {
    try {
      const [sf, st] = await Promise.all([
        api.get(`/workspaces/${workspaceId}/media/smart-folders`),
        api.get(`/workspaces/${workspaceId}/media/storage`),
      ]);
      setSmartFolders(sf.data.smart_folders || []);
      setStorage(st.data);
    } catch (err) { handleSilent(err, "MediaLibrary:op2"); }
  }, [workspaceId]);

  useEffect(() => { fetchItems(); fetchMeta(); }, [fetchItems, fetchMeta]);

  const handleUpload = async (files) => {
    if (!files?.length) return;
    setUploading(true);
    for (const file of Array.from(files)) {
      try {
        const formData = new FormData();
        formData.append("file", file);
        await api.post(`/workspaces/${workspaceId}/media/upload`, formData, { headers: { "Content-Type": "multipart/form-data" } });
        toast.success(`Uploaded: ${file.name}`);
      } catch (err) { handleError(err, "MediaLibrary:action"); }
    }
    setUploading(false);
    fetchItems();
    fetchMeta();
  };

  const toggleSelect = (id) => setSelected(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const selectAll = () => selected.size === items.length ? setSelected(new Set()) : setSelected(new Set(items.map(i => i.media_id)));

  const bulkDelete = async () => { const _ok = await confirmAction("Bulk Delete", `Delete ${selected.size} media items permanently?`); if (!_ok) return; try { await api.post(`/workspaces/${workspaceId}/media/bulk/delete`, { media_ids: [...selected] }); toast.success(`Deleted ${selected.size}`); setSelected(new Set()); fetchItems(); fetchMeta(); } catch (err) { handleError(err, "MediaLibrary:action"); } };
  const bulkTag = async (tag) => { try { await api.post(`/workspaces/${workspaceId}/media/bulk/tag`, { media_ids: [...selected], tags: [tag] }); toast.success("Tagged"); fetchItems(); } catch (err) { handleSilent(err, "MediaLibrary:op3"); } };

  const viewDetail = async (item) => {
    setDetailItem(item);
    setDetailData(null);
    try { const res = await api.get(`/media/${item.media_id}/data`); setDetailData(res.data.data); } catch (err) { handleSilent(err, "MediaLibrary:op4"); }
  };

  const shareItem = async (mediaId) => {
    try { const res = await api.post(`/media/${mediaId}/share`, { expires_hours: 24 }); navigator.clipboard.writeText(window.location.origin + res.data.share_url); toast.success("Share link copied!"); } catch (err) { handleError(err, "MediaLibrary:action"); }
  };

  const deleteItem = async (id) => { try { await api.delete(`/media/${id}`); toast.success("Deleted"); if (detailItem?.media_id === id) setDetailItem(null); fetchItems(); fetchMeta(); } catch (err) { handleSilent(err, "MediaLibrary:op5"); } };

  return (
    <div className="flex-1 flex min-h-0" data-testid="media-library">
      {/* Sidebar — Smart Folders + Storage */}
      <div className="w-48 flex-shrink-0 border-r border-zinc-800/40 p-3 space-y-4 overflow-y-auto">
        <p className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Smart Folders</p>
        {smartFolders.map(f => (
          <button key={f.name} onClick={() => { if (f.filter === "starred") { setSearch("starred"); setTypeFilter(""); } else if (["video","audio","image"].includes(f.filter)) { setTypeFilter(f.filter); setSearch(""); } else { setSearch(""); setTypeFilter(""); } }}
            className="w-full flex items-center justify-between px-2 py-1.5 rounded-lg text-xs text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50" data-testid={`smart-folder-${f.filter}`}>
            <span>{f.name}</span><Badge className="text-[9px] bg-zinc-800 text-zinc-500">{f.count}</Badge>
          </button>
        ))}
        {storage && (
          <div className="pt-3 border-t border-zinc-800/30">
            <p className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-2">Storage</p>
            <div className="text-xs text-zinc-400"><HardDrive className="w-3 h-3 inline mr-1" />{storage.total_mb}MB / {storage.limit_gb}GB</div>
            <div className="mt-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden"><div className="h-full bg-emerald-500 rounded-full" style={{ width: `${Math.min(storage.usage_percent, 100)}%` }} /></div>
            <p className="text-[9px] text-zinc-600 mt-0.5">{storage.usage_percent}% used</p>
          </div>
        )}
      </div>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Toolbar */}
        <div className="px-4 py-3 border-b border-zinc-800/40 space-y-2">
          <div className="flex items-center gap-3">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-600" />
              <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search media..." className="w-full bg-zinc-900/60 border border-zinc-800/60 rounded-lg pl-9 pr-3 py-2 text-sm text-zinc-300 placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-700" data-testid="media-search" />
            </div>
            <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="bg-zinc-900/60 border border-zinc-800/60 rounded-lg px-3 py-2 text-xs text-zinc-400" data-testid="media-type-filter">
              <option value="">All Types</option><option value="video">Video</option><option value="audio">Audio</option><option value="image">Image</option>
            </select>
            <div className="flex items-center gap-0.5 bg-zinc-800/40 rounded-lg p-0.5">
              <button onClick={() => setViewMode("grid")} className={`p-1.5 rounded ${viewMode === "grid" ? "bg-zinc-700 text-zinc-200" : "text-zinc-500"}`}><Grid3X3 className="w-3.5 h-3.5" /></button>
              <button onClick={() => setViewMode("list")} className={`p-1.5 rounded ${viewMode === "list" ? "bg-zinc-700 text-zinc-200" : "text-zinc-500"}`}><List className="w-3.5 h-3.5" /></button>
            </div>
            <Button onClick={() => fileInputRef.current?.click()} disabled={uploading} size="sm" className="bg-emerald-500 hover:bg-emerald-400 text-white gap-1.5" data-testid="upload-media-btn">
              <Upload className="w-3.5 h-3.5" /> Upload
            </Button>
            <input ref={fileInputRef} type="file" className="hidden" multiple accept="video/*,audio/*,image/*" onChange={(e) => handleUpload(e.target.files)} />
          </div>
          {/* Bulk actions */}
          {selected.size > 0 && (
            <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-zinc-800/60 border border-zinc-700/40">
              <span className="text-xs text-zinc-300 font-medium">{selected.size} selected</span>
              <button onClick={() => bulkTag("starred")} className="text-[10px] text-amber-400 px-2 py-0.5 rounded bg-amber-500/10 hover:bg-amber-500/20"><Star className="w-3 h-3 inline mr-0.5" />Star</button>
              <button onClick={bulkDelete} className="text-[10px] text-red-400 px-2 py-0.5 rounded bg-red-500/10 hover:bg-red-500/20"><Trash2 className="w-3 h-3 inline mr-0.5" />Delete</button>
              <button onClick={() => setSelected(new Set())} className="ml-auto text-zinc-500 hover:text-zinc-300"><X className="w-3 h-3" /></button>
            </div>
          )}
        </div>

        {/* Upload Dropzone overlay */}
        <div className="flex-1 overflow-y-auto p-4 relative"
          onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add("ring-2", "ring-emerald-500/30"); }}
          onDragLeave={(e) => { e.currentTarget.classList.remove("ring-2", "ring-emerald-500/30"); }}
          onDrop={(e) => { e.preventDefault(); e.currentTarget.classList.remove("ring-2", "ring-emerald-500/30"); handleUpload(e.dataTransfer.files); }}
          data-testid="media-dropzone"
        >
          {loading ? (
            <div className="text-center py-16 text-zinc-500">Loading...</div>
          ) : items.length === 0 ? (
            <div className="text-center py-16 border-2 border-dashed border-zinc-800 rounded-xl" data-testid="empty-media-library">
              <Upload className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
              <p className="text-zinc-400 font-medium">Drop files here or click Upload</p>
              <p className="text-sm text-zinc-600 mt-1">Supports video, audio, and image files</p>
            </div>
          ) : viewMode === "grid" ? (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3" data-testid="media-grid">
              {items.map(item => {
                const Icon = TYPE_ICONS[item.type] || Image;
                const colorClass = TYPE_COLORS[item.type] || TYPE_COLORS.image;
                const isSelected = selected.has(item.media_id);
                return (
                  <div key={item.media_id} className={`rounded-xl border overflow-hidden cursor-pointer group transition-all hover:shadow-lg ${isSelected ? "border-emerald-500/50 bg-emerald-500/5" : "border-zinc-800/50 bg-zinc-900/40 hover:border-zinc-700"}`} data-testid={`media-item-${item.media_id}`}>
                    <div className="aspect-square bg-zinc-800/30 flex items-center justify-center relative" onClick={() => viewDetail(item)}>
                      <Icon className={`w-8 h-8 ${colorClass.split(" ")[0]}`} />
                      <button onClick={(e) => { e.stopPropagation(); toggleSelect(item.media_id); }} className="absolute top-2 left-2 w-5 h-5 rounded border border-zinc-700 bg-zinc-900/80 flex items-center justify-center opacity-0 group-hover:opacity-100">{isSelected && <div className="w-3 h-3 rounded-sm bg-emerald-500" />}</button>
                      <Badge className={`absolute top-2 right-2 text-[8px] ${colorClass}`}>{item.type}</Badge>
                    </div>
                    <div className="p-2"><p className="text-xs text-zinc-300 truncate">{item.name || item.prompt?.substring(0, 40) || item.media_id}</p><p className="text-[10px] text-zinc-600">{item.file_size ? `${(item.file_size / 1024).toFixed(0)}KB` : ""}</p></div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="space-y-1" data-testid="media-list">
              <button onClick={selectAll} className="text-[10px] text-zinc-500 hover:text-zinc-300 px-2 py-1">{selected.size === items.length ? "Deselect all" : "Select all"}</button>
              {items.map(item => {
                const Icon = TYPE_ICONS[item.type] || Image;
                return (
                  <div key={item.media_id} className="flex items-center gap-3 p-2.5 rounded-lg bg-zinc-900/40 border border-zinc-800/40 hover:border-zinc-700 group cursor-pointer" onClick={() => viewDetail(item)} data-testid={`media-row-${item.media_id}`}>
                    <button onClick={(e) => { e.stopPropagation(); toggleSelect(item.media_id); }} className="w-4 h-4 rounded border border-zinc-700 flex items-center justify-center flex-shrink-0">{selected.has(item.media_id) && <div className="w-2.5 h-2.5 rounded-sm bg-emerald-500" />}</button>
                    <Icon className={`w-5 h-5 flex-shrink-0 ${TYPE_COLORS[item.type]?.split(" ")[0] || "text-zinc-500"}`} />
                    <div className="flex-1 min-w-0"><p className="text-sm text-zinc-200 truncate">{item.name || item.prompt?.substring(0, 60)}</p></div>
                    <span className="text-[10px] text-zinc-600">{item.file_size ? `${(item.file_size / 1024).toFixed(0)}KB` : ""}</span>
                    <div className="flex gap-1 opacity-0 group-hover:opacity-100">
                      <button onClick={(e) => { e.stopPropagation(); shareItem(item.media_id); }} className="p-1 rounded hover:bg-zinc-800 text-zinc-600 hover:text-zinc-300"><Share2 className="w-3 h-3" /></button>
                      <button onClick={(e) => { e.stopPropagation(); deleteItem(item.media_id); }} className="p-1 rounded hover:bg-zinc-800 text-zinc-600 hover:text-red-400"><Trash2 className="w-3 h-3" /></button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Asset Detail Panel (slide-out) */}
      <Dialog open={!!detailItem} onOpenChange={(open) => { if (!open) { setDetailItem(null); setDetailData(null); } }}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-lg">
          <DialogHeader><DialogTitle className="text-zinc-100 text-sm flex items-center gap-2">{detailItem?.type && (() => { const I = TYPE_ICONS[detailItem.type]; return <I className="w-4 h-4" />; })()}{detailItem?.name || "Media Details"}</DialogTitle></DialogHeader>
          {detailData && detailItem?.type === "video" && <video controls className="w-full rounded-lg" src={`data:video/mp4;base64,${detailData}`} />}
          {detailData && detailItem?.type === "audio" && <audio controls className="w-full" src={`data:audio/mp3;base64,${detailData}`} />}
          {detailData && detailItem?.type === "image" && <img className="w-full rounded-lg" src={`data:${detailItem.mime_type || "image/png"};base64,${detailData}`} alt="" />}
          {!detailData && <div className="h-32 bg-zinc-800 rounded-lg flex items-center justify-center text-zinc-500">Loading preview...</div>}
          <div className="space-y-2 text-xs">
            <div className="flex justify-between text-zinc-400"><span>Type</span><Badge className={TYPE_COLORS[detailItem?.type] || ""}>{detailItem?.type}</Badge></div>
            <div className="flex justify-between text-zinc-400"><span>Size</span><span>{detailItem?.file_size ? `${(detailItem.file_size / 1024).toFixed(1)}KB` : "—"}</span></div>
            <div className="flex justify-between text-zinc-400"><span>Provider</span><span>{detailItem?.provider || "—"}</span></div>
            {detailItem?.prompt && <div><span className="text-zinc-500">Prompt:</span><p className="text-zinc-300 mt-0.5">{detailItem.prompt}</p></div>}
            {detailItem?.tags?.length > 0 && <div className="flex flex-wrap gap-1">{detailItem.tags.map(t => <Badge key={t} className="text-[9px] bg-zinc-800 text-zinc-400">{t}</Badge>)}</div>}
          </div>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={() => shareItem(detailItem?.media_id)} className="border-zinc-700 text-zinc-300 gap-1"><Share2 className="w-3 h-3" />Share</Button>
            <Button size="sm" variant="outline" onClick={() => { if (detailItem) { setPublishMediaId(detailItem.media_id); setPublishMediaName(detailItem.name || "Media"); setPublishOpen(true); } }} className="border-cyan-500/30 text-cyan-400 gap-1"><Share2 className="w-3 h-3" />Publish</Button>
            <Button size="sm" variant="outline" onClick={() => { if (detailData && detailItem) { const a = document.createElement("a"); a.href = `data:${detailItem.mime_type || "application/octet-stream"};base64,${detailData}`; a.download = detailItem.name || detailItem.media_id; a.click(); } }} className="border-zinc-700 text-zinc-300 gap-1"><Download className="w-3 h-3" />Download</Button>
            <Button size="sm" variant="outline" onClick={() => { if (detailItem) deleteItem(detailItem.media_id); }} className="border-zinc-700 text-red-400 gap-1"><Trash2 className="w-3 h-3" />Delete</Button>
          </div>
        </DialogContent>
      </Dialog>
      <SocialPublishModal open={publishOpen} onOpenChange={setPublishOpen} mediaId={publishMediaId} mediaName={publishMediaName} workspaceId={workspaceId} />
    <ConfirmDlg />
    </div>
    );
}
