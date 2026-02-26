import React from 'react';
import { useAlarmsStore } from '../store/alarmsStore';

export default function AlarmsPage() {
  const { alarms } = useAlarmsStore();

  return (
    <div className="page-content">
      <h2>Alarms</h2>
      <table className="alarms-table">
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Severity</th>
            <th>Message</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {alarms.slice(0, 50).map((alarm, idx) => (
            <tr key={idx} className={`severity-${alarm.severity?.toLowerCase()}`}>
              <td>{new Date(alarm.timestamp).toLocaleString()}</td>
              <td>{alarm.severity}</td>
              <td>{alarm.message}</td>
              <td>{alarm.source}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
