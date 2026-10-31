import { memo, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { sendManualControl, sendQuarantineRelease } from "../lib/api.js";
import { getNodeZone } from "../lib/topologyLayout.js";

// Enterprise 8-Switch & 4-Switch default targets
const DEFAULT_HOST_PORTS = {
  "10.0.0.1": { dpid: 3, port: 1, label: "h1 (10.0.0.1 - 사무1)", zone: "USER_ZONE" },
  "10.0.0.2": { dpid: 3, port: 2, label: "h2 (10.0.0.2 - 사무2)", zone: "USER_ZONE" },
  "10.0.0.3": { dpid: 4, port: 1, label: "h3 (10.0.0.3 - 영업1)", zone: "USER_ZONE" },
  "10.0.0.4": { dpid: 4, port: 2, label: "h4 (10.0.0.4 - 영업2)", zone: "USER_ZONE" },
  "10.0.0.11": { dpid: 5, port: 1, label: "h5 (10.0.0.11 - Web)", zone: "SERVER_ZONE", protected: true },
  "10.0.0.12": { dpid: 5, port: 2, label: "h6 (10.0.0.12 - API)", zone: "SERVER_ZONE", protected: true },
  "10.0.0.21": { dpid: 6, port: 1, label: "h7 (10.0.0.21 - DB)", zone: "SERVER_ZONE", protected: true },
  "10.0.0.22": { dpid: 6, port: 2, label: "h8 (10.0.0.22 - Backup)", zone: "SERVER_ZONE", protected: true },
  "10.0.0.254": { dpid: 7, port: 1, label: "h_admin (10.0.0.254 - 관리자)", zone: "ADMIN_ZONE", protected: true },
  "10.0.0.253": { dpid: 7, port: 2, label: "h_patch (10.0.0.253 - 패치서버)", zone: "ADMIN_ZONE", protected: true },
  "10.0.0.250": { dpid: 8, port: 1, label: "h_sink (10.0.0.250 - 싱크홀)", zone: "QUARANTINE_ZONE" },
};

const ACTIONS = {
  ISOLATE: "포트 격리",
  RESTORE: "포트 복원",
  RELEASE: "단말 격리 해제 (QUARANTINE Release)",
};

function ManualControl({ topology }) {
  const [open, setOpen] = useState(false);
  const [notice, setNotice] = useState(null);
  const triggerRef = useRef(null);

  const close = (result) => {
    setOpen(false);
    if (result) setNotice(result);
    triggerRef.current?.focus();
  };

  useEffect(() => {
    if (!notice) return undefined;
    const t = setTimeout(() => setNotice(null), 6000);
    return () => clearTimeout(t);
  }, [notice]);

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen(true)}
        data-testid="manual-control-open"
        className="rounded-md border border-red-500/70 px-3 py-1 text-sm font-bold text-red-200 hover:bg-red-500/15 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
      >
        비상 수동 제어
      </button>
      {open && createPortal(<ManualControlDialog onClose={close} topology={topology} />, document.body)}
      {notice &&
        createPortal(
          <div
            role="status"
            data-testid="manual-control-notice"
            className="fixed bottom-4 left-4 z-30 rounded-lg border border-amber-500 bg-slate-900 px-4 py-3 text-sm text-amber-100 shadow-xl"
          >
            수동 {ACTIONS[notice.command.action] || notice.command.action} 명령 전송 ·{" "}
            {notice.command.target_ip ? notice.command.target_ip : `S${notice.command.target_dpid}:${notice.command.target_port}`}
            {notice.auto_isolation_hold_sec > 0 && ` · ${notice.auto_isolation_hold_sec}초간 자동 재격리 보류`}
            <span className="ml-2 font-mono text-xs text-amber-300">{notice.command.command_id}</span>
          </div>,
          document.body,
        )}
    </>
  );
}

export default memo(ManualControl);

function ManualControlDialog({ onClose, topology }) {
  const [action, setAction] = useState("ISOLATE");
  const [target, setTarget] = useState("3:2");
  const [reason, setReason] = useState("");
  const [operator, setOperator] = useState("admin");
  const [token, setToken] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const firstRef = useRef(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    firstRef.current?.focus();
    const onKey = (e) => e.key === "Escape" && onCloseRef.current(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Build target items grouped by zone
  const targetGroups = useMemo(() => {
    const nodes = topology?.nodes || [];
    const isLegacy = nodes.length > 0 && nodes.filter((n) => /^s\d+$/i.test(n.id)).length <= 4;

    if (isLegacy) {
      return {
        "레거시 사용자망": [
          { value: "1:2", ip: "10.0.0.2", label: "S1:2 · H_attacker (10.0.0.2)", normal: false },
          { value: "1:1", ip: "10.0.0.1", label: "S1:1 · H_legit (10.0.0.1)", normal: true, protected: true },
        ],
        "서버망": [
          { value: "4:1", ip: "10.0.0.4", label: "S4:1 · H_server (10.0.0.4)", normal: true, protected: true },
        ],
      };
    }

    // 8-switch grouped targets
    const groups = {
      "사용자망 (User Zone)": [],
      "서버망 (Server Zone - 보호 대상)": [],
      "관리자망 (Admin Zone - 보호 대상)": [],
      "격리망 (Quarantine Zone)": [],
    };

    for (const [ip, info] of Object.entries(DEFAULT_HOST_PORTS)) {
      const item = {
        value: `${info.dpid}:${info.port}`,
        ip,
        label: `S${info.dpid}:${info.port} · ${info.label}`,
        protected: Boolean(info.protected),
      };

      if (info.zone === "USER_ZONE") groups["사용자망 (User Zone)"].push(item);
      else if (info.zone === "SERVER_ZONE") groups["서버망 (Server Zone - 보호 대상)"].push(item);
      else if (info.zone === "ADMIN_ZONE") groups["관리자망 (Admin Zone - 보호 대상)"].push(item);
      else if (info.zone === "QUARANTINE_ZONE") groups["격리망 (Quarantine Zone)"].push(item);
    }

    return groups;
  }, [topology]);

  const allTargets = useMemo(() => Object.values(targetGroups).flat(), [targetGroups]);

  // Set default target if current target is not in list
  useEffect(() => {
    if (allTargets.length > 0 && !allTargets.some((t) => t.value === target)) {
      setTarget(allTargets[0].value);
    }
  }, [allTargets, target]);

  // Any change to what will be sent requires re-confirming.
  useEffect(() => setConfirmed(false), [action, target]);

  const currentTargetItem = allTargets.find((x) => x.value === target) || allTargets[0];
  const [dpid, port] = (target || "3:2").split(":").map(Number);
  const isProtectedIsolate = action === "ISOLATE" && Boolean(currentTargetItem?.protected);
  const valid = !isProtectedIsolate && reason.trim().length >= 3 && operator.trim().length > 0 && confirmed;

  const submit = async (e) => {
    e.preventDefault();
    if (!valid || busy) return;
    setBusy(true);
    setError(null);
    try {
      if (action === "RELEASE") {
        onClose(
          await sendQuarantineRelease({
            target_ip: currentTargetItem?.ip || "10.0.0.2",
            reason: reason.trim(),
            operator: operator.trim(),
            token,
          }),
        );
      } else {
        onClose(
          await sendManualControl({
            action,
            dpid,
            port,
            reason: reason.trim(),
            operator: operator.trim(),
            token,
          }),
        );
      }
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/70 p-4"
      onClick={() => onClose(null)}
    >
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby="manual-title"
        data-testid="manual-control-dialog"
        onSubmit={submit}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg space-y-4 rounded-xl border-2 border-red-500/70 bg-slate-900 p-5 shadow-2xl"
      >
        <div>
          <p className="font-mono text-xs font-bold tracking-widest text-red-300">EMERGENCY MANUAL CONTROL</p>
          <h2 id="manual-title" className="text-lg font-bold text-slate-50">
            비상 수동 제어 (엔터프라이즈 존)
          </h2>
          <p className="mt-1 text-sm text-slate-300">
            자동 방어와 별개로 포트를 직접 격리하거나 복원합니다. 모든 조작은 보안 감사 로그에 영구 기록됩니다.
          </p>
        </div>

        <fieldset className="space-y-1">
          <legend className="text-sm font-semibold text-slate-200">동작 선택</legend>
          <div className="flex flex-wrap gap-4">
            {Object.entries(ACTIONS).map(([value, label], i) => (
              <label key={value} className="flex items-center gap-2 text-sm text-slate-200 cursor-pointer">
                <input
                  ref={i === 0 ? firstRef : undefined}
                  type="radio"
                  name="action"
                  value={value}
                  checked={action === value}
                  onChange={() => setAction(value)}
                />
                {label}
              </label>
            ))}
          </div>
        </fieldset>

        <label className="block space-y-1 text-sm">
          <span className="font-semibold text-slate-200">대상 엔드포인트 / 포트</span>
          <select
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            data-testid="manual-target"
            className="w-full rounded-md border border-slate-600 bg-slate-800 px-2 py-2 text-slate-100"
          >
            {Object.entries(targetGroups).map(([groupName, items]) => (
              <optgroup key={groupName} label={groupName}>
                {items.map((x) => (
                  <option key={x.value} value={x.value}>
                    {x.label}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
          <span className="block text-xs text-slate-400">
            * 백본 스위치 간 트렁크 포트는 차단 시 전체 망 분열을 초래하므로 선택지에서 자동 제외됩니다.
          </span>
        </label>

        {isProtectedIsolate && (
          <div className="rounded-md border border-red-500/80 bg-red-950/40 p-3 text-xs text-red-200">
            ⚠️ <strong>화이트리스트 보호 가드레일:</strong> 선택하신 단말은 서버망 또는 최고 관리자 자산입니다.
            인프라 보호 정책에 따라 수동 격리할 수 없습니다.
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <label className="space-y-1 text-sm">
            <span className="font-semibold text-slate-200">작업자 ID</span>
            <input
              type="text"
              value={operator}
              onChange={(e) => setOperator(e.target.value)}
              placeholder="예: admin, sec-ops"
              className="w-full rounded-md border border-slate-600 bg-slate-800 px-3 py-1.5 text-slate-100 text-sm"
            />
          </label>
          <label className="space-y-1 text-sm">
            <span className="font-semibold text-slate-200">인가 토큰 (선택)</span>
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="API 인증 토큰"
              className="w-full rounded-md border border-slate-600 bg-slate-800 px-3 py-1.5 text-slate-100 text-sm"
            />
          </label>
        </div>

        <label className="block space-y-1 text-sm">
          <span className="font-semibold text-slate-200">수행 사유 (최소 3자 필수)</span>
          <input
            type="text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="예: 보안 감사 결과 악성코드 감염 확인에 따른 수동 격리"
            className="w-full rounded-md border border-slate-600 bg-slate-800 px-3 py-1.5 text-slate-100 text-sm"
          />
        </label>

        <label className="flex items-center gap-2 pt-1 text-sm text-slate-200 cursor-pointer">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
            disabled={isProtectedIsolate}
          />
          <span>조작 결과(망 분리/트래픽 영향)를 확인하였으며 실행을 승인합니다.</span>
        </label>

        {error && <p className="text-xs text-red-400">오류: {error}</p>}

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={() => onClose(null)}
            className="rounded-md border border-slate-600 px-3 py-1.5 text-sm font-semibold text-slate-300 hover:bg-slate-800"
          >
            취소
          </button>
          <button
            type="submit"
            disabled={!valid || busy}
            className="rounded-md bg-red-600 px-4 py-1.5 text-sm font-bold text-white hover:bg-red-500 disabled:opacity-40"
          >
            {busy ? "전송 중…" : "명령 실행"}
          </button>
        </div>
      </form>
    </div>
  );
}
