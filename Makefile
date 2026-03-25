SHELL := /bin/zsh

# 常用目标说明：
# - make up: 一键启动本地完整栈（默认不强制 build）
# - make up-build: 依赖或 Dockerfile 变更后强制重建，并刷新本地 build id
# - make rebuild-backend: 只重建 api + worker，适合代码或依赖变更后验证
# - make rebuild-temporal-stack: 重建 temporal + ui + opensearch + admin-tools
# - make temporal-visibility-smoke: 做一次可见性专项验收
# - make down: 停止并清理当前 compose 资源
# - make status: 查看容器状态
# - make dev-api / dev-worker / dev-web-*: 宿主机开发模式启动
.PHONY: codegen validate test test-stack eval-critical dev-api dev-worker dev-web dev-web-user dev-web-ops dev-web-evals clean-exports up up-build rebuild-backend rebuild-temporal-stack temporal-visibility-smoke down status urls

# 根据 contract 重新生成 generated 代码
codegen:
	uv run python tools/codegen/generate_all.py

# 本地机械校验：文档、contract、generated、架构规则、前端构建
validate:
	uv run python tools/ci/check_links.py
	uv run python tools/ci/check_forbidden_runtime_artifacts.py
	uv run python tools/ci/check_contracts.py
	$(MAKE) codegen
	uv run python tools/ci/check_generated_clean.py
	uv run python tools/ci/check_architecture.py
	uv run tach check --dependencies
	uv run tach check-external
	mise exec -- pnpm run check:deps:ts
	mise exec -- pnpm run check:unused:ts
	mise exec -- pnpm --dir apps/web-user run build
	mise exec -- pnpm --dir apps/web-ops run build
	mise exec -- pnpm --dir apps/web-evals run build

# 后端测试
test:
	uv run pytest -m 'not stack' --cov --cov-report=term-missing

# 栈集成测试：显式依赖 compose 栈
test-stack:
	@set -a; source .env 2>/dev/null || true; set +a; \
	uv run python tools/ci/check_local_stack_ready.py; \
	uv run pytest -m stack

# 最小 blocking eval 套件
eval-critical:
	@set -a; source .env 2>/dev/null || true; set +a; \
	uv run python tools/ci/check_local_stack_ready.py; \
	uv run python -m cvm_eval_runner.cli --suite blocking

# 宿主机启动 API，读取 .env 端口配置
dev-api:
	@set -a; source .env 2>/dev/null || true; set +a; \
	uv run uvicorn cvm_platform.main:app --factory --app-dir services/platform-api/src --reload --port $${CVM_API_PORT:-8010}

# 宿主机启动 Temporal worker
dev-worker:
	uv run python -m cvm_worker.main

# 宿主机启动用户站开发服务器，并写入 runtime config
dev-web: dev-web-user

dev-web-user:
	@set -a; source .env 2>/dev/null || true; set +a; \
	./tools/bootstrap/write-runtime-config.sh apps/web-user; \
	mise exec -- pnpm --dir apps/web-user exec ng serve --host 0.0.0.0 --port $${CVM_USER_WEB_PORT:-4200} --proxy-config proxy.conf.json

dev-web-ops:
	@set -a; source .env 2>/dev/null || true; set +a; \
	./tools/bootstrap/write-runtime-config.sh apps/web-ops; \
	mise exec -- pnpm --dir apps/web-ops exec ng serve --host 0.0.0.0 --port $${CVM_OPS_WEB_PORT:-4201} --proxy-config proxy.conf.json

dev-web-evals:
	@set -a; source .env 2>/dev/null || true; set +a; \
	./tools/bootstrap/write-runtime-config.sh apps/web-evals; \
	mise exec -- pnpm --dir apps/web-evals exec ng serve --host 0.0.0.0 --port $${CVM_EVALS_WEB_PORT:-4202} --proxy-config proxy.conf.json

# 清理本地导出目录中过期文件
clean-exports:
	uv run python tools/bootstrap/cleanup_exports.py

# 打印本地访问地址，便于直接复制
urls:
	@./tools/bootstrap/print-endpoints.sh

# 一键启动完整本地栈：postgres + temporal + api + worker + web-user + web-ops + web-evals
# 默认复用已有镜像，避免每次都重新 build
up:
	docker compose up -d --remove-orphans
	@$(MAKE) --no-print-directory urls

# 依赖、Dockerfile 或构建产物有变化时，手动强制重建
up-build:
	@BUILD_ID=$$(date -u +%Y%m%d%H%M%S); \
	echo "Using CVM_BUILD_ID=$$BUILD_ID"; \
	CVM_BUILD_ID=$$BUILD_ID docker compose up -d --build --remove-orphans
	@$(MAKE) --no-print-directory urls

# 显式重建后端服务，避免旧镜像导致 Temporal 观察失真
rebuild-backend:
	@BUILD_ID=$$(date -u +%Y%m%d%H%M%S); \
	echo "Using CVM_BUILD_ID=$$BUILD_ID"; \
	CVM_BUILD_ID=$$BUILD_ID docker compose up -d --build --remove-orphans api worker
	@$(MAKE) --no-print-directory urls

# 显式重建 Temporal 基础设施，便于验证 visibility 索引链路
rebuild-temporal-stack:
	docker compose up -d --force-recreate --remove-orphans opensearch temporal temporal-ui temporal-admin-tools
	@$(MAKE) --no-print-directory urls

# 做一次本地 Temporal execution/visibility/UI 专项验收
temporal-visibility-smoke:
	@set -a; source .env 2>/dev/null || true; set +a; \
	uv run python tools/ci/check_local_stack_ready.py; \
	uv run python tools/smoke/temporal_visibility_smoke.py

# 停止完整本地栈
down:
	docker compose down --remove-orphans

# 查看 compose 服务状态
status:
	docker compose ps
	@$(MAKE) --no-print-directory urls
