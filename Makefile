SHELL := /bin/zsh

.PHONY: codegen validate test eval-critical dev-api dev-worker dev-web clean-exports

codegen:
	uv run python tools/codegen/generate_all.py

validate:
	uv run python tools/ci/check_links.py
	uv run python tools/ci/check_contracts.py
	$(MAKE) codegen
	uv run python tools/ci/check_generated_clean.py
	uv run python tools/ci/check_architecture.py
	pnpm --dir apps/web-console run build

test:
	uv run pytest

eval-critical:
	uv run python -m cvm_eval_runner.cli --suite blocking

dev-api:
	uv run uvicorn cvm_platform.main:app --factory --app-dir services/platform-api/src --reload --port 8000

dev-worker:
	uv run python -m cvm_worker.main

dev-web:
	pnpm --dir apps/web-console run start

clean-exports:
	uv run python tools/bootstrap/cleanup_exports.py
