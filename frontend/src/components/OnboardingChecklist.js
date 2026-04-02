import { useState, useEffect } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { Button } from "@/components/ui/button";
import { CheckCircle2, Circle, X, Rocket, MessageSquare, Users, FolderKanban, Zap } from "lucide-react";
import { api } from "@/App";

const CHECKLIST_ITEMS = [
  { id: "create_workspace", label: "Create your first workspace", icon: Rocket, description: "Set up a workspace for your team" },
  { id: "create_channel", label: "Create a chat channel", icon: MessageSquare, description: "Add AI agents to collaborate with" },
  { id: "send_message", label: "Send your first message", icon: Zap, description: "Start a conversation with AI agents" },
  { id: "create_project", label: "Create a project", icon: FolderKanban, description: "Organize work into projects and tasks" },
  { id: "invite_member", label: "Invite a team member", icon: Users, description: "Collaborate with your team" },
];

export default function OnboardingChecklist({ user, workspaceCount }) {
  const [dismissed, setDismissed] = useState(false);
  const [completed, setCompleted] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem("nexus_onboarding_dismissed");
    if (stored === "true") { setDismissed(true); setLoading(false); return; }

    // OB-01: Use prop workspaceCount for reactive updates instead of API call
    (async () => {
      try {
        const done = {};
        if (workspaceCount > 0) done.create_workspace = true;
        const prefs = user?.onboarding_completed || {};
        setCompleted({ ...done, ...prefs });
      } catch (err) { handleSilent(err, "OnboardingChecklist:op1"); }
      setLoading(false);
    })();
  }, [user, workspaceCount]);

  const dismiss = () => {
    setDismissed(true);
    localStorage.setItem("nexus_onboarding_dismissed", "true");
  };

  const completedCount = Object.values(completed).filter(Boolean).length;
  const allDone = completedCount >= CHECKLIST_ITEMS.length;

  if (dismissed || allDone || loading) return null;

  return (
    <div className="mx-auto max-w-2xl p-4 mb-4 rounded-xl bg-zinc-900/80 border border-zinc-800/60 backdrop-blur" data-testid="onboarding-checklist">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-semibold text-zinc-100">Getting Started with Nexus Cloud</h3>
          <p className="text-[10px] text-zinc-500">{completedCount}/{CHECKLIST_ITEMS.length} completed</p>
        </div>
        <button onClick={dismiss} className="p-1 text-zinc-600 hover:text-zinc-400" aria-label="Dismiss onboarding">
          <X className="w-4 h-4" />
        </button>
      </div>
      {/* Progress bar */}
      <div className="h-1.5 bg-zinc-800 rounded-full mb-3 overflow-hidden">
        <div className="h-full bg-cyan-500 rounded-full transition-all" style={{ width: `${(completedCount / CHECKLIST_ITEMS.length) * 100}%` }} />
      </div>
      <div className="space-y-1.5">
        {CHECKLIST_ITEMS.map(item => {
          const Icon = item.icon;
          const done = completed[item.id];
          return (
            <div key={item.id} className={`flex items-center gap-3 p-2 rounded-lg transition-colors ${done ? "opacity-60" : "hover:bg-zinc-800/30"}`}>
              {done ? <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" /> : <Circle className="w-4 h-4 text-zinc-600 flex-shrink-0" />}
              <Icon className="w-4 h-4 text-zinc-500 flex-shrink-0" />
              <div>
                <span className={`text-xs ${done ? "text-zinc-500 line-through" : "text-zinc-300"}`}>{item.label}</span>
                <p className="text-[9px] text-zinc-600">{item.description}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
