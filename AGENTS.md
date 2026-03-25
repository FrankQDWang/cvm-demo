# AGENTS.md

## What This Repo Is
- Local-first MVP for JD-to-candidate matching.
- Runtime shape: one Angular shell, one FastAPI API, one Temporal worker, one PostgreSQL database.
- Start with `docs/00-INDEX.md` and `docs/ARCHITECTURE/context-map.md`.

## Hard Rules
- Single-branch repository: never create, switch to, or push any branch other than `main`.
- Do not edit `docs/_generated` by hand.
- Do not edit `libs/py/contracts-generated` or `libs/ts/api-client-generated` by hand.
- Do not bypass `contracts/` when changing boundary DTOs.
- Do not import HTTP, SQLAlchemy, or Temporal SDK modules into `services/platform-api/src/cvm_platform/domain`.

## Commands
- `uv sync`
- `pnpm install`
- `make codegen`
- `make validate`
- `make test`
- `make eval-critical`

## Task Intake
- Use `docs/EXEC-PLANS/active/` for non-trivial work.
- Keep implementation aligned with `docs/PRODUCT/requirements.md`.
- External CTS behavior is sourced from `contracts/external/cts.validated.yaml`.
