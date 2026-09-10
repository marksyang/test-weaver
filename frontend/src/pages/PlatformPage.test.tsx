import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import PlatformPage from './PlatformPage';
import { renderPage, mockApi } from '../test/rtl';

describe('PlatformPage', () => {
  it('loads the platform categories and renders the create form', async () => {
    mockApi({
      '/categories': [{ id: 1, name: '登入', code: 'LOGIN', description: '登入相關' }],
      '/teams': [],
    });
    renderPage(<PlatformPage />);

    expect(screen.getByText('共通類別平台')).toBeInTheDocument();
    expect(screen.getByText(/FR-1a/)).toBeInTheDocument();

    // 載入的類別行 + 底部計數
    expect(await screen.findByText('登入')).toBeInTheDocument();
    expect(screen.getByText('LOGIN')).toBeInTheDocument();
    expect(screen.getByText(/平台類別計 1 筆/)).toBeInTheDocument();
  });
});
