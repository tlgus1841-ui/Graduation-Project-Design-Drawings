import { PORT_NAMES, fmt } from "../lib/format.js";
import Panel from "./Panel.jsx";

export default function PortStatsPanel({ ports, phase, incident }) {
  const rows = Object.entries(ports).sort(([a], [b]) => a.localeCompare(b, undefined, { numeric: true }));
  // The port named in the open incident flashes red while the attack is live.
  const alertKey = phase === "ATTACK_DETECTED" && incident ? `${incident.dpid}:${incident.inPort}` : null;
  return (
    <Panel title="Port Telemetry" subtitle="수신 기준 · 2초 주기" className="h-[300px]">
      {rows.length === 0 ? (
        <p className="text-sm text-slate-400">포트 통계 수신 대기 중…</p>
      ) : (
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase tracking-wider text-slate-400">
            <tr>
              <th className="pb-2">Port</th><th className="pb-2">연결</th>
              <th className="pb-2 text-right">PPS</th><th className="pb-2 text-right">bps</th>
              <th className="pb-2 text-right">BPP</th>
            </tr>
          </thead>
          <tbody className="font-mono text-slate-200">
            {rows.map(([key, p]) => {
              const hot = p.pps > 1000 && p.bpp > 0 && p.bpp < 80;
              const alerting = key === alertKey;
              return (
                <tr
                  key={key}
                  data-alert={alerting || undefined}
                  className={`border-t border-slate-700/50 ${hot || alerting ? "text-red-300" : ""} ${
                    alerting ? "bg-red-950/60 font-bold animate-pulse motion-reduce:animate-none" : ""
                  }`}
                >
                  <td className="py-1.5">S{p.dpid}:{p.portNo}</td>
                  <td className="py-1.5 font-sans text-slate-400">{PORT_NAMES[key] ?? "-"}</td>
                  <td className="py-1.5 text-right">{fmt(p.pps)}</td>
                  <td className="py-1.5 text-right">{fmt(p.bps)}</td>
                  <td className="py-1.5 text-right">{p.bpp ? `${fmt(p.bpp)}B` : "-"}{(hot || alerting) && " ⚠"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </Panel>
  );
}
