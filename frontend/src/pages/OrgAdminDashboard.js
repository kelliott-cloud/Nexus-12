import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft, Building2, Users, BarChart3, Activity, Shield,
  Loader2, RefreshCw, UserPlus, Trash2, Mail
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { api } from "@/App";
import { toast } from "sonner";
import { OrgAdminAuditPanel } from "@/components/OrgAdminAuditPanel";

const ROLE_LABELS = {
  org_owner: "Owner", org_admin: "Admin", org_member: "Member", org_viewer: "Viewer"
};
const ROLE_COLORS = {
  org_owner: "bg-red-500/20 text-red-400",
  org_admin: "bg-amber-500/20 text-amber-400",
  org_member: "bg-zinc-800 text-zinc-300",
  org_viewer: "bg-zinc-800 text-zinc-500"
};
const PLAN_COLORS = {
  free: "bg-zinc-800 text-zinc-400",
  pro: "bg-amber-500/20 text-amber-400",
  enterprise: "bg-red-500/20 text-red-400"
};

export default function OrgAdminDashboard() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const [org, setOrg] = useState(null);
  const [stats, setStats] = useState(null);
  const [members, setMembers] = useState([]);
  const [billing, setBilling] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("overview");
  const [callerRole, setCallerRole] = useState(null);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("org_member");
  const [showInvite, setShowInvite] = useState(false);
  const [updatingRole, setUpdatingRole] = useState(null);

  useEffect(() => { loadAll(); }, [slug]);

  const loadAll = async () => {
    try {
      const orgRes = await api.get(`/orgs/by-slug/${slug}`);
      setOrg(orgRes.data);
      const orgId = orgRes.data.org_id;

      // Check role
      const myOrgs = await api.get("/orgs/my-orgs");
      const myOrg = myOrgs.data.organizations?.find(o => o.slug === slug);
      if (!myOrg || !["org_owner", "org_admin"].includes(myOrg.org_role)) {
        toast.error("Admin access required");
        navigate(`/org/${slug}/dashboard`);
        return;
      }
      setCallerRole(myOrg.org_role);

      const [statsRes, membersRes, billingRes] = await Promise.all([
        api.get(`/orgs/${orgId}/admin/stats`),
        api.get(`/orgs/${orgId}/admin/members`),
        api.get(`/orgs/${orgId}/billing`)
      ]);
      setStats(statsRes.data);
      setMembers(membersRes.data.members || []);
      setBilling(billingRes.data);
    } catch (err) {
      toast.error("Failed to load admin data");
      navigate(`/org/${slug}/dashboard`);
    } finally {
      setLoading(false);
    }
  };

  const inviteMember = async () => {
    if (!inviteEmail.trim() || !org) return;
    try {
      await api.post(`/orgs/${org.org_id}/members`, { email: inviteEmail, org_role: inviteRole });
      toast.success("Member invited");
      setShowInvite(false);
      setInviteEmail("");
      loadAll();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to invite");
    }
  };

  const updateMemberRole = async (userId, newRole) => {
    if (!org) return;
    setUpdatingRole(userId);
    try {
      await api.put(`/orgs/${org.org_id}/members/${userId}/role`, { org_role: newRole });
      setMembers(members.map(m => m.user_id === userId ? { ...m, org_role: newRole } : m));
      toast.success("Role updated");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to update role");
    } finally {
      setUpdatingRole(null);
    }
  };

  const removeMember = async (userId) => {
    if (!org) return;
    try {
      await api.delete(`/orgs/${org.org_id}/members/${userId}`);
      setMembers(members.filter(m => m.user_id !== userId));
      toast.success("Member removed");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to remove");
    }
  };

  const formatDate = (iso) => {
    if (!iso) return "";
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  };

  const tabs = [
    { id: "overview", label: "Overview", icon: BarChart3 },
    { id: "members", label: "Members", icon: Users },
    { id: "billing", label: "Billing", icon: Shield },
    { id: "activity", label: "Activity", icon: Activity },
  ];

  if (loading) return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
      <Loader2 className="w-8 h-8 animate-spin text-zinc-500" />
    </div>
  );

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100" data-testid="org-admin-dashboard">
      <header className="border-b border-zinc-800 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm" onClick={() => navigate(`/org/${slug}/dashboard`)}
              className="text-zinc-400 hover:text-zinc-100" data-testid="org-admin-back-btn">
              <ArrowLeft className="w-4 h-4 mr-2" /> Back
            </Button>
            <Building2 className="w-5 h-5 text-amber-400" />
            <h1 className="text-lg font-semibold" style={{ fontFamily: 'Syne, sans-serif' }}>{org?.name} Admin</h1>
          </div>
          <Button variant="ghost" size="sm" onClick={loadAll} className="text-zinc-400" data-testid="org-admin-refresh">
            <RefreshCw className="w-4 h-4 mr-2" /> Refresh
          </Button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-6">
        <div className="flex gap-1 mb-6 border-b border-zinc-800 overflow-x-auto">
          {tabs.map(t => (
            <button key={t.id} onClick={() => setActiveTab(t.id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm border-b-2 whitespace-nowrap transition-colors ${
                activeTab === t.id ? "border-zinc-100 text-zinc-100" : "border-transparent text-zinc-500 hover:text-zinc-300"
              }`} data-testid={`org-admin-tab-${t.id}`}>
              <t.icon className="w-4 h-4" /> {t.label}
              {t.id === "members" && <Badge className="bg-zinc-800 text-zinc-400 text-[10px] ml-1">{members.length}</Badge>}
            </button>
          ))}
        </div>

        {activeTab === "overview" && stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "Members", value: stats.members, color: "text-blue-400" },
              { label: "Workspaces", value: stats.workspaces, color: "text-emerald-400" },
              { label: "Channels", value: stats.channels, color: "text-amber-400" },
              { label: "Messages", value: stats.messages, color: "text-purple-400" },
            ].map(s => (
              <div key={s.label} className="p-5 rounded-xl bg-zinc-900/50 border border-zinc-800" data-testid={`org-stat-${s.label.toLowerCase()}`}>
                <p className="text-xs text-zinc-500 uppercase tracking-wider">{s.label}</p>
                <p className={`text-3xl font-bold mt-2 ${s.color}`}>{s.value}</p>
              </div>
            ))}
          </div>
        )}

        {activeTab === "members" && (
          <div>
            <div className="flex justify-end mb-4">
              <Dialog open={showInvite} onOpenChange={setShowInvite}>
                <DialogTrigger asChild>
                  <Button className="bg-zinc-100 text-zinc-900 hover:bg-zinc-200" data-testid="org-invite-btn">
                    <UserPlus className="w-4 h-4 mr-2" /> Invite Member
                  </Button>
                </DialogTrigger>
                <DialogContent className="bg-zinc-900 border-zinc-800 text-zinc-100">
                  <DialogHeader><DialogTitle>Invite Member</DialogTitle></DialogHeader>
                  <Input placeholder="Email address" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)}
                    className="bg-zinc-800/50 border-zinc-700" data-testid="org-invite-email" />
                  <Select value={inviteRole} onValueChange={setInviteRole}>
                    <SelectTrigger className="bg-zinc-800/50 border-zinc-700" data-testid="org-invite-role-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-zinc-900 border-zinc-800">
                      <SelectItem value="org_admin">Admin</SelectItem>
                      <SelectItem value="org_member">Member</SelectItem>
                      <SelectItem value="org_viewer">Viewer</SelectItem>
                    </SelectContent>
                  </Select>
                  <DialogFooter>
                    <Button onClick={inviteMember} className="bg-zinc-100 text-zinc-900" data-testid="org-invite-submit">Invite</Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>

            <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
              <table className="w-full">
                <thead className="bg-zinc-900">
                  <tr>
                    <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">User</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Email</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Role</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Workspaces</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Joined</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800">
                  {members.map((m) => (
                    <tr key={m.user_id} className="hover:bg-zinc-900/50" data-testid={`org-member-row-${m.user_id}`}>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          {m.picture ? (
                            <img src={m.picture} alt="" className="w-8 h-8 rounded-full" />
                          ) : (
                            <div className="w-8 h-8 rounded-full bg-zinc-700 flex items-center justify-center text-xs font-bold text-zinc-300">
                              {m.name?.[0] || "?"}
                            </div>
                          )}
                          <span className="text-sm text-zinc-200">{m.name || "Unknown"}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm text-zinc-400">{m.email}</td>
                      <td className="px-4 py-3">
                        {callerRole === "org_owner" && m.org_role !== "org_owner" ? (
                          <Select value={m.org_role} onValueChange={(v) => updateMemberRole(m.user_id, v)}
                            disabled={updatingRole === m.user_id}>
                            <SelectTrigger className={`w-28 h-7 text-xs border-0 ${ROLE_COLORS[m.org_role]}`}
                              data-testid={`org-role-select-${m.user_id}`}>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="bg-zinc-900 border-zinc-800">
                              <SelectItem value="org_admin">Admin</SelectItem>
                              <SelectItem value="org_member">Member</SelectItem>
                              <SelectItem value="org_viewer">Viewer</SelectItem>
                            </SelectContent>
                          </Select>
                        ) : (
                          <Badge className={ROLE_COLORS[m.org_role]}>{ROLE_LABELS[m.org_role]}</Badge>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-zinc-400">{m.workspace_count || 0}</td>
                      <td className="px-4 py-3 text-sm text-zinc-500">{formatDate(m.joined_at)}</td>
                      <td className="px-4 py-3">
                        {callerRole === "org_owner" && m.org_role !== "org_owner" && (
                          <Button variant="ghost" size="sm" onClick={() => removeMember(m.user_id)}
                            className="text-zinc-500 hover:text-red-400" data-testid={`org-remove-${m.user_id}`}>
                            <Trash2 className="w-3 h-3" />
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activeTab === "billing" && billing && (
          <div className="space-y-6">
            <div className="p-6 rounded-xl bg-zinc-900/50 border border-zinc-800">
              <h3 className="text-lg font-semibold mb-4">Current Plan</h3>
              <div className="flex items-center gap-4">
                <Badge className={`text-lg px-4 py-2 ${PLAN_COLORS[billing.plan]}`}>
                  {billing.plan?.toUpperCase() || "FREE"}
                </Badge>
                <span className="text-sm text-zinc-400">{billing.member_count} member{billing.member_count !== 1 ? "s" : ""}</span>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {Object.entries(billing.plans || {}).map(([key, plan]) => (
                <div key={key} className={`p-5 rounded-xl border transition-colors ${
                  billing.plan === key ? "bg-zinc-800/80 border-zinc-600" : "bg-zinc-900/50 border-zinc-800"
                }`} data-testid={`org-plan-${key}`}>
                  <h4 className="text-base font-semibold text-zinc-200">{plan.name}</h4>
                  <p className="text-2xl font-bold text-zinc-100 mt-2">
                    ${plan.price}<span className="text-sm text-zinc-500 font-normal">/mo</span>
                  </p>
                  <div className="text-xs text-zinc-500 mt-3 space-y-1">
                    <p>{plan.max_members === -1 ? "Unlimited" : plan.max_members} members</p>
                    <p>{plan.max_workspaces === -1 ? "Unlimited" : plan.max_workspaces} workspaces</p>
                  </div>
                  {billing.plan === key ? (
                    <Badge className="mt-4 bg-emerald-500/20 text-emerald-400">Current Plan</Badge>
                  ) : (
                    <Button variant="outline" size="sm" className="mt-4 border-zinc-700 text-zinc-400 text-xs">
                      {plan.price > (billing.plans[billing.plan]?.price || 0) ? "Upgrade" : "Downgrade"}
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === "activity" && org && (
          <OrgAdminAuditPanel orgId={org.org_id} />
        )}
      </main>
    </div>
  );
}
