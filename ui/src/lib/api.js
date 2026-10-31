// REST helpers for the control tower backend (same host as the WebSocket, port 8000 by default).

export function resolveApiBase() {
  const fromEnv = import.meta.env.VITE_API_URL;
  if (fromEnv) return fromEnv.replace(/\/$/, "");
  // Vite 개발 서버(포트 5173)에서는 포트 8000의 API 서버로 직결
  if (typeof window !== "undefined" && window.location && window.location.port === "5173") {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  // 프로덕션 / Nginx 리버스 프록시 환경에서는 동일 Origin 사용
  if (typeof window !== "undefined" && window.location && window.location.origin) {
    return window.location.origin;
  }
  return "http://localhost:8000";
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

// Special-situation relearn approval: the AI worker relearns traffic volume for `minutes`, then reverts.
// dpid/port 0 = every watched access port. Throws Error(detail) on refusal.
export async function sendRelearn({ minutes, dpid = 0, port = 0, reason, operator, token }) {
  const res = await fetch(`${resolveApiBase()}/api/control/relearn`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { "X-Admin-Token": token } : {}) },
    body: JSON.stringify({ minutes, dpid, port, reason, operator }),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = Array.isArray(body.detail) ? "입력값을 확인해 주세요." : body.detail;
    throw new Error(detail || `요청 실패 (${res.status})`);
  }
  return body;
}

// Quarantine Release (Human-in-the-loop): operator approves release of a quarantined host.
export async function sendQuarantineRelease({ target_ip, reason, operator, token }) {
  const res = await fetch(`${resolveApiBase()}/api/control/quarantine/release`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { "X-Admin-Token": token } : {}) },
    body: JSON.stringify({ target_ip, reason, operator }),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = Array.isArray(body.detail) ? "입력값을 확인해 주세요." : body.detail;
    throw new Error(detail || `요청 실패 (${res.status})`);
  }
  return body;
}
