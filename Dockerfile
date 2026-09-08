# TestWeaver 後端映像（api 與 worker 共用，以不同 command 啟動）
# build context = 倉庫根目錄；程式碼位於 backend/
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# 先裝依賴（利用分層快取，程式碼更動不重裝）
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 複製 app / migrations（alembic.ini、alembic/）
COPY backend/ ./

# 非 root 執行
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# 預設啟動 API；worker 端由 docker-compose 的 command 覆蓋
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
