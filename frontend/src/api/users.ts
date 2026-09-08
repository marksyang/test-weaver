import { apiFetch } from './client';
import type { ManagedUser, UserCreateBody, UserUpdateBody } from '../types/user';

// FR-5 帳號管理 API（admin）
export const usersApi = {
  list: () => apiFetch<ManagedUser[]>('/users'),
  create: (body: UserCreateBody) =>
    apiFetch<ManagedUser>('/users', { method: 'POST', body: JSON.stringify(body) }),
  update: (id: number, body: UserUpdateBody) =>
    apiFetch<ManagedUser>(`/users/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
};
