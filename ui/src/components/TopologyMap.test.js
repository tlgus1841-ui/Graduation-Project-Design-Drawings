import { describe, expect, it } from "vitest";
import {
  EDGE_STYLE,
  NODE_COLOR,
  SEED,
  SEED_8SW,
  isBypassEdge,
  toVisEdge,
  toVisNode,
} from "./TopologyMap.jsx";
import {
  ZONE_CONFIG,
  calculateZoneBounds,
  getNodeZone,
  getSeedCoordinates,
  isLargeTopology,
} from "../lib/topologyLayout.js";

const dist = ([ax, ay], [bx, by]) => Math.hypot(bx - ax, by - ay);

describe("SEED layout (Legacy 4-Switch)", () => {
  it("places the bypass node (S3) noticeably farther from S1/S4 than the primary node (S2)", () => {
    const primaryPathLength = dist(SEED.s1, SEED.s2) + dist(SEED.s2, SEED.s4);
    const bypassPathLength = dist(SEED.s1, SEED.s3) + dist(SEED.s3, SEED.s4);
    expect(bypassPathLength).toBeGreaterThan(primaryPathLength * 1.3);
  });
});

describe("SEED_8SW layout (Enterprise 8-Switch 5-Zone)", () => {
  it("places core backbone switches S1 and S2 at top tier y = -180", () => {
    expect(SEED_8SW.s1[1]).toBe(-180);
    expect(SEED_8SW.s2[1]).toBe(-180);
  });

  it("places user switches S3/S4 on left and server switches S5/S6 on right at y = -20", () => {
    expect(SEED_8SW.s3[1]).toBe(-20);
    expect(SEED_8SW.s4[1]).toBe(-20);
    expect(SEED_8SW.s5[1]).toBe(-20);
    expect(SEED_8SW.s6[1]).toBe(-20);
    expect(SEED_8SW.s3[0]).toBeLessThan(0);
    expect(SEED_8SW.s5[0]).toBeGreaterThan(0);
  });

  it("places admin S7 and quarantine S8 along center axis x = 0", () => {
    expect(SEED_8SW.s7[0]).toBe(0);
    expect(SEED_8SW.s8[0]).toBe(0);
    expect(SEED_8SW.s7[1]).toBe(80);
    expect(SEED_8SW.s8[1]).toBe(220);
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

  it("thickens the border only while ATTACKED or QUARANTINED", () => {
    const attacked = toVisNode({ id: "s1", node_type: "switch", status: "ATTACKED", label: "S1" });
    const normal = toVisNode({ id: "s1", node_type: "switch", status: "NORMAL", label: "S1" });
    const quarantined = toVisNode({ id: "h1", node_type: "host", status: "QUARANTINED", label: "h1" });
    expect(attacked.borderWidth).toBeGreaterThan(normal.borderWidth);
    expect(quarantined.borderWidth).toBe(5);
  });

  it("seeds the position from SEED and falls back to the origin for unknown nodes", () => {
    const seeded = toVisNode({ id: "s3", node_type: "switch", status: "NORMAL", label: "S3" });
    expect([seeded.x, seeded.y]).toEqual(SEED.s3);
    const unseeded = toVisNode({ id: "ghost", node_type: "switch", status: "NORMAL", label: "?" });
    expect([unseeded.x, unseeded.y]).toEqual([0, 0]);
  });

  it("formats special roles: h_patch (diamond), h_admin, and quarantined host", () => {
    const patch = toVisNode({ id: "h_patch", node_type: "host", status: "NORMAL", label: "h_patch" }, true);
    expect(patch.shape).toBe("diamond");
    expect(patch.label).toContain("패치서버");

    const admin = toVisNode({ id: "h_admin", node_type: "host", status: "NORMAL", label: "h_admin" }, true);
    expect(admin.label).toContain("관리자");

    const quar = toVisNode({ id: "h2", node_type: "host", status: "QUARANTINED", label: "h2" }, true);
    expect(quar.label).toContain("(격리)");
  });
});

describe("toVisEdge", () => {
  const link = (status, overrides = {}) => ({
    source: "s1",
    target: "s2",
    src_port: 3,
    dst_port: 1,
    status,
    ...overrides,
  });

  it("only draws an arrowhead and a glow shadow on REROUTED links", () => {
    expect(toVisEdge(link("REROUTED")).arrows).toBeTruthy();
    expect(toVisEdge(link("REROUTED")).shadow.enabled).toBe(true);

    for (const status of ["ACTIVE", "BLOCKED"]) {
      expect(toVisEdge(link(status)).arrows).toBeUndefined();
      expect(toVisEdge(link(status)).shadow.enabled).toBe(false);
    }
  });

  it("renders QUARANTINE_SAFE edges with orange dashed style and arrow", () => {
    const safeEdge = toVisEdge({
      source: "h2",
      target: "h_patch",
      src_port: 0,
      dst_port: 80,
      status: "QUARANTINE_SAFE",
    });
    expect(safeEdge.color.color).toBe(EDGE_STYLE.QUARANTINE_SAFE.color);
    expect(safeEdge.dashes).toEqual([5, 5]);
    expect(safeEdge.arrows).toBeTruthy();
    expect(safeEdge.title).toContain("L4 격리 치료 채널");
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

describe("topologyLayout helpers", () => {
  it("determines zone accurately from ID or zone field", () => {
    expect(getNodeZone({ id: "s1" })).toBe("BACKBONE_ZONE");
    expect(getNodeZone({ id: "s2" })).toBe("BACKBONE_ZONE");
    expect(getNodeZone({ id: "s3" })).toBe("USER_ZONE");
    expect(getNodeZone({ id: "h1" })).toBe("USER_ZONE");
    expect(getNodeZone({ id: "s5" })).toBe("SERVER_ZONE");
    expect(getNodeZone({ id: "h5" })).toBe("SERVER_ZONE");
    expect(getNodeZone({ id: "s7" })).toBe("ADMIN_ZONE");
    expect(getNodeZone({ id: "h_patch" })).toBe("ADMIN_ZONE");
    expect(getNodeZone({ id: "s8" })).toBe("QUARANTINE_ZONE");
    expect(getNodeZone({ id: "h_sink" })).toBe("QUARANTINE_ZONE");
  });

  it("detects large topology (8-switch vs 4-switch)", () => {
    const sw4 = [{ id: "s1" }, { id: "s2" }, { id: "s3" }, { id: "s4" }];
    const sw8 = [
      { id: "s1" }, { id: "s2" }, { id: "s3" }, { id: "s4" },
      { id: "s5" }, { id: "s6" }, { id: "s7" }, { id: "s8" },
    ];
    expect(isLargeTopology(sw4)).toBe(false);
    expect(isLargeTopology(sw8)).toBe(true);
  });

  it("calculates zone bounds for canvas beforeDrawing painting", () => {
    const nodes = [
      { id: "s1" }, { id: "s2" },
      { id: "s3" }, { id: "h1" },
      { id: "s5" }, { id: "h5" },
      { id: "s7" }, { id: "h_patch" },
      { id: "s8" }, { id: "h_sink" },
    ];
    const bounds = calculateZoneBounds(nodes, true);
    expect(Object.keys(bounds)).toContain("BACKBONE_ZONE");
    expect(Object.keys(bounds)).toContain("USER_ZONE");
    expect(Object.keys(bounds)).toContain("SERVER_ZONE");
    expect(Object.keys(bounds)).toContain("ADMIN_ZONE");
    expect(Object.keys(bounds)).toContain("QUARANTINE_ZONE");

    for (const b of Object.values(bounds)) {
      expect(b.width).toBeGreaterThan(0);
      expect(b.height).toBeGreaterThan(0);
      expect(b.config).toBeDefined();
    }
  });
});
