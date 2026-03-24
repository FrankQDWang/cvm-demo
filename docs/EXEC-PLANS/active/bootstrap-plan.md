# Bootstrap Plan

## Goal

Create a local-first AI-native MVP harness from an empty repository.

## Scope

- Repo operating system
- Contract-first backend and generated clients
- Angular shell routes
- Local compose for PostgreSQL and Temporal
- Blocking eval runner and validation scripts

## Exit Criteria

- `uv sync` succeeds
- `pnpm install` succeeds
- `make codegen`, `make validate`, `make test`, and `make eval-critical` succeed
