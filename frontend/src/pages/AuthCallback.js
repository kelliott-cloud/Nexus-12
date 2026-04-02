import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/App";
import { Loader2 } from "lucide-react";

export default function AuthCallback() {
  const navigate = useNavigate();
  const [status, setStatus] = useState("Processing login...");

  useEffect(() => {
    let attempts = 0;
    const maxAttempts = 20;

    const checkAuth = async () => {
      // Wait for pre-React session exchange to complete
      if (window.__NEXUS_AUTH_PENDING__) {
        attempts++;
        if (attempts < maxAttempts) {
          setTimeout(checkAuth, 250);
          return;
        }
        setStatus("Login timed out. Redirecting...");
        navigate("/auth", { replace: true });
        return;
      }

      // Check if session exchange succeeded
      const result = window.__NEXUS_AUTH_RESULT__;
      if (result?.success && result.data?.session_token) {
        try {
          const meRes = await api.get("/auth/me");
          if (meRes.data?.user_id) {
            navigate("/dashboard", { replace: true, state: { user: meRes.data } });
            return;
          }
        } catch (err) {
          console.warn("Auth verify failed after session exchange:", err);
        }
      }

      // Fallback: try POST /auth/session directly if hash has session_id
      const hash = window.location.hash;
      if (hash?.includes("session_id=")) {
        const params = new URLSearchParams(hash.substring(1));
        const sessionId = params.get("session_id");
        if (sessionId) {
          try {
            const res = await api.post("/auth/session", { session_id: sessionId });
            if (res.data?.session_token) {
              sessionStorage.setItem("nexus_session_token", res.data.session_token);
              navigate("/dashboard", { replace: true, state: { user: res.data } });
              return;
            }
          } catch (err) {
            console.warn("Direct session exchange failed:", err);
          }
        }
      }

      // All methods failed — redirect to auth
      setStatus("Login failed. Redirecting...");
      setTimeout(() => navigate("/auth", { replace: true }), 1000);
    };

    checkAuth();
  }, [navigate]);

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
      <div className="text-center">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-400 mx-auto mb-4" />
        <p className="text-sm text-zinc-400">{status}</p>
      </div>
    </div>
  );
}
