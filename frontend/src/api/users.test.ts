import { afterEach, describe, expect, it, vi } from 'vitest';
import { usersApi } from './users';
import { configureAuth } from './client';
import { mockFetch, res } from '../test/fetch';

afterEach(() => {
  vi.unstubAllGlobals();
  configureAuth({ getToken: () => null, onUnauthorized: () => {} });
});

describe('usersApi', () => {
  it('list GETs /users', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res([{ id: 1, username: 'admin', role: 'admin', is_active: true }]));
    const rows = await usersApi.list();
    expect(rows[0].username).toBe('admin');
    expect((f.mock.calls[0] as [string])[0]).toBe('/api/v1/users');
  });

  it('create POSTs to /users', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ id: 9, username: 'u', role: 'tester', is_active: true }, 201));
    const u = await usersApi.create({ username: 'u', password: 'pass1234', role: 'tester' });
    expect(u.id).toBe(9);
    const [url, init] = f.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/users');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(init!.body as string)).toEqual({ username: 'u', password: 'pass1234', role: 'tester' });
  });

  it('update PATCHes /users/{id}', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ id: 9, username: 'u', role: 'qa_lead', is_active: true }));
    await usersApi.update(9, { role: 'qa_lead' });
    const [url, init] = f.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/users/9');
    expect(init?.method).toBe('PATCH');
    expect(JSON.parse(init!.body as string)).toEqual({ role: 'qa_lead' });
  });
});
