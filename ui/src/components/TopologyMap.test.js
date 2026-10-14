import { describe, expect, it } from "vitest";
import { EDGE_STYLE, NODE_COLOR, SEED, isBypassEdge, toVisEdge, toVisNode } from "./TopologyMap.jsx";

const dist = ([ax, ay], [bx, by]) => Math.hypot(bx - ax, by - ay);

describe("SEED layout", () => {
  it("places the bypass node (S3) noticeably farther from S1/S4 than the primary node (S2)", () => {
    // Regression guard for the demo-rehearsal feedback: S2/S3 used to be a plain vertical
    // mirror, so the "bypass" route rendered exactly as long as the primary one and nobody
    // could tell it was a detour. This pins the fix down numerically so a future edit can't
    // silently turn S3 back into a symmetric mirror of S2.
    const primaryPathLength = dist(SEED.s1, SEED.s2) + dist(SEED.s2, SEED.s4);
    const bypassPathLength = dist(SEED.s1, SEED.s3) + dist(SEED.s3, SEED.s4);
    expect(bypassPathLength).toBeGreaterThan(primaryPathLength * 1.3);
  });
});

describe("isBypassEdge", () => {
  it("is true for both links touching S3 (the bypass switch)", () => {
    expect(isBypassEdge({ source: "s1", target: "s3" })).toBe(true);
    expect(isBypassEdge({ source: "s3", target: "s4" })).toBe(true);
  });

  it("is false for the primary path and access links", () => {
    expect(isBypassEdge({ source: "s1", target: "s2" })).toBe(false);
    expect(isBypassEdge({ source: "s2", target: "s4" })).toBe(false);
    expect(isBypassEdge({ source: "s1", target: "h_legit" })).toBe(false);
  });
});

describe("toVisNode", () => {
  it("maps each status to the spec §5 colour", () => {
    for (const [status, color] of Object.entries(NODE_COLOR)) {
      const node = toVisNode({ id: "s1", node_type: "switch", status, label: "S1" });
      expect(node.color.border).toBe(color);
    }
  });

  it("falls back to the NORMAL colour for an unknown status", () => {
    const node = toVisNode({ id: "s1", node_type: "switch", status: "SOMETHING_NEW", label: "S1" });
    expect(node.color.border).toBe(NODE_COLOR.NORMAL);
  });

  it("thickens the border only while ATTACKED", () => {
    const attacked = toVisNode({ id: "s1", node_type: "switch", status: "ATTACKED", label: "S1" });
    const normal = toVisNode({ id: "s1", node_type: "switch", status: "NORMAL", label: "S1" });
    expect(attacked.borderWidth).toBeGreaterThan(normal.borderWidth);
  });

  it("seeds the position from SEED and falls back to the origin for unknown nodes", () => {
    const seeded = toVisNode({ id: "s3", node_type: "switch", status: "NORMAL", label: "S3" });
    expect([seeded.x, seeded.y]).toEqual(SEED.s3);
    const unseeded = toVisNode({ id: "ghost", node_type: "switch", status: "NORMAL", label: "?" });
    expect([unseeded.x, unseeded.y]).toEqual([0, 0]);
  });
});

describe("toVisEdge", () => {
  const link = (status, overrides = {}) => ({
    source: "s1", target: "s2", src_port: 3, dst_port: 1, status, ...overrides,
  });

  it("only draws an arrowhead and a glow shadow on REROUTED links", () => {
    expect(toVisEdge(link("REROUTED")).arrows).toBeTruthy();
    expect(toVisEdge(link("REROUTED")).shadow.enabled).toBe(true);

    for (const status of ["ACTIVE", "BLOCKED"]) {
      expect(toVisEdge(link(status)).arrows).toBeUndefined();
      expect(toVisEdge(link(status)).shadow.enabled).toBe(false);
    }
  });

  it("curves only the bypass links (touching S3), regardless of status", () => {
    const bypass = toVisEdge({ source: "s1", target: "s3", src_port: 4, dst_port: 1, status: "ACTIVE" });
    const primary = toVisEdge({ source: "s1", target: "s2", src_port: 3, dst_port: 1, status: "ACTIVE" });
    expect(bypass.smooth.enabled).toBe(true);
    expect(primary.smooth.enabled).toBe(false);
  });

  it("matches the spec §5 colour/width/dash per status", () => {
    expect(toVisEdge(link("ACTIVE"))).toMatchObject({ color: { color: EDGE_STYLE.ACTIVE.color }, dashes: false });
    expect(toVisEdge(link("BLOCKED"))).toMatchObject({ color: { color: EDGE_STYLE.BLOCKED.color }, dashes: [8, 8] });
    expect(toVisEdge(link("REROUTED"))).toMatchObject({ color: { color: EDGE_STYLE.REROUTED.color } });
  });

  it("falls back to the ACTIVE style for an unknown status", () => {
    expect(toVisEdge(link("SOMETHING_NEW")).color.color).toBe(EDGE_STYLE.ACTIVE.color);
  });
});
