// Control API
import apiClient from './client';

export const controlAPI = {
  breakerSelect: async (nodeId, breakerId, action, reason, operatorId) => {
    const response = await apiClient.post('/control/breaker/select', {
      node_id: nodeId,
      breaker_id: breakerId,
      action,
      reason,
      operator_id: operatorId,
    });
    return response.data;
  },

  breakerOperate: async (sessionId) => {
    const response = await apiClient.post('/control/breaker/operate', {
      session_id: sessionId,
    });
    return response.data;
  },

  breakerCancel: async (sessionId) => {
    const response = await apiClient.post('/control/breaker/cancel', {
      session_id: sessionId,
    });
    return response.data;
  },

  isolateNode: async (nodeId, operatorId, reason) => {
    const response = await apiClient.post(`/control/isolation/${nodeId}`, {
      operator_id: operatorId,
      reason,
    });
    return response.data;
  },
};
