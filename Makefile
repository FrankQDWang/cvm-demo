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
.PHONY: codegen validate validate-static validate-contracts check-no-legacy-searchrun test test-stack test-stack-run eval-critical eval-critical-run verify-images install-single-branch-guard dev-api dev-worker dev-web dev-web-user dev-web-ops dev-web-evals clean-exports up up-build rebuild-backend rebuild-temporal-stack temporal-visibility-smoke temporal-visibility-smoke-run down status urls

# 根据 contract 重新生成 generated 代码
codegen:
	uv run python tools/codegen/generate_all.py

# 本地硬门入口：静态、契约、确定性测试
validate: validate-static validate-contracts test

# 静态门：类型、lint、架构、逃逸口、前端编译
validate-static:
	uv run python tools/ci/check_forbidden_runtime_artifacts.py
	$(MAKE) --no-print-directory check-no-legacy-searchrun
	uv run ruff check
	uv run python tools/ci/run_basedpyright.py
	uv run python tools/ci/check_architecture.py
	uv run tach check --dependencies
	uv run tach check-external
	uv run semgrep --config semgrep.yml --error
	mise exec -- pnpm run lint:ts
	mise exec -- pnpm run check:deps:ts
	mise exec -- pnpm run check:unused:ts
	mise exec -- pnpm --dir apps/web-user run build
	mise exec -- pnpm --dir apps/web-ops run build

# 避免 SearchRun 旧主链回流到现行代码、测试和 active 文档；历史 completed 文档不在检查范围
check-no-legacy-searchrun:
	@if rg -n "search-runs|SearchRun|createSearchRun|getSearchRun|getSearchRunPages|getSearchRunTemporalDiagnostic|wait_for_search_run|wait_for_temporal_diagnostic|cvm-search-runs|search-run-" \
		apps services tests libs tools README.md docker-compose.yml .env.example docs/00-INDEX.md docs/ARCHITECTURE/context-map.md docs/PRODUCT/requirement-traceability.md docs/EXEC-PLANS/active; then \
		echo "Legacy SearchRun references are not allowed in active code, tests, or active docs."; \
		exit 1; \
	fi

# 契约门：schema、codegen、generated/docs clean
validate-contracts:
	uv run python tools/ci/check_links.py
	uv run python tools/ci/check_contracts.py
	$(MAKE) codegen
	uv run python tools/ci/check_generated_clean.py

# 确定性测试：不依赖本地 compose 栈
test:
	uv run pytest -m 'not stack' --cov --cov-report=term-missing

# 栈集成测试：默认自带 deterministic mock/stub stack；CI 可通过 CVM_EXTERNAL_STACK=1 复用外部已启动栈
test-stack:
	@if [[ "$${CVM_EXTERNAL_STACK:-0}" == "1" ]]; then \
		$(MAKE) --no-print-directory test-stack-run; \
	else \
		./tools/ci/with_deterministic_stack.sh $(MAKE) --no-print-directory test-stack-run; \
	fi

test-stack-run:
	uv run python tools/ci/check_local_stack_ready.py
	uv run pytest -m stack

# 最小 blocking eval 套件：默认自带 deterministic mock/stub stack；CI 可通过 CVM_EXTERNAL_STACK=1 复用外部已启动栈
eval-critical:
	@if [[ "$${CVM_EXTERNAL_STACK:-0}" == "1" ]]; then \
		$(MAKE) --no-print-directory eval-critical-run; \
	else \
		./tools/ci/with_deterministic_stack.sh $(MAKE) --no-print-directory eval-critical-run; \
	fi

eval-critical-run:
	uv run python tools/ci/check_local_stack_ready.py
	uv run python -m cvm_eval_runner.cli --suite blocking

# 运行时 Docker 制品验证：构建本仓库镜像并拉取自托管 Langfuse 运行镜像
verify-images:
	docker compose build api worker web-user web-ops
	docker compose pull web-evals langfuse-worker langfuse-postgres langfuse-clickhouse langfuse-minio langfuse-redis

# 启用仓库级单分支模式：只允许 main，本地 hook 会拒绝创建/提交/推送其他分支
install-single-branch-guard:
	git config --local core.hooksPath .githooks
	@echo "Single-branch guard enabled with core.hooksPath=.githooks"

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
	docker compose up -d web-evals; \
	echo "Langfuse UI: http://127.0.0.1:$${CVM_EVALS_WEB_PORT:-4202}"; \
	echo "Langfuse Login: $${CVM_LANGFUSE_INIT_USER_EMAIL:-admin@local.test} / $${CVM_LANGFUSE_INIT_USER_PASSWORD:-local-admin-pass}"

# 清理本地导出目录中过期文件
clean-exports:
	uv run python tools/bootstrap/cleanup_exports.py

# 打印本地访问地址，便于直接复制
urls:
	@./tools/bootstrap/print-endpoints.sh

# 一键启动完整本地栈：postgres + temporal + api + worker + web-user + web-ops + self-hosted langfuse
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

# 做一次本地 Temporal execution/visibility/UI 专项验收：默认自带 deterministic mock/stub stack；CI 可通过 CVM_EXTERNAL_STACK=1 复用外部已启动栈
temporal-visibility-smoke:
	@if [[ "$${CVM_EXTERNAL_STACK:-0}" == "1" ]]; then \
		$(MAKE) --no-print-directory temporal-visibility-smoke-run; \
	else \
		./tools/ci/with_deterministic_stack.sh $(MAKE) --no-print-directory temporal-visibility-smoke-run; \
	fi

temporal-visibility-smoke-run:
	uv run python tools/ci/check_local_stack_ready.py
	uv run python tools/smoke/temporal_visibility_smoke.py

# 停止完整本地栈
down:
	docker compose down --remove-orphans

# 查看 compose 服务状态
status:
	docker compose ps
	@$(MAKE) --no-print-directory urls
