import { afterEach, describe, expect, it, vi } from 'vitest';
import { m3Api } from './m3';
import { mockFetch, res } from '../test/fetch';

afterEach(() => vi.unstubAllGlobals());

describe('m3Api', () => {
  it('createSelfTest POSTs full body (FR-2a required fields)', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ id: 1, result: 'pass' }, 201));
    const out = await m3Api.createSelfTest({
      project_id: 1,
      test_function_id: 2,
      test_case_id: 3,
      result: 'pass',
    });
    expect(out.id).toBe(1);
    const [url, init] = f.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/self-tests');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(init!.body as string)).toMatchObject({
      test_function_id: 2,
      test_case_id: 3,
    });
  });

  it('listSelfTests includes result filter in query', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res([]));
    await m3Api.listSelfTests(1, { result: 'fail' });
    const [url] = f.mock.calls[0] as [string];
    expect(url).toBe('/api/v1/projects/1/self-tests?result=fail');
  });

  it('listSelfTests omits query when no filter', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res([]));
    await m3Api.listSelfTests(1);
    const [url] = f.mock.calls[0] as [string];
    expect(url).toBe('/api/v1/projects/1/self-tests');
  });

  it('throws on non-2xx', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ detail: 'must bind function+case' }, 422));
    await expect(
      m3Api.createSelfTest({ project_id: 1, test_function_id: 2, test_case_id: 3, result: 'pass' }),
    ).rejects.toThrow(/422/);
  });
});
