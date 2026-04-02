import { useState, useEffect } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ArrowLeft, Mail, Lock, User, AlertCircle, Building2, Globe, Check, X, Loader2, Shield } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/App";
import { markRecentAuth } from "@/lib/api";
import { useLanguage } from "@/contexts/LanguageContext";
import { LanguageToggle } from "@/components/LanguageToggle";
import MFAChallenge from "@/components/MFAChallenge";

function SSOLoginButtons() {
  const [providers, setProviders] = useState([]);
  useEffect(() => {
    api.get("/sso/providers").then(r => {
      // NXS-002: Filter out test providers, NXS-003: Deduplicate by name
      const all = r.data?.providers || [];
      const filtered = all.filter(p => !p.provider_name?.toLowerCase().includes('test'));
      const seen = new Set();
      const unique = filtered.filter(p => {
        const key = p.provider_name || p.config_id;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
      setProviders(unique);
    }).catch(() => {});
  }, []);
  if (!providers.length) return null;
  return (
    <>
      {providers.map(p => (
        <Button
          key={p.config_id}
          onClick={() => { window.location.href = `/api/sso/${p.protocol}/login/${p.config_id}`; }}
          variant="outline"
          className="w-full bg-zinc-900 border-zinc-800 hover:bg-zinc-800 text-zinc-200 font-medium gap-2"
          data-testid={`sso-login-${p.config_id}`}
        >
          <Globe className="w-4 h-4 text-cyan-400" />
          Sign in with {p.provider_name}
        </Button>
      ))}
    </>
  );
}

export default function AuthPage() {
  const navigate = useNavigate();
  const { t, lang } = useLanguage();
  const [tab, setTab] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [tosAccepted, setTosAccepted] = useState(false);
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [mfaChallenge, setMfaChallenge] = useState(null);
  // Company registration
  const [companyName, setCompanyName] = useState("");
  const [companySlug, setCompanySlug] = useState("");
  const [slugAvailable, setSlugAvailable] = useState(null);
  const [slugChecking, setSlugChecking] = useState(false);

  useEffect(() => {
    if (window.location.hash?.includes('session_id=')) return;
    // PH2-06: Only check auth if session token exists
    const token = sessionStorage.getItem("nexus_session_token");
    if (!token) return;
    const checkAuth = async () => {
      try { await api.get("/auth/me"); navigate("/dashboard"); }
      catch (err) { /* Expected 401 for expired sessions */ }
    };
    checkAuth();
  }, [navigate]);

  const handleEmailAuth = async (e) => {
    if (e) e.preventDefault();
    // NXS-009: Client-side validation
    if (!email || !password) {
      setError("Please enter your email and password.");
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError("Please enter a valid email address.");
      return;
    }
    if (tab === "register" && !name) {
      setError("Please enter your name.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const endpoint = tab === "register" ? "/auth/register" : "/auth/login";
      const payload = tab === "register" ? { email, password, name } : { email, password };
      const res = await api.post(endpoint, payload);
      // Check if MFA is required
      if (res.data?.mfa_required) {
        setMfaChallenge({ email: res.data.email, challengeToken: res.data.challenge_token });
        setLoading(false);
        return;
      }
      markRecentAuth();
      // Store user in sessionStorage for 401 interceptor protection
      if (res.data) {
        sessionStorage.setItem("nexus_user", JSON.stringify({ user_id: res.data.user_id, name: res.data.name, platform_role: res.data.platform_role }));
        if (res.data.session_token) {
          sessionStorage.setItem("nexus_session_token", res.data.session_token);
        }
      }
      toast.success(tab === "register" ? "Account created!" : "Welcome back!");
      navigate("/dashboard", { state: { user: res.data }, replace: true });
    } catch (err) {
      setError(err.response?.data?.detail || "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    try {
      const res = await api.get("/auth/google/login");
      if (res.data?.url) {
        window.location.href = res.data.url;
        return;
      }
      if (res.data?.use_emergent_bridge) {
        const redirectUrl = window.location.origin + '/dashboard';
        window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
        return;
      }
      toast.error("Google login is not configured. Please use email login or contact your admin.");
    } catch (err) {
      const redirectUrl = window.location.origin + '/dashboard';
      window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
    }
  };

  const handleForgotPassword = async () => {
    if (!email) { setError("Enter your email first"); return; }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { setError("Please enter a valid email address."); return; }
    try {
      await api.post("/auth/forgot-password", { email });
      toast.success("If an account exists with this email, a password reset link has been sent.");
    } catch (err) {
      toast.success("If an account exists with this email, a password reset link has been sent.");
    }
  };

  // Auto-generate slug from company name
  const handleCompanyNameChange = (val) => {
    setCompanyName(val);
    const generated = val.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 50);
    setCompanySlug(generated);
    setSlugAvailable(null);
    if (generated.length >= 2) checkSlug(generated);
  };

  const checkSlug = async (s) => {
    setSlugChecking(true);
    try {
      const res = await api.post("/orgs/check-slug", { slug: s });
      setSlugAvailable(res.data.available);
    } catch (err) {
      setSlugAvailable(null);
    } finally {
      setSlugChecking(false);
    }
  };

  const handleCompanyRegister = async () => {
    if (!companyName || !companySlug || !name || !email || !password) return;
    if (!slugAvailable) { setError("Please choose an available company URL"); return; }
    setLoading(true);
    setError("");
    try {
      const res = await api.post("/orgs/register", {
        name: companyName,
        slug: companySlug,
        admin_name: name,
        admin_email: email,
        admin_password: password
      });
      toast.success("Organization created!");
      navigate(`/org/${res.data.slug}/dashboard`);
    } catch (err) {
      setError(err.response?.data?.detail || "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center px-4" data-testid="auth-page">
      {/* Background effects */}
      <div className="absolute top-20 left-1/4 w-64 h-64 rounded-full bg-[#D97757]/5 blur-[100px]" />
      <div className="absolute bottom-20 right-1/4 w-64 h-64 rounded-full bg-[#10A37F]/5 blur-[100px]" />

      <div className="w-full max-w-md relative">
        {mfaChallenge ? (
          <>
            <button
              onClick={() => setMfaChallenge(null)}
              className="flex items-center gap-2 text-zinc-500 hover:text-zinc-300 transition-colors text-sm mb-8"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to login
            </button>
            <MFAChallenge
              email={mfaChallenge.email}
              challengeToken={mfaChallenge.challengeToken}
              onSuccess={(userData) => {
                markRecentAuth();
                sessionStorage.setItem("nexus_user", JSON.stringify({ user_id: userData.user_id, name: userData.name, platform_role: userData.platform_role }));
                if (userData.session_token) {
                  sessionStorage.setItem("nexus_session_token", userData.session_token);
                }
                toast.success("Welcome back!");
                navigate("/dashboard", { state: { user: userData }, replace: true });
              }}
              onBack={() => setMfaChallenge(null)}
            />
          </>
        ) : (
        <>
        <button
          onClick={() => navigate("/")}
          className="flex items-center gap-2 text-zinc-500 hover:text-zinc-300 transition-colors text-sm mb-8"
          data-testid="back-to-home"
        >
          <ArrowLeft className="w-4 h-4" />
          {t("common.back")}
        </button>

        {/* Logo */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <img src="/logo.png" alt="Nexus Cloud" className="w-10 h-10 rounded-lg" />
            <span className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Syne, sans-serif' }}>NEXUS <span className="text-cyan-400">CLOUD</span></span>
          </div>
          <LanguageToggle variant="compact" />
        </div>

        <Tabs value={tab} onValueChange={setTab} className="w-full">
          <TabsList className="w-full bg-zinc-900 border border-zinc-800 mb-6">
            <TabsTrigger value="login" className="flex-1 data-[state=active]:bg-zinc-800" data-testid="login-tab">{t("auth.signIn")}</TabsTrigger>
            <TabsTrigger value="register" className="flex-1 data-[state=active]:bg-zinc-800" data-testid="register-tab">{t("auth.signUp")}</TabsTrigger>
            <TabsTrigger value="company" className="flex-1 data-[state=active]:bg-zinc-800" data-testid="company-tab">
              <Building2 className="w-3 h-3 mr-1" /> {t("auth.company")}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="login" className="space-y-4">
            <div className="space-y-3">
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
                <Input
                  type="email" placeholder="Email" value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleEmailAuth()}
                  className="pl-10 bg-zinc-900 border-zinc-800 placeholder:text-zinc-600"
                  data-testid="email-input"
                />
              </div>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
                <Input
                  type="password" placeholder="Password" value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleEmailAuth()}
                  className="pl-10 bg-zinc-900 border-zinc-800 placeholder:text-zinc-600"
                  data-testid="password-input"
                />
              </div>
              <button
                onClick={handleForgotPassword}
                className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
                data-testid="forgot-password-btn"
              >
                Forgot password?
              </button>
            </div>
            <Button
              onClick={handleEmailAuth} disabled={loading || !email || !password}
              className="w-full bg-zinc-100 text-zinc-900 hover:bg-zinc-200 font-medium"
              data-testid="login-submit-btn"
            >
              {loading ? t("common.loading") : t("auth.signIn")}
            </Button>
          </TabsContent>

          <TabsContent value="register" className="space-y-4">
            <div className="space-y-3">
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
                <Input
                  placeholder={t("auth.namePlaceholder")} value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="pl-10 bg-zinc-900 border-zinc-800 placeholder:text-zinc-600"
                  data-testid="name-input"
                />
              </div>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
                <Input
                  type="email" placeholder={t("common.email")} value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="pl-10 bg-zinc-900 border-zinc-800 placeholder:text-zinc-600"
                  data-testid="register-email-input"
                />
              </div>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
                <Input
                  type="password" placeholder={t("auth.passwordPlaceholder")} value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleEmailAuth()}
                  className="pl-10 bg-zinc-900 border-zinc-800 placeholder:text-zinc-600"
                  data-testid="register-password-input"
                />
              </div>
            </div>
            <label className="flex items-start gap-2 cursor-pointer">
              <input type="checkbox" checked={tosAccepted} onChange={(e) => setTosAccepted(e.target.checked)}
                className="mt-0.5 accent-emerald-500" data-testid="tos-checkbox" />
              <span className="text-xs text-zinc-500">
                I agree to the <a href="/terms" target="_blank" className="text-emerald-400 hover:underline">Terms of Service</a>,{" "}
                <a href="/privacy" target="_blank" className="text-emerald-400 hover:underline">Privacy Policy</a>.
              </span>
            </label>
            <Button
              onClick={handleEmailAuth} disabled={loading || !email || !password || !name || !tosAccepted}
              className="w-full bg-zinc-100 text-zinc-900 hover:bg-zinc-200 font-medium"
              data-testid="register-submit-btn"
            >
              {loading ? t("common.loading") : t("auth.createAccount")}
            </Button>
          </TabsContent>

          <TabsContent value="company" className="space-y-4">
            <p className="text-xs text-zinc-500 mb-2">{t("auth.companySignup")}</p>
            <div className="space-y-3">
              <div className="relative">
                <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
                <Input
                  placeholder={t("auth.companyName")} value={companyName}
                  onChange={(e) => handleCompanyNameChange(e.target.value)}
                  className="pl-10 bg-zinc-900 border-zinc-800 placeholder:text-zinc-600"
                  data-testid="company-name-input"
                />
              </div>
              <div className="relative">
                <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
                <Input
                  placeholder="yourcompany.com" value={companySlug}
                  onChange={(e) => { setCompanySlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '')); setSlugAvailable(null); }}
                  onBlur={() => companySlug.length >= 2 && checkSlug(companySlug)}
                  className="pl-10 pr-10 bg-zinc-900 border-zinc-800 placeholder:text-zinc-600"
                  data-testid="company-slug-input"
                />
                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                  {slugChecking && <Loader2 className="w-4 h-4 animate-spin text-zinc-500" />}
                  {!slugChecking && slugAvailable === true && <Check className="w-4 h-4 text-emerald-400" />}
                  {!slugChecking && slugAvailable === false && <X className="w-4 h-4 text-red-400" />}
                </div>
              </div>
              {companySlug && (
                <p className="text-[10px] text-zinc-500">
                  {t("auth.yourLoginUrl")} <span className="text-zinc-300 font-mono">apps.nexus/{companySlug}</span>
                </p>
              )}
              <div className="pt-2 border-t border-zinc-800">
                <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-2">{t("auth.adminAccount")}</p>
              </div>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
                <Input
                  placeholder={t("auth.yourName")} value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="pl-10 bg-zinc-900 border-zinc-800 placeholder:text-zinc-600"
                  data-testid="company-admin-name-input"
                />
              </div>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
                <Input
                  type="email" placeholder={t("auth.adminEmail")} value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="pl-10 bg-zinc-900 border-zinc-800 placeholder:text-zinc-600"
                  data-testid="company-admin-email-input"
                />
              </div>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
                <Input
                  type="password" placeholder={t("auth.passwordPlaceholder")} value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleCompanyRegister()}
                  className="pl-10 bg-zinc-900 border-zinc-800 placeholder:text-zinc-600"
                  data-testid="company-admin-password-input"
                />
              </div>
            </div>
            <Button
              onClick={handleCompanyRegister}
              disabled={loading || !companyName || !companySlug || !name || !email || !password || !slugAvailable}
              className="w-full bg-zinc-100 text-zinc-900 hover:bg-zinc-200 font-medium"
              data-testid="company-register-btn"
            >
              {loading ? t("auth.creatingOrganization") : t("auth.createOrganization")}
            </Button>
          </TabsContent>
        </Tabs>

        {error && (
          <div className="flex items-center gap-2 mt-3 p-3 rounded-lg bg-red-500/10 border border-red-500/20" data-testid="auth-error">
            <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
            <span className="text-sm text-red-400">{error}</span>
          </div>
        )}

        {/* Divider */}
        <div className="flex items-center gap-3 my-6">
          <div className="flex-1 h-px bg-zinc-800" />
          <span className="text-xs text-zinc-600 font-mono">{lang === "es" ? "O CONTINUAR CON" : "OR CONTINUE WITH"}</span>
          <div className="flex-1 h-px bg-zinc-800" />
        </div>

        {/* Social logins */}
        <div className="space-y-3">
          <SSOLoginButtons />
          <Button
            onClick={handleGoogleLogin}
            variant="outline"
            className="w-full bg-zinc-900 border-zinc-800 hover:bg-zinc-800 text-zinc-200 font-medium"
            data-testid="google-login-btn"
          >
            <svg className="w-4 h-4 mr-2" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            Google
          </Button>
        </div>
        </>
        )}
      </div>
    </div>
  );
}
