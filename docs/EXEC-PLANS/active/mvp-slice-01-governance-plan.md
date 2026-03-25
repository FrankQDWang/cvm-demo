# MVP Slice 01 Governance Plan

## Goal

Turn PRD/TDD from narrative PDF inputs into repository-native execution controls. Slice 01 does not change runtime behavior; it creates the traceability matrix, audits current repo coverage against the source documents, and fixes the execution-plan contract for all later slices.

## In-Scope Source IDs

- PRD: `G1-G6`, `JD-01..06`, `KW-01..08`, `SR-01..09`, `LI-01..06`, `CD-01..07`, `RV-01..06`, `EX-01..06`, `LD-01..04`, `AU-01..05`, `OP-01..02`, `EV-01`, `PRD AC-01..08`, `PRD-NFR-*`
- TDD: `ADR-001..008`, `TDD AC-01..08`, `TDD-ARCH-*`, `TDD-ERR-*`, `TDD-WF-*`, `TDD-IDEMPOTENCY-*`, `TDD-DAY0-GATES`, `TDD-WEEK1-GATES`, `TDD-HARD-RULES`

## Explicitly Out of Scope

- Runtime API behavior changes
- Database schema changes
- Codegen updates
- UI behavior fixes
- New tests beyond evidence capture for the governance documents themselves

## Allowed Write Paths

- `docs/00-INDEX.md`
- `docs/PRODUCT/**`
- `docs/EXEC-PLANS/**`

## Forbidden Write Paths

- `docs/_generated/**`
- `contracts/**`
- `libs/py/contracts-generated/**`
- `libs/ts/api-client-generated/**`
- `services/**`
- `apps/**`
- `tests/**`

## Preconditions and Dependencies

- Normative source documents remain [prd.pdf](/Users/frankqdwang/Agents/cvm-demo/prd.pdf) and [TDD.pdf](/Users/frankqdwang/Agents/cvm-demo/TDD.pdf).
- The execution source is repository markdown, not chat history.
- The current worktree may already contain in-flight code changes; Slice 01 audits them but does not bless them as complete without evidence.

## Implementation Steps

1. Create [Requirement Traceability](/Users/frankqdwang/Agents/cvm-demo/docs/PRODUCT/requirement-traceability.md) with one queryable row identity per `Source Doc + Source ID`.
2. Define status vocabulary, evidence rules, and synthetic ID namespaces for unnumbered PRD/TDD clauses.
3. Audit the current repository conservatively:
   - `validated` only when a concrete test or check already proves the behavior
   - `implemented` only when code exists but proof is missing
   - `partial` when only part of the requirement is visible
   - `missing` when no direct evidence exists
   - `deferred` or `conflict` only with an explicit note
4. Map current active execution plans to requirement IDs and assign disposition:
   - [bootstrap-plan.md](/Users/frankqdwang/Agents/cvm-demo/docs/EXEC-PLANS/active/bootstrap-plan.md): keep as historical bootstrap note; not sufficient as an execution source because it has no row-level traceability.
   - [dependency-governance-plan.md](/Users/frankqdwang/Agents/cvm-demo/docs/EXEC-PLANS/active/dependency-governance-plan.md): retain as thematic reference; split across Slice 02 and Slice 05 once mapped to concrete IDs.
   - [hard-harness-plan.md](/Users/frankqdwang/Agents/cvm-demo/docs/EXEC-PLANS/active/hard-harness-plan.md): retain as thematic reference; split across Slice 04 and Slice 05 once mapped to concrete IDs.
5. Install [MVP Slice Template](/Users/frankqdwang/Agents/cvm-demo/docs/EXEC-PLANS/templates/mvp-slice-template.md) as the only allowed template for future non-trivial slices.
6. Publish the default next-slice sequence:
   - Slice 02: `JD / KW / SearchRun` mainline
   - Slice 03: `List / Detail / Verdict`
   - Slice 04: `Export / Audit / Ops`
   - Slice 05: `Harness / Evals / Gates`

## Acceptance Evidence

- [Requirement Traceability](/Users/frankqdwang/Agents/cvm-demo/docs/PRODUCT/requirement-traceability.md) exists and covers the entire Slice 01 in-scope ID set.
- [MVP Slice Template](/Users/frankqdwang/Agents/cvm-demo/docs/EXEC-PLANS/templates/mvp-slice-template.md) exists and encodes mandatory sections for later slices.
- This plan explicitly names allowed write paths, forbidden write paths, and existing-plan dispositions.
- [docs/00-INDEX.md](/Users/frankqdwang/Agents/cvm-demo/docs/00-INDEX.md) exposes the new governance artifacts.
- Link validation passes for the new docs.

## Failure Standard

- Slice 01 fails if any PRD numbered ID or required TDD key item is absent from the traceability document.
- Slice 01 fails if any row is marked `implemented` or `validated` without repo evidence and validation evidence.
- Slice 01 fails if future slices could still cite PDFs directly without first landing requirement IDs in repo markdown.
- Slice 01 fails if the default slice sequence is omitted.

## Open Risks

- The status audit will age as code changes land; later slices must treat it as a snapshot and update affected rows.
- Some PDF clauses are narrative rather than formally numbered; synthetic IDs are required to keep them queryable.
- Compliance and role-boundary requirements still depend on final business confirmation, so several rows may remain `missing` or `deferred`.

## Required Close-Out Format

- Validated:
- Not completed:
- Assumptions:
- Next step:
