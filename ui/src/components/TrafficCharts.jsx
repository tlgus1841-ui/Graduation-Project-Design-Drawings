import { memo, useMemo } from "react";
import Chart from "react-apexcharts";
import Panel from "./Panel.jsx";

// Categorical slots 1-2 (dataviz reference palette, dark steps), validated on the panel surface.
const SERIES = [
  { key: "1:1", name: "H_legit (S1:1)", color: "#3987e5" },
  { key: "1:2", name: "H_attacker (S1:2)", color: "#d95926" },
];
const INK = { primary: "#e2e8f0", secondary: "#94a3b8", grid: "#334155" };

function buildOptions(unit, max) {
  return {
    chart: {
      type: "line",
      background: "transparent",
      animations: { enabled: false },
      toolbar: { show: false },
      zoom: { enabled: false },
      fontFamily: "ui-sans-serif, system-ui",
    },
    theme: { mode: "dark" },
    colors: SERIES.map((s) => s.color),
    stroke: { width: 2, curve: "straight" },
    markers: { size: 0, hover: { size: 5 } },
    grid: { borderColor: INK.grid, strokeDashArray: 3, xaxis: { lines: { show: false } }, padding: { right: 12 } },
    // Series names and latest values live in <LatestValues> above the chart (direct, text-labelled).
    legend: { show: false },
    // Per-point data labels made ApexCharts create and measure ~240 hidden <text> nodes per update
    // (the week-12 frame-drop cause), so they stay off.
    dataLabels: { enabled: false },
    xaxis: {
      type: "datetime",
      labels: { datetimeUTC: false, format: "HH:mm:ss", style: { colors: INK.secondary } },
      axisBorder: { color: INK.grid },
      axisTicks: { color: INK.grid },
      tooltip: { enabled: false },
    },
    yaxis: {
      min: 0,
      max,
      forceNiceScale: true,
      labels: { style: { colors: INK.secondary }, formatter: (v) => Math.round(v).toLocaleString("ko-KR") },
    },
    tooltip: {
      theme: "dark",
      shared: true,
      intersect: false,
      x: { format: "HH:mm:ss" },
      y: { formatter: (v) => (v == null ? "-" : `${Math.round(v).toLocaleString("ko-KR")}${unit}`) },
    },
  };
}

function seriesFor(history, field) {
  return SERIES.map((s) => ({
    name: s.name,
    data: (history[s.key] ?? []).map((p) => ({ x: p.t * 1000, y: p[field] || null })),
  }));
}

// Static options are built once; only series change per tick (keeps ApexCharts on its cheap update path).
const PPS_OPTIONS = buildOptions(" PPS");
const BPP_OPTIONS = buildOptions("B", 1500);

function LatestValues({ history, field, unit }) {
  return (
    <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs" data-testid={`latest-${field}`}>
      {SERIES.map((s) => {
        const last = history[s.key]?.at(-1)?.[field];
        return (
          <span key={s.key} className="inline-flex items-center gap-1.5 text-slate-300">
            <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: s.color }} />
            {s.name}
            <span className="font-mono font-semibold text-slate-100">
              {last ? `${Math.round(last).toLocaleString("ko-KR")}${unit}` : "-"}
            </span>
          </span>
        );
      })}
    </div>
  );
}

function ChartBody({ history, field, unit, options, series }) {
  return (
    <div className="flex h-full flex-col gap-1">
      <LatestValues history={history} field={field} unit={unit} />
      <div className="min-h-0 flex-1">
        <Chart type="line" height="100%" options={options} series={series} />
      </div>
    </div>
  );
}

function TrafficCharts({ history }) {
  const empty = SERIES.every((s) => !(history[s.key]?.length));
  const ppsSeries = useMemo(() => seriesFor(history, "pps"), [history]);
  const bppSeries = useMemo(() => seriesFor(history, "bpp"), [history]);
  return (
    <>
      <div className="lg:col-span-6">
        <Panel title="초당 패킷 수 (PPS)" subtitle="S1 유입 포트 · 최근 2분" className="h-[300px]">
          {empty ? <Waiting /> : (
            <ChartBody history={history} field="pps" unit=" PPS" options={PPS_OPTIONS} series={ppsSeries} />
          )}
        </Panel>
      </div>
      <div className="lg:col-span-6">
        <Panel title="패킷당 평균 크기 (BPP)" subtitle="공격 판별 핵심 지표 · 정상 500B↑ / SYN Flood ≈64B" className="h-[300px]">
          {empty ? <Waiting /> : (
            <ChartBody history={history} field="bpp" unit="B" options={BPP_OPTIONS} series={bppSeries} />
          )}
        </Panel>
      </div>
    </>
  );
}

export default memo(TrafficCharts);

function Waiting() {
  return <p className="text-sm text-slate-400">포트 통계 수신 대기 중…</p>;
}
