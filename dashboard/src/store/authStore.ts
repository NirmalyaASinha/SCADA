import { create } from 'zustand';
import { loginRequest } from '../api/auth';
import type { AuthUser, Role } from '../types';

type AuthState = {
  token: string | null;
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  hasRole: (role: Role) => boolean;
};

const roleRank: Record<Role, number> = {
  viewer: 0,
  operator: 1,
  engineer: 2,
  admin: 3,
};

export const useAuthStore = create<AuthState>((set, get) => ({
  token: null,
  user: null,
  isAuthenticated: false,
  isLoading: false,
  async login(username, password) {
    set({ isLoading: true });
    try {
      const { token, user } = await loginRequest(username, password);
      set({ token, user, isAuthenticated: true, isLoading: false });
    } catch (error) {
      set({ isLoading: false });
      throw error;
    }
  },
  logout() {
    set({ token: null, user: null, isAuthenticated: false });
  },
  hasRole(requiredRole) {
    const current = get().user?.role || 'viewer';
    return roleRank[current] >= roleRank[requiredRole];
  },
}));
