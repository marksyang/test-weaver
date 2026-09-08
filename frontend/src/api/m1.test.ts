import { afterEach, describe, expect, it, vi } from 'vitest';
import { m1Api } from './m1';
import { mockFetch, res } from '../test/fetch';

afterEach(() => vi.unstubAllGlobals());

describe('m1Api', () => {
  it('listProjects → GET /projects', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res([{ id: 1, name: 'P' }]));
    const out = await m1Api.listProjects();
    expect(out).toEqual([{ id: 1, name: 'P' }]);
    const [url] = f.mock.calls[0] as [string];
    expect(url).toBe('/api/v1/projects');
  });

  it('createProject → POST + JSON body', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ id: 2, name: 'X' }, 201));
    const out = await m1Api.createProject({ name: 'X' });
    expect(out.id).toBe(2);
    const [url, init] = f.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/projects');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(init?.body as string)).toEqual({ name: 'X' });
  });

  it('taskStatus URL-encodes the id', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ state: 'SUCCESS' }));
    await m1Api.taskStatus('a/b');
    const [url] = f.mock.calls[0] as [string];
    expect(url).toBe('/api/v1/tasks/a%2Fb');
  });

  it('uploadSpec appends FormData without forced Content-Type', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ id: 7 }, 201));
    const file = new Blob(['x'], { type: 'text/plain' }) as unknown as File;
    await m1Api.uploadSpec(3, file);
    const [url, init] = f.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/projects/3/spec-files');
    expect(init?.body).toBeInstanceOf(FormData);
    expect((init?.headers as Record<string, string> | undefined)?.['Content-Type']).toBeUndefined();
  });

  it('throws with status on non-2xx', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ detail: 'nope' }, 422));
    await expect(m1Api.listProjects()).rejects.toThrow(/422/);
  });
});
