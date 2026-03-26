# MVP Slice 03 List Detail Verdict Plan

Use this plan for the Slice 03 review-experience closure that turns the current candidate list/detail/verdict skeleton into a reviewer-grade workflow with explicit evidence handling, candidate-pool lifecycle, async AI degradation rules, and durable local review state.

## Goal

Recruiters can browse candidate snapshots, open stable detail views, receive AI assistance asynchronously with clear timeout/degrade behavior, and submit or revise verdicts with the right validation, history, and candidate-pool semantics.

## In-Scope Source IDs

- PRD: `G2`, `G6`, `KW-07..08`, `LI-01..06`, `CD-01..07`, `RV-01..06`, `PRD AC-01`, `PRD AC-03`, `PRD-NFR-USABILITY`
- TDD: `TDD AC-01`, `TDD AC-03`, `TDD-WF-AI`

Rules:

- Only reference IDs that already exist in [Requirement Traceability](../../PRODUCT/requirement-traceability.md).
- If a row is only partially addressed, keep it in scope and define the exact partial target.

## Explicitly Out of Scope

- PRD: `JD-*`, `KW-01..06`, `SR-*`, `EX-*`, `LD-*`, `AU-*`, `OP-*`, `EV-01`
- TDD: `TDD-WF-SEARCH`, `TDD-WF-DELIVERY`, `TDD-ARCH-UNIFIED-MASKING`, `TDD-ERR-EVAL`

Rules:

- Do not expand this slice into export, audit, ops, or CI/harness work.
- AgentRun orchestration changes are only allowed when required to support the AI timeout/degrade behavior in scope.

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
- `.github/**`
- Any path outside the allowed write set

## Preconditions and Dependencies

- Required repo state: snapshot-scoped list loading, detail loading, verdict persistence, and basic evidence spans already exist, but the current UX is synchronous and missing several mandatory reviewer behaviors.
- Required contracts/docs: [Requirement Traceability](../../PRODUCT/requirement-traceability.md) and the completed Slice 01 governance artifacts.
- Required local stack or external services: deterministic automation via `make validate` and `make test-stack`; live OpenAI confidence checks remain optional and manual.
- Blocking unknowns: none. Current gaps already called out in traceability include async AI workflowing, evidence-linked UI, candidate-pool lifecycle, verdict validation for `No`, conflict signaling, and review-state preservation.

## Implementation Steps

1. Make candidate browsing reviewer-grade: preserve list state, expose the required minimum fields and missing-field fallbacks, and add match-highlight/filter/sort behavior tied to snapshot-scoped data.
2. Split detail loading so raw resume content remains available even when AI assistance is pending, slow, or failed; add `AgentRunWorkflow`-compatible async AI behavior where required by in-scope rows.
3. Finish verdict and candidate-pool semantics: enforce `No` reason requirements, support explicit pool add/remove lifecycle, preserve history, and surface reviewer conflicts.
4. Add regression tests for async AI timeout/degrade behavior, evidence rendering, verdict transitions, and local review-state retention.
5. Update Slice 03 rows in [Requirement Traceability](../../PRODUCT/requirement-traceability.md) and write the close-out with exact proof.

## Acceptance Evidence

- Automated: `make codegen`, `make validate`, `make test-stack`
- Manual: user-web walkthrough for list filters, detail reload, async AI retry/degrade, verdict editing, and candidate-pool retention
- Traceability rows to update: every row already tagged `Slice 03` in [Requirement Traceability](../../PRODUCT/requirement-traceability.md)

Rules:

- `Repo Evidence` must be a locatable file path or symbol.
- `Validation Evidence` must be a test, a check command, or a concrete manual verification step.
- Do not mark `implemented` or `validated` without evidence.

## Failure Standard

- The slice fails if AI timeout/degrade behavior still blocks manual review.
- The slice fails if verdict and candidate-pool lifecycle rules remain implicit or testless.
- The slice fails if list/detail UI behavior depends on transient local state that is not preserved across navigation.
- The slice fails if export, audit, ops, or CI gate scope is pulled in without an explicit note.

## Open Risks

- Risk: moving AI work off the request path can destabilize existing detail and verdict flows.
- Mitigation: preserve raw resume loading as the primary path and add focused async failure-path tests before UI polish work.

- Risk: reviewer-state features can create broad UI churn.
- Mitigation: anchor the slice on traceability rows and only add state that is needed to satisfy in-scope requirements.

## Required Close-Out Format

- Validated:
- Not completed:
- Assumptions:
- Next step:
