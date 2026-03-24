# cvm-demo

Local-first AI-native harness MVP for JD-based candidate search and review.

## Quick Start

```bash
mise install
uv sync
pnpm install
make codegen
docker compose up -d
make dev-api
make dev-worker
make dev-web
```

## Repo Shape

- `apps/web-console`: Angular shell with `/cases`, `/agents`, `/ops`, `/evals`.
- `services/platform-api`: FastAPI modular monolith.
- `services/temporal-worker`: Temporal worker and workflows.
- `services/eval-runner`: Blocking eval suite runner.
- `contracts`: Internal and external contracts.
- `docs`: System of record for architecture and execution plans.

## Toolchain

- Node: `24.x` via `mise.toml`
- Python: managed by `uv`
- Frontend package manager: `pnpm`

## References

- [OpenAI Harness Engineering](https://openai.com/index/harness-engineering/)
- [`prd.pdf`](/Users/frankqdwang/Documents/工作/cv-match/prd.pdf)
- [`TDD.pdf`](/Users/frankqdwang/Documents/工作/cv-match/TDD.pdf)
