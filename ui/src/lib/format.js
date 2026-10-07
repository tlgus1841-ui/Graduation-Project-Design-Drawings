// Shared display helpers for the control tower.

export const PORT_NAMES = {
  "1:1": "H_legit", "1:2": "H_attacker", "1:3": "→ S2", "1:4": "→ S3",
  "2:1": "→ S1", "2:2": "→ S4", "3:1": "→ S1", "3:2": "→ S4",
  "4:1": "H_server", "4:2": "→ S2", "4:3": "→ S3",
};

// HH:MM:SS.mmm in local time; the security timeline is reviewed at millisecond resolution.
export function clockMs(ts) {
  if (ts == null) return "--:--:--.---";
  const d = new Date(ts * 1000);
  const hms = [d.getHours(), d.getMinutes(), d.getSeconds()].map((n) => String(n).padStart(2, "0")).join(":");
  return `${hms}.${String(d.getMilliseconds()).padStart(3, "0")}`;
}

export const fmt = (n) => Math.round(n).toLocaleString("ko-KR");
