// Alarms API
import apiClient from './client';

export const alarmsAPI = {
  getActive: async () => {
    const response = await apiClient.get('/alarms/active');
    return response.data;
  },

  acknowledge: async (alarmId, operatorId, comment) => {
    const response = await apiClient.post(`/alarms/${alarmId}/acknowledge`, {
      operator_id: operatorId,
      comment,
    });
    return response.data;
  },
};
