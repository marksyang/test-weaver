export type RevisionStatus = 'open' | 'accepted' | 'rejected' | 'done';

export interface RevisionRequest {
  id: number;
  defect_id: number | null;
  test_plan_id: number;
  reason: string | null;
  proposed_change: string | null;
  status: RevisionStatus;
  requested_by: string | null;
  created_at: string | null;
}

export interface RevisionCreateBody {
  test_plan_id: number;
  reason?: string;
  proposed_change?: string;
  requested_by?: string;
}
