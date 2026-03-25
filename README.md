# cvm-demo

Local-first AI-native harness MVP for JD-based candidate search and review.

## Quick Start

```bash
mise install
cp .env.example .env
make up
```

- `Cases` 页现在按业务步骤拆成 `新建 JD Case -> 生成草案 -> 确认条件 -> Search Run -> 浏览候选 -> 简历辅助分析 -> verdict -> 导出`。
- `.env` / `.env.example` 只表达真实运行时集成：默认搜索源是 `CTS`，复制 `.env.example` 后需要填入 `CVM_CTS_TENANT_KEY`、`CVM_CTS_TENANT_SECRET` 和 `OPENAI_API_KEY`。
- `API` 和 `worker` 在本地运行时默认按 `CVM_LLM_MODE=live` 调用 OpenAI `Responses API`；自动化测试与 CI 不读取这些 mode 作为判定依据，而是显式切到 deterministic `mock + stub`。
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
- 真实运行时配置从 `.env` 读取；自动化 stack tests 和 CI 会显式覆盖为 deterministic `mock + stub`，不依赖 `.env` 中的 mode 配置。

## CI

- `validate` is the only PR-blocking workflow; the intended required checks remain `validate-static`, `validate-contracts`, `test`, and `test-stack`.
- `test-stack` and `nightly-regression` pin stack-backed jobs to `CVM_RESUME_SOURCE_MODE=mock` and `CVM_LLM_MODE=stub`, so CI does not depend on live CTS or OpenAI behavior.
- `nightly-regression` runs the stack-backed `make eval-critical` gate and `make temporal-visibility-smoke`.
- `build-verify` runs `make verify-images` to prove the runtime Docker images still build from the checked-in lockfiles and Dockerfiles.

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
- `make test` is deterministic and does not require a pre-started local stack.
- `make test-stack`, `make eval-critical`, and `make temporal-visibility-smoke` now self-manage an isolated deterministic compose stack with `mock + stub`; they do not consume `.env` 中的 LLM / CTS mode.
- If you intentionally want to point these commands at an already running stack, set `CVM_EXTERNAL_STACK=1`.
- `make verify-images` validates that `api`, `worker`, `web-user`, `web-ops`, and `web-evals` Docker images still build from the current worktree.
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
