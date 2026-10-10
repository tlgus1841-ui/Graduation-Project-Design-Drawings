import { useEffect, useState } from "react";
import { PORT_NAMES, clockMs, elapsedMs, fmt } from "../lib/format.js";
import { COOLDOWN_SEC } from "../lib/towerState.js";

function CooldownStrip({ incident }) {
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now() / 1000), 250);
    return () => clearInterval(id);
  }, []);
  const left = Math.min(COOLDOWN_SEC, Math.max(0, COOLDOWN_SEC - (now - incident.cooldownAt)));
  const done = ((COOLDOWN_SEC - left) / COOLDOWN_SEC) * 100;
  return (
    <div
      role="status"
      data-testid="incident-strip"
      data-state="cooldown"
      className="flex flex-col gap-2 rounded-xl border-2 border-teal-500 bg-teal-950/60 px-4 py-3"
    >
      <div className="flex flex-wrap items-center gap-x-6 gap-y-1">
        <span className="font-mono text-sm font-bold tracking-widest text-teal-200">● RESTORING</span>
        <span className="text-base font-bold text-teal-50">
          공격 소멸 확인 중 · S{incident.dpid}:{incident.inPort} 격리와 우회는 유지
        </span>
        <span className="ml-auto font-mono text-sm text-teal-200" data-testid="cooldown-left">
          복구까지 {left.toFixed(1)}초
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-teal-900" aria-hidden="true">
        <div className="h-full bg-teal-400 transition-[width] duration-200" style={{ width: `${done}%` }} />
      </div>
    </div>
  );
}

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

  // Week 10 review item: after mitigation the strip turns blue and names the bypass path.
  if (phase === "MITIGATED" && incident) {
    return (
      <div
        role="status"
        data-testid="incident-strip"
        data-state="mitigated"
        className="flex flex-wrap items-center gap-x-6 gap-y-1 rounded-xl border-2 border-blue-500 bg-blue-950/70 px-4 py-3"
      >
        <span className="font-mono text-sm font-bold tracking-widest text-blue-200">● MITIGATED</span>
        <span className="text-base font-bold text-blue-50">
          S{incident.dpid}:{incident.inPort} 격리 · 정상 트래픽 S1 → S3 → S4 우회
        </span>
        <span className="font-mono text-sm text-blue-200">
          탐지→격리 {elapsedMs(incident.detectedAt, incident.isolatedAt)} · 탐지→우회{" "}
          {elapsedMs(incident.detectedAt, incident.reroutedAt)}
        </span>
        <span className="ml-auto font-mono text-sm text-blue-200">격리 {clockMs(incident.isolatedAt)}</span>
      </div>
    );
  }

  // Week 11 review item: the cooldown shows how much of the 10 s clean window is left.
  if (phase === "COOLDOWN_VERIFY" && incident?.cooldownAt != null) {
    return <CooldownStrip incident={incident} />;
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
