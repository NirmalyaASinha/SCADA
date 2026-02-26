import React from 'react';
import { useSecurityStore } from '../store/securityStore';

export default function SecurityConsole() {
  const { connections } = useSecurityStore();

  return (
    <div className="page-content">
      <h2>Security Console</h2>
      <div className="security-section">
        <h3>Active Connections</h3>
        <table className="connections-table">
          <thead>
            <tr>
              <th>Source IP</th>
              <th>Port</th>
              <th>Protocol</th>
              <th>Type</th>
              <th>Status</th>
              <th>Last Activity</th>
            </tr>
          </thead>
          <tbody>
            {connections.map((conn, idx) => (
              <tr key={idx} className={`type-${conn.type?.toLowerCase()}`}>
                <td>{conn.source_ip}</td>
                <td>{conn.port}</td>
                <td>{conn.protocol}</td>
                <td>{conn.type}</td>
                <td>{conn.status}</td>
                <td>{conn.last_activity ? new Date(conn.last_activity).toLocaleString() : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
