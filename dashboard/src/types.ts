export type Role = 'viewer' | 'operator' | 'engineer' | 'admin';

export type AuthUser = {
  username: string;
  role: Role;
};

export type GridOverview = {
  system_frequency_hz: number;
  total_generation_mw: number;
  total_load_mw: number;
  grid_losses_mw: number;
  nodes_online: number;
  nodes_offline: number;
  nodes_degraded?: number;
  active_alarms_critical?: number;
  active_alarms_high?: number;
  active_alarms_medium?: number;
  active_alarms_low?: number;
  last_updated?: string;
};

export type NodeState = 'CONNECTED' | 'CONNECTING' | 'RECONNECTING' | 'DEGRADED' | 'OFFLINE';

export type NodeInfo = {
  node_id: string;
  type: 'generation' | 'transmission' | 'distribution' | string;
  tier: number;
  state: NodeState;
  rest_url: string;
  rest_port: number;
  ws_port: number;
  last_heartbeat?: string | null;
  reconnect_count?: number;
  telemetry?: Record<string, number | string | boolean | null>;
  position?: { x: number; y: number };
};

export type AlarmPriority = 'critical' | 'high' | 'medium' | 'low';

export type AlarmItem = {
  id: string;
  node_id: string;
  priority: AlarmPriority;
  message: string;
  value?: number | string;
  timestamp: string;
  acknowledged?: boolean;
};

export type SecurityConnection = {
  node_id: string;
  protocol: string;
  client_ip: string;
  port: number;
  connected_at: string;
  requests: number;
  status: 'AUTH' | 'UNKNOWN';
};

export type WebSocketMessage =
  | { type: 'connected'; message: string; timestamp: string }
  | { type: 'full_state_snapshot'; grid_state: GridOverview; nodes: NodeInfo[] }
  | { type: 'grid_overview_update'; data: GridOverview }
  | { type: 'telemetry_update'; node_id: string; telemetry: Record<string, number | string> }
  | { type: 'alarm_raised'; alarm: AlarmItem }
  | { type: 'alarm_cleared'; alarm_id: string }
  | { type: 'unknown_connection'; connection: SecurityConnection }
  | { type: 'node_offline'; node_id: string }
  | { type: 'security_alert'; alert: Record<string, unknown> };
