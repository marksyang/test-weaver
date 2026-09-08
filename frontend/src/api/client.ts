// 共用 fetch 包裝：注入 Bearer token（FR-5 / M8）+ 401 導回登入。
// 各 api 模組（m1~m6 / rag）以此為底層 request，免重複定義。
export const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '/api/v1';

const TOKEN_KEY = 'tw_token';

let _getToken: () => string | null = () => {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
};

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

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {};
  const body = init?.body;
  // FormData 需瀏覽器自帶 boundary，不手動設 Content-Type
  if (typeof body === 'string' || !body) headers['Content-Type'] = 'application/json';
  const token = _getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  Object.assign(headers, (init?.headers as Record<string, string>) ?? {});

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    if (res.status === 401) _onUnauthorized();
    throw new Error(`API ${res.status}: ${await res.text()}`);
  }
  if (res.status === 204) return undefined as T; // 無回應體（如 DELETE）
  const text = await res.text();
  return (text ? (JSON.parse(text) as T) : (undefined as T));
}
