# Dependency Governance Plan

## Goal

Implement the long-term dependency governance and boundary hardening plan across Python and TypeScript.

## Scope

- `services/platform-api` application / infrastructure decoupling
- Python dependency metadata and Tach enforcement
- TypeScript workspace package formalization and shared API client extraction
- Dependency Cruiser and Knip repository governance
- `make validate` and CI hard-gates

## Phases

1. Move `PlatformService` onto application-owned ports, runtime config, and DTOs.
2. Correct Python dependency declarations and install Tach as a root governance tool.
3. Formalize `libs/ts/*` as pnpm workspace packages and route app imports through `@cvm/platform-api-client`.
4. Add repository-wide TypeScript dependency and unused-code governance.
5. Make `make validate` the single strict local/CI enforcement path.

## Exit Criteria

- `PlatformService` no longer imports SQLAlchemy, `cvm_platform.infrastructure`, or `cvm_platform.settings`
- `uv run python tools/ci/check_architecture.py` passes
- `uv run tach check --dependencies` passes
- `uv run tach check-external` passes
- `pnpm run check:deps:ts` passes
- `pnpm run check:unused:ts` passes
- `make validate`, `make test`, and `make eval-critical` pass
