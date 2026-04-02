import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api } from "@/App";
import { useHelper } from "@/contexts/NexusHelperContext";
import { Button } from "@/components/ui/button";
import { LayoutDashboard, LogOut, KanbanSquare, Bot, Hammer, BarChart3, Pin } from "lucide-react";
import { useLanguage } from "@/contexts/LanguageContext";
import { useSidebarCollapse } from "@/hooks/useSidebarCollapse";
import { SkeletonSidebarChannels, SkeletonChatList } from "@/components/Skeletons";
import Sidebar from "@/components/Sidebar";
import ChatPanel from "@/components/ChatPanel";
import TaskBoard from "@/components/TaskBoard";
import Reports from "@/components/Reports";
import Analytics from "@/components/Analytics";
import AgentArenaPanel from "@/components/AgentArenaPanel";
import CostDashboard from "@/components/CostDashboard";
import ROICalculator from "@/components/ROICalculator";
import NexusAgents from "@/components/NexusAgents";
import TaskPanel from "@/components/TaskPanel";
import MembersPanel from "@/components/MembersPanel";
import NotificationBell from "@/components/NotificationBell";
import WorkspaceSkillsTab from "@/components/WorkspaceSkillsTab";
import ProjectPanel from "@/components/ProjectPanel";
import WorkflowPanel from "@/components/WorkflowPanel";
import MarketplacePanel from "@/components/MarketplacePanel";
import ArtifactPanel from "@/components/ArtifactPanel";
import SchedulePanel from "@/components/SchedulePanel";
import KnowledgeBasePanel from "@/components/KnowledgeBasePanel";
import ImageGenPanel from "@/components/ImageGenPanel";
import VideoPanel from "@/components/VideoPanel";
import AudioPanel from "@/components/AudioPanel";
import MediaLibraryPanel from "@/components/MediaLibraryPanel";
import PlannerCalendar from "@/components/PlannerCalendar";
import GanttChart from "@/components/GanttChart";
import DrivePanel from "@/components/DrivePanel";
import CloudFileBrowser from "@/components/CloudFileBrowser";
import CodeRepoPanel from "@/components/CodeRepoPanel";
import WikiPanel from "@/components/WikiPanel";
import DocsPanel from "@/components/DocsPanel";
import IdeationPanel from "@/components/IdeationPanel";
import DeploymentPanel from "@/components/DeploymentPanel";
import ProjectsDashboard from "@/components/ProjectsDashboard";
import RepoAnalytics from "@/components/RepoAnalytics";
import DirectiveDashboard from "@/components/DirectiveDashboard";
import GuideMe from "@/components/GuideMe";
import CommandPalette from "@/components/CommandPalette";
import AgentStudio from "@/components/AgentStudio";
import SkillsMatrix from "@/components/SkillsMatrix";
import AgentCatalog from "@/components/AgentCatalog";
import RevenueSharing from "@/components/RevenueSharing";
import AgentTraining from "@/components/AgentTraining";
import PerformanceTimeSeries from "@/components/PerformanceTimeSeries";
import CostAlerts from "@/components/CostAlerts";
import AgentPlayground from "@/components/AgentPlayground";
import LeaderboardPanel from "@/components/LeaderboardPanel";
import KnowledgeDedupPanel from "@/components/KnowledgeDedupPanel";
import AgentEvaluation from "@/components/AgentEvaluation";
import TrainingQualityDashboard from "@/components/TrainingQualityDashboard";
import OrchestrationPanel from "@/components/OrchestrationPanel";
import FineTuningPanel from "@/components/FineTuningPanel";
import ReviewsPanel from "@/components/ReviewsPanel";
import WebhooksPanel from "@/components/WebhooksPanel";
import BenchmarksPanel from "@/components/BenchmarksPanel";
import BenchmarkCompare from "@/components/BenchmarkCompare";
import NAVCPanel from "@/components/NAVCPanel";
import SmartInboxPanel from "@/components/SmartInboxPanel";
import AgentDojoPanel from "@/components/AgentDojoPanel";
import KnowledgeExplorer from "@/components/KnowledgeExplorer";
import AgentTeamPanel from "@/components/AgentTeamPanel";
import ResearchIntelligencePanel from "@/components/ResearchIntelligencePanel";
import OrchSchedulePanel from "@/components/OrchSchedulePanel";
import CollabTemplatesPanel from "@/components/CollabTemplatesPanel";
import ReviewAnalyticsPanel from "@/components/ReviewAnalyticsPanel";
import SecurityDashboard from "@/components/SecurityDashboard";
import MarketplaceAdvancedSearch from "@/components/MarketplaceAdvancedSearch";
import NXFeaturesPanel from "@/components/NXFeaturesPanel";
import A2APipelinePanel from "@/components/A2APipelinePanel";
import OperatorPanel from "@/components/OperatorPanel";
import StrategicFeaturesPanel from "@/components/StrategicFeaturesPanel";
import { ModuleProvider, useModules } from "@/contexts/ModuleContext";
import { ModuleGateBanner } from "@/components/ModuleGateBanner";
import { requestNotificationPermission, registerServiceWorker, showLocalNotification } from "@/lib/notifications";
import AuditLogViewer from "@/components/AuditLogViewer";
import DataExportPanel from "@/components/DataExportPanel";
import TPMDesignation from "@/components/TPMDesignation";
import MultiRepoPanel from "@/components/MultiRepoPanel";

const ALL_NAV_MENUS = [
  {
    id: "workspace",
    label: "Workspace",
    icon: "LayoutDashboard",
    items: [
      { key: "chat", label: "Chat" },
      { key: "dashboard", label: "Dashboard" },
      { key: "members", label: "Members" },
      { key: "tpm", label: "TPM" },
      { key: "schedules", label: "Schedules" },
      { key: "drive", label: "Drive" },
    ],
  },
  {
    id: "plan",
    label: "Plan",
    icon: "KanbanSquare",
    items: [
      { key: "projects", label: "Projects" },
      { key: "tasks", label: "Tasks" },
      { key: "gantt", label: "Gantt" },
      { key: "planner", label: "Planner" },
      { key: "ideation", label: "Ideation" },
      { key: "workflows", label: "Workflows" },
      { key: "directives", label: "Directives" },
    ],
  },
  {
    id: "agents",
    label: "AI Agents",
    icon: "Bot",
    items: [
      { key: "agents", label: "Agents" },
      { key: "studio", label: "Studio" },
      { key: "skill-matrix", label: "Skills Matrix" },
      { key: "catalog", label: "Catalog" },
      { key: "training", label: "Training" },
      { key: "skills", label: "Skills" },
      { key: "playground", label: "Playground" },
      { key: "evaluation", label: "Evaluation" },
      { key: "arena", label: "Arena" },
      { key: "orchestration", label: "Orchestration" },
      { key: "a2a-pipelines", label: "A2A Workflows" },
      { key: "operator", label: "Operator" },
      { key: "orch-schedules", label: "Scheduling" },
      { key: "collab-templates", label: "Templates" },
      { key: "fine-tuning", label: "Fine-Tuning" },
      { key: "benchmarks", label: "Benchmarks" },
      { key: "benchmark-compare", label: "Compare" },
      { key: "deployments", label: "Deploy" },
    ],
  },
  {
    id: "build",
    label: "Build",
    icon: "Hammer",
    items: [
      { key: "code", label: "Code Repos" },
      { key: "docs", label: "Docs" },
      { key: "knowledge", label: "Knowledge" },
      { key: "artifacts", label: "Artifacts" },
      { key: "images", label: "Images" },
      { key: "video", label: "Video" },
      { key: "audio", label: "Audio" },
      { key: "media", label: "Media Library" },
      { key: "webhooks", label: "Webhooks" },
    ],
  },
  {
    id: "insights",
    label: "Insights",
    icon: "BarChart3",
    items: [
      { key: "reports", label: "Reports" },
      { key: "analytics", label: "Analytics" },
      { key: "costs", label: "Costs" },
      { key: "roi", label: "ROI Calculator" },
      { key: "revenue", label: "Revenue" },
      { key: "performance", label: "Performance" },
      { key: "leaderboard", label: "Leaderboard" },
      { key: "dedup", label: "Quality" },
      { key: "audit-log", label: "Audit Log" },
      { key: "data-export", label: "Data Export" },
      { key: "training-quality", label: "Coverage" },
      { key: "repo-analytics", label: "Repo Analytics" },
      { key: "reviews", label: "Reviews" },
      { key: "review-analytics", label: "Review Analytics" },
      { key: "marketplace-search", label: "Marketplace" },
      { key: "security", label: "Security" },
      { key: "nx-platform", label: "Platform" },
      { key: "strategic", label: "Business" },
    ],
  },
  {
    id: "optimization",
    label: "Optimization",
    icon: "Bot",
    items: [
      { key: "optimization", label: "NAVC" },
      { key: "compression-profiles", label: "Profiles" },
      { key: "compression-runs", label: "Runs" },
      { key: "compression-compare", label: "Compare" },
    ],
  },
  {
    id: "smart-inbox",
    label: "Smart Inbox",
    icon: "Bot",
    items: [
      { key: "inbox", label: "Inbox" },
      { key: "mail-accounts", label: "Accounts" },
      { key: "mail-rules", label: "Rules" },
      { key: "mail-review", label: "Review Queue" },
      { key: "mail-audit", label: "Audit" },
    ],
  },
  {
    id: "agent-dojo",
    label: "Agent Dojo",
    icon: "Bot",
    items: [
      { key: "dojo", label: "Sessions" },
      { key: "dojo-scenarios", label: "Scenarios" },
      { key: "dojo-data", label: "Training Data" },
    ],
  },
  {
    id: "agent-teams",
    label: "Agent Teams",
    icon: "Bot",
    items: [
      { key: "agent-teams", label: "Sessions" },
      { key: "agent-team-templates", label: "Templates" },
    ],
  },
  {
    id: "research",
    label: "Research",
    icon: "Bot",
    items: [
      { key: "research-library", label: "Libraries" },
      { key: "lit-review", label: "Lit Review" },
      { key: "annotations", label: "Annotations" },
      { key: "connectors", label: "Connectors" },
    ],
  },
];

const ICON_MAP = { LayoutDashboard, KanbanSquare, Bot, Hammer, BarChart3 };

function WorkspacePageInner({ user }) {
  const { workspaceId } = useParams();
  const navigate = useNavigate();
  const { isNavKeyEnabled } = useModules();

  // Filter nav menus based on enabled modules
  const NAV_MENUS = useMemo(() => {
    return ALL_NAV_MENUS.map(menu => ({
      ...menu,
      items: menu.items.filter(item => isNavKeyEnabled(item.key)),
    })).filter(menu => menu.items.length > 0);
  }, [isNavKeyEnabled]);
  const { t } = useLanguage();
  const { collapsed, setCollapsed, toggle: toggleSidebar } = useSidebarCollapse();

  // Auto-collapse sidebar on narrow screens
  useEffect(() => {
    const check = () => { if (window.innerWidth < 1024) setCollapsed(true); };
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, [setCollapsed]);
  const [workspace, setWorkspace] = useState(null);
  const [channels, setChannels] = useState([]);
  const [selectedChannel, setSelectedChannel] = useState(null);
  const [messages, setMessages] = useState([]);
  const [agentStatus, setAgentStatus] = useState({});
  const [isCollaborating, setIsCollaborating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [activeTab, setActiveTabState] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get("tab") || "chat";
  });
  const [openMenu, setOpenMenu] = useState(null);
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const [pinnedTabs, setPinnedTabs] = useState(() => {
    try { return JSON.parse(localStorage.getItem("nexus_pinned_tabs") || "[]"); }
    catch { return []; }
  });
  const menuRef = useRef(null);

  const togglePin = useCallback((key) => {
    setPinnedTabs(prev => {
      const next = prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key];
      localStorage.setItem("nexus_pinned_tabs", JSON.stringify(next));
      return next;
    });
  }, []);

  const reorderPinned = useCallback((fromIdx, toIdx) => {
    setPinnedTabs(prev => {
      const next = [...prev];
      const [moved] = next.splice(fromIdx, 1);
      next.splice(toIdx, 0, moved);
      localStorage.setItem("nexus_pinned_tabs", JSON.stringify(next));
      return next;
    });
  }, []);

  // Find label for a tab key across all menus
  const getTabLabel = useCallback((key) => {
    for (const m of NAV_MENUS) {
      const item = m.items.find(i => i.key === key);
      if (item) return item.label;
    }
    return key;
  }, []);

  // Simple tab setter that updates state + URL without triggering router re-renders
  const setActiveTab = useCallback((tab) => {
    setActiveTabState(tab);
    const url = new URL(window.location.href);
    if (tab === "chat") url.searchParams.delete("tab");
    else url.searchParams.set("tab", tab);
    window.history.replaceState({}, "", url.toString());
  }, []);

  // Sync helper context with active workspace tab
  try {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const helper = useHelper();
    // eslint-disable-next-line react-hooks/rules-of-hooks
    useEffect(() => {
      if (helper?.setPageContext) helper.setPageContext(activeTab, workspaceId);
    }, [activeTab, workspaceId, helper]);
  } catch {
    // Helper context not available (e.g., during SSR or outside provider)
  }

  // Reset focused index when menu changes
  useEffect(() => { setFocusedIndex(-1); }, [openMenu]);

  // Close flyout on click outside + keyboard navigation
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        const navBtn = e.target.closest('[data-testid^="nav-menu-"]');
        if (!navBtn) setOpenMenu(null);
      }
    };
    const handleKeydown = (e) => {
      if (e.key === "Escape") { setOpenMenu(null); return; }
      if (!openMenu) return;
      const menu = NAV_MENUS.find(m => m.id === openMenu);
      if (!menu) return;
      const len = menu.items.length;
      if (e.key === "ArrowDown") { e.preventDefault(); setFocusedIndex(prev => (prev + 1) % len); }
      else if (e.key === "ArrowUp") { e.preventDefault(); setFocusedIndex(prev => (prev - 1 + len) % len); }
      else if (e.key === "Home") { e.preventDefault(); setFocusedIndex(0); }
      else if (e.key === "End") { e.preventDefault(); setFocusedIndex(len - 1); }
      else if (e.key === "Enter" && focusedIndex >= 0 && focusedIndex < len) {
        e.preventDefault();
        setActiveTab(menu.items[focusedIndex].key);
        setOpenMenu(null);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeydown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeydown);
    };
  }, [openMenu, focusedIndex, setActiveTab, NAV_MENUS]);
  const [tasks, setTasks] = useState([]);
  const [reports, setReports] = useState(null);
  const [members, setMembers] = useState([]);
  const [projectRefreshKey, setProjectRefreshKey] = useState(0);
  const [docsSubTab, setDocsSubTab] = useState("files");
  const [codeRepoOpen, setCodeRepoOpen] = useState(false);
  const [projects, setProjects] = useState([]);

  // Fetch workspace and channels
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [wsRes, chRes] = await Promise.all([
          api.get(`/workspaces/${workspaceId}`),
          api.get(`/workspaces/${workspaceId}/channels`),
        ]);
        setWorkspace(wsRes.data);
        setChannels(chRes.data);
        if (chRes.data.length > 0) {
          setSelectedChannel(chRes.data[0]);
        }
      } catch (err) {
        if (err?.response?.status === 401) {
          navigate("/auth", { replace: true });
        } else {
          toast.error("Failed to load workspace");
          navigate("/dashboard");
        }
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [workspaceId, navigate]);

  // Setup push notifications
  useEffect(() => {
    requestNotificationPermission();
    registerServiceWorker();
  }, []);


  // Fetch channels
  const fetchChannels = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/channels`);
      setChannels(res.data);
    } catch (err) { handleSilent(err, "WorkspacePage:op1"); }
  }, [workspaceId]);

  // Close dropdowns on outside click
  const buildRef = React.useRef(null);
  const moreRef = React.useRef(null);
  useEffect(() => {
    const handler = (e) => {
      if (buildRef.current && !buildRef.current.contains(e.target)) setBuildOpen(false);
      if (moreRef.current && !moreRef.current.contains(e.target)) setMoreOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Fetch messages for selected channel
  const fetchMessages = useCallback(async () => {
    if (!selectedChannel || activeTab !== "chat") return;
    setMessagesLoading(true);
    try {
      const res = await api.get(`/channels/${selectedChannel.channel_id}/messages`);
      if (Array.isArray(res.data)) {
        setMessages(res.data);
      }
    } catch (err) { handleSilent(err, "WorkspacePage:op2"); }
    setMessagesLoading(false);
  }, [selectedChannel, activeTab]);

  useEffect(() => {
    fetchMessages();
  }, [fetchMessages]);

  // Poll for new messages and status (pause when tab hidden)
  // Poll for new messages and status + WebSocket for real-time delivery
  useEffect(() => {
    if (!selectedChannel || activeTab !== "chat") return;
    let interval;
    let pollActive = true;
    let ws = null;
    let shouldCloseOnOpen = false;
    
    // WebSocket for instant message delivery
    try {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${protocol}//${window.location.host}`;
      if (wsUrl) {
        ws = new WebSocket(`${wsUrl}/api/ws/channels/${selectedChannel.channel_id}`);
        ws.onopen = () => {
          if (shouldCloseOnOpen) {
            ws.close();
            return;
          }
          // Only send token if cookie auth may not be available (bridge handoff)
          const sessionToken = sessionStorage.getItem("nexus_session_token");
          if (sessionToken) ws.send(sessionToken);
          // If no token, cookie auth handles it — no action needed
        };
        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === "new_message" && data.message) {
              setMessages(prev => {
                if (prev.some(m => m.message_id === data.message.message_id)) return prev;
                return [...prev, data.message];
              });
            }
          } catch (err) { handleSilent(err, "WorkspacePage:op3"); }
        };
        ws.onerror = () => {};
      }
    } catch (err) { handleSilent(err, "WorkspacePage:op4"); }

    const poll = async () => {
      if (!pollActive) return;
      try {
        const [msgRes, statusRes] = await Promise.all([
          api.get(`/channels/${selectedChannel.channel_id}/messages`),
          api.get(`/channels/${selectedChannel.channel_id}/status`),
        ]);
        if (Array.isArray(msgRes.data) && msgRes.data.length > messages.length) {
          const newMsgs = msgRes.data.slice(messages.length);
          const aiMsg = newMsgs.find(m => m.sender_type === "ai");
          if (aiMsg && document.hidden) {
            showLocalNotification(
              `${aiMsg.sender_name} responded`,
              aiMsg.content?.substring(0, 100) || "New AI response",
              { tag: `ai-${selectedChannel.channel_id}` }
            );
          }
        }
        setMessages(msgRes.data);
        setAgentStatus(statusRes.data.agents || {});
        setIsCollaborating(statusRes.data.is_running || false);
      } catch (err) {
        if (err?.response?.status === 401) {
          pollActive = false;
          clearInterval(interval);
        }
      }
    };
    // Poll less frequently when WebSocket is active (5s vs 2s)
    const pollInterval = ws ? 5000 : 2000;
    const startPolling = () => { interval = setInterval(poll, pollInterval); };
    const handleVisibility = () => {
      clearInterval(interval);
      if (!document.hidden && pollActive) { poll(); startPolling(); }
    };
    startPolling();
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      pollActive = false;
      clearInterval(interval);
      document.removeEventListener("visibilitychange", handleVisibility);
      if (ws) {
        try {
          if (ws.readyState === WebSocket.CONNECTING) shouldCloseOnOpen = true;
          else if (ws.readyState === WebSocket.OPEN) ws.close();
        } catch (err) { handleSilent(err, "WorkspacePage:op5"); }
      }
    };
  }, [selectedChannel, activeTab]);

  const handleSendMessage = async (content) => {
    if (!selectedChannel || !content.trim()) return;
    try {
      await api.post(`/channels/${selectedChannel.channel_id}/messages`, { content });
      await fetchMessages();
    } catch (err) {
      toast.error("Failed to send message");
      return;
    }
    // Trigger collaboration separately — don't block message display
    try {
      const collabRes = await api.post(`/channels/${selectedChannel.channel_id}/collaborate`);
      if (collabRes.data.status === "limit_reached") {
        toast.error(collabRes.data.message);
      } else {
        setIsCollaborating(true);
      }
    } catch (err) { handleSilent(err, "WorkspacePage:op6"); }
  };

  // Fetch tasks
  const fetchTasks = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/tasks`);
      setTasks(res.data);
    } catch (err) { handleSilent(err, "WorkspacePage:op7"); }
  }, [workspaceId]);

  // Fetch reports
  const fetchReports = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/reports`);
      setReports(res.data);
    } catch (err) { handleSilent(err, "WorkspacePage:op8"); }
  }, [workspaceId]);

  // Fetch projects for linking
  const fetchProjects = useCallback(async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/projects`);
      setProjects(res.data || []);
    } catch (err) { handleSilent(err, "WorkspacePage:op9"); }
  }, [workspaceId]);

  useEffect(() => {
    if (activeTab === "tasks") fetchTasks();
    if (activeTab === "reports") fetchReports();
    if (activeTab === "projects" || activeTab === "members") {
      api.get(`/workspaces/${workspaceId}/members`).then(r => setMembers(r.data)).catch(() => {});
    }
    if (activeTab === "projects") fetchProjects();
  }, [activeTab, fetchTasks, fetchReports, fetchProjects, workspaceId]);

  const handleCreateChannel = async (name, description, agents) => {
    try {
      const res = await api.post(`/workspaces/${workspaceId}/channels`, {
        name,
        description,
        ai_agents: agents,
      });
      setChannels([...channels, res.data]);
      setSelectedChannel(res.data);
      toast.success("Channel created");
    } catch (err) {
      toast.error("Failed to create channel");
    }
  };

  const handleSelectChannel = (channel) => {
    setSelectedChannel(channel);
    setMessages([]);
    setAgentStatus({});
    setIsCollaborating(false);
    // Always navigate to chat view when selecting a channel
    setActiveTab("chat");
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex" data-testid="workspace-loading">
        <div className="w-56 border-r border-zinc-800/40 p-4 space-y-4">
          <div className="h-8 w-32 bg-zinc-800/60 rounded animate-pulse" />
          <SkeletonSidebarChannels count={5} />
        </div>
        <div className="flex-1 p-6">
          <SkeletonChatList count={6} />
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen bg-zinc-950 flex overflow-hidden" data-testid="workspace-page" role="application" aria-label="Nexus Cloud workspace">
      {/* Skip to main content link for keyboard users */}
      <a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[9999] focus:bg-cyan-500 focus:text-white focus:px-4 focus:py-2 focus:rounded-lg">
        Skip to main content
      </a>
      {/* Mobile overlay when flyout is open */}
      {openMenu && <div className="fixed inset-0 bg-black/50 z-30 lg:hidden" onClick={() => setOpenMenu(null)} />}
      <Sidebar
        workspace={workspace}
        channels={channels}
        selectedChannel={selectedChannel}
        onSelectChannel={handleSelectChannel}
        onCreateChannel={handleCreateChannel}
        onRefreshChannels={fetchChannels}
        user={user}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        projectRefreshKey={projectRefreshKey}
        collapsed={collapsed}
        onToggleCollapse={toggleSidebar}
        navMenus={NAV_MENUS}
        openMenu={openMenu}
        onMenuToggle={(id) => setOpenMenu(openMenu === id ? null : id)}
        pinnedTabs={pinnedTabs}
        getTabLabel={getTabLabel}
        onReorderPinned={reorderPinned}
      />

      {/* Flyout panel — expands right of sidebar when a nav group is open */}
      {openMenu && (() => {
        const menu = NAV_MENUS.find(m => m.id === openMenu);
        if (!menu) return null;
        const Icon = ICON_MAP[menu.icon];
        return (
          <div
            ref={menuRef}
            className="w-52 flex-shrink-0 bg-zinc-900/95 backdrop-blur border-r border-zinc-800/60 flex flex-col h-screen animate-in slide-in-from-left-2 duration-150 fixed lg:relative z-40 lg:z-auto left-0 top-0 lg:left-auto lg:top-auto"
            data-testid={`flyout-${menu.id}`}
          >
            <div className="px-3 py-3 border-b border-zinc-800/40 flex items-center gap-2">
              {Icon && <Icon className="w-4 h-4 text-cyan-400" />}
              <span className="text-sm font-semibold text-zinc-200">{menu.label}</span>
            </div>
            <div className="flex-1 overflow-y-auto py-1 px-1.5" role="menu">
              {menu.items.map((item, idx) => {
                const isActive = activeTab === item.key;
                const isFocused = focusedIndex === idx;
                const isPinned = pinnedTabs.includes(item.key);
                return (
                  <div key={item.key} className="flex items-center mb-0.5 group">
                    <button
                      onClick={() => { setActiveTab(item.key); setOpenMenu(null); }}
                      className={`flex-1 text-left px-3 py-2 rounded-l-md text-xs font-medium transition-colors flex items-center gap-2.5 ${
                        isActive
                          ? "text-cyan-400 bg-cyan-400/10"
                          : isFocused
                          ? "text-zinc-200 bg-zinc-800/70"
                          : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
                      }`}
                      data-testid={`tab-${item.key}`}
                      role="menuitem"
                      tabIndex={isFocused ? 0 : -1}
                    >
                      {isActive && <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 shrink-0" />}
                      <span>{item.label}</span>
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); togglePin(item.key); }}
                      className={`p-1.5 rounded-r-md transition-colors ${
                        isPinned
                          ? "text-cyan-400"
                          : "text-zinc-600 opacity-0 group-hover:opacity-100 hover:text-zinc-300"
                      }`}
                      title={isPinned ? "Unpin shortcut" : "Pin shortcut"}
                      data-testid={`pin-${item.key}`}
                    >
                      <Pin className={`w-3 h-3 ${isPinned ? "fill-current" : ""}`} />
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })()}
      <div className={`flex-1 flex flex-col min-h-0 transition-all duration-200 ${codeRepoOpen ? 'w-[55%]' : 'w-full'}`} style={{ minWidth: 0 }} role="main" id="main-content">
        {/* Top header with dashboard link */}
        <div className="flex-shrink-0 flex items-center justify-between px-3 sm:px-4 py-2 border-b border-zinc-800/60 bg-zinc-950/80">
          <div className="flex items-center gap-2 sm:gap-3 min-w-0">
            {/* Mobile sidebar toggle */}
            <Button variant="ghost" size="sm" onClick={toggleSidebar} className="lg:hidden text-zinc-400 hover:text-zinc-100 p-1" data-testid="mobile-menu-toggle">
              <LayoutDashboard className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/dashboard")}
              className="text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 gap-2"
              data-testid="header-dashboard-link"
            >
              <LayoutDashboard className="w-4 h-4" />
              <span className="text-xs font-medium">Dashboard</span>
            </Button>
            <span className="text-zinc-700">/</span>
            <span className="text-sm text-zinc-300 font-medium">{workspace?.name}</span>
            {selectedChannel && activeTab !== "chat" && (
              <>
                <span className="text-zinc-700">/</span>
                <button
                  onClick={() => setActiveTab("chat")}
                  className="text-sm text-cyan-400 hover:text-cyan-300 font-medium transition-colors cursor-pointer"
                  data-testid="header-channel-link"
                >
                  #{selectedChannel.name}
                </button>
              </>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={async () => { try { await api.post("/auth/logout"); } catch (err) { handleSilent(err, "WorkspacePage:op10"); } sessionStorage.removeItem("nexus_user"); sessionStorage.removeItem("nexus_session_token"); navigate("/"); }}
              className="flex items-center gap-2 px-5 py-2 rounded-xl text-sm font-semibold text-white bg-cyan-400 hover:bg-cyan-300 shadow-lg shadow-cyan-400/20 transition-all duration-200"
              data-testid="header-logout-btn"
              title={t("common.logout")}
            >
              <span>{t("common.logout")}</span>
              <LogOut className="w-4 h-4" />
            </button>
            <NotificationBell onNavigate={(path) => navigate(path)} />
          </div>
        </div>
        
        {/* Tab content */}
        {/* Module gate: if the active tab's module is disabled, show gate banner */}
        {activeTab && activeTab !== "chat" && activeTab !== "dashboard" && !isNavKeyEnabled(activeTab) ? (
          <ModuleGateBanner moduleName={activeTab} moduleId={activeTab} />
        ) : (<>
        {activeTab === "chat" && (
          <ChatPanel
            key={selectedChannel?.channel_id}
            channel={selectedChannel}
            messages={messages}
            messagesLoading={messagesLoading}
            agentStatus={agentStatus}
            isCollaborating={isCollaborating}
            onSendMessage={handleSendMessage}
            user={user}
            workspaceId={workspaceId}
            onToggleCodeRepo={() => setCodeRepoOpen(prev => !prev)}
            codeRepoOpen={codeRepoOpen}
          />
        )}
        {activeTab === "dashboard" && (
          <ProjectsDashboard workspaceId={workspaceId} />
        )}
        {activeTab === "projects" && (
          <ProjectPanel
            workspaceId={workspaceId}
            channels={channels}
            members={members}
            onProjectChange={() => setProjectRefreshKey(k => k + 1)}
            onNavigateToChannel={(ch) => handleSelectChannel(ch)}
          />
        )}
        {activeTab === "code" && (
          <MultiRepoPanel workspaceId={workspaceId} />
        )}
        {activeTab === "workflows" && (
          <WorkflowPanel workspaceId={workspaceId} />
        )}
        {activeTab === "marketplace" && (
          <MarketplacePanel workspaceId={workspaceId} orgId={workspace?.org_id} />
        )}
        {activeTab === "artifacts" && (
          <ArtifactPanel workspaceId={workspaceId} />
        )}
        {activeTab === "schedules" && (
          <SchedulePanel workspaceId={workspaceId} channels={channels} />
        )}
        {activeTab === "images" && (
          <ImageGenPanel workspaceId={workspaceId} />
        )}
        {activeTab === "video" && (
          <VideoPanel workspaceId={workspaceId} />
        )}
        {activeTab === "audio" && (
          <AudioPanel workspaceId={workspaceId} />
        )}
        {activeTab === "knowledge" && (
          <KnowledgeExplorer workspaceId={workspaceId} />
        )}
        {(activeTab === "agent-teams" || activeTab === "agent-team-templates") && (
          <AgentTeamPanel workspaceId={workspaceId} />
        )}
        {(activeTab === "research-library" || activeTab === "lit-review" || activeTab === "annotations" || activeTab === "connectors") && (
          <ResearchIntelligencePanel workspaceId={workspaceId} />
        )}
        {activeTab === "docs" && (
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="flex items-center gap-1 px-4 pt-2 flex-shrink-0">
              <button onClick={() => setDocsSubTab("wiki")} className={`px-3 py-1 rounded-md text-xs transition-colors ${docsSubTab === "wiki" ? "bg-zinc-700 text-zinc-200" : "text-zinc-500 hover:text-zinc-300"}`} data-testid="docs-wiki-tab">Wiki</button>
              <button onClick={() => setDocsSubTab("files")} className={`px-3 py-1 rounded-md text-xs transition-colors ${docsSubTab === "files" ? "bg-zinc-700 text-zinc-200" : "text-zinc-500 hover:text-zinc-300"}`} data-testid="docs-files-tab">Files</button>
            </div>
            {docsSubTab === "wiki" ? <WikiPanel workspaceId={workspaceId} /> : <DocsPanel workspaceId={workspaceId} />}
          </div>
        )}
        {activeTab === "directives" && (
          <DirectiveDashboard workspaceId={workspaceId} />
        )}
        {activeTab === "guide" && (
          <GuideMe workspaceId={workspaceId} />
        )}
        {activeTab === "media" && (
          <MediaLibraryPanel workspaceId={workspaceId} />
        )}
        {activeTab === "drive" && (
          <div className="flex-1 flex min-h-0" data-testid="drive-panel">
            <div className="flex-1 overflow-y-auto p-6">
              <div className="max-w-4xl mx-auto space-y-4">
                <h2 className="text-lg font-semibold text-zinc-100" style={{ fontFamily: 'Syne, sans-serif' }}>Workspace Drive</h2>
                <p className="text-sm text-zinc-500">Upload, organize, and share files within this workspace.</p>
                <DrivePanel workspaceId={workspaceId} />
              </div>
            </div>
            <div className="w-80 border-l border-zinc-800/60 flex-shrink-0">
              <CloudFileBrowser workspaceId={workspaceId} />
            </div>
          </div>
        )}
        {activeTab === "ideation" && (
          <IdeationPanel workspaceId={workspaceId} channels={channels} />
        )}
        {activeTab === "gantt" && (
          <div className="flex-1 overflow-auto p-4"><GanttChart workspaceId={workspaceId} /></div>
        )}
        {activeTab === "planner" && (
          <div className="flex-1 overflow-auto p-4"><PlannerCalendar workspaceId={workspaceId} /></div>
        )}
        {activeTab === "agents" && (
          <div className="flex-1 overflow-y-auto p-6">
            <div className="max-w-2xl mx-auto">
              <NexusAgents workspaceId={workspaceId} />
            </div>
          </div>
        )}
        {activeTab === "studio" && (
          <AgentStudio workspaceId={workspaceId} />
        )}
        {activeTab === "skill-matrix" && (
          <SkillsMatrix workspaceId={workspaceId} />
        )}
        {activeTab === "catalog" && (
          <AgentCatalog workspaceId={workspaceId} />
        )}
        {activeTab === "training" && (
          <AgentTraining workspaceId={workspaceId} />
        )}
        {activeTab === "playground" && (
          <AgentPlayground workspaceId={workspaceId} />
        )}
        {activeTab === "evaluation" && (
          <AgentEvaluation workspaceId={workspaceId} />
        )}
        {activeTab === "leaderboard" && (
          <LeaderboardPanel />
        )}
        {activeTab === "dedup" && (
          <KnowledgeDedupPanel workspaceId={workspaceId} />
        )}
        {activeTab === "training-quality" && (
          <TrainingQualityDashboard workspaceId={workspaceId} />
        )}
        {activeTab === "skills" && (
          <WorkspaceSkillsTab workspaceId={workspaceId} />
        )}
        {activeTab === "tasks" && (
          <div className="flex-1 flex min-h-0">
            <div className="flex-1 min-w-0">
              <TaskBoard
                workspaceId={workspaceId}
                tasks={tasks}
                onRefresh={fetchTasks}
              />
            </div>
            <div className="w-[380px] flex-shrink-0 border-l border-zinc-800/60">
              <TaskPanel workspaceId={workspaceId} embedded />
            </div>
          </div>
        )}
        {activeTab === "members" && (
          <div className="flex-1 overflow-y-auto p-6">
            <div className="max-w-2xl mx-auto">
              <MembersPanel 
                workspaceId={workspaceId} 
                currentUserId={user?.user_id}
                isOwner={workspace?.owner_id === user?.user_id}
              />
            </div>
          </div>
        )}
        {activeTab === "tpm" && (
          <div className="flex-1 overflow-y-auto p-6">
            <div className="max-w-2xl mx-auto">
              <TPMDesignation workspaceId={workspaceId} />
            </div>
          </div>
        )}
        {activeTab === "reports" && (
          <Reports reports={reports} />
        )}
        {activeTab === "analytics" && (
          <Analytics workspaceId={workspaceId} userPlan={user?.plan || "free"} />
        )}
        {activeTab === "costs" && (
          <div className="flex-1 flex flex-col min-h-0">
            <CostDashboard workspaceId={workspaceId} />
            <div className="border-t border-zinc-800/60 p-6 max-w-5xl mx-auto w-full">
              <CostAlerts workspaceId={workspaceId} />
            </div>
          </div>
        )}
        {activeTab === "roi" && (
          <ROICalculator workspaceId={workspaceId} />
        )}
        {activeTab === "revenue" && (
          <RevenueSharing />
        )}
        {activeTab === "performance" && (
          <PerformanceTimeSeries workspaceId={workspaceId} />
        )}
        {activeTab === "arena" && (
          <AgentArenaPanel workspaceId={workspaceId} />
        )}
        {activeTab === "deployments" && (
          <DeploymentPanel workspaceId={workspaceId} channels={channels} />
        )}
        {activeTab === "repo-analytics" && (
          <div className="flex-1 overflow-y-auto p-6">
            <div className="max-w-4xl mx-auto">
              <h2 className="text-lg font-semibold text-zinc-100 mb-4" style={{ fontFamily: "Syne, sans-serif" }}>Code Repository Analytics</h2>
              <RepoAnalytics workspaceId={workspaceId} />
            </div>
          </div>
        )}
        {activeTab === "orchestration" && (
          <OrchestrationPanel workspaceId={workspaceId} />
        )}
        {activeTab === "fine-tuning" && (
          <FineTuningPanel workspaceId={workspaceId} />
        )}
        {activeTab === "reviews" && (
          <ReviewsPanel workspaceId={workspaceId} />
        )}
        {activeTab === "webhooks" && (
          <WebhooksPanel workspaceId={workspaceId} />
        )}
        {activeTab === "benchmarks" && (
          <BenchmarksPanel workspaceId={workspaceId} />
        )}
        {activeTab === "benchmark-compare" && (
          <BenchmarkCompare workspaceId={workspaceId} />
        )}
        {activeTab === "orch-schedules" && (
          <OrchSchedulePanel workspaceId={workspaceId} />
        )}
        {activeTab === "collab-templates" && (
          <CollabTemplatesPanel workspaceId={workspaceId} />
        )}
        {activeTab === "review-analytics" && (
          <ReviewAnalyticsPanel />
        )}
        {activeTab === "marketplace-search" && (
          <MarketplaceAdvancedSearch />
        )}
        {activeTab === "security" && (
          <SecurityDashboard />
        )}
        {activeTab === "nx-platform" && (
          <NXFeaturesPanel workspaceId={workspaceId} />
        )}
        {activeTab === "strategic" && (
          <StrategicFeaturesPanel workspaceId={workspaceId} />
        )}
        {activeTab === "a2a-pipelines" && (
          <A2APipelinePanel workspaceId={workspaceId} />
        )}
        {activeTab === "operator" && (
          <OperatorPanel workspaceId={workspaceId} />
        )}
        {activeTab === "audit-log" && (
          <AuditLogViewer workspaceId={workspaceId} />
        )}
        {activeTab === "data-export" && (
          <DataExportPanel workspaceId={workspaceId} />
        )}
        {(activeTab === "optimization" || activeTab === "compression-profiles" || activeTab === "compression-runs" || activeTab === "compression-compare") && (
          <NAVCPanel workspaceId={workspaceId} />
        )}
        {(activeTab === "inbox" || activeTab === "mail-accounts" || activeTab === "mail-rules" || activeTab === "mail-review" || activeTab === "mail-audit") && (
          <SmartInboxPanel workspaceId={workspaceId} />
        )}
        {(activeTab === "dojo" || activeTab === "dojo-scenarios" || activeTab === "dojo-data") && (
          <AgentDojoPanel workspaceId={workspaceId} />
        )}
        </>)}
      </div>
      
      {/* Code Repository Slide-out Panel */}
      <CodeRepoPanel
        workspaceId={workspaceId}
        isOpen={codeRepoOpen}
        onClose={() => setCodeRepoOpen(false)}
        channels={channels}
        projects={projects}
      />
      <CommandPalette onNavigate={(tab) => {
        if (tab === "code") { setCodeRepoOpen(true); if (activeTab !== "chat") setActiveTab("chat"); }
        else setActiveTab(tab);
      }} />
    </div>
  );
}


export default function WorkspacePage({ user }) {
  const { workspaceId } = useParams();
  return (
    <ModuleProvider workspaceId={workspaceId}>
      <WorkspacePageInner user={user} />
    </ModuleProvider>
  );
}
