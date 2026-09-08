export type DefectStatus = 'open' | 'in_progress' | 'resolved' | 'closed';

export interface TestExecution {
  id: number;
  test_case_id: number;
  case_name: string | null;
  test_plan_id: number;
  executed_by: string | null;
  result: 'pass' | 'fail' | 'blocked';
  actual_result: string | null;
  executed_at: string | null;
}

export interface Defect {
  id: number;
  execution_id: number | null;
  test_case_id: number | null;
  case_name: string | null;
  title: string;
  description: string | null;
  severity: string;
  priority: string;
  status: DefectStatus;
  assigned_to: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ExecuteOut {
  execution: TestExecution;
  defect: Defect | null;
}
