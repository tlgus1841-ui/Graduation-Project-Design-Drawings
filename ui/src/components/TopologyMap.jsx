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
  const isCore = n.id === "s1" || n.id === "s2";
  const isQuarantined = n.status === "QUARANTINED";
  const isPatchServer = n.id === "h_patch";
  const isAdmin = n.id === "h_admin";
  const [x, y] = getSeedCoordinates(n.id, isLarge);

  let label = n.label;
  if (isSwitch) {
    label = isCore ? `${n.id.toUpperCase()} (Core)` : n.id.toUpperCase();
  } else if (isQuarantined) {
    label = `⚠️ ${n.label} (격리)`;
  } else if (isPatchServer) {
    label = `🛠️ ${n.label} (패치서버)`;
  } else if (isAdmin) {
    label = `🛡️ ${n.label} (관리자)`;
  } else if (n.id === "h5") {
    label = `${n.label} (Web)`;
  } else if (n.id === "h6") {
    label = `${n.label} (API)`;
  } else if (n.id === "h7") {
    label = `${n.label} (DB)`;
  } else if (n.id === "h8") {
    label = `${n.label} (Backup)`;
  }

  return {
    id: n.id,
    x,
    y,
    label,
    title: `${n.label} · ${n.status}${n.ip ? ` · ${n.ip}` : ""}`,
    shape: isSwitch ? "box" : (isPatchServer ? "diamond" : "ellipse"),
    borderWidth: n.status === "ATTACKED" || isQuarantined ? 5 : (isCore ? 4 : 3),
    shapeProperties: isSwitch ? { borderRadius: isCore ? 12 : 8 } : undefined,
    color: {
      background: isCore ? "#0f172a" : (isSwitch ? "#0b1329" : "#0f172a"),
      border: isPatchServer && !isQuarantined ? "#a855f7" : color,
      highlight: { background: "#1e293b", border: color },
    },
    font: {
      color: "#f8fafc",
      size: isCore ? 17 : (isSwitch ? 15 : 13),
      face: "ui-sans-serif, system-ui",
    },
    margin: isCore ? 14 : (isSwitch ? 10 : 8),
  };
}

export function toVisEdge(l) {
  const s = EDGE_STYLE[l.status] ?? EDGE_STYLE.ACTIVE;
  const rerouted = l.status === "REROUTED";
  const isSafeChannel = l.status === "QUARANTINE_SAFE";
  const bypass = isBypassEdge(l);
  const isTrunk = l.is_trunk || (l.source?.startsWith("s") && l.target?.startsWith("s"));
  const src = String(l.source || "").toUpperCase();
  const dst = String(l.target || "").toUpperCase();

  return {
    id: `${l.source}-${l.target}`,
    from: l.source,
    to: l.target,
    color: { color: s.color, highlight: s.color },
    width: rerouted ? 8 : (isTrunk ? 4 : s.width),
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
      : `${isTrunk ? "🔗 Trunk 백본" : "💻 호스트 접속"}: ${src}:${l.src_port ?? 0} ↔ ${dst}:${l.dst_port ?? 0} · ${l.status || "ACTIVE"}`,
  };
}

// Generate augmented links including dynamic quarantine safe channel links
export function getAugmentedLinks(topology) {
  const allLinks = [...(topology?.links || [])];
  const nodes = topology?.nodes || [];
  const hasPatchServer = nodes.some((n) => n.id === "h_patch");
  if (hasPatchServer) {
    for (const n of nodes) {
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
  return allLinks;
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
        ctx.setLineDash([]); // Clean solid border

        const radius = 16;
        ctx.beginPath();
        if (typeof ctx.roundRect === "function") {
          ctx.roundRect(b.minX, b.minY, b.width, b.height, radius);
        } else {
          ctx.rect(b.minX, b.minY, b.width, b.height);
        }
        ctx.fill();
        ctx.stroke();

        // Zone Tag Pill in top-left
        const tagText = b.config.label;
        ctx.font = "bold 12px ui-sans-serif, system-ui, sans-serif";
        const textWidth = ctx.measureText(tagText).width;
        const tagPadding = 8;
        const tagHeight = 20;

        ctx.fillStyle = b.config.border;
        ctx.beginPath();
        if (typeof ctx.roundRect === "function") {
          ctx.roundRect(b.minX + 12, b.minY + 10, textWidth + tagPadding * 2, tagHeight, 4);
        } else {
          ctx.rect(b.minX + 12, b.minY + 10, textWidth + tagPadding * 2, tagHeight);
        }
        ctx.fill();

        ctx.fillStyle = "#ffffff";
        ctx.fillText(tagText, b.minX + 12 + tagPadding, b.minY + 10 + 14);
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
    syncDataSet(
      nodesRef.current,
      hadNodes && layoutModeRef.current === "cluster"
        ? visNodes.map(({ x, y, ...rest }) => rest)
        : visNodes,
    );

    const allLinks = getAugmentedLinks(topology);
    syncDataSet(edgesRef.current, allLinks.map(toVisEdge));
    if (!hadNodes && visNodes.length) networkRef.current?.fit();
  }, [topology]);

  // Reactive Focus & Dimming when a node is selected/deselected
  useEffect(() => {
    if (!networkRef.current || !topology.nodes?.length) return;
    const net = networkRef.current;
    const isLarge = isLargeTopology(topology.nodes);
    const allLinks = getAugmentedLinks(topology);

    if (!selected) {
      // Restore all nodes and edges to full brightness
      const visNodes = topology.nodes.map((n) => toVisNode(n, isLarge));
      nodesRef.current.update(visNodes);
      edgesRef.current.update(allLinks.map(toVisEdge));
      return;
    }

    const connectedNodes = new Set(net.getConnectedNodes(selected));
    connectedNodes.add(selected);
    const connectedEdges = new Set(net.getConnectedEdges(selected));

    const nodeUpdates = topology.nodes.map((n) => {
      const base = toVisNode(n, isLarge);
      if (connectedNodes.has(n.id)) {
        return {
          id: n.id,
          opacity: 1.0,
          color: base.color,
          font: base.font,
          borderWidth: n.id === selected ? base.borderWidth + 2 : base.borderWidth,
        };
      }
      return {
        id: n.id,
        opacity: 0.18,
        color: {
          background: "#070b14",
          border: "rgba(100,116,139,0.2)",
          highlight: { background: "#0f172a", border: "rgba(100,116,139,0.3)" },
        },
        font: { color: "rgba(148,163,184,0.25)" },
      };
    });

    const edgeUpdates = allLinks.map((l) => {
      const base = toVisEdge(l);
      if (connectedEdges.has(base.id)) {
        return {
          id: base.id,
          color: base.color,
          width: base.width + 1.5,
          opacity: 1.0,
        };
      }
      return {
        id: base.id,
        color: { color: "rgba(51,65,85,0.12)", highlight: "rgba(51,65,85,0.12)" },
        width: 1,
        opacity: 0.12,
      };
    });

    nodesRef.current.update(nodeUpdates);
    edgesRef.current.update(edgeUpdates);
  }, [selected, topology]);

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

  const handleClearSelection = () => {
    setSelected(null);
    networkRef.current?.unselectAll();
  };

  const node = topology.nodes.find((n) => n.id === selected);
  const nodePorts = node?.dpid
    ? Object.values(ports).filter((p) => p.dpid === node.dpid).sort((a, b) => a.portNo - b.portNo)
    : [];

  return (
    <Panel
      title="Topology Map"
      subtitle="엔터프라이즈 8-스위치 5-Zone 망 구조 · 노드 선택 시 연관 경로 포커스"
      className="h-[580px]"
      headerAction={
        <div className="flex items-center gap-2">
          {selected && (
            <button
              type="button"
              onClick={handleClearSelection}
              className="flex items-center gap-1 rounded bg-sky-950/80 px-2 py-1 text-xs font-medium text-sky-300 border border-sky-700/60 hover:bg-sky-900 transition-colors"
            >
              <span>포커스: {selected.toUpperCase()}</span>
              <span className="text-slate-400">✕</span>
            </button>
          )}
          <div className="flex items-center gap-1 rounded-md bg-slate-800/80 p-0.5 border border-slate-700">
            <button
              type="button"
              onClick={() => handleLayoutModeChange("cluster")}
              className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                layoutMode === "cluster" ? "bg-sky-600 text-white shadow" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              5-Zone 클러스터
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
        </div>
      }
    >
      <div className="flex h-full flex-col gap-2">
        <div
          ref={containerRef}
          data-testid="topology-map"
          className="min-h-0 flex-1 rounded-lg bg-slate-950/40 border border-slate-800/60"
          aria-label="엔터프라이즈 8-스위치 5-구역 상태 지도"
        />
        <div className="flex min-h-[30px] flex-wrap items-center justify-between gap-x-4 gap-y-1 text-sm text-slate-300 px-1">
          {node ? (
            <div className="flex flex-wrap items-center gap-3">
              <span className="font-semibold text-slate-100 bg-slate-800 px-2 py-0.5 rounded border border-slate-700">
                {node.label}
              </span>
              <span className="text-xs text-slate-400">상태: <strong className="text-slate-200">{node.status}</strong></span>
              {node.ip && <span className="font-mono text-xs text-sky-400">IP: {node.ip}</span>}
              {nodePorts.map((p) => (
                <span key={p.portNo} className="font-mono text-xs bg-slate-900/80 px-1.5 py-0.5 rounded border border-slate-800 text-emerald-400">
                  p{p.portNo}{PORT_NAMES[`${p.dpid}:${p.portNo}`] ? ` (${PORT_NAMES[`${p.dpid}:${p.portNo}`]})` : ""}: {Math.round(p.pps)} PPS
                </span>
              ))}
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
              <Legend color="#10b981" label="정상" />
              <Legend color="#ef4444" label="공격 감지" />
              <Legend color="#f97316" label="격리/치료중" />
              <Legend color="#3b82f6" label="우회 경로" line />
              <Legend color="#38bdf8" label="Trunk 백본" line />
              <Legend color="#f97316" label="L4 패치 채널" line dashed />
            </div>
          )}
          <span className="text-[11px] text-slate-400 hidden sm:inline">
            ※ 노드 클릭 시 연관 링크 하이라이트 (1-Hop Focus)
          </span>
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
          className="inline-block w-4 border-t-[3px]"
          style={{ borderColor: color, borderStyle: dashed ? "dashed" : "solid" }}
        />
      ) : (
        <span className="inline-block h-2.5 w-2.5 rounded-sm border-2" style={{ borderColor: color }} />
      )}
      {label}
    </span>
  );
}
