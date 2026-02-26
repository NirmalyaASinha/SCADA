import { useEffect } from 'react';
import { useGridStore } from '../store/gridStore';
import { useNodesStore } from '../store/nodesStore';
import { useAlarmsStore } from '../store/alarmsStore';
import { useSecurityStore } from '../store/securityStore';
import { fetchGridOverview } from '../api/grid';
import { fetchNodes } from '../api/nodes';
import { fetchActiveAlarms } from '../api/alarms';
import { fetchSecurityConnections } from '../api/security';
import KpiCard from '../components/KpiCard';
import TopologyMap from '../components/TopologyMap';
import AlarmList from '../components/AlarmList';
import SecurityPanel from '../components/SecurityPanel';

export default function GridOverview() {
  const { overview, status, setOverview, setStatus } = useGridStore();
  const setNodes = useNodesStore((state) => state.setNodes);
  const setAlarms = useAlarmsStore((state) => state.setAlarms);
  const setConnections = useSecurityStore((state) => state.setConnections);

  useEffect(() => {
    let isMounted = true;

    const refresh = async () => {
      try {
        const [grid, nodes, alarms, security] = await Promise.all([
          fetchGridOverview(),
          fetchNodes(),
          fetchActiveAlarms(),
          fetchSecurityConnections(),
        ]);

        if (!isMounted) {
          return;
        }

        setOverview(grid);
        setNodes(nodes);
        setAlarms(alarms);
        const flatConnections = security.by_node.flatMap((node) => node.connections || []);
        setConnections(flatConnections);
      } catch {
        if (isMounted) {
          setStatus('connecting');
        }
      }
    };

    refresh();
    const interval = setInterval(refresh, 5000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [setOverview, setNodes, setAlarms, setConnections, setStatus]);

  const frequency = overview?.system_frequency_hz ?? 0;
  const totalGeneration = overview?.total_generation_mw ?? 0;
  const totalLoad = overview?.total_load_mw ?? 0;
  const losses = overview?.grid_losses_mw ?? 0;
  const nodesOnline = overview?.nodes_online ?? 0;
  const nodesTotal = (overview?.nodes_online ?? 0) + (overview?.nodes_offline ?? 0);
  const alarmsCount = (overview?.active_alarms_critical ?? 0) + (overview?.active_alarms_high ?? 0);

  return (
    <div className="space-y-6">
      {status !== 'online' && (
        <div className="panel p-3 text-sm text-[#ffaa00]">Connecting to backend...</div>
      )}

      <div className="grid grid-cols-6 gap-4">
        <KpiCard label="Total Generation" value={totalGeneration} unit="MW" />
        <KpiCard label="Total Load" value={totalLoad} unit="MW" />
        <KpiCard label="Frequency" value={frequency} unit="Hz" statusClass={frequency >= 49.8 && frequency <= 50.2 ? 'status-green' : 'status-amber'} />
        <KpiCard label="Grid Losses" value={losses} unit="MW" />
        <KpiCard label="Nodes Online" value={nodesTotal ? (nodesOnline / nodesTotal) * 100 : 0} unit="%" />
        <KpiCard label="Active Alarms" value={alarmsCount} />
      </div>

      <TopologyMap />

      <div className="grid grid-cols-2 gap-4">
        <AlarmList />
        <SecurityPanel />
      </div>
    </div>
  );
}
