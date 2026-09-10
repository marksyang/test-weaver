import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import PlanPage from './PlanPage';
import { renderPage, mockApi } from '../test/rtl';

describe('PlanPage', () => {
  it('loads projects/specs/items and exposes the plan tabs + rows', async () => {
    mockApi({
      '/spec-files': [
        { id: 1, file_name: 'spec.md', format: 'md', status: 'done', char_count: 120 },
      ],
      '/test-items': [
        {
          id: 1,
          name: '登入測試',
          category: { name: '登入', code: 'LOGIN' },
          matched_by: 'exact',
          similarity: 0.91,
          is_newly_created: false,
          description: 'desc',
        },
      ],
      '/projects': [{ id: 1, name: 'P1' }],
      '/teams': [],
    });
    renderPage(<PlanPage />);

    expect(screen.getByText('測試計畫工作台')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /新增專案/ })).toBeInTheDocument();

    // 專案載入後切到 Tabs，並顯示載入的規格書與測試項目
    expect(await screen.findByText('規格書 → 測試項目')).toBeInTheDocument();
    expect(await screen.findByText('spec.md')).toBeInTheDocument();
    expect(screen.getByText('登入測試')).toBeInTheDocument();
    expect(screen.getByText('exact')).toBeInTheDocument();
  });
});
