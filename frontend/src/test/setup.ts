// Vitest 全域設定：注入 jest-dom matchers（toBeInTheDocument 等）+ antd 所需 API shim
import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

// 每個測試後清理 DOM（避免同檔多 render 累積 → “found multiple”）
afterEach(() => cleanup());

// jsdom 沒有 window.matchMedia（antd Row/Col 響應式、Grid 會用到）→ 補最小 shim
if (typeof window !== 'undefined' && !window.matchMedia) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}
