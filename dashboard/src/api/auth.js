// Authentication API
import apiClient from './client';

export const authAPI = {
  login: async (username, password) => {
    const response = await apiClient.post('/auth/login', {
      username,
      password,
    });
    return response.data;
  },

  logout: async () => {
    const response = await apiClient.post('/auth/logout');
    return response.data;
  },

  getProfile: async () => {
    const response = await apiClient.get('/auth/me');
    return response.data;
  },

  getSessions: async () => {
    const response = await apiClient.get('/auth/sessions');
    return response.data;
  },

  forceLogout: async (sessionId) => {
    const response = await apiClient.delete(`/auth/sessions/${sessionId}`);
    return response.data;
  },
};
