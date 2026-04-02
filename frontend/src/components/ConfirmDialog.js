import { useState, useContext, createContext, useCallback } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { AlertTriangle } from "lucide-react";

const ConfirmContext = createContext(null);

export function ConfirmProvider({ children }) {
  const [state, setState] = useState({ open: false, title: "", message: "", resolve: null });

  const confirm = useCallback((title, message) => new Promise((resolve) => {
    setState({ open: true, title, message, resolve });
  }), []);

  const handleClose = (result) => {
    state.resolve?.(result);
    setState({ open: false, title: "", message: "", resolve: null });
  };

  return (
    <ConfirmContext.Provider value={{ confirm }}>
      {children}
      <Dialog open={state.open} onOpenChange={() => handleClose(false)}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-md">
          <DialogHeader>
            <DialogTitle className="text-zinc-100 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-amber-400" />
              {state.title}
            </DialogTitle>
            <DialogDescription className="text-zinc-400">{state.message}</DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2 mt-4">
            <Button variant="ghost" onClick={() => handleClose(false)} className="text-zinc-400">Cancel</Button>
            <Button onClick={() => handleClose(true)} className="bg-red-600 hover:bg-red-700 text-white">Confirm</Button>
          </div>
        </DialogContent>
      </Dialog>
    </ConfirmContext.Provider>
  );
}

export function useConfirm() {
  const ctx = useContext(ConfirmContext);
  // When global ConfirmProvider is active, use it (ConfirmDialog is a no-op)
  if (ctx) {
    return { confirm: ctx.confirm, ConfirmDialog: () => null };
  }
  // This should not happen if ConfirmProvider wraps the app
  // But return a safe fallback
  return {
    confirm: async (title, message) => {
      // eslint-disable-next-line no-restricted-globals
      return confirm(`${title}\n\n${message}`);
    },
    ConfirmDialog: () => null,
  };
}
