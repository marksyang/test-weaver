import { apiFetch } from './client';
import type { AuthUser, LoginResult } from '../types/auth';

// FR-5 / M8 認證 API
export const authApi = {
  login: (username: string, password: string) =>
    apiFetch<LoginResult>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  me: () => apiFetch<AuthUser>('/auth/me'),
  // 登出：撤銷 refresh token（client 內部另於 401 自動 refresh）
  logout: (refreshToken: string) =>
    apiFetch<{ ok: boolean }>('/auth/logout', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: refreshToken }),
    }),
};
