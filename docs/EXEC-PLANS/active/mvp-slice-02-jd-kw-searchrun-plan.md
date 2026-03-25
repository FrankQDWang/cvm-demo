# MVP Slice 02 JD KW SearchRun Plan

Use this plan for the Slice 02 mainline closure that takes the current JD -> keyword draft -> confirmed plan -> SearchRun skeleton and turns it into a fully governed, test-backed mainline slice without pulling list/detail/verdict, export/audit/ops, or harness backlog into scope.

## Goal

Recruiters can create and evolve a JD case, obtain one or more structured keyword plans with explicit human confirmation, and execute a SearchRun whose state, pagination, retries, and stop/continue controls are contract-backed, idempotent, and regression-tested end to end.

## In-Scope Source IDs

- PRD: `G1`, `G3`, `G4`, `JD-01..06`, `KW-01..06`, `SR-01..07`, `SR-09`, `PRD AC-02`, `PRD AC-04`
- TDD: `TDD AC-02`, `TDD AC-04`, `TDD-WF-SEARCH`, `TDD-IDEMPOTENCY-SEARCH-RUN`, `TDD-IDEMPOTENCY-PAGE-SNAPSHOT`

Rules:

- Only reference IDs that already exist in [Requirement Traceability](../../PRODUCT/requirement-traceability.md).
- If a row is only partially addressed, keep it in scope and define the exact partial target.

## Explicitly Out of Scope

- PRD: `G2`, `G5`, `G6`, `KW-07..08`, `LI-*`, `CD-*`, `RV-*`, `EX-*`, `LD-*`, `AU-*`, `OP-*`, `EV-01`, `SR-08`
- TDD: `TDD-WF-AI`, `TDD-WF-DELIVERY`, `TDD-ARCH-UNIFIED-MASKING`, `TDD-ERR-EVAL`

Rules:

- Do not pull candidate list/detail/verdict, export/audit/ops, or eval-platform behavior into this slice.
- If a requirement depends on async AI degradation beyond SearchRun, leave it for Slice 03 or Slice 05 and call it out in notes.

## Allowed Write Paths

- `contracts/**`
- `services/platform-api/**`
- `services/temporal-worker/**`
- `apps/web-user/**`
- `libs/ts/platform-api-client/**`
- `libs/py/contracts-generated/**` via codegen only
- `libs/ts/api-client-generated/**` via codegen only
- `tests/**`
- `docs/PRODUCT/**`
- `docs/EXEC-PLANS/**`

## Forbidden Write Paths

- `docs/_generated/**`
- `apps/web-ops/**`
- `apps/web-evals/**`
- `services/eval-runner/**`
- Any path outside the allowed write set

## Preconditions and Dependencies

- Required repo state: `create_case`, `create_jd_version`, keyword draft/confirm, `SearchRunWorkflow`, idempotency constraints, and CTS anomaly distinction already exist in the current repo.
- Required contracts/docs: [Requirement Traceability](../../PRODUCT/requirement-traceability.md), [MVP Slice Template](../templates/mvp-slice-template.md), and the completed governance / hardening plans under `docs/EXEC-PLANS/completed/`.
- Required local stack or external services: deterministic stack-backed automation via `make test-stack`; live `.env` remains available for manual CTS/OpenAI confidence checks if needed.
- Blocking unknowns: none. The current gaps are explicit in traceability: JD archive and unsaved-change guards, long-JD contract handling, multi-plan/conflict handling, explicit SearchRun control semantics, and stronger retry/stop proofs.

## Implementation Steps

1. Close JD lifecycle rules: archive semantics, active-version guards, long-JD rejection or condense entrypoint, and unsaved-change protection.
2. Upgrade keyword plan authoring: preserve evidence, support the required plan-editing operations, add explicit multi-plan selection and conflict detection, and keep human confirmation as the only SearchRun trigger.
3. Complete SearchRun control semantics: freeze actor/version metadata, enforce the initial page budget and explicit continue/stop actions, preserve partial-success visibility, and guarantee retry/idempotency behavior without duplicate snapshots or candidates.
4. Extend contract, API, UI, and stack-backed tests to prove the in-scope rows rather than relying on structural inference.
5. Update Slice 02 rows in [Requirement Traceability](../../PRODUCT/requirement-traceability.md) with concrete repo evidence and validation evidence, then write the close-out using the required format.

## Acceptance Evidence

- Automated: `make codegen`, `make validate`, `make test-stack`
- Manual: user-web mainline walkthrough for JD creation, plan confirmation, SearchRun start, explicit continue/stop, and partial-results visibility
- Traceability rows to update: every row already tagged `Slice 02` in [Requirement Traceability](../../PRODUCT/requirement-traceability.md)

Rules:

- `Repo Evidence` must be a locatable file path or symbol.
- `Validation Evidence` must be a test, a check command, or a concrete manual verification step.
- Do not mark `implemented` or `validated` without evidence.

## Failure Standard

- The slice fails if any in-scope row has no final status.
- The slice fails if SearchRun behavior depends on undocumented implicit UI behavior instead of explicit API and workflow rules.
- The slice fails if changes leak into list/detail/verdict, export/audit/ops, or eval-platform behavior.
- The slice fails if contract changes are made without running codegen and generated-clean checks.

## Open Risks

- Risk: JD, keyword, and SearchRun rules are tightly coupled, so shallow fixes can create regressions across API, workflow, and user web.
- Mitigation: keep contract, service, workflow, and UI changes together and require stack-backed regression proof.

- Risk: live CTS behavior can differ from deterministic test harness behavior.
- Mitigation: keep automation deterministic, then do a bounded live confidence pass only after automated gates are green.

## Required Close-Out Format

- Validated:
- Not completed:
- Assumptions:
- Next step:
