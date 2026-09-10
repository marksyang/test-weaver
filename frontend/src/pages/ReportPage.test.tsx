import { describe, expect, it } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import ReportPage from './ReportPage';
import { renderPage, mockApi } from '../test/rtl';

const report = {
  id: 1,
  test_plan_id: 1,
  model_name: 'offline',
  summary: '整體通過率良好',
  metrics: {
    pass_rate: 0.9,
    total_cases: 10,
    passed: 9,
    failed: 1,
    blocked: 0,
    pending: 0,
    coverage: 0.85,
    coverage_gaps: ['登入'],
    failed_cases: ['案例X'],
    defects: { total: 2, open_or_in_progress: 1, by_severity: { critical: 0, high: 1, medium: 1, low: 0 } },
  },
  recommendations: [{ title: '建議A', detail: '補充登入用例' }],
};

const routes = {
  '/test-plans': [{ id: 1, name: 'P1', version: 1, status: 'draft' }],
  '/reports': report,
  '/projects': [{ id: 1, name: 'P1' }],
  '/teams': [],
};

describe('ReportPage', () => {
  it('renders the project/plan selectors on load', () => {
    mockApi(routes);
    renderPage(<ReportPage />);
    expect(screen.getByText('專案')).toBeInTheDocument();
    expect(screen.getByText('測試計畫')).toBeInTheDocument();
  });

  it('selects a plan → loads the report (stat cards + AI recommendations)', async () => {
    mockApi(routes);
    renderPage(<ReportPage />);
    const planSelect = await screen.findByText('選測試計畫');
    fireEvent.mouseDown(planSelect);
    const option = await screen.findByText(/#1 P1 v1/);
    fireEvent.click(option);

    // 報表正文（指標卡 + AI 建議）
    expect(await screen.findByText('通過率')).toBeInTheDocument();
    expect(screen.getByText('整體通過率良好')).toBeInTheDocument();
    expect(screen.getByText('AI 分析建議（可一鍵轉 Revision Request）')).toBeInTheDocument();
    expect(screen.getByText('建議A')).toBeInTheDocument();
  });
});
