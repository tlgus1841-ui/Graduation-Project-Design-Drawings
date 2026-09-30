import { PHASE_LABELS } from "../lib/towerState.js";

const STYLES = {
  CALIBRATING: "bg-amber-500/15 text-amber-300 ring-amber-400/40",
  NORMAL: "bg-emerald-500/15 text-emerald-300 ring-emerald-400/40",
  ATTACK_DETECTED: "bg-red-500/20 text-red-300 ring-red-500/60 animate-pulse",
  MITIGATED: "bg-sky-500/15 text-sky-300 ring-sky-400/40",
  COOLDOWN_VERIFY: "bg-teal-500/15 text-teal-300 ring-teal-400/40",
};

// FSM phase badge (spec §2).
export default function PhaseBadge({ phase }) {
  const style = STYLES[phase] ?? "bg-slate-700 text-slate-300 ring-slate-500/40";
  return (
    <span
      data-testid="phase-badge"
      className={`rounded-md px-3 py-1 text-sm font-bold tracking-wider ring-1 ${style}`}
    >
      {PHASE_LABELS[phase] ?? "WAITING FOR DATA"}
    </span>
  );
}
