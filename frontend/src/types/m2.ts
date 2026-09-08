export type PlanStatus = 'draft' | 'in_progress' | 'completed' | 'archived';
export type CaseStatus = 'draft' | 'ready' | 'passed' | 'failed' | 'blocked';

export interface TestPlan {
  id: number;
  project_id: number;
  name: string;
  version: number;
  status: PlanStatus;
  created_by?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface TestFunction {
  id: number;
  test_plan_id: number;
  name: string;
  description?: string | null;
  sort_order: number;
}

export interface TestCase {
  id: number;
  test_function_id: number;
  name: string;
  precondition?: string | null;
  steps?: string | null;
  expected_result?: string | null;
  priority: string;
  status: CaseStatus;
  sort_order: number;
}

export interface FunctionNode {
  id: number;
  name: string;
  description?: string | null;
  sort_order: number;
  cases: TestCase[];
}

export interface PlanTree {
  id: number;
  project_id: number;
  name: string;
  version: number;
  status: PlanStatus;
  functions: FunctionNode[];
}
