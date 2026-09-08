// FR-5 稽核日誌類型
export interface AuditLog {
  id: number;
  user_id: number | null;
  username: string | null;
  action: string;
  method: string;
  path: string;
  status_code: number;
  ip: string | null;
  detail: string | null;
  created_at: string | null;
}
