import type {
  PlanTree,
  TestCase,
  TestFunction,
  TestPlan,
} from '../types/m2';
import { apiFetch } from './client';

const request = apiFetch;

const post = <T>(path: string, body?: unknown): Promise<T> =>
  request<T>(path, { method: 'POST', body: JSON.stringify(body ?? {}) });
const patch = <T>(path: string, body?: unknown): Promise<T> =>
  request<T>(path, { method: 'PATCH', body: JSON.stringify(body ?? {}) });

export const m2Api = {
  // Plan
  listPlans: (projectId: number) => request<TestPlan[]>(`/projects/${projectId}/test-plans`),
  createPlan: (projectId: number, b: { name: string; test_item_ids?: number[] }) =>
    post<TestPlan>(`/projects/${projectId}/test-plans`, b),
  getPlan: (id: number) => request<TestPlan>(`/test-plans/${id}`),
  patchPlan: (id: number, b: { name?: string; status?: string }) =>
    patch<TestPlan>(`/test-plans/${id}`, b),
  createRevision: (id: number) => post<TestPlan>(`/test-plans/${id}/revisions`, {}),

  // Function
  createFunction: (planId: number, b: { name: string; description?: string }) =>
    post<TestFunction>(`/test-plans/${planId}/functions`, b),
  patchFunction: (id: number, b: { name?: string; description?: string; sort_order?: number }) =>
    patch<TestFunction>(`/test-functions/${id}`, b),

  // Case
  createCase: (
    functionId: number,
    b: { name: string; precondition?: string; steps?: string; expected_result?: string; priority?: string },
  ) => post<TestCase>(`/functions/${functionId}/cases`, b),
  patchCase: (id: number, b: Partial<Omit<TestCase, 'id' | 'test_function_id'>>) =>
    patch<TestCase>(`/test-cases/${id}`, b),
  patchCaseStatus: (id: number, status: string) =>
    patch<TestCase>(`/test-cases/${id}/status`, { status }),

  // Tree
  tree: (planId: number) => request<PlanTree>(`/test-plans/${planId}/tree`),
};
