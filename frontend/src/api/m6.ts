import type { CompleteResult, Report } from '../types/m6';
import { apiFetch } from './client';

const request = apiFetch;

// M6 報表 / AI（對應計劃書 §7 M6）
export const m6Api = {
  // Plan 標記完成 → 同步生成報表 + AI（FR-4）
  completePlan: (planId: number) => request<CompleteResult>(`/test-plans/${planId}/complete`, { method: 'POST' }),
  // 取最新報表（未就緒 → 404）
  getReport: (planId: number) => request<Report>(`/reports/${planId}`),
  // 匯出（csv | pdf，直接下載）
  exportUrl: (planId: number, format: 'csv' | 'pdf' = 'csv') =>
    `/api/v1/reports/${planId}/export?format=${format}`,
  // Email 報表（附 PDF）
  sendReport: (planId: number, to: string) =>
    request<{ ok: boolean; to: string }>(`/reports/${planId}/send`, {
      method: 'POST',
      body: JSON.stringify({ to }),
    }),
};
