import type { RevisionCreateBody, RevisionRequest } from '../types/m5';
import { apiFetch } from './client';

const request = apiFetch;

export const m5Api = {
  // 手動建立修改要求（M6 報表「一鍵轉 Revision Request」）
  createRevision: (body: RevisionCreateBody) =>
    request<RevisionRequest>('/revision-requests', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  listRevisions: (filters?: { status?: string; test_plan_id?: number }) => {
    const q = new URLSearchParams();
    if (filters?.status) q.set('status', filters.status);
    if (filters?.test_plan_id != null) q.set('test_plan_id', String(filters.test_plan_id));
    const qs = q.toString();
    return request<RevisionRequest[]>(`/revision-requests${qs ? `?${qs}` : ''}`);
  },
  getRevision: (id: number) => request<RevisionRequest>(`/revision-requests/${id}`),
  accept: (id: number) =>
    request<RevisionRequest>(`/revision-requests/${id}/accept`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),
  reject: (id: number, reason: string) =>
    request<RevisionRequest>(`/revision-requests/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
  complete: (id: number) =>
    request<RevisionRequest>(`/revision-requests/${id}/complete`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),
};
