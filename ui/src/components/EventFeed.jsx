import Panel from "./Panel.jsx";

const KIND = {
  alert: { label: "ALERT", cls: "bg-red-500/20 text-red-300" },
  command: { label: "COMMAND", cls: "bg-sky-500/20 text-sky-300" },
  phase: { label: "STATE", cls: "bg-slate-600/60 text-slate-200" },
};

function clock(ts) {
  if (!ts) return "--:--:--";
  const d = new Date(ts * 1000);
  return [d.getHours(), d.getMinutes(), d.getSeconds()].map((n) => String(n).padStart(2, "0")).join(":");
}

export default function EventFeed({ events }) {
  return (
    <Panel title="Security Events" subtitle={`최근 ${events.length}건`} className="h-[420px]">
      {events.length === 0 ? (
        <p className="text-sm text-slate-400">아직 이벤트가 없습니다.</p>
      ) : (
        <ol className="space-y-2" data-testid="event-feed">
          {events.map((e) => {
            const k = KIND[e.kind] ?? KIND.phase;
            return (
              <li key={e.id} className="rounded-lg bg-slate-900/60 px-3 py-2">
                <div className="flex items-center gap-2 text-xs">
                  <span className={`rounded px-1.5 py-0.5 font-bold ${k.cls}`}>{k.label}</span>
                  <span className="font-mono text-slate-400">{clock(e.ts)}</span>
                </div>
                <p className="mt-1 text-sm font-semibold text-slate-100">{e.title}</p>
                <p className="text-xs text-slate-400">{e.detail}</p>
              </li>
            );
          })}
        </ol>
      )}
    </Panel>
  );
}
