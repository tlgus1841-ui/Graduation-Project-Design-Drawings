// 12주차 성능 검수: 관제탑이 공격·격리·복구 한 사이클 동안 60fps를 유지하는지 측정한다.
//
// 백엔드(더미 데이터)와 빌드된 화면을 띄우고, 브라우저 안에서 requestAnimationFrame 간격을 기록해
// 평균 FPS, 프레임 시간 p95·p99, 끊김 프레임(> 33.3ms) 비율, 50ms 넘는 긴 작업 수를 계산한다.
// CPU를 4배 느리게 만든 조건(저사양 노트북 가정)도 함께 잰다.
//
// 실행 (저장소 루트에서 uv sync, ui에서 npm install 후):
//   cd ui && npm run build && npm run perf
// 결과 JSON 경로: PERF_OUT (기본 ui/perf-result.json)

import { spawn, execSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const UI = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const REPO = resolve(UI, "..");
const SECONDS = Number(process.env.PERF_SECONDS ?? 80); // 보정 15s + 정상 20 + 공격 6 + 격리 20 + 복구 10 + 여유
const THROTTLES = (process.env.PERF_THROTTLES ?? "1,4").split(",").map(Number);
const OUT = process.env.PERF_OUT ?? resolve(UI, "perf-result.json");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function start(cmd, args, cwd) {
  return spawn(cmd, args, { cwd, stdio: "ignore", detached: true });
}

async function waitFor(url) {
  for (let i = 0; i < 80; i += 1) {
    try { await fetch(url); return; } catch { await sleep(500); }
  }
  throw new Error(`not reachable: ${url}`);
}

// Runs inside the page: record frame gaps and long tasks until stop() is called.
function installProbe() {
  const gaps = [];
  const longTasks = [];
  const phases = new Set();
  let last = performance.now();
  let running = true;
  const tick = (now) => {
    gaps.push(now - last);
    last = now;
    const p = document.querySelector('[data-testid="phase-badge"]')?.textContent;
    if (p) phases.add(p);
    if (running) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
  new PerformanceObserver((list) => list.getEntries().forEach((e) => longTasks.push(e.duration)))
    .observe({ type: "longtask", buffered: false });
  window.__probe = {
    stop() {
      running = false;
      return { gaps: gaps.slice(1), longTasks, phases: [...phases] };
    },
  };
}

function summarize({ gaps, longTasks, phases }) {
  const sorted = [...gaps].sort((a, b) => a - b);
  const pct = (q) => sorted[Math.min(sorted.length - 1, Math.floor(q * sorted.length))];
  const total = gaps.reduce((a, b) => a + b, 0);
  return {
    frames: gaps.length,
    avgFps: Math.round((gaps.length / total) * 1000 * 10) / 10,
    p95FrameMs: Math.round(pct(0.95) * 10) / 10,
    p99FrameMs: Math.round(pct(0.99) * 10) / 10,
    maxFrameMs: Math.round(sorted.at(-1) * 10) / 10,
    jankPercent: Math.round((gaps.filter((g) => g > 1000 / 30).length / gaps.length) * 1000) / 10,
    longTasks: longTasks.length,
    longestTaskMs: Math.round(Math.max(0, ...longTasks)),
    phasesSeen: phases,
  };
}

const backend = start("uv", ["run", "uvicorn", "api.main:app", "--port", "8000"], REPO);
const preview = start("npx", ["vite", "preview", "--port", "4173", "--strictPort"], UI);
const browser = await chromium.launch();
const results = {};
try {
  await waitFor("http://127.0.0.1:8000/api/health");
  await waitFor("http://127.0.0.1:4173");
  for (const rate of THROTTLES) {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const cdp = await page.context().newCDPSession(page);
    await cdp.send("Emulation.setCPUThrottlingRate", { rate });
    await page.goto("http://localhost:4173");
    await page.waitForSelector('[data-status="CONNECTED"]', { timeout: 20000 });
    await page.evaluate(installProbe);
    await sleep(SECONDS * 1000);
    results[`cpu_x${rate}`] = summarize(await page.evaluate(() => window.__probe.stop()));
    console.log(`CPU x${rate}:`, JSON.stringify(results[`cpu_x${rate}`]));
    await page.close();
  }
  writeFileSync(OUT, JSON.stringify({ seconds: SECONDS, measuredAt: new Date().toISOString(), results }, null, 2));
  console.log(`saved ${OUT}`);
} finally {
  await browser.close();
  for (const p of [backend, preview]) { try { process.kill(-p.pid, "SIGTERM"); } catch { /* already gone */ } }
  try { execSync("pkill -f 'uvicorn api[.]main:app'"); } catch { /* none left */ }
}
