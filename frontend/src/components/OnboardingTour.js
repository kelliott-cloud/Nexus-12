import { useState, useEffect } from "react";
import { X, ArrowRight, Sparkles, MessageSquare, Workflow, FolderKanban } from "lucide-react";
import { Button } from "@/components/ui/button";

const TOUR_STEPS = [
  { title: "Welcome to Nexus!", description: "Your AI collaboration platform. Let's take a quick tour.", icon: Sparkles, color: "text-emerald-400" },
  { title: "Create Channels", description: "Add AI agents to channels and watch them collaborate in real-time on your projects.", icon: MessageSquare, color: "text-blue-400" },
  { title: "Build Workflows", description: "Design multi-step AI workflows with a visual canvas. Chain agents, add conditions, automate tasks.", icon: Workflow, color: "text-purple-400" },
  { title: "Manage Projects", description: "Track tasks with Kanban boards. AI agents can create and update tasks autonomously.", icon: FolderKanban, color: "text-amber-400" },
];

export default function OnboardingTour({ onComplete }) {
  const [step, setStep] = useState(0);
  const [show, setShow] = useState(false);

  useEffect(() => {
    const seen = localStorage.getItem("nexus_tour_seen");
    if (!seen) setShow(true);
  }, []);

  // Dismiss tour on Escape key
  useEffect(() => {
    if (!show) return;
    const handleKey = (e) => { if (e.key === "Escape") finish(); };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [show]);

  const finish = () => {
    localStorage.setItem("nexus_tour_seen", "true");
    setShow(false);
    onComplete?.();
  };

  if (!show) return null;

  const current = TOUR_STEPS[step];
  const Icon = current.icon;

  return (
    <div className="fixed inset-0 z-[250] flex items-center justify-center" data-testid="onboarding-tour">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm cursor-pointer" onClick={finish} />
      <div className="relative bg-zinc-900 border border-zinc-800 rounded-2xl shadow-2xl w-96 p-6 text-center">
        <button onClick={finish} className="absolute top-3 right-3 p-1 rounded hover:bg-zinc-800 text-zinc-500"><X className="w-4 h-4" /></button>
        <div className={`w-14 h-14 rounded-2xl bg-zinc-800 flex items-center justify-center mx-auto mb-4 ${current.color}`}>
          <Icon className="w-7 h-7" />
        </div>
        <h3 className="text-lg font-semibold text-zinc-100 mb-2" style={{ fontFamily: 'Syne, sans-serif' }}>{current.title}</h3>
        <p className="text-sm text-zinc-400 mb-6 leading-relaxed">{current.description}</p>
        <div className="flex justify-center gap-1.5 mb-4">
          {TOUR_STEPS.map((_, i) => (
            <div key={i} className={`w-2 h-2 rounded-full transition-colors ${i === step ? "bg-emerald-400" : i < step ? "bg-emerald-400/40" : "bg-zinc-700"}`} />
          ))}
        </div>
        <p className="text-[10px] text-zinc-600 mb-3">Step {step + 1} of {TOUR_STEPS.length}</p>
        <div className="flex items-center justify-between">
          <button onClick={finish} className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors" data-testid="tour-skip-btn">Skip tour</button>
          {step < TOUR_STEPS.length - 1 ? (
            <Button onClick={() => setStep(step + 1)} size="sm" className="bg-emerald-500 hover:bg-emerald-400 text-white gap-1" data-testid="tour-next-btn">
              Next <ArrowRight className="w-3.5 h-3.5" />
            </Button>
          ) : (
            <Button onClick={finish} size="sm" className="bg-emerald-500 hover:bg-emerald-400 text-white" data-testid="tour-finish-btn">
              Get Started
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
