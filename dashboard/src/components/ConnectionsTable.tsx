import type { SecurityConnection } from '../types';

export default function ConnectionsTable({ connections }: { connections: SecurityConnection[] }) {
  return (
    <div className="panel p-4">
      <div className="text-sm uppercase tracking-widest text-gray-400">Connected Clients</div>
      <table className="w-full text-xs font-mono mt-3">
        <thead>
          <tr className="text-gray-500">
            <th className="text-left py-2">CLIENT</th>
            <th className="text-left">PROTOCOL</th>
            <th className="text-left">PORT</th>
            <th className="text-left">STATUS</th>
          </tr>
        </thead>
        <tbody>
          {connections.length === 0 && (
            <tr>
              <td colSpan={4} className="py-4 text-gray-500">
                No active connections
              </td>
            </tr>
          )}
          {connections.map((conn, index) => (
            <tr key={`${conn.client_ip}-${index}`}>
              <td className="py-2">{conn.client_ip}</td>
              <td>{conn.protocol}</td>
              <td>{conn.port}</td>
              <td className={conn.status === 'UNKNOWN' ? 'status-purple' : 'status-green'}>{conn.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
