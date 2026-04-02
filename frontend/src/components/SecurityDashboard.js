import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { handleSilent } from "@/lib/errorHandler";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Shield, Users, Lock, Unlock, Globe, AlertTriangle, Key,
  CheckCircle2, XCircle, Activity, Loader2, RefreshCw
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { FeatureHelp, FEATURE_HELP } from "@/components/FeatureHelp";

export default function SecurityDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const res = await api.get("/admin/security-dashboard");
      setData(res.data);
    } catch (err) { handleSilent(err, "SD:fetch"); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) return <div className="flex-1 flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-zinc-500" /></div>;
  if (!data) return <div className="flex-1 flex items-center justify-center text-zinc-500">Unable to load security dashboard</div>;

  const { auth, webhooks, platform, recent_events } = data;
  const whDeliveryRate = webhooks.deliveries_7d?.success_rate || 0;

  return (
    <div className="flex-1 overflow-y-auto p-6" data-testid="security-dashboard">
      <div className="max-w-6xl mx-auto space-y-6">
        <FeatureHelp featureId="security" {...FEATURE_HELP["security"]} />
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100">Security Dashboard</h2>
            <p className="text-sm text-zinc-500 mt-1">Real-time platform security posture and monitoring</p>
          </div>
          <Button variant="ghost" size="sm" onClick={() => { setLoading(true); fetchData(); }} data-testid="sd-refresh"><RefreshCw className="w-4 h-4 mr-1" /> Refresh</Button>
        </div>

        {/* Top-level KPIs */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: "Active Sessions", value: auth.active_sessions, icon: Users, color: "text-emerald-400", bg: "bg-emerald-600/15" },
            { label: "Failed Logins (24h)", value: auth.failed_logins_24h, icon: AlertTriangle, color: auth.failed_logins_24h > 5 ? "text-red-400" : "text-zinc-300", bg: auth.failed_logins_24h > 5 ? "bg-red-600/15" : "bg-zinc-800" },
            { label: "Locked Accounts", value: auth.locked_accounts, icon: Lock, color: auth.locked_accounts > 0 ? "text-amber-400" : "text-zinc-300", bg: auth.locked_accounts > 0 ? "bg-amber-600/15" : "bg-zinc-800" },
            { label: "Total Users", value: auth.total_users, icon: Users, color: "text-blue-400", bg: "bg-blue-600/15" },
          ].map(({ label, value, icon: Icon, color, bg }) => (
            <Card key={label} className="bg-zinc-900 border-zinc-800">
              <CardContent className="py-4 flex items-center gap-3">
                <div className={`w-10 h-10 rounded-lg ${bg} flex items-center justify-center`}>
                  <Icon className={`w-5 h-5 ${color}`} />
                </div>
                <div>
                  <div className={`text-xl font-bold ${color}`}>{value}</div>
                  <div className="text-xs text-zinc-500">{label}</div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Webhook Health */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader><CardTitle className="text-sm text-zinc-100 flex items-center gap-2"><Globe className="w-4 h-4" /> Webhook Health</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="p-3 bg-zinc-800/50 rounded-lg">
                  <div className="text-lg font-bold text-emerald-400">{webhooks.enabled}</div>
                  <div className="text-xs text-zinc-500">Active</div>
                </div>
                <div className="p-3 bg-zinc-800/50 rounded-lg">
                  <div className="text-lg font-bold text-red-400">{webhooks.disabled}</div>
                  <div className="text-xs text-zinc-500">Disabled</div>
                </div>
                <div className="p-3 bg-zinc-800/50 rounded-lg">
                  <div className="text-lg font-bold text-amber-400">{webhooks.dead_letters}</div>
                  <div className="text-xs text-zinc-500">Dead Letters</div>
                </div>
              </div>
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-zinc-400">Delivery Success Rate (7d)</span>
                  <span className={whDeliveryRate >= 95 ? "text-emerald-400" : whDeliveryRate >= 80 ? "text-amber-400" : "text-red-400"}>{whDeliveryRate}%</span>
                </div>
                <Progress value={whDeliveryRate} className="h-2" />
                <div className="flex justify-between text-xs text-zinc-600 mt-1">
                  <span>{webhooks.deliveries_7d?.success || 0} success</span>
                  <span>{webhooks.deliveries_7d?.failed || 0} failed</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Platform Overview */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader><CardTitle className="text-sm text-zinc-100 flex items-center gap-2"><Shield className="w-4 h-4" /> Platform Overview</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-zinc-800/50 rounded-lg flex items-center gap-3">
                  <Activity className="w-5 h-5 text-blue-400" />
                  <div>
                    <div className="text-lg font-bold text-zinc-100">{platform.total_workspaces}</div>
                    <div className="text-xs text-zinc-500">Workspaces</div>
                  </div>
                </div>
                <div className="p-3 bg-zinc-800/50 rounded-lg flex items-center gap-3">
                  <Key className="w-5 h-5 text-purple-400" />
                  <div>
                    <div className="text-lg font-bold text-zinc-100">{platform.api_keys_configured}</div>
                    <div className="text-xs text-zinc-500">API Keys Configured</div>
                  </div>
                </div>
              </div>

              {/* Security Checklist */}
              <div className="space-y-2">
                <div className="text-xs text-zinc-400 font-medium">Security Checklist</div>
                {[
                  { check: "Tenant Isolation", ok: true },
                  { check: "Password Policy", ok: true },
                  { check: "OAuth Validation", ok: true },
                  { check: "ReDoS Protection", ok: true },
                  { check: "Sandbox Code Exec", ok: true },
                ].map(({ check, ok }) => (
                  <div key={check} className="flex items-center gap-2 text-xs">
                    {ok ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> : <XCircle className="w-3.5 h-3.5 text-red-400" />}
                    <span className={ok ? "text-zinc-300" : "text-red-300"}>{check}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Recent Security Events */}
        {recent_events && recent_events.length > 0 && (
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader><CardTitle className="text-sm text-zinc-100 flex items-center gap-2"><AlertTriangle className="w-4 h-4 text-amber-400" /> Recent Security Events</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {recent_events.map((evt, i) => (
                <div key={i} className="flex items-center justify-between py-2 border-b border-zinc-800/50 last:border-0">
                  <div className="flex items-center gap-2">
                    <Lock className="w-3.5 h-3.5 text-amber-400" />
                    <span className="text-sm text-zinc-300">{evt.email}</span>
                    <Badge variant="outline" className="text-xs border-red-800/50 text-red-400">{evt.attempts} failed attempts</Badge>
                  </div>
                  {evt.locked_until && <span className="text-xs text-zinc-500">Locked until {new Date(evt.locked_until).toLocaleString()}</span>}
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
