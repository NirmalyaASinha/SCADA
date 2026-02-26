// Nodes API
import apiClient from './client';

export const nodesAPI = {
  getAll: async () => {
    const response = await apiClient.get('/nodes');
    return response.data;
  },

  getNode: async (nodeId) => {
    const response = await apiClient.get(`/nodes/${nodeId}`);
    return response.data;
  },

  getTelemetry: async (nodeId) => {
    const response = await apiClient.get(`/nodes/${nodeId}/telemetry`);
    return response.data;
  },

  getTelemetryHistory: async (nodeId, hours = 1) => {
    const response = await apiClient.get(`/nodes/${nodeId}/telemetry/history`, {
      params: { hours },
    });
    return response.data;
  },

  getConnections: async (nodeId) => {
    const response = await apiClient.get(`/nodes/${nodeId}/connections`);
    return response.data;
  },
};
