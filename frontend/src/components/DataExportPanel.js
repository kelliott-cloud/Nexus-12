import { useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Download, FileJson, FileText, Loader2 } from "lucide-react";

export default function DataExportPanel({ workspaceId }) {
  const [exporting, setExporting] = useState(null);

  const exportData = async (type) => {
    setExporting(type);
    try {
      const endpoints = {
        workspace: `/workspaces/${workspaceId}`,
        channels: `/workspaces/${workspaceId}/channels`,
        agents: `/workspaces/${workspaceId}/agents`,
        projects: `/workspaces/${workspaceId}/projects`,
        tasks: `/workspaces/${workspaceId}/tasks`,
        wiki: `/workspaces/${workspaceId}/wiki`,
      };
      const res = await api.get(endpoints[type]);
      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `nexus_${type}_${workspaceId}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`${type} data exported`);
    } catch (err) {
      toast.error(`Export failed: ${err?.response?.data?.detail || err?.message}`);
    }
    setExporting(null);
  };

  const exportAll = async () => {
    setExporting("all");
    try {
      const types = ["channels", "agents", "projects", "tasks", "wiki"];
      const results = {};
      for (const type of types) {
        try {
          const res = await api.get(`/workspaces/${workspaceId}/${type}`);
          results[type] = res.data;
        } catch { results[type] = []; }
      }
      const wsRes = await api.get(`/workspaces/${workspaceId}`);
      results.workspace = wsRes.data;
      const blob = new Blob([JSON.stringify(results, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `nexus_workspace_${workspaceId}_full_export.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Full workspace exported");
    } catch (err) {
      toast.error(`Export failed: ${err?.message}`);
    }
    setExporting(null);
  };

  const items = [
    { type: "workspace", label: "Workspace Config", icon: FileJson },
    { type: "channels", label: "Channels & Messages", icon: FileText },
    { type: "agents", label: "AI Agents", icon: FileJson },
    { type: "projects", label: "Projects", icon: FileText },
    { type: "tasks", label: "Tasks", icon: FileText },
    { type: "wiki", label: "Wiki Pages", icon: FileText },
  ];

  return (
    <div className="p-6 max-w-2xl mx-auto" data-testid="data-export-panel">
      <h2 className="text-lg font-semibold text-zinc-100 mb-1">Data Export</h2>
      <p className="text-sm text-zinc-500 mb-6">Export your workspace data as JSON files for backup or migration.</p>
      <div className="space-y-2 mb-6">
        {items.map(({ type, label, icon: Icon }) => (
          <div key={type} className="flex items-center justify-between p-3 rounded-lg bg-zinc-900/50 border border-zinc-800/50">
            <div className="flex items-center gap-3">
              <Icon className="w-4 h-4 text-zinc-500" />
              <span className="text-sm text-zinc-300">{label}</span>
            </div>
            <Button size="sm" variant="outline" onClick={() => exportData(type)} disabled={!!exporting}
              className="text-xs border-zinc-700 text-zinc-400 hover:text-zinc-200">
              {exporting === type ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3 mr-1" />}
              Export
            </Button>
          </div>
        ))}
      </div>
      <Button onClick={exportAll} disabled={!!exporting} className="w-full bg-cyan-600 hover:bg-cyan-500 text-white">
        {exporting === "all" ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Download className="w-4 h-4 mr-2" />}
        Export Everything
      </Button>
    </div>
  );
}
