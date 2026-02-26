import { useGridStore } from '../store/gridStore';
import { useAlarmsStore } from '../store/alarmsStore';
import { useSecurityStore } from '../store/securityStore';
import FlashValue from './FlashValue';

export default function TopBar() {
  const overview = useGridStore((state) => state.overview);
  const status = useGridStore((state) => state.status);
  const alarms = useAlarmsStore((state) => state.alarms);
  const unknownCount = useSecurityStore((state) => state.unknownCount);

  const frequency = overview?.system_frequency_hz ?? 0;
  const frequencyClass = frequency >= 49.8 && frequency <= 50.2 ? 'status-green' : frequency >= 49.4 ? 'status-amber' : 'status-red';

  return (
    <header className="flex items-center justify-between border-b border-[#2a2a2a] px-6 py-4 bg-[#0d0d0d]">
      <div className="text-xs uppercase tracking-[0.3em] text-gray-500">Control Room</div>
      <div className="flex items-center gap-6">
        <div className={`text-3xl font-mono ${frequencyClass}`}>
          {status === 'online' ? (
            <FlashValue value={frequency} formatter={(val) => `${Number(val).toFixed(3)} Hz`} />
          ) : (
            <span className="status-amber">Connecting...</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="badge" style={{ color: '#ff3333' }}>Alarms</span>
          <span className="font-mono text-sm">{alarms.length}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="badge" style={{ color: '#aa44ff' }}>Unknown</span>
          <span className="font-mono text-sm">{unknownCount}</span>
        </div>
      </div>
      <div className="text-xs text-gray-500">SCADA Master API: :9000</div>
    </header>
  );
}
