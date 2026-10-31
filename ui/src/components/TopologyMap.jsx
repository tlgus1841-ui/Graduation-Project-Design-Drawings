import { memo, useEffect, useRef, useState } from "react";
import { DataSet } from "vis-data/peer";
import { Network } from "vis-network/peer";
import "vis-network/styles/vis-network.css";
import Panel from "./Panel.jsx";
import { PORT_NAMES, getPortLabel } from "../lib/format.js";
import {
  SEED_4SW,
  SEED_8SW,
  ZONE_CONFIG,
  getNodeZone,
  isLargeTopology,
  getSeedCoordinates,
  calculateZoneBounds,
} from "../lib/topologyLayout.js";

// Spec §5 colour mapping. Status is also written in the label/tooltip, never colour alone.
export const NODE_COLOR = {
  NORMAL: "#10b981",
  ATTACKED: "#ef4444",
  MITIGATED: "#0ea5e9",
  OFFLINE: "#64748b",
  QUARANTINED: "#f97316",
};

export const EDGE_STYLE = {
  ACTIVE: { color: "#10b981", width: 3, dashes: false },
  REROUTED: { color: "#3b82f6", width: 8, dashes: false },
  BLOCKED: { color: "#64748b", width: 3, dashes: [8, 8] },
  QUARANTINE_SAFE: { color: "#f97316", width: 3, dashes: [5, 5] },
};

// Re-export SEED pointing to legacy SEED_4SW for unit test compatibility
export const SEED = SEED_4SW;
export { SEED_4SW, SEED_8SW };

const BYPASS_NODES = new Set(["s3"]);
export const isBypassEdge = (l) => BYPASS_NODES.has(l.source) || BYPASS_NODES.has(l.target);

export function toVisNode(n, isLarge = false) {
  const color = NODE_COLOR[n.status] ?? NODE_COLOR.NORMAL;
  const isSwitch = n.node_type === "switch" || /^s\d+$/i.test(n.id);
  const isQuarantined = n.status === "QUARANTINED";
  const isPatchServer = n.id === "h_patch";
  const isAdmin = n.id === "h_admin";
  const [x, y] = getSeedCoordinates(n.id, isLarge);

  let label = n.label;
  if (isSwitch) {
    label = n.id.toUpperCase();
  } else if (isQuarantined) {
    label = `⚠️ ${n.label} (격리)`;
  } else if (isPatchServer) {
    label = `🛠️ ${n.label} (패치서버)`;
  } else if (isAdmin) {
    label = `🛡️ ${n.label} (관리자)`;
  }

  return {
    id: n.id,
    x,
    y,
    label,
    title: `${n.label} · ${n.status}${n.ip ? ` · ${n.ip}` : ""}`,
    shape: isSwitch ? "box" : (isPatchServer ? "diamond" : "ellipse"),
    borderWidth: n.status === "ATTACKED" || isQuarantined ? 5 : 3,
    color: {
      background: "#0f172a",
      border: isPatchServer && !isQuarantined ? "#a855f7" : color,
      highlight: { background: "#1e293b", border: color },
    },
    font: { color: "#e2e8f0", size: 16, face: "ui-sans-serif, system-ui", bold: isSwitch },
    margin: 12,
  };
}

export function toVisEdge(l) {
  const s = EDGE_STYLE[l.status] ?? EDGE_STYLE.ACTIVE;
  const rerouted = l.status === "REROUTED";
  const isSafeChannel = l.status === "QUARANTINE_SAFE";
  const bypass = isBypassEdge(l);

  return {
    id: `${l.source}-${l.target}`,
    from: l.source,
    to: l.target,
    color: { color: s.color, highlight: s.color },
    width: s.width,
    dashes: s.dashes,
    smooth: bypass
      ? { enabled: true, type: "curvedCW", roundness: 0.35 }
      : (isSafeChannel ? { enabled: true, type: "curvedCCW", roundness: 0.25 } : { enabled: false }),
    arrows: (rerouted || isSafeChannel) ? { to: { enabled: true, scaleFactor: 1.1, type: "arrow" } } : undefined,
    shadow: rerouted
      ? { enabled: true, color: "rgba(59,130,246,0.95)", size: 20, x: 0, y: 0 }
      : (isSafeChannel ? { enabled: true, color: "rgba(249,115,22,0.95)", size: 15, x: 0, y: 0 } : { enabled: false }),
    title: isSafeChannel
      ? "L4 격리 치료 채널: TCP 80 (패치 다운로드 허용)"
      : `${l.source.toUpperCase()}:${l.src_port} ↔ ${l.target.toUpperCase()}:${l.dst_port} · ${l.status}`,
  };
}

// Sync a DataSet to `items` in place (update/add/remove) instead of rebuilding the network.
function syncDataSet(ds, items) {
  const ids = new Set(items.map((i) => i.id));
  ds.remove(ds.getIds().filter((id) => !ids.has(id)));
  ds.update(items);
}

function TopologyMap({ topology, ports }) {
  const containerRef = useRef(null);
  const networkRef = useRef(null);
  const nodesRef = useRef(new DataSet());
  const edgesRef = useRef(new DataSet());
  const currentNodesRef = useRef([]);
  const layoutModeRef = useRef("cluster");

  const [selected, setSelected] = useState(null);
  const [layoutMode, setLayoutMode] = useState("cluster");

  // Mount vis-network once
  useEffect(() => {
    const network = new Network(
      containerRef.current,
      { nodes: nodesRef.current, edges: edgesRef.current },
      {
        physics: false,
        interaction: { hover: true, tooltipDelay: 150, zoomView: true, dragView: true },
        edges: { smooth: false },
      },
    );

    // Canvas background zone boxes rendering (beforeDrawing hook)
    network.on("beforeDrawing", (ctx) => {
      if (layoutModeRef.current === "hierarchical") return;
      const currentNodes = currentNodesRef.current;
      if (!currentNodes || !currentNodes.length) return;
      const isLarge = isLargeTopology(currentNodes);
      if (!isLarge) return;

      const bounds = calculateZoneBounds(currentNodes, isLarge);
      for (const b of Object.values(bounds)) {
        if (b.nodeCount === 0) continue;
        ctx.save();
        ctx.fillStyle = b.config.bg;
        ctx.strokeStyle = b.config.border;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 4]);

        const radius = 12;
        ctx.beginPath();
        if (typeof ctx.roundRect === "function") {
          ctx.roundRect(b.minX, b.minY, b.width, b.height, radius);
        } else {
          ctx.rect(b.minX, b.minY, b.width, b.height);
        }
        ctx.fill();
        ctx.stroke();

        // Zone Header Text
        ctx.font = "bold 13px ui-sans-serif, system-ui, sans-serif";
        ctx.fillStyle = b.config.color;
        ctx.fillText(b.config.label, b.minX + 16, b.minY + 22);
        ctx.restore();
      }
    });

    network.on("selectNode", (e) => setSelected(e.nodes[0] ?? null));
    network.on("deselectNode", () => setSelected(null));
    networkRef.current = network;

    return () => {
      network.destroy();
      networkRef.current = null;
    };
  }, []);

  // Update nodes and edges on topology change
  useEffect(() => {
    currentNodesRef.current = topology.nodes;
    const isLarge = isLargeTopology(topology.nodes);
    const hadNodes = nodesRef.current.length > 0;

    const visNodes = topology.nodes.map((n) => toVisNode(n, isLarge));
    syncDataSet(nodesRef.current, hadNodes && layoutModeRef.current === "cluster"
      ? visNodes.map(({ x, y, ...rest }) => rest)
      : visNodes);

    // Combine explicit links + dynamic quarantine safe channel links
    const allLinks = [...(topology.links || [])];
    const hasPatchServer = topology.nodes.some((n) => n.id === "h_patch");
    if (hasPatchServer) {
      for (const n of topology.nodes) {
        if (n.status === "QUARANTINED") {
          allLinks.push({
            source: n.id,
            target: "h_patch",
            src_port: 0,
            dst_port: 80,
            status: "QUARANTINE_SAFE",
          });
        }
      }
    }

    syncDataSet(edgesRef.current, allLinks.map(toVisEdge));
    if (!hadNodes && visNodes.length) networkRef.current?.fit();
  }, [topology]);

  const handleLayoutModeChange = (mode) => {
    setLayoutMode(mode);
    layoutModeRef.current = mode;
    if (!networkRef.current) return;

    if (mode === "hierarchical") {
      networkRef.current.setOptions({
        layout: {
          hierarchical: {
            enabled: true,
            direction: "UD",
            sortMethod: "directed",
            levelSeparation: 130,
            nodeSpacing: 180,
          },
        },
        physics: {
          hierarchicalRepulsion: {
            nodeDistance: 160,
          },
        },
      });
    } else {
      networkRef.current.setOptions({
        layout: {
          hierarchical: {
            enabled: false,
          },
        },
        physics: false,
      });
      // Restore seed positions
      const isLarge = isLargeTopology(topology.nodes);
      const updates = topology.nodes.map((n) => {
        const [x, y] = getSeedCoordinates(n.id, isLarge);
        return { id: n.id, x, y };
      });
      nodesRef.current.update(updates);
      networkRef.current.fit();
    }
  };

  const node = topology.nodes.find((n) => n.id === selected);
  const nodePorts = node?.dpid
    ? Object.values(ports).filter((p) => p.dpid === node.dpid).sort((a, b) => a.portNo - b.portNo)
    : [];

  return (
    <Panel
      title="Topology"
      subtitle="드래그로 배치 · 노드 클릭 시 상세"
      className="h-[460px]"
      headerAction={
        <div className="flex items-center gap-1 rounded-md bg-slate-800/80 p-0.5 border border-slate-700">
          <button
            type="button"
            onClick={() => handleLayoutModeChange("cluster")}
            className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
              layoutMode === "cluster" ? "bg-sky-600 text-white shadow" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            클러스터 뷰
          </button>
          <button
            type="button"
            onClick={() => handleLayoutModeChange("hierarchical")}
            className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
              layoutMode === "hierarchical" ? "bg-sky-600 text-white shadow" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            계층형 정렬
          </button>
        </div>
      }
    >
      <div className="flex h-full flex-col gap-2">
        <div
          ref={containerRef}
          data-testid="topology-map"
          className="min-h-0 flex-1"
          aria-label="엔터프라이즈 8-스위치 5-구역 상태 지도"
        />
        <div className="flex min-h-[28px] flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-300">
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
              <Legend color="#f97316" label="격리(치료중)" />
              <Legend color="#3b82f6" label="우회 경로" line />
              <Legend color="#64748b" label="차단 링크" line dashed />
              <Legend color="#f97316" label="L4 치료 채널" line dashed />
            </>
          )}
        </div>
      </div>
    </Panel>
  );
}

export default memo(TopologyMap);

function Legend({ color, label, line = false, dashed = false }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      {line ? (
        <span
          className="inline-block w-5 border-t-[3px]"
          style={{ borderColor: color, borderStyle: dashed ? "dashed" : "solid" }}
        />
      ) : (
        <span className="inline-block h-3 w-3 rounded-sm border-2" style={{ borderColor: color }} />
      )}
      {label}
    </span>
  );
}
