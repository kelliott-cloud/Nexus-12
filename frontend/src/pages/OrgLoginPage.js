import { useState, useEffect } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Zap, Mail, Lock, User, AlertCircle, Loader2, Building2 } from "lucide-react";
import { toast } from "sonner";
import { api, API } from "@/App";

export default function OrgLoginPage() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const [org, setOrg] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const loadOrg = async () => {
      try {
        const res = await api.get(`/orgs/by-slug/${slug}`);
        setOrg(res.data);
      } catch (err) {
        setNotFound(true);
      } finally {
        setLoading(false);
      }
    };
    loadOrg();
  }, [slug]);

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!email || !password) return;
    setAuthLoading(true);
    setError("");
    try {
      const res = await api.post("/auth/login", { email, password });
      // Check if user is a member of this org
      const orgsRes = await api.get("/orgs/my-orgs");
      const isMember = orgsRes.data.organizations?.some(o => o.slug === slug);
      if (!isMember) {
        setError("You are not a member of this organization. Contact your org admin for access.");
        setAuthLoading(false);
        return;
      }
      navigate(`/org/${slug}/dashboard`, { state: { user: res.data, org } });
    } catch (err) {
      setError(err.response?.data?.detail || "Login failed");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    try {
      const res = await api.get("/auth/google/login");
      if (res.data?.url) { window.location.href = res.data.url; return; }
      toast.error("Google login not available. Use email/password or contact admin.");
    } catch (err) { toast.error(err?.response?.data?.detail || "Google login not available."); }
  };

  if (loading) return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
      <Loader2 className="w-8 h-8 animate-spin text-zinc-500" />
    </div>
  );

  if (notFound) return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
      <div className="text-center">
        <Building2 className="w-12 h-12 text-zinc-700 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-zinc-300 mb-2">Organization not found</h2>
        <p className="text-sm text-zinc-500 mb-6">The organization "{slug}" doesn't exist.</p>
        <Button onClick={() => navigate("/")} className="bg-zinc-100 text-zinc-900">Go to Nexus Home</Button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center px-4" data-testid="org-login-page">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          {org?.logo_url ? (
            <img src={org.logo_url} alt={org.name} className="w-16 h-16 rounded-xl mx-auto mb-4" />
          ) : (
            <div className="w-16 h-16 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center mx-auto mb-4">
              <Building2 className="w-8 h-8 text-zinc-400" />
            </div>
          )}
          <h1 className="text-2xl font-bold text-zinc-100" style={{ fontFamily: 'Syne, sans-serif' }}>{org?.name}</h1>
          <p className="text-sm text-zinc-500 mt-1">Sign in to your organization workspace</p>
        </div>

        <div className="p-6 rounded-xl bg-zinc-900/50 border border-zinc-800">
          <Button
            onClick={handleGoogleLogin}
            className="w-full bg-zinc-800 hover:bg-zinc-700 text-zinc-200 mb-4"
            data-testid="org-google-login-btn"
          >
            <svg className="w-4 h-4 mr-2" viewBox="0 0 24 24"><path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
            Sign in with Google
          </Button>

          <div className="relative my-4">
            <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-zinc-800" /></div>
            <div className="relative flex justify-center"><span className="bg-zinc-900/50 px-3 text-xs text-zinc-500">or</span></div>
          </div>

          <form onSubmit={handleLogin} className="space-y-3">
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
              <Input
                type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)}
                className="pl-10 bg-zinc-800/50 border-zinc-700 text-zinc-200"
                data-testid="org-email-input"
              />
            </div>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
              <Input
                type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)}
                className="pl-10 bg-zinc-800/50 border-zinc-700 text-zinc-200"
                data-testid="org-password-input"
              />
            </div>
            {error && (
              <div className="flex items-center gap-2 text-red-400 text-xs p-2 bg-red-500/10 rounded-lg" data-testid="org-login-error">
                <AlertCircle className="w-3 h-3" />
                {error}
              </div>
            )}
            <Button type="submit" disabled={authLoading} className="w-full bg-zinc-100 text-zinc-900 hover:bg-zinc-200" data-testid="org-login-btn">
              {authLoading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              Sign In
            </Button>
          </form>
        </div>

        <p className="text-center text-xs text-zinc-600 mt-6">
          Powered by <span className="text-zinc-400 font-medium" style={{ fontFamily: 'Syne, sans-serif' }}>Nexus</span>
        </p>
      </div>
    </div>
  );
}
