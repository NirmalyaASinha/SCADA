import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { fetchNodeConnections, fetchNodeDetail, fetchNodeTelemetry } from '../api/nodes';
import { useNodesStore } from '../store/nodesStore';
import ConnectionsTable from '../components/ConnectionsTable';
import Sparkline from '../components/Sparkline';
import type { SecurityConnection } from '../types';

export default function NodeDetail() {
  const { id } = useParams();
  const node = useNodesStore((state) => state.nodes.find((n) => n.node_id === id));
  const telemetryHistory = useNodesStore((state) => state.telemetryHistory[id || ''] || []);
  const updateNode = useNodesStore((state) => state.updateNode);
  const [connections, setConnections] = useState<SecurityConnection[]>([]);

  useEffect(() => {
    if (!id) {
      return;
    }

    fetchNodeDetail(id).then((detail) => updateNode(id, detail)).catch(() => undefined);
    fetchNodeTelemetry(id).then((telemetry) => updateNode(id, { telemetry })).catch(() => undefined);
    fetchNodeConnections(id).then((data) => setConnections(data.connections as SecurityConnection[])).catch(() => undefined);
  }, [id, updateNode]);

  const telemetryEntries = useMemo(() => {
    return Object.entries(node?.telemetry || {}).map(([key, value]) => ({
      key,
      value,
    }));
  }, [node]);

  const timeSeries = telemetryHistory.map((point) => ({
    timestamp: point.timestamp,
    ...point.values,
  }));

  return (
    <div className="space-y-6">
      <div className="panel p-4">
        <div className="text-lg font-mono">{node?.node_id || id}</div>
        <div className="text-xs text-gray-500">{node?.type} tier {node?.tier}</div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="panel p-4">
          <div className="text-sm uppercase tracking-widest text-gray-400">Single Line Diagram</div>
          <svg viewBox="0 0 320 220" className="mt-4 w-full">
            <line x1="40" y1="110" x2="280" y2="110" stroke="#2a2a2a" strokeWidth="4" />
            <circle cx="80" cy="110" r="12" stroke="#00ff88" strokeWidth="3" fill="#0a0a0a" className="pulse" />
            <circle cx="160" cy="110" r="12" stroke="#ffaa00" strokeWidth="3" fill="#0a0a0a" />
            <circle cx="240" cy="110" r="12" stroke="#ff3333" strokeWidth="3" fill="#0a0a0a" />
            <line x1="80" y1="110" x2="160" y2="110" stroke="#00ff88" strokeWidth="2" />
            <line x1="160" y1="110" x2="240" y2="110" stroke="#ffaa00" strokeWidth="2" />
          </svg>
        </div>

        <div className="panel p-4">
          <div className="text-sm uppercase tracking-widest text-gray-400">Live Telemetry</div>
          <table className="w-full text-xs font-mono mt-3">
            <thead>
              <tr className="text-gray-500">
                <th className="text-left py-2">TAG</th>
                <th className="text-left">VALUE</th>
                <th className="text-left">QUALITY</th>
                <th className="text-left">TREND</th>
              </tr>
            </thead>
            <tbody>
              {telemetryEntries.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-4 text-gray-500">No telemetry available</td>
                </tr>
              )}
              {telemetryEntries.map((entry) => (
                <tr key={entry.key} className="border-b border-[#1e1e1e]">
                  <td className="py-2">{entry.key}</td>
                  <td>{String(entry.value)}</td>
                  <td className="status-green">GOOD</td>
                  <td>
                    <Sparkline
                      values={telemetryHistory.map((point) => point.values[entry.key] || 0).slice(-24)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <ConnectionsTable connections={connections} />
      </div>

      <div className="panel p-4">
        <div className="text-sm uppercase tracking-widest text-gray-400">Telemetry Trend (Last Hour)</div>
        <div className="h-[260px] mt-3">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={timeSeries}>
              <XAxis dataKey="timestamp" hide />
              <YAxis hide />
              <Tooltip contentStyle={{ background: '#111111', border: '1px solid #2a2a2a' }} />
              <Line type="monotone" dataKey="frequency_hz" stroke="#00ff88" dot={false} />
              <Line type="monotone" dataKey="voltage_kv" stroke="#ffaa00" dot={false} />
              <Line type="monotone" dataKey="active_power_mw" stroke="#33a1ff" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
