// Shared display helpers for the control tower (Phase 6-C-2).

// Enterprise 8-Switch & Legacy 4-Switch Port Display Names
export const PORT_NAMES = {
  // 8-Switch Core 1 (S1)
  "1:1": "Core S2", "1:2": "User S3", "1:3": "Server S5", "1:4": "Admin S7", "1:5": "Quar S8",
  // 8-Switch Core 2 (S2)
  "2:1": "Core S1", "2:2": "User S4", "2:3": "Server S6", "2:4": "Admin S7", "2:5": "Quar S8",
  // User Edge A (S3)
  "3:1": "H1 (사무1)", "3:2": "H2 (사무2)", "3:99": "Trunk S1",
  // User Edge B (S4)
  "4:1": "H3 (영업1)", "4:2": "H4 (영업2)", "4:99": "Trunk S2",
  // Server Edge A (S5)
  "5:1": "H5 (Web)", "5:2": "H6 (API)", "5:99": "Trunk S1",
  // Server Edge B (S6)
  "6:1": "H7 (DB)", "6:2": "H8 (Backup)", "6:99": "Trunk S2",
  // Admin Edge (S7)
  "7:1": "H_Admin", "7:2": "H_Patch", "7:98": "Trunk S1", "7:99": "Trunk S2",
  // Quarantine Edge (S8)
  "8:1": "H_Sinkhole", "8:98": "Trunk S1", "8:99": "Trunk S2",
};

// Legacy 4-switch fallback port names
export const PORT_NAMES_4SW = {
  "1:1": "H_legit", "1:2": "H_attacker", "1:3": "→ S2", "1:4": "→ S3",
  "2:1": "→ S1", "2:2": "→ S4", "3:1": "→ S1", "3:2": "→ S4",
  "4:1": "H_server", "4:2": "→ S2", "4:3": "→ S3",
};

export function getPortLabel(key, isLarge = true) {
  if (!key) return "-";
  if (isLarge && PORT_NAMES[key]) return PORT_NAMES[key];
  if (!isLarge && PORT_NAMES_4SW[key]) return PORT_NAMES_4SW[key];
  return PORT_NAMES[key] ?? PORT_NAMES_4SW[key] ?? "-";
}

// HH:MM:SS.mmm in local time; the security timeline is reviewed at millisecond resolution.
export function clockMs(ts) {
  if (ts == null) return "--:--:--.---";
  const d = new Date(ts * 1000);
  const hms = [d.getHours(), d.getMinutes(), d.getSeconds()].map((n) => String(n).padStart(2, "0")).join(":");
  return `${hms}.${String(d.getMilliseconds()).padStart(3, "0")}`;
}

// Gap between two unix-second stamps as "1,234 ms"; "-" until both exist.
export function elapsedMs(from, to) {
  if (from == null || to == null) return "-";
  return `${Math.max(0, Math.round((to - from) * 1000)).toLocaleString("ko-KR")} ms`;
}

export const fmt = (n) => Math.round(n).toLocaleString("ko-KR");
