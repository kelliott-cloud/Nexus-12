/**
 * RepoEditor — Monaco editor area with file header, collab bar, and save controls.
 * Extracted from CodeRepoPanel.js for maintainability.
 */
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { FileCode, Save, GitCommit, Pencil, Trash2, MoreVertical, Users } from "lucide-react";
import Editor from "@monaco-editor/react";

export function RepoEditor({
  selectedFile, fileContent, setFileContent, hasUnsavedChanges, saving,
  handleSave, handleEditorMount, fetchHistory, handleDeleteFile,
  setRenameFileId, setRenamePath, setRenameDialog,
  collabParticipants, loading,
}) {
  if (!selectedFile) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <FileCode className="w-12 h-12 text-zinc-800 mx-auto mb-3" />
          <p className="text-sm text-zinc-500 mb-1">Select a file to edit</p>
          <p className="text-xs text-zinc-600">or create a new file to get started</p>
        </div>
      </div>
    );
  }

  return (
    <>
      {/* File header */}
      <div className="flex-shrink-0 flex items-center justify-between px-3 py-1.5 border-b border-zinc-800/40 bg-zinc-900/30">
        <div className="flex items-center gap-2 min-w-0">
          <FileCode className="w-3.5 h-3.5 text-zinc-500 flex-shrink-0" />
          <span className="text-xs text-zinc-300 truncate font-mono">{selectedFile.path}</span>
          {hasUnsavedChanges && (
            <span className="w-2 h-2 rounded-full bg-amber-400 flex-shrink-0" title="Unsaved changes" />
          )}
          <span className="text-[10px] text-zinc-600 font-mono">v{selectedFile.version}</span>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="sm" onClick={() => fetchHistory(selectedFile.file_id)}
            className="text-zinc-400 hover:text-zinc-200 h-6 px-2 text-[11px]" data-testid="file-history-btn">
            <GitCommit className="w-3 h-3 mr-1" /> History
          </Button>
          <Button variant="ghost" size="sm" onClick={handleSave} disabled={!hasUnsavedChanges || saving}
            className={`h-6 px-2 text-[11px] ${hasUnsavedChanges ? "text-emerald-400 hover:text-emerald-300" : "text-zinc-600"}`}
            data-testid="save-file-btn">
            <Save className="w-3 h-3 mr-1" /> {saving ? "Saving..." : "Save"}
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="p-1 rounded text-zinc-500 hover:text-zinc-300" data-testid="file-actions-btn">
                <MoreVertical className="w-3.5 h-3.5" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="bg-zinc-900 border-zinc-800" align="end">
              <DropdownMenuItem onClick={() => { setRenameFileId(selectedFile.file_id); setRenamePath(selectedFile.path); setRenameDialog(true); }}
                className="text-zinc-300 hover:bg-zinc-800 cursor-pointer text-xs">
                <Pencil className="w-3.5 h-3.5 mr-2" /> Rename
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleDeleteFile(selectedFile.file_id)}
                className="text-red-400 hover:bg-zinc-800 cursor-pointer text-xs">
                <Trash2 className="w-3.5 h-3.5 mr-2" /> Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
      {/* Collaborative participants bar */}
      {Object.keys(collabParticipants).length > 1 && (
        <div className="flex items-center gap-1.5 px-3 py-1 border-b border-zinc-800/30 bg-zinc-900/50" data-testid="collab-participants-bar">
          <Users className="w-3 h-3 text-zinc-500" />
          <span className="text-[9px] text-zinc-500">Editing:</span>
          {Object.entries(collabParticipants).map(([uid, p]) => (
            <span key={uid} className="flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded-full" style={{ backgroundColor: p.color + "20", color: p.color }}>
              <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: p.color }} />
              {p.name}
              {p.is_agent && <span className="text-[7px] opacity-70">AI</span>}
            </span>
          ))}
        </div>
      )}
      {/* Monaco Editor */}
      <div className="flex-1 min-h-0">
        {loading ? (
          <div className="flex items-center justify-center h-full text-zinc-500 text-sm">Loading...</div>
        ) : (
          <Editor
            height="100%"
            language={selectedFile.language || "plaintext"}
            value={fileContent}
            onChange={(value) => setFileContent(value || "")}
            onMount={handleEditorMount}
            theme="vs-dark"
            options={{
              fontSize: 13,
              fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
              minimap: { enabled: true, scale: 1 },
              scrollBeyondLastLine: false,
              wordWrap: "on",
              padding: { top: 8 },
              renderLineHighlight: "gutter",
              smoothScrolling: true,
              cursorBlinking: "smooth",
              bracketPairColorization: { enabled: true },
              automaticLayout: true,
            }}
          />
        )}
      </div>
    </>
  );
}
