import { useState, useEffect, useRef, Component } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Send, Hash, Loader2, Share2, Copy, Check, Upload, Paperclip, FolderKanban, AtSign, Mic, MicOff, Volume2, Code2, RotateCw, Power, AlertTriangle, UserPlus, Download, Users, Target, Activity, Search, Pin, PinOff, ThumbsUp, ThumbsDown, Crown, Shield, Globe, FileText, Gavel } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/App";
import MessageBubble from "@/components/MessageBubble";
import FileUpload, { FileAttachment } from "@/components/FileUpload";
import MentionDropdown from "@/components/MentionDropdown";
import { AiDisclaimer } from "@/components/LegalComponents";
import DirectiveSetup from "@/components/DirectiveSetup";
import DisagreementAuditLog from "@/components/DisagreementAuditLog";
import { SkeletonChatList } from "@/components/Skeletons";
import AgentActivityPanel from "@/components/AgentActivityPanel";
import NexusBrowserPanel from "@/components/NexusBrowserPanel";
import DocsPreviewPanel from "@/components/DocsPreviewPanel";
import ChatAIKeyHealthBanner from "@/components/ChatAIKeyHealthBanner";
import { ChatHeader } from "@/components/chat/ChatHeader";
import { ChatThreadPanel } from "@/components/chat/ChatThreadPanel";

// Error boundary to catch rendering crashes
class MessageErrorBoundary extends Component {
  constructor(props) { super(props); this.state = { hasError: false, error: null }; }
  static getDerivedStateFromError(error) { return { hasError: true, error }; }
  componentDidCatch(error, info) { console.error("Message render error:", error, info); }
  render() {
    if (this.state.hasError) {
      return (
        <div className="p-4 m-4 rounded-lg bg-red-500/10 border border-red-500/30 text-center">
          <AlertTriangle className="w-6 h-6 text-red-400 mx-auto mb-2" />
          <p className="text-sm text-red-400 font-medium">Message display error</p>
          <p className="text-xs text-red-400/60 mt-1">{this.state.error?.message || "Unknown error"}</p>
          <button onClick={() => { this.setState({ hasError: false, error: null }); window.location.reload(); }}
            className="mt-2 px-3 py-1 bg-red-500/20 text-red-400 text-xs rounded hover:bg-red-500/30">
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

const AI_COLORS = {
  claude: "#D97757",
  chatgpt: "#10A37F",
  gemini: "#4285F4",
  perplexity: "#20B2AA",
  mistral: "#FF7000",
  cohere: "#39594D",
  groq: "#F55036",
  deepseek: "#4D6BFE",
  grok: "#F5F5F5",
  mercury: "#00D4FF",
  pi: "#FF6B35",
  manus: "#6C5CE7",
  qwen: "#615EFF",
  kimi: "#000000",
  llama: "#0467DF",
  glm: "#3D5AFE",
  cursor: "#00E5A0",
  notebooklm: "#FBBC04",
  copilot: "#171515",
};

const AI_NAMES = {
  claude: "Claude",
  chatgpt: "ChatGPT",
  gemini: "Gemini",
  perplexity: "Perplexity",
  mistral: "Mistral",
  cohere: "Cohere",
  groq: "Groq",
  deepseek: "DeepSeek",
  grok: "Grok",
  mercury: "Mercury 2",
  pi: "Pi",
  manus: "Manus",
  qwen: "Qwen",
  kimi: "Kimi",
  llama: "Llama",
  glm: "GLM",
  cursor: "Cursor",
  notebooklm: "NotebookLM",
  copilot: "GitHub Copilot",
};

export const ChatPanel = ({ channel, messages, messagesLoading, agentStatus, isCollaborating, onSendMessage, user, workspaceId, onToggleCodeRepo, codeRepoOpen }) => {
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [pendingFile, setPendingFile] = useState(null); // File to attach to next message
  const [shareOpen, setShareOpen] = useState(false);
  const [shareLink, setShareLink] = useState("");
  const [isPublic, setIsPublic] = useState(true);
  const [sharePassword, setSharePassword] = useState("");
  const [copied, setCopied] = useState(false);
  const [userScrolledUp, setUserScrolledUp] = useState(false);
  const [linkedProjects, setLinkedProjects] = useState([]);
  const [mentionOpen, setMentionOpen] = useState(false);
  const [mentionQuery, setMentionQuery] = useState("");
  const [mentionableAgents, setMentionableAgents] = useState([]);
  const [mentionCursorPos, setMentionCursorPos] = useState(0);
  const [isRecording, setIsRecording] = useState(false);
  const [mediaRecorder, setMediaRecorder] = useState(null);
  const [autoCollab, setAutoCollab] = useState(false);
  const [autoCollabInfo, setAutoCollabInfo] = useState(null);
  const [disabledAgents, setDisabledAgents] = useState([]);
  const [manageAgentsOpen, setManageAgentsOpen] = useState(false);
  const [directiveOpen, setDirectiveOpen] = useState(false);
  const [activityPanelOpen, setActivityPanelOpen] = useState(false);
  const [msgSearchOpen, setMsgSearchOpen] = useState(false);
  const [activeThread, setActiveThread] = useState(null);
  const [threadReplies, setThreadReplies] = useState([]);
  const [auditLogOpen, setAuditLogOpen] = useState(false);
  const [msgSearchQuery, setMsgSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [agentsPaused, setAgentsPaused] = useState(false);
  const [persistMode, setPersistMode] = useState(false);
  const [persistInfo, setPersistInfo] = useState(null);
  const [agentPanelOpen, setAgentPanelOpen] = useState(false);
  const [availableModels, setAvailableModels] = useState({});
  const [channelAgentModels, setChannelAgentModels] = useState({});
  const [channelRoles, setChannelRoles] = useState({ tpm: null, architect: null, browser_operator: null, qa: [], security: null });
  const [browserOpen, setBrowserOpen] = useState(false);
  const [docsPreviewOpen, setDocsPreviewOpen] = useState(false);
  const [isDraggingFile, setIsDraggingFile] = useState(false);
  const [aiKeyHealth, setAiKeyHealth] = useState(null);
  
  // Panel pin state — persisted per channel in localStorage
  const getPinnedPanels = () => {
    try {
      return JSON.parse(localStorage.getItem(`nexus_pinned_${channel?.channel_id}`) || "{}");
    } catch (err) { handleSilent(err, "ChatPanel:op11"); return {}; }
  };
  const [pinnedPanels, setPinnedPanels] = useState(getPinnedPanels);
  
  const togglePin = (panel) => {
    const updated = { ...pinnedPanels, [panel]: !pinnedPanels[panel] };
    setPinnedPanels(updated);
    localStorage.setItem(`nexus_pinned_${channel?.channel_id}`, JSON.stringify(updated));
    // Also sync to server for cross-device
    api.put("/user/preferences", { pinned_panels: { [channel?.channel_id]: updated } }).catch(() => {});
    toast.success(updated[panel] ? `${panel.replace("_", " ")} pinned` : `${panel.replace("_", " ")} unpinned`);
  };
  const messagesEndRef = useRef(null);
  const scrollContainerRef = useRef(null);
  const inputRef = useRef(null);
  const fileDropRef = useRef(null);

  // Auto-open pinned panels when channel changes
  useEffect(() => {
    if (!channel?.channel_id) return;
    const pins = getPinnedPanels();
    setPinnedPanels(pins);
    if (pins.agents) setAgentPanelOpen(true);
    if (pins.activity) setActivityPanelOpen(true);
    if (pins.browser) setBrowserOpen(true);
    if (pins.docs) setDocsPreviewOpen(true);
    if (pins.code_repo && onToggleCodeRepo && !codeRepoOpen) onToggleCodeRepo();
  }, [channel?.channel_id]);

  // Fetch auto-collab status when channel changes
  useEffect(() => {
    if (channel?.channel_id) {
      // CRITICAL: Reset disabled agents immediately on channel switch to prevent cross-channel bleed
      setDisabledAgents(channel.disabled_agents || []);
      api.get(`/channels/${channel.channel_id}/auto-collab`)
        .then(r => {
          setAutoCollab(r.data?.enabled || false);
          setAutoCollabInfo(r.data);
        })
        .catch(() => {});
      // Fetch disabled agents from backend (authoritative source)
      api.get(`/channels/${channel.channel_id}/disabled-agents`)
        .then(r => setDisabledAgents(r.data?.disabled_agents || []))
        .catch(() => setDisabledAgents(channel.disabled_agents || []));
      // Fetch channel roles (TPM/Architect/Browser Operator)
      api.get(`/channels/${channel.channel_id}/roles`)
        .then(r => setChannelRoles({ tpm: r.data?.tpm || null, architect: r.data?.architect || null, browser_operator: r.data?.browser_operator || null, qa: r.data?.qa || [], security: r.data?.security || null }))
        .catch(() => setChannelRoles({ tpm: null, architect: null, browser_operator: null, qa: [], security: null }));
      api.get(`/workspaces/${workspaceId}/ai-key-health?channel_id=${channel.channel_id}`)
        .then(r => setAiKeyHealth(r.data || null))
        .catch(() => setAiKeyHealth(null));
      // Fetch persist mode
      api.get(`/channels/${channel.channel_id}/auto-collab-persist`)
        .then(r => { setPersistMode(r.data?.enabled || false); setPersistInfo(r.data); })
        .catch(() => {});
      // Fetch available models
      api.get("/ai-models").then(r => setAvailableModels(r.data?.models || {})).catch(() => {});
      // Fetch channel model overrides from the channel data
      api.get(`/channels/${channel.channel_id}`).then(r => {
        setChannelAgentModels(r.data?.agent_models || {});
      }).catch(() => {});
    }
  }, [channel?.channel_id, workspaceId]);

  const toggleAgent = async (agentKey) => {
    const isCurrentlyDisabled = disabledAgents.includes(agentKey);
    const newEnabled = isCurrentlyDisabled;
    try {
      await api.put(`/channels/${channel.channel_id}/agent-toggle`, {
        agent_key: agentKey,
        enabled: newEnabled,
      });
      if (newEnabled) {
        setDisabledAgents(prev => prev.filter(a => a !== agentKey));
        toast.success(`${AI_NAMES[agentKey] || agentKey} enabled`);
      } else {
        setDisabledAgents(prev => [...prev, agentKey]);
        toast.info(`${AI_NAMES[agentKey] || agentKey} disabled`);
      }
    } catch (err) { handleError(err, "ChatPanel:op1"); }
  };

  // Fetch mentionable agents when channel changes
  useEffect(() => {
    if (channel?.channel_id) {
      api.get(`/channels/${channel.channel_id}/mentionable`)
        .then(r => setMentionableAgents(r.data?.agents || []))
        .catch(() => setMentionableAgents([]));
    }
  }, [channel?.channel_id]);

  const togglePersistMode = async () => {
    if (!channel) return;
    const newState = !persistMode;
    try {
      await api.put(`/channels/${channel.channel_id}/auto-collab-persist`, { enabled: newState });
      setPersistMode(newState);
      if (newState) {
        toast.success("Persist mode ON — agents will collaborate until stopped");
      } else {
        toast.info("Persist mode stopped");
      }
    } catch (err) { handleError(err, "ChatPanel:op2"); }
  };

  // === CONSOLIDATED STATUS POLLING (persist + autoCollab + human-priority) ===
  useEffect(() => {
    if (!channel?.channel_id) return;
    if (!persistMode && !autoCollab && !isCollaborating) return;
    
    let active = true;
    const pollAll = async () => {
      if (!active) return;
      const promises = [];
      if (persistMode) {
        promises.push(
          api.get(`/channels/${channel.channel_id}/auto-collab-persist`)
            .then(res => { setPersistInfo(res.data); if (!res.data?.enabled) setPersistMode(false); })
            .catch(err => handleSilent(err, "ChatPanel:persistPoll"))
        );
      }
      if (autoCollab) {
        promises.push(
          api.get(`/channels/${channel.channel_id}/auto-collab`)
            .then(res => { setAutoCollabInfo(res.data); if (!res.data?.enabled) setAutoCollab(false); })
            .catch(err => handleSilent(err, "ChatPanel:autoCollabPoll"))
        );
      }
      if (isCollaborating) {
        promises.push(
          api.get(`/channels/${channel.channel_id}/human-priority`)
            .then(res => setAgentsPaused(res.data?.active || false))
            .catch(err => handleSilent(err, "ChatPanel:priorityPoll"))
        );
      }
      await Promise.allSettled(promises);
    };
    pollAll();
    const interval = setInterval(pollAll, 5000);
    return () => { active = false; clearInterval(interval); };
  }, [channel?.channel_id, persistMode, autoCollab, isCollaborating]);


  // Fetch linked projects when channel changes
  useEffect(() => {
    if (channel?.channel_id) {
      api.get(`/channels/${channel.channel_id}/projects`).then(r => setLinkedProjects(r.data || [])).catch(() => setLinkedProjects([]));
    }
  }, [channel?.channel_id]);

  // Handle scroll events to detect if user scrolled up
  const handleScroll = (e) => {
    const container = e.target;
    const { scrollTop, scrollHeight, clientHeight } = container;
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
    setUserScrolledUp(!isNearBottom);
  };

  // Auto-scroll to bottom on new messages (only if user hasn't scrolled up)
  useEffect(() => {
    if (!userScrolledUp && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, userScrolledUp]);

  // Scroll to bottom when collaboration starts (to see new messages)
  useEffect(() => {
    if (isCollaborating && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
      setUserScrolledUp(false);
    }
  }, [isCollaborating]);

  // Poll auto-collab status when active
  const handleShare = async () => {
    if (!channel) return;
    try {
      const res = await api.post(`/channels/${channel.channel_id}/share`, {
        is_public: isPublic,
        password: isPublic ? null : sharePassword || null,
        expires_in_days: 7,
      });
      const link = `${window.location.origin}/replay/${res.data.share_id}`;
      setShareLink(link);
      toast.success("Share link created!");
    } catch (err) { handleError(err, "ChatPanel:op3"); }
  };

  const copyLink = () => {
    navigator.clipboard.writeText(shareLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSend = async (e) => {
    if (e && e.preventDefault) e.preventDefault();
    if ((!input.trim() && !pendingFile) || sending) return;
    const msg = input;
    setSending(true);
    setMentionOpen(false);
    setInput("");
    try {
      // If there's a pending file, upload it with the message text
      if (pendingFile) {
        const formData = new FormData();
        formData.append("file", pendingFile);
        formData.append("message", msg);
        await api.post(`/channels/${channel.channel_id}/files`, formData, { headers: { "Content-Type": "multipart/form-data" } });
        setPendingFile(null);
      } else {
        await onSendMessage(msg);
      }
    } catch (err) {
      console.error("Send failed:", err);
    }
    setSending(false);
  };

  const toggleAutoCollab = async () => {
    if (!channel) return;
    const newState = !autoCollab;
    try {
      await api.put(`/channels/${channel.channel_id}/auto-collab`, { enabled: newState });
      setAutoCollab(newState);
      if (newState) {
        toast.success("Auto-collaboration enabled — agents will keep working");
      } else {
        toast.info("Auto-collaboration disabled");
      }
    } catch (err) { handleError(err, "ChatPanel:op4"); }
  };

  const updateChannelAgents = async (newAgents) => {
    if (!channel) return;
    try {
      await api.put(`/channels/${channel.channel_id}`, { ai_agents: newAgents });
      // Update channel in parent - trigger refetch via message
      toast.success("Channel agents updated");
      setManageAgentsOpen(false);
      // Force reload by navigating
      window.location.reload();
    } catch (err) { handleError(err, "ChatPanel:op5"); }
  };

  const updateAgentModel = async (agentKey, modelId) => {
    const newModels = { ...channelAgentModels, [agentKey]: modelId };
    setChannelAgentModels(newModels);
    try {
      await api.put(`/channels/${channel.channel_id}`, { agent_models: newModels });
      toast.success(`Model updated for ${AI_NAMES[agentKey] || agentKey}`);
    } catch (err) { handleError(err, "ChatPanel:op6"); }
  };


  const reactToMessage = async (messageId, reaction) => {
    try { await api.post(`/messages/${messageId}/react`, { reaction }); } catch (err) { handleSilent(err, "ChatPanel:op3"); }
  };

  const pinMessage = async (messageId) => {
    try {
      const res = await api.post(`/messages/${messageId}/pin`);
      toast.success(res.data.pinned ? "Message pinned" : "Message unpinned");
    } catch (err) { handleSilent(err, "ChatPanel:op4"); }
  };

  const searchMessages = async (q) => {
    setMsgSearchQuery(q);
    if (!q.trim()) { setSearchResults([]); return; }
    try {
      const res = await api.get(`/channels/${channel.channel_id}/search-messages?q=${encodeURIComponent(q)}`);
      setSearchResults(res.data?.messages || []);
    } catch (err) { handleSilent(err, "ChatPanel:op5"); }
  };


  // Check if agents are paused (human priority active)
  const resumeAgents = async () => {
    try {
      await api.post(`/channels/${channel.channel_id}/resume-agents`);
      setAgentsPaused(false);
      toast.success("Agents resumed");
    } catch (err) { handleSilent(err, "ChatPanel:op7"); }
  };



  const openThread = async (msg) => {
    setActiveThread(msg);
    try {
      const res = await api.get(`/messages/${msg.message_id}/thread`);
      setThreadReplies(res.data?.replies || []);
    } catch (err) { handleSilent(err, "ChatPanel:openThread"); }
  };

  const sendThreadReply = async (content) => {
    if (!activeThread || !content.trim()) return;
    try {
      await api.post(`/messages/${activeThread.message_id}/thread`, { content });
      const res = await api.get(`/messages/${activeThread.message_id}/thread`);
      setThreadReplies(res.data?.replies || []);
    } catch (err) { handleError(err, "ChatPanel:sendThreadReply"); }
  };

  const handleInputChange = (e) => {
    const val = e.target.value;
    setInput(val);

    // Detect @mention trigger
    const cursorPos = e.target.selectionStart;
    const textBeforeCursor = val.slice(0, cursorPos);
    const mentionMatch = textBeforeCursor.match(/@(\w*)$/);

    if (mentionMatch) {
      setMentionOpen(true);
      setMentionQuery(mentionMatch[1]);
      setMentionCursorPos(mentionMatch.index);
    } else {
      setMentionOpen(false);
      setMentionQuery("");
    }
  };

  const handleMentionSelect = (agent) => {
    if (!agent) {
      setMentionOpen(false);
      return;
    }
    const beforeMention = input.slice(0, mentionCursorPos);
    const afterMention = input.slice(mentionCursorPos).replace(/@\w*/, "");
    const mentionText = `@${agent.key === "everyone" ? "everyone" : agent.name.toLowerCase().replace(/\s/g, "")}`;
    const newInput = `${beforeMention}${mentionText} ${afterMention}`;
    setInput(newInput);
    setMentionOpen(false);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  // Voice recording
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      const chunks = [];
      recorder.ondataavailable = (e) => chunks.push(e.data);
      recorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        const blob = new Blob(chunks, { type: "audio/webm" });
        if (blob.size < 100) return;
        // Transcribe
        const formData = new FormData();
        formData.append("file", blob, "recording.webm");
        try {
          const res = await api.post(`/workspaces/${workspaceId}/transcribe`, formData, { headers: { "Content-Type": "multipart/form-data" } });
          if (res.data.text) {
            setInput(prev => prev ? prev + " " + res.data.text : res.data.text);
            toast.success("Transcribed!");
          } else {
            toast.info("No speech detected");
          }
        } catch (err) { handleError(err, "ChatPanel:op7"); }
      };
      recorder.start();
      setMediaRecorder(recorder);
      setIsRecording(true);
    } catch (err) {
      toast.error("Microphone access denied");
    }
  };

  const stopRecording = () => {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }
    setIsRecording(false);
    setMediaRecorder(null);
  };

  // TTS playback for AI messages
  const playMessage = async (messageContent) => {
    try {
      const res = await api.post(`/workspaces/${workspaceId}/generate-audio`, {
        text: messageContent.substring(0, 4096),
        voice: "nova", model: "tts-1", speed: 1.0,
      });
      if (res.data.media_id) {
        const dataRes = await api.get(`/media/${res.data.media_id}/data`);
        const audio = new Audio(`data:audio/mp3;base64,${dataRes.data.data}`);
        audio.play();
      }
    } catch (err) { handleError(err, "ChatPanel:op8"); }
  };

  // Set TPM or Architect role
  const setAgentRole = async (agentKey, role) => {
    try {
      const payload = {};
      if (role === "tpm") {
        payload.tpm = channelRoles.tpm === agentKey ? null : agentKey;
      } else if (role === "architect") {
        payload.architect = channelRoles.architect === agentKey ? null : agentKey;
      } else if (role === "browser_operator") {
        payload.browser_operator = channelRoles.browser_operator === agentKey ? null : agentKey;
      } else if (role === "qa") {
        const current = channelRoles.qa || [];
        payload.qa = current.includes(agentKey) ? current.filter(a => a !== agentKey) : [...current, agentKey];
      } else if (role === "security") {
        payload.security = channelRoles.security === agentKey ? null : agentKey;
      }
      const res = await api.put(`/channels/${channel.channel_id}/roles`, payload);
      setChannelRoles({ tpm: res.data.tpm, architect: res.data.architect, browser_operator: res.data.browser_operator, qa: res.data.qa || [], security: res.data.security });
      const name = AI_NAMES[agentKey] || agentKey;
      const roleNames = { tpm: "TPM", architect: "Architect", browser_operator: "Browser Operator", qa: "QA", security: "Security" };
      toast.success(`${name} — ${roleNames[role]} role ${role === "qa" ? (payload.qa.includes(agentKey) ? "added" : "removed") : (res.data[role] === agentKey ? "set" : "removed")}`);
    } catch (err) { handleError(err, "ChatPanel:op9"); }
  };

  if (!channel) {
    return (
      <div className="flex-1 flex items-center justify-center bg-zinc-950" data-testid="no-channel-selected">
        <div className="text-center max-w-sm">
          <div className="w-14 h-14 rounded-2xl bg-zinc-900 border border-zinc-800 flex items-center justify-center mx-auto mb-4">
            <Hash className="w-6 h-6 text-zinc-500" />
          </div>
          <h3 className="text-lg font-semibold text-zinc-300 mb-2" style={{ fontFamily: 'Syne, sans-serif' }}>
            Get started with your first channel
          </h3>
          <p className="text-sm text-zinc-500 mb-4 leading-relaxed">
            Create a channel, add AI agents, and watch them collaborate on your project in real-time.
          </p>
          <div className="space-y-2 text-left bg-zinc-900/60 rounded-lg p-4 border border-zinc-800/40">
            <div className="flex items-center gap-2 text-xs text-zinc-400"><span className="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-[10px] font-bold">1</span> Create a channel from the sidebar</div>
            <div className="flex items-center gap-2 text-xs text-zinc-400"><span className="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-[10px] font-bold">2</span> Select which AI models to include</div>
            <div className="flex items-center gap-2 text-xs text-zinc-400"><span className="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-[10px] font-bold">3</span> Send a message and watch them collaborate</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex" style={{ minHeight: 0 }}>
    <div 
      className="flex-1 bg-zinc-950 relative" 
      style={{ display: "grid", gridTemplateRows: "auto 1fr auto", height: "100%", minHeight: 0 }} 
      data-testid="chat-panel"
      ref={fileDropRef}
      onDragOver={(e) => { e.preventDefault(); setIsDraggingFile(true); }}
      onDragLeave={(e) => { if (fileDropRef.current && !fileDropRef.current.contains(e.relatedTarget)) setIsDraggingFile(false); }}
      onDrop={async (e) => {
        e.preventDefault();
        setIsDraggingFile(false);
        const files = Array.from(e.dataTransfer.files);
        if (files.length > 0 && channel?.channel_id) {
          const file = files[0];
          if (file.size > 25 * 1024 * 1024) { toast.error("File too large (25MB max)"); return; }
          try {
            const formData = new FormData();
            formData.append("file", file);
            toast.loading("Uploading document...", { id: "doc-upload" });
            const res = await api.post(`/channels/${channel.channel_id}/files`, formData, { headers: { "Content-Type": "multipart/form-data" } });
            toast.success(`Document shared: ${file.name}`, { id: "doc-upload" });
            if (res.data?.file?.has_extracted_text) toast.info("AI agents can now read this document");
          } catch (err) { toast.error(err.response?.data?.detail || "Upload failed", { id: "doc-upload" }); }
        }
      }}
    >
      {/* Drag & drop overlay */}
      {isDraggingFile && (
        <div className="absolute inset-0 z-50 bg-zinc-950/90 backdrop-blur-sm flex items-center justify-center border-2 border-dashed border-emerald-500/50 rounded-xl pointer-events-none" data-testid="drop-zone-overlay">
          <div className="text-center">
            <Upload className="w-10 h-10 text-emerald-400 mx-auto mb-3" />
            <p className="text-lg font-semibold text-emerald-400">Drop document here</p>
            <p className="text-sm text-zinc-400 mt-1">AI agents will be able to read its contents</p>
          </div>
        </div>
      )}
      {/* Channel header */}
      <ChatHeader
        channel={channel} agentStatus={agentStatus}
        agentPanelOpen={agentPanelOpen} setAgentPanelOpen={setAgentPanelOpen}
        pinnedPanels={pinnedPanels} togglePin={togglePin} setPinnedPanels={setPinnedPanels}
        setDirectiveOpen={setDirectiveOpen}
        activityPanelOpen={activityPanelOpen} setActivityPanelOpen={setActivityPanelOpen}
        browserOpen={browserOpen} setBrowserOpen={setBrowserOpen}
        docsPreviewOpen={docsPreviewOpen} setDocsPreviewOpen={setDocsPreviewOpen}
        auditLogOpen={auditLogOpen} setAuditLogOpen={setAuditLogOpen}
        msgSearchOpen={msgSearchOpen} setMsgSearchOpen={setMsgSearchOpen}
        onToggleCodeRepo={onToggleCodeRepo} codeRepoOpen={codeRepoOpen}
        shareOpen={shareOpen} setShareOpen={setShareOpen}
        isPublic={isPublic} setIsPublic={setIsPublic}
        sharePassword={sharePassword} setSharePassword={setSharePassword}
        shareLink={shareLink} setShareLink={setShareLink}
        copied={copied} setCopied={setCopied}
        handleShare={handleShare} copyLink={copyLink}
        autoCollab={autoCollab} toggleAutoCollab={toggleAutoCollab} autoCollabInfo={autoCollabInfo}
      />

      <ChatAIKeyHealthBanner health={aiKeyHealth} user={user} />

      {/* Search bar */}
      {msgSearchOpen && (
        <div className="px-4 py-2 border-b border-zinc-800/40 flex items-center gap-2 bg-zinc-900/60">
          <Search className="w-3.5 h-3.5 text-zinc-500" />
          <input value={msgSearchQuery} onChange={(e) => searchMessages(e.target.value)}
            placeholder="Search messages..." autoFocus
            className="flex-1 bg-transparent text-xs text-zinc-200 placeholder:text-zinc-600 focus:outline-none" data-testid="msg-search-input" />
          <span className="text-[10px] text-zinc-600">{searchResults.length} results</span>
          <button onClick={() => { setMsgSearchOpen(false); setMsgSearchQuery(""); setSearchResults([]); }} className="text-zinc-500 hover:text-zinc-300 text-xs">✕</button>
        </div>
      )}

      {/* Messages + Agent Panel row */}
      <div style={{ display: "flex", minHeight: 0 }}>
        {/* Messages area */}
        <div 
          ref={scrollContainerRef}
          onScroll={handleScroll}
          style={{ overflow: "auto", minHeight: 0, flex: "1 1 0%" }}
          data-testid="messages-scroll-area"
        >
        <MessageErrorBoundary>
        <AiDisclaimer />
        <div className="px-6 py-4 space-y-1">
          {messagesLoading && messages.length === 0 ? (
            <SkeletonChatList count={6} />
          ) : messages.length === 0 ? (
            <div className="flex items-center justify-center h-[60vh]" data-testid="empty-messages">
              <div className="text-center">
                <div className="flex justify-center gap-2 mb-6">
                  {(channel.ai_agents || []).map((agentKey) => (
                    <div
                      key={agentKey}
                      className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold"
                      style={{
                        backgroundColor: AI_COLORS[agentKey],
                        color: agentKey === "grok" ? "#09090b" : "#fff",
                      }}
                    >
                      {AI_NAMES[agentKey]?.[0]}
                    </div>
                  ))}
                </div>
                <h3 className="text-lg font-semibold text-zinc-300 mb-2" style={{ fontFamily: 'Syne, sans-serif' }}>
                  Start the conversation
                </h3>
                <p className="text-sm text-zinc-500 max-w-sm">
                  Send a message to begin. All AI agents in this channel will collaborate on your request.
                </p>
              </div>
            </div>
          ) : (
            (() => {
              // Collapse duplicate system messages (NX-CHAT-003)
              const apiKeyMsgs = messages.filter(m => m.sender_type === "system" && m.content?.includes("requires an API key"));
              const collapsed = [];
              let apiKeyCollapsed = false;
              
              for (const msg of messages) {
                if (!msg || !msg.message_id) continue;
                if (msg.sender_type === "system" && msg.content?.includes("requires an API key")) {
                  if (!apiKeyCollapsed) {
                    apiKeyCollapsed = true;
                    collapsed.push({
                      ...msg,
                      content: `_${apiKeyMsgs.length} agent${apiKeyMsgs.length > 1 ? "s" : ""} need API keys. Configure them in Settings → AI Keys._`,
                    });
                  }
                  continue;
                }
                collapsed.push(msg);
              }
              return collapsed;
            })().map((msg) => {
              if (!msg || !msg.message_id) return null;
              try {
                return (
                  <div key={msg.message_id} className="group/msg relative">
                    <MessageBubble
                      message={msg}
                      isOwn={msg.sender_type === "human" && msg.sender_id === user?.user_id}
                      workspaceId={workspaceId}
                      onPlayAudio={playMessage}
                      onStartThread={openThread}
                    />
                    {/* Reaction + Pin buttons (on hover) */}
                    {msg.sender_type === "ai" && (
                      <div className="absolute top-0 right-2 opacity-0 group-hover/msg:opacity-100 transition-opacity flex items-center gap-0.5 bg-zinc-900 border border-zinc-800 rounded-md px-1 py-0.5 shadow-lg">
                        <button onClick={() => reactToMessage(msg.message_id, "thumbs_up")} className="p-0.5 text-zinc-600 hover:text-emerald-400" title="Good response"><ThumbsUp className="w-3 h-3" /></button>
                        <button onClick={() => reactToMessage(msg.message_id, "thumbs_down")} className="p-0.5 text-zinc-600 hover:text-red-400" title="Poor response"><ThumbsDown className="w-3 h-3" /></button>
                        <button onClick={() => pinMessage(msg.message_id)} className="p-0.5 text-zinc-600 hover:text-amber-400" title="Pin message"><Pin className="w-3 h-3" /></button>
                      </div>
                    )}
                    {msg.pinned && <Pin className="absolute top-1 right-1 w-3 h-3 text-amber-400" />}
                  </div>
                );
              } catch (err) {
                return <div key={msg.message_id || Math.random()} className="text-xs text-red-400 py-1">Failed to render message</div>;
              }
            })
          )}
          <div ref={messagesEndRef} />
        </div>
        </MessageErrorBoundary>
      </div>

      {/* Agent Side Panel */}
      {agentPanelOpen && (
        <div className="w-64 flex-shrink-0 border-l border-zinc-800/60 overflow-y-auto bg-zinc-900/30" data-testid="agent-side-panel">
          <div className="p-3 border-b border-zinc-800/40 flex items-center justify-between">
            <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">Channel Agents</span>
            <button onClick={() => setManageAgentsOpen(true)} className="p-1 text-zinc-500 hover:text-emerald-400" title="Add agents" data-testid="panel-add-agent-btn">
              <UserPlus className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="p-2 space-y-1">
            {(channel.ai_agents || []).map((agentKey) => {
              const status = agentStatus[agentKey] || "idle";
              const color = AI_COLORS[agentKey] || "#666";
              const name = AI_NAMES[agentKey] || agentKey;
              const isDisabled = disabledAgents.includes(agentKey);
              const isTPM = channelRoles.tpm === agentKey;
              const isArchitect = channelRoles.architect === agentKey;
              const isBrowserOp = channelRoles.browser_operator === agentKey;
              const isQA = (channelRoles.qa || []).includes(agentKey);
              const isSecurity = channelRoles.security === agentKey;
              return (
                <div key={agentKey} className={`flex items-center gap-2 px-2.5 py-2 rounded-lg transition-colors ${isDisabled ? "opacity-50" : "hover:bg-zinc-800/40"}`} data-testid={`panel-agent-${agentKey}`}>
                  <div className="relative">
                    <div className="w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold flex-shrink-0"
                      style={{ backgroundColor: isDisabled ? "#27272a" : color, color: agentKey === "grok" ? "#09090b" : "#fff" }}>
                      {name[0]}
                    </div>
                    {isTPM && <Crown className="w-3 h-3 text-amber-400 absolute -top-1 -right-1" />}
                    {isArchitect && <Shield className="w-3 h-3 text-blue-400 absolute -top-1 -right-1" />}
                    {isBrowserOp && <Globe className="w-3 h-3 text-orange-400 absolute -top-1 -right-1" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1 flex-wrap">
                      <p className={`text-xs font-medium truncate ${isDisabled ? "text-zinc-600 line-through" : "text-zinc-300"}`}>{name}</p>
                      {isTPM && <span className="text-[8px] px-1 py-0.5 rounded bg-amber-500/20 text-amber-400 font-semibold flex-shrink-0">TPM</span>}
                      {isArchitect && <span className="text-[8px] px-1 py-0.5 rounded bg-blue-500/20 text-blue-400 font-semibold flex-shrink-0">ARCH</span>}
                      {isBrowserOp && <span className="text-[8px] px-1 py-0.5 rounded bg-orange-500/20 text-orange-400 font-semibold flex-shrink-0">BROWSER</span>}
                      {isQA && <span className="text-[8px] px-1 py-0.5 rounded bg-cyan-500/20 text-cyan-400 font-semibold flex-shrink-0">QA</span>}
                      {isSecurity && <span className="text-[8px] px-1 py-0.5 rounded bg-red-500/20 text-red-400 font-semibold flex-shrink-0">SEC</span>}
                    </div>
                    <p className="text-[9px] text-zinc-600">
                      {isDisabled ? "Disabled" : status === "thinking" ? "Thinking..." : "Active"}
                    </p>
                    {/* Role assignment */}
                    {!isDisabled && (
                      <div className="flex gap-1 mt-0.5 flex-wrap">
                        <button
                          onClick={() => setAgentRole(agentKey, "tpm")}
                          className={`text-[8px] px-1 py-0.5 rounded transition-colors ${isTPM ? "bg-amber-500/20 text-amber-400" : "text-zinc-600 hover:text-amber-400 hover:bg-amber-500/10"}`}
                          title={isTPM ? "Remove TPM role" : "Set as TPM"}
                          data-testid={`set-tpm-${agentKey}`}
                        >
                          <Crown className="w-2.5 h-2.5 inline" /> TPM
                        </button>
                        <button
                          onClick={() => setAgentRole(agentKey, "architect")}
                          className={`text-[8px] px-1 py-0.5 rounded transition-colors ${isArchitect ? "bg-blue-500/20 text-blue-400" : "text-zinc-600 hover:text-blue-400 hover:bg-blue-500/10"}`}
                          title={isArchitect ? "Remove Architect role" : "Set as Architect"}
                          data-testid={`set-architect-${agentKey}`}
                        >
                          <Shield className="w-2.5 h-2.5 inline" /> Arch
                        </button>
                        <button
                          onClick={() => setAgentRole(agentKey, "browser_operator")}
                          className={`text-[8px] px-1 py-0.5 rounded transition-colors ${isBrowserOp ? "bg-orange-500/20 text-orange-400" : "text-zinc-600 hover:text-orange-400 hover:bg-orange-500/10"}`}
                          title={isBrowserOp ? "Remove Browser Operator role" : "Set as Browser Operator"}
                          data-testid={`set-browser-${agentKey}`}
                        >
                          <Globe className="w-2.5 h-2.5 inline" /> Browser
                        </button>
                        <button
                          onClick={() => setAgentRole(agentKey, "qa")}
                          className={`text-[8px] px-1 py-0.5 rounded transition-colors ${isQA ? "bg-cyan-500/20 text-cyan-400" : "text-zinc-600 hover:text-cyan-400 hover:bg-cyan-500/10"}`}
                          title={isQA ? "Remove QA role" : "Add as QA"}
                          data-testid={`set-qa-${agentKey}`}
                        >
                          QA
                        </button>
                        <button
                          onClick={() => setAgentRole(agentKey, "security")}
                          className={`text-[8px] px-1 py-0.5 rounded transition-colors ${isSecurity ? "bg-red-500/20 text-red-400" : "text-zinc-600 hover:text-red-400 hover:bg-red-500/10"}`}
                          title={isSecurity ? "Remove Security role" : "Set as Security"}
                          data-testid={`set-security-${agentKey}`}
                        >
                          Sec
                        </button>
                      </div>
                    )}
                    {/* Model selector */}
                    {!isDisabled && availableModels[agentKey] && (
                      <select
                        value={channelAgentModels[agentKey] || availableModels[agentKey]?.find(m => m.default)?.id || ""}
                        onChange={(e) => updateAgentModel(agentKey, e.target.value)}
                        className="mt-0.5 w-full bg-transparent text-[9px] text-zinc-500 border-0 p-0 cursor-pointer hover:text-zinc-300"
                        data-testid={`model-select-${agentKey}`}
                      >
                        {availableModels[agentKey].map(m => (
                          <option key={m.id} value={m.id} className="bg-zinc-900">{m.name}</option>
                        ))}
                      </select>
                    )}
                  </div>
                  <button
                    onClick={() => toggleAgent(agentKey)}
                    className={`p-1 rounded transition-colors ${isDisabled ? "text-zinc-600 hover:text-emerald-400" : "text-zinc-600 hover:text-red-400"}`}
                    title={isDisabled ? `Enable ${name}` : `Disable ${name}`}
                    data-testid={`panel-toggle-${agentKey}`}
                  >
                    <Power className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })}
            {(channel.ai_agents || []).length === 0 && (
              <div className="text-center py-6">
                <Users className="w-6 h-6 text-zinc-800 mx-auto mb-2" />
                <p className="text-[10px] text-zinc-600">No agents in this channel</p>
                <button onClick={() => setManageAgentsOpen(true)} className="text-[10px] text-emerald-400 mt-1">Add agents</button>
              </div>
            )}
          </div>
          {/* Channel info */}
          <div className="p-3 border-t border-zinc-800/40 mt-2">
            <p className="text-[9px] text-zinc-600 uppercase tracking-wider mb-1">Summary</p>
            <p className="text-[10px] text-zinc-500">{(channel.ai_agents || []).length} total, {(channel.ai_agents || []).filter(a => !disabledAgents.includes(a)).length} active, {disabledAgents.filter(a => (channel.ai_agents || []).includes(a)).length} disabled</p>
          </div>
        </div>
      )}
      {/* Agent Activity Panel */}
      <AgentActivityPanel
        workspaceId={workspaceId}
        channelId={channel?.channel_id}
        isOpen={activityPanelOpen}
        onClose={() => setActivityPanelOpen(false)}
        onNewActivity={(act) => {
          if (!activityPanelOpen) setActivityPanelOpen(true);
        }}
      />
      {/* Nexus Browser Panel */}
      <NexusBrowserPanel
        channelId={channel?.channel_id}
        isOpen={browserOpen}
        onClose={() => setBrowserOpen(false)}
      />
      {/* Docs Preview Panel */}
      <DocsPreviewPanel
        workspaceId={workspaceId}
        channelId={channel?.channel_id}
        isOpen={docsPreviewOpen}
        onClose={() => setDocsPreviewOpen(false)}
      />
      </div>

      {/* Scroll to bottom button (shows when scrolled up) */}
      {userScrolledUp && messages.length > 0 && (
        <button
          onClick={() => {
            messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
            setUserScrolledUp(false);
          }}
          className="absolute bottom-24 right-8 z-40 p-2 rounded-full bg-zinc-800 border border-zinc-700 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-700 shadow-lg transition-all"
          data-testid="scroll-to-bottom-btn"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 5v14M19 12l-7 7-7-7"/>
          </svg>
        </button>
      )}

      {/* Human Priority Banner */}
      {agentsPaused && (
        <div className="px-4 py-2 bg-amber-500/10 border-t border-amber-500/20 flex items-center gap-3" data-testid="agents-paused-banner">
          <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
          <span className="text-xs text-amber-400 flex-1">Agents paused — your message has priority</span>
          <button onClick={resumeAgents} className="px-2 py-1 rounded bg-emerald-500/20 text-emerald-400 text-[10px] font-medium hover:bg-emerald-500/30" data-testid="resume-agents-btn">
            Resume Agents
          </button>
        </div>
      )}

      {/* Input area */}
      <div className="px-6 py-3 border-t border-zinc-800/60">
        <div className="flex items-end gap-3" data-testid="message-form">
          <FileUpload 
            channelId={channel?.channel_id} 
            compact={true}
            onUploadComplete={async (fileData) => {
              toast.success("Document shared!");
              if (fileData?.file?.has_extracted_text) {
                toast.info("AI agents can now read this document");
              }
            }}
          />
          {/* Voice input */}
          <button
            onClick={isRecording ? stopRecording : startRecording}
            className={`p-2.5 rounded-xl transition-colors flex-shrink-0 ${isRecording ? "bg-red-500/20 text-red-400 animate-pulse" : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"}`}
            title={isRecording ? "Stop recording" : "Voice input (Whisper)"}
            data-testid="voice-input-btn"
          >
            {isRecording ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
          </button>
          <div className="flex-1 relative">
            {/* Pending file attachment indicator */}
            {pendingFile && (
              <div className="flex items-center gap-2 px-3 py-1.5 mb-1 rounded-lg bg-emerald-500/10 border border-emerald-500/20" data-testid="pending-file-indicator">
                <Paperclip className="w-3 h-3 text-emerald-400" />
                <span className="text-[11px] text-emerald-400 truncate flex-1">{pendingFile.name}</span>
                <span className="text-[9px] text-zinc-500">{(pendingFile.size / 1024).toFixed(0)}KB</span>
                <button onClick={() => setPendingFile(null)} className="text-zinc-500 hover:text-red-400 p-0.5"><span className="text-xs">✕</span></button>
              </div>
            )}
            {mentionOpen && (
              <MentionDropdown
                agents={mentionableAgents}
                query={mentionQuery}
                onSelect={handleMentionSelect}
                position={{ bottom: "100%", left: 0 }}
              />
            )}
            <textarea
              ref={inputRef}
              value={input}
              onChange={handleInputChange}
              onKeyDown={(e) => {
                // Let mention dropdown handle arrow/enter/tab/escape
                if (mentionOpen && ["ArrowDown", "ArrowUp", "Enter", "Tab", "Escape"].includes(e.key)) {
                  return;
                }
                // Ctrl+Enter or Cmd+Enter = send
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                  e.preventDefault();
                  handleSend(e);
                  return;
                }
                // Plain Enter = newline (default textarea behavior, do nothing)
              }}
              placeholder={isCollaborating ? "AI agents are thinking..." : "Type @ to mention an agent... (Ctrl+Enter to send)"}
              className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-700 focus:border-zinc-700 font-[Manrope] resize-none"
              style={{ height: 80 }}
              rows={3}
              disabled={sending}
              data-testid="message-input"
              autoComplete="off"
            />
          </div>
          <div className="flex flex-col items-center gap-1.5 mb-0.5">
            {/* Persist mode toggle */}
            <button
              onClick={togglePersistMode}
              className={`p-2 rounded-xl transition-all flex-shrink-0 ${
                persistMode
                  ? "bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/40"
                  : "text-zinc-600 hover:text-zinc-400 hover:bg-zinc-800"
              }`}
              title={persistMode ? `Persist ON — Round ${persistInfo?.round || 0}, ${persistInfo?.status || "running"}` : "Enable persistent collaboration (runs until stopped)"}
              data-testid="persist-toggle"
            >
              <Power className={`w-4 h-4 ${persistMode ? "text-emerald-400" : ""}`} />
            </button>
            {/* Auto-collab toggle */}
            <button
              onClick={toggleAutoCollab}
              className={`p-2 rounded-xl transition-all flex-shrink-0 ${
                autoCollab
                  ? "bg-amber-500/20 text-amber-400 ring-1 ring-amber-500/40"
                  : "text-zinc-600 hover:text-zinc-400 hover:bg-zinc-800"
              }`}
              title={autoCollab ? "Auto-collab ON" : "Enable auto-collaboration (limited rounds)"}
              data-testid="auto-collab-toggle"
            >
              <RotateCw className={`w-4 h-4 ${autoCollab ? "animate-spin" : ""}`} style={autoCollab ? { animationDuration: "3s" } : {}} />
            </button>
            {/* Attach file button */}
            <button
              type="button"
              onClick={() => {
                const inp = document.createElement("input");
                inp.type = "file";
                inp.onchange = (ev) => {
                  const f = ev.target.files[0];
                  if (f) { if (f.size > 25*1024*1024) { toast.error("File too large (25MB max)"); return; } setPendingFile(f); }
                };
                inp.click();
              }}
              className={`p-2 rounded-lg transition-colors ${pendingFile ? "text-emerald-400 bg-emerald-500/10" : "text-zinc-600 hover:text-zinc-400 hover:bg-zinc-800"}`}
              title="Attach file to message"
              data-testid="attach-file-btn"
            >
              <Paperclip className="w-4 h-4" />
            </button>
            {/* Send button */}
            <Button
              type="button"
              onClick={handleSend}
              disabled={(!input.trim() && !pendingFile) || sending}
              className="bg-emerald-500 hover:bg-emerald-400 text-white rounded-xl px-4 py-3 h-auto relative z-50"
              data-testid="send-message-btn"
            >
              {sending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </Button>
          </div>
        </div>
        <div className="flex items-center justify-between mt-1 px-1">
          {persistMode && (
            <span className="text-[10px] text-emerald-400 flex items-center gap-1">
              <Power className="w-2.5 h-2.5" />
              Persist: Round {persistInfo?.round || 0} — {persistInfo?.status || "running"} ({Math.round(persistInfo?.delay || 0)}s delay)
            </span>
          )}
          {autoCollab && !persistMode && (
            <span className="text-[10px] text-amber-400 flex items-center gap-1">
              <RotateCw className="w-2.5 h-2.5" />
              Auto-collab active {autoCollabInfo?.round > 0 ? `(round ${autoCollabInfo.round})` : ""}
            </span>
          )}
          <p className="text-[10px] text-zinc-600 ml-auto">Ctrl+Enter to send</p>
        </div>
        {isCollaborating && (
          <div className="flex items-center gap-2 mt-2 px-1" data-testid="collaboration-indicator">
            <div className="typing-indicator text-amber-500">
              <span /><span /><span />
            </div>
            <span className="text-xs text-zinc-400">
              {(() => {
                const thinkingAgents = Object.entries(agentStatus).filter(([k, v]) => v === "thinking").map(([k]) => AI_NAMES[k] || k);
                if (thinkingAgents.length > 0) return `${thinkingAgents.join(", ")} ${thinkingAgents.length === 1 ? "is" : "are"} responding...`;
                if (persistMode) return `Agents working persistently (round ${persistInfo?.round || "..."})`;
                if (autoCollab) return `Auto-collaborating (round ${autoCollabInfo?.round || "..."})`;
                return "Agents are thinking...";
              })()}
            </span>
          </div>
        )}
      </div>

      {/* Manage Agents Dialog */}
      <Dialog open={manageAgentsOpen} onOpenChange={setManageAgentsOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-md" style={{ zIndex: 200 }}>
          <DialogHeader>
            <DialogTitle className="text-zinc-100 flex items-center gap-2">
              <UserPlus className="w-4 h-4 text-emerald-400" />
              Manage AI Agents
            </DialogTitle>
          </DialogHeader>
          <div className="mt-2">
            <p className="text-xs text-zinc-500 mb-3">Select which AI agents participate in this channel.</p>
            <div className="space-y-1.5 max-h-[400px] overflow-y-auto">
              {Object.entries(AI_NAMES).map(([key, name]) => {
                const isActive = (channel?.ai_agents || []).includes(key);
                const color = AI_COLORS[key] || "#666";
                return (
                  <button
                    key={key}
                    onClick={() => {
                      const current = channel?.ai_agents || [];
                      const newAgents = isActive
                        ? current.filter(a => a !== key)
                        : [...current, key];
                      updateChannelAgents(newAgents);
                    }}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg border transition-all ${
                      isActive
                        ? "bg-zinc-800/60 border-zinc-700 text-zinc-200"
                        : "bg-zinc-900/40 border-zinc-800/40 text-zinc-500 hover:border-zinc-700 hover:text-zinc-300"
                    }`}
                    data-testid={`manage-agent-${key}`}
                  >
                    <div className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold"
                      style={{ backgroundColor: isActive ? color : "#27272a", color: key === "grok" ? "#09090b" : "#fff" }}>
                      {name[0]}
                    </div>
                    <span className="text-sm flex-1 text-left">{name}</span>
                    {isActive ? (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400">Active</span>
                    ) : (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-600">Add</span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Directive Setup */}
      <DirectiveSetup channel={channel} open={directiveOpen} onOpenChange={setDirectiveOpen} />

      {/* Disagreement Audit Log Side Panel */}
      {pinnedPanels.audit && (
        <Dialog open={pinnedPanels.audit} onOpenChange={(open) => setPinnedPanels(p => ({ ...p, audit: open }))}>
          <DialogContent className="bg-zinc-900 border-zinc-800 max-w-2xl max-h-[80vh] p-0 overflow-hidden">
            <DisagreementAuditLog workspaceId={channel?.workspace_id} onClose={() => setPinnedPanels(p => ({ ...p, audit: false }))} />
          </DialogContent>
        </Dialog>
      )}
    </div>

    {/* Thread Side Panel */}
    <ChatThreadPanel
      activeThread={activeThread}
      threadReplies={threadReplies}
      onClose={() => { setActiveThread(null); setThreadReplies([]); }}
      onSendReply={sendThreadReply}
    />
    </div>
  );
};

export default ChatPanel;
