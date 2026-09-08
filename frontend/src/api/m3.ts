import type { SelfTest } from '../types/m3';
import { apiFetch } from './client';

const request = apiFetch;

export interface SelfTestCreateBody {
  project_id: number;
  test_function_id: number; // 必填（FR-2a）
  test_case_id: number;     // 必填（FR-2a）
  result: 'pass' | 'fail';
  tester?: string;
  notes?: string;
}

export const m3Api = {
  createSelfTest: (b: SelfTestCreateBody) =>
    request<SelfTest>('/self-tests', { method: 'POST', body: JSON.stringify(b) }),

  listSelfTests: (projectId: number, filters?: { result?: string }) => {
    const q = new URLSearchParams();
    if (filters?.result) q.set('result', filters.result);
    const qs = q.toString();
    return request<SelfTest[]>(`/projects/${projectId}/self-tests${qs ? `?${qs}` : ''}`);
  },
};
