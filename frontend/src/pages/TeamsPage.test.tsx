import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import TeamsPage from './TeamsPage';
import { renderPage, mockApi } from '../test/rtl';

describe('TeamsPage', () => {
  it('loads the current team members + shows the create-team card', async () => {
    mockApi({
      '/members': [{ user_id: 1, username: 'alice', role: 'owner' }],
      '/teams': [{ id: 1, name: '電商品質組', my_role: 'owner' }],
    });
    renderPage(<TeamsPage />);

    expect(screen.getByText('團隊成員')).toBeInTheDocument();
    expect(screen.getByText('建立新團隊')).toBeInTheDocument();
    // 成員自動載入（登入者為 null → 角色欄顯示文字、無管理按鈕）
    expect(await screen.findByText('alice')).toBeInTheDocument();
    expect(screen.getByText('Owner')).toBeInTheDocument();
  });
});
