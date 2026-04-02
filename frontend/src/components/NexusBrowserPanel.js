import { useState, useEffect, useCallback, useRef } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { api } from "@/App";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { toast } from "sonner";
import {
  Globe, ArrowLeft, ArrowRight, RotateCw, X, AlertTriangle,
  CheckCircle2, Loader2, ExternalLink, Home, Lock, Star,
  ZoomIn, ZoomOut, Search, BookmarkPlus, Clock, ChevronDown,
} from "lucide-react";

const BOOKMARKS = [
  { name: "Google", url: "https://www.google.com" },
  { name: "GitHub", url: "https://github.com" },
  { name: "Stack Overflow", url: "https://stackoverflow.com" },
  { name: "MDN Docs", url: "https://developer.mozilla.org" },
  { name: "NPM", url: "https://www.npmjs.com" },
];

export default function NexusBrowserPanel({ channelId, isOpen, onClose }) {
  const [urlInput, setUrlInput] = useState("https://www.google.com");
  const [currentUrl, setCurrentUrl] = useState("");
  const [screenshot, setScreenshot] = useState(null);
  const [pageTitle, setPageTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionActive, setSessionActive] = useState(false);
  const [helpRequested, setHelpRequested] = useState(false);
  const [helpMessage, setHelpMessage] = useState("");
  const [history, setHistory] = useState([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [zoom, setZoom] = useState(100);
  const [isSecure, setIsSecure] = useState(false);
  const [urlSuggestions, setUrlSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [bookmarks, setBookmarks] = useState(() => {
    try { return JSON.parse(localStorage.getItem("nexus_browser_bookmarks") || "null") || BOOKMARKS; }
    catch (err) { return BOOKMARKS; }
  });
  const [showBookmarkBar, setShowBookmarkBar] = useState(true);
  const urlInputRef = useRef(null);
  const pollRef = useRef(null);

  // Poll for screenshot updates
  const pollScreenshot = useCallback(async () => {
    if (!channelId || !sessionActive) return;
    try {
      const [ssRes, statusRes] = await Promise.all([
        api.get(`/channels/${channelId}/browser/screenshot`),
        api.get(`/channels/${channelId}/browser/status`),
      ]);
      if (ssRes.data?.screenshot) {
        setScreenshot(ssRes.data.screenshot);
        if (ssRes.data.title) setPageTitle(ssRes.data.title);
        if (ssRes.data.url) {
          setCurrentUrl(ssRes.data.url);
          setIsSecure(ssRes.data.url.startsWith("https://"));
        }
      }
      if (statusRes.data?.session) {
        setHelpRequested(statusRes.data.session.help_requested || false);
        setHelpMessage(statusRes.data.session.help_message || "");
      }
    } catch (err) { handleSilent(err, "NexusBrowser:op1"); }
  }, [channelId, sessionActive]);

  useEffect(() => {
    if (!isOpen || !sessionActive) return;
    pollRef.current = setInterval(pollScreenshot, 2000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [isOpen, sessionActive, pollScreenshot]);

  // Check if session exists on open
  useEffect(() => {
    if (!isOpen || !channelId) return;
    api.get(`/channels/${channelId}/browser/status`).then(res => {
      if (res.data?.active && res.data?.session) {
        setSessionActive(true);
        setCurrentUrl(res.data.session.current_url || "");
        setUrlInput(res.data.session.current_url || "https://www.google.com");
        // Fetch initial screenshot
        api.get(`/channels/${channelId}/browser/screenshot`).then(ssRes => {
          if (ssRes.data?.screenshot) setScreenshot(ssRes.data.screenshot);
          if (ssRes.data?.title) setPageTitle(ssRes.data.title);
        }).catch(() => {});
      }
    }).catch(() => {});
  }, [isOpen, channelId]);

  const doNavigate = async (targetUrl) => {
    if (!targetUrl?.trim()) return;
    // Auto-add https:// if no protocol
    let url = targetUrl.trim();
    if (!/^https?:\/\//i.test(url)) {
      if (url.includes(".") && !url.includes(" ")) {
        url = "https://" + url;
      } else {
        url = `https://www.google.com/search?q=${encodeURIComponent(url)}`;
      }
    }
    setLoading(true);
    setShowSuggestions(false);
    try {
      let res;
      if (!sessionActive) {
        res = await api.post(`/channels/${channelId}/browser/open`, { url });
        setSessionActive(true);
      } else {
        res = await api.post(`/channels/${channelId}/browser/navigate`, { url });
      }
      if (res.data?.error) {
        if (res.data?.available === false) {
          toast.error("Nexus Browser is not available on this server. Playwright Firefox needs to be installed.");
          setSessionActive(false);
        } else {
          toast.error(res.data.error);
        }
      } else {
        const newUrl = res.data?.url || url;
        setCurrentUrl(newUrl);
        setUrlInput(newUrl);
        setIsSecure(newUrl.startsWith("https://"));
        if (res.data?.screenshot) setScreenshot(res.data.screenshot);
        if (res.data?.title) setPageTitle(res.data.title || "");
        // Update history
        const newHistory = [...history.slice(0, historyIndex + 1), newUrl];
        setHistory(newHistory);
        setHistoryIndex(newHistory.length - 1);
        // Save to URL history for autocomplete
        const hist = JSON.parse(localStorage.getItem("nexus_url_history") || "[]");
        if (!hist.includes(newUrl)) {
          hist.unshift(newUrl);
          localStorage.setItem("nexus_url_history", JSON.stringify(hist.slice(0, 50)));
        }
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || "Navigation failed");
    }
    setLoading(false);
  };

  const goBack = () => {
    if (historyIndex > 0) {
      const newIdx = historyIndex - 1;
      setHistoryIndex(newIdx);
      doNavigate(history[newIdx]);
    }
  };

  const goForward = () => {
    if (historyIndex < history.length - 1) {
      const newIdx = historyIndex + 1;
      setHistoryIndex(newIdx);
      doNavigate(history[newIdx]);
    }
  };

  const refresh = () => { if (currentUrl) doNavigate(currentUrl); };

  const goHome = () => doNavigate("https://www.google.com");

  const closeBrowser = async () => {
    try { await api.post(`/channels/${channelId}/browser/close`); } catch (err) { handleSilent(err, "NexusBrowser:op2"); }
    setSessionActive(false);
    setScreenshot(null);
    setCurrentUrl("");
    setPageTitle("");
    setHistory([]);
    setHistoryIndex(-1);
  };

  const resolveHelp = async () => {
    try {
      await api.post(`/channels/${channelId}/browser/help-resolve`);
      setHelpRequested(false);
      setHelpMessage("");
      toast.success("Help resolved — agents can continue");
    } catch (err) { handleSilent(err, "NexusBrowser:op3"); }
  };

  const addBookmark = () => {
    if (!currentUrl || !pageTitle) return;
    const updated = [...bookmarks, { name: pageTitle.substring(0, 30), url: currentUrl }];
    setBookmarks(updated);
    localStorage.setItem("nexus_browser_bookmarks", JSON.stringify(updated));
    toast.success("Bookmark added");
  };

  const removeBookmark = (idx) => {
    const updated = bookmarks.filter((_, i) => i !== idx);
    setBookmarks(updated);
    localStorage.setItem("nexus_browser_bookmarks", JSON.stringify(updated));
  };

  // URL autocomplete
  const handleUrlChange = (val) => {
    setUrlInput(val);
    if (val.length > 1) {
      const hist = JSON.parse(localStorage.getItem("nexus_url_history") || "[]");
      const bk = bookmarks.map(b => b.url);
      const all = [...new Set([...bk, ...hist])];
      const matches = all.filter(u => u.toLowerCase().includes(val.toLowerCase())).slice(0, 6);
      setUrlSuggestions(matches);
      setShowSuggestions(matches.length > 0);
    } else {
      setShowSuggestions(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="flex-1 flex flex-col border-l border-zinc-800/60 bg-zinc-950 min-w-[420px]" data-testid="nexus-browser-panel">
      {/* Title bar */}
      <div className="flex items-center gap-2 px-3 py-1.5 border-b border-zinc-800/50 bg-zinc-900/70 flex-shrink-0">
        <Globe className="w-4 h-4 text-orange-400 flex-shrink-0" />
        <span className="text-[11px] font-bold text-zinc-300 tracking-wide" style={{ fontFamily: "Syne, sans-serif" }}>NEXUS BROWSER</span>
        <Badge className="bg-orange-500/15 text-orange-400 text-[8px] border border-orange-500/20">Firefox</Badge>
        {sessionActive && <span className="text-[9px] text-zinc-600 truncate flex-1">{pageTitle}</span>}
        <div className="flex items-center gap-0.5 ml-auto">
          {sessionActive && (
            <button onClick={closeBrowser} className="p-1 text-zinc-600 hover:text-red-400" title="Close browser" data-testid="close-browser-session">
              <X className="w-3 h-3" />
            </button>
          )}
          <button onClick={onClose} className="p-1 text-zinc-600 hover:text-zinc-300" title="Hide panel" data-testid="hide-browser-panel">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Navigation bar */}
      <div className="flex items-center gap-1.5 px-2 py-1 border-b border-zinc-800/40 bg-zinc-900/40 flex-shrink-0">
        <button onClick={goBack} disabled={historyIndex <= 0} className="p-1 rounded text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 disabled:opacity-30" title="Back" data-testid="browser-back">
          <ArrowLeft className="w-3.5 h-3.5" />
        </button>
        <button onClick={goForward} disabled={historyIndex >= history.length - 1} className="p-1 rounded text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 disabled:opacity-30" title="Forward" data-testid="browser-forward">
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
        <button onClick={refresh} className="p-1 rounded text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800" title="Refresh" data-testid="browser-refresh">
          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RotateCw className="w-3.5 h-3.5" />}
        </button>
        <button onClick={goHome} className="p-1 rounded text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800" title="Home" data-testid="browser-home">
          <Home className="w-3.5 h-3.5" />
        </button>

        {/* URL bar with autocomplete */}
        <div className="flex-1 relative">
          <div className="flex items-center bg-zinc-800/80 rounded-md border border-zinc-700/50 focus-within:border-orange-500/40 px-2">
            {isSecure ? <Lock className="w-3 h-3 text-emerald-400 flex-shrink-0 mr-1" /> : <Globe className="w-3 h-3 text-zinc-500 flex-shrink-0 mr-1" />}
            <form onSubmit={(e) => { e.preventDefault(); doNavigate(urlInput); }} className="flex-1">
              <input
                ref={urlInputRef}
                value={urlInput}
                onChange={(e) => handleUrlChange(e.target.value)}
                onFocus={() => { if (urlInput) handleUrlChange(urlInput); urlInputRef.current?.select(); }}
                onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
                placeholder="Search or enter URL"
                className="w-full bg-transparent text-[11px] text-zinc-200 placeholder:text-zinc-600 py-1 focus:outline-none"
                data-testid="browser-url-input"
              />
            </form>
          </div>
          {/* Autocomplete dropdown */}
          {showSuggestions && (
            <div className="absolute top-full left-0 right-0 mt-0.5 bg-zinc-900 border border-zinc-800 rounded-md shadow-xl z-50 overflow-hidden" data-testid="url-suggestions">
              {urlSuggestions.map((s, i) => (
                <button key={i} onMouseDown={() => { setUrlInput(s); setShowSuggestions(false); doNavigate(s); }}
                  className="w-full text-left px-3 py-1.5 text-[10px] text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 flex items-center gap-2 truncate">
                  <Clock className="w-2.5 h-2.5 text-zinc-600 flex-shrink-0" />
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Action buttons */}
        <button onClick={addBookmark} className="p-1 rounded text-zinc-500 hover:text-amber-400 hover:bg-zinc-800" title="Bookmark page" data-testid="browser-bookmark">
          <BookmarkPlus className="w-3.5 h-3.5" />
        </button>
        <div className="flex items-center gap-0.5">
          <button onClick={() => setZoom(z => Math.max(50, z - 10))} className="p-0.5 rounded text-zinc-600 hover:text-zinc-300" title="Zoom out">
            <ZoomOut className="w-3 h-3" />
          </button>
          <span className="text-[9px] text-zinc-600 w-6 text-center">{zoom}%</span>
          <button onClick={() => setZoom(z => Math.min(200, z + 10))} className="p-0.5 rounded text-zinc-600 hover:text-zinc-300" title="Zoom in">
            <ZoomIn className="w-3 h-3" />
          </button>
        </div>
        <a href={currentUrl || "#"} target="_blank" rel="noopener noreferrer" className="p-1 rounded text-zinc-600 hover:text-zinc-300 hover:bg-zinc-800" title="Open in new tab">
          <ExternalLink className="w-3 h-3" />
        </a>
      </div>

      {/* Bookmark bar */}
      {showBookmarkBar && (
        <div className="flex items-center gap-1 px-2 py-0.5 border-b border-zinc-800/30 bg-zinc-900/20 flex-shrink-0 overflow-x-auto" data-testid="bookmark-bar">
          {bookmarks.map((bk, i) => (
            <button key={i} onClick={() => doNavigate(bk.url)} onContextMenu={(e) => { e.preventDefault(); removeBookmark(i); }}
              className="flex items-center gap-1 px-2 py-0.5 rounded text-[9px] text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 flex-shrink-0" title={bk.url}>
              <Star className="w-2.5 h-2.5 text-amber-500/50" />
              {bk.name}
            </button>
          ))}
        </div>
      )}

      {/* Help request banner */}
      {helpRequested && (
        <div className="px-3 py-2 bg-amber-500/10 border-b border-amber-500/30 flex items-center gap-2 flex-shrink-0" data-testid="browser-help-banner">
          <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-xs font-medium text-amber-400">Agent needs your help</p>
            <p className="text-[10px] text-zinc-400">{helpMessage}</p>
          </div>
          <Button size="sm" onClick={resolveHelp} className="h-6 text-[10px] bg-emerald-500 hover:bg-emerald-400 text-white" data-testid="resolve-help-btn">
            <CheckCircle2 className="w-3 h-3 mr-1" /> Resolve
          </Button>
        </div>
      )}

      {/* Browser viewport */}
      <div className="flex-1 overflow-auto bg-zinc-900 flex items-center justify-center relative">
        {!sessionActive ? (
          <div className="text-center p-8 max-w-sm">
            <div className="w-16 h-16 rounded-2xl bg-orange-500/10 border border-orange-500/20 flex items-center justify-center mx-auto mb-4">
              <Globe className="w-8 h-8 text-orange-400" />
            </div>
            <p className="text-base font-semibold text-zinc-300 mb-1" style={{ fontFamily: "Syne, sans-serif" }}>Nexus Browser</p>
            <p className="text-xs text-zinc-500 mb-4">Firefox-based browser for AI agent web interaction</p>
            <div className="space-y-2">
              {BOOKMARKS.slice(0, 4).map((bk, i) => (
                <button key={i} onClick={() => { setUrlInput(bk.url); doNavigate(bk.url); }}
                  className="w-full text-left px-3 py-2 rounded-lg bg-zinc-800/40 border border-zinc-800/30 hover:border-zinc-700 text-xs text-zinc-400 hover:text-zinc-200 transition-colors">
                  <Globe className="w-3 h-3 inline mr-2 text-zinc-600" />{bk.name}
                </button>
              ))}
            </div>
            <p className="text-[10px] text-zinc-700 mt-4">Enter a URL above or click a quick link to start</p>
          </div>
        ) : screenshot ? (
          <img
            src={`data:image/jpeg;base64,${screenshot}`}
            alt={pageTitle || "Browser viewport"}
            className="max-w-full h-auto"
            style={{ transform: `scale(${zoom / 100})`, transformOrigin: "top left" }}
            data-testid="browser-screenshot"
          />
        ) : (
          <div className="text-center p-8">
            <Loader2 className="w-8 h-8 text-orange-400/50 animate-spin mx-auto mb-2" />
            <p className="text-xs text-zinc-600">Loading page...</p>
          </div>
        )}
      </div>

      {/* Status bar */}
      <div className="px-3 py-1 border-t border-zinc-800/40 bg-zinc-900/50 flex items-center gap-2 flex-shrink-0">
        <div className={`w-1.5 h-1.5 rounded-full ${sessionActive ? "bg-emerald-500 animate-pulse" : "bg-zinc-600"}`} />
        <span className="text-[9px] text-zinc-500 truncate flex-1">{sessionActive ? (pageTitle || currentUrl || "Ready") : "No session"}</span>
        {sessionActive && <span className="text-[9px] text-zinc-600">Live • 2s refresh</span>}
        {loading && <Loader2 className="w-3 h-3 text-orange-400 animate-spin" />}
      </div>
    </div>
  );
}
