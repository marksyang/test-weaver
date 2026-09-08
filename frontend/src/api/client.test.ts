import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiFetch, configureAuth } from './client';
import { mockFetch, res } from '../test/fetch';

afterEach(() => {
  vi.unstubAllGlobals();
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
});
