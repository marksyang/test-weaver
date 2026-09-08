#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# 可重複執行：seed 示範資料 → 起後端(:8011) + 前端 Vite(:5173) → 無頭 Chrome 截圖 → 清理。
# 產物：shots/{login,plan,defect,report}.png（供 一頁摘要.html 的「產品畫面」）。
#
# 前提：
#   • 後端依賴已裝：  pip install -r backend/requirements.txt
#   • 前端依賴已裝：  cd frontend && npm install
#   • 系統有 Chrome/Chromium（macOS 預設用 Google Chrome；否則以 CHROME_PATH 指定）
#
# 可選 env：API_PORT(預設 8011) FRONTEND_PORT(預設 5173) CHROME_PATH
# ─────────────────────────────────────────────────────────────────────────────
set +e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_PORT="${API_PORT:-8011}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
OUT="$ROOT/shots"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

# 挑 Chrome/Chromium
if [ -z "${CHROME_PATH:-}" ]; then
  if [ -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]; then
    CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
  else
    CHROME_PATH="$(command -v google-chrome || command -v chromium || command -v chromium-browser || true)"
  fi
fi
[ -n "$CHROME_PATH" ] && [ -x "$CHROME_PATH" ] || {
  echo "找不到 Chrome/Chromium。請用 CHROME_PATH=/path/to/chrome $0 指定。"; exit 1;
}

# 前提檢查
command -v python3 >/dev/null || { echo "缺 python3"; exit 1; }
[ -d "$FRONTEND/node_modules" ] || { echo "frontend 未安裝依賴：先 cd frontend && npm install"; exit 1; }

TMP="$(mktemp -d)"
DB="sqlite:///$TMP/shot.db"   # 4 斜線 = 絕對路徑的 SQLite
API_PID="" VITE_PID=""

cleanup() {
  [ -n "$API_PID" ]  && kill "$API_PID"  2>/dev/null
  [ -n "$VITE_PID" ] && kill "$VITE_PID" 2>/dev/null
  pkill -f "uvicorn app.main:app.*--port $API_PORT"      2>/dev/null
  pkill -f "vite.*--port $FRONTEND_PORT"                 2>/dev/null
  rm -rf "$TMP"
}
trap cleanup EXIT

echo "==> root=$ROOT"; echo "==> api=:$API_PORT  frontend=:$FRONTEND_PORT  out=$OUT"
echo "==> chrome=$CHROME_PATH"

# 清掉可能佔用 port 的舊殘留
pkill -f "uvicorn app.main:app" 2>/dev/null
pkill -f "vite.*--port $FRONTEND_PORT" 2>/dev/null
mkdir -p "$OUT"

# 1) seed（temp DB）
echo "==> [1/4] seed demo data"
PYTHONPATH="$BACKEND" DATABASE_URL="$DB" AUTH_ENABLED=true \
  python3 "$ROOT/scripts/seed_demo.py"
if [ $? -ne 0 ]; then echo "SEED_FAILED"; exit 1; fi

# 2) API
echo "==> [2/4] start API :$API_PORT"
(
  cd "$BACKEND" || exit 1
  DATABASE_URL="$DB" AUTH_ENABLED=true AUDIT_ENABLED=false \
    JWT_SECRET=shots-secret UPLOAD_DIR="$TMP/uploads" \
    nohup python3 -m uvicorn app.main:app --host 127.0.0.1 --port "$API_PORT" >"$TMP/api.log" 2>&1 &
  echo $! > "$TMP/api.pid"
)
API_PID="$(cat "$TMP/api.pid")"
ready=""
for i in $(seq 1 60); do
  code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$API_PORT/openapi.json)"
  [ "$code" = "200" ] && { ready=1; echo "    API ready (${i}s)"; break; }
  sleep 1
done
[ -n "$ready" ] || { echo "API_NOT_READY"; tail -30 "$TMP/api.log"; exit 1; }

# 3) 前端 Vite（proxy -> API port）
echo "==> [3/4] start Vite :$FRONTEND_PORT (proxy -> :$API_PORT)"
(
  cd "$FRONTEND" || exit 1
  API_PROXY_TARGET="http://127.0.0.1:$API_PORT" \
    nohup npx vite --strictPort --port "$FRONTEND_PORT" >"$TMP/vite.log" 2>&1 &
  echo $! > "$TMP/vite.pid"
)
VITE_PID="$(cat "$TMP/vite.pid")"
ready=""
for i in $(seq 1 90); do
  code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$FRONTEND_PORT/)"
  [ "$code" = "200" ] && { ready=1; echo "    VITE ready (${i}s)"; break; }
  sleep 1
done
[ -n "$ready" ] || { echo "VITE_NOT_READY"; tail -30 "$TMP/vite.log"; exit 1; }

# 4) 截圖（puppeteer-core）
echo "==> [4/4] capture"
(
  cd "$ROOT/scripts" || exit 1
  [ -d node_modules/puppeteer-core ] || npm install --no-save puppeteer-core >/dev/null 2>&1
  BASE="http://localhost:$FRONTEND_PORT" OUT="$OUT" CHROME_PATH="$CHROME_PATH" \
    node "$ROOT/scripts/capture_shots.js"
)
CAP=$?

echo "==> 完成。產物："
ls -la "$OUT"
if [ $CAP -eq 0 ]; then echo "✅ OK"; else echo "❌ FAILED（見上方）"; fi
exit $CAP
