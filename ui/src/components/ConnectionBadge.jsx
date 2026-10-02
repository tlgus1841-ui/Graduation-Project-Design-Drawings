const STYLES = {
  CONNECTING: { dot: "bg-amber-400 animate-pulse", text: "text-amber-300", ring: "ring-amber-400/40", label: "CONNECTING" },
  CONNECTED: { dot: "bg-emerald-400", text: "text-emerald-300", ring: "ring-emerald-400/40", label: "CONNECTED" },
  RECONNECTING: { dot: "bg-amber-400 animate-pulse", text: "text-amber-300", ring: "ring-amber-400/40", label: "RECONNECTING" },
  DISCONNECTED: { dot: "bg-red-500", text: "text-red-300", ring: "ring-red-500/40", label: "DISCONNECTED" },
};

// WebSocket connection badge (spec §5): CONNECTED / RECONNECTING / DISCONNECTED.
export default function ConnectionBadge({ status, retries }) {
  const s = STYLES[status] ?? STYLES.DISCONNECTED;
  return (
    <span
      data-testid="connection-badge"
      data-status={status}
      className={`inline-flex items-center gap-2 rounded-full bg-slate-800 px-3 py-1 text-xs font-semibold tracking-wide ring-1 ${s.ring} ${s.text}`}
      title={retries > 0 ? `재연결 시도 ${retries}회` : undefined}
    >
      <span className={`h-2 w-2 rounded-full ${s.dot}`} />
      WS {s.label}
      {status !== "CONNECTED" && retries > 0 && <span className="font-normal text-slate-400">· {retries}</span>}
    </span>
  );
}
