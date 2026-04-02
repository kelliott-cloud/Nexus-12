import { useState, useEffect, useCallback } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import DOMPurify from "dompurify";
import { api } from "@/App";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  FileText, Image, Code2, X, Eye, File, FolderOpen,
  Layers, ChevronDown, ChevronRight, Download, Loader2,
} from "lucide-react";

const TYPE_VIEWERS = {
  wireframe: "svg", svg: "svg", html: "html",
  text: "text", code: "code", json: "code", markdown: "markdown",
  image: "image",
};

export default function DocsPreviewPanel({ workspaceId, channelId, isOpen, onClose }) {
  const [items, setItems] = useState([]);
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [viewingItem, setViewingItem] = useState(null);
  const [tab, setTab] = useState("artifacts");

  const fetchData = useCallback(async () => {
    if (!workspaceId) return;
    try {
      const [artRes, fileRes] = await Promise.all([
        api.get(`/workspaces/${workspaceId}/artifacts?limit=50`),
        channelId ? api.get(`/workspaces/${workspaceId}/files?channel_id=${channelId}`) : api.get(`/workspaces/${workspaceId}/files`),
      ]);
      setItems(artRes.data?.artifacts || artRes.data || []);
      setFiles(fileRes.data?.files || fileRes.data || []);
    } catch (err) { handleSilent(err, "DocsPreviewPanel:op1"); }
    setLoading(false);
  }, [workspaceId, channelId]);

  useEffect(() => { if (isOpen) fetchData(); }, [isOpen, fetchData]);

  // Poll for new artifacts
  useEffect(() => {
    if (!isOpen) return;
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [isOpen, fetchData]);

  if (!isOpen) return null;

  const handleFileDownload = async (fileId, fileName) => {
    try {
      const res = await api.get(`/files/${fileId}/download`, { responseType: "blob" });
      const blobUrl = URL.createObjectURL(res.data);
      const link = document.createElement("a");
      link.href = blobUrl;
      link.download = fileName || "download";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(blobUrl);
    } catch (err) { handleSilent(err, "DocsPreviewPanel:download"); }
  };

  const renderViewer = (item) => {
    const type = item.type || item.artifact_type || "text";
    const content = item.content || "";
    const ext = (item.extension || item.name?.split(".").pop() || "").toLowerCase();
    const isImage = ["png", "jpg", "jpeg", "gif", "webp", "svg"].includes(ext);

    // PDF — fetch as blob for preview
    if (ext === "pdf" && item.file_id) {
      return <BlobIframe fileId={item.file_id} name={item.name} />;
    }
    // DOCX/DOC/XLSX — extracted text
    if (["docx", "doc", "xlsx"].includes(ext) && item.file_id) {
      return <ExtractedTextViewer fileId={item.file_id} />;
    }
    if (type === "wireframe" || type === "svg" || ext === "svg") {
      const clean = DOMPurify.sanitize(content, { USE_PROFILES: { svg: true }, ALLOWED_TAGS: ["svg","rect","circle","line","text","path","g","ellipse","polygon","polyline","defs","marker","tspan"], FORBID_ATTR: ["onload","onerror","onclick","onmouseover"] });
      return <div className="p-4 flex items-center justify-center bg-white/5 rounded-lg" dangerouslySetInnerHTML={{ __html: clean }} />;
    }
    if (type === "html") {
      return <iframe srcDoc={content} className="w-full h-full border-0 bg-white rounded-lg" title={item.name} sandbox="allow-scripts" />;
    }
    if (isImage && item.file_id) {
      return <BlobImage fileId={item.file_id} name={item.name} />;
    }
    if (type === "code" || type === "json") {
      return <pre className="p-4 text-xs font-mono text-emerald-300 whitespace-pre-wrap break-words leading-relaxed bg-zinc-900/50 rounded-lg m-2">{content}</pre>;
    }
    if (type === "markdown") {
      return <div className="p-4 text-sm text-zinc-300 whitespace-pre-wrap leading-relaxed">{content}</div>;
    }
    // Default text
    return <pre className="p-4 text-xs text-zinc-400 whitespace-pre-wrap">{content || "No content"}</pre>;
  };

  const typeIcon = (type) => {
    if (type === "wireframe" || type === "svg") return <Layers className="w-3.5 h-3.5 text-purple-400" />;
    if (type === "html") return <Code2 className="w-3.5 h-3.5 text-orange-400" />;
    if (type === "code" || type === "json") return <Code2 className="w-3.5 h-3.5 text-emerald-400" />;
    if (type === "image") return <Image className="w-3.5 h-3.5 text-pink-400" />;
    return <FileText className="w-3.5 h-3.5 text-zinc-400" />;
  };

  return (
    <div className="w-80 flex-shrink-0 border-l border-zinc-800/60 flex flex-col bg-zinc-900/30" data-testid="docs-preview-panel">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800/40">
        <div className="flex items-center gap-2">
          <FolderOpen className="w-4 h-4 text-amber-400" />
          <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">Docs</span>
          <Badge className="bg-zinc-800 text-zinc-500 text-[9px]">{items.length + files.length}</Badge>
        </div>
        <button onClick={onClose} className="p-1 text-zinc-600 hover:text-zinc-300" data-testid="close-docs-panel">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Tab toggle */}
      <div className="flex items-center gap-1 px-2 py-1 border-b border-zinc-800/30">
        <button onClick={() => setTab("artifacts")} className={`text-[10px] px-2 py-0.5 rounded ${tab === "artifacts" ? "bg-zinc-700 text-zinc-200" : "text-zinc-500"}`}>
          Artifacts ({items.length})
        </button>
        <button onClick={() => setTab("files")} className={`text-[10px] px-2 py-0.5 rounded ${tab === "files" ? "bg-zinc-700 text-zinc-200" : "text-zinc-500"}`}>
          Files ({files.length})
        </button>
      </div>

      {/* Content */}
      {viewingItem ? (
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex items-center gap-2 px-3 py-1.5 border-b border-zinc-800/30 flex-shrink-0">
            <button onClick={() => setViewingItem(null)} className="text-zinc-500 hover:text-zinc-300 text-xs">← Back</button>
            <span className="text-xs text-zinc-300 truncate flex-1">{viewingItem.name}</span>
            {viewingItem.type && <Badge className="bg-purple-500/15 text-purple-400 text-[8px]">{viewingItem.type}</Badge>}
          </div>
          <ScrollArea className="flex-1">
            {renderViewer(viewingItem)}
          </ScrollArea>
        </div>
      ) : (
        <ScrollArea className="flex-1">
          {loading ? (
            <div className="text-center py-8"><Loader2 className="w-5 h-5 text-zinc-600 animate-spin mx-auto" /></div>
          ) : tab === "artifacts" ? (
            <div className="p-1.5 space-y-0.5">
              {items.length === 0 ? (
                <div className="text-center py-6"><Layers className="w-6 h-6 text-zinc-800 mx-auto mb-1" /><p className="text-[10px] text-zinc-600">No artifacts yet</p></div>
              ) : items.map(art => (
                <button key={art.artifact_id} onClick={() => setViewingItem(art)}
                  className="w-full text-left px-2.5 py-2 rounded-lg hover:bg-zinc-800/40 flex items-center gap-2 transition-colors" data-testid={`preview-artifact-${art.artifact_id}`}>
                  {typeIcon(art.type)}
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] text-zinc-300 truncate">{art.name}</p>
                    <p className="text-[9px] text-zinc-600">{art.type || "text"} • {art.created_by?.replace("ai:", "") || "?"}</p>
                  </div>
                  <Eye className="w-3 h-3 text-zinc-700" />
                </button>
              ))}
            </div>
          ) : (
            <div className="p-1.5 space-y-0.5">
              {files.length === 0 ? (
                <div className="text-center py-6"><File className="w-6 h-6 text-zinc-800 mx-auto mb-1" /><p className="text-[10px] text-zinc-600">No files yet</p></div>
              ) : files.map(f => {
                const ext = (f.extension || (f.original_name || "").split(".").pop() || "").toLowerCase();
                return (
                  <button key={f.file_id} onClick={() => setViewingItem({ ...f, name: f.original_name || f.name, type: ["png","jpg","jpeg","gif","webp","svg"].includes(ext) ? "image" : ext })}
                    className="w-full text-left px-2.5 py-2 rounded-lg hover:bg-zinc-800/40 flex items-center gap-2 transition-colors" data-testid={`preview-file-${f.file_id}`}>
                    <FileText className="w-3.5 h-3.5 text-zinc-500" />
                    <div className="flex-1 min-w-0">
                      <p className="text-[11px] text-zinc-300 truncate">{f.original_name || f.name}</p>
                      <p className="text-[9px] text-zinc-600">{ext.toUpperCase()} • {f.size ? `${(f.size/1024).toFixed(0)}KB` : ""}</p>
                    </div>
                    <Eye className="w-3 h-3 text-zinc-700" />
                  </button>
                );
              })}
            </div>
          )}
        </ScrollArea>
      )}
    </div>
  );
}

function ExtractedTextViewer({ fileId }) {
  const [text, setText] = useState("Loading...");
  useEffect(() => {
    api.get(`/files/${fileId}/text`).then(r => setText(r.data?.text || "No preview available")).catch(() => setText("Preview unavailable"));
  }, [fileId]);
  return <pre className="p-3 text-xs text-zinc-300 whitespace-pre-wrap leading-relaxed">{text}</pre>;
}

function BlobIframe({ fileId, name }) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    let blobUrl = null;
    api.get(`/files/${fileId}/preview`, { responseType: "blob" })
      .then(res => { blobUrl = URL.createObjectURL(res.data); setUrl(blobUrl); })
      .catch(() => setUrl(null));
    return () => { if (blobUrl) URL.revokeObjectURL(blobUrl); };
  }, [fileId]);
  if (!url) return <div className="p-4 text-xs text-zinc-500">Loading preview...</div>;
  return <iframe src={url} className="w-full h-[500px] border-0 rounded-lg" title={name} sandbox="allow-scripts" />;
}

function BlobImage({ fileId, name }) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    let blobUrl = null;
    api.get(`/files/${fileId}/download`, { responseType: "blob" })
      .then(res => { blobUrl = URL.createObjectURL(res.data); setUrl(blobUrl); })
      .catch(() => setUrl(null));
    return () => { if (blobUrl) URL.revokeObjectURL(blobUrl); };
  }, [fileId]);
  if (!url) return <div className="p-4 text-xs text-zinc-500">Loading image...</div>;
  return <div className="p-4 flex items-center justify-center"><img src={url} alt={name} className="max-w-full max-h-[500px] object-contain rounded-lg" /></div>;
}


