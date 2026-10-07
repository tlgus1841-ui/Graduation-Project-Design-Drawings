// Pure state reducer for the control tower.
// Input: WebSocket envelopes {type, data} defined in docs/specs/defense_scenarios.md §5.1.
// Kept free of React so it can be unit-tested with vitest.

export const MAX_EVENTS = 50;
export const MAX_HISTORY = 60; // 60 samples x 2 s = last 2 minutes per port

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
  upstream: null,
  topology: { nodes: [], links: [] },
  ports: {},
  history: {},
  events: [],
  incident: null,
  lastMessageAt: null,
};

// An incident opens on the first alert and closes when the FSM is back to NORMAL (or recalibrates).
const CLOSED_PHASES = new Set(["NORMAL", "CALIBRATING"]);

function openIncident(incident, data) {
  if (incident) return { ...incident, score: data.score, pps: data.pps, bpp: data.bpp };
  return {
    dpid: data.dpid,
    inPort: data.in_port,
    threatType: data.threat_type,
    score: data.score,
    pps: data.pps,
    bpp: data.bpp,
    detectedAt: data.timestamp,
    isolatedAt: null,
    reroutedAt: null,
  };
}

// Mitigation commands stamp the open incident so the UI can show detection-to-action time.
const COMMAND_STAMP = { ISOLATE: "isolatedAt", REROUTE: "reroutedAt" };

function stampIncident(incident, data) {
  const field = COMMAND_STAMP[data.action];
  if (!incident || !field || incident[field] != null) return incident;
  return { ...incident, [field]: data.timestamp };
}

export function portKey(dpid, portNo) {
  return `${dpid}:${portNo}`;
}

function pushEvent(events, event) {
  return [event, ...events].slice(0, MAX_EVENTS);
}

function applyPortStats(state, data) {
  const ports = { ...state.ports };
  const history = { ...state.history };
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
    if (prev) {
      history[key] = [...(history[key] ?? []), { t: data.timestamp, pps, bpp }].slice(-MAX_HISTORY);
    }
  }
  return { ...state, ports, history };
}

export function applyEnvelope(state, envelope) {
  const { type, data } = envelope ?? {};
  if (!type || !data) return state;
  const next = { ...state, lastMessageAt: data.timestamp ?? state.lastMessageAt };

  switch (type) {
    case "system:status": {
      const upstream = data.upstream ?? null;
      if (data.phase === state.phase) return { ...next, mode: data.mode, upstream };
      const incident = CLOSED_PHASES.has(data.phase) ? null : state.incident;
      const events = state.phase
        ? pushEvent(state.events, {
            id: `phase-${data.timestamp}-${data.phase}`,
            kind: "phase",
            ts: data.timestamp,
            title: `상태 전환: ${PHASE_LABELS[data.phase] ?? data.phase}`,
            detail: `${PHASE_LABELS[state.phase] ?? state.phase} → ${PHASE_LABELS[data.phase] ?? data.phase}`,
          })
        : state.events;
      return { ...next, phase: data.phase, mode: data.mode, upstream, events, incident };
    }
    case "sdn:stats:port":
      return applyPortStats(next, data);
    case "sdn:anomaly:alert":
      return {
        ...next,
        incident: openIncident(state.incident, data),
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
        incident: stampIncident(state.incident, data),
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
