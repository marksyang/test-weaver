import type { Defect, ExecuteOut, TestExecution } from '../types/m4';
import { apiFetch } from './client';

const request = apiFetch;

export const m4Api = {
  // 執行案例（Fail → 自動開 Defect）
  executeCase: (b: {
    test_case_id: number;
    result: 'pass' | 'fail' | 'blocked';
    executed_by?: string;
    actual_result?: string;
  }) => request<ExecuteOut>('/test-executions', { method: 'POST', body: JSON.stringify(b) }),

  caseExecutions: (caseId: number) =>
    request<TestExecution[]>(`/test-cases/${caseId}/executions`),

  // 缺陷
  listDefects: (filters?: { status?: string; severity?: string }) => {
    const q = new URLSearchParams();
    if (filters?.status) q.set('status', filters.status);
    if (filters?.severity) q.set('severity', filters.severity);
    const qs = q.toString();
    return request<Defect[]>(`/defects${qs ? `?${qs}` : ''}`);
  },
  getDefect: (id: number) => request<Defect>(`/defects/${id}`),
  createDefect: (b: {
    title: string;
    description?: string;
    severity?: string;
    priority?: string;
    test_case_id?: number | null;
  }) => request<Defect>('/defects', { method: 'POST', body: JSON.stringify(b) }),
  patchDefect: (id: number, b: { status?: string; assigned_to?: string }) =>
    request<Defect>(`/defects/${id}`, { method: 'PATCH', body: JSON.stringify(b) }),
};
