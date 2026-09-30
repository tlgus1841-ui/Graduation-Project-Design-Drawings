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
    grid: { borderColor: INK.grid, strokeDashArray: 3, xaxis: { lines: { show: false } }, padding: { right: 36 } },
    legend: { show: true, position: "top", horizontalAlign: "left", labels: { colors: INK.primary }, fontSize: "12px" },
    // Direct label on the last point only (identity is never colour alone); text stays in ink, not series colour.
    dataLabels: {
      enabled: true,
      formatter: (val, { seriesIndex, dataPointIndex, w }) =>
        dataPointIndex === w.config.series[seriesIndex].data.length - 1 && val != null
          ? Math.round(val).toLocaleString("ko-KR")
          : "",
      offsetY: -6,
      background: { enabled: false },
      style: { colors: [INK.primary], fontSize: "11px", fontWeight: 600 },
    },
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

export default function TrafficCharts({ history }) {
  const empty = SERIES.every((s) => !(history[s.key]?.length));
  return (
    <>
      <div className="lg:col-span-6">
        <Panel title="초당 패킷 수 (PPS)" subtitle="S1 유입 포트 · 최근 2분" className="h-[300px]">
          {empty ? <Waiting /> : (
            <Chart type="line" height="100%" options={buildOptions(" PPS")} series={seriesFor(history, "pps")} />
          )}
        </Panel>
      </div>
      <div className="lg:col-span-6">
        <Panel title="패킷당 평균 크기 (BPP)" subtitle="공격 판별 핵심 지표 · 정상 500B↑ / SYN Flood ≈64B" className="h-[300px]">
          {empty ? <Waiting /> : (
            <Chart type="line" height="100%" options={buildOptions("B", 1500)} series={seriesFor(history, "bpp")} />
          )}
        </Panel>
      </div>
    </>
  );
}

function Waiting() {
  return <p className="text-sm text-slate-400">포트 통계 수신 대기 중…</p>;
}
