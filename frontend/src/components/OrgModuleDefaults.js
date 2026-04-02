import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Settings2, Lock, Ban, Loader2, Save } from "lucide-react";

export default function OrgModuleDefaults({ orgId }) {
  const [defaults, setDefaults] = useState(null);
  const [registry, setRegistry] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [modules, setModules] = useState({});
  const [locked, setLocked] = useState([]);
  const [blocked, setBlocked] = useState([]);
  const [maxModels, setMaxModels] = useState(null);

  useEffect(() => {
    if (!orgId) return;
    Promise.all([
      api.get(`/orgs/${orgId}/module-defaults`),
      api.get("/modules/registry"),
    ]).then(([defRes, regRes]) => {
      const d = defRes.data;
      setDefaults(d);
      setModules(d.modules || {});
      setLocked(d.locked_modules || []);
      setBlocked(d.blocked_modules || []);
      setMaxModels(d.max_ai_models);
      setRegistry(regRes.data.modules || {});
    }).catch(() => {}).finally(() => setLoading(false));
  }, [orgId]);

  const save = async () => {
    setSaving(true);
    try {
      await api.put(`/orgs/${orgId}/module-defaults`, { modules, locked_modules: locked, blocked_modules: blocked, max_ai_models: maxModels });
      toast.success("Org defaults saved");
    } catch (err) { toast.error(err?.response?.data?.detail || "Save failed"); }
    setSaving(false);
  };

  const toggleDefault = (mid) => setModules(prev => ({ ...prev, [mid]: !prev[mid] }));
  const toggleLocked = (mid) => setLocked(prev => prev.includes(mid) ? prev.filter(m => m !== mid) : [...prev, mid]);
  const toggleBlocked = (mid) => setBlocked(prev => prev.includes(mid) ? prev.filter(m => m !== mid) : [...prev, mid]);

  if (loading) return <div className="flex justify-center py-8"><Loader2 className="w-5 h-5 animate-spin text-zinc-500" /></div>;

  return (
    <div className="space-y-4" data-testid="org-module-defaults">
      <div className="flex items-center gap-2"><Settings2 className="w-5 h-5 text-cyan-400" /><h3 className="text-sm font-medium text-zinc-100">Organization Module Defaults</h3></div>
      <p className="text-xs text-zinc-500">Set default modules for new workspaces, lock modules that members cannot disable, and block modules that members cannot enable.</p>

      <div className="space-y-2">
        {Object.entries(registry).map(([mid, mod]) => {
          if (mod.always_on) return null;
          const isDefault = modules[mid];
          const isLocked = locked.includes(mid);
          const isBlocked = blocked.includes(mid);
          return (
            <Card key={mid} className="bg-zinc-900/50 border-zinc-800">
              <CardContent className="py-3 flex items-center justify-between">
                <div>
                  <span className="text-sm text-zinc-200">{mod.name}</span>
                  <div className="flex gap-1 mt-0.5">
                    {isLocked && <Badge className="text-[7px] bg-amber-500/20 text-amber-400"><Lock className="w-2 h-2 mr-0.5" />Locked</Badge>}
                    {isBlocked && <Badge className="text-[7px] bg-red-500/20 text-red-400"><Ban className="w-2 h-2 mr-0.5" />Blocked</Badge>}
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="text-center"><span className="text-[8px] text-zinc-500 block">Default</span><Switch checked={!!isDefault} onCheckedChange={() => toggleDefault(mid)} className="scale-75" /></div>
                  <div className="text-center"><span className="text-[8px] text-zinc-500 block">Lock</span><Switch checked={isLocked} onCheckedChange={() => toggleLocked(mid)} className="scale-75" /></div>
                  <div className="text-center"><span className="text-[8px] text-zinc-500 block">Block</span><Switch checked={isBlocked} onCheckedChange={() => toggleBlocked(mid)} className="scale-75" /></div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="flex items-center gap-3">
        <div><label className="text-xs text-zinc-500 block mb-1">Max AI Models</label><Input type="number" value={maxModels || ""} onChange={e => setMaxModels(e.target.value ? parseInt(e.target.value) : null)} placeholder="No limit" className="bg-zinc-800 border-zinc-700 w-24 h-8" /></div>
        <Button onClick={save} disabled={saving} className="bg-cyan-600 hover:bg-cyan-700 mt-5">{saving ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Save className="w-3 h-3 mr-1" />}Save Defaults</Button>
      </div>
    </div>
  );
}
