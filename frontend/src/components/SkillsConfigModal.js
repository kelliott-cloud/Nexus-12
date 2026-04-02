import { useState, useEffect } from "react";
import {
  Terminal, Search, Wrench, BarChart3, Sparkles, Bot,
  ExternalLink, Check, X, Loader2, Settings2, ChevronDown, ChevronUp, Info
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogDescription } from "@/components/ui/dialog";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { toast } from "sonner";
import { api } from "@/App";

const CATEGORY_ICONS = {
  code_execution: Terminal,
  search: Search,
  functions: Wrench,
  analysis: BarChart3,
  generation: Sparkles,
  automation: Bot,
};

const CATEGORY_COLORS = {
  code_execution: "text-emerald-400 bg-emerald-500/20",
  search: "text-blue-400 bg-blue-500/20",
  functions: "text-amber-400 bg-amber-500/20",
  analysis: "text-purple-400 bg-purple-500/20",
  generation: "text-pink-400 bg-pink-500/20",
  automation: "text-indigo-400 bg-indigo-500/20",
};

export default function SkillsConfigModal({ 
  workspaceId, 
  modelKey, 
  modelName,
  hasApiKey = false,
  trigger 
}) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [availableSkills, setAvailableSkills] = useState([]);
  const [enabledSkills, setEnabledSkills] = useState([]);
  const [expandedCategory, setExpandedCategory] = useState(null);

  useEffect(() => {
    if (open && workspaceId && modelKey) {
      fetchSkillsConfig();
    }
  }, [open, workspaceId, modelKey]);

  const fetchSkillsConfig = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/workspaces/${workspaceId}/ai-skills/${modelKey}`);
      setAvailableSkills(res.data.available_skills || []);
      setEnabledSkills(res.data.enabled_skills || []);
    } catch (err) {
      toast.error("Failed to load skills configuration");
    } finally {
      setLoading(false);
    }
  };

  const toggleSkill = async (skillId, isAlwaysEnabled) => {
    if (isAlwaysEnabled) {
      toast.info("This skill is always enabled for this AI model");
      return;
    }

    const newEnabled = enabledSkills.includes(skillId)
      ? enabledSkills.filter(s => s !== skillId)
      : [...enabledSkills, skillId];
    
    setEnabledSkills(newEnabled);
    
    // Save immediately
    setSaving(true);
    try {
      await api.put(`/workspaces/${workspaceId}/ai-skills/${modelKey}`, {
        skill_ids: newEnabled
      });
    } catch (err) {
      // Revert on error
      setEnabledSkills(enabledSkills);
      toast.error("Failed to update skills");
    } finally {
      setSaving(false);
    }
  };

  // Group skills by category
  const skillsByCategory = availableSkills.reduce((acc, skill) => {
    const cat = skill.category || "functions";
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(skill);
    return acc;
  }, {});

  const enabledCount = enabledSkills.length;
  const totalCount = availableSkills.length;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger || (
          <Button
            variant="outline"
            size="sm"
            className="border-zinc-700 text-zinc-300 hover:bg-zinc-800 gap-2"
            disabled={!hasApiKey}
            data-testid={`skills-config-btn-${modelKey}`}
          >
            <Settings2 className="w-4 h-4" />
            Skills
            {enabledCount > 0 && (
              <Badge className="bg-emerald-500/20 text-emerald-400 text-[10px] ml-1">
                {enabledCount}
              </Badge>
            )}
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="bg-zinc-900 border-zinc-800 max-w-lg max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-zinc-100 flex items-center gap-2">
            <Settings2 className="w-5 h-5" />
            {modelName} Skills
          </DialogTitle>
          <DialogDescription className="text-zinc-500 text-sm">
            Enable vendor-supported skills for this AI model in your workspace
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-zinc-400" />
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto pr-2 space-y-3 mt-4">
            {Object.entries(skillsByCategory).map(([category, skills]) => {
              const CategoryIcon = CATEGORY_ICONS[category] || Wrench;
              const colorClass = CATEGORY_COLORS[category] || "text-zinc-400 bg-zinc-500/20";
              const isExpanded = expandedCategory === category || Object.keys(skillsByCategory).length <= 2;
              const enabledInCategory = skills.filter(s => enabledSkills.includes(s.id)).length;

              return (
                <div key={category} className="border border-zinc-800 rounded-lg overflow-hidden">
                  <button
                    onClick={() => setExpandedCategory(isExpanded ? null : category)}
                    className="w-full flex items-center justify-between px-4 py-3 bg-zinc-800/50 hover:bg-zinc-800 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div className={`p-1.5 rounded ${colorClass.split(" ")[1]}`}>
                        <CategoryIcon className={`w-4 h-4 ${colorClass.split(" ")[0]}`} />
                      </div>
                      <span className="text-sm font-medium text-zinc-200 capitalize">
                        {category.replace("_", " ")}
                      </span>
                      <Badge className="bg-zinc-700 text-zinc-400 text-[10px]">
                        {enabledInCategory}/{skills.length}
                      </Badge>
                    </div>
                    {isExpanded ? (
                      <ChevronUp className="w-4 h-4 text-zinc-500" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-zinc-500" />
                    )}
                  </button>
                  
                  {isExpanded && (
                    <div className="divide-y divide-zinc-800/50">
                      {skills.map((skill) => {
                        const isEnabled = enabledSkills.includes(skill.id);
                        const isAlwaysEnabled = skill.always_enabled;
                        const isPriority = skill.priority;
                        const isBeta = skill.beta;

                        return (
                          <div
                            key={skill.id}
                            className="flex items-start justify-between px-4 py-3 hover:bg-zinc-800/30 transition-colors"
                          >
                            <div className="flex-1 pr-4">
                              <div className="flex items-center gap-2">
                                <span className="text-sm text-zinc-200">{skill.name}</span>
                                {isPriority && (
                                  <Badge className="bg-emerald-500/20 text-emerald-400 text-[9px]">
                                    Recommended
                                  </Badge>
                                )}
                                {isBeta && (
                                  <Badge className="bg-amber-500/20 text-amber-400 text-[9px]">
                                    Beta
                                  </Badge>
                                )}
                                {isAlwaysEnabled && (
                                  <Badge className="bg-blue-500/20 text-blue-400 text-[9px]">
                                    Always On
                                  </Badge>
                                )}
                              </div>
                              <p className="text-xs text-zinc-500 mt-1">{skill.description}</p>
                              {skill.docs_url && (
                                <a
                                  href={skill.docs_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1 text-[10px] text-blue-400 hover:text-blue-300 mt-1.5"
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  <ExternalLink className="w-3 h-3" />
                                  Documentation
                                </a>
                              )}
                            </div>
                            <TooltipProvider>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <div>
                                    <Switch
                                      checked={isEnabled || isAlwaysEnabled}
                                      onCheckedChange={() => toggleSkill(skill.id, isAlwaysEnabled)}
                                      disabled={saving || isAlwaysEnabled}
                                      className="data-[state=checked]:bg-emerald-500"
                                      data-testid={`skill-toggle-${skill.id}`}
                                    />
                                  </div>
                                </TooltipTrigger>
                                {isAlwaysEnabled && (
                                  <TooltipContent className="bg-zinc-800 border-zinc-700 text-zinc-300">
                                    <p>This skill is always enabled for {modelName}</p>
                                  </TooltipContent>
                                )}
                              </Tooltip>
                            </TooltipProvider>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between pt-4 border-t border-zinc-800 mt-4">
          <div className="flex items-center gap-2 text-xs text-zinc-500">
            <Info className="w-3 h-3" />
            Skills are used when {modelName} participates in collaborations
          </div>
          <div className="flex items-center gap-2">
            {saving && (
              <span className="text-xs text-zinc-500 flex items-center gap-1">
                <Loader2 className="w-3 h-3 animate-spin" />
                Saving...
              </span>
            )}
            <Badge className="bg-zinc-800 text-zinc-400">
              {enabledCount} of {totalCount} enabled
            </Badge>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// Compact version for the AI key row
export function SkillsConfigButton({ workspaceId, modelKey, modelName, hasApiKey }) {
  return (
    <SkillsConfigModal
      workspaceId={workspaceId}
      modelKey={modelKey}
      modelName={modelName}
      hasApiKey={hasApiKey}
    />
  );
}
