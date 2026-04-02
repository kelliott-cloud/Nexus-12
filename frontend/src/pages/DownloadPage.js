import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, Monitor, Download, Cpu, Globe, WifiOff, Zap } from "lucide-react";
import { useLanguage } from "@/contexts/LanguageContext";
import { toast } from "sonner";
import { api } from "@/lib/api";

export default function DownloadPage({ user }) {
  const navigate = useNavigate();
  const { t } = useLanguage();

  const handleDownload = (arch) => {
    toast.info(`Downloading Nexus Desktop (${arch === "x64" ? "64-bit" : "32-bit"})...`);
    window.open(`/api/download/desktop/${arch}`, "_blank");
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100" data-testid="download-page">
      <header className="border-b border-zinc-800 px-6 py-4">
        <div className="max-w-4xl mx-auto flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate("/dashboard")} className="text-zinc-400 hover:text-zinc-100" data-testid="back-btn">
            <ArrowLeft className="w-4 h-4 mr-2" />
            {t("common.back")}
          </Button>
          <div className="flex items-center gap-2">
            <Monitor className="w-5 h-5 text-zinc-400" />
            <h1 className="text-lg font-semibold" style={{ fontFamily: 'Syne, sans-serif' }}>{t("download.title")}</h1>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-12">
        <div className="text-center mb-12">
          <div className="w-20 h-20 rounded-2xl bg-zinc-900 border border-zinc-800 flex items-center justify-center mx-auto mb-6">
            <Zap className="w-10 h-10 text-zinc-300" />
          </div>
          <h2 className="text-3xl font-bold mb-3" style={{ fontFamily: 'Syne, sans-serif' }}>{t("download.nexusForWindows")}</h2>
          <p className="text-zinc-500 max-w-md mx-auto">{t("download.description")}</p>
          <Badge className="bg-amber-500/20 text-amber-400 mt-3">{t("download.beta")}</Badge>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-12">
          <div className="p-6 rounded-xl bg-zinc-900/50 border border-zinc-800 hover:border-zinc-700 transition-colors">
            <div className="flex items-center gap-3 mb-4">
              <Cpu className="w-5 h-5 text-zinc-400" />
              <h3 className="font-semibold text-zinc-200">{t("download.win64")}</h3>
              <Badge className="bg-emerald-500/20 text-emerald-400 text-[10px]">{t("download.recommended")}</Badge>
            </div>
            <p className="text-sm text-zinc-500 mb-4">{t("download.win64Desc")}</p>
            <Button onClick={() => handleDownload("x64")} className="w-full bg-zinc-100 text-zinc-900 hover:bg-zinc-200" data-testid="download-win64">
              <Download className="w-4 h-4 mr-2" />
              {t("download.downloadExe")} (64-bit)
            </Button>
          </div>
          <div className="p-6 rounded-xl bg-zinc-900/50 border border-zinc-800 hover:border-zinc-700 transition-colors">
            <div className="flex items-center gap-3 mb-4">
              <Cpu className="w-5 h-5 text-zinc-400" />
              <h3 className="font-semibold text-zinc-200">{t("download.win32")}</h3>
            </div>
            <p className="text-sm text-zinc-500 mb-4">{t("download.win32Desc")}</p>
            <Button onClick={() => handleDownload("ia32")} className="w-full bg-zinc-100 text-zinc-900 hover:bg-zinc-200" data-testid="download-win32">
              <Download className="w-4 h-4 mr-2" />
              {t("download.downloadExe")} (32-bit)
            </Button>
          </div>
        </div>

        <div className="p-4 rounded-lg bg-blue-500/10 border border-blue-500/20 mb-8">
          <p className="text-sm text-blue-300">
            <strong>How to install:</strong> Extract the downloaded ZIP, then run <code className="bg-blue-500/20 px-1.5 py-0.5 rounded text-xs font-mono">Nexus Desktop.exe</code>. Configure your server URL via the <strong>Mode</strong> menu.
          </p>
        </div>

        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-zinc-200" style={{ fontFamily: 'Syne, sans-serif' }}>{t("download.features")}</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="p-4 rounded-lg bg-zinc-900/30 border border-zinc-800/40">
              <Globe className="w-5 h-5 text-emerald-400 mb-2" />
              <h4 className="text-sm font-medium text-zinc-200 mb-1">{t("download.onlineMode")}</h4>
              <p className="text-xs text-zinc-500">{t("download.onlineModeDesc")}</p>
            </div>
            <div className="p-4 rounded-lg bg-zinc-900/30 border border-zinc-800/40">
              <WifiOff className="w-5 h-5 text-blue-400 mb-2" />
              <h4 className="text-sm font-medium text-zinc-200 mb-1">{t("download.offlineMode")}</h4>
              <p className="text-xs text-zinc-500">{t("download.offlineModeDesc")}</p>
            </div>
            <div className="p-4 rounded-lg bg-zinc-900/30 border border-zinc-800/40">
              <Monitor className="w-5 h-5 text-amber-400 mb-2" />
              <h4 className="text-sm font-medium text-zinc-200 mb-1">{t("download.nativeExperience")}</h4>
              <p className="text-xs text-zinc-500">{t("download.nativeExperienceDesc")}</p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
