# MVP Slice 05 Harness Evals Gates Plan

Use this plan for the Slice 05 closure that owns the remaining harness, eval, delivery-workflow, and architecture-hardening backlog after the baseline governance, dependency, hard-harness, and CI pipeline plans have been completed and archived.

## Goal

The repository exposes a coherent harness and gate model: remaining architecture hardening items are resolved or explicitly documented, delivery and eval workflows are backgrounded where required, deterministic and live validation paths are intentional, and CI/release gates fail with stable error contracts and diagnostics.

## In-Scope Source IDs

- PRD: `SR-08`, `EV-01`, `PRD-NFR-PERFORMANCE`, `PRD-NFR-RELIABILITY`, `PRD-NFR-CAPACITY`, `PRD-NFR-TRACEABILITY`
- TDD: `ADR-001`, `ADR-002`, `ADR-003`, `ADR-004`, `ADR-006`, `ADR-007`, `ADR-008`, `TDD-ARCH-DOMAIN-BOUNDARY`, `TDD-ARCH-CONTRACT-FIRST`, `TDD-ARCH-AI-SCHEMA`, `TDD-ARCH-SNAPSHOT-IMMUTABILITY`, `TDD-ERR-API-GUARDS`, `TDD-ERR-DEGRADE`, `TDD-ERR-PERMISSION-IDEMPOTENCY`, `TDD-ERR-EVAL`, `TDD-WF-DELIVERY`, `TDD-IDEMPOTENCY-EXPORT-EVENTS`, `TDD-WEEK1-GATES`, `TDD-HARD-RULES`

Rules:

- Only reference IDs that already exist in [Requirement Traceability](../../PRODUCT/requirement-traceability.md).
- If a row is only partially addressed, keep it in scope and define the exact partial target.

## Explicitly Out of Scope

- PRD: `JD-*`, `KW-*`, `LI-*`, `CD-*`, `RV-*`, `EX-*`, `LD-*`, `AU-*`, `OP-*`
- TDD: `TDD-WF-SEARCH`, `TDD-WF-AI`, `TDD-ARCH-UNIFIED-MASKING`

Rules:

- Do not pull recruiter-facing feature polish back into this slice unless it is required to satisfy an in-scope harness or architecture row.
- Slice 05 is the home for remaining architecture and gate hardening, not a catch-all for unfinished UI work.

## Allowed Write Paths

- `.github/**`
- `tools/ci/**`
- `Makefile`
- `contracts/**`
- `services/platform-api/**`
- `services/temporal-worker/**`
- `services/eval-runner/**`
- `apps/web-ops/**` when required for eval or metrics views
- `libs/ts/platform-api-client/**`
- `libs/py/contracts-generated/**` via codegen only
- `libs/ts/api-client-generated/**` via codegen only
- `tests/**`
- `docs/PRODUCT/**`
- `docs/EXEC-PLANS/**`
- `README.md`

## Forbidden Write Paths

- `docs/_generated/**`
- `apps/web-user/**` unless needed for an in-scope contract or runtime-hardening issue
- Any path outside the allowed write set

## Preconditions and Dependencies

- Required repo state: deterministic stack harnesses, nightly/build verification workflows, blocking eval, AgentRun workflow, and snapshot immutability already exist in baseline form.
- Required contracts/docs: [Requirement Traceability](../../PRODUCT/requirement-traceability.md) and the completed plans under `docs/EXEC-PLANS/completed/`.
- Required local stack or external services: deterministic stack automation via `make test-stack`, `make eval-critical`, and `make temporal-visibility-smoke`; live `.env` remains available for manual CTS/OpenAI confidence checks and throughput investigations.
- Blocking unknowns: `ADR-002` is currently marked `conflict` and must either be explicitly retired, revised, or resolved in-repo rather than silently carried forward.

## Implementation Steps

1. Resolve the remaining architecture and contract hardening rows: document or fix `ADR-002`, complete contract-first async boundary rules, close AI schema-versioning gaps, and finish the remaining stable error-contract expectations.
2. Background the remaining delivery and eval workflows where the TDD requires orchestration rather than request-thread execution.
3. Complete eval and gate behavior: comparison-oriented eval surfaces, explicit `EVAL_BLOCKING_FAILED` propagation, export-event dedupe, and the remaining Week 1 / hard-rule enforcement gaps.
4. Add performance, reliability, capacity, and traceability instrumentation plus the tests or harnesses needed to validate those claims.
5. Update Slice 05 rows in [Requirement Traceability](../../PRODUCT/requirement-traceability.md) and write a close-out that makes every remaining architecture decision explicit.

## Acceptance Evidence

- Automated: `make codegen`, `make validate`, `make test-stack`, `make eval-critical`, `make temporal-visibility-smoke`, `make verify-images`
- Manual: eval comparison workflow review, CI workflow review for explicit gate semantics, and any documented live confidence pass needed to close performance or reliability claims
- Traceability rows to update: every row already tagged `Slice 05` in [Requirement Traceability](../../PRODUCT/requirement-traceability.md)

Rules:

- `Repo Evidence` must be a locatable file path or symbol.
- `Validation Evidence` must be a test, a check command, or a concrete manual verification step.
- Do not mark `implemented` or `validated` without evidence.

## Failure Standard

- The slice fails if `ADR-002` remains in unresolved conflict without an explicit repo decision.
- The slice fails if eval and gate behavior still depends on informal workflow conventions rather than stable scripts, jobs, and error contracts.
- The slice fails if performance, reliability, or capacity claims are asserted without instrumentation or proof.
- The slice fails if generated artifacts or boundary DTOs are hand-edited.

## Open Risks

- Risk: Slice 05 mixes architecture, workflow, and CI concerns, so scope creep is likely.
- Mitigation: keep every change tied to a specific in-scope traceability row and reject generic cleanup that does not close one.

- Risk: live CTS/OpenAI behavior can mask deterministic harness regressions or vice versa.
- Mitigation: keep deterministic automation authoritative and use live checks only as bounded confidence evidence.

## Required Close-Out Format

- Validated:
- Not completed:
- Assumptions:
- Next step:
