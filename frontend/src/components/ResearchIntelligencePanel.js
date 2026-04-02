import { useState, useEffect } from "react";
import { api } from "@/App";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Loader2, BookOpen, Plus, Upload, Search, MessageSquare, RefreshCw, Trash2, FileText, ArrowRight, Send, ChevronRight, GitBranch } from "lucide-react";
import { toast } from "sonner";

const STATUS_COLORS = { completed: "bg-emerald-500/15 text-emerald-400", processing: "bg-amber-500/15 text-amber-400", failed: "bg-red-500/15 text-red-400", metadata_only: "bg-zinc-800 text-zinc-400", pending: "bg-zinc-800 text-zinc-500" };

export default function ResearchIntelligencePanel({ workspaceId }) {
  const [tab, setTab] = useState("libraries");
  const [libraries, setLibraries] = useState([]);
  const [selectedLib, setSelectedLib] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [chatQuery, setChatQuery] = useState("");
  const [chatResult, setChatResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [chatLoading, setChatLoading] = useState(false);
  const [newLibName, setNewLibName] = useState("");

  useEffect(() => { loadLibraries(); }, [workspaceId]);

  const loadLibraries = async () => {
    setLoading(true);
    try {
      const r = await api.get(`/workspaces/${workspaceId}/research-libraries`);
      setLibraries(r.data?.libraries || []);
    } catch {}
    setLoading(false);
  };

  const createLibrary = async () => {
    if (!newLibName.trim()) return;
    try {
      await api.post(`/workspaces/${workspaceId}/research-libraries`, { name: newLibName });
      setNewLibName("");
      toast.success("Library created");
      loadLibraries();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const selectLibrary = async (lib) => {
    setSelectedLib(lib);
    setTab("documents");
    try {
      const r = await api.get(`/research-libraries/${lib.library_id}/documents`);
      setDocuments(r.data?.documents || []);
    } catch {}
  };

  const askResearch = async () => {
    if (!chatQuery.trim() || !selectedLib) return;
    setChatLoading(true);
    try {
      const r = await api.post(`/research-libraries/${selectedLib.library_id}/chat`, { query: chatQuery });
      setChatResult(r.data);
    } catch (e) { toast.error(e.response?.data?.detail || "Chat failed"); }
    setChatLoading(false);
  };

  const searchDocs = async () => {
    if (!chatQuery.trim() || !selectedLib) return;
    setChatLoading(true);
    try {
      const r = await api.post(`/research-libraries/${selectedLib.library_id}/search`, { query: chatQuery });
      setChatResult({ search_results: r.data?.results || [] });
    } catch {}
    setChatLoading(false);
  };

  const tabs = [
    { key: "libraries", label: "Libraries" },
    { key: "documents", label: "Documents", hidden: !selectedLib },
    { key: "chat", label: "Research Chat", hidden: !selectedLib },
  ];

  if (loading) return <div className="p-8 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-zinc-500" /></div>;

  return (
    <div className="p-6 space-y-6" data-testid="research-intelligence-panel">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center">
            <BookOpen className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-zinc-100" style={{ fontFamily: 'Syne, sans-serif' }}>Research Intelligence</h2>
            <p className="text-xs text-zinc-500">Deep document analysis with citation-linked AI responses, literature review automation, and cross-document synthesis</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={loadLibraries} className="border-zinc-700 text-zinc-400"><RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Refresh</Button>
      </div>

      <div className="flex gap-1 border-b border-zinc-800">
        {tabs.filter(t => !t.hidden).map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors ${tab === t.key ? "text-zinc-100 border-blue-500" : "text-zinc-500 border-transparent hover:text-zinc-300"}`}>{t.label}</button>
        ))}
      </div>

      {tab === "libraries" && (
        <div className="space-y-3">
          <div className="flex gap-2">
            <Input value={newLibName} onChange={e => setNewLibName(e.target.value)} placeholder="New library name..."
              className="bg-zinc-950 border-zinc-800 text-sm flex-1" />
            <Button size="sm" onClick={createLibrary} disabled={!newLibName.trim()} className="bg-blue-600 hover:bg-blue-500 text-white text-xs">
              <Plus className="w-3 h-3 mr-1" /> Create
            </Button>
          </div>
          {libraries.length === 0 ? (
            <div className="text-center py-12 text-zinc-500 text-sm">No research libraries yet.</div>
          ) : libraries.map(lib => (
            <div key={lib.library_id} className="p-4 rounded-xl bg-zinc-950/50 border border-zinc-800/40 hover:border-zinc-700 cursor-pointer transition-colors"
              onClick={() => selectLibrary(lib)}>
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-sm font-medium text-zinc-200">{lib.name}</span>
                  <p className="text-xs text-zinc-500 mt-0.5">{lib.doc_count || 0} documents · {(lib.tags || []).join(", ")}</p>
                </div>
                <ChevronRight className="w-4 h-4 text-zinc-600" />
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === "documents" && selectedLib && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <button onClick={() => { setSelectedLib(null); setTab("libraries"); }} className="text-xs text-zinc-500 hover:text-zinc-300">&larr; Back to libraries</button>
            <span className="text-xs text-zinc-400">{selectedLib.name} · {documents.length} documents</span>
          </div>
          {documents.length === 0 ? (
            <div className="text-center py-12 text-zinc-500 text-sm">No documents in this library yet. Upload PDFs or DOCX files to start.</div>
          ) : documents.map(doc => (
            <div key={doc.doc_id} className="p-3 rounded-xl bg-zinc-950/50 border border-zinc-800/40">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-2.5 min-w-0 flex-1">
                  <FileText className="w-4 h-4 text-blue-400 mt-0.5 shrink-0" />
                  <div className="min-w-0">
                    <p className="text-sm text-zinc-200 truncate">{doc.title}</p>
                    <p className="text-xs text-zinc-500">{(doc.authors || []).slice(0, 3).join(", ")}{doc.authors?.length > 3 ? " et al." : ""}</p>
                    <div className="flex items-center gap-2 mt-1 text-[10px] text-zinc-600">
                      <Badge className={`text-[9px] ${STATUS_COLORS[doc.ingestion_status] || STATUS_COLORS.pending}`}>{doc.ingestion_status}</Badge>
                      <span>{doc.chunk_count || 0} chunks</span>
                      <span>{doc.page_count || 0} pages</span>
                      {doc.doi && <span className="text-blue-400">{doc.doi}</span>}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === "chat" && selectedLib && (
        <div className="space-y-4">
          <div className="flex gap-2">
            <Input value={chatQuery} onChange={e => setChatQuery(e.target.value)}
              onKeyDown={e => e.key === "Enter" && askResearch()}
              placeholder="Ask a research question..." className="bg-zinc-950 border-zinc-800 text-sm flex-1" />
            <Button size="sm" onClick={askResearch} disabled={chatLoading || !chatQuery.trim()} className="bg-blue-600 hover:bg-blue-500 text-white text-xs">
              {chatLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
            </Button>
            <Button size="sm" variant="outline" onClick={searchDocs} disabled={chatLoading} className="border-zinc-700 text-zinc-400 text-xs">
              <Search className="w-3.5 h-3.5" />
            </Button>
          </div>
          {chatResult && (
            <div className="space-y-3">
              {chatResult.answer && (
                <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/40">
                  <p className="text-sm text-zinc-300 whitespace-pre-wrap leading-relaxed">{chatResult.answer}</p>
                  {chatResult.citations && Object.keys(chatResult.citations).length > 0 && (
                    <div className="mt-3 border-t border-zinc-800/40 pt-3">
                      <p className="text-[10px] text-zinc-500 uppercase mb-2">Sources</p>
                      <div className="space-y-1">
                        {Object.entries(chatResult.citations).map(([marker, cite]) => (
                          <div key={marker} className="flex items-start gap-2 text-xs">
                            <Badge className="text-[8px] bg-blue-500/15 text-blue-400 shrink-0">{marker}</Badge>
                            <div className="min-w-0">
                              <span className="text-zinc-300">{cite.doc_title}</span>
                              <span className="text-zinc-600"> · {cite.section} · p.{cite.page}</span>
                              <p className="text-zinc-500 truncate">{cite.excerpt}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
              {chatResult.search_results && (
                <div className="space-y-2">
                  {chatResult.search_results.map((r, i) => (
                    <div key={r.chunk_id || i} className="p-3 rounded-lg bg-zinc-950/50 border border-zinc-800/30 text-xs">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge className="text-[8px] bg-zinc-800 text-zinc-400">{r.doc_title || r.doc_id}</Badge>
                        <span className="text-zinc-500">{r.section_title} · p.{r.page_num}</span>
                      </div>
                      <p className="text-zinc-400">{r.content?.substring(0, 300)}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
