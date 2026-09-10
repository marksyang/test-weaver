import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import SettingsPage from './SettingsPage';
import { renderPage, mockApi } from '../test/rtl';

describe('SettingsPage', () => {
  it('loads users + audit logs and renders the account-management tab', async () => {
    mockApi({
      '/audit/logs': [
        { id: 1, username: 'admin', action: 'login', method: 'POST', path: '/auth/login', status_code: 200, ip: '127.0.0.1', created_at: '2026-01-01T00:00:00Z' },
      ],
      '/users': [{ id: 1, username: 'carol', role: 'qa_lead', is_active: true, created_at: '2026-01-01T00:00:00Z' }],
      '/teams': [],
    });
    renderPage(<SettingsPage />);

    expect(screen.getByText('系統設定（admin）')).toBeInTheDocument();
    // tab 標籤（稽核日誌非 active，內容不渲染，故唯一）
    expect(screen.getByText('稽核日誌')).toBeInTheDocument();

    // active = 帳號管理：新增帳號按鈕 + 使用者行
    expect(await screen.findByText('新增帳號')).toBeInTheDocument();
    expect(await screen.findByText('carol')).toBeInTheDocument();
  });
});
