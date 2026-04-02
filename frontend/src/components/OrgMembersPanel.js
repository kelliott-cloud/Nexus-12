import { useState, useEffect, useCallback } from "react";
import { useConfirm } from "@/components/ConfirmDialog";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { UserPlus, Trash2, Shield, Users } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/App";

const ROLE_COLORS = { org_owner: "bg-amber-500/20 text-amber-400", org_admin: "bg-blue-500/20 text-blue-400", org_member: "bg-zinc-700 text-zinc-300", org_viewer: "bg-zinc-800 text-zinc-500" };
const ROLE_LABELS = { org_owner: "Owner", org_admin: "Admin", org_member: "Member", org_viewer: "Viewer" };

function getTimeSince(ts) {
  const diff = Date.now() - new Date(ts).getTime();
  if (diff < 60000) return "Active now";
  if (diff < 3600000) return `Active ${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `Active ${Math.floor(diff / 3600000)}h ago`;
  return `Active ${Math.floor(diff / 86400000)}d ago`;
}

export default function OrgMembersPanel({ orgId, slug }) {
  const { confirm: confirmAction, ConfirmDialog: ConfirmDlg } = useConfirm();
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("org_member");
  const [showInvite, setShowInvite] = useState(false);

  const fetchMembers = useCallback(async () => {
    if (!orgId) return;
    try { const res = await api.get(`/orgs/${orgId}/admin/members`); setMembers(res.data.members || res.data || []); }
    catch (err) { handleSilent(err, "OrgMembersPanel:op1"); } finally { setLoading(false); }
  }, [orgId]);

  useEffect(() => { fetchMembers(); }, [fetchMembers]);

  const invite = async () => {
    if (!inviteEmail.trim()) return;
    try {
      await api.post(`/orgs/${orgId}/members/invite`, { email: inviteEmail, role: inviteRole });
      toast.success(`Invited ${inviteEmail}`);
      setInviteEmail(""); setShowInvite(false); fetchMembers();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed to invite"); }
  };

  const removeMember = async (userId) => {
    const _ok = await confirmAction("Remove Member", "Remove this member from the organization?"); if (!_ok) return;
    try { await api.delete(`/orgs/${orgId}/members/${userId}`); toast.success("Removed"); fetchMembers(); }
    catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  const changeRole = async (userId, newRole) => {
    try { await api.put(`/orgs/${orgId}/members/${userId}/role`, { role: newRole }); toast.success("Role updated"); fetchMembers(); }
    catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  return (
    <div data-testid="org-members-panel">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-zinc-100" style={{ fontFamily: 'Syne, sans-serif' }}>Members</h2>
          <p className="text-sm text-zinc-500">{members.length} member{members.length !== 1 ? "s" : ""}</p>
        </div>
        <Dialog open={showInvite} onOpenChange={setShowInvite}>
          <DialogTrigger asChild>
            <Button className="bg-emerald-500 hover:bg-emerald-400 text-white gap-2" data-testid="invite-member-btn">
              <UserPlus className="w-4 h-4" /> Invite Member
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-zinc-900 border-zinc-800">
            <DialogHeader><DialogTitle className="text-zinc-100">Invite Member</DialogTitle></DialogHeader>
            <div className="space-y-3 mt-2">
              <Input placeholder="Email address" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} className="bg-zinc-800 border-zinc-700 text-zinc-200" data-testid="invite-email-input" />
              <select value={inviteRole} onChange={(e) => setInviteRole(e.target.value)} className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200" data-testid="invite-role-select">
                <option value="org_admin">Admin</option>
                <option value="org_member">Member</option>
                <option value="org_viewer">Viewer</option>
              </select>
              <Button onClick={invite} disabled={!inviteEmail.trim()} className="w-full bg-emerald-500 hover:bg-emerald-400 text-white" data-testid="send-invite-btn">Send Invite</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {loading ? (
        <div className="text-center py-8 text-zinc-500">Loading...</div>
      ) : (
        <div className="space-y-2" data-testid="members-list">
          {members.map((m) => (
            <div key={m.user_id} className="flex items-center gap-3 p-3 rounded-lg bg-zinc-900/40 border border-zinc-800/40 group" data-testid={`member-${m.user_id}`}>
              <div className="relative">
                <div className="w-9 h-9 rounded-full bg-indigo-500 flex items-center justify-center text-sm font-bold text-white flex-shrink-0">
                  {(m.name || m.email || "?")[0]?.toUpperCase()}
                </div>
                {/* Online indicator */}
                <div className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-zinc-900 ${
                  m.last_active && (Date.now() - new Date(m.last_active).getTime()) < 300000 ? "bg-emerald-500" :
                  m.last_active && (Date.now() - new Date(m.last_active).getTime()) < 3600000 ? "bg-amber-500" :
                  "bg-zinc-600"
                }`} title={m.last_active ? `Last active: ${new Date(m.last_active).toLocaleString()}` : "Offline"} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-zinc-200">{m.name || "Unknown"}</p>
                <p className="text-[11px] text-zinc-500">{m.email}</p>
                {m.last_active && <p className="text-[9px] text-zinc-600">{getTimeSince(m.last_active)}</p>}
              </div>
              <Badge className={`text-[10px] ${ROLE_COLORS[m.org_role] || "bg-zinc-800 text-zinc-400"}`}>
                {ROLE_LABELS[m.org_role] || m.org_role}
              </Badge>
              {m.org_role !== "org_owner" && (
                <div className="flex gap-1 opacity-0 group-hover:opacity-100">
                  <select
                    value={m.org_role}
                    onChange={(e) => changeRole(m.user_id, e.target.value)}
                    className="bg-zinc-800 border border-zinc-700 rounded text-[10px] text-zinc-300 px-1.5 py-0.5"
                  >
                    <option value="org_admin">Admin</option>
                    <option value="org_member">Member</option>
                    <option value="org_viewer">Viewer</option>
                  </select>
                  <button onClick={() => removeMember(m.user_id)} className="p-1 rounded hover:bg-zinc-800 text-zinc-600 hover:text-red-400">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    <ConfirmDlg />
    </div>
    );
}
