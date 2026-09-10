// 頁面級 RTL 測試共用 helper：
//  - renderPage：以 App + MemoryRouter + AuthProvider + TeamProvider 包裹（多數頁面需要）
//  - mockApi：按 URL 子字串路由 mock fetch（免管呼叫順序；未匹配回空 list）
import type { ReactElement } from 'react';
import { render } from '@testing-library/react';
import type { RenderResult } from '@testing-library/react';
import { App } from 'antd';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
import { AuthProvider } from '../auth/AuthContext';
import { TeamProvider } from '../team/TeamContext';
import { res } from './fetch';

/** 以完整 provider 樹包裹並 render（多數頁面需要 App/Router/Auth/Team）。 */
export function renderPage(ui: ReactElement): RenderResult {
  return render(
    <App>
      <MemoryRouter>
        <AuthProvider>
          <TeamProvider>{ui}</TeamProvider>
        </AuthProvider>
      </MemoryRouter>
    </App>,
  );
}

/**
 * Stub fetch，依 URL 子字串回對應資料。
 * @param routes 例：{ '/defects': [...], '/teams': [...] }；未匹配的呼叫回 `res([])`。
 */
export function mockApi(routes: Record<string, unknown> = {}) {
  const fn = vi.fn();
  fn.mockImplementation((url: string | URL | Request) => {
    const u = String(url);
    for (const [key, val] of Object.entries(routes)) {
      if (u.includes(key)) return Promise.resolve(res(val));
    }
    return Promise.resolve(res([]));
  });
  vi.stubGlobal('fetch', fn);
  return fn;
}
