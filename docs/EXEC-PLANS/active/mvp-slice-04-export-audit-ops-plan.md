# MVP Slice 04 Export Audit Ops Plan

Use this plan for the Slice 04 operational and compliance closure that turns the current masked export and ops-summary skeleton into a unified field-policy, export-center, audit-query, and team-lead operations slice.

## Goal

The repository supports policy-consistent export, audit, and ops workflows: masking rules are unified across views, export jobs are asynchronous and traceable, admins can query immutable audit logs, and team-lead ops surfaces expose the required filtered and comparative views.

## In-Scope Source IDs

- PRD: `G5`, `EX-01..06`, `LD-01..04`, `AU-01..05`, `OP-01..02`, `PRD AC-05..08`, `PRD-NFR-SECURITY`, `PRD-NFR-RETENTION`, `PRD-NFR-OPERABILITY`
- TDD: `TDD-ARCH-UNIFIED-MASKING`, `TDD AC-05..08`

Rules:

- Only reference IDs that already exist in [Requirement Traceability](../../PRODUCT/requirement-traceability.md).
- If a row is only partially addressed, keep it in scope and define the exact partial target.

## Explicitly Out of Scope

- PRD: `JD-*`, `KW-*`, `SR-*`, `LI-*`, `CD-*`, `RV-*`, `EV-01`, `PRD-NFR-PERFORMANCE`, `PRD-NFR-CAPACITY`
- TDD: `TDD-WF-SEARCH`, `TDD-WF-AI`, `TDD-WF-DELIVERY`, `TDD-ERR-EVAL`

Rules:

- Do not let audit or ops work silently change recruiter-facing list/detail/verdict rules outside the masking policy shared in this slice.
- Eval-platform and deeper harness work remain in Slice 05.

## Allowed Write Paths

- `contracts/**`
- `services/platform-api/**`
- `services/temporal-worker/**`
- `apps/web-user/**`
- `apps/web-ops/**`
- `libs/ts/platform-api-client/**`
- `libs/py/contracts-generated/**` via codegen only
- `libs/ts/api-client-generated/**` via codegen only
- `tests/**`
- `docs/PRODUCT/**`
- `docs/EXEC-PLANS/**`

## Forbidden Write Paths

- `docs/_generated/**`
- `apps/web-evals/**`
- `.github/**`
- Any path outside the allowed write set

## Preconditions and Dependencies

- Required repo state: masked CSV export, audit-write scaffolding, and minimal ops summary already exist, but export is still synchronous, audit is write-only, and masking is inconsistent across surfaces.
- Required contracts/docs: [Requirement Traceability](../../PRODUCT/requirement-traceability.md) and the completed governance / hardening plans.
- Required local stack or external services: deterministic automation via `make validate` and `make test-stack`; manual validation can use the local stack if download and ops views need interactive confirmation.
- Blocking unknowns: none. The current gaps are explicit: async export center, download audit, unified masking, audit query APIs/UI, team-lead filters/trends/compare views, and retention behavior.

## Implementation Steps

1. Introduce one shared masking and field-policy layer used by export, list/detail, and ops projections.
2. Turn export into an async, queryable job flow with status, retry, expiry, and download-audit semantics.
3. Add immutable audit query surfaces for admins and complete the required sensitive-action coverage.
4. Build team-lead and ops views for filtered metrics, trend lines, compare mode, and reviewed-verdict traceability.
5. Add contract, service, UI, and regression tests, then update Slice 04 rows in [Requirement Traceability](../../PRODUCT/requirement-traceability.md).

## Acceptance Evidence

- Automated: `make codegen`, `make validate`, `make test-stack`
- Manual: export-center walkthrough, masked vs sensitive access checks, audit query walkthrough, and team-lead compare/filter walkthrough
- Traceability rows to update: every row already tagged `Slice 04` in [Requirement Traceability](../../PRODUCT/requirement-traceability.md)

Rules:

- `Repo Evidence` must be a locatable file path or symbol.
- `Validation Evidence` must be a test, a check command, or a concrete manual verification step.
- Do not mark `implemented` or `validated` without evidence.

## Failure Standard

- The slice fails if any surface still bypasses the shared masking policy.
- The slice fails if export, audit, and ops remain write-only or non-queryable where the in-scope rows require retrieval and filtering.
- The slice fails if retention behavior is undocumented or untested.
- The slice fails if eval-platform or CI-gate work is silently folded in.

## Open Risks

- Risk: unified masking can change multiple projections at once and cause user-visible regressions.
- Mitigation: centralize policy first, then add focused projection tests before UI wiring.

- Risk: export/audit retention rules may require background cleanup and durable metadata.
- Mitigation: model retention explicitly and prove it with automated checks rather than operational assumptions.

## Required Close-Out Format

- Validated:
- Not completed:
- Assumptions:
- Next step:
