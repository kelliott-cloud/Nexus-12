import { toast } from "sonner";

let _reportQueue = [];
let _flushTimer = null;

function _flushErrors() {
  if (!_reportQueue.length) return;
  const batch = _reportQueue.splice(0, 10);
  const { api } = require("@/App");
  batch.forEach(e => {
    api.post("/errors/report", e).catch(() => {});
  });
}

function _queueError(report) {
  _reportQueue.push(report);
  if (!_flushTimer) {
    _flushTimer = setTimeout(() => { _flushErrors(); _flushTimer = null; }, 2000);
  }
}

export function handleError(err, context = "unknown") {
  console.error(`[Nexus Error] ${context}:`, err);
  const message = err?.response?.data?.detail || err?.response?.data?.error || err?.response?.data?.message || err?.message || "Something went wrong";
  toast.error(message);
  _queueError({
    message: message,
    status: err?.response?.status,
    stack: (err?.stack || "").split("\n").slice(0, 5).join("\n"),
    source: "frontend",
    component: context,
    url: window.location.pathname,
  });
}

export function handleSilent(err, context = "unknown") {
  console.warn(`[Nexus Warning] ${context}:`, err?.message || err);
}

export function handleCritical(err, context = "unknown") {
  console.error(`[Nexus CRITICAL] ${context}:`, err);
  const message = err?.response?.data?.detail || err?.response?.data?.error || err?.response?.data?.message || err?.message || "A critical error occurred";
  toast.error(message, { duration: 10000 });
  _queueError({
    message: message,
    stack: (err?.stack || "").split("\n").slice(0, 5).join("\n"),
    source: "frontend",
    component: context,
    url: window.location.pathname,
  });
}

export function reportError(message, extra = {}) {
  _queueError({
    message,
    source: "frontend",
    component: extra.component || "manual",
    url: window.location.pathname,
    extra,
  });
}
