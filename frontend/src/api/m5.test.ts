import { afterEach, describe, expect, it, vi } from 'vitest';
import { m5Api } from './m5';
import { mockFetch, res } from '../test/fetch';

afterEach(() => vi.unstubAllGlobals());
const base: { id: number; status: string } = { id: 1, status: 'open' };

describe('m5Api', () => {
  it('listRevisions builds query (status before test_plan_id)', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res([base]));
    await m5Api.listRevisions({ test_plan_id: 3, status: 'open' });
    const [url] = f.mock.calls[0] as [string];
    expect(url).toBe('/api/v1/revision-requests?status=open&test_plan_id=3');
  });

  it('createRevision POSTs body (M6 one-click → RR)', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ ...base, id: 7 }, 201));
    const out = await m5Api.createRevision({ test_plan_id: 3, reason: 'R', proposed_change: 'C' });
    expect(out.id).toBe(7);
    const [url, init] = f.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/revision-requests');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(init!.body as string)).toMatchObject({ test_plan_id: 3, reason: 'R' });
  });

  it('accept/reject/complete hit the right action verbs', async () => {
    const f = mockFetch();
    f.mockResolvedValue(res(base));
    await m5Api.accept(4);
    await m5Api.reject(4, 'because');
    await m5Api.complete(4);
    expect(f).toHaveBeenCalledTimes(3);
    const urls = f.mock.calls.map(([u]) => u as string);
    expect(urls).toEqual([
      '/api/v1/revision-requests/4/accept',
      '/api/v1/revision-requests/4/reject',
      '/api/v1/revision-requests/4/complete',
    ]);
  });

  it('reject body carries reason', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res(base));
    await m5Api.reject(4, 'dup');
    const [url, init] = f.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/revision-requests/4/reject');
    expect(JSON.parse(init!.body as string)).toEqual({ reason: 'dup' });
  });
});
