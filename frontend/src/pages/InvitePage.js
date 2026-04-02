import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Users, Loader2, CheckCircle, XCircle, LogIn } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { api } from "@/App";

export default function InvitePage({ user }) {
  const { linkCode } = useParams();
  const navigate = useNavigate();
  const [inviteInfo, setInviteInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [joining, setJoining] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchInviteInfo();
  }, [linkCode]);

  const fetchInviteInfo = async () => {
    try {
      const res = await api.get(`/invites/${linkCode}`);
      setInviteInfo(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Invalid or expired invite link");
    } finally {
      setLoading(false);
    }
  };

  const handleJoin = async () => {
    setJoining(true);
    try {
      const res = await api.post(`/invites/${linkCode}/join`);
      toast.success("Successfully joined workspace!");
      navigate(`/workspace/${res.data.workspace_id}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to join workspace");
    } finally {
      setJoining(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-zinc-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="max-w-md w-full mx-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 text-center">
            <XCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
            <h1 className="text-xl font-semibold text-zinc-100 mb-2">Invalid Invite</h1>
            <p className="text-zinc-400 mb-6">{error}</p>
            <Button
              onClick={() => navigate("/dashboard")}
              className="bg-zinc-100 text-zinc-900 hover:bg-zinc-200"
            >
              Go to Dashboard
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="max-w-md w-full mx-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 text-center">
            <Users className="w-16 h-16 text-blue-500 mx-auto mb-4" />
            <h1 className="text-xl font-semibold text-zinc-100 mb-2">
              You've been invited to join
            </h1>
            <h2 className="text-2xl font-bold text-zinc-100 mb-2">
              {inviteInfo?.workspace_name}
            </h2>
            {inviteInfo?.workspace_description && (
              <p className="text-zinc-400 mb-4">{inviteInfo.workspace_description}</p>
            )}
            <p className="text-sm text-zinc-500 mb-6">
              Sign in to accept this invitation
            </p>
            <Button
              onClick={() => navigate(`/?redirect=/invite/${linkCode}`)}
              className="bg-zinc-100 text-zinc-900 hover:bg-zinc-200 gap-2"
            >
              <LogIn className="w-4 h-4" />
              Sign In to Join
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (inviteInfo?.expired) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="max-w-md w-full mx-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 text-center">
            <XCircle className="w-16 h-16 text-amber-500 mx-auto mb-4" />
            <h1 className="text-xl font-semibold text-zinc-100 mb-2">Invite Expired</h1>
            <p className="text-zinc-400 mb-6">
              This invite link has expired. Ask the workspace admin for a new invite.
            </p>
            <Button
              onClick={() => navigate("/dashboard")}
              className="bg-zinc-100 text-zinc-900 hover:bg-zinc-200"
            >
              Go to Dashboard
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (inviteInfo?.is_member) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="max-w-md w-full mx-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 text-center">
            <CheckCircle className="w-16 h-16 text-emerald-500 mx-auto mb-4" />
            <h1 className="text-xl font-semibold text-zinc-100 mb-2">
              Already a Member
            </h1>
            <p className="text-zinc-400 mb-6">
              You're already a member of {inviteInfo.workspace_name}
            </p>
            <Button
              onClick={() => navigate("/dashboard")}
              className="bg-zinc-100 text-zinc-900 hover:bg-zinc-200"
            >
              Go to Dashboard
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
      <div className="max-w-md w-full mx-4">
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 text-center">
          <Users className="w-16 h-16 text-blue-500 mx-auto mb-4" />
          <h1 className="text-xl font-semibold text-zinc-100 mb-2">
            You've been invited to join
          </h1>
          <h2 className="text-2xl font-bold text-zinc-100 mb-2">
            {inviteInfo?.workspace_name}
          </h2>
          {inviteInfo?.workspace_description && (
            <p className="text-zinc-400 mb-4">{inviteInfo.workspace_description}</p>
          )}
          <div className="inline-block px-3 py-1 bg-zinc-800 rounded-full text-sm text-zinc-300 mb-6">
            You'll join as: <span className="font-medium capitalize">{inviteInfo?.role}</span>
          </div>
          <div className="space-y-3">
            <Button
              onClick={handleJoin}
              disabled={joining}
              className="w-full bg-zinc-100 text-zinc-900 hover:bg-zinc-200"
            >
              {joining ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                "Accept Invite"
              )}
            </Button>
            <Button
              variant="outline"
              onClick={() => navigate("/dashboard")}
              className="w-full border-zinc-700 text-zinc-300"
            >
              Decline
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
