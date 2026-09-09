# TestWeaver 測試管理平台

> Web 化的測試管理平台：規格書 → 測試項目自動產生、`Test Plan → Function → Case` 三層管理、缺陷追蹤與自動補件、完成後報表 + AI 分析，並內建 **RAG 智能檢索**。
>
> **目前進度**：已**端到端實作 M1–M6（FR-1 ~ FR-4）+ RAG（FR-6 / M9）**，含前端 React 頁面；完整設計見 [`程式計劃書.md`](./程式計劃書.md)。

## 功能概覽

| 編號 | 功能 | 狀態 |
| --- | --- | --- |
| FR-1 / 1a | 規格書解析 + 測試項目產生（共通類別平台衍生） | ✅ 已實作 + 測試（M1/M7） |
| FR-2 / 2a | 三層測試結構 + 自測對應 | ✅ 已實作 + 測試（M2/M3） |
| FR-3 / 3a | Fail → Defect；無案例 → 測試計畫修改要求 | ✅ 已實作 + 測試（M4/M5） |
| FR-4 | 完成 → 報表 + AI 分析建議（ECharts + 一鍵轉 Revision） | ✅ 已實作 + 測試（M6） |
| FR-5 | Web UI + Python + MySQL | ✅ API 完整 + React UI（M1–M8）；**JWT 登入 + 角色選單 + 稽核日誌 + 帳號管理（M8）** |
| FR-6 | **RAG 查詢**（索引 + 檢索 + 引用溯源） | ✅ 已實作 + 測試 |

## 技術棧

| 層 | 技術 |
| --- | --- |
| 前端 | React + TypeScript + Ant Design + ECharts（📐 規劃中） |
| 後端 | Python 3.11+ · FastAPI |
| ORM / 遷移 | SQLAlchemy 2.x · Alembic |
| 任務佇列 | Celery + Redis |
| 資料庫 | MySQL 8.0（主庫）；本機可用 SQLite 開發 |
| 向量引擎 | Qdrant（預設）/ pgvector，以 `VectorStore` 介面抽象 |
| AI | OpenAI-compatible Embedding + Chat（可換本地模型） |

## 目錄結構

```
test-weaver/
├─ 程式計劃書.md              # 完整設計文件（架構 / DB / 流程 / AI / 部署 / 里程碑）
├─ pyproject.toml
└─ backend/
   ├─ app/
   │  ├─ main.py              # FastAPI 入口（create_app）
   │  ├─ core/db.py           # engine / get_db(FastAPI) / session_scope(Celery)
   │  ├─ models/              # SQLAlchemy 模型（rag.py: knowledge_chunk, rag_query_log）
   │  ├─ ai/
   │  │  ├─ config.py         # RagConfig（chunking / 相似度門檻）
   │  │  ├─ rag.py            # split_text / index_source / rag_query / persist_chunks
   │  │  ├─ embedder.py       # OpenAIEmbedder（/embeddings）
   │  │  ├─ llm.py            # llm_answer（RAG answerer）
   │  │  ├─ provide.py        # env → 單一實例（store / embedder / config）
   │  │  └─ vector_store/     # VectorStore(ABC) + Qdrant / pgvector + factory
   │  ├─ workers/             # celery_app + rag_tasks（rag.index_source / rag.query）
   │  └─ api/v1/rag.py        # /rag/* 路由
   ├─ alembic/ + alembic.ini  # 資料庫遷移
   ├─ tests/                  # RAG 單元 + API 測試（離線可跑）
   └─ requirements.txt
```

## 快速開始

### 0) 前置
- Python 3.11+
- 跑**真實 API** 需要 Redis + Qdrant（預設向量引擎）；可選 MySQL。
- 本機開發可用 SQLite，免裝 MySQL。

### 1) 【最簡】Docker Compose 一把起（推薦，含 MySQL / Redis / Qdrant）
```bash
cp .env.example .env        # 填入 EMBEDDING_API_KEY（必填）/ LLM_API_KEY（可選）
docker compose up --build   # api + worker + qdrant + redis + mysql
```
- API：http://localhost:8000/docs（`api` 啟動時自動執行 `alembic upgrade head`）
- worker：處理 `/rag/index`、`/rag/query/async` 的非同步任務
- **認證（可選）**：`.env` 設 `AUTH_ENABLED=true` 啟用 JWT 登入（預設 `admin/admin123`），再加 `AUDIT_ENABLED=true` 開稽核日誌；預設皆為關閉（免登入）
- 以下 2)~7) 為「不用 Docker、本機直接執行」的替代流程。

### 2) （本機執行）安裝依賴
```bash
pip install -r backend/requirements.txt
```

### 3) 跑測試（零基礎設施，離線綠燈）
```bash
python -m pytest backend/tests -q     # 15 passed
```
> RAG 測試以 in-memory 向量庫 + fake embedding + SQLite 執行，**不需** Qdrant / Celery / LLM key。

### 4) 建立向量庫與佇列（僅真實 API 需要）
```bash
docker run -d -p 6333:6333 -v "$PWD/.data/qdrant":/qdrant qdrant/qdrant   # Qdrant
docker run -d -p 6379:6379 redis:7                                        # Redis
```

### 5) 設定環境變數
```bash
export DATABASE_URL="mysql+pymysql://user:pass@localhost:3306/testweaver"  # 或留空用 SQLite
export VECTOR_STORE=qdrant          # qdrant | pgvector
export EMBEDDING_API_KEY="sk-..."   # embedding（必填，否則索引/檢索會報錯）
export LLM_API_KEY="sk-..."         # LLM 答案（可選；未設則回 fallback 字串）
```

### 6) 資料庫遷移
```bash
cd backend
alembic -c alembic.ini upgrade head   # MySQL / SQLite 皆可
```

### 7) 啟動 Worker + API
```bash
# terminal A：Worker
celery -A app.workers.celery_app.celery_app worker --loglevel=info
# terminal B：API
uvicorn app.main:app --reload --port 8000
```
> 互動式 API 文件：http://localhost:8000/docs

## RAG API 範例

```bash
# 建立索引（非同步 → Celery）
curl -X POST localhost:8000/api/v1/rag/index \
  -H 'Content-Type: application/json' \
  -d '{"source_type":"spec","source_id":1001,"text":"登入功能：輸入帳號密碼驗證並回傳 token。","section_title":"功能規格"}'
# → {"task_id":"...","status":"queued"}

# 同步檢索（快速路徑，無 LLM）
curl -X POST localhost:8000/api/v1/rag/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"登入如何驗證","top_k":3}'

# 非同步檢索 + LLM 答案
curl -X POST localhost:8000/api/v1/rag/query/async \
  -H 'Content-Type: application/json' \
  -d '{"question":"登入如何驗證","answer":true}'

# 查任務狀態 / 結果
curl localhost:8000/api/v1/rag/tasks/<task_id>

# 查詢紀錄（分頁）
curl "localhost:8000/api/v1/rag/query-logs?page=1&page_size=20"
```

端點清單：

| Method | Path | 說明 |
| --- | --- | --- |
| POST | `/rag/index` | 非同步建/更新向量索引，回 `task_id` |
| POST | `/rag/query` | 同步檢索（無 LLM），回 Top-K 引用 + context |
| POST | `/rag/query/async` | 非同步檢索 + LLM 答案，回 `task_id` |
| GET | `/rag/tasks/{task_id}` | 查 Celery 任務狀態 / 結果 |
| GET | `/rag/query-logs` | 查詢紀錄（分頁） |

## 前端（React + Ant Design）

骨幹位於 [`frontend/`](./frontend)，React 18 + TypeScript + Ant Design v5 + **ECharts**，已實作下列頁面：
- **RAG**（/rag）：查詢 / 建立索引 / AI 查詢 / 查詢紀錄
- **測試計畫**（/plan）：FR-1 規格書上傳 + AI 生成測試項目；FR-2 三層結構（計畫/功能/案例）+ 版本管理
- **自測對應**（/self-test）：FR-2a，Function + Case 綁定
- **缺陷追蹤**（/defect）：FR-3 執行 + 自動建缺陷；Tab 內含 FR-3a 修改要求（accept/reject/complete）
- **報表 / AI**（/report）：FR-4，完成→指標（通過率/缺陷分佈，ECharts）+ AI 建議卡片 + 一鍵轉 Revision Request
- **類別平台**（/platform）：M7 類別 CRUD
- **登入**（/login）：FR-5 / M8，JWT 登入；登入後選單依角色過濾、401 自動導回登入
- **設定**（/settings，admin）：FR-5 帳號管理（新增/改角色/停用/重設密碼，最後一個 admin 保護）＋ 稽核日誌

```bash
cd frontend
npm install
npm run dev                # http://localhost:5173
```
- dev server 將 `/api` 代理到 `http://localhost:8000`（見 `vite.config.ts`），免 CORS。
- 先啟動後端 API（`docker compose up` 或本機 `uvicorn app.main:app`）。
- **角色控制選單**（FR-5）：admin 見全部（含 /settings、/platform）；qa_lead 無 /platform、/settings；tester 只有核心四項。

---

## 環境變數

| 變數 | 預設 | 說明 |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./testweaver_dev.db` | 主庫連線（MySQL：`mysql+pymysql://...`） |
| `AUTH_ENABLED` | `false` | 啟用 JWT 認證（false=免登入、角色門檻放過） |
| `JWT_SECRET` | dev 預設 | JWT 簽章密鑰（**生產必填**） |
| `ACCESS_TOKEN_MINUTES` | `60` | access token 效期（分） |
| `REFRESH_TOKEN_DAYS` | `7` | refresh token 效期（天；可登出撤銷 / 旋轉） |
| `AUTH_ADMIN_USERNAME` / `AUTH_ADMIN_PASSWORD` | admin / admin123 | 首次啟動建立的預設 admin（可改） |
| `AUDIT_ENABLED` | `false` | 記錄登入與狀態變更稽核日誌（admin 於 `/audit/logs` 檢視） |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | redis `//:6379/0` , `/1` | Celery broker / 結果 |
| `VECTOR_STORE` | `qdrant` | `qdrant` 或 `pgvector` |
| `QDRANT_URL` / `QDRANT_API_KEY` / `QDRANT_COLLECTION` | http://localhost:6333 / — / testweaver_chunks | Qdrant 設定 |
| `POSTGRES_DSN` | — | pgvector 後端的 PostgreSQL DSN |
| `EMBEDDING_API_KEY` / `EMBEDDING_BASE_URL` / `EMBEDDING_MODEL` / `EMBEDDING_DIM` | — / openai / text-embedding-3-small / 1536 | embedding |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | — / openai / gpt-4o-mini | LLM 答案（可選） |
| `RAG_CHUNK_BY` / `RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP` | recursive / 512 / 64 | 切塊策略與長度（token） |
| `RAG_TOP_K` / `RAG_SIMILARITY_THRESHOLD` / `RAG_MAX_CONTEXT_TOKENS` | 5 / 0.75 / 2048 | 檢索參數 |
| `RAG_REINDEX_ON_CHANGE` | true | 來源更新時先刪舊向量再重寫 |

> 參數含調整建議（chunking / 相似度門檻）見 [`程式計劃書.md`](./程式計劃書.md) §8.1。

## 測試

### 後端（pytest，離線綠燈）

```bash
python -m pytest backend/tests -q
# tests/test_rag.py / test_rag_api.py — RAG 索引/檢索 + API
# tests/test_m1~m6(+api).py          — 規格/項目、三層/版本、自測、缺陷/執行、修改要求、報表+AI
```

### 前端（vitest + Testing Library）

```bash
cd frontend && npm test
# src/api/m1~m6.test.ts         — API 客戶端：URL/method/body + 錯誤路徑（mock fetch）
# src/hooks/useTask.test.ts     — 任務狀態輪詢 hook（success / pending / error）
# src/components/EChart.test.tsx — ECharts 組件生命週期（init / setOption / dispose）
```

## CI / 本機一次跑

兩類 runner，行為一致（typecheck + 後端 pytest + 前端 vitest + build）：

```bash
# 本機（Makefile）
make ci             # 全流程；或 make test / make test-backend / make test-frontend / make typecheck / make build
make install        # 先裝前後端依賴（pip -r backend/requirements.txt + npm ci）
```

GitHub Actions：`.github/workflows/ci.yml` — push / PR 時跑兩個 job（`Backend·pytest` + `Frontend·tsc/vitest/build`），失敗即紅燈。

### 重新產出 UI 截圖（供 `一頁摘要.html`）
```bash
./scripts/capture-shots.sh   # seed 示範資料 + 起後端(:8011)/前端(:5173) + 無頭 Chrome 抓 4 張 → shots/
```
- 前提：後端 `pip install -r backend/requirements.txt`、前端 `cd frontend && npm install`、系統有 Chrome/Chromium。
- 可選 env：`API_PORT`（預設 8011）、`FRONTEND_PORT`（預設 5173）、`CHROME_PATH`。
- 首次會自動裝 `scripts/node_modules/puppeteer-core`（用系統 Chrome，不下載瀏覽器）。

## Roadmap（對應里程碑）

### 已完成（v1，已合併 main）
- ✅ **P1**：RAG 索引 + 檢索 + API/Worker（FR-6 / M9）
- ✅ **P1**：規格書解析 + AI 生成測試項目（FR-1 / 1a，M1/M7）
- ✅ **P2**：三層測試計畫 + 自測（FR-2 / 2a，M2/M3）
- ✅ **P3**：缺陷追蹤 + 自動補件（FR-3 / 3a，M4/M5）
- ✅ **P4**：完成觸發報表 + AI 分析（FR-4，M6）
- ✅ **P5**：Web UI + JWT 登入 + 角色選單 + 稽核日誌 + **帳號/角色管理**（FR-5，M8）
- ✅ **P6**：CI（Makefile + GitHub Actions）+ Docker 部署 + 交付文件（README/程式計劃書/交付說明/一頁摘要+截圖）
- ✅ **v1.1 · 多團隊**：team/member + 資料隔離 + 團隊級 RBAC（owner/platform admin）+ team switcher/成員頁 + 稽核 team_id + team 刪除保護（T1–T3，見 `docs/規劃-多團隊.md`）

### 下一步（規劃中，依優先序）
- **P7 · 治理細化**：完整 RBAC（端點級角色控制）、審批流程；✅ **JWT refresh token + 登出失效（revoke）** 已實作（access 短效 + refresh 可撤銷/旋轉，前端 401 自動刷新）
- **P7 · 稽核增強**：欄位級 before/after diff、稽核保留期與匯出
- **P8 · 產品化/效能**：ECharts code-splitting（`echarts/core`，只註冊 bar/pie）、MySQL 連線池調校、輸入驗證 + 限流
- **P8 · 測試/CI**：✅ 覆蓋率門檻（後端 `pytest-cov` ≥82% / 前端 vitest ratchet）+ CI coverage artifact；剩餘：前端頁面級 RTL 元件測試（拉高前端覆蓋率，現 ~9.4%）
- **P9 · 生產加固**：CORS 白名單、HTTPS、備份策略、密鑰/Secrets 管理
- **可選**：RAG 檢索回饋（點擊/評分）、報表排程與 email/PDF 匯出、跨團隊共用專案
