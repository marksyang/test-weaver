import { afterEach, describe, expect, it, vi } from 'vitest';
import { m4Api } from './m4';
import { mockFetch, res } from '../test/fetch';

afterEach(() => vi.unstubAllGlobals());

describe('m4Api', () => {
  it('executeCase POSTs to /test-executions (Fail → defect)', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ execution: { id: 1 }, defect: { id: 2 } }, 201));
    const out = await m4Api.executeCase({ test_case_id: 3, result: 'fail' });
    expect(out.defect?.id).toBe(2);
    const [url, init] = f.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/test-executions');
    expect(JSON.parse(init!.body as string)).toMatchObject({ test_case_id: 3, result: 'fail' });
  });

  it('listDefects combines status + severity filters', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res([]));
    await m4Api.listDefects({ status: 'open', severity: 'high' });
    const [url] = f.mock.calls[0] as [string];
    expect(url).toBe('/api/v1/defects?status=open&severity=high');
  });

  it('createDefect allows null test_case_id (FR-3a)', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ id: 9 }, 201));
    await m4Api.createDefect({ title: 'T', test_case_id: null });
    const [url, init] = f.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/defects');
    expect(JSON.parse(init!.body as string).test_case_id).toBeNull();
  });

  it('patchDefect PATCHes status/assignee', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ id: 9, status: 'fixed' }));
    await m4Api.patchDefect(9, { status: 'fixed', assigned_to: 'bob' });
    const [url, init] = f.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/defects/9');
    expect(init?.method).toBe('PATCH');
  });
});
