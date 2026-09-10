import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import DefectPage from './DefectPage';
import { renderPage, mockApi } from '../test/rtl';

const defect = {
  id: 7,
  title: 'BUG 標題',
  severity: 'high',
  status: 'open',
  case_name: null,
  assigned_to: 'qa',
  created_at: '2026-01-01T00:00:00Z',
};

describe('DefectPage', () => {
  it('renders the execution form + defect list and loads defects', async () => {
    // '/test-plans' 需在前：listPlans 的 URL `/projects/{id}/test-plans` 也含 '/projects'，
    // mockApi 依子字串「首個命中」回傳，故具體 key 要先列。
    mockApi({
      '/test-plans': [],
      '/projects': [{ id: 1, name: 'P1' }],
      '/defects': [defect],
      '/teams': [],
    });
    renderPage(<DefectPage />);

    expect(screen.getByText(/FR-3 \/ FR-3a/)).toBeInTheDocument();
    expect(await screen.findByText('執行測試案例')).toBeInTheDocument();
    expect(screen.getByText('缺陷列表')).toBeInTheDocument();
    // 異步載入的缺陷標題 + 嚴重度 tag
    expect(await screen.findByText('BUG 標題')).toBeInTheDocument();
    expect(screen.getByText('high')).toBeInTheDocument();
  });

  it('shows the manual-defect modal trigger', () => {
    mockApi({ '/projects': [], '/defects': [], '/teams': [] });
    renderPage(<DefectPage />);
    expect(screen.getByRole('button', { name: /手動建立/ })).toBeInTheDocument();
  });
});
