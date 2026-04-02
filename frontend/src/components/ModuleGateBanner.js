import { Shield, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * ModuleGateBanner — shows when a feature is disabled by module config.
 * Displayed instead of the feature panel content.
 */
export function ModuleGateBanner({ moduleName, moduleId, onActivate }) {
  return (
    <div className="flex-1 flex items-center justify-center p-8" data-testid={`module-gate-${moduleId}`}>
      <div className="text-center max-w-md space-y-4">
        <div className="w-16 h-16 rounded-2xl bg-zinc-800 flex items-center justify-center mx-auto">
          <Lock className="w-8 h-8 text-zinc-600" />
        </div>
        <h2 className="text-lg font-semibold text-zinc-200">{moduleName} is not enabled</h2>
        <p className="text-sm text-zinc-500">
          This feature requires the <span className="text-cyan-400 font-medium">{moduleName}</span> module.
          Activate it in your workspace settings to unlock this feature.
        </p>
        {onActivate ? (
          <Button onClick={onActivate} className="bg-cyan-600 hover:bg-cyan-700">
            <Shield className="w-4 h-4 mr-2" /> Activate {moduleName}
          </Button>
        ) : (
          <p className="text-xs text-zinc-600">Contact your workspace admin to enable this module.</p>
        )}
      </div>
    </div>
  );
}
