import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import { handleSilent } from "@/lib/errorHandler";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  GraduationCap, Globe, FileText, Trash2, Search, Plus, Loader2, X,
  Upload, AlertTriangle, Download, Brain, Zap, ChevronDown, ChevronRight,
  Clock, BarChart3, CheckCircle2, XCircle, RefreshCw
} from "lucide-react";

import TrainingAnalytics from "@/components/TrainingAnalytics";
import AgentVersioning from "@/components/AgentVersioning";

const DEPTH_OPTIONS = [
  { value: "quick", label: "Quick", desc: "~3 sources", color: "text-zinc-400" },
  { value: "standard", label: "Standard", desc: "~8 sources", color: "text-cyan-400" },
  { value: "comprehensive", label: "Deep", desc: "~15 sources", color: "text-amber-400" },
];

export default function AgentTraining({ workspaceId, agentId: propAgentId, agentName: propAgentName }) {
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(propAgentId || null);
  const [selectedAgentName, setSelectedAgentName] = useState(propAgentName || "");
  const agentId = selectedAgent;
  const agentName = selectedAgentName;

  const [sessions, setSessions] = useState([]);
  const [knowledge, setKnowledge] = useState({ chunks: [], topics: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [staleness, setStaleness] = useState(null);
  const [view, setView] = useState("dashboard"); // dashboard | new-session | knowledge | analytics | versions
  const [mode, setMode] = useState("topics"); // topics | url | text | file
  const [expandedSession, setExpandedSession] = useState(null);

  // Topic training state
  const [topicItems, setTopicItems] = useState([{ topic: "", depth: "standard" }]);
  const [manualUrls, setManualUrls] = useState("");
  const [topicSuggestions, setTopicSuggestions] = useState([]);

  // URL/Text/File training state
  const [urls, setUrls] = useState("");
  const [urlTopics, setUrlTopics] = useState("");
  const [textTitle, setTextTitle] = useState("");
  const [textContent, setTextContent] = useState("");
  const [textTopic, setTextTopic] = useState("general");
  const [fileTopic, setFileTopic] = useState("general");
  const [ingesting, setIngesting] = useState(false);
  const [uploading, setUploading] = useState(false);

  // Active training progress
  const [activeSession, setActiveSession] = useState(null);
  const [progress, setProgress] = useState(null);
  const progressRef = useRef(null);

  // Knowledge query
  const [queryText, setQueryText] = useState("");
  const [queryResults, setQueryResults] = useState(null);
  const [topicFilter, setTopicFilter] = useState(null);

  // Auto-refresh state
  const [autoRefresh, setAutoRefresh] = useState({ enabled: false, interval_days: 30 });

  // Fetch agents for selector
  useEffect(() => {
    if (propAgentId) return;
    api.get(`/workspaces/${workspaceId}/agents`).then(res => {
      const list = Array.isArray(res.data) ? res.data : res.data.agents || [];
      setAgents(list);
      if (list.length === 1) {
        setSelectedAgent(list[0].agent_id);
        setSelectedAgentName(list[0].name);
      }
    }).catch(() => {});
  }, [workspaceId, propAgentId]);

  const fetchData = useCallback(async () => {
    if (!agentId) { setLoading(false); return; }
    try {
      const [sessRes, knowledgeRes, stalenessRes] = await Promise.all([
        api.get(`/workspaces/${workspaceId}/agents/${agentId}/training-sessions`),
        api.get(`/workspaces/${workspaceId}/agents/${agentId}/knowledge${topicFilter ? `?topic=${topicFilter}` : ""}`),
        api.get(`/workspaces/${workspaceId}/agents/${agentId}/train/staleness?threshold_days=30`).catch(() => ({ data: null })),
      ]);
      setSessions(sessRes.data || []);
      setKnowledge(knowledgeRes.data || { chunks: [], topics: [], total: 0 });
      setStaleness(stalenessRes.data);
    } catch (err) { handleSilent(err, "AgentTraining:fetch"); }
    setLoading(false);
  }, [workspaceId, agentId, topicFilter]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Fetch auto-refresh settings
  useEffect(() => {
    if (!agentId) return;
    api.get(`/workspaces/${workspaceId}/agents/${agentId}/training/auto-refresh`)
      .then(res => setAutoRefresh(res.data))
      .catch(() => {});
  }, [workspaceId, agentId]);

  // Fetch topic suggestions
  useEffect(() => {
    if (!agentId) return;
    api.post(`/workspaces/${workspaceId}/agents/${agentId}/train/suggest-topics`, { skill_ids: [] })
      .then(res => setTopicSuggestions(res.data.suggestions || []))
      .catch(() => {});
  }, [workspaceId, agentId]);

  // Poll training progress
  useEffect(() => {
    if (!activeSession) return;
    const interval = setInterval(async () => {
      try {
        const res = await api.get(`/workspaces/${workspaceId}/agents/${agentId}/training-sessions/${activeSession}/progress`);
        setProgress(res.data);
        if (res.data.status === "completed" || res.data.status === "failed") {
          clearInterval(interval);
          setActiveSession(null);
          fetchData();
          if (res.data.status === "completed") toast.success(`Training complete! ${res.data.total_chunks || 0} chunks extracted`);
          else toast.error("Training failed");
        }
      } catch { /* ignore */ }
    }, 1500);
    progressRef.current = interval;
    return () => clearInterval(interval);
  }, [activeSession, workspaceId, agentId, fetchData]);

  // --- Training Actions ---
  const startTopicTraining = async () => {
    const validTopics = topicItems.filter(t => t.topic.trim());
    if (!validTopics.length) { toast.error("Add at least one topic"); return; }
    setIngesting(true);
    try {
      const res = await api.post(`/workspaces/${workspaceId}/agents/${agentId}/train/topics`, {
        topics: validTopics.map(t => ({ topic: t.topic.trim(), depth: t.depth })),
        manual_urls: manualUrls.split("\n").map(u => u.trim()).filter(Boolean),
      });
      setActiveSession(res.data.session_id);
      setProgress({ status: "pending", progress_pct: 0 });
      setView("dashboard");
      toast.success("Training session started");
    } catch (err) { toast.error("Failed to start training"); handleSilent(err, "train:topics"); }
    setIngesting(false);
  };

  const trainFromUrl = async () => {
    const urlList = urls.split("\n").map(u => u.trim()).filter(Boolean);
    if (!urlList.length) { toast.error("Enter at least one URL"); return; }
    setIngesting(true);
    try {
      const topicList = urlTopics.split(",").map(t => t.trim()).filter(Boolean);
      const res = await api.post(`/workspaces/${workspaceId}/agents/${agentId}/train/url`, { urls: urlList, topics: topicList });
      toast.success(`Ingested ${res.data.total_chunks} chunks from ${res.data.successful_urls} URLs`);
      if (res.data.failed_urls?.length) toast.error(`${res.data.failed_urls.length} URLs failed`);
      setUrls(""); setUrlTopics("");
      fetchData();
    } catch (err) { toast.error("Training failed"); } finally { setIngesting(false); }
  };

  const trainFromText = async () => {
    if (!textContent.trim()) { toast.error("Enter some content"); return; }
    setIngesting(true);
    try {
      const res = await api.post(`/workspaces/${workspaceId}/agents/${agentId}/train/text`, { title: textTitle, content: textContent, topic: textTopic });
      toast.success(`Ingested ${res.data.total_chunks} chunks`);
      setTextTitle(""); setTextContent("");
      fetchData();
    } catch (err) { toast.error("Training failed"); } finally { setIngesting(false); }
  };

  const handleFileUpload = async (file) => {
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("topic", fileTopic);
      const res = await api.post(`/workspaces/${workspaceId}/agents/${agentId}/train/file`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success(`Uploaded ${file.name}: ${res.data.total_chunks} chunks`);
      fetchData();
    } catch (err) { toast.error("File upload failed"); handleSilent(err, "train:file"); }
    setUploading(false);
  };

  const deleteChunk = async (chunkId) => {
    try {
      await api.delete(`/workspaces/${workspaceId}/agents/${agentId}/knowledge/${chunkId}`);
      fetchData();
    } catch { toast.error("Delete failed"); }
  };

  const queryKnowledge = async () => {
    if (!queryText.trim()) return;
    try {
      const res = await api.post(`/workspaces/${workspaceId}/agents/${agentId}/knowledge/query`, { query: queryText, top_k: 5 });
      setQueryResults(res.data);
    } catch { toast.error("Query failed"); }
  };

  if (!agentId) {
    return (
      <div className="flex-1 flex items-center justify-center p-6" data-testid="agent-training-select">
        <div className="text-center max-w-sm">
          <GraduationCap className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
          <p className="text-sm text-zinc-400 mb-4">Select an agent to train</p>
          {agents.length > 0 ? (
            <div className="space-y-1.5">
              {agents.map(a => (
                <button key={a.agent_id} onClick={() => { setSelectedAgent(a.agent_id); setSelectedAgentName(a.name); }}
                  className="w-full flex items-center gap-3 px-3 py-2 rounded-lg bg-zinc-900/50 border border-zinc-800/40 hover:border-zinc-700 transition-colors text-left"
                  data-testid={`select-agent-${a.agent_id}`}>
                  <Brain className="w-4 h-4 text-cyan-400 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-zinc-300 truncate">{a.name}</p>
                    <p className="text-[9px] text-zinc-600">{a.training?.total_chunks || 0} chunks / {a.training?.total_sessions || 0} sessions</p>
                  </div>
                  <ChevronRight className="w-3.5 h-3.5 text-zinc-600" />
                </button>
              ))}
            </div>
          ) : (
            <p className="text-xs text-zinc-600">No agents found. Create one in the Agent Studio first.</p>
          )}
        </div>
      </div>
    );
  }

  if (loading) return <div className="flex-1 flex items-center justify-center"><Loader2 className="w-5 h-5 animate-spin text-zinc-500" /></div>;

  return (
    <div className="flex-1 flex flex-col overflow-hidden" data-testid="agent-training">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-zinc-800/60">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100 flex items-center gap-2" style={{ fontFamily: "Syne, sans-serif" }}>
              {!propAgentId && (
                <button onClick={() => { setSelectedAgent(null); setSelectedAgentName(""); }} className="text-zinc-500 hover:text-zinc-300 transition-colors" data-testid="train-back-btn">
                  <ChevronRight className="w-4 h-4 rotate-180" />
                </button>
              )}
              <GraduationCap className="w-5 h-5 text-amber-400" /> Train {agentName || "Agent"}
            </h2>
            <p className="text-xs text-zinc-500 mt-0.5">{knowledge.total} knowledge chunks / {knowledge.topics?.length || 0} topics / {sessions.length} sessions</p>
          </div>
          <div className="flex gap-1.5">
            <div className="flex gap-1 bg-zinc-800/50 rounded-lg p-0.5 mr-2">
              {[
                { key: "dashboard", label: "Dashboard" },
                { key: "new-session", label: "New Session" },
                { key: "knowledge", label: "Knowledge" },
                { key: "analytics", label: "Analytics" },
                { key: "versions", label: "Versions" },
              ].map(v => (
                <button key={v.key} onClick={() => setView(v.key)}
                  className={`px-3 py-1 text-xs rounded-md transition-colors ${view === v.key ? "bg-zinc-700 text-zinc-200" : "text-zinc-500 hover:text-zinc-300"}`}
                  data-testid={`train-view-${v.key}`}>
                  {v.label}
                </button>
              ))}
            </div>
            <Button size="sm" variant="outline" className="text-xs h-7 border-zinc-700 text-zinc-400 hover:text-zinc-200" data-testid="export-knowledge-btn"
              onClick={async () => {
                try {
                  const res = await api.get(`/workspaces/${workspaceId}/agents/${agentId}/knowledge/export`);
                  const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: "application/json" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a"); a.href = url; a.download = `knowledge_${agentId}.json`; a.click();
                  URL.revokeObjectURL(url);
                  toast.success("Knowledge pack exported");
                } catch (err) { handleSilent(err, "export"); toast.error("Export failed"); }
              }}>
              <Download className="w-3 h-3 mr-1" /> Export
            </Button>
            <Button size="sm" variant="outline" className="text-xs h-7 border-zinc-700 text-zinc-400 hover:text-zinc-200" data-testid="import-knowledge-btn"
              onClick={() => document.getElementById("knowledge-import-input")?.click()}>
              <Upload className="w-3 h-3 mr-1" /> Import
            </Button>
            <input id="knowledge-import-input" type="file" accept=".json" className="hidden"
              onChange={async (e) => {
                const file = e.target.files?.[0]; if (!file) return;
                const formData = new FormData(); formData.append("file", file);
                try {
                  const res = await api.post(`/workspaces/${workspaceId}/agents/${agentId}/knowledge/import`, formData, { headers: { "Content-Type": "multipart/form-data" } });
                  toast.success(`Imported ${res.data.imported} chunks (${res.data.skipped_duplicates} skipped)`);
                  fetchData();
                } catch (err) { handleSilent(err, "import"); toast.error("Import failed"); }
                e.target.value = "";
              }} />
          </div>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-6 space-y-6 max-w-4xl mx-auto">
          {/* Active Training Progress */}
          {progress && activeSession && (
            <ActiveTrainingProgress progress={progress} sessionId={activeSession} />
          )}

          {/* Dashboard View */}
          {view === "dashboard" && (
            <DashboardView
              sessions={sessions} staleness={staleness} knowledge={knowledge}
              expandedSession={expandedSession} setExpandedSession={setExpandedSession}
              onNewSession={() => setView("new-session")}
              workspaceId={workspaceId} agentId={agentId}
            />
          )}

          {/* New Session View */}
          {view === "new-session" && (
            <NewSessionView
              mode={mode} setMode={setMode}
              topicItems={topicItems} setTopicItems={setTopicItems}
              manualUrls={manualUrls} setManualUrls={setManualUrls}
              topicSuggestions={topicSuggestions}
              urls={urls} setUrls={setUrls}
              urlTopics={urlTopics} setUrlTopics={setUrlTopics}
              textTitle={textTitle} setTextTitle={setTextTitle}
              textContent={textContent} setTextContent={setTextContent}
              textTopic={textTopic} setTextTopic={setTextTopic}
              fileTopic={fileTopic} setFileTopic={setFileTopic}
              ingesting={ingesting} uploading={uploading}
              startTopicTraining={startTopicTraining}
              trainFromUrl={trainFromUrl}
              trainFromText={trainFromText}
              handleFileUpload={handleFileUpload}
            />
          )}

          {/* Knowledge View */}
          {view === "knowledge" && (
            <KnowledgeView
              knowledge={knowledge} topicFilter={topicFilter} setTopicFilter={setTopicFilter}
              queryText={queryText} setQueryText={setQueryText}
              queryResults={queryResults} queryKnowledge={queryKnowledge}
              deleteChunk={deleteChunk}
            />
          )}

          {/* Analytics View */}
          {view === "analytics" && (
            <TrainingAnalytics workspaceId={workspaceId} agentId={agentId} agentName={agentName} />
          )}

          {/* Versions View */}
          {view === "versions" && (
            <AgentVersioning workspaceId={workspaceId} agentId={agentId} agentName={agentName} />
          )}

          {/* Auto-Refresh Settings (shown on dashboard) */}
          {view === "dashboard" && agentId && (
            <AutoRefreshToggle
              autoRefresh={autoRefresh}
              onChange={async (enabled, interval_days) => {
                try {
                  const res = await api.put(`/workspaces/${workspaceId}/agents/${agentId}/training/auto-refresh`, { enabled, interval_days });
                  setAutoRefresh(res.data);
                  toast.success(enabled ? `Auto-refresh enabled (every ${interval_days} days)` : "Auto-refresh disabled");
                } catch { toast.error("Failed to update"); }
              }}
            />
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

/* ---- Sub-components ---- */

function ActiveTrainingProgress({ progress, sessionId }) {
  const pct = progress.progress_pct || 0;
  const statusColors = {
    pending: "text-zinc-400", crawling: "text-cyan-400", extracting: "text-amber-400",
    indexing: "text-violet-400", completed: "text-emerald-400", failed: "text-red-400",
  };
  return (
    <div className="bg-zinc-900/60 border border-zinc-800/40 rounded-xl p-4 space-y-3" data-testid="training-progress">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin text-cyan-400" />
          <span className="text-sm font-medium text-zinc-200">Training in Progress</span>
        </div>
        <Badge variant="secondary" className={`text-[10px] ${statusColors[progress.status] || "text-zinc-400"}`}>
          {progress.status}
        </Badge>
      </div>
      <Progress value={pct} className="h-1.5" />
      <div className="flex items-center justify-between text-[10px] text-zinc-500">
        <span>{progress.current_topic ? `Processing: ${progress.current_topic}` : `Session: ${sessionId.slice(0, 16)}...`}</span>
        <div className="flex gap-3">
          {progress.topic_index !== undefined && <span>Topic {progress.topic_index + 1}/{progress.total_topics}</span>}
          <span>{progress.total_chunks || 0} chunks</span>
          <span>{pct}%</span>
        </div>
      </div>
    </div>
  );
}

function DashboardView({ sessions, staleness, knowledge, expandedSession, setExpandedSession, onNewSession, workspaceId, agentId }) {
  return (
    <>
      {/* Staleness Alert */}
      {staleness && (staleness.stale_count > 0 || staleness.never_used_count > 0) && (
        <div className="bg-amber-950/20 border border-amber-900/30 rounded-lg p-3 flex items-start gap-3" data-testid="staleness-indicator">
          <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-xs font-medium text-amber-300">Knowledge Health</p>
            <div className="flex gap-4 mt-1 text-[10px] text-zinc-400">
              {staleness.stale_count > 0 && <span><strong className="text-amber-400">{staleness.stale_count}</strong> stale</span>}
              {staleness.never_used_count > 0 && <span><strong className="text-zinc-300">{staleness.never_used_count}</strong> never used</span>}
              <span>{staleness.fresh_count} fresh</span>
            </div>
          </div>
        </div>
      )}

      {/* Stats Row */}
      <div className="grid grid-cols-4 gap-3">
        <StatCard label="Total Chunks" value={knowledge.total} color="text-cyan-400" />
        <StatCard label="Topics" value={knowledge.topics?.length || 0} color="text-amber-400" />
        <StatCard label="Sessions" value={sessions.length} color="text-violet-400" />
        <StatCard label="Avg Quality" value={sessions.length ? `${Math.round(sessions.reduce((s, x) => s + (x.quality_score || 0), 0) / Math.max(sessions.length, 1))}%` : "—"} color="text-emerald-400" />
      </div>

      {/* New Session CTA */}
      <Button onClick={onNewSession} className="w-full bg-cyan-600/10 hover:bg-cyan-600/20 text-cyan-400 border border-cyan-500/20 gap-2" data-testid="new-training-session-btn">
        <Plus className="w-4 h-4" /> New Training Session
      </Button>

      {/* Sessions List */}
      {sessions.length > 0 ? (
        <div className="space-y-2">
          <p className="text-sm font-semibold text-zinc-300">Training Sessions</p>
          {sessions.map(s => {
            const isExpanded = expandedSession === s.session_id;
            const StatusIcon = s.status === "completed" ? CheckCircle2 : s.status === "failed" ? XCircle : Loader2;
            const statusColor = s.status === "completed" ? "text-emerald-400" : s.status === "failed" ? "text-red-400" : "text-amber-400";
            const sourceIcon = s.source_type === "topics" ? Brain : s.source_type === "url" ? Globe : s.source_type === "file" ? Upload : FileText;
            const SrcIcon = sourceIcon;

            return (
              <div key={s.session_id} className="bg-zinc-900/40 border border-zinc-800/40 rounded-lg overflow-hidden" data-testid={`session-${s.session_id}`}>
                <div className="flex items-center gap-3 p-3 cursor-pointer hover:bg-zinc-800/20 transition-colors"
                  onClick={() => setExpandedSession(isExpanded ? null : s.session_id)}>
                  <SrcIcon className={`w-4 h-4 flex-shrink-0 ${s.source_type === "topics" ? "text-cyan-400" : "text-violet-400"}`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-zinc-300 truncate">
                      {s.source_type === "topics" ? s.topics?.map(t => t.topic).join(", ") || "Topic training" :
                       s.title || s.urls?.join(", ") || "Training session"}
                    </p>
                    <div className="flex gap-3 mt-0.5 text-[9px] text-zinc-600">
                      <span>{s.total_chunks || 0} chunks</span>
                      {s.total_sources > 0 && <span>{s.total_sources} sources</span>}
                      {s.quality_score > 0 && <span>Quality: {Math.round(s.quality_score)}%</span>}
                      {s.duration_seconds > 0 && <span>{s.duration_seconds}s</span>}
                      <span>{new Date(s.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                  <StatusIcon className={`w-4 h-4 flex-shrink-0 ${statusColor} ${s.status === "crawling" || s.status === "extracting" ? "animate-spin" : ""}`} />
                  <ChevronDown className={`w-3.5 h-3.5 text-zinc-600 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                </div>

                {isExpanded && (
                  <div className="px-3 pb-3 border-t border-zinc-800/30 pt-2 space-y-2">
                    {s.topics?.map((t, i) => (
                      <div key={i} className="flex items-center justify-between text-[10px] px-2 py-1 rounded bg-zinc-800/30">
                        <span className="text-zinc-300">{t.topic}</span>
                        <div className="flex gap-2 text-zinc-500">
                          <span>{t.depth || "standard"}</span>
                          <span>{t.sources_found || 0} sources</span>
                          <span>{t.chunks_extracted || 0} chunks</span>
                          <Badge variant="secondary" className={`text-[8px] ${t.status === "completed" ? "bg-emerald-500/10 text-emerald-400" : "bg-zinc-800 text-zinc-500"}`}>{t.status || "—"}</Badge>
                        </div>
                      </div>
                    ))}
                    {s.error && <p className="text-[10px] text-red-400 px-2">Error: {s.error}</p>}
                    <div className="flex gap-2 text-[9px] text-zinc-600 px-2">
                      <span>ID: {s.session_id}</span>
                      {s.started_at && <span>Started: {new Date(s.started_at).toLocaleString()}</span>}
                      {s.completed_at && <span>Completed: {new Date(s.completed_at).toLocaleString()}</span>}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-center py-8">
          <Brain className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
          <p className="text-sm text-zinc-400">No training sessions yet</p>
          <p className="text-xs text-zinc-600 mt-1">Start a new session to give your agent domain expertise</p>
        </div>
      )}
    </>
  );
}

function StatCard({ label, value, color }) {
  return (
    <div className="bg-zinc-900/50 border border-zinc-800/40 rounded-lg p-3 text-center">
      <p className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</p>
      <p className={`text-xl font-bold mt-0.5 ${color}`}>{value}</p>
    </div>
  );
}

function NewSessionView({
  mode, setMode, topicItems, setTopicItems, manualUrls, setManualUrls,
  topicSuggestions, urls, setUrls, urlTopics, setUrlTopics,
  textTitle, setTextTitle, textContent, setTextContent,
  textTopic, setTextTopic, fileTopic, setFileTopic,
  ingesting, uploading, startTopicTraining, trainFromUrl, trainFromText, handleFileUpload,
}) {
  return (
    <>
      {/* Mode Tabs */}
      <div className="flex gap-1 bg-zinc-800/40 rounded-lg p-1">
        {[
          { key: "topics", icon: Brain, label: "Topic Search" },
          { key: "url", icon: Globe, label: "Web URLs" },
          { key: "text", icon: FileText, label: "Text / Docs" },
          { key: "file", icon: Upload, label: "File Upload" },
        ].map(m => (
          <button key={m.key} onClick={() => setMode(m.key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs transition-colors flex-1 justify-center ${mode === m.key ? "bg-zinc-700 text-zinc-200" : "text-zinc-500 hover:text-zinc-300"}`}
            data-testid={`train-mode-${m.key}`}>
            <m.icon className="w-3.5 h-3.5" /> {m.label}
          </button>
        ))}
      </div>

      {/* Topic Search Mode */}
      {mode === "topics" && (
        <div className="bg-zinc-900/50 border border-zinc-800/40 rounded-xl p-4 space-y-4">
          <div>
            <p className="text-xs font-medium text-zinc-300 mb-1">Topics to Learn</p>
            <p className="text-[10px] text-zinc-600 mb-3">Add topics and the system will search the web, extract content, and build your agent's knowledge base.</p>
          </div>

          {/* Topic Suggestions */}
          {topicSuggestions.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-[10px] text-zinc-600 font-medium">Suggested from agent skills:</p>
              <div className="flex flex-wrap gap-1">
                {topicSuggestions.map(s => {
                  const isAdded = topicItems.some(t => t.topic === s);
                  return (
                    <button key={s} onClick={() => {
                      if (!isAdded) setTopicItems(prev => [...prev.filter(t => t.topic), { topic: s, depth: "standard" }]);
                    }}
                      className={`px-2 py-0.5 rounded text-[10px] border transition-colors ${isAdded ? "bg-cyan-500/10 border-cyan-500/30 text-cyan-400" : "bg-zinc-800 border-zinc-700 text-zinc-400 hover:border-zinc-600"}`}
                      data-testid={`suggestion-${s.replace(/\s+/g, '-').toLowerCase()}`}>
                      {isAdded ? "+" : ""} {s}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Topic Items */}
          <div className="space-y-2">
            {topicItems.map((item, i) => (
              <div key={i} className="flex gap-2 items-start">
                <Input value={item.topic} onChange={e => {
                  const next = [...topicItems]; next[i] = { ...next[i], topic: e.target.value }; setTopicItems(next);
                }} placeholder="e.g. OWASP Top 10 2025" className="bg-zinc-950 border-zinc-800 text-zinc-200 text-xs flex-1"
                  data-testid={`topic-input-${i}`} />
                <select value={item.depth} onChange={e => {
                  const next = [...topicItems]; next[i] = { ...next[i], depth: e.target.value }; setTopicItems(next);
                }} className="bg-zinc-950 border border-zinc-800 text-zinc-300 text-xs rounded-md h-9 px-2 w-32"
                  data-testid={`topic-depth-${i}`}>
                  {DEPTH_OPTIONS.map(d => <option key={d.value} value={d.value}>{d.label} ({d.desc})</option>)}
                </select>
                {topicItems.length > 1 && (
                  <button onClick={() => setTopicItems(prev => prev.filter((_, j) => j !== i))}
                    className="text-zinc-600 hover:text-red-400 p-2 transition-colors" data-testid={`remove-topic-${i}`}>
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            ))}
            <button onClick={() => setTopicItems(prev => [...prev, { topic: "", depth: "standard" }])}
              className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1 transition-colors" data-testid="add-topic-btn">
              <Plus className="w-3.5 h-3.5" /> Add Topic
            </button>
          </div>

          {/* Optional URLs */}
          <div>
            <p className="text-[10px] text-zinc-600 font-medium mb-1">Additional URLs (optional)</p>
            <textarea value={manualUrls} onChange={e => setManualUrls(e.target.value)}
              placeholder="https://docs.example.com/guide&#10;https://owasp.org/..."
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-xs text-zinc-200 h-16 resize-none placeholder:text-zinc-700"
              data-testid="training-manual-urls" />
          </div>

          {/* Preview & Start */}
          <div className="flex items-center justify-between pt-2 border-t border-zinc-800/30">
            <div className="text-[10px] text-zinc-500">
              {topicItems.filter(t => t.topic.trim()).length} topics /
              ~{topicItems.reduce((sum, t) => sum + ({ quick: 3, standard: 8, comprehensive: 15 }[t.depth] || 8), 0)} sources estimated
            </div>
            <Button onClick={startTopicTraining} disabled={ingesting}
              className="bg-cyan-600 hover:bg-cyan-700 text-white text-xs gap-1.5" data-testid="start-topic-training-btn">
              {ingesting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Brain className="w-3.5 h-3.5" />}
              {ingesting ? "Starting..." : "Start Training"}
            </Button>
          </div>
        </div>
      )}

      {/* URL Mode */}
      {mode === "url" && (
        <div className="bg-zinc-900/50 border border-zinc-800/40 rounded-xl p-4 space-y-3">
          <textarea value={urls} onChange={e => setUrls(e.target.value)} placeholder="Enter URLs (one per line)..."
            className="w-full h-24 px-3 py-2 rounded-md bg-zinc-950 border border-zinc-800 text-sm text-zinc-200 resize-none placeholder:text-zinc-600" data-testid="train-urls-input" />
          <Input value={urlTopics} onChange={e => setUrlTopics(e.target.value)} placeholder="Topics (comma-separated, optional)"
            className="bg-zinc-950 border-zinc-800 text-zinc-200 text-xs" data-testid="train-topics-input" />
          <Button onClick={trainFromUrl} disabled={ingesting} className="bg-amber-500 hover:bg-amber-400 text-black gap-1 text-xs" data-testid="train-url-submit">
            {ingesting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Globe className="w-3.5 h-3.5" />} {ingesting ? "Crawling..." : "Crawl & Ingest"}
          </Button>
        </div>
      )}

      {/* Text Mode */}
      {mode === "text" && (
        <div className="bg-zinc-900/50 border border-zinc-800/40 rounded-xl p-4 space-y-3">
          <Input value={textTitle} onChange={e => setTextTitle(e.target.value)} placeholder="Title (optional)"
            className="bg-zinc-950 border-zinc-800 text-zinc-200 text-xs" data-testid="train-text-title" />
          <textarea value={textContent} onChange={e => setTextContent(e.target.value)} placeholder="Paste or type knowledge content..."
            className="w-full h-32 px-3 py-2 rounded-md bg-zinc-950 border border-zinc-800 text-sm text-zinc-200 resize-none placeholder:text-zinc-600" data-testid="train-text-content" />
          <div className="flex gap-2">
            <Input value={textTopic} onChange={e => setTextTopic(e.target.value)} placeholder="Topic"
              className="bg-zinc-950 border-zinc-800 text-zinc-200 text-xs w-40" data-testid="train-text-topic" />
            <Button onClick={trainFromText} disabled={ingesting} className="bg-amber-500 hover:bg-amber-400 text-black gap-1 text-xs" data-testid="train-text-submit">
              {ingesting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />} {ingesting ? "Processing..." : "Add Knowledge"}
            </Button>
          </div>
        </div>
      )}

      {/* File Mode */}
      {mode === "file" && (
        <div className="bg-zinc-900/50 border border-zinc-800/40 rounded-xl p-4 space-y-3">
          <div className="border-2 border-dashed border-zinc-700 rounded-lg p-6 text-center hover:border-zinc-600 transition-colors cursor-pointer"
            onClick={() => document.getElementById("file-upload-input")?.click()}
            onDragOver={e => { e.preventDefault(); e.currentTarget.classList.add("border-amber-500"); }}
            onDragLeave={e => { e.currentTarget.classList.remove("border-amber-500"); }}
            onDrop={async e => { e.preventDefault(); e.currentTarget.classList.remove("border-amber-500"); if (e.dataTransfer.files[0]) await handleFileUpload(e.dataTransfer.files[0]); }}
            data-testid="file-drop-zone">
            <Upload className="w-8 h-8 text-zinc-600 mx-auto mb-2" />
            <p className="text-xs text-zinc-400">Drop a file here or click to browse</p>
            <p className="text-[9px] text-zinc-600 mt-1">Supports .txt, .md, .csv, .json files</p>
          </div>
          <input id="file-upload-input" type="file" accept=".txt,.md,.csv,.json" className="hidden"
            onChange={async e => { if (e.target.files[0]) await handleFileUpload(e.target.files[0]); e.target.value = ""; }} />
          <div className="flex gap-2">
            <Input value={fileTopic} onChange={e => setFileTopic(e.target.value)} placeholder="Topic for file content"
              className="bg-zinc-950 border-zinc-800 text-zinc-200 text-xs w-40" data-testid="file-topic-input" />
            {uploading && <div className="flex items-center gap-1 text-xs text-amber-400"><Loader2 className="w-3 h-3 animate-spin" /> Uploading...</div>}
          </div>
        </div>
      )}
    </>
  );
}

function KnowledgeView({ knowledge, topicFilter, setTopicFilter, queryText, setQueryText, queryResults, queryKnowledge, deleteChunk }) {
  return (
    <>
      {/* Knowledge Query */}
      <div className="bg-zinc-900/50 border border-zinc-800/40 rounded-xl p-4">
        <p className="text-xs font-medium text-zinc-400 mb-2">Test Knowledge Retrieval</p>
        <div className="flex gap-2">
          <Input value={queryText} onChange={e => setQueryText(e.target.value)}
            placeholder="Ask a question to test what the agent knows..."
            className="bg-zinc-950 border-zinc-800 text-zinc-200 text-xs flex-1"
            onKeyDown={e => e.key === "Enter" && queryKnowledge()} data-testid="knowledge-query-input" />
          <Button onClick={queryKnowledge} variant="outline" className="border-zinc-700 text-zinc-300 text-xs gap-1" data-testid="knowledge-query-btn">
            <Search className="w-3 h-3" /> Query
          </Button>
        </div>
        {queryResults && (
          <div className="mt-3 space-y-2">
            <p className="text-[10px] text-zinc-600">Found {queryResults.results?.length || 0} relevant chunks (searched {queryResults.total_searched})</p>
            {queryResults.results?.map((r, i) => (
              <div key={i} className="p-2 rounded-lg bg-zinc-800/30 border border-zinc-800/20">
                <div className="flex justify-between items-start mb-1">
                  <Badge variant="secondary" className="text-[9px] bg-amber-500/10 text-amber-400">{r.topic}</Badge>
                  <span className="text-[9px] text-zinc-600">Score: {r.relevance_score}</span>
                </div>
                <p className="text-xs text-zinc-400 line-clamp-3">{r.content}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Knowledge Chunks */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm font-semibold text-zinc-300">Knowledge Base ({knowledge.total})</p>
          <div className="flex gap-1 flex-wrap">
            <button onClick={() => setTopicFilter(null)}
              className={`px-2 py-1 rounded text-[10px] ${!topicFilter ? "bg-zinc-700 text-zinc-100" : "text-zinc-500"}`} data-testid="topic-filter-all">All</button>
            {knowledge.topics?.map(t => (
              <button key={t} onClick={() => setTopicFilter(t)}
                className={`px-2 py-1 rounded text-[10px] ${topicFilter === t ? "bg-zinc-700 text-zinc-100" : "text-zinc-500"}`}
                data-testid={`topic-filter-${t}`}>{t}</button>
            ))}
          </div>
        </div>
        <div className="space-y-1.5">
          {knowledge.chunks?.map(chunk => (
            <div key={chunk.chunk_id} className="flex gap-2 p-2.5 rounded-lg bg-zinc-900/30 border border-zinc-800/20 group" data-testid={`chunk-${chunk.chunk_id}`}>
              <div className="flex-1 min-w-0">
                <div className="flex gap-1.5 mb-0.5 flex-wrap">
                  <Badge variant="secondary" className="text-[8px] bg-zinc-800 text-zinc-500">{chunk.category}</Badge>
                  <Badge variant="secondary" className="text-[8px] bg-zinc-800 text-zinc-500">{chunk.topic}</Badge>
                  {chunk.quality_score > 0 && <span className="text-[8px] text-zinc-600">q:{chunk.quality_score}</span>}
                  <span className="text-[8px] text-zinc-700">retrieved {chunk.times_retrieved || 0}x</span>
                  {chunk.ai_summarized && <span className="text-[8px] text-emerald-500">AI summarized</span>}
                  {chunk.flagged && <span className="text-[8px] text-red-400">FLAGGED</span>}
                </div>
                <p className="text-xs text-zinc-400 line-clamp-2">{chunk.content}</p>
                {chunk.source?.domain && <p className="text-[9px] text-zinc-600 mt-0.5">{chunk.source.domain}</p>}
              </div>
              <Button variant="ghost" size="sm" onClick={() => deleteChunk(chunk.chunk_id)}
                className="opacity-0 group-hover:opacity-100 h-7 w-7 p-0 text-zinc-600 hover:text-red-400"
                data-testid={`delete-chunk-${chunk.chunk_id}`}>
                <Trash2 className="w-3 h-3" />
              </Button>
            </div>
          ))}
          {knowledge.chunks?.length === 0 && (
            <p className="text-xs text-zinc-600 text-center py-4">No knowledge chunks yet. Start a training session to build the knowledge base.</p>
          )}
        </div>
      </div>
    </>
  );
}


function AutoRefreshToggle({ autoRefresh, onChange }) {
  const [interval, setInterval] = useState(autoRefresh.interval_days || 30);
  return (
    <div className="bg-zinc-900/40 border border-zinc-800/40 rounded-lg p-3" data-testid="auto-refresh-toggle">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium text-zinc-400 flex items-center gap-1.5">
            <RefreshCw className="w-3.5 h-3.5 text-cyan-400" /> Auto-Refresh Training
          </p>
          <p className="text-[10px] text-zinc-600 mt-0.5">Automatically re-crawl stale web sources to keep knowledge fresh</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={interval} onChange={e => setInterval(Number(e.target.value))}
            className="bg-zinc-950 border border-zinc-800 text-zinc-400 text-[10px] rounded-md h-6 px-1.5"
            data-testid="refresh-interval-select">
            <option value={7}>7 days</option>
            <option value={14}>14 days</option>
            <option value={30}>30 days</option>
            <option value={60}>60 days</option>
            <option value={90}>90 days</option>
          </select>
          <button onClick={() => onChange(!autoRefresh.enabled, interval)}
            className={`relative w-9 h-5 rounded-full transition-colors ${autoRefresh.enabled ? "bg-cyan-500" : "bg-zinc-700"}`}
            data-testid="auto-refresh-switch">
            <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${autoRefresh.enabled ? "left-[18px]" : "left-0.5"}`} />
          </button>
        </div>
      </div>
      {autoRefresh.last_trained && (
        <p className="text-[9px] text-zinc-600 mt-1.5">Last trained: {new Date(autoRefresh.last_trained).toLocaleDateString()}</p>
      )}
    </div>
  );
}
