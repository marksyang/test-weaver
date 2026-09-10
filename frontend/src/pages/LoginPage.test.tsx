import { describe, expect, it } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import LoginPage from './LoginPage';
import { renderPage, mockApi } from '../test/rtl';

describe('LoginPage', () => {
  it('renders the login card with username/password fields and submit button', () => {
    mockApi({ '/auth/login': { access_token: 'AT', refresh_token: 'RT' } });
    renderPage(<LoginPage />);
    expect(screen.getByText('TestWeaver')).toBeInTheDocument();
    expect(screen.getByText('測試管理平台')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('admin')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('password')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /登\s*入/ })).toBeInTheDocument();
  });

  it('submits credentials and posts to /auth/login', async () => {
    const fetchMock = mockApi({ '/auth/login': { access_token: 'AT', refresh_token: 'RT' } });
    renderPage(<LoginPage />);

    fireEvent.change(screen.getByPlaceholderText('admin'), { target: { value: 'admin' } });
    fireEvent.change(screen.getByPlaceholderText('password'), { target: { value: 'secret' } });

    // jsdom 不會在點擊 submit 按鈕時觸發表單提交 → 直接對 <form> 派發 submit
    const form = screen.getByRole('button', { name: /登\s*入/ }).closest('form')!;
    fireEvent.submit(form);

    await waitFor(
      () =>
        expect(fetchMock).toHaveBeenCalledWith(
          expect.stringContaining('/auth/login'),
          expect.anything(),
        ),
      { timeout: 2000 },
    );
  });
});
