import { NavLink } from 'react-router-dom';
import { Shield, Activity, CircuitBoard, AlertTriangle, Network, Database } from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { useAlarmsStore } from '../store/alarmsStore';
import { useSecurityStore } from '../store/securityStore';

const navItems = [
  { label: 'Overview', to: '/', icon: Activity },
  { label: 'Nodes', to: '/nodes', icon: Network },
  { label: 'Control', to: '/control', icon: CircuitBoard },
  { label: 'Alarms', to: '/alarms', icon: AlertTriangle },
  { label: 'Security', to: '/security', icon: Shield },
  { label: 'Historian', to: '/historian', icon: Database },
];

export default function Sidebar() {
  const { user, logout } = useAuthStore();
  const alarms = useAlarmsStore((state) => state.alarms);
  const unknownCount = useSecurityStore((state) => state.unknownCount);

  return (
    <aside className="w-[200px] border-r border-[#2a2a2a] bg-[#0e0e0e] flex flex-col">
      <div className="px-4 py-5 font-mono text-[#00ff88] text-lg">SCADA OCC</div>
      <nav className="flex-1 px-2 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center justify-between gap-2 px-3 py-2 rounded-md text-sm ${
                  isActive ? 'bg-[#111111] text-white' : 'text-gray-400 hover:text-white'
                }`
              }
            >
              <span className="flex items-center gap-2">
                <Icon size={16} />
                {item.label}
              </span>
              {item.label === 'Alarms' && alarms.length > 0 && (
                <span className="badge" style={{ color: '#ff3333' }}>
                  {alarms.length}
                </span>
              )}
              {item.label === 'Security' && unknownCount > 0 && (
                <span className="badge" style={{ color: '#aa44ff' }}>
                  {unknownCount}
                </span>
              )}
            </NavLink>
          );
        })}
      </nav>
      <div className="px-4 py-4 border-t border-[#2a2a2a]">
        <div className="text-xs text-gray-400">{user?.username}</div>
        <div className="badge mt-2" style={{ color: '#33a1ff' }}>{user?.role?.toUpperCase()}</div>
        <button
          onClick={logout}
          className="mt-3 w-full rounded-md border border-[#2a2a2a] px-3 py-2 text-xs text-gray-300 hover:text-white"
        >
          Logout
        </button>
      </div>
    </aside>
  );
}
