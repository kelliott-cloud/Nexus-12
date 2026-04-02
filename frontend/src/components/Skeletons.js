/**
 * Loading Skeleton Components — Shimmer placeholders for data-loading states.
 * Replace spinners with layout-aware skeletons for better perceived performance.
 */

export function SkeletonLine({ width = "100%", height = "12px", className = "" }) {
  return (
    <div className={`bg-zinc-800/60 rounded animate-pulse ${className}`} style={{ width, height }} />
  );
}

export function SkeletonCard({ className = "" }) {
  return (
    <div className={`p-4 rounded-xl border border-zinc-800/40 space-y-3 ${className}`}>
      <SkeletonLine width="60%" height="16px" />
      <SkeletonLine width="90%" />
      <SkeletonLine width="40%" />
    </div>
  );
}

export function SkeletonChatMessage({ isOwn = false }) {
  return (
    <div className={`flex gap-3 px-4 py-2 ${isOwn ? "flex-row-reverse" : ""}`}>
      <div className="w-8 h-8 rounded-lg bg-zinc-800/60 animate-pulse flex-shrink-0" />
      <div className="space-y-1.5 flex-1" style={{ maxWidth: "60%" }}>
        <SkeletonLine width="80px" height="10px" />
        <SkeletonLine width="100%" height="14px" />
        <SkeletonLine width="70%" height="14px" />
      </div>
    </div>
  );
}

export function SkeletonChatList({ count = 5 }) {
  return (
    <div className="space-y-1">
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonChatMessage key={`skel-chat-${i}`} isOwn={i % 3 === 0} />
      ))}
    </div>
  );
}

export function SkeletonSidebarChannels({ count = 4 }) {
  return (
    <div className="space-y-1 px-2">
      {Array.from({ length: count }).map((_, i) => (
        <div key={`skel-ch-${i}`} className="flex items-center gap-2 px-3 py-2">
          <div className="w-3.5 h-3.5 rounded bg-zinc-800/60 animate-pulse" />
          <SkeletonLine width={`${50 + Math.random() * 40}%`} height="12px" />
        </div>
      ))}
    </div>
  );
}

export function SkeletonProjectCard() {
  return (
    <div className="p-3 rounded-lg border border-zinc-800/40 space-y-2">
      <div className="flex items-center justify-between">
        <SkeletonLine width="120px" height="14px" />
        <SkeletonLine width="50px" height="18px" className="rounded-full" />
      </div>
      <SkeletonLine width="60px" height="10px" />
    </div>
  );
}

export function SkeletonDashboardStats() {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={`skel-stat-${i}`} className="p-3 rounded-lg bg-zinc-900/80 border border-zinc-800/40 space-y-2">
          <SkeletonLine width="40px" height="24px" />
          <SkeletonLine width="80px" height="10px" />
        </div>
      ))}
    </div>
  );
}

export function SkeletonTable({ rows = 5, cols = 4 }) {
  return (
    <div className="rounded-lg border border-zinc-800/40 overflow-hidden">
      <div className="grid gap-2 px-4 py-2 bg-zinc-900/50" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
        {Array.from({ length: cols }).map((_, i) => <SkeletonLine key={`skel-th-${i}`} width="60%" height="10px" />)}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={`skel-tr-${r}`} className="grid gap-2 px-4 py-2.5 border-t border-zinc-800/30" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
          {Array.from({ length: cols }).map((_, c) => <SkeletonLine key={`skel-td-${r}-${c}`} width={`${40 + Math.random() * 50}%`} height="12px" />)}
        </div>
      ))}
    </div>
  );
}
