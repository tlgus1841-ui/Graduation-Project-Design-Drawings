import { memo, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { sendRelearn } from "../lib/api.js";

// Special-situation relearn approval (criteria spec §4): when normal traffic really grows (course
// registration, an event), the operator approves a period in which the AI worker relearns traffic volume.
// Attack signals (unmatched SYN, failure replies) are never relearned, and the baseline returns afterwards.
const TARGETS = [
  { value: "0:0", label: "모든 접속 포트" },
  { value: "1:1", label: "S1:1 · H_legit" },
  { value: "1:2", label: "S1:2 · H_attacker" },
];
const PERIODS = [30, 60, 120, 240];

function RelearnControl() {
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
        data-testid="relearn-open"
        className="rounded-md border border-sky-500/70 px-3 py-1 text-sm font-bold text-sky-200 hover:bg-sky-500/15 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
      >
        특수 상황 재학습
      </button>
      {open && createPortal(<RelearnDialog onClose={close} />, document.body)}
      {notice && createPortal(
        <div role="status" data-testid="relearn-notice"
          className="fixed bottom-4 left-4 z-30 rounded-lg border border-sky-500 bg-slate-900 px-4 py-3 text-sm text-sky-100 shadow-xl">
          재학습 승인 전송 · {Math.round(notice.command.duration_sec / 60)}분
          <span className="ml-2 font-mono text-xs text-sky-300">{notice.command.command_id}</span>
        </div>,
        document.body,
      )}
    </>
  );
}

export default memo(RelearnControl);

function RelearnDialog({ onClose }) {
  const [minutes, setMinutes] = useState(60);
  const [target, setTarget] = useState("0:0");
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

  useEffect(() => setConfirmed(false), [minutes, target]);

  const [dpid, port] = target.split(":").map(Number);
  const valid = reason.trim().length >= 3 && operator.trim().length > 0 && confirmed;

  const submit = async (e) => {
    e.preventDefault();
    if (!valid || busy) return;
    setBusy(true);
    setError(null);
    try {
      onClose(await sendRelearn({ minutes, dpid, port, reason: reason.trim(), operator: operator.trim(), token }));
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
        aria-labelledby="relearn-title"
        data-testid="relearn-dialog"
        onSubmit={submit}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md space-y-4 rounded-xl border-2 border-sky-500/70 bg-slate-900 p-5 shadow-2xl"
      >
        <div>
          <p className="font-mono text-xs font-bold tracking-widest text-sky-300">SPECIAL-SITUATION RELEARN</p>
          <h2 id="relearn-title" className="text-lg font-bold text-slate-50">특수 상황 재학습 승인</h2>
          <p className="mt-1 text-sm text-slate-400">
            수강신청 · 이벤트처럼 정상 트래픽이 진짜로 늘었을 때, 정한 기간 동안 트래픽 양(SYN · UDP · ICMP)을 새로 배웁니다.
            짝이 안 맞는 연결이나 실패 응답 같은 공격 신호는 다시 배우지 않고, 기간이 끝나면 원래 평소값으로 돌아갑니다.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3 text-sm">
          <label className="space-y-1">
            <span className="font-semibold text-slate-200">기간</span>
            <select ref={firstRef} value={minutes} onChange={(e) => setMinutes(Number(e.target.value))}
              data-testid="relearn-minutes"
              className="w-full rounded-md border border-slate-600 bg-slate-800 px-2 py-1.5 text-slate-100">
              {PERIODS.map((m) => <option key={m} value={m}>{m >= 60 ? `${m / 60}시간` : `${m}분`}</option>)}
            </select>
          </label>
          <label className="space-y-1">
            <span className="font-semibold text-slate-200">대상</span>
            <select value={target} onChange={(e) => setTarget(e.target.value)} data-testid="relearn-target"
              className="w-full rounded-md border border-slate-600 bg-slate-800 px-2 py-1.5 text-slate-100">
              {TARGETS.map((x) => <option key={x.value} value={x.value}>{x.label}</option>)}
            </select>
          </label>
        </div>

        <label className="block space-y-1 text-sm">
          <span className="font-semibold text-slate-200">사유 (필수)</span>
          <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} maxLength={200}
            data-testid="relearn-reason" placeholder="예: 수강신청 기간, SYN · FIN 짝과 서비스 상태 정상 확인"
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
            data-testid="relearn-confirm" className="mt-0.5" />
          <span>지금 늘어난 트래픽이 정상임을 확인했고, <b>{minutes >= 60 ? `${minutes / 60}시간` : `${minutes}분`}</b> 동안 재학습을 승인합니다.</span>
        </label>

        {error && <p role="alert" data-testid="relearn-error" className="text-sm text-red-300">{error}</p>}

        <div className="flex justify-end gap-2">
          <button type="button" onClick={() => onClose(null)}
            className="rounded-md bg-slate-800 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-700">취소</button>
          <button type="submit" disabled={!valid || busy} data-testid="relearn-submit"
            className="rounded-md bg-sky-600 px-3 py-1.5 text-sm font-bold text-white enabled:hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-40">
            {busy ? "전송 중…" : "재학습 승인"}
          </button>
        </div>
      </form>
    </div>
  );
}
