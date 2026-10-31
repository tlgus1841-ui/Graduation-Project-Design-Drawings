// SOC dark theme shell: fixed header + 12-column widescreen grid.
export default function DashboardLayout({ badges, children }) {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <header className="sticky top-0 z-10 border-b border-slate-800 bg-slate-900/95 backdrop-blur">
        <div className="mx-auto flex max-w-[1600px] w-full flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6 lg:px-8">
          <div>
            <p className="font-mono text-xs tracking-widest text-sky-400">SELF-DEFENDING SDN TOWER</p>
            <h1 className="text-lg font-bold text-slate-50">관제탑 대시보드</h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">{badges}</div>
        </div>
      </header>
      <main className="mx-auto grid max-w-[1600px] w-full grid-cols-1 gap-4 p-4 sm:p-6 lg:p-8 lg:grid-cols-12">{children}</main>
    </div>
  );
}
