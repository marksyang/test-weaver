import { afterEach, describe, expect, it, vi } from 'vitest';
import { m2Api } from './m2';
import { mockFetch, res } from '../test/fetch';

afterEach(() => vi.unstubAllGlobals());

describe('m2Api', () => {
  it('listPlans → GET /projects/{id}/test-plans', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res([{ id: 1, name: 'P', version: 1, status: 'draft' }]));
    await m2Api.listPlans(9);
    const [url] = f.mock.calls[0] as [string];
    expect(url).toBe('/api/v1/projects/9/test-plans');
  });

  it('createPlan POSTs name + test_item_ids', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ id: 5, name: 'P' }, 201));
    await m2Api.createPlan(9, { name: 'P', test_item_ids: [1, 2] });
    const [url, init] = f.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/projects/9/test-plans');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(init!.body as string)).toEqual({ name: 'P', test_item_ids: [1, 2] });
  });

  it('patchPlan sends PATCH to /test-plans/{id}', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ id: 5, status: 'completed' }));
    await m2Api.patchPlan(5, { status: 'completed' });
    const [url, init] = f.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/test-plans/5');
    expect(init?.method).toBe('PATCH');
  });

  it('createCase targets /functions/{id}/cases', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ id: 3 }, 201));
    await m2Api.createCase(4, { name: 'C' });
    const [url] = f.mock.calls[0] as [string];
    expect(url).toBe('/api/v1/functions/4/cases');
  });

  it('tree → GET /test-plans/{id}/tree', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ plan: { id: 1 }, functions: [], cases: [] }));
    await m2Api.tree(1);
    const [url] = f.mock.calls[0] as [string];
    expect(url).toBe('/api/v1/test-plans/1/tree');
  });

  it('propagates API errors with status', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ detail: '409 conflict' }, 409));
    await expect(m2Api.patchPlan(5, { status: 'completed' })).rejects.toThrow(/409/);
  });
});
