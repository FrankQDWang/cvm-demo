# Hard Harness Plan

## Goal

Turn the repository from soft local checks into a repo-local hard harness:

- `contracts/` is the single boundary source of truth
- generated code stays generated and is guarded by clean checks only
- handwritten Python / TypeScript code enters strict static gates immediately
- runtime boundaries validate external data before application logic consumes it
- deterministic tests and stack-smoke tests are split into separate enforcement paths

## Scope

- `contracts/openapi/platform-api.openapi.yaml`
- `services/platform-api`
- `apps/web-user`, `apps/web-ops`, `apps/web-evals`
- `libs/ts/platform-api-client`
- repository governance files under root / `.github/` / `tools/ci/`

## Workstreams

1. Tighten the internal OpenAPI contract and regenerate Python / TypeScript artifacts.
2. Replace loose error handling and raw boundary JSON with typed error contracts and strict Pydantic boundary models.
3. Split repository validation into static gates, contract gates, deterministic tests, and stack-smoke tests.
4. Add repo-local governance files for pyright, ESLint, Semgrep, pre-commit, coverage, and CODEOWNERS.

## Exit Criteria

- API contract exposes explicit `StructuredFilters`, `NormalizedQuery`, resume projection, ops summary, and `ApiErrorResponse`
- service / adapter boundaries reject malformed CTS and OpenAI payloads before domain logic
- `/openapi.json` is served from the checked-in contract file
- `make validate-static`, `make validate-contracts`, `make test`, and `make test-stack` exist and are independently enforceable
- deterministic tests run without a pre-started local stack
- stack smoke remains available as a separate gate

## Close-Out

- Validated: the checked-in contract exposes the explicit error and projection schemas; strict boundary validation rejects malformed CTS/OpenAI payloads; `/openapi.json` is served from the checked-in OpenAPI file; `make validate-static`, `make validate-contracts`, `make test`, `make test-stack`, and `make eval-critical` all pass.
- Not completed: broader performance, capacity, and eval-platform work is not part of this baseline hard harness and moves to Slice 04 and Slice 05.
- Assumptions: deterministic stack-backed harnesses are the repo-local default for repeatable validation, while live `.env` remains available for manual operational checks when needed.
- Next step: keep this plan as the completed hard-harness baseline and continue the remaining ops, audit, and harness expansion in Slice 04 and Slice 05.
