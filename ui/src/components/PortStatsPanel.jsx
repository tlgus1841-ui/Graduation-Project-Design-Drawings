import Panel from "./Panel.jsx";

const PORT_NAMES = {
  "1:1": "H_legit", "1:2": "H_attacker", "1:3": "→ S2", "1:4": "→ S3",
  "2:1": "→ S1", "2:2": "→ S4", "3:1": "→ S1", "3:2": "→ S4",
  "4:1": "H_server", "4:2": "→ S2", "4:3": "→ S3",
};

const fmt = (n) => Math.round(n).toLocaleString("ko-KR");

export default function PortStatsPanel({ ports }) {
  const rows = Object.entries(ports).sort(([a], [b]) => a.localeCompare(b, undefined, { numeric: true }));
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
              return (
                <tr key={key} className={`border-t border-slate-700/50 ${hot ? "text-red-300" : ""}`}>
                  <td className="py-1.5">S{p.dpid}:{p.portNo}</td>
                  <td className="py-1.5 font-sans text-slate-400">{PORT_NAMES[key] ?? "-"}</td>
                  <td className="py-1.5 text-right">{fmt(p.pps)}</td>
                  <td className="py-1.5 text-right">{fmt(p.bps)}</td>
                  <td className="py-1.5 text-right">{p.bpp ? `${fmt(p.bpp)}B` : "-"}{hot && " ⚠"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </Panel>
  );
}
