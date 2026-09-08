import type { CompleteResult, Report } from '../types/m6';
import { apiFetch } from './client';

const request = apiFetch;

// M6 報表 / AI（對應計劃書 §7 M6）
export const m6Api = {
  // Plan 標記完成 → 同步生成報表 + AI（FR-4）
  completePlan: (planId: number) => request<CompleteResult>(`/test-plans/${planId}/complete`, { method: 'POST' }),
  // 取最新報表（未就緒 → 404）
  getReport: (planId: number) => request<Report>(`/reports/${planId}`),
  // CSV 匯出（直接下載）
  exportUrl: (planId: number) => `/api/v1/reports/${planId}/export`,
};
