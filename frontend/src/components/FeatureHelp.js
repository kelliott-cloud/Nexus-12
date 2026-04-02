import { useState } from "react";
import { HelpCircle, X } from "lucide-react";

/**
 * FeatureHelp — Contextual help banner for feature panels.
 * Shows a dismissible help card with title, description, and bullet points.
 * Remembers dismissal per feature via localStorage.
 */
export function FeatureHelp({ featureId, title, description, bullets = [], tips = [] }) {
  const storageKey = `nexus_help_dismissed_${featureId}`;
  const [dismissed, setDismissed] = useState(() => localStorage.getItem(storageKey) === "1");
  const [expanded, setExpanded] = useState(false);

  if (dismissed && !expanded) {
    return (
      <button onClick={() => setExpanded(true)} className="flex items-center gap-1 text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors mb-2" data-testid={`help-toggle-${featureId}`}>
        <HelpCircle className="w-3 h-3" /> What is this?
      </button>
    );
  }

  return (
    <div className="mb-4 p-3 rounded-lg bg-cyan-950/20 border border-cyan-800/20" data-testid={`help-banner-${featureId}`}>
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-2">
          <HelpCircle className="w-4 h-4 text-cyan-400 mt-0.5 flex-shrink-0" />
          <div>
            <h3 className="text-sm font-medium text-cyan-300">{title}</h3>
            <p className="text-xs text-zinc-400 mt-1 leading-relaxed">{description}</p>
            {bullets.length > 0 && (
              <ul className="mt-2 space-y-1">
                {bullets.map((b, i) => (
                  <li key={i} className="text-xs text-zinc-400 flex items-start gap-1.5">
                    <span className="text-cyan-500 mt-0.5">&#8227;</span> {b}
                  </li>
                ))}
              </ul>
            )}
            {tips.length > 0 && (
              <div className="mt-2 pt-2 border-t border-cyan-800/20">
                {tips.map((t, i) => (
                  <p key={i} className="text-[10px] text-cyan-400/60 italic">{t}</p>
                ))}
              </div>
            )}
          </div>
        </div>
        <button onClick={() => { setDismissed(true); setExpanded(false); localStorage.setItem(storageKey, "1"); }} className="text-zinc-600 hover:text-zinc-400 p-0.5" title="Dismiss">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}

/**
 * Pre-built help content for all Nexus features.
 */
export const FEATURE_HELP = {
  chat: {
    title: "Chat & AI Collaboration",
    description: "Real-time messaging with AI agents. Multiple AI models collaborate in the same channel, responding to your messages and each other.",
    bullets: ["@mention specific agents to direct questions", "Enable Auto-Collab for continuous AI discussion", "Use the Manage Agents button to enable/disable specific AI models per channel"],
    tips: ["Tip: Disable agents you don't need to save on API costs"],
  },
  orchestration: {
    title: "Multi-Agent Orchestration",
    description: "Chain multiple AI agents together in sequential or parallel workflows. Each step passes its output to the next agent.",
    bullets: ["Sequential mode: agents run one after another in a chain", "Parallel mode: agents run simultaneously on the same input", "Add conditions to route outputs to different agents based on content"],
    tips: ["Tip: Start with 2-3 steps and expand as you validate the workflow"],
  },
  "fine-tuning": {
    title: "Fine-Tuning Pipeline",
    description: "Build training datasets from your agent's knowledge base and conversations, then use Claude AI to evaluate quality and generate optimized system prompts.",
    bullets: ["Create datasets from knowledge chunks and conversation history", "Claude evaluates consistency, coverage, and tone alignment", "Apply the optimized prompt to instantly improve your agent"],
    tips: ["Tip: Include both knowledge and conversation sources for best results"],
  },
  benchmarks: {
    title: "Agent Performance Benchmarks",
    description: "Create test suites to measure your agent's accuracy, response quality, and knowledge utilization with automated scoring.",
    bullets: ["Write test cases with expected keywords and topics", "Automated scoring: retrieval, keyword match, and topic relevance", "Run benchmarks after training to track improvement"],
    tips: ["Tip: Create at least 10 test cases across different topics for meaningful results"],
  },
  "benchmark-compare": {
    title: "Benchmark Comparison",
    description: "Compare benchmark scores across multiple runs side-by-side to track how your agent improves over time.",
    bullets: ["Score trends show improvement or regression", "Category breakdown reveals strengths and weaknesses", "Compare up to 5 runs at once"],
  },
  webhooks: {
    title: "Webhook Integrations",
    description: "Send real-time event notifications to external systems when things happen in your workspace — messages, tasks, workflows, and more.",
    bullets: ["16 event types: messages, tasks, workflows, collaboration, etc.", "HMAC secret signing for secure delivery verification", "Automatic retry with exponential backoff (5s → 30s → 2min)", "Dead-letter queue for permanently failed deliveries"],
    tips: ["Tip: Use the Test button to verify your endpoint before going live"],
  },
  reviews: {
    title: "Marketplace Reviews & Ratings",
    description: "Read and write reviews for marketplace agents and templates. Ratings help the community discover the best agents.",
    bullets: ["Star ratings (1-5) with written reviews", "Mark reviews as helpful to surface the best feedback", "Reviews require 3 community flags before auto-hiding (prevents censorship)"],
  },
  "review-analytics": {
    title: "Review Analytics",
    description: "Aggregate review statistics showing rating distribution, sentiment trends, and the most-reviewed templates in the marketplace.",
    bullets: ["Rating distribution (5-star breakdown)", "Sentiment analysis: positive, neutral, negative percentages", "30-day rating trend to spot quality changes"],
  },
  security: {
    title: "Security Dashboard",
    description: "Real-time platform security posture — monitor authentication, webhook health, and API activity across all workspaces.",
    bullets: ["Active sessions, failed logins, locked accounts", "Webhook delivery success rate and dead-letter queue size", "Security checklist: tenant isolation, password policy, OAuth, ReDoS protection, code sandboxing"],
    tips: ["Tip: Check this dashboard regularly to spot unusual login patterns"],
  },
  "nx-platform": {
    title: "Nexus Platform Features",
    description: "Advanced platform capabilities: transparent model routing, workspace branching, cost controls, MCP integrations, and execution chain auditing.",
    bullets: ["Model Routing: see which AI handles each task, override assignments, compare outputs side-by-side", "Workspaces: branch and snapshot workspace state for exploration", "Cost Controls: pre-execution estimates, budget limits, detailed cost attribution", "MCP Integrations: connect to external tools (GitHub, Slack, Jira, etc.)", "Execution Chains: visual DAG traces with replay, fork, and export"],
  },
  "a2a-pipelines": {
    title: "A2A Autonomous Workflows",
    description: "Multi-agent pipelines that run autonomously with quality gates, conditional routing, and automatic retries. Each step is executed by a different AI agent.",
    bullets: ["Quality gates validate output before proceeding (AI validation, keyword check, JSON schema)", "Conditional routing: branch to different agents based on output content", "Automatic retry with feedback injection when quality gates fail", "6 pre-built templates: Code Review, Content Pipeline, Support Triage, and more"],
    tips: ["Tip: Start with a template and customize it for your use case"],
  },
  operator: {
    title: "Nexus Operator",
    description: "Multi-agent autonomous computer use. Describe a goal in natural language and the Operator decomposes it into parallel tasks executed by AI agents.",
    bullets: ["AI plans tasks automatically with parallel execution groups", "Budget controls prevent runaway costs", "Observation sharing lets agents build on each other's findings", "Templates for common workflows: research, code review, content creation"],
    tips: ["Tip: Use 'Plan First' to review the task plan before execution", "Tip: Set a budget limit to control costs"],
  },
  strategic: {
    title: "Business & Platform Features",
    description: "Revenue tools, compliance, developer API, and marketplace features for scaling your Nexus deployment.",
    bullets: ["Usage Billing: per-model cost tracking with invoice generation", "Scheduled Jobs: run A2A pipelines on a cron schedule", "Agent Learning: track knowledge growth and quality over time", "Activity Feed: real-time cross-workspace AI activity stream", "Developer API: generate API keys for external integrations", "White-Label: custom branding per organization", "Agent Marketplace: publish and install trained agents with knowledge packs", "Compliance: SOC2-ready audit exports"],
  },
  "collab-templates": {
    title: "Collaboration Templates",
    description: "Pre-built multi-agent orchestration workflows you can install with one click. Each template defines a sequence of AI agents with specific roles.",
    bullets: ["Research & Summarize: parallel research → synthesis", "Draft, Review & Edit: content creation pipeline", "Multi-Perspective Analysis: same topic analyzed from 3 angles", "Code Review Pipeline: bugs → style → optimization", "Q&A Knowledge Pipeline: retrieval → comprehensive answer"],
  },
  "orch-schedules": {
    title: "Orchestration Schedules",
    description: "Run your orchestrations automatically on a recurring interval. Set up a schedule and the system triggers the workflow at the specified time.",
    bullets: ["Intervals from 5 minutes to weekly", "Enable/disable toggle without deleting the schedule", "Run count and last run timestamp for monitoring"],
  },
  "marketplace-search": {
    title: "Marketplace Search",
    description: "Discover and install agent templates, workflows, and tools from the marketplace. Filter by category, rating, and popularity.",
    bullets: ["Faceted search with text, category, and minimum rating filters", "Sort by popularity, rating, or recency", "One-click install to your workspace"],
  },
  training: {
    title: "Agent Training",
    description: "Train your AI agents with domain-specific knowledge. Upload documents, crawl websites, or search topics to build a knowledge base that makes your agent smarter.",
    bullets: ["4 training modes: Topic Search, Web URLs, Text/Docs, File Upload", "Real-time training progress with WebSocket updates", "Knowledge Explorer to search, edit, flag, and manage chunks"],
    tips: ["Tip: Start with a focused topic and expand gradually"],
  },
  "skill-matrix": {
    title: "Skills Matrix",
    description: "Visual overview of your agent's skill levels across all categories. The training depth overlay shows how much knowledge backs each skill.",
    bullets: ["46 skills across 6 categories: Engineering, Product, Data, Operations, Marketing, Finance", "Skill levels: Novice → Intermediate → Advanced → Expert → Master", "Training depth glow shows knowledge density per skill"],
  },
};
