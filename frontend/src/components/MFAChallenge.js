import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ShieldCheck, Loader2, ArrowLeft, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/App";

export default function MFAChallenge({ email, challengeToken, onSuccess, onBack }) {
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [useBackup, setUseBackup] = useState(false);

  const handleVerify = async () => {
    if (!code) return;
    setLoading(true);
    setError("");
    try {
      const res = await api.post("/auth/mfa/verify", {
        code: useBackup ? code.trim().toUpperCase() : code,
        email,
        challenge_token: challengeToken,
      });
      if (res.data?.backup_warning) {
        toast.warning(res.data.backup_warning);
      }
      toast.success("Verified!");
      onSuccess(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Invalid code");
    }
    setLoading(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") handleVerify();
  };

  return (
    <div className="w-full max-w-sm mx-auto space-y-6" data-testid="mfa-challenge">
      <div className="text-center space-y-2">
        <div className="w-12 h-12 mx-auto rounded-full bg-emerald-500/10 flex items-center justify-center">
          <ShieldCheck className="w-6 h-6 text-emerald-400" />
        </div>
        <h2 className="text-lg font-semibold text-zinc-100" style={{ fontFamily: "Syne, sans-serif" }}>Two-Factor Verification</h2>
        <p className="text-xs text-zinc-500">
          {useBackup
            ? "Enter one of your backup codes"
            : "Enter the 6-digit code from your authenticator app"
          }
        </p>
        {useBackup && (
          <p className="text-[11px] text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded px-3 py-2" data-testid="mfa-backup-warning">
            Backup codes are single-use. After you sign in, regenerate them if you are running low.
          </p>
        )}
      </div>

      <div className="space-y-3">
        <Input
          value={code}
          onChange={e => {
            const val = useBackup ? e.target.value.toUpperCase() : e.target.value.replace(/\D/g, "").slice(0, 6);
            setCode(val);
          }}
          onKeyDown={handleKeyDown}
          placeholder={useBackup ? "BACKUP CODE" : "000000"}
          className="bg-zinc-800 border-zinc-700 text-zinc-200 text-center font-mono text-lg tracking-[0.3em] h-12"
          maxLength={useBackup ? 10 : 6}
          autoFocus
          data-testid="mfa-challenge-code-input"
        />

        {error && (
          <div className="flex items-center gap-2 text-xs text-red-400 bg-red-500/10 rounded px-3 py-2">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
            {error}
          </div>
        )}

        <Button
          onClick={handleVerify}
          disabled={loading || (!useBackup && code.length < 6) || (useBackup && !code)}
          className="w-full bg-emerald-600 hover:bg-emerald-700 text-white h-10"
          data-testid="mfa-challenge-verify-btn"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Verify"}
        </Button>

        <div className="flex items-center justify-between">
          <button
            onClick={() => { setUseBackup(!useBackup); setCode(""); setError(""); }}
            className="text-[11px] text-zinc-500 hover:text-zinc-300 transition-colors"
            data-testid="mfa-toggle-backup"
          >
            {useBackup ? "Use authenticator code" : "Use a backup code"}
          </button>

          {onBack && (
            <button onClick={onBack} className="text-[11px] text-zinc-500 hover:text-zinc-300 flex items-center gap-1">
              <ArrowLeft className="w-3 h-3" /> Back to login
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
