// 多團隊（v1.1 T2）：team CRUD + members 管理 API client。
import { apiFetch } from './client';

export interface Team {
  id: number;
  name: string;
  description?: string | null;
  my_role?: string | null; // 當前使用者在此 team 的團隊級角色（非成員→null）
}

export interface Member {
  user_id: number;
  username: string;
  role: string; // owner / qa_lead / tester
}

export const TEAM_ROLES = ['owner', 'qa_lead', 'tester'] as const;

export const teamsApi = {
  list: () => apiFetch<Team[]>('/teams'),
  create: (b: { name: string; description?: string }) =>
    apiFetch<Team>('/teams', { method: 'POST', body: JSON.stringify(b) }),
  get: (id: number) => apiFetch<Team>(`/teams/${id}`),
  update: (id: number, b: { name?: string; description?: string }) =>
    apiFetch<Team>(`/teams/${id}`, { method: 'PATCH', body: JSON.stringify(b) }),

  listMembers: (id: number) => apiFetch<Member[]>(`/teams/${id}/members`),
  addMember: (id: number, b: { user_id: number; role: string }) =>
    apiFetch<Member>(`/teams/${id}/members`, { method: 'POST', body: JSON.stringify(b) }),
  setMemberRole: (id: number, userId: number, role: string) =>
    apiFetch<Member>(`/teams/${id}/members/${userId}`, { method: 'PATCH', body: JSON.stringify({ role }) }),
  removeMember: (id: number, userId: number) =>
    apiFetch<void>(`/teams/${id}/members/${userId}`, { method: 'DELETE' }),
  deleteTeam: (id: number) => apiFetch<void>(`/teams/${id}`, { method: 'DELETE' }),
};
