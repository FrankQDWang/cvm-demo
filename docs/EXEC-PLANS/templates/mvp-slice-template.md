# MVP Slice Template

Use this template for every non-trivial MVP slice. A slice is not done until every in-scope `Source Doc + Source ID` row in [Requirement Traceability](/Users/frankqdwang/Agents/cvm-demo/docs/PRODUCT/requirement-traceability.md) has explicit status and evidence.

## Goal

State the user-facing or governance outcome in one paragraph. Do not describe tasks here; describe the result.

## In-Scope Source IDs

- PRD:
- TDD:

Rules:

- Only reference IDs that already exist in [Requirement Traceability](/Users/frankqdwang/Agents/cvm-demo/docs/PRODUCT/requirement-traceability.md).
- If `AC-01` exists in both PRD and TDD, spell it as `PRD AC-01` or `TDD AC-01`.
- If a row is only partially addressed, keep it in scope and define the exact partial target.

## Explicitly Out of Scope

- PRD:
- TDD:

Rules:

- List nearby IDs that are easy to accidentally touch.
- If a dependency is intentionally deferred, name it here instead of hiding it in notes.

## Allowed Write Paths

- `docs/...`

## Forbidden Write Paths

- `docs/_generated/**`
- `contracts/**` unless the slice explicitly targets contract changes
- `libs/py/contracts-generated/**`
- `libs/ts/api-client-generated/**`
- Any path outside the allowed write set

## Preconditions and Dependencies

- Required repo state:
- Required contracts/docs:
- Required local stack or external services:
- Blocking unknowns:

## Implementation Steps

1. Establish the exact baseline and list current gaps against the in-scope IDs.
2. Implement the smallest complete change set that satisfies the in-scope IDs.
3. Update traceability rows with repo evidence and validation evidence.
4. Run the relevant automated checks and capture the exact evidence.
5. Write a close-out that includes validated work, incomplete work, assumptions, and the next slice.

## Acceptance Evidence

- Automated:
- Manual:
- Traceability rows to update:

Rules:

- `Repo Evidence` must be a locatable file path or symbol.
- `Validation Evidence` must be a test, a check command, or a concrete manual verification step.
- Do not mark `implemented` or `validated` without evidence.

## Failure Standard

- The slice fails if any in-scope row has no final status.
- The slice fails if any claim of completion lacks evidence.
- The slice fails if changes leak outside the allowed write set.
- The slice fails if an out-of-scope ID is silently modified or behaviorally changed.

## Open Risks

- Risk:
- Mitigation:

## Required Close-Out Format

- Validated:
- Not completed:
- Assumptions:
- Next step:
