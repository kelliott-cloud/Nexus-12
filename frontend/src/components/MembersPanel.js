import { useState, useEffect } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { useConfirm } from "@/components/ConfirmDialog";
import { 
  Users, UserPlus, Crown, User, Eye, Settings, X, Copy, 
  Link, Mail, Trash2, ChevronDown, Check, Loader2, LogOut
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { api } from "@/App";

const ROLE_CONFIG = {
  admin: {
    label: "Admin",
    icon: Crown,
    color: "text-amber-400",
    bgColor: "bg-amber-500/20",
    description: "Full access to workspace settings, members, and all features"
  },
  user: {
    label: "User",
    icon: User,
    color: "text-blue-400",
    bgColor: "bg-blue-500/20",
    description: "Can create channels, send messages, manage tasks, upload files"
  },
  observer: {
    label: "Observer",
    icon: Eye,
    color: "text-zinc-400",
    bgColor: "bg-zinc-500/20",
    description: "View-only access to channels, messages, and tasks"
  }
};

export default function MembersPanel({ workspaceId, currentUserId, isOwner }) {
  const { confirm: confirmAction, ConfirmDialog: ConfirmDlg } = useConfirm();
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [inviteDialogOpen, setInviteDialogOpen] = useState(false);
  const [linkDialogOpen, setLinkDialogOpen] = useState(false);

  useEffect(() => {
    fetchMembers();
  }, [workspaceId]);

  const fetchMembers = async () => {
    try {
      const res = await api.get(`/workspaces/${workspaceId}/members`);
      setMembers(res.data.members || []);
    } catch (err) {
      toast.error("Failed to load members");
    } finally {
      setLoading(false);
    }
  };

  const updateRole = async (userId, newRole) => {
    try {
      await api.put(`/workspaces/${workspaceId}/members/${userId}/role`, { role: newRole });
      setMembers(members.map(m => m.user_id === userId ? { ...m, role: newRole } : m));
      toast.success("Role updated");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to update role");
    }
  };

  const removeMember = async (userId, userName) => {
    const _ok = await confirmAction("Remove Member", `Remove ${userName} from this workspace?`); if (!_ok) return;
    try {
      await api.delete(`/workspaces/${workspaceId}/members/${userId}`);
      setMembers(members.filter(m => m.user_id !== userId));
      toast.success("Member removed");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to remove member");
    }
  };

  const leaveWorkspace = async () => {
    const _ok = await confirmAction("Leave Workspace", "Leave this workspace? You'll need a new invite to rejoin."); if (!_ok) return;
    try {
      await api.post(`/workspaces/${workspaceId}/leave`);
      toast.success("Left workspace");
      window.location.href = "/dashboard";
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to leave workspace");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-6 h-6 animate-spin text-zinc-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="members-panel">
      {/* Header with actions */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Users className="w-5 h-5 text-zinc-400" />
          <h3 className="text-lg font-semibold text-zinc-100">Members</h3>
          <Badge className="bg-zinc-800 text-zinc-400">{members.length}</Badge>
        </div>
        
        {isOwner && (
          <div className="flex items-center gap-2">
            <InviteLinkDialog 
              workspaceId={workspaceId} 
              open={linkDialogOpen}
              onOpenChange={setLinkDialogOpen}
            />
            <InviteByEmailDialog
              workspaceId={workspaceId}
              open={inviteDialogOpen}
              onOpenChange={setInviteDialogOpen}
              onInvited={fetchMembers}
            />
          </div>
        )}
      </div>

      {/* Members list */}
      <div className="space-y-2">
        {members.map((member) => {
          const roleConfig = ROLE_CONFIG[member.role] || ROLE_CONFIG.user;
          const RoleIcon = roleConfig.icon;
          const isCurrentUser = member.user_id === currentUserId;
          const canManage = isOwner && !member.is_owner && !isCurrentUser;

          return (
            <div
              key={member.user_id}
              className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-lg border border-zinc-800"
              data-testid={`member-${member.user_id}`}
            >
              <div className="flex items-center gap-3">
                {member.picture ? (
                  <img
                    src={member.picture}
                    alt={member.name}
                    className="w-10 h-10 rounded-full"
                  />
                ) : (
                  <div className="w-10 h-10 rounded-full bg-zinc-700 flex items-center justify-center">
                    <User className="w-5 h-5 text-zinc-400" />
                  </div>
                )}
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-zinc-100">
                      {member.name}
                    </span>
                    {member.is_owner && (
                      <Badge className="bg-amber-500/20 text-amber-400 text-[10px]">
                        Owner
                      </Badge>
                    )}
                    {isCurrentUser && (
                      <Badge className="bg-zinc-700 text-zinc-400 text-[10px]">
                        You
                      </Badge>
                    )}
                  </div>
                  <p className="text-xs text-zinc-500">{member.email}</p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                {canManage ? (
                  <Select
                    value={member.role}
                    onValueChange={(value) => updateRole(member.user_id, value)}
                  >
                    <SelectTrigger className="w-32 h-8 bg-zinc-900 border-zinc-700 text-xs">
                      <div className="flex items-center gap-1.5">
                        <RoleIcon className={`w-3 h-3 ${roleConfig.color}`} />
                        <SelectValue />
                      </div>
                    </SelectTrigger>
                    <SelectContent className="bg-zinc-900 border-zinc-800">
                      {Object.entries(ROLE_CONFIG).map(([key, config]) => {
                        const Icon = config.icon;
                        return (
                          <SelectItem key={key} value={key}>
                            <div className="flex items-center gap-2">
                              <Icon className={`w-3 h-3 ${config.color}`} />
                              <span>{config.label}</span>
                            </div>
                          </SelectItem>
                        );
                      })}
                    </SelectContent>
                  </Select>
                ) : (
                  <Badge className={`${roleConfig.bgColor} ${roleConfig.color} text-xs`}>
                    <RoleIcon className="w-3 h-3 mr-1" />
                    {roleConfig.label}
                  </Badge>
                )}

                {canManage && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => removeMember(member.user_id, member.name)}
                    className="p-1.5 h-auto text-zinc-500 hover:text-red-400"
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Leave workspace button for non-owners */}
      {!isOwner && (
        <Button
          variant="outline"
          onClick={leaveWorkspace}
          className="w-full border-zinc-700 text-zinc-400 hover:text-red-400 hover:border-red-500/50"
        >
          <LogOut className="w-4 h-4 mr-2" />
          Leave Workspace
        </Button>
      )}

      {/* Role permissions info */}
      <div className="mt-6 p-4 bg-zinc-800/30 rounded-lg border border-zinc-800">
        <h4 className="text-sm font-medium text-zinc-300 mb-3">Role Permissions</h4>
        <div className="space-y-2">
          {Object.entries(ROLE_CONFIG).map(([key, config]) => {
            const Icon = config.icon;
            return (
              <div key={key} className="flex items-start gap-2">
                <Icon className={`w-4 h-4 mt-0.5 ${config.color}`} />
                <div>
                  <span className="text-xs font-medium text-zinc-300">{config.label}:</span>
                  <span className="text-xs text-zinc-500 ml-1">{config.description}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <ConfirmDlg />
    </div>
  );
}

function InviteByEmailDialog({ workspaceId, open, onOpenChange, onInvited }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("user");
  const [loading, setLoading] = useState(false);

  const handleInvite = async () => {
    if (!email.trim()) {
      toast.error("Please enter an email address");
      return;
    }
    setLoading(true);
    try {
      const res = await api.post(`/workspaces/${workspaceId}/members/invite`, {
        email: email.trim(),
        role
      });
      toast.success(res.data.message);
      setEmail("");
      setRole("user");
      onOpenChange(false);
      onInvited?.();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to invite member");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button size="sm" className="bg-zinc-100 text-zinc-900 hover:bg-zinc-200">
          <UserPlus className="w-4 h-4 mr-1.5" />
          Invite
        </Button>
      </DialogTrigger>
      <DialogContent className="bg-zinc-900 border-zinc-800">
        <DialogHeader>
          <DialogTitle className="text-zinc-100 flex items-center gap-2">
            <Mail className="w-5 h-5" />
            Invite by Email
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 mt-4">
          <div>
            <label className="text-xs text-zinc-400 mb-1 block">Email Address</label>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="colleague@example.com"
              className="bg-zinc-950 border-zinc-800"
            />
          </div>
          <div>
            <label className="text-xs text-zinc-400 mb-1 block">Role</label>
            <Select value={role} onValueChange={setRole}>
              <SelectTrigger className="bg-zinc-950 border-zinc-800">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-zinc-900 border-zinc-800">
                {Object.entries(ROLE_CONFIG).map(([key, config]) => {
                  const Icon = config.icon;
                  return (
                    <SelectItem key={key} value={key}>
                      <div className="flex items-center gap-2">
                        <Icon className={`w-3 h-3 ${config.color}`} />
                        <span>{config.label}</span>
                      </div>
                    </SelectItem>
                  );
                })}
              </SelectContent>
            </Select>
          </div>
          <Button
            onClick={handleInvite}
            disabled={loading || !email.trim()}
            className="w-full bg-zinc-100 text-zinc-900 hover:bg-zinc-200"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Send Invite"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function InviteLinkDialog({ workspaceId, open, onOpenChange }) {
  const [role, setRole] = useState("user");
  const [expiresHours, setExpiresHours] = useState("24");
  const [maxUses, setMaxUses] = useState("");
  const [generatedLink, setGeneratedLink] = useState(null);
  const [loading, setLoading] = useState(false);

  const generateLink = async () => {
    setLoading(true);
    try {
      const res = await api.post(`/workspaces/${workspaceId}/invite-link`, {
        role,
        expires_hours: expiresHours && expiresHours !== "never" ? parseInt(expiresHours) : null,
        max_uses: maxUses ? parseInt(maxUses) : null
      });
      const fullLink = `${window.location.origin}/invite/${res.data.link_code}`;
      setGeneratedLink(fullLink);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to generate link");
    } finally {
      setLoading(false);
    }
  };

  const copyLink = () => {
    navigator.clipboard.writeText(generatedLink);
    toast.success("Link copied to clipboard");
  };

  const resetForm = () => {
    setGeneratedLink(null);
    setRole("user");
    setExpiresHours("24");
    setMaxUses("");
  };

  return (
    <>
    <Dialog open={open} onOpenChange={(v) => { onOpenChange(v); if (!v) resetForm(); }}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="border-zinc-700 text-zinc-300">
          <Link className="w-4 h-4 mr-1.5" />
          Get Link
        </Button>
      </DialogTrigger>
      <DialogContent className="bg-zinc-900 border-zinc-800">
        <DialogHeader>
          <DialogTitle className="text-zinc-100 flex items-center gap-2">
            <Link className="w-5 h-5" />
            Create Invite Link
          </DialogTitle>
        </DialogHeader>
        
        {generatedLink ? (
          <div className="space-y-4 mt-4">
            <div className="p-3 bg-zinc-950 rounded-lg border border-zinc-800">
              <p className="text-xs text-zinc-400 mb-2">Share this link:</p>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={generatedLink}
                  readOnly
                  className="flex-1 bg-transparent text-sm text-zinc-300 outline-none"
                />
                <Button size="sm" onClick={copyLink} className="bg-zinc-800 hover:bg-zinc-700">
                  <Copy className="w-4 h-4" />
                </Button>
              </div>
            </div>
            <Button
              variant="outline"
              onClick={resetForm}
              className="w-full border-zinc-700 text-zinc-300"
            >
              Create Another Link
            </Button>
          </div>
        ) : (
          <div className="space-y-4 mt-4">
            <div>
              <label className="text-xs text-zinc-400 mb-1 block">Role for invitees</label>
              <Select value={role} onValueChange={setRole}>
                <SelectTrigger className="bg-zinc-950 border-zinc-800">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-zinc-900 border-zinc-800">
                  <SelectItem value="user">
                    <div className="flex items-center gap-2">
                      <User className="w-3 h-3 text-blue-400" />
                      User
                    </div>
                  </SelectItem>
                  <SelectItem value="observer">
                    <div className="flex items-center gap-2">
                      <Eye className="w-3 h-3 text-zinc-400" />
                      Observer
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Expires in</label>
                <Select value={expiresHours} onValueChange={setExpiresHours}>
                  <SelectTrigger className="bg-zinc-950 border-zinc-800">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-zinc-900 border-zinc-800">
                    <SelectItem value="1">1 hour</SelectItem>
                    <SelectItem value="24">24 hours</SelectItem>
                    <SelectItem value="168">7 days</SelectItem>
                    <SelectItem value="never">Never</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Max uses</label>
                <Input
                  type="number"
                  value={maxUses}
                  onChange={(e) => setMaxUses(e.target.value)}
                  placeholder="Unlimited"
                  className="bg-zinc-950 border-zinc-800"
                />
              </div>
            </div>
            <Button
              onClick={generateLink}
              disabled={loading}
              className="w-full bg-zinc-100 text-zinc-900 hover:bg-zinc-200"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Generate Link"}
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
    </>
    );
}
