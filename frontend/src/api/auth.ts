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
};
