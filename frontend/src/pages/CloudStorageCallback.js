import { useEffect, useState } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { api } from "@/lib/api";

export default function CloudStorageCallback() {
  const [status, setStatus] = useState("processing");
  const [message, setMessage] = useState("Completing connection...");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const state = params.get("state");
    const error = params.get("error");

    if (error) {
      setStatus("error");
      setMessage(`OAuth error: ${error}`);
      return;
    }
    if (!code || !state) {
      setStatus("error");
      setMessage("Missing authorization code. Please try again.");
      return;
    }

    (async () => {
      try {
        const isSocial = window.location.pathname.startsWith("/social");
        const callbackEndpoint = isSocial ? "/social/callback" : "/cloud-storage/callback";
        const redirectUri = `${window.location.origin}${window.location.pathname}`;
        await api.post(callbackEndpoint, { code, state, redirect_uri: redirectUri });
        setStatus("success");
        setMessage("Connected successfully! You can close this window.");
        setTimeout(() => { try { window.close(); } catch (err) { handleSilent(err, "CloudStorageCallback:op1"); } }, 2000);
      } catch (err) {
        setStatus("error");
        setMessage(err.response?.data?.detail || "Connection failed. Please try again.");
      }
    })();
  }, []);

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center" data-testid="cloud-storage-callback">
      <div className="text-center max-w-sm p-8">
        {status === "processing" && (
          <div className="w-8 h-8 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        )}
        {status === "success" && (
          <div className="w-12 h-12 rounded-full bg-emerald-500/20 flex items-center justify-center mx-auto mb-4">
            <svg className="w-6 h-6 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
          </div>
        )}
        {status === "error" && (
          <div className="w-12 h-12 rounded-full bg-red-500/20 flex items-center justify-center mx-auto mb-4">
            <svg className="w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
          </div>
        )}
        <p className="text-sm text-zinc-300">{message}</p>
        {status === "error" && (
          <button onClick={() => window.close()} className="mt-4 px-4 py-2 bg-zinc-800 text-zinc-300 rounded-lg text-sm hover:bg-zinc-700">Close</button>
        )}
      </div>
    </div>
  );
}
