import { Badge } from "@/components/ui/badge";
import {
  ShieldCheck, SearchCode, Code, BookOpen, Kanban, Zap, Target, Flame
} from "lucide-react";

const BADGE_ICONS = {
  "security-specialist": ShieldCheck,
  "code-reviewer-certified": SearchCode,
  "full-stack-master": Code,
  "research-guru": BookOpen,
  "project-lead": Kanban,
  "fast-responder": Zap,
  "high-confidence": Target,
  "streak-master": Flame,
};

const BADGE_COLORS = {
  "security-specialist": "bg-red-500/10 text-red-400 border-red-500/20",
  "code-reviewer-certified": "bg-blue-500/10 text-blue-400 border-blue-500/20",
  "full-stack-master": "bg-violet-500/10 text-violet-400 border-violet-500/20",
  "research-guru": "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  "project-lead": "bg-amber-500/10 text-amber-400 border-amber-500/20",
  "fast-responder": "bg-orange-500/10 text-orange-400 border-orange-500/20",
  "high-confidence": "bg-green-500/10 text-green-400 border-green-500/20",
  "streak-master": "bg-red-500/10 text-red-400 border-red-500/20",
};

const BADGE_LABELS = {
  "security-specialist": "Security Specialist",
  "code-reviewer-certified": "Certified Code Reviewer",
  "full-stack-master": "Full-Stack Master",
  "research-guru": "Research Guru",
  "project-lead": "Project Lead",
  "fast-responder": "Fast Responder",
  "high-confidence": "High Confidence",
  "streak-master": "Streak Master",
};

export function SkillBadge({ badgeId, size = "sm" }) {
  const Icon = BADGE_ICONS[badgeId] || Target;
  const colors = BADGE_COLORS[badgeId] || "bg-zinc-800 text-zinc-400 border-zinc-700";
  const label = BADGE_LABELS[badgeId] || badgeId.replace(/-/g, " ");
  const iconSize = size === "lg" ? "w-4 h-4" : "w-3 h-3";
  const textSize = size === "lg" ? "text-xs" : "text-[9px]";
  const padding = size === "lg" ? "px-2.5 py-1.5" : "px-1.5 py-0.5";

  return (
    <span className={`inline-flex items-center gap-1 ${padding} rounded-md border ${colors} ${textSize} font-medium`}
      data-testid={`badge-${badgeId}`} title={label}>
      <Icon className={iconSize} />
      {label}
    </span>
  );
}

export function SkillBadgeList({ badges = [], size = "sm", max = 5 }) {
  if (!badges || badges.length === 0) return null;
  const displayed = badges.slice(0, max);
  const remaining = badges.length - max;

  return (
    <div className="flex flex-wrap gap-1" data-testid="badge-list">
      {displayed.map(b => (
        <SkillBadge key={b} badgeId={b} size={size} />
      ))}
      {remaining > 0 && (
        <Badge variant="secondary" className="bg-zinc-800 text-zinc-500 text-[8px]">
          +{remaining} more
        </Badge>
      )}
    </div>
  );
}
