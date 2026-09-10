import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import SelfTestPage from './SelfTestPage';
import { renderPage, mockApi } from '../test/rtl';

describe('SelfTestPage', () => {
  it('loads projects/self-tests and shows the Function+Case binding prompt', async () => {
    mockApi({
      '/self-tests': [
        { id: 1, function_name: 'F1', case_name: 'C1', result: 'pass', tester: 'me', notes: '', executed_at: '2026-01-01T00:00:00Z' },
      ],
      '/test-plans': [],
      '/projects': [{ id: 1, name: 'P1' }],
      '/teams': [],
    });
    renderPage(<SelfTestPage />);

    expect(screen.getByText(/FR-2a/)).toBeInTheDocument();
    expect(screen.getByText('錄入自測')).toBeInTheDocument();
    expect(screen.getByText('自測紀錄')).toBeInTheDocument();

    // 未選計畫 → 提示；自測紀錄行載入
    expect(await screen.findByText('請先選擇專案與測試計畫')).toBeInTheDocument();
    expect(await screen.findByText('F1')).toBeInTheDocument();
  });
});
