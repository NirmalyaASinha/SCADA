// Grid API
import apiClient from './client';

export const gridAPI = {
  getOverview: async () => {
    const response = await apiClient.get('/grid/overview');
    return response.data;
  },

  getTopology: async () => {
    const response = await apiClient.get('/grid/topology');
    return response.data;
  },
};
