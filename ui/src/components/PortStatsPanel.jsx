import { useState } from "react";
import { fmt, getPortLabel } from "../lib/format.js";
import Panel from "./Panel.jsx";

const TABS = [
  { id: "ALL", label: "전체" },
  { id: "USER", label: "사용자망 (S3, S4)", dpids: [3, 4] },
  { id: "SERVER", label: "서버망 (S5, S6)", dpids: [5, 6] },
  { id: "ADMIN_QUAR", label: "관리/격리 (S7, S8)", dpids: [7, 8] },
  { id: "BACKBONE", label: "백본망 (S1, S2)", dpids: [1, 2] },
];

export default function PortStatsPanel({ ports, phase, incident }) {
  const [activeTab, setActiveTab] = useState("ALL");
  const [viewMode, setViewMode] = useState("cards"); // "cards" | "table"

  const rows = Object.entries(ports).sort(([a], [b]) =>
    a.localeCompare(b, undefined, { numeric: true }),
  );

  // The port named in the open incident flashes red while the attack is live.
  const alertKey = phase === "ATTACK_DETECTED" && incident ? `${incident.dpid}:${incident.inPort}` : null;
  const alertDpid = phase === "ATTACK_DETECTED" && incident ? incident.dpid : null;

  const currentTab = TABS.find((t) => t.id === activeTab);
  const filteredRows = rows.filter(([_, p]) => {
    if (activeTab === "ALL") return true;
    return currentTab?.dpids?.includes(p.dpid);
  });

  return (
    <Panel
      title="Port Telemetry"
      subtitle="수신 기준 · 2초 주기"
      className="min-h-[350px]"
      headerAction={
        <div className="flex flex-wrap items-center gap-2">
          {/* Subnet Tabs */}
          <div className="flex items-center gap-1 overflow-x-auto rounded-lg bg-slate-900/60 p-0.5 border border-slate-700/60">
            {TABS.map((tab) => {
              const hasAlert = alertDpid && tab.dpids?.includes(alertDpid);
              const active = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium transition-colors ${
                    active ? "bg-sky-600 text-white" : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  <span>{tab.label}</span>
                  {hasAlert && (
                    <span className="flex h-3.5 w-3.5 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white animate-ping motion-reduce:animate-none">
                      !
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* View Mode Switcher */}
          <div className="flex items-center rounded-lg bg-slate-900/60 p-0.5 border border-slate-700/60 text-xs">
            <button
              type="button"
              onClick={() => setViewMode("cards")}
              className={`px-2 py-0.5 rounded font-medium transition-colors ${
                viewMode === "cards" ? "bg-sky-600 text-white font-semibold" : "text-slate-400 hover:text-slate-200"
              }`}
              title="카드 그리드 뷰"
            >
              카드
            </button>
            <button
              type="button"
              onClick={() => setViewMode("table")}
              className={`px-2 py-0.5 rounded font-medium transition-colors ${
                viewMode === "table" ? "bg-sky-600 text-white font-semibold" : "text-slate-400 hover:text-slate-200"
              }`}
              title="상세 테이블 뷰"
            >
              테이블
            </button>
          </div>
        </div>
      }
    >
      {filteredRows.length === 0 ? (
        <p className="text-base text-slate-300">해당 구역의 포트 통계 수신 대기 중…</p>
      ) : viewMode === "cards" ? (
        /* Responsive Card Grid View (4~6 columns) */
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2.5">
          {filteredRows.map(([key, p]) => {
            const hot = p.pps > 1000 && p.bpp > 0 && p.bpp < 80;
            const alerting = key === alertKey;
            const ppsPct = Math.min(100, Math.max(2, Math.round((p.pps / 2000) * 100)));
            return (
              <div
                key={key}
                data-alert={alerting || undefined}
                className={`flex flex-col justify-between rounded-lg border p-2.5 transition-all ${
                  alerting
                    ? "bg-red-950/70 border-red-500 shadow-lg shadow-red-950/60 ring-2 ring-red-500/50 animate-pulse"
                    : hot
                    ? "bg-red-950/30 border-red-500/60"
                    : "bg-slate-900/70 border-slate-700/60 hover:border-slate-500"
                }`}
              >
                <div className="flex items-center justify-between gap-1">
                  <span className="font-mono text-xs font-bold text-sky-300 bg-sky-950/80 px-1.5 py-0.5 rounded border border-sky-800/60">
                    S{p.dpid}:{p.portNo}
                  </span>
                  {(alerting || hot) && (
                    <span className="flex items-center gap-0.5 text-[11px] font-bold text-red-400 animate-bounce">
                      ⚠ ALERT
                    </span>
                  )}
                </div>
                <div className="mt-1.5 truncate text-xs font-semibold text-slate-200" title={getPortLabel(key)}>
                  {getPortLabel(key)}
                </div>
                <div className="mt-2">
                  <div className="flex items-baseline justify-between">
                    <span className="font-mono text-lg font-extrabold tracking-tight text-white">
                      {fmt(p.pps)}
                    </span>
                    <span className="text-[10px] uppercase font-mono text-slate-400">pps</span>
                  </div>
                  {/* Traffic Meter Progress Bar */}
                  <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
                    <div
                      className={`h-full transition-all duration-300 rounded-full ${
                        alerting || hot ? "bg-red-500" : p.pps > 500 ? "bg-amber-400" : "bg-emerald-400"
                      }`}
                      style={{ width: `${ppsPct}%` }}
                    />
                  </div>
                </div>
                <div className="mt-2.5 flex items-center justify-between border-t border-slate-800/80 pt-1.5 font-mono text-[11px] text-slate-400">
                  <span>{fmt(p.bps)}b</span>
                  <span>{p.bpp ? `${fmt(p.bpp)}B` : "-"}</span>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* Detailed Table View */
        <table className="w-full text-base">
          <thead className="text-left text-sm uppercase tracking-wider text-slate-300">
            <tr>
              <th className="pb-2">Port</th>
              <th className="pb-2">연결 대상</th>
              <th className="pb-2 text-right">PPS</th>
              <th className="pb-2 text-right">bps</th>
              <th className="pb-2 text-right">BPP</th>
            </tr>
          </thead>
          <tbody className="font-mono text-slate-100">
            {filteredRows.map(([key, p]) => {
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
                  <td className="py-2">S{p.dpid}:{p.portNo}</td>
                  <td className="py-2 font-sans text-slate-300">{getPortLabel(key)}</td>
                  <td className="py-2 text-right">{fmt(p.pps)}</td>
                  <td className="py-2 text-right">{fmt(p.bps)}</td>
                  <td className="py-2 text-right">
                    {p.bpp ? `${fmt(p.bpp)}B` : "-"}
                    {(hot || alerting) && " ⚠"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </Panel>
  );
}
