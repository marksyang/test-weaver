import { describe, expect, it } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import RagPage from './RagPage';
import { renderPage, mockApi } from '../test/rtl';

describe('RagPage', () => {
  it('renders the RAG tabs and the default synchronous-query form', () => {
    mockApi({ '/query-logs': [], '/teams': [] });
    renderPage(<RagPage />);

    // 四個 tab 標籤（非 active 的 tab 內容不渲染，故唯一）
    expect(screen.getByText('建立索引')).toBeInTheDocument();
    expect(screen.getByText('AI 查詢')).toBeInTheDocument();
    expect(screen.getByText('查詢紀錄')).toBeInTheDocument();

    // 預設 active = 同步查詢
    expect(screen.getByText('同步檢索（快速路徑，無 LLM）')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('例：登入如何驗證')).toBeInTheDocument();
  });

  it('activates the 查詢紀錄 tab and loads the query logs', async () => {
    mockApi({
      '/query-logs': [
        { id: 1, question: '如何驗證登入', top_k: 5, answer: '使用 JWT 簽名', created_at: '2026-01-01T00:00:00Z' },
      ],
      '/teams': [],
    });
    renderPage(<RagPage />);

    // 切換到「查詢紀錄」tab → LogsTab 載入 /rag/query-logs
    fireEvent.click(screen.getByText('查詢紀錄'));
    expect(await screen.findByText('如何驗證登入')).toBeInTheDocument();
  });
});
