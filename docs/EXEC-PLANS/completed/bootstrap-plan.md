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

## Close-Out

- Validated: `uv sync`; `pnpm install`; `make codegen`; `make validate`; `make test`; `make up-build`; `make eval-critical`
- Not completed: no additional product-slice delivery is bundled into this historical bootstrap note; remaining behavior work is transferred to Slice 02-05.
- Assumptions: live `.env` credentials remain available for manual full-stack verification; repo-local stack-backed gates now prefer the deterministic harness behind `make test-stack` and `make eval-critical`.
- Next step: keep this plan as a completed historical bootstrap reference only and execute Slice 02-05 as the active delivery plans.
