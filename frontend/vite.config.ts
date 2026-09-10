/// <reference types="vitest" />
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // 預設代理到 :8000；可用 API_PROXY_TARGET 覆蓋（如 http://127.0.0.1:8011）
      '/api': { target: process.env.API_PROXY_TARGET || 'http://localhost:8000', changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      reportsDirectory: './coverage',
      exclude: [
        '**/node_modules/**',
        '**/dist/**',
        '**/coverage/**',
        '**/*.d.ts',
        '**/*.test.*',
        'src/test/**',
        'src/types/**',
      ],
      // 防回歸的 ratchet floor（含頁面級 RTL 測試，現 ~62%；留緩衝避免跨環境微變）
      thresholds: { statements: 55, lines: 55 },
    },
  },
});
