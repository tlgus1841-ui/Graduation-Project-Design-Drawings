import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { sendManualControl } from "../lib/api.js";

// Week 13 review item: operator emergency manual control (spec: whitelist guard, traceable reason).
// Only access ports are offered; trunk ports are refused by the backend as well.
// The dialog and notice are portalled to <body>: the sticky header uses backdrop-blur, which makes it
// the containing block for position:fixed children and would clip them to the header.
const TARGETS = [
  { value: "1:2", label: "S1:2 · H_attacker (공격자)", normal: false },
  { value: "1:1", label: "S1:1 · H_legit (정상 사용자)", normal: true },
  { value: "4:1", label: "S4:1 · H_server (서버)", normal: true },
];
const ACTIONS = { ISOLATE: "격리 (차단)", RESTORE: "복원 (차단 해제)" };

export default function ManualControl() {
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
      {open && createPortal(<ManualControlDialog onClose={close} />, document.body)}
      {notice && createPortal(
        <div role="status" data-testid="manual-control-notice"
          className="fixed bottom-4 left-4 z-30 rounded-lg border border-amber-500 bg-slate-900 px-4 py-3 text-sm text-amber-100 shadow-xl">
          수동 {ACTIONS[notice.command.action]} 명령 전송 · S{notice.command.target_dpid}:{notice.command.target_port}
          <span className="ml-2 font-mono text-xs text-amber-300">{notice.command.command_id}</span>
        </div>,
        document.body,
      )}
    </>
  );
}

function ManualControlDialog({ onClose }) {
  const [action, setAction] = useState("ISOLATE");
  const [target, setTarget] = useState("1:2");
  const [reason, setReason] = useState("");
  const [operator, setOperator] = useState("admin");
  const [token, setToken] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const firstRef = useRef(null);

  useEffect(() => {
    firstRef.current?.focus();
    const onKey = (e) => e.key === "Escape" && onClose(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Any change to what will be sent requires re-confirming.
  useEffect(() => setConfirmed(false), [action, target]);

  const t = TARGETS.find((x) => x.value === target);
  const [dpid, port] = target.split(":").map(Number);
  const valid = reason.trim().length >= 3 && operator.trim().length > 0 && confirmed;

  const submit = async (e) => {
    e.preventDefault();
    if (!valid || busy) return;
    setBusy(true);
    setError(null);
    try {
      onClose(await sendManualControl({ action, dpid, port, reason: reason.trim(), operator: operator.trim(), token }));
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/70 p-4" onClick={() => onClose(null)}>
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby="manual-title"
        data-testid="manual-control-dialog"
        onSubmit={submit}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md space-y-4 rounded-xl border-2 border-red-500/70 bg-slate-900 p-5 shadow-2xl"
      >
        <div>
          <p className="font-mono text-xs font-bold tracking-widest text-red-300">EMERGENCY MANUAL CONTROL</p>
          <h2 id="manual-title" className="text-lg font-bold text-slate-50">비상 수동 제어</h2>
          <p className="mt-1 text-sm text-slate-400">자동 방어와 별개로 포트를 직접 격리하거나 복원합니다. 모든 조작은 보안 이벤트에 기록됩니다.</p>
        </div>

        <fieldset className="space-y-1">
          <legend className="text-sm font-semibold text-slate-200">동작</legend>
          <div className="flex gap-4">
            {Object.entries(ACTIONS).map(([value, label], i) => (
              <label key={value} className="flex items-center gap-2 text-sm text-slate-200">
                <input ref={i === 0 ? firstRef : undefined} type="radio" name="action" value={value}
                  checked={action === value} onChange={() => setAction(value)} />
                {label}
              </label>
            ))}
          </div>
        </fieldset>

        <label className="block space-y-1 text-sm">
          <span className="font-semibold text-slate-200">대상 포트</span>
          <select value={target} onChange={(e) => setTarget(e.target.value)} data-testid="manual-target"
            className="w-full rounded-md border border-slate-600 bg-slate-800 px-2 py-1.5 text-slate-100">
            {TARGETS.map((x) => <option key={x.value} value={x.value}>{x.label}</option>)}
          </select>
          <span className="block text-xs text-slate-400">스위치끼리 연결된 포트는 망 전체가 끊길 수 있어 선택할 수 없습니다.</span>
        </label>

        {action === "ISOLATE" && t.normal && (
          <p role="alert" className="rounded-md border border-amber-500/60 bg-amber-500/10 px-3 py-2 text-sm text-amber-200">
            정상 호스트 포트입니다. 격리하면 해당 사용자의 통신이 끊깁니다.
          </p>
        )}

        <label className="block space-y-1 text-sm">
          <span className="font-semibold text-slate-200">사유 (필수)</span>
          <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} maxLength={200}
            data-testid="manual-reason" placeholder="예: AI 오탐 의심으로 수동 해제"
            className="w-full rounded-md border border-slate-600 bg-slate-800 px-2 py-1.5 text-slate-100" />
        </label>

        <div className="grid grid-cols-2 gap-3 text-sm">
          <label className="space-y-1">
            <span className="font-semibold text-slate-200">운영자</span>
            <input value={operator} onChange={(e) => setOperator(e.target.value)} maxLength={40}
              className="w-full rounded-md border border-slate-600 bg-slate-800 px-2 py-1.5 text-slate-100" />
          </label>
          <label className="space-y-1">
            <span className="font-semibold text-slate-200">관리자 토큰</span>
            <input type="password" value={token} onChange={(e) => setToken(e.target.value)} placeholder="설정 시에만"
              className="w-full rounded-md border border-slate-600 bg-slate-800 px-2 py-1.5 text-slate-100" />
          </label>
        </div>

        <label className="flex items-start gap-2 text-sm text-slate-200">
          <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)}
            data-testid="manual-confirm" className="mt-0.5" />
          <span>S{dpid}:{port} 포트를 <b>{ACTIONS[action]}</b>합니다. 이 조작이 실제 트래픽에 바로 반영됨을 확인했습니다.</span>
        </label>

        {error && <p role="alert" data-testid="manual-error" className="text-sm text-red-300">{error}</p>}

        <div className="flex justify-end gap-2">
          <button type="button" onClick={() => onClose(null)}
            className="rounded-md bg-slate-800 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-700">취소</button>
          <button type="submit" disabled={!valid || busy} data-testid="manual-submit"
            className="rounded-md bg-red-600 px-3 py-1.5 text-sm font-bold text-white enabled:hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-40">
            {busy ? "전송 중…" : `${ACTIONS[action].split(" ")[0]} 실행`}
          </button>
        </div>
      </form>
    </div>
  );
}
