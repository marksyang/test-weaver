import { apiFetch } from './client';
import type { AuditLog } from '../types/audit';

// FR-5 稽核日誌 API（admin）
export const auditApi = {
  logs: (limit = 50) => apiFetch<AuditLog[]>(`/audit/logs?limit=${limit}`),
};
