import { describe, expect, it } from "vitest";
import { MAX_EVENTS, MAX_HISTORY, applyEnvelope, initialState, portKey } from "./towerState.js";

const stats = (timestamp, rxPackets, rxBytes) => ({
  type: "sdn:stats:port",
  data: {
    timestamp,
    dpid: 1,
    stats: [{ dpid: 1, port_no: 2, rx_packets: rxPackets, tx_packets: 0, rx_bytes: rxBytes, tx_bytes: 0, rx_errors: 0, duration_sec: 10 }],
  },
});

describe("applyEnvelope", () => {
  it("derives PPS, bps and BPP from cumulative counters", () => {
    let s = applyEnvelope(initialState, stats(100, 1000, 800000));
    s = applyEnvelope(s, stats(102, 7000, 1184000)); // +6000 pkts, +384000 B in 2 s
    const p = s.ports[portKey(1, 2)];
    expect(p.pps).toBe(3000);
    expect(p.bpp).toBe(64);
    expect(p.bps).toBe((384000 * 8) / 2);
  });

  it("keeps a bounded per-port history for charts", () => {
    let s = initialState;
    for (let i = 0; i <= MAX_HISTORY + 5; i += 1) s = applyEnvelope(s, stats(100 + 2 * i, 1000 + 6000 * i, 64000 * (i + 1)));
    const h = s.history[portKey(1, 2)];
    expect(h).toHaveLength(MAX_HISTORY);
    expect(h.at(-1).pps).toBe(3000);
    expect(h.at(-1).t).toBe(100 + 2 * (MAX_HISTORY + 5));
  });

  it("first sample has no rate yet", () => {
    const s = applyEnvelope(initialState, stats(100, 1000, 800000));
    expect(s.ports[portKey(1, 2)].pps).toBe(0);
  });

  it("records phase changes but not the very first status", () => {
    let s = applyEnvelope(initialState, { type: "system:status", data: { phase: "NORMAL", mode: "mock", timestamp: 1 } });
    expect(s.phase).toBe("NORMAL");
    expect(s.events).toHaveLength(0);
    s = applyEnvelope(s, { type: "system:status", data: { phase: "ATTACK_DETECTED", mode: "mock", timestamp: 2 } });
    expect(s.events[0].kind).toBe("phase");
    expect(s.events[0].detail).toBe("NORMAL → UNDER ATTACK");
  });

  it("tracks the live Redis link state", () => {
    let s = applyEnvelope(initialState, { type: "system:status", data: { phase: null, mode: "live", upstream: "disconnected", timestamp: 1 } });
    expect(s.upstream).toBe("disconnected");
    s = applyEnvelope(s, { type: "system:status", data: { phase: null, mode: "live", upstream: "connected", timestamp: 2 } });
    expect(s.upstream).toBe("connected");
  });

  it("adds alerts and commands newest-first and caps the feed", () => {
    let s = initialState;
    for (let i = 0; i < MAX_EVENTS + 5; i += 1) {
      s = applyEnvelope(s, {
        type: "sdn:control:command",
        data: { timestamp: i, command_id: `c${i}`, action: "ISOLATE", target_dpid: 1, target_port: 2, reason: "test", priority: 100 },
      });
    }
    expect(s.events).toHaveLength(MAX_EVENTS);
    expect(s.events[0].id).toBe(`c${MAX_EVENTS + 4}`);

    s = applyEnvelope(s, {
      type: "sdn:anomaly:alert",
      data: { timestamp: 99, dpid: 1, in_port: 2, threat_type: "SYN_FLOOD_SPOOFING", score: -0.8, pps: 3000, bps: 192000, bpp: 64, metadata: {} },
    });
    expect(s.events[0].kind).toBe("alert");
    expect(s.events[0].title).toContain("S1:2");
  });

  it("opens an incident on the first alert and closes it back in NORMAL", () => {
    const status = (phase, timestamp) => ({ type: "system:status", data: { phase, mode: "mock", timestamp } });
    const alert = (timestamp, score) => ({
      type: "sdn:anomaly:alert",
      data: { timestamp, dpid: 1, in_port: 2, threat_type: "SYN_FLOOD_SPOOFING", score, pps: 3000, bps: 192000, bpp: 64, metadata: {} },
    });
    let s = applyEnvelope(initialState, status("NORMAL", 1));
    s = applyEnvelope(s, status("ATTACK_DETECTED", 10.123));
    s = applyEnvelope(s, alert(10.123, -0.8));
    s = applyEnvelope(s, alert(12.5, -0.9));
    expect(s.incident).toMatchObject({ dpid: 1, inPort: 2, detectedAt: 10.123, score: -0.9 });
    s = applyEnvelope(s, status("MITIGATED", 13));
    expect(s.incident.inPort).toBe(2);
    const command = (action, timestamp) => ({
      type: "sdn:control:command",
      data: { timestamp, command_id: `${action}-${timestamp}`, action, target_dpid: 1, target_port: 2, reason: "t", priority: 100 },
    });
    s = applyEnvelope(s, command("REROUTE", 13.004));
    s = applyEnvelope(s, command("ISOLATE", 13.006));
    s = applyEnvelope(s, command("ISOLATE", 20)); // a repeat must not move the first stamp
    expect(s.incident).toMatchObject({ reroutedAt: 13.004, isolatedAt: 13.006 });
    s = applyEnvelope(s, status("NORMAL", 40));
    expect(s.incident).toBeNull();
  });

  it("replaces topology on sync and ignores unknown types", () => {
    const topo = { nodes: [{ id: "s1", status: "ATTACKED" }], links: [] };
    let s = applyEnvelope(initialState, { type: "sdn:topology:sync", data: { timestamp: 1, ...topo } });
    expect(s.topology.nodes[0].status).toBe("ATTACKED");
    expect(applyEnvelope(s, { type: "unknown", data: {} })).toBe(s);
    expect(applyEnvelope(s, null)).toBe(s);
  });
});
