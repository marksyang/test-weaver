import type {
  Category,
  Project,
  SpecFile,
  TaskStatus,
  TestItemRow,
} from '../types/m1';
import { apiFetch } from './client';

const request = apiFetch;

const post = <T>(path: string, body?: unknown): Promise<T> =>
  request<T>(path, {
    method: 'POST',
    body: body instanceof FormData ? body : body === undefined ? undefined : JSON.stringify(body),
  });

export const m1Api = {
  // 專案
  listProjects: () => request<Project[]>('/projects'),
  createProject: (b: { name: string; description?: string }) => post<Project>('/projects', b),
  getProject: (id: number) => request<Project>(`/projects/${id}`),

  // 規格書
  listSpecs: (projectId: number) => request<SpecFile[]>(`/projects/${projectId}/spec-files`),
  uploadSpec: (projectId: number, file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return post<SpecFile>(`/projects/${projectId}/spec-files`, fd);
  },

  // AI 生成測試項目
  generateItems: (projectId: number, specFileId: number) =>
    post<{ task_id: string; status: string }>(
      `/projects/${projectId}/spec-files/${specFileId}/generate-items`,
    ),

  // 測試項目
  listTestItems: (projectId: number) =>
    request<TestItemRow[]>(`/projects/${projectId}/test-items`),

  // 共通類別平台
  listCategories: () => request<Category[]>('/platform/categories'),
  createCategory: (b: { name: string; code?: string; description?: string }) =>
    post<Category>('/platform/categories', b),

  // 通用任務狀態
  taskStatus: (id: string) => request<TaskStatus>(`/tasks/${encodeURIComponent(id)}`),
};
