import ConnectionBadge from "./components/ConnectionBadge.jsx";
import ErrorBoundary from "./components/ErrorBoundary.jsx";
import EventFeed from "./components/EventFeed.jsx";
import IncidentStrip from "./components/IncidentStrip.jsx";
import ManualControl from "./components/ManualControl.jsx";
import PhaseBadge from "./components/PhaseBadge.jsx";
import PortStatsPanel from "./components/PortStatsPanel.jsx";
import RecoveryNotice from "./components/RecoveryNotice.jsx";
import RelearnControl from "./components/RelearnControl.jsx";
import TopologyMap from "./components/TopologyMap.jsx";
import TrafficCharts from "./components/TrafficCharts.jsx";
import { useControlTowerSocket } from "./hooks/useControlTowerSocket.js";
import DashboardLayout from "./layouts/DashboardLayout.jsx";

export default function App() {
  const { state, status, retries } = useControlTowerSocket();
  return (
    <DashboardLayout
      badges={
        <>
          {state.mode === "mock" && (
            <span className="rounded-md bg-slate-800 px-2 py-1 text-xs font-semibold text-slate-300">MOCK DATA</span>
          )}
          {state.mode === "live" && (
            <span
              data-testid="upstream-badge"
              className={`rounded-md px-2 py-1 text-xs font-semibold ${
                state.upstream === "connected" ? "bg-slate-800 text-emerald-300" : "bg-amber-500/15 text-amber-300"
              }`}
            >
              {state.upstream === "connected" ? "LIVE · REDIS" : "REDIS OFFLINE"}
            </span>
          )}
          <PhaseBadge phase={state.phase} />
          <ConnectionBadge status={status} retries={retries} />
          <RelearnControl />
          <ManualControl topology={state.topology} />
        </>
      }
    >
      <div className="lg:col-span-12">
        <ErrorBoundary>
          <IncidentStrip phase={state.phase} incident={state.incident} />
        </ErrorBoundary>
      </div>
      <div className="lg:col-span-8">
        <ErrorBoundary>
          <TopologyMap topology={state.topology} ports={state.ports} />
        </ErrorBoundary>
      </div>
      <div className="lg:col-span-4">
        <ErrorBoundary>
          <EventFeed events={state.events} />
        </ErrorBoundary>
      </div>
      <ErrorBoundary>
        <TrafficCharts history={state.history} />
      </ErrorBoundary>
      <div className="lg:col-span-12">
        <ErrorBoundary>
          <PortStatsPanel ports={state.ports} phase={state.phase} incident={state.incident} />
        </ErrorBoundary>
      </div>
      <ErrorBoundary>
        <RecoveryNotice recovery={state.recovery} />
      </ErrorBoundary>
    </DashboardLayout>
  );
}
