import { vi } from 'vitest';

/** 構造一個最小 Response（只含 api/*.ts 用到的 ok / status / json / text）。 */
export function res(body: unknown, status = 200) {
  const ok = status >= 200 && status < 300;
  return {
    ok,
    status,
    json: async () => body,
    text: async () => (typeof body === 'string' ? body : JSON.stringify(body)),
  } as unknown as Response;
}

/** 替換全域 fetch，回傳 spy（可 `.mockResolvedValueOnce(...)`）。 */
export function mockFetch() {
  const fn = vi.fn();
  vi.stubGlobal('fetch', fn);
  return fn;
}
