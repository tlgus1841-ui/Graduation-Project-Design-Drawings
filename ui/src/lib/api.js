// REST helpers for the control tower backend (same host as the WebSocket, port 8000 by default).

export function resolveApiBase() {
  const fromEnv = import.meta.env.VITE_API_URL;
  if (fromEnv) return fromEnv.replace(/\/$/, "");
  return `${window.location.protocol}//${window.location.hostname}:8000`;
}

// Week 13: operator emergency ISOLATE / RESTORE. Throws Error(detail) on refusal.
export async function sendManualControl({ action, dpid, port, reason, operator, token }) {
  const res = await fetch(`${resolveApiBase()}/api/control/manual`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { "X-Admin-Token": token } : {}) },
    body: JSON.stringify({ action, dpid, port, reason, operator }),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = Array.isArray(body.detail) ? "입력값을 확인해 주세요." : body.detail;
    throw new Error(detail || `요청 실패 (${res.status})`);
  }
  return body;
}
