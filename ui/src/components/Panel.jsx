// Fixed-height dark card so the grid does not jump as data streams in.
export default function Panel({ title, subtitle, headerAction = null, className = "", children }) {
  return (
    <section className={`flex min-h-0 flex-col rounded-xl border border-slate-700/60 bg-slate-800/70 ${className}`}>
      <header className="flex items-center justify-between border-b border-slate-700/60 px-4 py-2.5">
        <div className="flex items-baseline gap-3">
          <h2 className="text-base font-semibold uppercase tracking-wider text-slate-100">{title}</h2>
          {subtitle && <span className="text-sm text-slate-300">{subtitle}</span>}
        </div>
        {headerAction && <div>{headerAction}</div>}
      </header>
      <div className="min-h-0 flex-1 overflow-auto p-4">{children}</div>
    </section>
  );
}
