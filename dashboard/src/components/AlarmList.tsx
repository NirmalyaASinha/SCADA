import { useAuthStore } from '../store/authStore';
import { useAlarmsStore } from '../store/alarmsStore';
import { acknowledgeAlarm } from '../api/alarms';
import type { AlarmItem } from '../types';

const priorityColor: Record<string, string> = {
  critical: '#ff3333',
  high: '#ffaa00',
  medium: '#ffaa00',
  low: '#00ff88',
};

export default function AlarmList() {
  const alarms = useAlarmsStore((state) => state.alarms);
  const removeAlarm = useAlarmsStore((state) => state.removeAlarm);
  const user = useAuthStore((state) => state.user);

  const onAck = async (alarm: AlarmItem) => {
    if (!user) {
      return;
    }
    await acknowledgeAlarm(alarm.id, user.username, 'Acknowledged from dashboard');
    removeAlarm(alarm.id);
  };

  return (
    <div className="panel p-4 h-full flex flex-col">
      <div className="text-sm uppercase tracking-widest text-gray-400">Active Alarms</div>
      <div className="mt-3 space-y-2 overflow-y-auto">
        {alarms.length === 0 && (
          <div className="text-sm text-gray-500">No active alarms.</div>
        )}
        {alarms.map((alarm) => (
          <div
            key={alarm.id}
            className="border border-[#2a2a2a] rounded-md p-3 flex items-center justify-between"
            style={{ borderLeft: `4px solid ${priorityColor[alarm.priority] || '#ffaa00'}` }}
          >
            <div>
              <div className="font-mono text-sm" style={{ color: priorityColor[alarm.priority] || '#ffaa00' }}>
                {alarm.priority.toUpperCase()} - {alarm.node_id}
              </div>
              <div className="text-xs text-gray-400">{alarm.message}</div>
            </div>
            <button
              onClick={() => onAck(alarm)}
              className="text-xs border border-[#2a2a2a] px-3 py-1 rounded-md hover:text-white"
            >
              ACK
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
