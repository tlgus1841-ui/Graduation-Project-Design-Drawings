import ConnectionBadge from "./components/ConnectionBadge.jsx";
import EventFeed from "./components/EventFeed.jsx";
import PhaseBadge from "./components/PhaseBadge.jsx";
import PortStatsPanel from "./components/PortStatsPanel.jsx";
import TopologyPanel from "./components/TopologyPanel.jsx";
import { useControlTowerSocket } from "./hooks/useControlTowerSocket.js";
import DashboardLayout from "./layouts/DashboardLayout.jsx";

export default function App() {
  const { state, status, retries } = useControlTowerSocket();
  return (
    <DashboardLayout
      badges={
        <>
          {state.mode === "mock" && (
            <span className="rounded-md bg-slate-800 px-2 py-1 text-xs text-slate-400">MOCK DATA</span>
          )}
          <PhaseBadge phase={state.phase} />
          <ConnectionBadge status={status} retries={retries} />
        </>
      }
    >
      <div className="lg:col-span-8"><TopologyPanel topology={state.topology} /></div>
      <div className="lg:col-span-4"><EventFeed events={state.events} /></div>
      <div className="lg:col-span-12"><PortStatsPanel ports={state.ports} /></div>
    </DashboardLayout>
  );
}
