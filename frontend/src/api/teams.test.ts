import { afterEach, describe, expect, it, vi } from 'vitest';
import { teamsApi } from './teams';
import { mockFetch, res } from '../test/fetch';
import { canManageTeam } from '../auth/roles';

afterEach(() => vi.unstubAllGlobals());

describe('teamsApi (多團隊 T2)', () => {
  it('list → GET /teams', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res([{ id: 1, name: 'T', my_role: 'owner' }]));
    const out = await teamsApi.list();
    expect(out[0].id).toBe(1);
    expect((f.mock.calls[0] as [string])[0]).toBe('/api/v1/teams');
  });

  it('addMember → POST /teams/:id/members + JSON body', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ user_id: 5, username: 'u', role: 'tester' }, 201));
    await teamsApi.addMember(3, { user_id: 5, role: 'tester' });
    const [url, init] = f.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/teams/3/members');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(init?.body as string)).toEqual({ user_id: 5, role: 'tester' });
  });

  it('setMemberRole → PATCH /teams/:id/members/:uid', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res({ user_id: 5, username: 'u', role: 'owner' }));
    await teamsApi.setMemberRole(3, 5, 'owner');
    const [url, init] = f.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/teams/3/members/5');
    expect(init?.method).toBe('PATCH');
    expect(JSON.parse(init?.body as string)).toEqual({ role: 'owner' });
  });

  it('removeMember → DELETE /teams/:id/members/:uid（204 → undefined）', async () => {
    const f = mockFetch();
    f.mockResolvedValueOnce(res(null, 204));
    const out = await teamsApi.removeMember(3, 5);
    expect(out).toBeUndefined();
    const [url, init] = f.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/teams/3/members/5');
    expect(init?.method).toBe('DELETE');
  });
});

describe('canManageTeam (前端授權)', () => {
  it('admin 無論 my_role 皆可管理', () => {
    expect(canManageTeam('admin', null)).toBe(true);
    expect(canManageTeam('admin', 'tester')).toBe(true);
  });
  it('該團隊 owner 可管理', () => {
    expect(canManageTeam('tester', 'owner')).toBe(true);
  });
  it('非 owner 且非 admin 不可管理', () => {
    expect(canManageTeam('tester', 'tester')).toBe(false);
    expect(canManageTeam('qa_lead', null)).toBe(false);
  });
});
