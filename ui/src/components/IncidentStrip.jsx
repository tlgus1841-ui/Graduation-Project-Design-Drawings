import { PORT_NAMES, clockMs, fmt } from "../lib/format.js";

// Always-present status strip under the header, so the layout never jumps when an alert opens.
// Week 9 review item: red alert flashes while the FSM is in ATTACK_DETECTED (spec §5 colour mapping).
export default function IncidentStrip({ phase, incident }) {
  if (phase === "ATTACK_DETECTED" && incident) {
    const key = `${incident.dpid}:${incident.inPort}`;
    return (
      <div
        role="alert"
        data-testid="incident-strip"
        data-state="red-alert"
        className="flex flex-wrap items-center gap-x-6 gap-y-1 rounded-xl border-2 border-red-500 bg-red-950/70 px-4 py-3 animate-alert-blink motion-reduce:animate-none"
      >
        <span className="font-mono text-sm font-bold tracking-widest text-red-200">● RED ALERT</span>
        <span className="text-base font-bold text-red-50">
          {incident.threatType} · 유입 포트 S{incident.dpid}:{incident.inPort}
          {PORT_NAMES[key] ? ` (${PORT_NAMES[key]})` : ""}
        </span>
        <span className="font-mono text-sm text-red-200">
          score {incident.score.toFixed(2)} · {fmt(incident.pps)} PPS · BPP {fmt(incident.bpp)}B
        </span>
        <span className="ml-auto font-mono text-sm text-red-200">탐지 {clockMs(incident.detectedAt)}</span>
      </div>
    );
  }

  const quiet = {
    CALIBRATING: ["text-amber-300", "기준 트래픽 학습 중 · 탐지 대기"],
    NORMAL: ["text-emerald-300", "정상 · 감지된 위협 없음"],
    MITIGATED: ["text-sky-300", "대응 중 · 공격 포트 격리, 우회 경로 운영"],
    COOLDOWN_VERIFY: ["text-teal-300", "복구 확인 중 · 공격 종료 여부 검증"],
  }[phase] ?? ["text-slate-400", "데이터 수신 대기 중"];

  return (
    <div
      data-testid="incident-strip"
      data-state="quiet"
      className="flex items-center gap-3 rounded-xl border-2 border-slate-800 bg-slate-800/40 px-4 py-3"
    >
      <span className={`font-mono text-sm font-bold tracking-widest ${quiet[0]}`}>●</span>
      <span className="text-base text-slate-300">{quiet[1]}</span>
    </div>
  );
}
