import { useEffect, useRef, useState } from "react";
import { DataSet } from "vis-data/peer";
import { Network } from "vis-network/peer";
import "vis-network/styles/vis-network.css";
import Panel from "./Panel.jsx";

// Spec §5 colour mapping. Status is also written in the label/tooltip, never colour alone.
const NODE_COLOR = { NORMAL: "#10b981", ATTACKED: "#ef4444", MITIGATED: "#0ea5e9", OFFLINE: "#64748b" };
const EDGE_STYLE = {
  ACTIVE: { color: "#10b981", width: 3, dashes: false },
  REROUTED: { color: "#3b82f6", width: 6, dashes: false },
  BLOCKED: { color: "#64748b", width: 3, dashes: [8, 8] },
};
// Fixed diamond layout (topo/diamond_topo.py). Physics is off, so nodes never drift or jitter;
// they can still be dragged and stay where they are dropped.
const SEED = {
  h_legit: [-330, -110], h_attacker: [-330, 110], s1: [-160, 0],
  s2: [0, -140], s3: [0, 140], s4: [160, 0], h_server: [330, 0],
};

const PORT_NAMES = { "1:1": "H_legit", "1:2": "H_attacker", "1:3": "→ S2", "1:4": "→ S3", "4:1": "H_server" };

function toVisNode(n) {
  const color = NODE_COLOR[n.status] ?? NODE_COLOR.NORMAL;
  const isSwitch = n.node_type === "switch";
  const [x, y] = SEED[n.id] ?? [0, 0];
  return {
    id: n.id,
    x,
    y,
    label: isSwitch ? n.id.toUpperCase() : n.label,
    title: `${n.label} · ${n.status}${n.ip ? ` · ${n.ip}` : ""}`,
    shape: isSwitch ? "box" : "ellipse",
    borderWidth: n.status === "ATTACKED" ? 5 : 3,
    color: { background: "#0f172a", border: color, highlight: { background: "#1e293b", border: color } },
    font: { color: "#e2e8f0", size: 16, face: "ui-sans-serif, system-ui", bold: isSwitch },
    margin: 12,
  };
}

function toVisEdge(l) {
  const s = EDGE_STYLE[l.status] ?? EDGE_STYLE.ACTIVE;
  return {
    id: `${l.source}-${l.target}`,
    from: l.source,
    to: l.target,
    color: { color: s.color, highlight: s.color },
    width: s.width,
    dashes: s.dashes,
    title: `${l.source.toUpperCase()}:${l.src_port} ↔ ${l.target.toUpperCase()}:${l.dst_port} · ${l.status}`,
  };
}

// Sync a DataSet to `items` in place (update/add/remove) instead of rebuilding the network.
function syncDataSet(ds, items) {
  const ids = new Set(items.map((i) => i.id));
  ds.remove(ds.getIds().filter((id) => !ids.has(id)));
  ds.update(items);
}

export default function TopologyMap({ topology, ports }) {
  const containerRef = useRef(null);
  const networkRef = useRef(null);
  const nodesRef = useRef(new DataSet());
  const edgesRef = useRef(new DataSet());
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    const network = new Network(
      containerRef.current,
      { nodes: nodesRef.current, edges: edgesRef.current },
      {
        physics: false,
        interaction: { hover: true, tooltipDelay: 150, zoomView: false, dragView: false },
        edges: { smooth: false },
      },
    );
    network.on("selectNode", (e) => setSelected(e.nodes[0] ?? null));
    network.on("deselectNode", () => setSelected(null));
    networkRef.current = network;
    return () => {
      network.destroy();
      networkRef.current = null;
    };
  }, []);

  useEffect(() => {
    const hadNodes = nodesRef.current.length > 0;
    // Positions are only seeded once; later updates must not snap dragged nodes back.
    const nodes = topology.nodes.map(toVisNode);
    // eslint-disable-next-line no-unused-vars
    syncDataSet(nodesRef.current, hadNodes ? nodes.map(({ x, y, ...rest }) => rest) : nodes);
    syncDataSet(edgesRef.current, topology.links.map(toVisEdge));
    if (!hadNodes && nodes.length) networkRef.current?.fit();
  }, [topology]);

  const node = topology.nodes.find((n) => n.id === selected);
  const nodePorts = node?.dpid
    ? Object.values(ports).filter((p) => p.dpid === node.dpid).sort((a, b) => a.portNo - b.portNo)
    : [];

  return (
    <Panel title="Topology" subtitle="드래그로 배치 · 노드 클릭 시 상세" className="h-[420px]">
      <div className="flex h-full flex-col gap-2">
        <div ref={containerRef} data-testid="topology-map" className="min-h-0 flex-1" aria-label="다이아몬드 토폴로지 상태 지도" />
        <div className="flex min-h-[28px] flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400">
          {node ? (
            <>
              <span className="font-semibold text-slate-100">{node.label}</span>
              <span>상태 {node.status}</span>
              {node.ip && <span>{node.ip}</span>}
              {nodePorts.map((p) => (
                <span key={p.portNo} className="font-mono">
                  p{p.portNo}{PORT_NAMES[`${p.dpid}:${p.portNo}`] ? ` ${PORT_NAMES[`${p.dpid}:${p.portNo}`]}` : ""}: {Math.round(p.pps)} PPS
                </span>
              ))}
            </>
          ) : (
            <>
              <Legend color="#10b981" label="정상" />
              <Legend color="#ef4444" label="공격 받음" />
              <Legend color="#0ea5e9" label="격리됨" />
              <Legend color="#3b82f6" label="우회 경로" line />
              <Legend color="#64748b" label="차단 링크" line dashed />
            </>
          )}
        </div>
      </div>
    </Panel>
  );
}

function Legend({ color, label, line = false, dashed = false }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      {line ? (
        <span className="inline-block w-5 border-t-[3px]" style={{ borderColor: color, borderStyle: dashed ? "dashed" : "solid" }} />
      ) : (
        <span className="inline-block h-3 w-3 rounded-sm border-2" style={{ borderColor: color }} />
      )}
      {label}
    </span>
  );
}
