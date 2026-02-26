import type { NodeState } from '../types';

export function stateToColor(state: NodeState | undefined) {
  switch (state) {
    case 'CONNECTED':
      return 'text-[#00ff88]';
    case 'RECONNECTING':
    case 'DEGRADED':
      return 'text-[#ffaa00]';
    case 'OFFLINE':
      return 'text-[#ff3333]';
    case 'CONNECTING':
      return 'text-[#aa44ff]';
    default:
      return 'text-[#888888]';
  }
}

export function stateToBg(state: NodeState | undefined) {
  switch (state) {
    case 'CONNECTED':
      return '#00ff88';
    case 'RECONNECTING':
    case 'DEGRADED':
      return '#ffaa00';
    case 'OFFLINE':
      return '#ff3333';
    case 'CONNECTING':
      return '#aa44ff';
    default:
      return '#666666';
  }
}
