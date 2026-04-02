import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  MessageSquare, Kanban, Bot, GitBranch, Code, Image, BarChart3, Shield,
  Loader2, Settings2, Zap
} from "lucide-react";

const ICONS = { "message-square": MessageSquare, kanban: Kanban, bot: Bot, "git-branch": GitBranch, code: Code, image: Image, "bar-chart-3": BarChart3, shield: Shield };

export default function ModuleSettingsPanel({ workspaceId }) {
  const [registry, setRegistry] = useState({});
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    Promise.all([
      api.get("/modules/registry"),
      api.get(`/workspaces/${workspaceId}/modules`),
    ]).then(([regRes, modRes]) => {
      setRegistry(regRes.data.modules || {});
      setConfig(modRes.data);
    }).catch(() => {}).finally(() => setLoading(false));
  }, [workspaceId]);

  const toggleModule = async (moduleId, enabled) => {
    setSaving(true);
    try {
      const res = await api.put(`/workspaces/${workspaceId}/modules`, { modules: { [moduleId]: enabled } });
      setConfig(res.data);
      toast.success(`${registry[moduleId]?.name} ${enabled ? "activated" : "deactivated"}`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to update");
    }
    setSaving(false);
  };

  if (loading) return <div className="flex justify-center py-8"><Loader2 className="w-5 h-5 animate-spin text-zinc-500" /></div>;

  const modules = config?.modules || {};

  return (
    <div className="space-y-4" data-testid="module-settings-panel">
      <div className="flex items-center gap-2 mb-2">
        <Settings2 className="w-5 h-5 text-cyan-400" />
        <h3 className="text-sm font-medium text-zinc-100">Module Configuration</h3>
        {config?.persona && <Badge className="text-[9px] bg-cyan-500/15 text-cyan-400">{config.persona}</Badge>}
      </div>
      <p className="text-xs text-zinc-500">Enable or disable feature modules for this workspace. Disabled modules hide their UI and block API access.</p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {Object.entries(registry).map(([mid, mod]) => {
          const Icon = ICONS[mod.icon] || Zap;
          const enabled = mod.always_on || modules[mid]?.enabled;
          return (
            <Card key={mid} className={`border transition-colors ${enabled ? "bg-zinc-900/70 border-zinc-700" : "bg-zinc-900/20 border-zinc-800/50 opacity-70"}`}>
              <CardContent className="py-3 flex items-start justify-between">
                <div className="flex items-start gap-2.5">
                  <Icon className={`w-4 h-4 mt-0.5 ${enabled ? "text-cyan-400" : "text-zinc-600"}`} />
                  <div>
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm font-medium text-zinc-200">{mod.name}</span>
                      {mod.always_on && <Badge className="text-[7px] bg-zinc-700 text-zinc-400">ALWAYS ON</Badge>}
                      {mod.monthly_price > 0 && <Badge className="text-[7px] bg-emerald-500/20 text-emerald-400">+${mod.monthly_price}/mo</Badge>}
                      <Badge className="text-[7px] bg-zinc-800 text-zinc-500">{mod.min_tier}+</Badge>
                    </div>
                    <p className="text-[10px] text-zinc-500 mt-0.5 leading-relaxed">{mod.description}</p>
                  </div>
                </div>
                {!mod.always_on && (
                  <Switch checked={!!enabled} onCheckedChange={(v) => toggleModule(mid, v)} disabled={saving} className="mt-0.5" />
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {config?.ai_models && (
        <div className="mt-4">
          <h4 className="text-xs text-zinc-400 font-medium mb-2">Enabled AI Models ({config.ai_models.length})</h4>
          <div className="flex flex-wrap gap-1">
            {config.ai_models.map(m => <Badge key={m} className="text-[9px] bg-cyan-500/15 text-cyan-400">{m}</Badge>)}
          </div>
        </div>
      )}
    </div>
  );
}
