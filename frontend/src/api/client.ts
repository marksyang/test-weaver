// 共用 fetch 包裝：注入 Bearer token（FR-5 / M8）+ 401 自動 refresh + retry。
// 各 api 模組（m1~m6 / rag）以此為底層 request，免重複定義。
export const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '/api/v1';

const TOKEN_KEY = 'tw_token';
const REFRESH_KEY = 'tw_refresh';

function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

let _getToken: () => string | null = () => readStorage(TOKEN_KEY);

let _onUnauthorized: () => void = () => {
  if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
    window.location.href = '/login';
  }
};

/** 可覆寫 token 讀取 / 401 行為（測試或 SPA 導航）。 */
export function configureAuth(opts: {
  getToken?: () => string | null;
  onUnauthorized?: () => void;
}) {
  if (opts.getToken) _getToken = opts.getToken;
  if (opts.onUnauthorized) _onUnauthorized = opts.onUnauthorized;
}

// 併流：並發的 401 只觸發一次 refresh
let _refreshPromise: Promise<boolean> | null = null;

async function doRefresh(): Promise<boolean> {
  const refreshToken = readStorage(REFRESH_KEY);
  if (!refreshToken) return false;
  try {
    const r = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!r.ok) return false;
    const data = await r.json();
    if (!data || typeof data.access_token !== 'string') return false;
    try {
      localStorage.setItem(TOKEN_KEY, data.access_token);
      if (typeof data.refresh_token === 'string') {
        localStorage.setItem(REFRESH_KEY, data.refresh_token);
      }
    } catch {
      /* ignore storage errors */
    }
    return true;
  } catch {
    return false;
  }
}

function tryRefresh(): Promise<boolean> {
  if (!_refreshPromise) {
    _refreshPromise = doRefresh().finally(() => {
      _refreshPromise = null;
    });
  }
  return _refreshPromise;
}

export async function apiFetch<T>(path: string, init?: RequestInit, _retried = false): Promise<T> {
  const headers: Record<string, string> = {};
  const body = init?.body;
  // FormData 需瀏覽器自帶 boundary，不手動設 Content-Type
  if (typeof body === 'string' || !body) headers['Content-Type'] = 'application/json';
  const token = _getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  Object.assign(headers, (init?.headers as Record<string, string>) ?? {});

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    if (res.status === 401 && !_retried) {
      // 非認證端點且尚未重試 → 嘗試用 refresh token 換新 access，再重試一次
      const isAuthEndpoint = path.startsWith('/auth/login') || path.startsWith('/auth/refresh');
      if (!isAuthEndpoint) {
        const refreshed = await tryRefresh();
        if (refreshed) return apiFetch<T>(path, init, true);
      }
    }
    if (res.status === 401) _onUnauthorized();
    throw new Error(`API ${res.status}: ${await res.text()}`);
  }
  if (res.status === 204) return undefined as T; // 無回應體（如 DELETE）
  const text = await res.text();
  return (text ? (JSON.parse(text) as T) : (undefined as T));
}
