import { afterEach, describe, expect, it, vi } from 'vitest';
import { m6Api } from './m6';
import { mockFetch, res } from '../test/fetch';

afterEach(() => vi.unstubAllGlobals());

describe('m6Api', () => {
  it('completePlan POSTs to /test-plans/{id}/complete', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ plan_id: 1, status: 'completed', report_id: 5 }));
    const out = await m6Api.completePlan(1);
    expect(out.report_id).toBe(5);
    const [url, init] = f.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/test-plans/1/complete');
    expect(init?.method).toBe('POST');
  });

  it('getReport → GET /reports/{id}', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ id: 5, summary: 's', recommendations: [], metrics: {} }));
    await m6Api.getReport(1);
    const [url] = f.mock.calls[0] as [string];
    expect(url).toBe('/api/v1/reports/1');
  });

  it('getReport throws 404 when report not ready', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ detail: 'report not ready' }, 404));
    await expect(m6Api.getReport(1)).rejects.toThrow(/404/);
  });

  it('exportUrl points to csv/pdf endpoint without fetching', async () => {
    const f = mockFetch();
    expect(m6Api.exportUrl(1)).toBe('/api/v1/reports/1/export?format=csv');
    expect(m6Api.exportUrl(1, 'pdf')).toBe('/api/v1/reports/1/export?format=pdf');
    expect(f).not.toHaveBeenCalled();
  });

  it('sendReport POSTs {to} to /reports/{id}/send', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ ok: true, to: 'a@b.com' }));
    const out = await m6Api.sendReport(1, 'a@b.com');
    expect(out.ok).toBe(true);
    const [url, init] = f.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/reports/1/send');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(init!.body as string)).toEqual({ to: 'a@b.com' });
  });
});
