import apiClient from './client';
import type { AuthUser } from '../types';

export type LoginResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  role: string;
  username: string;
  expires_in: number;
  last_login: string;
  session_id: string;
};

export async function loginRequest(username: string, password: string): Promise<{ token: string; user: AuthUser }> {
  const response = await apiClient.post<LoginResponse>('/auth/login', {
    username,
    password,
  });

  return {
    token: response.data.access_token,
    user: {
      username: response.data.username,
      role: response.data.role as AuthUser['role'],
    },
  };
}
