export interface SelfTest {
  id: number;
  project_id: number;
  tester: string | null;
  test_function_id: number;
  function_name: string | null;
  test_case_id: number;
  case_name: string | null;
  result: 'pass' | 'fail';
  notes: string | null;
  executed_at: string | null;
}
