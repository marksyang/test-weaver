import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiFetch, configureAuth } from './client';
import { mockFetch, res } from '../test/fetch';

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
  configureAuth({ getToken: () => null, onUnauthorized: () => {} });
});

describe('apiFetch (FR-5)', () => {
  it('sends no Authorization header when there is no token', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ ok: 1 }));
    await apiFetch('/x');
    const init = f.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>)['Authorization']).toBeUndefined();
  });

  it('injects a Bearer token when present', async () => {
    configureAuth({ getToken: () => 'tok123' });
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ ok: 1 }));
    await apiFetch('/x');
    const init = f.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>)['Authorization']).toBe('Bearer tok123');
  });

  it('throws with the status on non-2xx', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ detail: 'bad' }, 400));
    await expect(apiFetch('/x')).rejects.toThrow(/400/);
  });

  it('invokes onUnauthorized exactly once on 401', async () => {
    const onUnauthorized = vi.fn();
    configureAuth({ getToken: () => 'x', onUnauthorized });
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ detail: 'unauthorized' }, 401));
    await expect(apiFetch('/x')).rejects.toThrow(/401/);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it('does not call onUnauthorized for other errors (e.g. 500)', async () => {
    const onUnauthorized = vi.fn();
    configureAuth({ getToken: () => null, onUnauthorized });
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ detail: 'boom' }, 500));
    await expect(apiFetch('/x')).rejects.toThrow(/500/);
    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it('refreshes on 401 then retries with the new access token', async () => {
    localStorage.setItem('tw_token', 'old-access');
    localStorage.setItem('tw_refresh', 'old-refresh');
    configureAuth({ getToken: () => localStorage.getItem('tw_token') });
    const f = mockFetch();
    // 1) /x with old-access -> 401
    f.mockResolvedValueOnce(res({ detail: 'unauthorized' }, 401));
    // 2) /auth/refresh -> 200 { new tokens }
    f.mockResolvedValueOnce(
      res({ access_token: 'new-access', refresh_token: 'new-refresh' }, 200),
    );
    // 3) /x retried with new-access -> 200
    f.mockResolvedValueOnce(res({ ok: 1 }));
    const out = await apiFetch('/x');
    expect(out).toEqual({ ok: 1 });
    expect(f).toHaveBeenCalledTimes(3);
    const thirdHeaders = f.mock.calls[2][1].headers as Record<string, string>;
    expect(thirdHeaders['Authorization']).toBe('Bearer new-access');
    expect(localStorage.getItem('tw_token')).toBe('new-access');
  });

  it('does not attempt refresh on /auth/login', async () => {
    localStorage.setItem('tw_refresh', 'r');
    const onUnauthorized = vi.fn();
    configureAuth({ getToken: () => 'x', onUnauthorized });
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ detail: 'bad creds' }, 401));
    await expect(apiFetch('/auth/login', { method: 'POST' })).rejects.toThrow(/401/);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    expect(f).toHaveBeenCalledTimes(1); // 沒有觸發 refresh
  });

  it('calls onUnauthorized when there is no refresh token to rotate', async () => {
    localStorage.setItem('tw_token', 'old');
    const onUnauthorized = vi.fn();
    configureAuth({ getToken: () => 'old', onUnauthorized });
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ detail: 'unauthorized' }, 401));
    await expect(apiFetch('/x')).rejects.toThrow(/401/);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    expect(f).toHaveBeenCalledTimes(1); // 無 refresh token → 不發 refresh request
  });
});
