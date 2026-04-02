import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Shield, ShieldCheck, ShieldOff, Copy, Check, RefreshCw, Loader2, AlertTriangle, Download } from "lucide-react";
import { toast } from "sonner";
import { handleError } from "@/lib/errorHandler";
import { api } from "@/App";

export default function MFASetup() {
  const [mfaStatus, setMfaStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [step, setStep] = useState("idle");
  const [setupData, setSetupData] = useState(null);
  const [verifyCode, setVerifyCode] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [disableCode, setDisableCode] = useState("");
  const [disablePassword, setDisablePassword] = useState("");
  const [disabling, setDisabling] = useState(false);
  const [copied, setCopied] = useState(false);
  const [backupCodes, setBackupCodes] = useState(null);
  const [regenerating, setRegenerating] = useState(false);

  const remainingBackupCount = backupCodes?.length ?? mfaStatus?.backup_codes_remaining ?? 0;

  useEffect(() => { fetchStatus(); }, []);

  const fetchStatus = async () => {
    try {
      const res = await api.get("/auth/mfa/status");
      setMfaStatus(res.data);
    } catch (err) { handleError(err, "MFASetup:status"); }
    setLoading(false);
  };

  const startSetup = async () => {
    setStep("loading");
    try {
      const res = await api.post("/auth/mfa/setup");
      setSetupData(res.data);
      setStep("scan");
    } catch (err) {
      handleError(err, "MFASetup:setup");
      setStep("idle");
    }
  };

  const confirmSetup = async () => {
    if (!verifyCode || verifyCode.length < 6) return;
    setVerifying(true);
    try {
      await api.post("/auth/mfa/setup/confirm", { code: verifyCode });
      toast.success("MFA enabled successfully!");
      setStep("idle");
      setSetupData(null);
      setVerifyCode("");
      fetchStatus();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Invalid code");
    }
    setVerifying(false);
  };

  const disableMFA = async () => {
    if (!disableCode || !disablePassword) return;
    setDisabling(true);
    try {
      await api.post("/auth/mfa/disable", { code: disableCode, password: disablePassword });
      toast.success("MFA disabled");
      setDisableCode("");
      setDisablePassword("");
      setStep("idle");
      fetchStatus();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to disable MFA");
    }
    setDisabling(false);
  };

  const regenerateBackup = async () => {
    setRegenerating(true);
    try {
      const res = await api.post("/auth/mfa/regenerate-backup");
      setBackupCodes(res.data.backup_codes);
      toast.success("New backup codes generated");
    } catch (err) { handleError(err, "MFASetup:regen"); }
    setRegenerating(false);
  };

  const copySecret = () => {
    if (setupData?.secret) {
      navigator.clipboard.writeText(setupData.secret);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const downloadBackupCodes = (codes) => {
    const text = "Nexus Cloud — MFA Backup Codes\n" + "=".repeat(40) + "\n\n" +
      codes.map((c, i) => `${i + 1}. ${c}`).join("\n") +
      "\n\nStore these codes safely. Each can only be used once.";
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "nexus-mfa-backup-codes.txt";
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) return <div className="animate-pulse h-24 bg-zinc-800/40 rounded-xl" />;

  return (
    <div className="p-6 rounded-xl bg-zinc-900/40 border border-zinc-800/60 space-y-4" data-testid="mfa-setup-panel">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="w-4 h-4 text-emerald-400" />
          <h3 className="text-sm font-semibold text-zinc-300">Two-Factor Authentication</h3>
        </div>
        {mfaStatus?.mfa_enabled && (
          <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400">
            <ShieldCheck className="w-3 h-3" /> Enabled
          </span>
        )}
      </div>

      {!mfaStatus?.mfa_enabled && step === "idle" && (
        <div className="space-y-3">
          <p className="text-xs text-zinc-500">Add an extra layer of security to your account using a TOTP authenticator app (Google Authenticator, Authy, 1Password, etc.).</p>
          <Button size="sm" onClick={startSetup} className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs gap-1.5" data-testid="mfa-enable-btn">
            <Shield className="w-3.5 h-3.5" /> Enable MFA
          </Button>
        </div>
      )}

      {step === "loading" && (
        <div className="flex items-center gap-2 py-4">
          <Loader2 className="w-4 h-4 animate-spin text-zinc-500" />
          <span className="text-xs text-zinc-500">Generating setup...</span>
        </div>
      )}

      {step === "scan" && setupData && (
        <div className="space-y-4">
          <p className="text-xs text-zinc-400">Scan this QR code with your authenticator app:</p>
          <div className="flex flex-col sm:flex-row gap-4 items-start">
            <div className="bg-zinc-950 p-2 rounded-lg border border-zinc-800">
              <img src={setupData.qr_code} alt="MFA QR Code" className="w-44 h-44" data-testid="mfa-qr-code" />
            </div>
            <div className="flex-1 space-y-3">
              <div>
                <label className="text-[10px] text-zinc-500 uppercase tracking-wider">Manual entry key</label>
                <div className="flex items-center gap-2 mt-1">
                  <code className="text-xs text-zinc-300 bg-zinc-800 px-2 py-1 rounded font-mono break-all">{setupData.secret}</code>
                  <button onClick={copySecret} className="text-zinc-500 hover:text-zinc-300" data-testid="mfa-copy-secret">
                    {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>

              <div>
                <label className="text-[10px] text-zinc-500 uppercase tracking-wider">Backup codes</label>
                <div className="grid grid-cols-2 gap-1 mt-1">
                  {setupData.backup_codes?.map((code, i) => (
                    <code key={i} className="text-[11px] text-amber-400 bg-zinc-800/80 px-2 py-0.5 rounded font-mono">{code}</code>
                  ))}
                </div>
                <button onClick={() => downloadBackupCodes(setupData.backup_codes)} className="text-[10px] text-zinc-500 hover:text-zinc-300 mt-1.5 flex items-center gap-1" data-testid="mfa-download-backup">
                  <Download className="w-3 h-3" /> Download backup codes
                </button>
              </div>

              <div className="flex items-start gap-1.5 p-2 rounded bg-amber-500/10 border border-amber-500/20">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-500 mt-0.5 shrink-0" />
                <p className="text-[10px] text-amber-400">Save these backup codes now. They won't be shown again.</p>
              </div>

              <div>
                <label className="text-[10px] text-zinc-500 uppercase tracking-wider">Enter code from your app to verify</label>
                <div className="flex items-center gap-2 mt-1">
                  <Input
                    value={verifyCode}
                    onChange={e => setVerifyCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                    placeholder="000000"
                    className="bg-zinc-800 border-zinc-700 text-zinc-200 w-32 font-mono text-center tracking-widest"
                    maxLength={6}
                    data-testid="mfa-verify-code-input"
                  />
                  <Button size="sm" onClick={confirmSetup} disabled={verifying || verifyCode.length < 6} className="bg-emerald-600 hover:bg-emerald-700 text-xs" data-testid="mfa-verify-btn">
                    {verifying ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Verify & Enable"}
                  </Button>
                </div>
              </div>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={() => { setStep("idle"); setSetupData(null); }} className="text-xs text-zinc-500">Cancel</Button>
        </div>
      )}

      {mfaStatus?.mfa_enabled && step === "idle" && (
        <div className="space-y-4">
          <div className="flex items-center gap-4 text-xs text-zinc-400">
            <span>Enabled: {mfaStatus.enabled_at ? new Date(mfaStatus.enabled_at).toLocaleDateString() : "Yes"}</span>
            <span>Backup codes remaining: <strong className={mfaStatus.backup_codes_remaining <= 2 ? "text-amber-400" : "text-zinc-300"}>{mfaStatus.backup_codes_remaining}</strong></span>
          </div>

          <div className="rounded-lg border border-zinc-800/60 bg-zinc-950/50 p-3 space-y-2" data-testid="mfa-recovery-status">
            <div className="flex items-center justify-between text-xs">
              <span className="text-zinc-400">Recovery readiness</span>
              <span className={remainingBackupCount <= 2 ? "text-amber-400" : "text-emerald-400"}>{remainingBackupCount <= 2 ? "Needs attention" : "Healthy"}</span>
            </div>
            <p className="text-[11px] text-zinc-500">Keep at least 3 unused backup codes saved offline so you can still access Nexus if your authenticator app is unavailable.</p>
          </div>

          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={regenerateBackup} disabled={regenerating} className="text-xs gap-1 border-zinc-700" data-testid="mfa-regen-backup-btn">
              {regenerating ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />} New Backup Codes
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setStep("disable")} className="text-xs text-red-400 hover:text-red-300 gap-1" data-testid="mfa-disable-start-btn">
              <ShieldOff className="w-3 h-3" /> Disable MFA
            </Button>
          </div>

          {backupCodes && (
            <div className="space-y-2">
              <p className="text-[10px] text-zinc-500 uppercase tracking-wider">New backup codes (save these now)</p>
              <div className="grid grid-cols-2 gap-1">
                {backupCodes.map((code, i) => (
                  <code key={i} className="text-[11px] text-amber-400 bg-zinc-800/80 px-2 py-0.5 rounded font-mono">{code}</code>
                ))}
              </div>
              <button onClick={() => downloadBackupCodes(backupCodes)} className="text-[10px] text-zinc-500 hover:text-zinc-300 flex items-center gap-1">
                <Download className="w-3 h-3" /> Download
              </button>
            </div>
          )}
        </div>
      )}

      {step === "disable" && (
        <div className="space-y-3 p-3 rounded-lg bg-red-500/5 border border-red-500/20">
          <p className="text-xs text-red-400">To disable MFA, enter your current TOTP code and password:</p>
          <div className="flex flex-col gap-2">
            <Input value={disableCode} onChange={e => setDisableCode(e.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="TOTP Code" className="bg-zinc-800 border-zinc-700 w-40 font-mono" maxLength={6} data-testid="mfa-disable-code" />
            <Input type="password" value={disablePassword} onChange={e => setDisablePassword(e.target.value)} placeholder="Password" className="bg-zinc-800 border-zinc-700 w-60" data-testid="mfa-disable-password" />
          </div>
          <div className="flex gap-2">
            <Button size="sm" onClick={disableMFA} disabled={disabling || !disableCode || !disablePassword} className="bg-red-600 hover:bg-red-700 text-xs" data-testid="mfa-disable-confirm-btn">
              {disabling ? <Loader2 className="w-3 h-3 animate-spin" /> : "Disable MFA"}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setStep("idle")} className="text-xs text-zinc-500">Cancel</Button>
          </div>
        </div>
      )}
    </div>
  );
}
