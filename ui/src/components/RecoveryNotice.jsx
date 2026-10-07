import { useEffect, useState } from "react";
import { clockMs } from "../lib/format.js";

const AUTO_CLOSE_MS = 15000;

// Week 11 review item: self-healing completion notice with the full incident timeline (ms).
// Non-blocking dialog in the corner so the operator keeps watching the map while it is open.
export default function RecoveryNotice({ recovery }) {
  const [dismissed, setDismissed] = useState(null);
  const id = recovery?.restoredAt ?? null;

  useEffect(() => {
    if (id == null) return undefined;
    const t = setTimeout(() => setDismissed(id), AUTO_CLOSE_MS);
    return () => clearTimeout(t);
  }, [id]);

  if (id == null || dismissed === id) return null;

  const rows = [
    ["공격 탐지", recovery.detectedAt],
    ["우회 경로 적용", recovery.reroutedAt],
    ["공격 포트 격리", recovery.isolatedAt],
    ["복구 확인 시작", recovery.cooldownAt],
    ["복구 완료", recovery.restoredAt],
  ];
  const total = recovery.restoredAt - recovery.detectedAt;

  return (
    <div
      role="dialog"
      aria-labelledby="recovery-title"
      data-testid="recovery-notice"
      className="fixed bottom-4 right-4 z-20 w-[min(22rem,calc(100vw-2rem))] rounded-xl border-2 border-emerald-500 bg-slate-900 p-4 shadow-2xl"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-mono text-xs font-bold tracking-widest text-emerald-300">SELF-HEALING COMPLETE</p>
          <h2 id="recovery-title" className="text-lg font-bold text-slate-50">
            자가 복구 완료 · S{recovery.dpid}:{recovery.inPort}
          </h2>
        </div>
        <button
          type="button"
          onClick={() => setDismissed(id)}
          className="rounded-md bg-slate-800 px-2 py-1 text-sm text-slate-200 hover:bg-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
        >
          확인
        </button>
      </div>
      <ol className="mt-3 space-y-1 text-sm">
        {rows.map(([label, ts]) => (
          <li key={label} className="flex justify-between gap-4">
            <span className="text-slate-300">{label}</span>
            <span className="font-mono text-slate-100">{clockMs(ts)}</span>
          </li>
        ))}
      </ol>
      <p className="mt-3 border-t border-slate-700 pt-2 text-sm text-slate-300">
        총 소요 <span className="font-mono font-bold text-emerald-300">{total.toFixed(1)}초</span>
        {" · "}차단·우회 규칙 해제, 기본 경로 복귀
      </p>
    </div>
  );
}
