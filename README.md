# cvm-demo

Local-first AI-native harness MVP for JD-based candidate search and review.

## Quick Start

```bash
mise install
cp .env.example .env
make up
```

- `Cases` 页现在按业务步骤拆成 `新建 JD Case -> 生成草案 -> 确认条件 -> Search Run -> 浏览候选 -> 简历辅助分析 -> verdict -> 导出`。
- 默认搜索源是 `CTS`；复制 `.env.example` 后需要填入 `CVM_CTS_TENANT_KEY` 和 `CVM_CTS_TENANT_SECRET`。
- `.env.example` 里已经补齐 `LLM` 配置位：`CVM_LLM_MODE`、`CVM_LLM_PROVIDER`、`CVM_LLM_MODEL`、`OPENAI_API_KEY` 等。
- 默认仍是 `stub`；切到 `CVM_LLM_MODE=live` 并填写 `OPENAI_API_KEY` 后，API 和 worker 会调用 OpenAI `Responses API`。
- `Search Run` 现在默认且唯一通过 `Temporal` 执行，不再支持同步 fallback。
- `Temporal` 可见性现在默认走 `OpenSearch-backed advanced visibility`；判断 `Temporal UI` 前，先执行显式重建命令。

## Repo Shape

- `apps/web-user`: User-facing recruiting workbench.
- `apps/web-ops`: Internal monitoring web.
- `apps/web-evals`: Internal evaluation web.
- `services/platform-api`: FastAPI modular monolith.
- `services/temporal-worker`: Temporal worker and workflows.
- `services/eval-runner`: Blocking eval suite runner.
- `contracts`: Internal and external contracts.
- `docs`: System of record for architecture and execution plans.

## Toolchain

- Node: `24.x` via `mise.toml`
- Python: managed by `uv`
- Frontend package manager: `pnpm`

## Runtime Notes

- User web lives in `apps/web-user`, monitoring web in `apps/web-ops`, and evaluation web in `apps/web-evals`.
- `docker compose` now starts the full local stack: `postgres`, `opensearch`, `temporal`, `temporal-ui`, `temporal-admin-tools`, `api`, `worker`, `web-user`, `web-ops`, and `web-evals`.
- Manual host-mode development is available with `make dev-api`, `make dev-worker`, `make dev-web-user`, `make dev-web-ops`, and `make dev-web-evals`.
- Configuration is loaded from `.env`; start from `.env.example`.

## One-Click Local Run

```bash
cp .env.example .env
make up
make up-build
make rebuild-backend
make rebuild-temporal-stack
make temporal-visibility-smoke
make status
make down
```

- `make up` runs `docker compose up -d` and reuses existing images when possible.
- `make up-build` runs `docker compose up -d --build` when Dockerfile or dependencies changed, and refreshes `CVM_BUILD_ID`.
- `make rebuild-backend` only rebuilds `api + worker`; use it after changing Python code or dependencies.
- `make rebuild-temporal-stack` force-recreates `opensearch + temporal + temporal-ui + temporal-admin-tools`; use it after changing Temporal/OpenSearch config.
- `make temporal-visibility-smoke` creates a smoke `SearchRun` and checks DB state, Temporal execution, visibility index, and UI count together.
- `make test` 和 `make eval-critical` 依赖已启动的本地 `postgres + temporal + api + worker`。
- `make up` and `make status` both print copyable local URLs after execution.
- User Web: `http://127.0.0.1:4200`
- Ops Web: `http://127.0.0.1:4201`
- Evals Web: `http://127.0.0.1:4202`
- API URL: `http://127.0.0.1:8010`
- Temporal UI: `http://127.0.0.1:8080`
- OpenSearch: `http://127.0.0.1:9200`
- Ports are configurable in `.env` via `CVM_API_PORT`, `CVM_USER_WEB_PORT`, `CVM_OPS_WEB_PORT`, and `CVM_EVALS_WEB_PORT`.
- On this machine, `localhost` may resolve to IPv6 `::1`; if you hit resets, use `127.0.0.1`.

## References

- [OpenAI Harness Engineering](https://openai.com/index/harness-engineering/)
- [`prd.pdf`](/Users/frankqdwang/Documents/工作/cv-match/prd.pdf)
- [`TDD.pdf`](/Users/frankqdwang/Documents/工作/cv-match/TDD.pdf)
