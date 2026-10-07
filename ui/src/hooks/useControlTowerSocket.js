import { useEffect, useReducer, useRef, useState } from "react";
import { applyEnvelope, initialState } from "../lib/towerState.js";

// CONNECTING → CONNECTED; on drop → RECONNECTING (retries with backoff);
// after MAX_SOFT_RETRIES consecutive failures the badge shows DISCONNECTED but retries continue.
const MAX_SOFT_RETRIES = 5;
const MAX_BACKOFF_MS = 10000;
const PING_INTERVAL_MS = 15000;

export function resolveWsUrl() {
  const fromEnv = import.meta.env.VITE_WS_URL;
  if (fromEnv) return fromEnv;
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${window.location.hostname}:8000/ws`;
}

export function useControlTowerSocket(url = resolveWsUrl()) {
  const [state, dispatch] = useReducer(applyEnvelope, initialState);
  const [status, setStatus] = useState("CONNECTING");
  const [retries, setRetries] = useState(0);
  const socketRef = useRef(null);

  useEffect(() => {
    let closedByUs = false;
    let attempt = 0;
    let retryTimer = null;
    let pingTimer = null;
    // One telemetry tick arrives as ~6 frames (a stats message per switch + status + topology).
    // Queue them and apply once per animation frame so charts and the map redraw once, not six times.
    let pending = [];
    let frame = null;
    const flush = () => {
      frame = null;
      const batch = pending;
      pending = [];
      if (batch.length) dispatch({ type: "batch", data: batch });
    };

    const connect = () => {
      const ws = new WebSocket(url);
      socketRef.current = ws;

      ws.onopen = () => {
        attempt = 0;
        setRetries(0);
        setStatus("CONNECTED");
        pingTimer = setInterval(() => ws.readyState === WebSocket.OPEN && ws.send("ping"), PING_INTERVAL_MS);
      };

      ws.onmessage = (event) => {
        if (event.data === "pong") return;
        try {
          pending.push(JSON.parse(event.data));
        } catch {
          return; // Ignore malformed frames; the backend only sends contract-validated JSON.
        }
        if (frame == null) frame = requestAnimationFrame(flush);
      };

      ws.onclose = () => {
        clearInterval(pingTimer);
        if (closedByUs) return;
        attempt += 1;
        setRetries(attempt);
        setStatus(attempt > MAX_SOFT_RETRIES ? "DISCONNECTED" : "RECONNECTING");
        retryTimer = setTimeout(connect, Math.min(1000 * 2 ** (attempt - 1), MAX_BACKOFF_MS));
      };

      ws.onerror = () => ws.close();
    };

    connect();
    return () => {
      closedByUs = true;
      if (frame != null) cancelAnimationFrame(frame);
      clearTimeout(retryTimer);
      clearInterval(pingTimer);
      socketRef.current?.close();
    };
  }, [url]);

  return { state, status, retries, url };
}
