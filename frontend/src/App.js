import React, { useState, useEffect } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import "@/App.css";
import { BrowserRouter, Routes, Route, useLocation, useNavigate, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { api } from "@/lib/api";
import { AgentConfigProvider } from "@/contexts/AgentConfigContext";
import { PlatformProfileProvider } from "@/contexts/PlatformProfileContext";
import { NexusHelperProvider, useHelper } from "@/contexts/NexusHelperContext";
import NexusHelper from "@/components/NexusHelper";
import LandingPage from "@/pages/LandingPage";
import AuthPage from "@/pages/AuthPage";
import AuthCallback from "@/pages/AuthCallback";
import Dashboard from "@/pages/Dashboard";
import WorkspacePage from "@/pages/WorkspacePage";
import BillingPage from "@/pages/BillingPage";
import ReplayPage from "@/pages/ReplayPage";
import CloudStorageCallback from "@/pages/CloudStorageCallback";
import SettingsPage from "@/pages/SettingsPage";
import InvitePage from "@/pages/InvitePage";
import AdminDashboard from "@/pages/AdminDashboard";
import MyBugReports from "@/pages/MyBugReports";
import DownloadPage from "@/pages/DownloadPage";
import OrgLoginPage from "@/pages/OrgLoginPage";
import OrgDashboard from "@/pages/OrgDashboard";
import OrgAdminDashboard from "@/pages/OrgAdminDashboard";
import LegalPage from "@/pages/LegalPage";
import { CookieConsentBanner, BetaBanner, TosAcceptanceModal } from "@/components/LegalComponents";
import OrgAnalytics from "@/pages/OrgAnalytics";
import WalkthroughBuilderPage from "@/components/WalkthroughBuilder";
import MarketplacePage from "@/pages/MarketplacePage";
import WorkspaceShortcutPage from "@/pages/WorkspaceShortcutPage";
import { ConfirmProvider } from "@/components/ConfirmDialog";
import { LanguageProvider, useLanguage } from "@/contexts/LanguageContext";
import { useIsMobile } from "@/hooks/useIsMobile";
import { MobileDashboard, MobileWorkspace, MobileAuth } from "@/pages/MobileApp";

// SSO callback — redirects to dashboard after SSO login
function SSOCallback() {
  const navigate = useNavigate();
  useEffect(() => {
    navigate("/dashboard", { replace: true });
  }, [navigate]);
  return null;
}

export { api } from "@/lib/api";
export { API, BACKEND_URL } from "@/lib/api";

// Loading screen
const LoadingScreen = () => (
  <div className="min-h-screen bg-zinc-950 flex items-center justify-center" data-testid="loading-screen">
    <div className="flex flex-col items-center gap-4">
      <div className="flex gap-2">
        <div className="w-2.5 h-2.5 rounded-full bg-[#D97757] animate-bounce" style={{ animationDelay: '0ms' }} />
        <div className="w-2.5 h-2.5 rounded-full bg-[#10A37F] animate-bounce" style={{ animationDelay: '150ms' }} />
        <div className="w-2.5 h-2.5 rounded-full bg-[#4D6BFE] animate-bounce" style={{ animationDelay: '300ms' }} />
        <div className="w-2.5 h-2.5 rounded-full bg-zinc-300 animate-bounce" style={{ animationDelay: '450ms' }} />
      </div>
      <p className="text-zinc-500 text-sm font-mono tracking-wider">LOADING NEXUS CLOUD</p>
    </div>
  </div>
);

// Protected route wrapper
const ProtectedRoute = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [authFailed, setAuthFailed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { markAuthenticated } = useLanguage();

  useEffect(() => {
    if (location.state?.user) {
      setUser(location.state.user);
      markAuthenticated();
      setLoading(false);
      return;
    }

    // Skip auth check if returning from Emergent OAuth bridge (wait for session exchange)
    if (window.location.hash?.includes('session_id=')) {
      setLoading(false);
      return;
    }

    // Always verify via /auth/me — sole source of auth truth
    const checkAuth = async () => {
      try {
        const response = await api.get("/auth/me");
        setUser(response.data);
        markAuthenticated();
        sessionStorage.setItem("nexus_user", JSON.stringify({ user_id: response.data.user_id, name: response.data.name, platform_role: response.data.platform_role }));
      } catch (err) {
        if (err?.response?.status === 401) {
          sessionStorage.removeItem("nexus_user");
          setAuthFailed(true);
        }
      } finally {
        setLoading(false);
      }
    };
    checkAuth();
  }, [navigate, location.state, markAuthenticated]);

  useEffect(() => {
    if (authFailed) {
      navigate("/auth", { replace: true });
    }
  }, [authFailed, navigate]);

  if (loading) return <LoadingScreen />;
  if (!user) return <LoadingScreen />;

  return (
    <NexusHelperProvider>
      {typeof children === 'function' ? children(user) : 
        children?.props ? 
          <children.type {...children.props} user={user} /> : 
          children}
      <HelperOverlay />
    </NexusHelperProvider>
  );
};

function HelperOverlay() {
  const h = useHelper();
  return (
    <NexusHelper
      open={h.open} minimized={h.minimized} messages={h.messages}
      loading={h.loading} context={h.context}
      onToggle={h.toggle} onMinimize={h.minimize} onRestore={h.restore}
      onSend={h.sendMessage} onClear={h.clearHistory}
      onApproveAction={h.approveAction} onDismissAction={h.dismissAction}
    />
  );
}


class GlobalErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { hasError: false, error: null }; }
  static getDerivedStateFromError(error) { return { hasError: true, error }; }
  componentDidCatch(error, info) { console.error("[Nexus Fatal]", error, info); }
  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
          <div className="text-center max-w-md">
            <div className="w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/30 flex items-center justify-center mx-auto mb-4">
              <span className="text-2xl text-red-400">!</span>
            </div>
            <h1 className="text-xl font-semibold text-zinc-200 mb-2">Something went wrong</h1>
            <p className="text-sm text-zinc-500 mb-4">{this.state.error?.message || "An unexpected error occurred"}</p>
            <button onClick={() => window.location.reload()}
              className="px-4 py-2 bg-cyan-600 hover:bg-cyan-700 text-white rounded-lg text-sm font-medium">
              Reload Nexus
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

function AppRouter() {
  const location = useLocation();
  const isMobile = useIsMobile();

  // Detect session_id from Emergent OAuth bridge — route to AuthCallback
  if (location.hash?.includes('session_id=')) {
    return <AuthCallback />;
  }

  // Mobile routes — show landing page on root, separate UI for authenticated
  if (isMobile) {
    return (
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/auth" element={<AuthPage />} />
        <Route path="/dashboard" element={<ProtectedRoute>{(user) => <MobileDashboard user={user} />}</ProtectedRoute>} />
        <Route path="/workspace/:workspaceId" element={<ProtectedRoute>{(user) => <MobileWorkspace user={user} />}</ProtectedRoute>} />
        <Route path="/replay/:shareId" element={<ReplayPage />} />
        <Route path="/cloud-storage/callback" element={<CloudStorageCallback />} />
        <Route path="/social/callback" element={<CloudStorageCallback />} />
        <Route path="/terms" element={<LegalPage />} />
        <Route path="/privacy" element={<LegalPage />} />
        <Route path="/acceptable-use" element={<LegalPage />} />
        <Route path="/settings" element={<ProtectedRoute>{(user) => <SettingsPage user={user} />}</ProtectedRoute>} />
        <Route path="/billing" element={<ProtectedRoute>{(user) => <BillingPage user={user} />}</ProtectedRoute>} />
        <Route path="/workflows" element={<ProtectedRoute>{() => <WorkspaceShortcutPage tab="workflows" title="Workflows" />}</ProtectedRoute>} />
        <Route path="/analytics" element={<ProtectedRoute>{() => <WorkspaceShortcutPage tab="analytics" title="Analytics" />}</ProtectedRoute>} />
        <Route path="/agent-studio" element={<ProtectedRoute>{() => <WorkspaceShortcutPage tab="studio" title="Agent Studio" />}</ProtectedRoute>} />
        <Route path="/org/:slug" element={<OrgLoginPage />} />
        <Route path="*" element={<LandingPage />} />
      </Routes>
    );
  }

  // Desktop routes — existing UI unchanged
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/auth" element={<AuthPage />} />
      <Route path="/terms" element={<LegalPage />} />
      <Route path="/privacy" element={<LegalPage />} />
      <Route path="/acceptable-use" element={<LegalPage />} />
      <Route path="/replay/:shareId" element={<ReplayPage />} />
      <Route path="/cloud-storage/callback" element={<CloudStorageCallback />} />
      <Route path="/auth/sso-callback" element={<SSOCallback />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            {(user) => <Dashboard user={user} />}
          </ProtectedRoute>
        }
      />
      <Route
        path="/workspace/:workspaceId"
        element={
          <ProtectedRoute>
            {(user) => <WorkspacePage user={user} />}
          </ProtectedRoute>
        }
      />
      <Route
        path="/billing"
        element={
          <ProtectedRoute>
            {(user) => <BillingPage user={user} />}
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            {(user) => <SettingsPage user={user} />}
          </ProtectedRoute>
        }
      />
      <Route
        path="/invite/:linkCode"
        element={
          <ProtectedRoute>
            {(user) => <InvitePage user={user} />}
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin"
        element={
          <ProtectedRoute>
            {(user) => user?.platform_role === "super_admin" ? <AdminDashboard user={user} /> : <Navigate to="/dashboard" replace />}
          </ProtectedRoute>
        }
      />
      <Route
        path="/my-bugs"
        element={
          <ProtectedRoute>
            {(user) => <MyBugReports user={user} />}
          </ProtectedRoute>
        }
      />
      <Route
        path="/download"
        element={
          <ProtectedRoute>
            {(user) => <DownloadPage user={user} />}
          </ProtectedRoute>
        }
      />
      <Route
        path="/marketplace"
        element={
          <ProtectedRoute>
            {(user) => <MarketplacePage user={user} />}
          </ProtectedRoute>
        }
      />
      {/* Organization routes */}
      <Route path="/org/:slug" element={<OrgLoginPage />} />

      <Route path="/workflows" element={<ProtectedRoute>{() => <WorkspaceShortcutPage tab="workflows" title="Workflows" />}</ProtectedRoute>} />
      <Route path="/analytics" element={<ProtectedRoute>{() => <WorkspaceShortcutPage tab="analytics" title="Analytics" />}</ProtectedRoute>} />
      <Route path="/agent-studio" element={<ProtectedRoute>{() => <WorkspaceShortcutPage tab="studio" title="Agent Studio" />}</ProtectedRoute>} />

      <Route
        path="/org/:slug/dashboard"
        element={
          <ProtectedRoute>
            {(user) => <OrgDashboard user={user} />}
          </ProtectedRoute>
        }
      />
      <Route
        path="/org/:slug/admin"
        element={
          <ProtectedRoute>
            {(user) => (user?.platform_role === "super_admin" || user?.org_role === "admin" || user?.org_role === "owner")
              ? <OrgAdminDashboard user={user} />
              : <Navigate to="/dashboard" replace />}
          </ProtectedRoute>
        }
      />
      <Route
        path="/org/:slug/analytics"
        element={
          <ProtectedRoute>
            {(user) => <OrgAnalytics user={user} />}
          </ProtectedRoute>
        }
      />
      <Route
        path="/walkthrough-builder"
        element={
          <ProtectedRoute>
            {(user) => (
              <div className="h-screen flex bg-[#09090b]">
                <aside className="w-56 flex-shrink-0 bg-zinc-900/50 border-r border-zinc-800/40 flex flex-col">
                  <div className="px-4 py-4 border-b border-zinc-800/40">
                    <div className="flex items-center gap-2.5">
                      <img src="/logo.png" alt="Nexus Cloud" className="w-7 h-7 rounded-lg" />
                      <span className="font-bold text-sm text-zinc-100" style={{ fontFamily: 'Syne, sans-serif' }}>NEXUS <span className="text-cyan-400">CLOUD</span></span>
                    </div>
                  </div>
                  <div className="flex-1 px-3 py-3">
                    <button onClick={() => window.location.href = '/dashboard'} className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50 mb-1">Dashboard</button>
                    <button className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm bg-zinc-800 text-zinc-100 font-medium">Walkthrough Builder</button>
                  </div>
                  <div className="border-t border-zinc-800/40 px-3 py-3">
                    <div className="flex items-center gap-2"><div className="w-7 h-7 rounded-full bg-indigo-500 flex items-center justify-center text-[10px] font-bold text-white">{user?.name?.[0]}</div><span className="text-xs text-zinc-400 truncate">{user?.name}</span></div>
                  </div>
                </aside>
                <div className="flex-1 flex flex-col min-w-0">
                  <WalkthroughBuilderPage />
                </div>
              </div>
            )}
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}

function App() {
  // Apply saved theme on mount — scoped per user
  useEffect(() => {
    // Try user-scoped theme first, fall back to generic
    let saved = "default";
    try {
      const storedUser = sessionStorage.getItem("nexus_user");
      if (storedUser) {
        const user = JSON.parse(storedUser);
        saved = localStorage.getItem(`nexus_theme_${user.user_id}`) || localStorage.getItem("nexus_theme") || "default";
      } else {
        saved = localStorage.getItem("nexus_theme") || "default";
      }
    } catch (_) {
      saved = localStorage.getItem("nexus_theme") || "default";
    }
    const root = document.documentElement;
    // Remove all theme classes
    root.className = root.className.replace(/theme-\S+/g, "").trim();
    root.classList.remove("light", "dark");
    const natureThemes = ["beach", "forest", "desert", "river", "mountain", "sunset", "aurora", "tropical", "arctic", "volcano", "cherry-blossom", "lavender", "midnight", "coral-reef", "savanna", "bamboo", "glacier", "autumn", "nebula", "rainforest"];
    if (saved === "light") {
      root.classList.add("light");
    } else if (saved === "system") {
      const prefersDark = window.matchMedia("(prefers-color-scheme: dark)");
      root.classList.add(prefersDark.matches ? "dark" : "light");
      // PH2-29: Listen for OS theme changes
      const handler = (e) => {
        root.classList.remove("light", "dark");
        root.classList.add(e.matches ? "dark" : "light");
      };
      prefersDark.addEventListener("change", handler);
      return () => prefersDark.removeEventListener("change", handler);
    } else if (saved.startsWith("theme-") || natureThemes.includes(saved)) {
      root.classList.add("dark");
      root.classList.add(saved.startsWith("theme-") ? saved : `theme-${saved}`);
    } else {
      root.classList.add("dark");
    }
  }, []);

  return (
    <div>
    <PlatformProfileProvider>
    <AgentConfigProvider>
      <LanguageProvider>
        <ConfirmProvider>
        <GlobalErrorBoundary>
          <BrowserRouter>
            <AppRouter />
            <CookieConsentBanner />
          </BrowserRouter>
        </GlobalErrorBoundary>
        </ConfirmProvider>
        <Toaster
          theme={typeof window !== 'undefined' && localStorage.getItem('nexus_theme') === 'light' ? 'light' : 'dark'}
          position="top-right"
          className="!z-[99999]"
          toastOptions={{
            style: localStorage.getItem('nexus_theme') === 'light'
              ? { background: '#ffffff', border: '1px solid #e5e7eb', color: '#111827', zIndex: 99999 }
              : { background: '#18181b', border: '1px solid rgba(255,255,255,0.08)',
              color: '#fafafa', zIndex: 99999,
            },
          }}
        />
      </LanguageProvider>
    </AgentConfigProvider>
    </PlatformProfileProvider>
    </div>
  );
}

export default App;
