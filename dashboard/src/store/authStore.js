// Auth Store
import { create } from 'zustand';

const useAuthStore = create((set) => ({
  isAuthenticated: false,
  token: null,
  username: null,
  role: null,
  sessionId: null,
  
  login: (authData) => {
    window.sessionToken = authData.access_token;
    set({
      isAuthenticated: true,
      token: authData.access_token,
      username: authData.username,
      role: authData.role,
      sessionId: authData.session_id,
    });
  },
  
  logout: () => {
    window.sessionToken = null;
    set({
      isAuthenticated: false,
      token: null,
      username: null,
      role: null,
      sessionId: null,
    });
  },
}));

export default useAuthStore;
