import { useEffect, useMemo, useState } from 'react';
import { fetchActiveAlarms, acknowledgeAlarm } from '../api/alarms';
import { useAlarmsStore } from '../store/alarmsStore';
import { useAuthStore } from '../store/authStore';
import type { AlarmItem, AlarmPriority } from '../types';

const priorities: AlarmPriority[] = ['critical', 'high', 'medium', 'low'];

export default function AlarmsPage() {
  const alarms = useAlarmsStore((state) => state.alarms);
  const setAlarms = useAlarmsStore((state) => state.setAlarms);
  const user = useAuthStore((state) => state.user);
  const [priority, setPriority] = useState<AlarmPriority | 'all'>('all');
  const [nodeFilter, setNodeFilter] = useState('');

  useEffect(() => {
    fetchActiveAlarms().then(setAlarms).catch(() => undefined);
  }, [setAlarms]);

  const filtered = useMemo(() => {
    return alarms.filter((alarm) => {
      if (priority !== 'all' && alarm.priority !== priority) {
        return false;
      }
      if (nodeFilter && !alarm.node_id.toLowerCase().includes(nodeFilter.toLowerCase())) {
        return false;
      }
      return true;
    });
  }, [alarms, priority, nodeFilter]);

  const onAck = async (alarm: AlarmItem) => {
    if (!user) {
      return;
    }
    await acknowledgeAlarm(alarm.id, user.username, 'Acknowledged via alarm console');
  };

  return (
    <div className="panel p-6">
      <div className="flex items-center justify-between">
        <div className="text-lg font-mono">Alarm Management</div>
        <div className="flex gap-2">
          <select
            className="bg-[#0d0d0d] border border-[#2a2a2a] rounded-md px-3 py-2 text-sm"
            value={priority}
            onChange={(event) => setPriority(event.target.value as AlarmPriority | 'all')}
          >
            <option value="all">All Priorities</option>
            {priorities.map((p) => (
              <option key={p} value={p}>{p.toUpperCase()}</option>
            ))}
          </select>
          <input
            className="bg-[#0d0d0d] border border-[#2a2a2a] rounded-md px-3 py-2 text-sm"
            placeholder="Filter node"
            value={nodeFilter}
            onChange={(event) => setNodeFilter(event.target.value)}
          />
        </div>
      </div>

      <table className="w-full text-sm font-mono mt-4">
        <thead>
          <tr className="text-gray-500">
            <th className="text-left py-2">PRIORITY</th>
            <th className="text-left">NODE</th>
            <th className="text-left">MESSAGE</th>
            <th className="text-left">VALUE</th>
            <th className="text-left">TIME</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {filtered.length === 0 && (
            <tr>
              <td colSpan={6} className="py-4 text-gray-500">No alarms to display</td>
            </tr>
          )}
          {filtered.map((alarm) => (
            <tr key={alarm.id} className={alarm.priority === 'critical' ? 'flash' : ''}>
              <td className="py-2">
                <span className="badge" style={{ color: alarm.priority === 'critical' ? '#ff3333' : '#ffaa00' }}>
                  {alarm.priority.toUpperCase()}
                </span>
              </td>
              <td>{alarm.node_id}</td>
              <td>{alarm.message}</td>
              <td>{alarm.value ?? '-'}</td>
              <td>{new Date(alarm.timestamp).toLocaleTimeString()}</td>
              <td>
                <button
                  onClick={() => onAck(alarm)}
                  className="text-xs border border-[#2a2a2a] px-3 py-1 rounded-md"
                >
                  ACK
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
