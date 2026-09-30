import Panel from "./Panel.jsx";

// Fixed diamond layout (topo/diamond_topo.py). Replaced by vis-network in week 7.
const POS = {
  h_legit: [60, 90], h_attacker: [60, 250], s1: [200, 170],
  s2: [340, 60], s3: [340, 280], s4: [480, 170], h_server: [600, 170],
};
const NODE_COLOR = { NORMAL: "#10b981", ATTACKED: "#ef4444", MITIGATED: "#0ea5e9", OFFLINE: "#64748b" };
const LINK_STYLE = {
  ACTIVE: { stroke: "#10b981", dash: undefined, width: 3 },
  REROUTED: { stroke: "#3b82f6", dash: undefined, width: 5 },
  BLOCKED: { stroke: "#64748b", dash: "6 6", width: 3 },
};

export default function TopologyPanel({ topology }) {
  const { nodes, links } = topology;
  return (
    <Panel title="Topology" subtitle="간이 뷰 · 7주차 vis-network로 교체 예정" className="h-[380px]">
      {nodes.length === 0 ? (
        <p className="text-sm text-slate-400">토폴로지 수신 대기 중…</p>
      ) : (
        <svg viewBox="0 0 660 340" className="h-full w-full" role="img" aria-label="다이아몬드 토폴로지 상태">
          {links.map((l) => {
            const [x1, y1] = POS[l.source] ?? [0, 0];
            const [x2, y2] = POS[l.target] ?? [0, 0];
            const s = LINK_STYLE[l.status] ?? LINK_STYLE.ACTIVE;
            return (
              <line key={`${l.source}-${l.target}`} x1={x1} y1={y1} x2={x2} y2={y2}
                stroke={s.stroke} strokeWidth={s.width} strokeDasharray={s.dash} strokeLinecap="round" />
            );
          })}
          {nodes.map((n) => {
            const [x, y] = POS[n.id] ?? [0, 0];
            const color = NODE_COLOR[n.status] ?? NODE_COLOR.NORMAL;
            const isSwitch = n.node_type === "switch";
            return (
              <g key={n.id} className={n.status === "ATTACKED" ? "animate-pulse" : undefined}>
                {isSwitch ? (
                  <rect x={x - 34} y={y - 22} width="68" height="44" rx="8" fill="#0f172a" stroke={color} strokeWidth="3" />
                ) : (
                  <ellipse cx={x} cy={y} rx="52" ry="20" fill="#0f172a" stroke={color} strokeWidth="3" />
                )}
                <text x={x} y={y + 5} textAnchor="middle" fontSize="14" fontWeight="700" fill="#e2e8f0">
                  {isSwitch ? n.id.toUpperCase() : n.label}
                </text>
              </g>
            );
          })}
        </svg>
      )}
    </Panel>
  );
}
