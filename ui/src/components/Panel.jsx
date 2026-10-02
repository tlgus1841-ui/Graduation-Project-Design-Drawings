// Fixed-height dark card so the grid does not jump as data streams in.
export default function Panel({ title, subtitle, className = "", children }) {
  return (
    <section className={`flex min-h-0 flex-col rounded-xl border border-slate-700/60 bg-slate-800/70 ${className}`}>
      <header className="flex items-baseline justify-between border-b border-slate-700/60 px-4 py-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-200">{title}</h2>
        {subtitle && <span className="text-xs text-slate-400">{subtitle}</span>}
      </header>
      <div className="min-h-0 flex-1 overflow-auto p-4">{children}</div>
    </section>
  );
}
