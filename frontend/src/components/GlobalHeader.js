import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { LogOut, LayoutDashboard } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function GlobalHeader({ user, title }) {
  const navigate = useNavigate();

  const handleLogout = async () => {
    try { await api.post("/auth/logout"); } catch {}
    sessionStorage.removeItem("nexus_user");
    sessionStorage.removeItem("nexus_session_token");
    navigate("/");
  };

  return (
    <div className="sticky top-0 z-40 h-12 border-b border-zinc-800/40 bg-zinc-950/90 backdrop-blur-xl flex items-center justify-between px-4"
      data-testid="global-header">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => navigate("/dashboard")}
          className="text-zinc-400 hover:text-zinc-100 gap-2 h-8 px-2">
          <LayoutDashboard className="w-3.5 h-3.5" />
          <span className="text-xs">Dashboard</span>
        </Button>
        {title && (
          <>
            <span className="text-zinc-700">/</span>
            <span className="text-xs font-medium text-zinc-300">{title}</span>
          </>
        )}
      </div>
      <div className="flex items-center gap-3">
        {user && <span className="text-[10px] text-zinc-600">{user.name || user.email}</span>}
        <button onClick={handleLogout}
          className="flex items-center gap-2 px-5 py-2 rounded-xl text-sm font-semibold text-white bg-cyan-400 hover:bg-cyan-300 shadow-lg shadow-cyan-400/20 transition-all duration-200"
          data-testid="global-logout-btn">
          <span>Logout</span>
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
