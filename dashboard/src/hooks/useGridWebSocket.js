// WebSocket Hook for Grid Updates
import { useEffect, useRef } from 'react';
import toast from 'react-hot-toast';
import useGridStore from '../store/gridStore';
import useNodesStore from '../store/nodesStore';
import useAlarmsStore from '../store/alarmsStore';
import useSecurityStore from '../store/securityStore';

const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:9001';

export const useGridWebSocket = (token) => {
  const ws = useRef(null);
  const reconnectTimeout = useRef(null);
  
  const { setGridState } = useGridStore();
  const { updateNodeTelemetry } = useNodesStore();
  const { addAlarm } = useAlarmsStore();
  const { addUnknownConnection, addSecurityEvent } = useSecurityStore();
  
  useEffect(() => {
    if (!token) return;
    
    const connect = () => {
      const websocket = new WebSocket(`${WS_URL}/ws/grid?token=${token}`);
      
      websocket.onopen = () => {
        console.log('WebSocket connected');
        ws.current = websocket;
      };
      
      websocket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          handleMessage(message);
        } catch (error) {
          console.error('WebSocket message error:', error);
        }
      };
      
      websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
      
      websocket.onclose = () => {
        console.log('WebSocket disconnected. Reconnecting...');
        reconnectTimeout.current = setTimeout(connect, 5000);
      };
    };
    
    connect();
    
    return () => {
      if (ws.current) {
        ws.current.close();
      }
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
      }
    };
  }, [token]);
  
  const handleMessage = (message) => {
    const { type, data, node_id } = message;
    
    switch (type) {
      case 'full_state_snapshot':
        setGridState(message.grid_state);
        break;
      
      case 'telemetry_update':
        updateNodeTelemetry(node_id, data);
        break;
      
      case 'grid_overview_update':
        setGridState(data);
        break;
      
      case 'alarm_raised':
        addAlarm(data);
        toast.error(`Alarm: ${data.message}`, { duration: 5000 });
        break;
      
      case 'unknown_connection':
        addUnknownConnection({
          ...data,
          node_id,
          id: `${node_id}-${data.client_ip}-${Date.now()}`,
        });
        toast((t) => (
          <div className="flex items-center space-x-2">
            <span className="text-status-purple">⚠</span>
            <div>
              <div className="font-bold">Unknown Connection</div>
              <div className="text-sm text-text-secondary">
                {data.client_ip} → {node_id} via {data.protocol}
              </div>
            </div>
          </div>
        ), {
          duration: 10000,
          style: {
            background: '#220044',
            color: '#e8e8e8',
            border: '1px solid #aa44ff',
          },
        });
        break;
      
      case 'security_alert':
        addSecurityEvent(message);
        break;
      
      case 'node_offline':
        toast.error(`Node ${node_id} is offline`, { duration: 8000 });
        break;
      
      case 'breaker_operated':
        toast.success(`Breaker ${data.breaker_id} ${data.action} on ${node_id}`);
        break;
      
      default:
        console.log('Unknown message type:', type);
    }
  };
  
  return ws.current;
};
