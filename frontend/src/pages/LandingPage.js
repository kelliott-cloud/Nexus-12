import { useEffect, useState } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ArrowRight, Users, Shield, Workflow, Code2, Globe, Sparkles, FolderKanban, BarChart3, Zap, Lock, Clock, CheckCircle2, Star, ChevronRight, Monitor, Cpu, Eye } from "lucide-react";
import { api } from "@/App";
import { useLanguage } from "@/contexts/LanguageContext";
import { LanguageToggle } from "@/components/LanguageToggle";

const LOGO_URL = "/logo.png";

const AI_AGENTS = [
  { name: "Claude", color: "#D97757" },
  { name: "ChatGPT", color: "#10A37F" },
  { name: "Gemini", color: "#4285F4" },
  { name: "Perplexity", color: "#20B2AA" },
  { name: "Mistral", color: "#FF7000" },
  { name: "DeepSeek", color: "#4D6BFE" },
  { name: "Grok", color: "#1DA1F2" },
  { name: "Groq", color: "#F55036" },
  { name: "Mercury 2", color: "#00D4FF" },
  { name: "Cohere", color: "#39594D" },
  { name: "Pi", color: "#FF6B35" },
  { name: "Manus", color: "#6C5CE7" },
  { name: "Qwen", color: "#615EFF" },
  { name: "Kimi", color: "#000000" },
  { name: "Llama", color: "#0467DF" },
  { name: "GLM", color: "#3D5AFE" },
  { name: "Cursor", color: "#00E5A0" },
  { name: "NotebookLM", color: "#FBBC04" },
  { name: "GitHub Copilot", color: "#171515" },
];

export default function LandingPage() {
  const navigate = useNavigate();
  const [checking, setChecking] = useState(true);
  const { t } = useLanguage();

  useEffect(() => {
    if (window.location.hash?.includes("session_id=")) { setChecking(false); return; }
    // NXS-018: Only check auth if session token exists — skip unnecessary 401s
    const token = sessionStorage.getItem("nexus_session_token");
    if (!token) { setChecking(false); return; }
    const checkAuth = async () => {
      try { await api.get("/auth/me"); navigate("/dashboard"); }
      catch (err) { setChecking(false); }
    };
    checkAuth();
  }, [navigate]);

  if (checking) return null;

  return (
    <div className="min-h-screen bg-[#07080c] text-zinc-100 overflow-x-hidden" data-testid="landing-page">
      {/* NXS-024: Skip navigation */}
      <a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:p-3 focus:bg-cyan-600 focus:text-white">Skip to main content</a>

      {/* ═══════ NAVBAR ═══════ */}
      <nav role="navigation" className="fixed top-0 w-full z-50 border-b border-white/5 bg-[#07080c]/80 backdrop-blur-2xl">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 sm:h-24 flex items-center justify-between">
          <div className="flex items-center gap-2 sm:gap-3.5">
            <img src={LOGO_URL} alt="Nexus Cloud" className="w-8 h-8 sm:w-14 sm:h-14 rounded-lg sm:rounded-xl object-contain" />
            <span className="font-bold text-sm sm:text-xl tracking-tight" style={{ fontFamily: "Syne, sans-serif" }}>NEXUS <span className="text-cyan-400">CLOUD</span></span>
          </div>
          <div className="hidden md:flex items-center gap-8 text-base text-zinc-400">
            <a href="#features" className="hover:text-white transition-colors">Features</a>
            <a href="#agents" className="hover:text-white transition-colors">AI Agents</a>
            <a href="#security" className="hover:text-white transition-colors">Security</a>
            <a href="#pricing" className="hover:text-white transition-colors">Pricing</a>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            <Button onClick={() => navigate("/auth")} variant="ghost" size="sm" className="text-zinc-400 hover:text-white text-xs sm:text-base hidden sm:inline-flex">Sign In</Button>
            <Button onClick={() => navigate("/auth")} size="sm" className="bg-cyan-500 hover:bg-cyan-400 text-white font-semibold text-xs sm:text-base px-3 sm:px-7 py-2 sm:py-3 rounded-lg whitespace-nowrap" data-testid="nav-get-started-btn">
              Get Started <ArrowRight className="w-3 h-3 sm:w-3.5 sm:h-3.5 ml-1" />
            </Button>
          </div>
        </div>
      </nav>

      {/* ═══════ HERO ═══════ */}
      <main id="main-content" role="main">
      <section className="relative pt-24 sm:pt-40 pb-12 sm:pb-24 px-4 sm:px-6">
        {/* Background effects */}
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute top-20 left-1/2 -translate-x-1/2 w-[900px] h-[600px] rounded-full bg-gradient-to-b from-cyan-500/6 via-blue-500/4 to-transparent blur-[150px]" />
          <div className="absolute top-40 right-20 w-[300px] h-[300px] rounded-full bg-purple-500/5 blur-[100px]" />
          <div className="absolute top-60 left-20 w-[200px] h-[200px] rounded-full bg-cyan-500/5 blur-[80px]" />
        </div>

        <div className="relative max-w-5xl mx-auto text-center">
          {/* Trust badge */}
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-cyan-500/20 bg-cyan-500/5 mb-8">
            <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
            <span className="text-xs text-cyan-400 font-medium">Enterprise-Grade AI Collaboration Platform</span>
          </div>

          <h1 className="text-3xl sm:text-5xl lg:text-7xl font-bold tracking-tight mb-4 sm:mb-6" style={{ fontFamily: "Syne, sans-serif", lineHeight: "1.15" }}>
            Your AI Team
          </h1>
          <div className="mb-6" style={{ lineHeight: "1" }}>
            <svg viewBox="0 0 900 100" className="w-full max-w-[680px] mx-auto" style={{ overflow: "visible", display: "block" }}>
              <defs>
                <linearGradient id="hero-grad" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#22d3ee" />
                  <stop offset="50%" stopColor="#60a5fa" />
                  <stop offset="100%" stopColor="#c084fc" />
                </linearGradient>
              </defs>
              <text x="50%" y="72" textAnchor="middle" fill="url(#hero-grad)" style={{ fontFamily: "Syne, sans-serif", fontWeight: 700, fontSize: "72px" }}>Working Together</text>
            </svg>
          </div>

          <p className="text-lg sm:text-xl text-zinc-400 max-w-2xl mx-auto mb-10 leading-relaxed">
            Nexus Cloud orchestrates 19 AI models in real-time collaboration channels.
            Ship faster with AI agents that plan, code, review, and deploy — together.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
            <Button onClick={() => navigate("/auth")} size="lg"
              className="bg-cyan-500 hover:bg-cyan-400 text-white font-semibold text-base px-8 py-6 rounded-xl shadow-[0_0_40px_rgba(0,188,212,0.2)] hover:shadow-[0_0_60px_rgba(0,188,212,0.3)] transition-all"
              data-testid="hero-cta">
              Start Building Free <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
            <Button variant="outline" size="lg" onClick={() => document.getElementById("how-it-works")?.scrollIntoView({ behavior: "smooth" })}
              className="border-zinc-700 text-zinc-300 hover:text-white hover:border-zinc-500 text-base px-8 py-6 rounded-xl">
              See How It Works
            </Button>
          </div>

          {/* Agent cloud */}
          <div id="agents" className="flex flex-wrap items-center justify-center gap-3 mb-8">
            {AI_AGENTS.map((a, i) => (
              <div key={a.name} className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-zinc-900/80 border border-zinc-800/50 hover:border-zinc-600 transition-all hover:scale-105"
                style={{ animationDelay: `${i * 100}ms` }}>
                <div className="w-5 h-5 rounded-full flex items-center justify-center text-[8px] font-bold text-white" style={{ backgroundColor: a.color }}>{a.name[0]}</div>
                <span className="text-xs text-zinc-400">{a.name}</span>
              </div>
            ))}
          </div>
          <p className="text-xs text-zinc-600">19 AI models working in harmony</p>
        </div>
      </section>

      {/* ═══════ STATS BAR ═══════ */}
      <section className="border-y border-white/5 bg-zinc-900/30 py-12">
        <div className="max-w-6xl mx-auto px-6 grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          {[
            { value: "19", label: "AI Models", sub: "Integrated" },
            { value: "99.9%", label: "Uptime", sub: "SLA Guaranteed" },
            { value: "SOC 2", label: "Compliant", sub: "Enterprise Security" },
            { value: "<500ms", label: "Response", sub: "Avg. Latency" },
          ].map((s) => (
            <div key={s.label || s.value}>
              <div className="text-3xl font-bold text-white mb-1">{s.value}</div>
              <div className="text-sm text-zinc-400">{s.label}</div>
              <div className="text-xs text-zinc-600">{s.sub}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ═══════ FEATURES ═══════ */}
      <section id="features" className="py-12 sm:py-24 px-4 sm:px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <span className="text-xs text-cyan-400 font-semibold uppercase tracking-widest">Platform Features</span>
            <h2 className="text-3xl sm:text-4xl font-bold mt-3 mb-4" style={{ fontFamily: "Syne, sans-serif" }}>Everything you need to build with AI</h2>
            <p className="text-zinc-400 max-w-xl mx-auto">From ideation to deployment, Nexus Cloud provides the infrastructure for AI-powered teams.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              { icon: Users, title: "Multi-Agent Collaboration", desc: "19 AI models collaborate in real-time channels. TPM-directed workflows prevent duplicate work and ensure quality.", color: "cyan", tag: "Core" },
              { icon: FolderKanban, title: "Project Lifecycle Management", desc: "Full PLM with projects, tasks, sprints, Gantt charts, and milestones. AI agents create and manage tasks automatically.", color: "blue", tag: "PLM" },
              { icon: Code2, title: "Code Repository & Review", desc: "Built-in code repo with AI-powered code review, syntax highlighting, version control, and GitHub sync.", color: "purple", tag: "Build" },
              { icon: Shield, title: "Enterprise Security", desc: "RBAC, DataGuard privacy layer, audit logging, encrypted keys, and SOC 2 compliant architecture.", color: "emerald", tag: "Security" },
              { icon: Workflow, title: "Visual Workflow Canvas", desc: "Drag-and-drop multi-agent workflows. Chain AI models, add conditions, and automate complex pipelines.", color: "amber", tag: "Automation" },
              { icon: Monitor, title: "Desktop Bridge", desc: "Connect AI agents to your local machine. Read files, run commands, and interact with your dev environment.", color: "rose", tag: "Integration" },
              { icon: BarChart3, title: "Analytics & Reporting", desc: "Token usage, cost tracking, agent performance dashboards, scheduled reports, and webhook alerts.", color: "indigo", tag: "Analytics" },
              { icon: Globe, title: "Autonomous Deployments", desc: "AI agents that run autonomously on triggers. Webhooks, cron schedules, multi-step execution with governance.", color: "teal", tag: "Deploy" },
              { icon: Sparkles, title: "AI Content Generation", desc: "Generate images, videos, audio, and documents. Social media publishing with AI-generated captions.", color: "pink", tag: "Create" },
            ].map((f) => (
              <div key={f.title} className="group p-6 rounded-2xl border border-zinc-800/50 bg-zinc-900/30 hover:bg-zinc-900/60 hover:border-zinc-700/60 transition-all duration-300 hover:-translate-y-1">
                <div className="flex items-center gap-3 mb-4">
                  <div className={`w-10 h-10 rounded-xl bg-${f.color}-500/10 flex items-center justify-center`}>
                    <f.icon className={`w-5 h-5 text-${f.color}-400`} />
                  </div>
                  <span className={`text-[9px] font-semibold uppercase tracking-widest text-${f.color}-400/70`}>{f.tag}</span>
                </div>
                <h3 className="text-base font-semibold text-zinc-100 mb-2">{f.title}</h3>
                <p className="text-sm text-zinc-500 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════ HOW IT WORKS ═══════ */}
      <section id="how-it-works" className="py-12 sm:py-24 px-4 sm:px-6 border-t border-white/5 bg-gradient-to-b from-zinc-900/20 to-transparent">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <span className="text-xs text-cyan-400 font-semibold uppercase tracking-widest">How It Works</span>
            <h2 className="text-3xl sm:text-4xl font-bold mt-3" style={{ fontFamily: "Syne, sans-serif" }}>From idea to production in minutes</h2>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-8">
            {[
              { step: "01", title: "Create Workspace", desc: "Set up a workspace and invite your AI team — choose from 11 specialized models." },
              { step: "02", title: "Define Objectives", desc: "Describe what you want to build. The TPM agent coordinates the team and assigns work." },
              { step: "03", title: "Agents Collaborate", desc: "AI agents work together in real-time — coding, reviewing, testing, and iterating." },
              { step: "04", title: "Deploy & Monitor", desc: "Deploy autonomously with governance. Track costs, performance, and quality metrics." },
            ].map((s) => (
              <div key={s.step} className="text-center">
                <div className="w-14 h-14 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center mx-auto mb-4">
                  <span className="text-lg font-bold text-cyan-400">{s.step}</span>
                </div>
                <h3 className="font-semibold text-zinc-200 mb-2">{s.title}</h3>
                <p className="text-sm text-zinc-500">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════ SECURITY ═══════ */}
      <section id="security" className="py-12 sm:py-24 px-4 sm:px-6">
        <div className="max-w-5xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-16 items-center">
            <div>
              <span className="text-xs text-emerald-400 font-semibold uppercase tracking-widest">Enterprise Security</span>
              <h2 className="text-3xl font-bold mt-3 mb-6" style={{ fontFamily: "Syne, sans-serif" }}>Built for teams that take security seriously</h2>
              <div className="space-y-4">
                {[
                  { icon: Lock, label: "End-to-end encryption for all API keys and credentials" },
                  { icon: Shield, label: "Role-based access control with org-level permissions" },
                  { icon: Eye, label: "DataGuard privacy layer — filter sensitive data before AI processing" },
                  { icon: BarChart3, label: "Complete audit logging with disagreement tracking" },
                  { icon: Clock, label: "Automated deployment governance with cost limits and approval gates" },
                ].map((item) => (
                  <div key={item.label} className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <item.icon className="w-4 h-4 text-emerald-400" />
                    </div>
                    <span className="text-sm text-zinc-300">{item.label}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              {[
                { label: "SOC 2", sub: "Type II Compliant" },
                { label: "GDPR", sub: "Data Protection" },
                { label: "SSO", sub: "Google OAuth" },
                { label: "RBAC", sub: "Fine-grained Access" },
              ].map((badge) => (
                <div key={badge.label} className="p-5 rounded-xl border border-zinc-800/50 bg-zinc-900/40 text-center hover:border-emerald-500/20 transition-colors">
                  <div className="text-xl font-bold text-white mb-1">{badge.label}</div>
                  <div className="text-xs text-zinc-500">{badge.sub}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ═══════ PRICING ═══════ */}
      <section id="pricing" className="py-12 sm:py-24 px-4 sm:px-6 border-t border-white/5">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <span className="text-xs text-cyan-400 font-semibold uppercase tracking-widest">Pricing</span>
            <h2 className="text-3xl sm:text-4xl font-bold mt-3 mb-4" style={{ fontFamily: "Syne, sans-serif" }}>Start free, scale as you grow</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              { name: "Starter", price: "$0", period: "forever", desc: "For individuals exploring AI collaboration", features: ["1 workspace", "3 channels", "5 AI models", "Community support"], cta: "Get Started Free", popular: false },
              { name: "Pro", price: "$29", period: "/month", desc: "For teams building with AI agents", features: ["Unlimited workspaces", "All 19 AI models", "10 deployments", "Priority support", "Desktop Bridge"], cta: "Start Pro Trial", popular: true },
              { name: "Enterprise", price: "Custom", period: "", desc: "For organizations with advanced needs", features: ["Everything in Pro", "SSO & RBAC", "Dedicated support", "Custom integrations", "SLA guarantee", "On-premise option"], cta: "Contact Sales", popular: false },
            ].map((plan) => (
              <div key={plan.name} className={`p-8 rounded-2xl border ${plan.popular ? "border-cyan-500/40 bg-cyan-500/5 shadow-[0_0_40px_rgba(0,188,212,0.08)]" : "border-zinc-800/50 bg-zinc-900/30"} relative`}>
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 bg-cyan-500 text-white text-[10px] font-bold uppercase tracking-wider rounded-full">Most Popular</div>
                )}
                <div className="mb-6">
                  <h3 className="text-lg font-semibold text-zinc-100">{plan.name}</h3>
                  <div className="flex items-baseline gap-1 mt-2">
                    <span className="text-4xl font-bold text-white">{plan.price}</span>
                    <span className="text-sm text-zinc-500">{plan.period}</span>
                  </div>
                  <p className="text-sm text-zinc-500 mt-2">{plan.desc}</p>
                </div>
                <ul className="space-y-3 mb-8">
                  {plan.features.map((f, j) => (
                    <li key={j} className="flex items-center gap-2 text-sm text-zinc-300">
                      <CheckCircle2 className="w-4 h-4 text-cyan-400 flex-shrink-0" />
                      {f}
                    </li>
                  ))}
                </ul>
                <Button onClick={() => navigate("/auth")} className={`w-full py-5 rounded-xl font-semibold ${plan.popular ? "bg-cyan-500 hover:bg-cyan-400 text-white" : "bg-zinc-800 hover:bg-zinc-700 text-zinc-200"}`}>
                  {plan.cta}
                </Button>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════ FINAL CTA ═══════ */}
      <section className="py-12 sm:py-24 px-4 sm:px-6 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-t from-cyan-500/5 to-transparent" />
        <div className="relative max-w-3xl mx-auto text-center">
          <h2 className="text-3xl sm:text-4xl font-bold mb-4" style={{ fontFamily: "Syne, sans-serif" }}>Ready to build with AI?</h2>
          <p className="text-lg text-zinc-400 mb-8">Join teams shipping 10x faster with AI agent collaboration.</p>
          <Button onClick={() => navigate("/auth")} size="lg"
            className="bg-cyan-500 hover:bg-cyan-400 text-white font-semibold text-base px-10 py-6 rounded-xl shadow-[0_0_40px_rgba(0,188,212,0.2)]"
            data-testid="final-cta">
            Get Started Free <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
      </section>

      </main>
      {/* ═══════ FOOTER ═══════ */}
      <footer role="contentinfo" className="border-t border-white/5 bg-zinc-900/20 py-16 px-6">
        <div className="max-w-6xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-12">
          <div>
            <div className="flex items-center gap-2 mb-4">
              <img src={LOGO_URL} alt="Nexus Cloud" className="w-6 h-6 rounded" />
              <span className="text-sm font-semibold text-zinc-300" style={{ fontFamily: "Syne, sans-serif" }}>NEXUS CLOUD</span>
            </div>
            <p className="text-xs text-zinc-600 leading-relaxed">Enterprise AI collaboration platform. 19 models working together to build what matters.</p>
          </div>
          <div>
            <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-4">Product</h4>
            <div className="space-y-2">
              {["Features", "Pricing", "Security"].map(l => (
                <a key={l} href={`#${l.toLowerCase()}`} className="block text-sm text-zinc-600 hover:text-zinc-300 transition-colors">{l}</a>
              ))}
              <span className="block text-sm text-zinc-700">Changelog — Coming Soon</span>
              <span className="block text-sm text-zinc-700">Roadmap — Coming Soon</span>
            </div>
          </div>
          <div>
            <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-4">Company</h4>
            <div className="space-y-2">
              <span className="block text-sm text-zinc-700">About — Coming Soon</span>
              <span className="block text-sm text-zinc-700">Blog — Coming Soon</span>
              <span className="block text-sm text-zinc-700">Careers — Coming Soon</span>
              <a href="mailto:support@nexus.cloud" className="block text-sm text-zinc-600 hover:text-zinc-300 transition-colors">Contact</a>
            </div>
          </div>
          <div>
            <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-4">Legal</h4>
            <div className="space-y-2">
              <a href="/terms" className="block text-sm text-zinc-600 hover:text-zinc-300 transition-colors">Terms of Service</a>
              <a href="/privacy" className="block text-sm text-zinc-600 hover:text-zinc-300 transition-colors">Privacy Policy</a>
              <a href="/acceptable-use" className="block text-sm text-zinc-600 hover:text-zinc-300 transition-colors">Acceptable Use</a>
            </div>
          </div>
        </div>
        <div className="max-w-6xl mx-auto mt-12 pt-8 border-t border-zinc-800/50 flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-xs text-zinc-700">&copy; {new Date().getFullYear()} Nexus Cloud. All rights reserved.</p>
          <div className="flex items-center gap-4">
            {[
              { label: "SOC 2", href: "/terms#security" },
              { label: "GDPR", href: "/privacy" },
              { label: "CCPA", href: "/privacy#ccpa" },
            ].map(b => (
              <a key={b.label} href={b.href} className="text-[9px] px-2 py-1 rounded border border-zinc-800 text-zinc-600 hover:text-zinc-400 hover:border-zinc-600 transition-colors cursor-pointer">{b.label}</a>
            ))}
          </div>
        </div>
      </footer>
    </div>
  );
}
