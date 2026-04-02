import { useState, useEffect } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { api } from "@/App";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  FileText, Image, Code2, FileSpreadsheet, Film, Music,
  Download, Eye, X, Loader2, File, Upload, Search,
} from "lucide-react";

const TYPE_CONFIG = {
  pdf: { icon: FileText, color: "text-red-400", viewer: "iframe" },
  docx: { icon: FileText, color: "text-blue-400", viewer: "extracted" },
  doc: { icon: FileText, color: "text-blue-400", viewer: "extracted" },
  txt: { icon: FileText, color: "text-zinc-400", viewer: "text" },
  md: { icon: FileText, color: "text-zinc-300", viewer: "markdown" },
  csv: { icon: FileSpreadsheet, color: "text-emerald-400", viewer: "table" },
  xlsx: { icon: FileSpreadsheet, color: "text-emerald-400", viewer: "extracted" },
  json: { icon: Code2, color: "text-amber-400", viewer: "code" },
  xml: { icon: Code2, color: "text-orange-400", viewer: "code" },
  html: { icon: Code2, color: "text-orange-400", viewer: "iframe" },
  py: { icon: Code2, color: "text-blue-400", viewer: "code" },
  js: { icon: Code2, color: "text-yellow-400", viewer: "code" },
  jsx: { icon: Code2, color: "text-yellow-400", viewer: "code" },
  ts: { icon: Code2, color: "text-blue-500", viewer: "code" },
  tsx: { icon: Code2, color: "text-blue-500", viewer: "code" },
  css: { icon: Code2, color: "text-purple-400", viewer: "code" },
  sql: { icon: Code2, color: "text-cyan-400", viewer: "code" },
  png: { icon: Image, color: "text-pink-400", viewer: "image" },
  jpg: { icon: Image, color: "text-pink-400", viewer: "image" },
  jpeg: { icon: Image, color: "text-pink-400", viewer: "image" },
  gif: { icon: Image, color: "text-pink-400", viewer: "image" },
  webp: { icon: Image, color: "text-pink-400", viewer: "image" },
  svg: { icon: Image, color: "text-pink-400", viewer: "image" },
  mp4: { icon: Film, color: "text-violet-400", viewer: "video" },
  webm: { icon: Film, color: "text-violet-400", viewer: "video" },
  mp3: { icon: Music, color: "text-teal-400", viewer: "audio" },
  wav: { icon: Music, color: "text-teal-400", viewer: "audio" },
};

export default function DocViewer({ file, onClose }) {
  const [content, setContent] = useState(null);
  const [loading, setLoading] = useState(true);
  const ext = (file?.extension || file?.name?.split(".").pop() || "").toLowerCase();
  const config = TYPE_CONFIG[ext] || { icon: File, color: "text-zinc-400", viewer: "download" };
  const Icon = config.icon;
  const downloadPath = `/files/${file?.file_id}/download`;

  const handleDownload = async () => {
    try {
      const res = await api.get(downloadPath, { responseType: "blob" });
      const blobUrl = URL.createObjectURL(res.data);
      const link = document.createElement("a");
      link.href = blobUrl;
      link.download = file?.original_name || file?.name || "download";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(blobUrl);
    } catch (err) {
      handleSilent(err, "DocViewer:download");
      toast.error("Download failed");
    }
  };

  useEffect(() => {
    if (!file) return;
    setLoading(true);
    (async () => {
      try {
        if (["image", "video", "audio"].includes(config.viewer)) {
          try {
            const res = await api.get(downloadPath, { responseType: "blob" });
            const blobUrl = URL.createObjectURL(res.data);
            setContent(blobUrl);
          } catch (err) { handleSilent(err, "DocViewer:media"); setContent(null); }
        } else if (config.viewer === "iframe") {
          // For PDF: fetch as blob and create object URL (avoids cookie auth issue)
          try {
            const res = await api.get(`/files/${file.file_id}/preview`, { responseType: "blob" });
            const blobUrl = URL.createObjectURL(res.data);
            setContent(blobUrl);
          } catch (err) { handleSilent(err, "DocViewer:op1"); setContent(downloadUrl); }
        } else if (config.viewer === "extracted") {
          try {
            const res = await api.get(`/files/${file.file_id}/text`);
            setContent(res.data?.text || "No text could be extracted from this document.");
          } catch (err) { handleSilent(err, "DocViewer:op2"); setContent("Preview unavailable. Click Download to view this file."); }
        } else if (config.viewer === "text" || config.viewer === "code" || config.viewer === "markdown" || config.viewer === "table") {
          // Fetch the extracted text content from the message or the file itself
          if (file.extracted_text) {
            setContent(file.extracted_text);
          } else {
            const res = await api.get(`/files/${file.file_id}/download`, { responseType: "text" });
            setContent(typeof res.data === "string" ? res.data : JSON.stringify(res.data, null, 2));
          }
        }
      } catch (err) { handleSilent(err, "DocViewer:op3"); setContent(null); }
      setLoading(false);
    })();
  }, [file?.file_id]);

  if (!file) return null;

  return (
    <div className="flex flex-col h-full bg-zinc-950" data-testid="doc-viewer">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-zinc-800/40 flex-shrink-0">
        <Icon className={`w-4 h-4 ${config.color}`} />
        <span className="text-sm font-medium text-zinc-200 truncate flex-1">{file.original_name || file.name}</span>
        <Badge className="bg-zinc-800 text-zinc-500 text-[9px]">{ext.toUpperCase()}</Badge>
        {file.size && <span className="text-[9px] text-zinc-600">{(file.size / 1024).toFixed(0)}KB</span>}
        <button onClick={handleDownload} className="p-1 text-zinc-500 hover:text-zinc-300" data-testid="doc-download-btn">
          <Download className="w-3.5 h-3.5" />
        </button>
        <button onClick={onClose} className="p-1 text-zinc-500 hover:text-zinc-300">
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="flex items-center justify-center h-full"><Loader2 className="w-6 h-6 text-zinc-600 animate-spin" /></div>
        ) : config.viewer === "image" ? (
          <div className="flex items-center justify-center p-4 h-full">
            <img src={content} alt={file.name} className="max-w-full max-h-full object-contain rounded-lg" />
          </div>
        ) : config.viewer === "video" ? (
          <div className="flex items-center justify-center p-4 h-full">
            <video src={content} controls className="max-w-full max-h-full rounded-lg" />
          </div>
        ) : config.viewer === "audio" ? (
          <div className="flex items-center justify-center p-8">
            <audio src={content} controls className="w-full max-w-md" />
          </div>
        ) : config.viewer === "iframe" ? (
          <iframe src={content} className="w-full h-full border-0" title={file.name} sandbox="allow-same-origin allow-scripts" />
        ) : config.viewer === "extracted" ? (
          <div className="p-4 text-sm text-zinc-300 leading-relaxed whitespace-pre-wrap">{content}</div>
        ) : config.viewer === "code" ? (
          <pre className="p-4 text-xs font-mono text-zinc-300 whitespace-pre-wrap break-words leading-relaxed">{content}</pre>
        ) : config.viewer === "table" && content ? (
          <div className="p-4 overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              {content.split("\n").filter(Boolean).map((row, i) => (
                <tr key={i} className={i === 0 ? "bg-zinc-800/50" : "hover:bg-zinc-800/30"}>
                  {row.split(",").map((cell, j) => (
                    i === 0 ? <th key={j} className="px-3 py-1.5 border border-zinc-800 text-left text-zinc-300 font-semibold">{cell.trim().replace(/^"|"$/g, "")}</th>
                             : <td key={j} className="px-3 py-1.5 border border-zinc-800 text-zinc-400">{cell.trim().replace(/^"|"$/g, "")}</td>
                  ))}
                </tr>
              ))}
            </table>
          </div>
        ) : config.viewer === "markdown" ? (
          <div className="p-4 text-sm text-zinc-300 leading-relaxed whitespace-pre-wrap">{content}</div>
        ) : content ? (
          <pre className="p-4 text-xs text-zinc-400 whitespace-pre-wrap">{content}</pre>
        ) : (
          <div className="flex flex-col items-center justify-center h-full gap-3">
            <File className="w-10 h-10 text-zinc-700" />
            <p className="text-sm text-zinc-500">This file type cannot be previewed</p>
            <Button size="sm" variant="outline" className="border-zinc-700 text-zinc-300" onClick={handleDownload} data-testid="doc-fallback-download-btn">
              <Download className="w-3 h-3 mr-1.5" /> Download
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
