import { useState, useRef } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { Upload, X, FileText, Image, Code, File, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { api } from "@/App";

const FILE_ICONS = {
  image: Image,
  code: Code,
  document: FileText,
  default: File,
};

const getFileCategory = (extension) => {
  const imageExts = ["png", "jpg", "jpeg", "gif", "webp", "svg", "ico"];
  const codeExts = ["py", "js", "jsx", "ts", "tsx", "html", "css", "json", "xml", "yaml", "yml", "java", "cpp", "c", "go", "rs", "rb", "php", "swift", "kt", "sql", "sh"];
  const docExts = ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "md", "csv"];

  if (imageExts.includes(extension)) return "image";
  if (codeExts.includes(extension)) return "code";
  if (docExts.includes(extension)) return "document";
  return "default";
};

const formatFileSize = (bytes) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

export default function FileUpload({ 
  channelId, 
  taskSessionId, 
  onUploadComplete,
  compact = false 
}) {
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const fileInputRef = useRef(null);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    setIsDragging(false);
    
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      await uploadFile(files[0]);
    }
  };

  const handleFileSelect = async (e) => {
    const files = Array.from(e.target.files);
    if (files.length > 0) {
      await uploadFile(files[0]);
    }
    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const uploadFile = async (file) => {
    // Validate file size (25MB)
    if (file.size > 25 * 1024 * 1024) {
      toast.error("File too large. Maximum size is 25MB.");
      return;
    }

    setUploading(true);
    setUploadProgress(0);

    try {
      const formData = new FormData();
      formData.append("file", file);

      let endpoint;
      if (channelId) {
        endpoint = `/channels/${channelId}/files`;
      } else if (taskSessionId) {
        endpoint = `/task-sessions/${taskSessionId}/files`;
      } else {
        toast.error("No destination specified for upload");
        return;
      }

      // Simulate progress for better UX
      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => Math.min(prev + 10, 90));
      }, 100);

      const res = await api.post(endpoint, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      clearInterval(progressInterval);
      setUploadProgress(100);

      toast.success(`Uploaded: ${file.name}`);
      onUploadComplete?.(res.data);
    } catch (err) {
      const message = err.response?.data?.detail || "Upload failed";
      toast.error(message);
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  if (compact) {
    return (
      <>
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileSelect}
          className="hidden"
          data-testid="file-input-compact"
        />
        <Button
          variant="ghost"
          size="sm"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 p-2"
          data-testid="file-upload-btn-compact"
        >
          {uploading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Upload className="w-4 h-4" />
          )}
        </Button>
      </>
    );
  }

  return (
    <div
      className={`relative border-2 border-dashed rounded-lg transition-colors ${
        isDragging
          ? "border-blue-500 bg-blue-500/10"
          : "border-zinc-700 hover:border-zinc-600"
      }`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      data-testid="file-upload-dropzone"
    >
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileSelect}
        className="hidden"
        data-testid="file-input"
      />

      <div
        className="flex flex-col items-center justify-center py-6 px-4 cursor-pointer"
        onClick={() => fileInputRef.current?.click()}
      >
        {uploading ? (
          <>
            <Loader2 className="w-8 h-8 text-blue-400 animate-spin mb-2" />
            <p className="text-sm text-zinc-400">Uploading... {uploadProgress}%</p>
            <div className="w-full max-w-xs h-1.5 bg-zinc-800 rounded-full mt-2 overflow-hidden">
              <div
                className="h-full bg-blue-500 transition-all duration-200"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </>
        ) : (
          <>
            <Upload className="w-8 h-8 text-zinc-500 mb-2" />
            <p className="text-sm text-zinc-400">
              Drop files here or <span className="text-blue-400">browse</span>
            </p>
            <p className="text-xs text-zinc-600 mt-1">Max 25MB • Images, docs, code files</p>
          </>
        )}
      </div>
    </div>
  );
}

export function FileAttachment({ file, onDelete, canDelete = true }) {
  const ext = file.extension || file.name?.split(".").pop() || "";
  const category = getFileCategory(ext);
  const Icon = FILE_ICONS[category];

  const handleDownload = async () => {
    try {
      window.open(`${api.defaults.baseURL}/files/${file.file_id}/download`, "_blank");
    } catch (err) {
      toast.error("Failed to download file");
    }
  };

  return (
    <div
      className="flex items-center gap-3 p-3 bg-zinc-800/50 rounded-lg border border-zinc-700 group"
      data-testid={`file-attachment-${file.file_id}`}
    >
      <div className="w-10 h-10 rounded bg-zinc-700 flex items-center justify-center">
        {category === "image" && file.mime_type?.startsWith("image/") ? (
          <img
            src={`${api.defaults.baseURL}/files/${file.file_id}/download`}
            alt={file.name || file.original_name}
            className="w-full h-full object-cover rounded"
            onError={(e) => {
              e.target.style.display = "none";
              e.target.nextSibling.style.display = "flex";
            }}
          />
        ) : null}
        <Icon className="w-5 h-5 text-zinc-400" style={{ display: category === "image" ? "none" : "block" }} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-zinc-200 truncate">{file.name || file.original_name}</p>
        <p className="text-xs text-zinc-500">
          {formatFileSize(file.size || file.file_size)} • {ext.toUpperCase()}
        </p>
      </div>
      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <Button
          variant="ghost"
          size="sm"
          onClick={handleDownload}
          className="p-1.5 h-auto text-zinc-400 hover:text-zinc-200"
        >
          <FileText className="w-4 h-4" />
        </Button>
        {canDelete && onDelete && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onDelete(file.file_id)}
            className="p-1.5 h-auto text-zinc-400 hover:text-red-400"
          >
            <X className="w-4 h-4" />
          </Button>
        )}
      </div>
    </div>
  );
}
