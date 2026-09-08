import { afterEach, describe, expect, it, vi } from 'vitest';
import { auditApi } from './audit';
import { configureAuth } from './client';
import { mockFetch, res } from '../test/fetch';

afterEach(() => {
  vi.unstubAllGlobals();
  configureAuth({ getToken: () => null, onUnauthorized: () => {} });
});

describe('auditApi', () => {
  it('logs GETs /audit/logs with limit param', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(
      res([{ id: 1, action: 'auth.login', method: 'POST', path: '/x', status_code: 200 }]),
    );
    const rows = await auditApi.logs();
    expect(rows[0].action).toBe('auth.login');
    const [url] = f.mock.calls[0] as [string];
    expect(url).toBe('/api/v1/audit/logs?limit=50');
  });

  it('respects a custom limit', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res([]));
    await auditApi.logs(10);
    const [url] = f.mock.calls[0] as [string];
    expect(url).toBe('/api/v1/audit/logs?limit=10');
  });
});
