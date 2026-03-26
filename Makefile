SHELL := /bin/bash
.DEFAULT_GOAL := help

# 人类日常只需要关注 3 个完整栈命令：up-build / up / down。
# 其余目标仍然保留，因为 CI、执行计划、专项验收脚本和本地开发都在使用。
.PHONY: help codegen validate validate-static validate-contracts check-no-legacy-searchrun check-no-legacy-agent-config check-no-embeddeddb test test-stack test-stack-run eval-critical eval-critical-run verify-images install-single-branch-guard dev-api dev-worker dev-web dev-web-user dev-web-ops dev-web-evals clean-exports up up-build rebuild-backend rebuild-temporal-stack temporal-visibility-smoke temporal-visibility-smoke-run down status urls

help:
	@printf '\n'
	@printf '人类常用完整栈命令：\n'
	@printf '  make up-build   强制重建并启动完整栈；改了依赖、Dockerfile、后端镜像后优先用这个。\n'
	@printf '  make up         直接启动完整栈；复用已有镜像，适合日常开工。\n'
	@printf '  make down       关闭并清理完整栈。\n'
	@printf '\n'
	@printf '其它本地辅助命令：\n'
	@printf '  make status     查看当前容器状态，并打印访问地址。\n'
	@printf '  make urls       仅打印本地访问地址。\n'
	@printf '\n'
	@printf '内部 / CI / 专项目标：\n'
	@printf '  make validate | test | test-stack | eval-critical | temporal-visibility-smoke | verify-images\n'
	@printf '  make dev-api | dev-worker | dev-web-user | dev-web-ops | dev-web-evals\n'
	@printf '\n'

# 只打印本地访问地址，便于确认当前端口与入口
urls:
	@./tools/bootstrap/print-endpoints.sh

# 人类常用：强制重建并启动完整本地栈
# 适用于 Dockerfile、依赖、镜像层或后端构建产物发生变化后的刷新启动
up-build:
	@BUILD_ID=$$(date -u +%Y%m%d%H%M%S); \
	echo "Using CVM_BUILD_ID=$$BUILD_ID"; \
	CVM_BUILD_ID=$$BUILD_ID docker compose up -d --build --remove-orphans
	@$(MAKE) --no-print-directory urls

# 人类常用：直接启动完整本地栈
# 默认复用已有镜像，适合日常启动或继续上次的本地环境
up:
	docker compose up -d --remove-orphans
	@$(MAKE) --no-print-directory urls

# 人类常用：关闭并清理完整本地栈
# 停掉 compose 服务并移除当前项目创建的孤儿容器
down:
	docker compose down --remove-orphans

# 查看 compose 服务状态，并补充打印当前访问地址
status:
	docker compose ps
	@$(MAKE) --no-print-directory urls

# 根据 contract 重新生成 generated 代码
codegen:
	uv run python tools/codegen/generate_all.py

# 本地硬门入口：静态、契约、确定性测试
validate: validate-static validate-contracts test

# 静态门：类型、lint、架构、逃逸口、前端编译
validate-static:
	uv run python tools/ci/check_forbidden_runtime_artifacts.py
	$(MAKE) --no-print-directory check-no-legacy-searchrun
	$(MAKE) --no-print-directory check-no-legacy-agent-config
	$(MAKE) --no-print-directory check-no-embeddeddb
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

check-no-legacy-agent-config:
	@if rg -n "CVM_LLM_|llm_mode|llm_provider|llm_model|llm_timeout_seconds|llm_base_url" \
		apps services tests libs tools README.md docker-compose.yml .env.example .github docs/00-INDEX.md docs/ARCHITECTURE/context-map.md docs/PRODUCT/requirement-traceability.md docs/EXEC-PLANS/active; then \
		echo "Legacy CVM_LLM_* runtime config references are not allowed."; \
		exit 1; \
	fi

check-no-embeddeddb:
	@pattern="$$(printf '%s|%s|%s|%s|%s' 'sqli''te' 'py''sqli''te' 'aio''sqli''te' 'sqli''te3' 'Static''Pool')"; \
	if rg -n -i "$$pattern" \
		apps services tests libs tools README.md docker-compose.yml .env.example docs .github; then \
		echo "Embedded-database references are forbidden. This repository is PostgreSQL-only."; \
		exit 1; \
	fi

# 契约门：schema、codegen、generated/docs clean
validate-contracts:
	uv run python tools/ci/check_links.py
	uv run python tools/ci/check_contracts.py
	$(MAKE) codegen
	uv run python tools/ci/check_generated_clean.py

# 确定性测试：自动拉起隔离 PostgreSQL，并显式覆盖为 deterministic agent profile
test:
	CVM_AGENT_PROFILE=deterministic CVM_RESUME_SOURCE_MODE=mock ./tools/ci/with_test_postgres.sh uv run pytest -m 'not stack' --cov --cov-report=term-missing

# 栈集成测试：默认自带 deterministic mock/profile stack；CI 可通过 CVM_EXTERNAL_STACK=1 复用外部已启动栈
test-stack:
	@if [[ "$${CVM_EXTERNAL_STACK:-0}" == "1" ]]; then \
		$(MAKE) --no-print-directory test-stack-run; \
	else \
		./tools/ci/with_deterministic_stack.sh $(MAKE) --no-print-directory test-stack-run; \
	fi

test-stack-run:
	uv run python tools/ci/check_local_stack_ready.py
	uv run pytest -m stack

# 最小 blocking eval 套件：默认自带 deterministic mock/profile stack；CI 可通过 CVM_EXTERNAL_STACK=1 复用外部已启动栈
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

# 做一次本地 Temporal execution/visibility/UI 专项验收：默认自带 deterministic mock/profile stack；CI 可通过 CVM_EXTERNAL_STACK=1 复用外部已启动栈
temporal-visibility-smoke:
	@if [[ "$${CVM_EXTERNAL_STACK:-0}" == "1" ]]; then \
		$(MAKE) --no-print-directory temporal-visibility-smoke-run; \
	else \
		./tools/ci/with_deterministic_stack.sh $(MAKE) --no-print-directory temporal-visibility-smoke-run; \
	fi

temporal-visibility-smoke-run:
	uv run python tools/ci/check_local_stack_ready.py
	uv run python tools/smoke/temporal_visibility_smoke.py
