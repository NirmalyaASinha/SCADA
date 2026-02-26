import { useSecurityStore } from '../store/securityStore';

export default function SecurityPanel() {
  const connections = useSecurityStore((state) => state.connections);

  return (
    <div className="panel p-4 h-full flex flex-col">
      <div className="text-sm uppercase tracking-widest text-gray-400">Security Monitor</div>
      <div className="mt-3 overflow-y-auto">
        <table className="w-full text-xs font-mono">
          <thead>
            <tr className="text-gray-500">
              <th className="text-left py-2">NODE</th>
              <th className="text-left">PROTOCOL</th>
              <th className="text-left">CLIENT IP</th>
              <th className="text-left">PORT</th>
              <th className="text-left">STATUS</th>
            </tr>
          </thead>
          <tbody>
            {connections.length === 0 && (
              <tr>
                <td colSpan={5} className="py-4 text-gray-500">
                  No active connections.
                </td>
              </tr>
            )}
            {connections.map((conn, index) => (
              <tr key={`${conn.client_ip}-${index}`} className={conn.status === 'UNKNOWN' ? 'pulse' : ''}>
                <td className="py-2">{conn.node_id}</td>
                <td>{conn.protocol}</td>
                <td>{conn.client_ip}</td>
                <td>{conn.port}</td>
                <td className={conn.status === 'UNKNOWN' ? 'status-purple' : 'status-green'}>{conn.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
