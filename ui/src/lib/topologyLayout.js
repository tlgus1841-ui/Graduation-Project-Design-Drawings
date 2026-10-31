// Topology Layout Engine & Dual-Mode Coordinates (Phase 6-C-2)
// Provides 8-Switch 5-Zone layout, 4-Switch legacy fallback, and zone clustering helpers.

export const SEED_4SW = {
  h_legit: [-330, -110],
  h_attacker: [-330, 110],
  s1: [-160, 0],
  s2: [0, -140],
  s3: [60, 280],
  s4: [160, 0],
  h_server: [330, 0],
};

export const SEED_8SW = {
  // 1. Core Backbone Tier (Top Center: y = -220)
  s1: [-180, -220],
  s2: [180, -220],

  // 2. User Zone (Left Wing: S3 & S4 at y = -60, Hosts at y = 80)
  s3: [-440, -60],
  s4: [-240, -60],
  h1: [-490, 80],
  h2: [-390, 80],
  h3: [-290, 80],
  h4: [-190, 80],

  // 3. Server Zone (Right Wing: S5 & S6 at y = -60, Hosts at y = 80)
  s5: [240, -60],
  s6: [440, -60],
  h5: [190, 80], // Web Server (10.0.0.11)
  h6: [290, 80], // API Server (10.0.0.12)
  h7: [390, 80], // DB Server (10.0.0.21)
  h8: [490, 80], // Storage Server (10.0.0.22)

  // 4. Admin Zone (Bottom Left: S7 at y = 240, Hosts at y = 360)
  s7: [-200, 240],
  h_admin: [-280, 360], // Security Admin PC (10.0.0.254)
  h_patch: [-120, 360], // Security Patch Server (10.0.0.253)

  // 5. Quarantine Zone (Bottom Right: S8 at y = 240, Host at y = 360)
  s8: [200, 240],
  h_sink: [200, 360],   // Malware Analysis Sinkhole (10.0.0.250)
};

export const ZONE_CONFIG = {
  BACKBONE_ZONE: {
    id: "BACKBONE_ZONE",
    label: "중앙 백본망 (Core Backbone)",
    color: "#64748b",
    bg: "rgba(100, 116, 139, 0.08)",
    border: "rgba(100, 116, 139, 0.35)",
  },
  USER_ZONE: {
    id: "USER_ZONE",
    label: "사용자망 (User Zone)",
    color: "#3b82f6",
    bg: "rgba(59, 130, 246, 0.08)",
    border: "rgba(59, 130, 246, 0.35)",
  },
  SERVER_ZONE: {
    id: "SERVER_ZONE",
    label: "서버망 (Server Zone)",
    color: "#10b981",
    bg: "rgba(16, 185, 129, 0.08)",
    border: "rgba(16, 185, 129, 0.35)",
  },
  ADMIN_ZONE: {
    id: "ADMIN_ZONE",
    label: "관리자망 (Admin & Patch Server)",
    color: "#a855f7",
    bg: "rgba(168, 85, 247, 0.08)",
    border: "rgba(168, 85, 247, 0.35)",
  },
  QUARANTINE_ZONE: {
    id: "QUARANTINE_ZONE",
    label: "격리망 (Quarantine & Sinkhole)",
    color: "#f59e0b",
    bg: "rgba(245, 158, 11, 0.08)",
    border: "rgba(245, 158, 11, 0.35)",
  },
};

export function getNodeZone(node) {
  if (!node) return "USER_ZONE";
  if (typeof node === "object" && node.zone) {
    const z = String(node.zone).toUpperCase();
    if (z.includes("BACKBONE") || z.includes("CORE")) return "BACKBONE_ZONE";
    if (z.includes("USER")) return "USER_ZONE";
    if (z.includes("SERVER")) return "SERVER_ZONE";
    if (z.includes("ADMIN")) return "ADMIN_ZONE";
    if (z.includes("QUARANTINE")) return "QUARANTINE_ZONE";
  }

  const id = String(typeof node === "object" ? node.id : node).toLowerCase();
  if (id === "s1" || id === "s2") return "BACKBONE_ZONE";
  if (["s3", "s4", "h1", "h2", "h3", "h4", "h_legit", "h_attacker"].includes(id)) return "USER_ZONE";
  if (["s5", "s6", "h5", "h6", "h7", "h8", "h_server"].includes(id)) return "SERVER_ZONE";
  if (["s7", "h_admin", "h_patch"].includes(id)) return "ADMIN_ZONE";
  if (["s8", "h_sink"].includes(id)) return "QUARANTINE_ZONE";

  return "USER_ZONE";
}

export function isLargeTopology(nodes = []) {
  if (!Array.isArray(nodes) || nodes.length === 0) return true;
  const switchCount = nodes.filter((n) => n.node_type === "switch" || /^s\d+$/i.test(n.id)).length;
  return switchCount >= 5;
}

export function getSeedCoordinates(nodeId, isLarge = true) {
  const primarySeed = isLarge ? SEED_8SW : SEED_4SW;
  const fallbackSeed = isLarge ? SEED_4SW : SEED_8SW;
  return primarySeed[nodeId] ?? fallbackSeed[nodeId] ?? [0, 0];
}

export function calculateZoneBounds(nodes, isLarge = true, padding = 45) {
  const bounds = {};
  if (!Array.isArray(nodes)) return bounds;

  for (const node of nodes) {
    const zoneId = getNodeZone(node);
    const [x, y] = getSeedCoordinates(node.id, isLarge);

    if (!bounds[zoneId]) {
      bounds[zoneId] = {
        zoneId,
        config: ZONE_CONFIG[zoneId] || ZONE_CONFIG.USER_ZONE,
        minX: x,
        maxX: x,
        minY: y,
        maxY: y,
        nodeCount: 0,
      };
    }

    bounds[zoneId].minX = Math.min(bounds[zoneId].minX, x);
    bounds[zoneId].maxX = Math.max(bounds[zoneId].maxX, x);
    bounds[zoneId].minY = Math.min(bounds[zoneId].minY, y);
    bounds[zoneId].maxY = Math.max(bounds[zoneId].maxY, y);
    bounds[zoneId].nodeCount += 1;
  }

  // Apply padding to bounding box
  for (const b of Object.values(bounds)) {
    b.minX -= padding;
    b.maxX += padding;
    b.minY -= (padding + 15); // extra top padding for label
    b.maxY += padding;
    b.width = b.maxX - b.minX;
    b.height = b.maxY - b.minY;
  }

  return bounds;
}
