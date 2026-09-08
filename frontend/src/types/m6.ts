// M6 報表 / AI 分析類型（對應計劃書 §5.4, §7 M6）
export interface Recommendation {
  title: string;
  detail: string;
}

export interface ReportMetrics {
  plan_id?: number;
  total_functions: number;
  total_cases: number;
  passed: number;
  failed: number;
  blocked: number;
  pending: number;
  pass_rate: number;
  fail_rate: number;
  coverage: number;
  coverage_gaps: string[];
  defects: {
    total: number;
    by_severity: Record<string, number>;
    by_status: Record<string, number>;
    open_or_in_progress: number;
    high_severity: number;
  };
  failed_cases: string[];
}

export interface Report {
  id: number;
  summary: string | null;
  recommendations: Recommendation[];
  metrics: ReportMetrics | null;
  model_name: string | null;
  generated_at: string | null;
}

export interface CompleteResult {
  plan_id: number;
  name: string;
  version: number;
  status: string;
  report_id: number;
}
