import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { Loader2, ArrowLeft } from "lucide-react";

export default function WorkspaceShortcutPage({ tab, title }) {
  const navigate = useNavigate();
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const res = await api.get("/workspaces");
        const workspaces = res.data || [];
        if (workspaces.length === 0) {
          setError(`No workspace available for ${title}. Create a workspace first.`);
          return;
        }
        navigate(`/workspace/${workspaces[0].workspace_id}?tab=${tab}`, { replace: true });
      } catch {
        setError(`Unable to open ${title.toLowerCase()} right now.`);
      }
    };
    load();
  }, [navigate, tab, title]);

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center px-6" data-testid={`workspace-shortcut-${tab}`}>
      <div className="text-center max-w-md">
        {error ? (
          <>
            <div className="w-12 h-12 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center mx-auto mb-4">
              <ArrowLeft className="w-5 h-5 text-zinc-500" />
            </div>
            <h1 className="text-lg font-semibold text-zinc-200 mb-2">{title}</h1>
            <p className="text-sm text-zinc-500 mb-4">{error}</p>
            <button onClick={() => navigate("/dashboard")} className="px-4 py-2 rounded-lg bg-zinc-100 text-zinc-900 hover:bg-zinc-200 text-sm font-medium" data-testid={`workspace-shortcut-${tab}-back`}>
              Back to Dashboard
            </button>
          </>
        ) : (
          <>
            <Loader2 className="w-8 h-8 animate-spin text-zinc-500 mx-auto mb-4" />
            <p className="text-sm text-zinc-400">Opening {title.toLowerCase()}...</p>
          </>
        )}
      </div>
    </div>
  );
}