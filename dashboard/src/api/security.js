// Security API
import apiClient from './client';

export const securityAPI = {
  getConnections: async () => {
    const response = await apiClient.get('/security/connections');
    return response.data;
  },

  getAuditLog: async (limit = 1000) => {
    const response = await apiClient.get('/security/audit', {
      params: { limit },
    });
    return response.data;
  },
};
