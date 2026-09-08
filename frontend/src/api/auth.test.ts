import { afterEach, describe, expect, it, vi } from 'vitest';
import { authApi } from './auth';
import { configureAuth } from './client';
import { mockFetch, res } from '../test/fetch';

afterEach(() => {
  vi.unstubAllGlobals();
  configureAuth({ getToken: () => null, onUnauthorized: () => {} });
});

describe('authApi', () => {
  it('login POSTs username/password to /auth/login', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(
      res({ access_token: 't', token_type: 'bearer', user: { id: 1, username: 'admin', role: 'admin' } }),
    );
    const out = await authApi.login('admin', 'p');
    expect(out.access_token).toBe('t');
    const [url, init] = f.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/auth/login');
    expect(JSON.parse(init!.body as string)).toEqual({ username: 'admin', password: 'p' });
  });

  it('login propagates 401 (wrong credentials)', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ detail: 'invalid credentials' }, 401));
    await expect(authApi.login('admin', 'wrong')).rejects.toThrow(/401/);
  });

  it('me GETs /auth/me', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ id: 1, username: 'admin', role: 'admin' }));
    const u = await authApi.me();
    expect(u.role).toBe('admin');
    const [url] = f.mock.calls[0] as [string];
    expect(url).toBe('/api/v1/auth/me');
  });
});
