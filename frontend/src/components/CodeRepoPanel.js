import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import Editor from "@monaco-editor/react";
import { api } from "@/App";
import { toast } from "sonner";
import { RepoEditor } from "@/components/repo/RepoEditor";
import { RepoToolbar } from "@/components/repo/RepoToolbar";
import { RepoDialogs } from "@/components/repo/RepoDialogs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import {
  X, Plus, File, Folder, FolderOpen, ChevronRight, ChevronDown,
  Save, Trash2, History, GitCommit, Link2, Unlink, MoreVertical,
  FileCode, FilePlus, FolderPlus, RefreshCw, Search, Pencil,
  GitBranch, GitPullRequest, Upload, Download, Users, Loader2,
} from "lucide-react";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const LANG_ICONS = {
  javascript: "JS", typescript: "TS", python: "PY", html: "HT",
  css: "CS", json: "JN", markdown: "MD", shell: "SH", go: "GO",
  rust: "RS", java: "JA", ruby: "RB", sql: "SQ", yaml: "YM",
};

function buildTree(files) {
  const root = { children: {}, files: [] };
  for (const f of files) {
    const parts = f.path.split("/");
    let node = root;
    if (f.is_folder) {
      for (const part of parts) {
        if (!node.children[part]) node.children[part] = { children: {}, files: [] };
        node = node.children[part];
      }
      node._folderData = f;
    } else {
      const fileName = parts.pop();
      for (const part of parts) {
        if (!node.children[part]) node.children[part] = { children: {}, files: [] };
        node = node.children[part];
      }
      node.files.push({ ...f, _name: fileName });
    }
  }
  return root;
}

function TreeNode({ name, node, depth, onSelectFile, selectedFileId, onContextMenu }) {
  const [expanded, setExpanded] = useState(depth < 2);
  const hasChildren = Object.keys(node.children).length > 0 || node.files.length > 0;
  const folderData = node._folderData;

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        onContextMenu={(e) => { e.preventDefault(); if (folderData) onContextMenu(e, folderData); }}
        className="w-full flex items-center gap-1.5 px-2 py-1 text-left hover:bg-zinc-800/60 rounded text-xs transition-colors group"
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
        data-testid={`tree-folder-${name}`}
      >
        {hasChildren ? (
          expanded ? <ChevronDown className="w-3 h-3 text-zinc-500 flex-shrink-0" /> : <ChevronRight className="w-3 h-3 text-zinc-500 flex-shrink-0" />
        ) : <span className="w-3" />}
        {expanded ? <FolderOpen className="w-3.5 h-3.5 text-amber-400/80 flex-shrink-0" /> : <Folder className="w-3.5 h-3.5 text-amber-400/60 flex-shrink-0" />}
        <span className="text-zinc-300 truncate">{name}</span>
      </button>
      {expanded && (
        <>
          {Object.entries(node.children).sort(([a], [b]) => a.localeCompare(b)).map(([childName, childNode]) => (
            <TreeNode
              key={childName}
              name={childName}
              node={childNode}
              depth={depth + 1}
              onSelectFile={onSelectFile}
              selectedFileId={selectedFileId}
              onContextMenu={onContextMenu}
            />
          ))}
          {node.files.sort((a, b) => a._name.localeCompare(b._name)).map((f) => (
            <button
              key={f.file_id}
              onClick={() => onSelectFile(f)}
              onContextMenu={(e) => { e.preventDefault(); onContextMenu(e, f); }}
              className={`w-full flex items-center gap-1.5 px-2 py-1 text-left rounded text-xs transition-colors ${
                selectedFileId === f.file_id ? "bg-zinc-800 text-zinc-100" : "text-zinc-400 hover:bg-zinc-800/40 hover:text-zinc-200"
              }`}
              style={{ paddingLeft: `${(depth + 1) * 12 + 8}px` }}
              data-testid={`tree-file-${f.file_id}`}
            >
              <FileCode className="w-3.5 h-3.5 flex-shrink-0 text-zinc-500" />
              <span className="truncate">{f._name}</span>
              {f.language && LANG_ICONS[f.language] && (
                <span className="ml-auto text-[9px] font-mono text-zinc-600">{LANG_ICONS[f.language]}</span>
              )}
            </button>
          ))}
        </>
      )}
    </div>
  );
}

function RootFileList({ files, onSelectFile, selectedFileId, onContextMenu }) {
  // Files at root level (no folder parent)
  return files.sort((a, b) => a._name.localeCompare(b._name)).map((f) => (
    <button
      key={f.file_id}
      onClick={() => onSelectFile(f)}
      onContextMenu={(e) => { e.preventDefault(); onContextMenu(e, f); }}
      className={`w-full flex items-center gap-1.5 px-2 py-1 text-left rounded text-xs transition-colors ${
        selectedFileId === f.file_id ? "bg-zinc-800 text-zinc-100" : "text-zinc-400 hover:bg-zinc-800/40 hover:text-zinc-200"
      }`}
      style={{ paddingLeft: "8px" }}
      data-testid={`tree-file-${f.file_id}`}
    >
      <FileCode className="w-3.5 h-3.5 flex-shrink-0 text-zinc-500" />
      <span className="truncate">{f._name}</span>
      {f.language && LANG_ICONS[f.language] && (
        <span className="ml-auto text-[9px] font-mono text-zinc-600">{LANG_ICONS[f.language]}</span>
      )}
    </button>
  ));
}

export const CodeRepoPanel = ({ workspaceId, isOpen, onClose, channels, projects, repoId = null, isInline = false }) => {
  const [files, setFiles] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileContent, setFileContent] = useState("");
  const [originalContent, setOriginalContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [history, setHistory] = useState([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [links, setLinks] = useState([]);
  const [linksOpen, setLinksOpen] = useState(false);
  const [newFileDialog, setNewFileDialog] = useState(false);
  const [newFilePath, setNewFilePath] = useState("");
  const [newFileIsFolder, setNewFileIsFolder] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [commitViewOpen, setCommitViewOpen] = useState(false);
  const [activeCommit, setActiveCommit] = useState(null);
  const [renameDialog, setRenameDialog] = useState(false);
  const [renamePath, setRenamePath] = useState("");
  const [renameFileId, setRenameFileId] = useState("");
  const [contextFile, setContextFile] = useState(null);
  const [contextMenu, setContextMenu] = useState(null);
  const [branches, setBranches] = useState([]);
  const [currentBranch, setCurrentBranch] = useState("main");
  const [branchDialogOpen, setBranchDialogOpen] = useState(false);
  const [newBranchName, setNewBranchName] = useState("");
  const [gitDialogOpen, setGitDialogOpen] = useState(false);
  const [gitRepo, setGitRepo] = useState("");
  const [gitAction, setGitAction] = useState("push");
  const [gitToken, setGitToken] = useState("");
  const [gitLoading, setGitLoading] = useState(false);
  const [collaborators, setCollaborators] = useState([]);
  const [refreshing, setRefreshing] = useState(false);
  const editorRef = useRef(null);
  const collabWsRef = useRef(null);
  const [collabParticipants, setCollabParticipants] = useState({});
  const cursorDecorationsRef = useRef([]);

  const fetchTree = useCallback(async (showToast) => {
    try {
      setRefreshing(true);
      const res = await api.get(`/workspaces/${workspaceId}/code-repo/tree${repoId ? `?repo_id=${repoId}` : ""}`);
      setFiles(res.data.files || []);
      if (showToast) toast.success(`Refreshed — ${(res.data.files || []).length} files`);
    } catch (err) {
      console.error("Failed to fetch repo tree:", err);
      if (showToast) toast.error("Failed to refresh repo");
    } finally {
      setRefreshing(false);
    }
  }, [workspaceId]);

  const fetchLinks = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/code-repo/links${repoId ? `?repo_id=${repoId}` : ""}`);
      setLinks(res.data.links || []);
    } catch (err) { handleSilent(err, "CodeRepoPanel:op1"); }
  }, [workspaceId]);

  const fetchBranches = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/code-repo/branches${repoId ? `?repo_id=${repoId}` : ""}`);
      setBranches(res.data.branches || []);
    } catch (err) { handleSilent(err, "CodeRepoPanel:op2"); }
  }, [workspaceId]);

  useEffect(() => {
    if (isOpen && workspaceId) {
      fetchTree();
      fetchLinks();
      fetchBranches();
    }
  }, [isOpen, workspaceId, fetchTree, fetchLinks]);

  // Poll for changes every 8 seconds when open
  useEffect(() => {
    if (!isOpen) return;
    const interval = setInterval(fetchTree, 8000);
    return () => {
      clearInterval(interval);
      // Clean up collab WebSocket when panel closes
      if (collabWsRef.current) {
        try {
          if (collabWsRef.current.provider) { collabWsRef.current.provider.destroy(); collabWsRef.current.ydoc.destroy(); }
          else collabWsRef.current.close();
        } catch (err) { handleSilent(err, "CodeRepoPanel:op3"); }
      }
    };
  }, [isOpen, fetchTree]);

  const handleSelectFile = async (file) => {
    if (file.is_folder) return;
    // Close previous collab session
    if (collabWsRef.current) { try { collabWsRef.current.close(); } catch (err) { handleSilent(err, "CodeRepoPanel:op4"); } }
    setCollabParticipants({});
    
    setLoading(true);
    try {
      const res = await api.get(`/workspaces/${workspaceId}/code-repo/files/${file.file_id}${repoId ? `?repo_id=${repoId}` : ""}`);
      setSelectedFile(res.data);
      setFileContent(res.data.content || "");
      setOriginalContent(res.data.content || "");
      
      // Connect to Yjs collaborative editing
      try {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}`;
        if (wsUrl) {
          const Y = require("yjs");
          const { WebsocketProvider } = require("y-websocket");
          
          const ydoc = new Y.Doc();
          const ytext = ydoc.getText("content");
          
          // Initialize with file content
          ytext.insert(0, res.data.content || "");
          
          const provider = new WebsocketProvider(wsUrl, `yjs/${res.data.file_id}`, ydoc);
          
          provider.on("status", ({ status }) => {
            if (status === "connected") {
              setCollabParticipants(prev => ({ ...prev, _connected: true }));
            }
          });
          
          // Listen for remote changes
          ytext.observe((event) => {
            if (event.transaction.local) return;
            const newContent = ytext.toString();
            setFileContent(newContent);
            if (editorRef.current) {
              const model = editorRef.current.getModel();
              if (model && model.getValue() !== newContent) {
                const pos = editorRef.current.getPosition();
                model.setValue(newContent);
                if (pos) editorRef.current.setPosition(pos);
              }
            }
          });
          
          collabWsRef.current = { provider, ydoc, ytext };
        }
      } catch (e) {
        console.warn("Yjs collab init failed:", e);
      }
    } catch (err) {
      toast.error("Failed to load file");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!selectedFile) return;
    setSaving(true);
    try {
      await api.put(`/workspaces/${workspaceId}/code-repo/files/${selectedFile.file_id}${repoId ? `?repo_id=${repoId}` : ""}`, {
        content: fileContent,
        message: `Edit ${selectedFile.path}`,
      });
      setOriginalContent(fileContent);
      setSelectedFile(prev => ({ ...prev, version: (prev.version || 0) + 1 }));
      toast.success("File saved");
      fetchTree();
    } catch (err) {
      toast.error("Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const handleCreateFile = async () => {
    if (!newFilePath.trim()) return;
    try {
      if (newFileIsFolder) {
        await api.post(`/workspaces/${workspaceId}/code-repo/folders${repoId ? `?repo_id=${repoId}` : ""}`, { path: newFilePath });
      } else {
        const res = await api.post(`/workspaces/${workspaceId}/code-repo/files${repoId ? `?repo_id=${repoId}` : ""}`, {
          path: newFilePath,
          content: "",
        });
        setSelectedFile(res.data);
        setFileContent("");
        setOriginalContent("");
      }
      toast.success(newFileIsFolder ? "Folder created" : "File created");
      setNewFileDialog(false);
      setNewFilePath("");
      setNewFileIsFolder(false);
      fetchTree();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to create");
    }
  };

  const handleDeleteFile = async (fileId) => {
    try {
      await api.delete(`/workspaces/${workspaceId}/code-repo/files/${fileId}${repoId ? `?repo_id=${repoId}` : ""}`);
      if (selectedFile?.file_id === fileId) {
        setSelectedFile(null);
        setFileContent("");
      }
      toast.success("Deleted");
      fetchTree();
    } catch (err) {
      toast.error("Failed to delete");
    }
  };

  const handleRenameFile = async () => {
    if (!renamePath.trim() || !renameFileId) return;
    try {
      await api.patch(`/workspaces/${workspaceId}/code-repo/files/${renameFileId}`, {
        path: renamePath,
      });
      toast.success("Renamed");
      setRenameDialog(false);
      fetchTree();
      if (selectedFile?.file_id === renameFileId) {
        setSelectedFile(prev => ({ ...prev, path: renamePath, name: renamePath.split("/").pop() }));
      }
    } catch (err) {
      toast.error("Failed to rename");
    }
  };

  const handleCreateBranch = async () => {
    if (!newBranchName.trim()) return;
    try {
      await api.post(`/workspaces/${workspaceId}/code-repo/branches${repoId ? `?repo_id=${repoId}` : ""}`, { name: newBranchName, from_branch: currentBranch });
      toast.success(`Branch '${newBranchName}' created`);
      setBranchDialogOpen(false);
      setNewBranchName("");
      fetchBranches();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed to create branch"); }
  };

  const [mergePreview, setMergePreview] = useState(null);
  const [merging, setMerging] = useState(false);

  const handleMergeBranch = async (branchName) => {
    // Show merge preview first
    try {
      const [branchFiles, mainFiles] = await Promise.all([
        api.get(`/workspaces/${workspaceId}/code-repo/tree${repoId ? `?repo_id=${repoId}` : ""}`),
        api.get(`/workspaces/${workspaceId}/code-repo/tree${repoId ? `?repo_id=${repoId}` : ""}`),
      ]);
      setMergePreview({ branch: branchName, target: "main" });
    } catch (err) { toast.error("Failed to load merge preview"); }
  };

  const confirmMerge = async () => {
    if (!mergePreview) return;
    setMerging(true);
    try {
      const res = await api.post(`/workspaces/${workspaceId}/code-repo/branches/${mergePreview.branch}/merge${repoId ? `?repo_id=${repoId}` : ""}`, { target: mergePreview.target });
      toast.success(`Merged ${res.data.files_merged} files from ${mergePreview.branch} into ${mergePreview.target}`);
      setMergePreview(null);
      fetchTree();
      fetchBranches();
    } catch (err) { toast.error(err.response?.data?.detail || "Merge failed"); }
    setMerging(false);
  };

  const handleDeleteBranch = async (branchName) => {
    try {
      await api.delete(`/workspaces/${workspaceId}/code-repo/branches/${branchName}${repoId ? `?repo_id=${repoId}` : ""}`);
      toast.success(`Branch '${branchName}' deleted`);
      if (currentBranch === branchName) setCurrentBranch("main");
      fetchBranches();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed to delete branch"); }
  };

  const handleGitAction = async () => {
    if (!gitRepo.trim()) return;
    setGitLoading(true);
    try {
      const tokenParam = gitToken.trim() ? gitToken.trim() : undefined;
      if (gitAction === "push") {
        const res = await api.post(`/workspaces/${workspaceId}/code-repo/github-push${repoId ? `?repo_id=${repoId}` : ""}`, { repo: gitRepo, branch: currentBranch, message: "Push from Nexus", token: tokenParam });
        toast.success(`Pushed ${res.data.pushed} files to GitHub`);
        if (res.data.errors?.length) toast.error(`${res.data.errors.length} errors`);
      } else {
        const res = await api.post(`/workspaces/${workspaceId}/code-repo/github-pull${repoId ? `?repo_id=${repoId}` : ""}`, { repo: gitRepo, branch: currentBranch, token: tokenParam });
        toast.success(`Pulled ${res.data.pulled} files from GitHub`);
        fetchTree();
      }
      setGitDialogOpen(false);
    } catch (err) { toast.error(err.response?.data?.detail || `Git ${gitAction} failed`); }
    setGitLoading(false);
  };


  const fetchHistory = async (fileId) => {
    try {
      const url = fileId
        ? `/workspaces/${workspaceId}/code-repo/history?file_id=${fileId}`
        : `/workspaces/${workspaceId}/code-repo/history`;
      const res = await api.get(url);
      setHistory(res.data.commits || []);
      setHistoryOpen(true);
    } catch (err) {
      toast.error("Failed to load history");
    }
  };

  const viewCommit = async (commitId) => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/code-repo/commits/${commitId}${repoId ? `?repo_id=${repoId}` : ""}`);
      setActiveCommit(res.data);
      setCommitViewOpen(true);
    } catch (err) {
      toast.error("Failed to load commit");
    }
  };

  const handleAddLink = async (targetType, targetId) => {
    try {
      await api.post(`/workspaces/${workspaceId}/code-repo/links${repoId ? `?repo_id=${repoId}` : ""}`, {
        target_type: targetType,
        target_id: targetId,
      });
      toast.success("Linked!");
      fetchLinks();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to link");
    }
  };

  const handleRemoveLink = async (linkId) => {
    try {
      await api.delete(`/workspaces/${workspaceId}/code-repo/links/${linkId}${repoId ? `?repo_id=${repoId}` : ""}`);
      fetchLinks();
    } catch (err) {
      toast.error("Failed to unlink");
    }
  };

  const handleContextMenu = (e, file) => {
    setContextFile(file);
    setContextMenu({ x: e.clientX, y: e.clientY });
  };

  // Close context menu on click outside
  useEffect(() => {
    const handler = () => setContextMenu(null);
    if (contextMenu) document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, [contextMenu]);

  const hasUnsavedChanges = fileContent !== originalContent;

  const filteredFiles = useMemo(() => searchQuery
    ? files.filter(f => f.path.toLowerCase().includes(searchQuery.toLowerCase()))
    : files, [files, searchQuery]);

  const tree = useMemo(() => buildTree(filteredFiles), [filteredFiles]);

  const handleEditorMount = (editor) => {
    editorRef.current = editor;
    // Ctrl+S to save
    editor.addCommand(2097, () => { handleSave(); });
    
    // Send cursor position updates + content sync via Yjs
    editor.onDidChangeCursorPosition((e) => {
      if (collabWsRef.current?.provider) {
        // Yjs handles sync automatically
      }
    });
    editor.onDidChangeModelContent(() => {
      if (collabWsRef.current?.ytext) {
        const model = editor.getModel();
        if (model) {
          const newVal = model.getValue();
          const ytext = collabWsRef.current.ytext;
          if (ytext.toString() !== newVal) {
            collabWsRef.current.ydoc.transact(() => {
              ytext.delete(0, ytext.length);
              ytext.insert(0, newVal);
            });
          }
        }
      }
    });
  };

  if (!isOpen) return null;

  return (
    <div
      className={isInline
        ? "flex-1 flex flex-col bg-zinc-950 border-l border-zinc-800 min-h-0"
        : "fixed inset-y-0 right-0 z-50 flex flex-col bg-zinc-950 border-l border-zinc-800 shadow-2xl"
      }
      style={isInline ? {} : { width: "min(45vw, 800px)", maxWidth: "calc(100vw - 320px)" }}
      data-testid="code-repo-panel"
    >
      {/* Header */}
      <RepoToolbar
        files={files} currentBranch={currentBranch} branches={branches}
        setCurrentBranch={setCurrentBranch} setBranchDialogOpen={setBranchDialogOpen}
        setGitAction={setGitAction} setGitDialogOpen={setGitDialogOpen}
        workspaceId={workspaceId} repoId={repoId}
        setLinksOpen={setLinksOpen} onClose={onClose} isInline={isInline}
      />

      {/* Main content: file tree + editor */}
      <div className="flex-1 flex min-h-0">
        {/* File Tree Sidebar */}
        <div className="w-56 flex-shrink-0 border-r border-zinc-800/60 flex flex-col bg-zinc-900/40">
          {/* File tree header */}
          <div className="flex items-center gap-1 px-2 py-1.5 border-b border-zinc-800/40">
            <div className="flex-1 relative">
              <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-zinc-600" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search files..."
                className="w-full bg-transparent text-xs text-zinc-300 placeholder:text-zinc-600 pl-6 pr-2 py-1 rounded border border-transparent focus:border-zinc-700 focus:outline-none"
                data-testid="file-search-input"
              />
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="p-1 rounded text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors" data-testid="new-file-menu-btn">
                  <Plus className="w-3.5 h-3.5" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent className="bg-zinc-900 border-zinc-800" align="end">
                <DropdownMenuItem
                  onClick={() => { setNewFileIsFolder(false); setNewFileDialog(true); }}
                  className="text-zinc-300 hover:bg-zinc-800 cursor-pointer text-xs"
                >
                  <FilePlus className="w-3.5 h-3.5 mr-2" />
                  New File
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => { setNewFileIsFolder(true); setNewFileDialog(true); }}
                  className="text-zinc-300 hover:bg-zinc-800 cursor-pointer text-xs"
                >
                  <FolderPlus className="w-3.5 h-3.5 mr-2" />
                  New Folder
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          {/* File tree */}
          <ScrollArea className="flex-1">
            <div className="py-1">
              {Object.entries(tree.children).sort(([a], [b]) => a.localeCompare(b)).map(([name, node]) => (
                <TreeNode
                  key={name}
                  name={name}
                  node={node}
                  depth={0}
                  onSelectFile={handleSelectFile}
                  selectedFileId={selectedFile?.file_id}
                  onContextMenu={handleContextMenu}
                />
              ))}
              <RootFileList
                files={tree.files}
                onSelectFile={handleSelectFile}
                selectedFileId={selectedFile?.file_id}
                onContextMenu={handleContextMenu}
              />
              {files.length === 0 && (
                <div className="px-4 py-8 text-center">
                  <FileCode className="w-8 h-8 text-zinc-700 mx-auto mb-2" />
                  <p className="text-[11px] text-zinc-600">No files yet</p>
                  <button
                    onClick={() => { setNewFileIsFolder(false); setNewFileDialog(true); }}
                    className="text-[11px] text-emerald-400 hover:text-emerald-300 mt-1"
                    data-testid="empty-create-file-btn"
                  >
                    Create your first file
                  </button>
                </div>
              )}
            </div>
          </ScrollArea>
        </div>

        {/* Editor Area */}
        <div className="flex-1 flex flex-col min-w-0">
          <RepoEditor
            selectedFile={selectedFile}
            fileContent={fileContent}
            setFileContent={setFileContent}
            hasUnsavedChanges={hasUnsavedChanges}
            saving={saving}
            handleSave={handleSave}
            handleEditorMount={handleEditorMount}
            fetchHistory={fetchHistory}
            handleDeleteFile={handleDeleteFile}
            setRenameFileId={setRenameFileId}
            setRenamePath={setRenamePath}
            setRenameDialog={setRenameDialog}
            collabParticipants={collabParticipants}
            loading={loading}
          />
        </div>
      </div>

      {/* Context Menu */}
      {contextMenu && contextFile && (
        <div
          className="fixed z-[100] bg-zinc-900 border border-zinc-800 rounded-lg shadow-xl py-1 min-w-[140px]"
          style={{ top: contextMenu.y, left: contextMenu.x }}
        >
          {!contextFile.is_folder && (
            <button
              onClick={() => { handleSelectFile(contextFile); setContextMenu(null); }}
              className="w-full px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-800 text-left flex items-center gap-2"
            >
              <File className="w-3 h-3" /> Open
            </button>
          )}
          <button
            onClick={() => {
              setRenameFileId(contextFile.file_id);
              setRenamePath(contextFile.path);
              setRenameDialog(true);
              setContextMenu(null);
            }}
            className="w-full px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-800 text-left flex items-center gap-2"
          >
            <Pencil className="w-3 h-3" /> Rename
          </button>
          <button
            onClick={() => { handleDeleteFile(contextFile.file_id); setContextMenu(null); }}
            className="w-full px-3 py-1.5 text-xs text-red-400 hover:bg-zinc-800 text-left flex items-center gap-2"
          >
            <Trash2 className="w-3 h-3" /> Delete
          </button>
        </div>
      )}

      {/* Dialogs */}
      <RepoDialogs
        newFileDialog={newFileDialog} setNewFileDialog={setNewFileDialog}
        newFileIsFolder={newFileIsFolder} newFilePath={newFilePath} setNewFilePath={setNewFilePath}
        handleCreateFile={handleCreateFile}
        renameDialog={renameDialog} setRenameDialog={setRenameDialog}
        renamePath={renamePath} setRenamePath={setRenamePath} handleRenameFile={handleRenameFile}
        historyOpen={historyOpen} setHistoryOpen={setHistoryOpen}
        fileHistory={fileHistory} commitDetail={commitDetail} setCommitDetail={setCommitDetail}
        handleRevert={handleRevert}
        linksOpen={linksOpen} setLinksOpen={setLinksOpen}
        repoLinks={repoLinks} channels={channels} projects={projects}
        handleAddLink={handleAddLink} handleRemoveLink={handleRemoveLink}
        branchDialogOpen={branchDialogOpen} setBranchDialogOpen={setBranchDialogOpen}
        newBranchName={newBranchName} setNewBranchName={setNewBranchName}
        handleCreateBranch={handleCreateBranch}
        currentBranch={currentBranch} branches={branches} handleMergeBranch={handleMergeBranch}
        gitDialogOpen={gitDialogOpen} setGitDialogOpen={setGitDialogOpen}
        gitAction={gitAction} gitUrl={gitUrl} setGitUrl={setGitUrl}
        gitPat={gitPat} setGitPat={setGitPat} gitBranch={gitBranch} setGitBranch={setGitBranch}
        gitLoading={gitLoading} handleGitAction={handleGitAction}
        mergePreview={mergePreview} setMergePreview={setMergePreview}
        merging={merging} confirmMerge={confirmMerge}
      />
    </div>
  );
};

export default CodeRepoPanel;
