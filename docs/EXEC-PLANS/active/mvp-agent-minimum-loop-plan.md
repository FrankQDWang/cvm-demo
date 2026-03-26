# MVP Agent Minimum Loop Plan

Use this plan for the extracted short-path delivery of a complete agent loop that spans selected Slice 02, Slice 03, and Slice 05 rows. This plan does not change `Target Slice` ownership in [Requirement Traceability](../../PRODUCT/requirement-traceability.md); it is a focused execution wedge for the fastest end-to-end agent closure inside the current PRD and TDD boundary.

## Goal

The user pastes exactly two raw inputs, `JD` and `寻访偏好`, then starts one bounded agent run. The system uses Chinese prompts to extract search intent from those inputs, generates a first-round CTS query, records an append-only round ledger, searches CTS in multiple configurable ReAct rounds, deduplicates repeated resumes across rounds, uses parallel LLM analysis to keep only the strongest candidates, and returns a final shortlist of 5 resumes with selection rationales. The full run is traceable in a self-hosted local Langfuse deployment, while the product UI remains minimal in v1: the business UI shows only the initial input and final output, and run review happens in Langfuse on port `4202` rather than a separate Angular eval app.

## In-Scope Source IDs

- PRD: `G1`, `G3`, `G4`, `G6`, `JD-01`, `KW-01`, `KW-05`, `KW-07`, `SR-01`, `SR-03`, `SR-04`, `SR-06`, `SR-07`, `LI-01`, `CD-01`, `CD-02`, `CD-03`, `CD-04`, `CD-06`, `EV-01`, `PRD AC-03`, `PRD-NFR-PERFORMANCE`, `PRD-NFR-RELIABILITY`, `PRD-NFR-TRACEABILITY`, `PRD-NFR-USABILITY`
- TDD: `TDD AC-02`, `TDD AC-03`, `TDD-WF-SEARCH`, `TDD-WF-AI`, `TDD-WF-DELIVERY`, `TDD-IDEMPOTENCY-SEARCH-RUN`, `TDD-ARCH-AI-SCHEMA`, `TDD-ERR-DEGRADE`, `ADR-007`

Rules:

- Only reference IDs that already exist in [Requirement Traceability](../../PRODUCT/requirement-traceability.md).
- This plan owns only the minimum closed loop for `JD + 寻访偏好 -> final top 5 resumes with reasons`.
- `EV-01` is in scope only as self-hosted Langfuse-linked run review, not as a separate Angular eval product or a full prompt/model comparison platform.
- If a row is only partially addressed in v1, the close-out must say so explicitly instead of stretching the implementation to cover unrelated scope.

## Explicitly Out of Scope

- PRD: `JD-02..06`, `KW-02..06`, `KW-08`, `SR-02`, `SR-05`, `SR-08`, `SR-09`, `LI-02..06`, `CD-05`, `CD-07`, `RV-*`, `EX-*`, `LD-*`, `AU-*`, `OP-*`, `PRD AC-01`, `PRD AC-05..08`, `PRD-NFR-CAPACITY`, `PRD-NFR-SECURITY`, `PRD-NFR-RETENTION`, `PRD-NFR-OPERABILITY`
- TDD: `AC-01`, `AC-04..08`, `TDD-ARCH-CONTRACT-FIRST`, `TDD-ARCH-SNAPSHOT-IMMUTABILITY`, `TDD-ARCH-UNIFIED-MASKING`, `TDD-ERR-API-GUARDS`, `TDD-ERR-PERMISSION-IDEMPOTENCY`, `TDD-ERR-EVAL`, `TDD-IDEMPOTENCY-PAGE-SNAPSHOT`, `TDD-IDEMPOTENCY-EXPORT-EVENTS`, `TDD-WEEK1-GATES`, `TDD-HARD-RULES`, `ADR-002`, `ADR-003`, `ADR-004`, `ADR-006`, `ADR-008`

Rules:

- Do not turn this slice into a generic multi-agent platform, memory platform, or broad ops/audit/dashboard program.
- Do not add extra end-user workflow steps beyond the two raw inputs and one explicit run start.
- Existing Angular screens are disposable scaffolds for this slice. The frontend track must delete and rebuild them rather than polishing the current UI incrementally.
- Langfuse is the local trace backend and eval surface for this slice, not a prompt to build a third product surface.

## Allowed Write Paths

- `contracts/**`
- `services/platform-api/**`
- `services/temporal-worker/**`
- `services/eval-runner/**`
- `apps/web-user/**`
- `docker-compose.yml`
- `infra/docker/**`
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

## Execution Split

- Backend track:
  this conversation owns contract changes, persistence model, workflow orchestration, CTS search loop, dedupe, LLM ranking, reflection summaries, Langfuse integration, and backend validation.
- Frontend track:
  a separate conversation owns deleting the current `web-user` screen and rebuilding the business UI from scratch against the backend contract finalized here; `4202` is reserved for self-hosted Langfuse instead of a custom eval frontend.

Rules:

- Backend is the source of truth for run state, trace payloads, and step semantics.
- Frontend may not invent extra workflow semantics or hidden state to compensate for missing backend fields.
- If frontend work reveals a backend contract gap, update this plan and the backend contract first instead of encoding the gap in Angular-only logic.

## Preconditions and Dependencies

- Required repo state: Slice 02 agent-run baseline, CTS adapter, Temporal worker, and eval-runner skeletons already exist; current Angular UIs exist only as replaceable scaffolds.
- Required contracts/docs: [Requirement Traceability](../../PRODUCT/requirement-traceability.md), [MVP Slice 02 JD KW Agent Run Plan](mvp-slice-02-jd-kw-agent-run-plan.md), [MVP Slice 03 List Detail Verdict Plan](mvp-slice-03-list-detail-verdict-plan.md), and [MVP Slice 05 Harness Evals Gates Plan](mvp-slice-05-harness-evals-gates-plan.md).
- Required local stack or external services: local Docker stack, Temporal, OpenSearch, CTS connectivity, and self-hosted Langfuse remain required; live OpenAI remains optional for confidence checks, but deterministic test paths must stay authoritative.
- Blocking unknowns: local Langfuse bootstrap credentials, storage volumes, and host/container URL split must stay aligned so trace ingestion and browser links both work.

## Confirmed Business Flow

1. The user provides exactly two inputs: raw `JD` text and raw `寻访偏好` text.
2. The backend creates one `AgentRun` with configurable defaults, initially `max_rounds=3`, `round_fetch_schedule=[10, 5, 5]`, and `final_top_k=5`; runtime configuration may increase `max_rounds` up to `5`, but not below `3`.
3. The agent extracts structured search intent from the two raw inputs and produces a Chinese first-round search plan with `must/core/bonus/exclude` understanding plus one first-round CTS query.
4. The agent calls CTS, first fetching 10 resumes, then 5 per later round.
5. CTS results are deduplicated against all previously seen resumes before any LLM scoring or ranking.
6. Only newly admitted resumes are analyzed in parallel by the LLM against the JD and user preference.
7. Each round keeps the strongest candidates, discards the weakest, appends one explicit round ledger entry, and emits one Chinese reflection summary that may revise only the next CTS search strategy.
8. The run must execute at least `3` rounds; after that it may stop when `max_rounds` is reached, or when there is no meaningful new progress, or when the shortlist has stabilized.
9. The final output is exactly 5 resumes, each with one LLM-written explanation of why it was selected.
10. Langfuse records the full run trace as a round-grouped tree: root `agent-run`, global `extract-search-strategy` and `finalize`, plus one `round-N` node per round that contains `cts-search`, `dedupe`, `analysis`, `shortlist`, `reflect`, and `stop` children as applicable.

Rules:

- Persist explicit reasoning summaries and reflection notes; do not persist opaque or hidden provider chain-of-thought.
- The run must have a hard stop for duplicate search strategies or repeated no-progress rounds, but not before the minimum `3` rounds are executed.
- Duplicate resumes from CTS must be skipped before ranking and must not re-enter the candidate pool.

## Implementation Steps

1. Define the contract and persistence model for an `AgentRun`: raw `jdText`, raw `sourcingPreferenceText`, round config, round timeline, first-round strategy extraction, append-only round ledger, CTS request/response summaries, dedupe counters, candidate analyses, reflection summaries, final shortlist, prompt/model versions, and Langfuse correlation identifiers.
2. Implement a bounded `AgentRunWorkflow` and API surface that executes `extract -> search -> dedupe -> parallel analyze -> rerank -> reflect -> repeat -> finalize`, with minimum `3` rounds, maximum `5` rounds, duplicate-query/no-progress blockers, CTS anomaly handling, and explicit `AI_TIMEOUT` degrade behavior.
3. Keep the tool set minimal and product-aligned: one keyword-extraction step, one CTS search step, one resume-analysis step, and one reflection step; do not add generic browsing, memory, or unrelated external tools.
4. Make dedupe and ranking deterministic at the workflow boundary: only unseen resumes can enter analysis; each round keeps the strongest set and discards the weaker tail before the next round.
5. Integrate Langfuse so the run exposes user input, Chinese authored prompts, CTS tool spans, dedupe summaries, append-only round ledger, per-resume analysis generations, reflection summaries, stop nodes, and final answer, while deliberately avoiding hidden reasoning leakage.
6. Finalize the backend contract first, then hand it to the separate frontend rebuild track so `web-user` can be deleted and rebuilt against the stabilized API while `4202` is hard-wired to self-hosted Langfuse.
7. Add regression and stack-backed validation for timeout/degrade, duplicate search blocking, duplicate resume suppression, round progression, trace completeness, and final-top-5 output; then update the in-scope traceability rows with exact evidence.

## Acceptance Evidence

- Automated: `make codegen`, `make validate`, `make test-stack`, `make eval-critical`, targeted backend agent-flow tests under `tests/**`
- Manual:
  backend thread validates API and workflow behavior with deterministic stack-backed runs;
  frontend thread separately validates the rebuilt `web-user` surface against the finalized contract and confirms run review in the local Langfuse deployment.
- Traceability rows to update: `G1`, `G3`, `G4`, `G6`, `JD-01`, `KW-01`, `KW-05`, `KW-07`, `SR-01`, `SR-03`, `SR-04`, `SR-06`, `SR-07`, `LI-01`, `CD-01`, `CD-02`, `CD-03`, `CD-04`, `CD-06`, `EV-01`, `PRD AC-03`, `PRD-NFR-PERFORMANCE`, `PRD-NFR-RELIABILITY`, `PRD-NFR-TRACEABILITY`, `PRD-NFR-USABILITY`, `TDD AC-02`, `TDD AC-03`, `TDD-WF-SEARCH`, `TDD-WF-AI`, `TDD-WF-DELIVERY`, `TDD-IDEMPOTENCY-SEARCH-RUN`, `TDD-ARCH-AI-SCHEMA`, `TDD-ERR-DEGRADE`, `ADR-007`

Rules:

- `Repo Evidence` must be a locatable file path or symbol.
- `Validation Evidence` must be a test, a check command, or a concrete manual verification step.
- Do not mark `implemented` or `validated` without evidence.
- Backend completion in this conversation is allowed before frontend completion, but the close-out must clearly say which frontend work is intentionally left to the companion thread.

## Failure Standard

- The slice fails if the agent loop can repeat semantically identical search strategies or tool calls without a hard stop or forced strategy change.
- The slice fails if duplicate CTS resumes can re-enter analysis or ranking after they have already been seen.
- The slice fails if `AI_TIMEOUT`, CTS anomalies, or provider failure block the run instead of producing an explicit degrade path.
- The slice fails if prompt, CTS span, dedupe summary, reflection summary, and final answer traceability is missing from either the backend surface or Langfuse.
- The slice fails if the rebuilt frontend keeps or incrementally decorates the current screens instead of replacing them from scratch.

## Open Risks

- Risk: the request can sprawl into a generic agent platform and consume Slice 02, Slice 03, and Slice 05 wholesale.
- Mitigation: keep the scope pinned to one bounded shortlist workflow with one final output shape.

- Risk: dedupe, multi-round ranking, and reflection can create non-deterministic behavior that is hard to test.
- Mitigation: persist round state explicitly, make ranking inputs auditable, and keep deterministic harnesses authoritative.

- Risk: Langfuse integration can create local stack friction or tempt the implementation into leaking hidden reasoning.
- Mitigation: keep authored prompt and explicit summary tracing only, keep private model internals out of persisted outputs, and keep the local self-host bootstrap isolated inside Docker-managed services.

## Required Close-Out Format

- Validated:
- Not completed:
- Assumptions:
- Next step:
