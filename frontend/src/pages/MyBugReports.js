import { useState, useEffect } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { useNavigate } from "react-router-dom";
import { Bug, ArrowLeft, Loader2, CheckCircle, AlertTriangle, Clock, XCircle, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/App";
import BugReportModal from "@/components/BugReportModal";
import { useLanguage } from "@/contexts/LanguageContext";

const STATUS_CONFIG = {
  open: { label: "Open", color: "bg-blue-500/20 text-blue-400", icon: AlertTriangle },
  in_progress: { label: "In Progress", color: "bg-amber-500/20 text-amber-400", icon: Clock },
  resolved: { label: "Resolved", color: "bg-emerald-500/20 text-emerald-400", icon: CheckCircle },
  closed: { label: "Closed", color: "bg-zinc-500/20 text-zinc-400", icon: XCircle },
  wont_fix: { label: "Won't Fix", color: "bg-red-500/20 text-red-400", icon: XCircle },
};

const SEVERITY_CONFIG = {
  low: "text-zinc-400",
  medium: "text-blue-400",
  high: "text-amber-400",
  critical: "text-red-400",
};

export default function MyBugReports({ user }) {
  const navigate = useNavigate();
  const { t } = useLanguage();
  const [bugs, setBugs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedBug, setSelectedBug] = useState(null);

  useEffect(() => { fetchBugs(); }, []);

  const fetchBugs = async () => {
    try {
      const res = await api.get("/bugs/my-reports");
      setBugs(res.data.bugs || []);
    } catch (err) { handleSilent(err, "MyBugReports:op1"); } finally {
      setLoading(false);
    }
  };

  const formatDate = (iso) => {
    if (!iso) return "";
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit"
    });
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100" data-testid="my-bugs-page">
      <header className="border-b border-zinc-800 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm" onClick={() => navigate("/dashboard")} className="text-zinc-400 hover:text-zinc-100" data-testid="back-to-dashboard-btn">
              <ArrowLeft className="w-4 h-4 mr-2" />
              {t("common.back")}
            </Button>
            <div className="flex items-center gap-2">
              <Bug className="w-5 h-5 text-red-400" />
              <h1 className="text-lg font-semibold" style={{ fontFamily: 'Syne, sans-serif' }}>{t("bugs.myBugReports")}</h1>
            </div>
          </div>
          <BugReportModal
            trigger={
              <Button size="sm" className="bg-zinc-100 text-zinc-900 hover:bg-zinc-200" data-testid="file-new-bug-btn">
                <Plus className="w-4 h-4 mr-2" />
                {t("bugs.fileNewBug")}
              </Button>
            }
            onSubmitted={fetchBugs}
          />
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8">
        {loading ? (
          <div className="flex justify-center py-16">
            <Loader2 className="w-8 h-8 animate-spin text-zinc-400" />
          </div>
        ) : bugs.length === 0 ? (
          <div className="text-center py-16" data-testid="no-bugs-empty">
            <Bug className="w-12 h-12 text-zinc-700 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-zinc-300 mb-2">{t("bugs.noBugs")}</h3>
            <p className="text-sm text-zinc-500 mb-6">{t("bugs.noBugsDesc")}</p>
            <BugReportModal
              trigger={
                <Button className="bg-zinc-100 text-zinc-900 hover:bg-zinc-200">
                  <Plus className="w-4 h-4 mr-2" />
                  File Your First Bug
                </Button>
              }
              onSubmitted={fetchBugs}
            />
          </div>
        ) : (
          <div className="flex gap-6">
            <div className="flex-1 space-y-2">
              <p className="text-sm text-zinc-500 mb-4" data-testid="bug-count">{bugs.length} bug report{bugs.length !== 1 ? "s" : ""}</p>
              {bugs.map((bug) => {
                const statusConf = STATUS_CONFIG[bug.status] || STATUS_CONFIG.open;
                const StatusIcon = statusConf.icon;
                return (
                  <div
                    key={bug.bug_id}
                    onClick={() => setSelectedBug(bug)}
                    className={`p-4 rounded-lg border cursor-pointer transition-colors ${
                      selectedBug?.bug_id === bug.bug_id
                        ? "bg-zinc-800 border-zinc-700"
                        : "bg-zinc-900/50 border-zinc-800 hover:bg-zinc-900"
                    }`}
                    data-testid={`bug-item-${bug.bug_id}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <h4 className="text-sm font-medium text-zinc-200 truncate">{bug.title}</h4>
                        <p className="text-xs text-zinc-500 mt-1">{formatDate(bug.created_at)}</p>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <Badge className={statusConf.color}>
                          <StatusIcon className="w-3 h-3 mr-1" />
                          {statusConf.label}
                        </Badge>
                        <span className={`text-xs capitalize ${SEVERITY_CONFIG[bug.severity] || ""}`}>{bug.severity}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {selectedBug && (
              <div className="w-96 bg-zinc-900 border border-zinc-800 rounded-xl p-5 flex-shrink-0" data-testid="bug-detail-panel">
                <h3 className="text-base font-semibold text-zinc-100 mb-4">{selectedBug.title}</h3>
                <div className="space-y-4">
                  <div className="flex gap-3">
                    <div>
                      <label className="text-[10px] uppercase tracking-wider text-zinc-500">Status</label>
                      <Badge className={`mt-1 block w-fit ${(STATUS_CONFIG[selectedBug.status] || STATUS_CONFIG.open).color}`}>
                        {(STATUS_CONFIG[selectedBug.status] || STATUS_CONFIG.open).label}
                      </Badge>
                    </div>
                    <div>
                      <label className="text-[10px] uppercase tracking-wider text-zinc-500">Severity</label>
                      <p className={`mt-1 text-sm capitalize ${SEVERITY_CONFIG[selectedBug.severity] || ""}`}>{selectedBug.severity}</p>
                    </div>
                    <div>
                      <label className="text-[10px] uppercase tracking-wider text-zinc-500">Category</label>
                      <p className="mt-1 text-sm text-zinc-300 capitalize">{selectedBug.category}</p>
                    </div>
                  </div>
                  <div>
                    <label className="text-[10px] uppercase tracking-wider text-zinc-500">Description</label>
                    <p className="mt-1 text-sm text-zinc-300 bg-zinc-950 p-3 rounded-lg">{selectedBug.description}</p>
                  </div>
                  {selectedBug.steps_to_reproduce && (
                    <div>
                      <label className="text-[10px] uppercase tracking-wider text-zinc-500">Steps to Reproduce</label>
                      <p className="mt-1 text-sm text-zinc-400 bg-zinc-950 p-3 rounded-lg whitespace-pre-wrap">{selectedBug.steps_to_reproduce}</p>
                    </div>
                  )}
                  {selectedBug.expected_behavior && (
                    <div>
                      <label className="text-[10px] uppercase tracking-wider text-zinc-500">Expected</label>
                      <p className="mt-1 text-sm text-zinc-400">{selectedBug.expected_behavior}</p>
                    </div>
                  )}
                  {selectedBug.actual_behavior && (
                    <div>
                      <label className="text-[10px] uppercase tracking-wider text-zinc-500">Actual</label>
                      <p className="mt-1 text-sm text-zinc-400">{selectedBug.actual_behavior}</p>
                    </div>
                  )}
                  <div className="text-xs text-zinc-600 pt-3 border-t border-zinc-800">
                    Filed {formatDate(selectedBug.created_at)}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
