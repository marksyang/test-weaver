PYTHON ?= python3

.PHONY: help install test test-backend test-frontend typecheck build ci

help:
	@echo "本機一次跑（目標）："
	@echo "  make install        - 安裝前後端依賴"
	@echo "  make test           - 全部測試（後端 pytest + 前端 vitest）"
	@echo "  make test-backend   - 後端 pytest"
	@echo "  make test-frontend  - 前端 vitest"
	@echo "  make typecheck      - 前端 tsc --noEmit"
	@echo "  make build          - 前端 vite build"
	@echo "  make ci             - CI 全流程（typecheck + 測試 + build）"

install:
	$(PYTHON) -m pip install -r backend/requirements.txt
	cd frontend && npm ci

test: test-backend test-frontend

test-backend:
	$(PYTHON) -m pytest backend/tests -q --cov=app --cov-report=term-missing --cov-report=xml --cov-fail-under=82

test-frontend:
	cd frontend && npx vitest run --coverage

typecheck:
	cd frontend && npx tsc --noEmit

build:
	cd frontend && npm run build

ci: typecheck test-backend test-frontend build
	@echo "✅ CI 全綠（typecheck + 後端 pytest/cov≥82% + 前端 vitest/cov + build）"
