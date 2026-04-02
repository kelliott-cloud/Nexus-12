import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Shield, Plus, Trash2, Globe, Check, X, Loader2, Key, ExternalLink, Settings2, Copy } from "lucide-react";
import { toast } from "sonner";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { api } from "@/App";

export default function SSOConfigPanel() {
  const [configs, setConfigs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ protocol: "saml", provider_name: "", auto_provision: true, default_role: "member" });
  const [creating, setCreating] = useState(false);
  const [workspaces, setWorkspaces] = useState([]);
  const [selectedWs, setSelectedWs] = useState("");

  useEffect(() => { fetchAll(); }, []);

  const fetchAll = async () => {
    try {
      const [confRes, wsRes] = await Promise.all([
        api.get("/admin/sso/configs"),
        api.get("/workspaces?include_disabled=true"),
      ]);
      setConfigs(confRes.data?.configs || []);
      setWorkspaces(wsRes.data || []);
    } catch (err) { handleSilent(err, "SSOConfig:fetch"); }
    setLoading(false);
  };

  const createConfig = async () => {
    if (!selectedWs || !form.provider_name) {
      toast.error("Workspace and provider name required");
      return;
    }
    setCreating(true);
    try {
      await api.post(`/admin/sso/config?workspace_id=${selectedWs}`, form);
      toast.success("SSO configuration created");
      setShowForm(false);
      setForm({ protocol: "saml", provider_name: "", auto_provision: true, default_role: "member" });
      fetchAll();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to create SSO config");
    }
    setCreating(false);
  };

  const toggleConfig = async (configId, enabled) => {
    try {
      await api.put(`/admin/sso/config/${configId}`, { enabled: !enabled });
      toast.success(enabled ? "SSO disabled" : "SSO enabled");
      fetchAll();
    } catch (err) { handleError(err, "SSOConfig:toggle"); }
  };

  const deleteConfig = async (configId) => {
    try {
      await api.delete(`/admin/sso/config/${configId}`);
      toast.success("SSO configuration deleted");
      fetchAll();
    } catch (err) { handleError(err, "SSOConfig:delete"); }
  };

  const copyUrl = (url) => {
    navigator.clipboard.writeText(url);
    toast.success("Copied to clipboard");
  };

  if (loading) return <div className="py-8 text-center"><Loader2 className="w-4 h-4 animate-spin text-zinc-500 mx-auto" /></div>;

  return (
    <div className="space-y-4" data-testid="sso-config-panel">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="w-5 h-5 text-cyan-400" />
          <h2 className="text-lg font-semibold text-zinc-100" style={{ fontFamily: "Syne, sans-serif" }}>SSO Configuration</h2>
        </div>
        <Button size="sm" onClick={() => setShowForm(!showForm)} className="bg-zinc-800 text-zinc-300 text-xs gap-1" data-testid="sso-add-btn">
          <Plus className="w-3 h-3" /> Add Provider
        </Button>
      </div>

      {showForm && (
        <div className="p-4 rounded-lg border border-zinc-800 bg-zinc-900/50 space-y-3" data-testid="sso-config-form">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] text-zinc-500 uppercase mb-1 block">Protocol</label>
              <select value={form.protocol} onChange={e => setForm({ ...form, protocol: e.target.value })} className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-1.5 text-xs text-zinc-300" data-testid="sso-protocol-select">
                <option value="saml">SAML 2.0</option>
                <option value="oidc">OpenID Connect</option>
              </select>
            </div>
            <div>
              <label className="text-[10px] text-zinc-500 uppercase mb-1 block">Provider Name</label>
              <Input value={form.provider_name} onChange={e => setForm({ ...form, provider_name: e.target.value })} placeholder="e.g. Okta, Azure AD" className="bg-zinc-800 border-zinc-700 text-xs" data-testid="sso-provider-name" />
            </div>
            <div>
              <label className="text-[10px] text-zinc-500 uppercase mb-1 block">Workspace</label>
              <select value={selectedWs} onChange={e => setSelectedWs(e.target.value)} className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-1.5 text-xs text-zinc-300" data-testid="sso-workspace-select">
                <option value="">Select workspace...</option>
                {workspaces.map(ws => <option key={ws.workspace_id} value={ws.workspace_id}>{ws.name}</option>)}
              </select>
            </div>
            <div>
              <label className="text-[10px] text-zinc-500 uppercase mb-1 block">Default Role</label>
              <select value={form.default_role} onChange={e => setForm({ ...form, default_role: e.target.value })} className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-1.5 text-xs text-zinc-300">
                <option value="member">Member</option>
                <option value="admin">Admin</option>
              </select>
            </div>
          </div>

          {form.protocol === "saml" && (
            <div className="space-y-2">
              <Input value={form.idp_entity_id || ""} onChange={e => setForm({ ...form, idp_entity_id: e.target.value })} placeholder="IdP Entity ID" className="bg-zinc-800 border-zinc-700 text-xs" data-testid="sso-idp-entity" />
              <Input value={form.idp_sso_url || ""} onChange={e => setForm({ ...form, idp_sso_url: e.target.value })} placeholder="IdP SSO URL" className="bg-zinc-800 border-zinc-700 text-xs" data-testid="sso-idp-sso-url" />
              <textarea value={form.idp_certificate || ""} onChange={e => setForm({ ...form, idp_certificate: e.target.value })} placeholder="IdP Certificate (PEM)" rows={3} className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-xs text-zinc-300 placeholder:text-zinc-600" data-testid="sso-idp-cert" />
            </div>
          )}

          {form.protocol === "oidc" && (
            <div className="space-y-2">
              <Input value={form.client_id || ""} onChange={e => setForm({ ...form, client_id: e.target.value })} placeholder="Client ID" className="bg-zinc-800 border-zinc-700 text-xs" data-testid="sso-oidc-client-id" />
              <Input value={form.client_secret || ""} onChange={e => setForm({ ...form, client_secret: e.target.value })} placeholder="Client Secret" className="bg-zinc-800 border-zinc-700 text-xs" type="password" data-testid="sso-oidc-client-secret" />
              <Input value={form.authorization_url || ""} onChange={e => setForm({ ...form, authorization_url: e.target.value })} placeholder="Authorization URL" className="bg-zinc-800 border-zinc-700 text-xs" data-testid="sso-oidc-auth-url" />
              <Input value={form.token_url || ""} onChange={e => setForm({ ...form, token_url: e.target.value })} placeholder="Token URL" className="bg-zinc-800 border-zinc-700 text-xs" data-testid="sso-oidc-token-url" />
              <Input value={form.userinfo_url || ""} onChange={e => setForm({ ...form, userinfo_url: e.target.value })} placeholder="UserInfo URL (optional)" className="bg-zinc-800 border-zinc-700 text-xs" />
            </div>
          )}

          <div className="flex items-center gap-2">
            <input type="checkbox" checked={form.auto_provision} onChange={e => setForm({ ...form, auto_provision: e.target.checked })} className="rounded" id="auto-provision" />
            <label htmlFor="auto-provision" className="text-xs text-zinc-400">Auto-provision new users</label>
          </div>

          <div className="flex gap-2">
            <Button size="sm" onClick={createConfig} disabled={creating} className="bg-cyan-600 hover:bg-cyan-700 text-xs" data-testid="sso-save-btn">
              {creating ? <Loader2 className="w-3 h-3 animate-spin" /> : "Create Configuration"}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setShowForm(false)} className="text-xs text-zinc-500">Cancel</Button>
          </div>
        </div>
      )}

      <ScrollArea className="max-h-[400px]">
        {configs.length === 0 ? (
          <div className="text-center py-8 text-xs text-zinc-600">No SSO providers configured</div>
        ) : (
          <div className="space-y-2">
            {configs.map(config => (
              <div key={config.config_id} className="p-3 rounded-lg border border-zinc-800/40 bg-zinc-900/30 hover:bg-zinc-900/50 transition-colors" data-testid={`sso-config-${config.config_id}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${config.enabled ? "bg-cyan-500/10" : "bg-zinc-800"}`}>
                      <Globe className={`w-4 h-4 ${config.enabled ? "text-cyan-400" : "text-zinc-600"}`} />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-zinc-200">{config.provider_name}</span>
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-500 uppercase">{config.protocol}</span>
                        <span className={`text-[9px] px-1.5 py-0.5 rounded ${config.enabled ? "bg-emerald-500/20 text-emerald-400" : "bg-zinc-800 text-zinc-600"}`}>
                          {config.enabled ? "Active" : "Disabled"}
                        </span>
                      </div>
                      <span className="text-[10px] text-zinc-600">{config.workspace_id}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Button size="sm" variant="ghost" onClick={() => toggleConfig(config.config_id, config.enabled)} className="h-7 w-7 p-0" data-testid={`sso-toggle-${config.config_id}`}>
                      {config.enabled ? <X className="w-3.5 h-3.5 text-zinc-500" /> : <Check className="w-3.5 h-3.5 text-emerald-400" />}
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => deleteConfig(config.config_id)} className="h-7 w-7 p-0 text-red-400 hover:text-red-300" data-testid={`sso-delete-${config.config_id}`}>
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </div>

                {config.protocol === "saml" && (
                  <div className="mt-2 pl-11 space-y-1">
                    <div className="flex items-center gap-1 text-[10px] text-zinc-500">
                      <span>SP Metadata:</span>
                      <code className="text-zinc-400 truncate max-w-xs">{`/api/sso/saml/metadata/${config.config_id}`}</code>
                      <button onClick={() => copyUrl(window.location.origin + `/api/sso/saml/metadata/${config.config_id}`)} className="text-zinc-600 hover:text-zinc-400"><Copy className="w-2.5 h-2.5" /></button>
                    </div>
                    <div className="flex items-center gap-1 text-[10px] text-zinc-500">
                      <span>Login URL:</span>
                      <code className="text-zinc-400 truncate max-w-xs">{`/api/sso/saml/login/${config.config_id}`}</code>
                      <button onClick={() => copyUrl(window.location.origin + `/api/sso/saml/login/${config.config_id}`)} className="text-zinc-600 hover:text-zinc-400"><Copy className="w-2.5 h-2.5" /></button>
                    </div>
                  </div>
                )}

                {config.protocol === "oidc" && (
                  <div className="mt-2 pl-11 space-y-1">
                    <div className="flex items-center gap-1 text-[10px] text-zinc-500">
                      <span>Login URL:</span>
                      <code className="text-zinc-400 truncate max-w-xs">{`/api/sso/oidc/login/${config.config_id}`}</code>
                      <button onClick={() => copyUrl(window.location.origin + `/api/sso/oidc/login/${config.config_id}`)} className="text-zinc-600 hover:text-zinc-400"><Copy className="w-2.5 h-2.5" /></button>
                    </div>
                    <div className="flex items-center gap-1 text-[10px] text-zinc-500">
                      <span>Callback URL:</span>
                      <code className="text-zinc-400 truncate max-w-xs">{`/api/sso/oidc/callback/${config.config_id}`}</code>
                      <button onClick={() => copyUrl(window.location.origin + `/api/sso/oidc/callback/${config.config_id}`)} className="text-zinc-600 hover:text-zinc-400"><Copy className="w-2.5 h-2.5" /></button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
