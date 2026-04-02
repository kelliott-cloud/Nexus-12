import { useState, useEffect, useCallback } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { api } from "@/App";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import DocViewer from "@/components/DocViewer";
import { toast } from "sonner";
import {
  FileText, Image, Code2, FileSpreadsheet, Film, Music,
  Upload, Search, File, Download, Eye, FolderOpen, Filter,
} from "lucide-react";

const EXT_ICONS = {
  pdf: FileText, docx: FileText, doc: FileText, txt: FileText, md: FileText,
  csv: FileSpreadsheet, xlsx: FileSpreadsheet, xls: FileSpreadsheet,
  json: Code2, xml: Code2, html: Code2, py: Code2, js: Code2, ts: Code2, css: Code2,
  png: Image, jpg: Image, jpeg: Image, gif: Image, webp: Image, svg: Image,
  mp4: Film, webm: Film, mov: Film,
  mp3: Music, wav: Music, ogg: Music,
};

const EXT_COLORS = {
  pdf: "text-red-400", docx: "text-blue-400", txt: "text-zinc-400",
  csv: "text-emerald-400", xlsx: "text-emerald-400",
  json: "text-amber-400", py: "text-blue-400", js: "text-yellow-400",
  png: "text-pink-400", jpg: "text-pink-400", mp4: "text-violet-400",
};

export default function DocsPanel({ workspaceId }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filterExt, setFilterExt] = useState("");
  const [viewingFile, setViewingFile] = useState(null);

  const fetchFiles = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/files`);
      setFiles(res.data?.files || res.data || []);
    } catch (err) { handleSilent(err, "DocsPanel:op1"); }
    setLoading(false);
  }, [workspaceId]);

  useEffect(() => { fetchFiles(); }, [fetchFiles]);

  const filtered = files.filter(f => {
    const name = (f.original_name || f.name || "").toLowerCase();
    const ext = (f.extension || name.split(".").pop() || "").toLowerCase();
    if (search && !name.includes(search.toLowerCase())) return false;
    if (filterExt && ext !== filterExt) return false;
    return true;
  });

  const extensions = [...new Set(files.map(f => (f.extension || (f.original_name || "").split(".").pop() || "").toLowerCase()).filter(Boolean))];

  const handleUpload = () => {
    const inp = document.createElement("input");
    inp.type = "file";
    inp.multiple = true;
    inp.onchange = async (e) => {
      for (const file of Array.from(e.target.files)) {
        if (file.size > 25 * 1024 * 1024) { toast.error(`${file.name} too large`); continue; }
        const formData = new FormData();
        formData.append("file", file);
        try {
          await api.post(`/workspaces/${workspaceId}/files`, formData, { headers: { "Content-Type": "multipart/form-data" } });
        } catch (err) { toast.error(`Failed to upload ${file.name}`); }
      }
      toast.success("Files uploaded");
      fetchFiles();
    };
    inp.click();
  };

  if (viewingFile) {
    return <DocViewer file={viewingFile} onClose={() => setViewingFile(null)} />;
  }

  return (
    <div className="flex flex-col h-full" data-testid="docs-panel">
      {/* Header */}
      <div className="flex items-center gap-3 p-4 border-b border-zinc-800/40">
        <FolderOpen className="w-5 h-5 text-amber-400" />
        <h2 className="text-sm font-semibold text-zinc-200">Documents</h2>
        <Badge className="bg-zinc-800 text-zinc-500 text-[9px]">{files.length} files</Badge>
        <div className="flex-1" />
        <Button size="sm" onClick={handleUpload} className="bg-emerald-500 hover:bg-emerald-400 text-white gap-1 h-7 text-xs" data-testid="docs-upload-btn">
          <Upload className="w-3 h-3" /> Upload
        </Button>
      </div>

      {/* Search + filter */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-zinc-800/30">
        <div className="relative flex-1">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-600" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search documents..."
            className="h-7 text-xs bg-zinc-900 border-zinc-800 pl-8" data-testid="docs-search" />
        </div>
        <select value={filterExt} onChange={(e) => setFilterExt(e.target.value)}
          className="h-7 text-xs bg-zinc-900 border border-zinc-800 rounded-md px-2 text-zinc-400" data-testid="docs-filter">
          <option value="">All types</option>
          {extensions.map(ext => <option key={ext} value={ext}>{ext.toUpperCase()}</option>)}
        </select>
      </div>

      {/* File list */}
      <ScrollArea className="flex-1">
        {loading ? (
          <div className="text-center py-12 text-zinc-600 text-xs">Loading documents...</div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-12">
            <FolderOpen className="w-8 h-8 text-zinc-800 mx-auto mb-2" />
            <p className="text-sm text-zinc-500">{search ? "No matching documents" : "No documents yet"}</p>
            <p className="text-xs text-zinc-600 mt-1">Upload files or share documents in chat</p>
          </div>
        ) : (
          <div className="p-2 space-y-1">
            {filtered.map(file => {
              const name = file.original_name || file.name || "Unknown";
              const ext = (file.extension || name.split(".").pop() || "").toLowerCase();
              const Icon = EXT_ICONS[ext] || File;
              const color = EXT_COLORS[ext] || "text-zinc-400";
              const size = file.size ? `${(file.size / 1024).toFixed(0)}KB` : "";

              return (
                <div key={file.file_id} className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-zinc-800/40 cursor-pointer group transition-colors"
                  onClick={() => setViewingFile(file)} data-testid={`doc-file-${file.file_id}`}>
                  <Icon className={`w-5 h-5 ${color} flex-shrink-0`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-zinc-300 truncate">{name}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <Badge className="bg-zinc-800 text-zinc-500 text-[8px]">{ext.toUpperCase()}</Badge>
                      {size && <span className="text-[9px] text-zinc-600">{size}</span>}
                      {file.has_extracted_text && <span className="text-[8px] text-emerald-400/60">AI readable</span>}
                      {file.uploaded_by_name && <span className="text-[9px] text-zinc-600">{file.uploaded_by_name}</span>}
                    </div>
                  </div>
                  <Eye className="w-3.5 h-3.5 text-zinc-600 opacity-0 group-hover:opacity-100" />
                </div>
              );
            })}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
