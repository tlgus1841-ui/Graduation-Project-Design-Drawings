// Pure state reducer for the control tower.
// Input: WebSocket envelopes {type, data} defined in docs/specs/defense_scenarios.md §5.1.
// Kept free of React so it can be unit-tested with vitest.

export const MAX_EVENTS = 50;

export const PHASE_LABELS = {
  CALIBRATING: "SYSTEM CALIBRATING",
  NORMAL: "NORMAL",
  ATTACK_DETECTED: "UNDER ATTACK",
  MITIGATED: "MITIGATED",
  COOLDOWN_VERIFY: "RESTORING",
};

export const initialState = {
  phase: null,
  mode: null,
  topology: { nodes: [], links: [] },
  ports: {},
  events: [],
  lastMessageAt: null,
};

export function portKey(dpid, portNo) {
  return `${dpid}:${portNo}`;
}

function pushEvent(events, event) {
  return [event, ...events].slice(0, MAX_EVENTS);
}

function applyPortStats(state, data) {
  const ports = { ...state.ports };
  for (const item of data.stats ?? []) {
    const key = portKey(item.dpid, item.port_no);
    const prev = ports[key];
    let pps = 0;
    let bps = 0;
    let bpp = 0;
    if (prev && data.timestamp > prev.timestamp) {
      const dt = data.timestamp - prev.timestamp;
      const dPackets = Math.max(item.rx_packets - prev.rx_packets, 0);
      const dBytes = Math.max(item.rx_bytes - prev.rx_bytes, 0);
      pps = dPackets / dt;
      bps = (dBytes * 8) / dt;
      bpp = dPackets > 0 ? dBytes / dPackets : 0;
    }
    ports[key] = {
      dpid: item.dpid,
      portNo: item.port_no,
      rx_packets: item.rx_packets,
      rx_bytes: item.rx_bytes,
      timestamp: data.timestamp,
      pps,
      bps,
      bpp,
    };
  }
  return { ...state, ports };
}

export function applyEnvelope(state, envelope) {
  const { type, data } = envelope ?? {};
  if (!type || !data) return state;
  const next = { ...state, lastMessageAt: data.timestamp ?? state.lastMessageAt };

  switch (type) {
    case "system:status": {
      if (data.phase === state.phase) return { ...next, mode: data.mode };
      const events = state.phase
        ? pushEvent(state.events, {
            id: `phase-${data.timestamp}-${data.phase}`,
            kind: "phase",
            ts: data.timestamp,
            title: `상태 전환: ${PHASE_LABELS[data.phase] ?? data.phase}`,
            detail: `${PHASE_LABELS[state.phase] ?? state.phase} → ${PHASE_LABELS[data.phase] ?? data.phase}`,
          })
        : state.events;
      return { ...next, phase: data.phase, mode: data.mode, events };
    }
    case "sdn:stats:port":
      return applyPortStats(next, data);
    case "sdn:anomaly:alert":
      return {
        ...next,
        events: pushEvent(state.events, {
          id: `alert-${data.timestamp}-${data.dpid}-${data.in_port}`,
          kind: "alert",
          ts: data.timestamp,
          title: `${data.threat_type} 탐지 · S${data.dpid}:${data.in_port}`,
          detail: `score ${data.score.toFixed(2)} · ${Math.round(data.pps)} PPS · BPP ${Math.round(data.bpp)}B`,
        }),
      };
    case "sdn:control:command":
      return {
        ...next,
        events: pushEvent(state.events, {
          id: data.command_id,
          kind: "command",
          ts: data.timestamp,
          title: `${data.action} · S${data.target_dpid}:${data.target_port}`,
          detail: data.reason,
        }),
      };
    case "sdn:topology:sync":
      return { ...next, topology: { nodes: data.nodes ?? [], links: data.links ?? [] } };
    default:
      return state;
  }
}
