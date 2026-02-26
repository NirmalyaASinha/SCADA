import { useEffect, useMemo, useState } from 'react';
import { fetchSecurityConnections } from '../api/security';
import { useSecurityStore } from '../store/securityStore';

export default function SecurityConsole() {
  const connections = useSecurityStore((state) => state.connections);
  const setConnections = useSecurityStore((state) => state.setConnections);
  const [blocked, setBlocked] = useState<string[]>([]);

  useEffect(() => {
    fetchSecurityConnections()
      .then((data) => setConnections(data.by_node.flatMap((node) => node.connections || [])))
      .catch(() => undefined);
  }, [setConnections]);

  const timeline = useMemo(() => {
    return connections
      .filter((conn) => conn.status === 'UNKNOWN')
      .map((conn) => ({
        time: conn.connected_at,
        message: `Unknown connection from ${conn.client_ip} on ${conn.node_id}`,
      }));
  }, [connections]);

  const onBlock = (clientIp: string) => {
    setBlocked((state) => [...state, clientIp]);
  };

  return (
    <div className="space-y-6">
      <div className="panel p-4">
        <div className="text-lg font-mono">Security Console</div>
        <table className="w-full text-xs font-mono mt-3">
          <thead>
            <tr className="text-gray-500">
              <th className="text-left py-2">NODE</th>
              <th className="text-left">PROTOCOL</th>
              <th className="text-left">CLIENT IP</th>
              <th className="text-left">PORT</th>
              <th className="text-left">STATUS</th>
              <th className="text-left">ACTION</th>
            </tr>
          </thead>
          <tbody>
            {connections.length === 0 && (
              <tr>
                <td colSpan={6} className="py-4 text-gray-500">No security events</td>
              </tr>
            )}
            {connections.map((conn, index) => (
              <tr key={`${conn.client_ip}-${index}`} className={conn.status === 'UNKNOWN' ? 'pulse' : ''}>
                <td className="py-2">{conn.node_id}</td>
                <td>{conn.protocol}</td>
                <td>{conn.client_ip}</td>
                <td>{conn.port}</td>
                <td className={conn.status === 'UNKNOWN' ? 'status-purple' : 'status-green'}>{conn.status}</td>
                <td>
                  {conn.status === 'UNKNOWN' ? (
                    <button
                      onClick={() => onBlock(conn.client_ip)}
                      className="text-xs border border-[#2a2a2a] px-3 py-1 rounded-md"
                    >
                      {blocked.includes(conn.client_ip) ? 'BLOCKED' : 'BLOCK'}
                    </button>
                  ) : (
                    <span className="text-gray-500">-</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="panel p-4">
          <div className="text-sm uppercase tracking-widest text-gray-400">Security Timeline</div>
          <div className="mt-3 space-y-2">
            {timeline.length === 0 && <div className="text-xs text-gray-500">No unknown connections.</div>}
            {timeline.map((item, index) => (
              <div key={index} className="text-xs border-l-2 border-[#aa44ff] pl-2">
                <div className="text-gray-400">{item.time}</div>
                <div>{item.message}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="panel p-4">
          <div className="text-sm uppercase tracking-widest text-gray-400">Anomaly Feed</div>
          <div className="mt-3 text-xs text-gray-500">
            No anomalies reported by the detection engine.
          </div>
        </div>
      </div>
    </div>
  );
}
