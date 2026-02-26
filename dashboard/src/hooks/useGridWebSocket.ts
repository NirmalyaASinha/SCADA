import { useEffect, useRef } from 'react';
import toast from 'react-hot-toast';
import { useAuthStore } from '../store/authStore';
import { useGridStore } from '../store/gridStore';
import { useNodesStore } from '../store/nodesStore';
import { useAlarmsStore } from '../store/alarmsStore';
import { useSecurityStore } from '../store/securityStore';
import type { WebSocketMessage, SecurityConnection, AlarmItem } from '../types';

function playSecurityTone() {
  try {
    const audioContext = new AudioContext();
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();

    oscillator.type = 'sine';
    oscillator.frequency.value = 540;
    gainNode.gain.value = 0.08;

    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);

    oscillator.start();
    setTimeout(() => {
      oscillator.stop();
      audioContext.close();
    }, 220);
  } catch {
    // Audio context may be blocked by browser autoplay policy.
  }
}

export function useGridWebSocket() {
  const token = useAuthStore((state) => state.token);
  const setOverview = useGridStore((state) => state.setOverview);
  const setStatus = useGridStore((state) => state.setStatus);
  const setNodes = useNodesStore((state) => state.setNodes);
  const updateNode = useNodesStore((state) => state.updateNode);
  const addTelemetry = useNodesStore((state) => state.addTelemetry);
  const addAlarm = useAlarmsStore((state) => state.addAlarm);
  const removeAlarm = useAlarmsStore((state) => state.removeAlarm);
  const addUnknown = useSecurityStore((state) => state.addUnknown);

  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!token) {
      return undefined;
    }

    // Use relative path to go through nginx proxy
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsBase = import.meta.env.VITE_WS_URL || `${wsProtocol}//${window.location.hostname}${window.location.port ? ':' + window.location.port : ''}/ws/grid`;
    const wsUrl = `${wsBase}?token=${token}`;

    setStatus('connecting');

    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onopen = () => {
      setStatus('online');
    };

    socket.onclose = () => {
      setStatus('offline');
    };

    socket.onerror = () => {
      setStatus('offline');
    };

    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as WebSocketMessage;

        if (payload.type === 'full_state_snapshot') {
          if (payload.grid_state) {
            setOverview(payload.grid_state);
          }
          if (payload.nodes) {
            setNodes(payload.nodes);
          }
          return;
        }

        if (payload.type === 'grid_overview_update') {
          setOverview(payload.data);
          return;
        }

        if (payload.type === 'telemetry_update') {
          addTelemetry(payload.node_id, payload.telemetry);
          return;
        }

        if (payload.type === 'alarm_raised') {
          const alarm = payload.alarm as AlarmItem;
          addAlarm(alarm);
          toast.error(`ALARM: ${alarm.node_id} - ${alarm.message}`);
          return;
        }

        if (payload.type === 'alarm_cleared') {
          removeAlarm(payload.alarm_id);
          toast.success('Alarm cleared');
          return;
        }

        if (payload.type === 'unknown_connection') {
          const connection = payload.connection as SecurityConnection;
          addUnknown(connection);
          toast(`Unknown connection from ${connection.client_ip}`, {
            icon: '🟪',
            style: { background: '#1a1025', color: '#aa44ff' },
          });
          playSecurityTone();
          return;
        }

        if (payload.type === 'node_offline') {
          updateNode(payload.node_id, { state: 'DEGRADED' });
          toast('Node offline: ' + payload.node_id, {
            icon: '⚠️',
            style: { background: '#1a1206', color: '#ffaa00' },
          });
        }
      } catch {
        // Ignore malformed messages
      }
    };

    return () => {
      socket.close();
    };
  }, [token, setOverview, setStatus, setNodes, updateNode, addTelemetry, addAlarm, removeAlarm, addUnknown]);
}
