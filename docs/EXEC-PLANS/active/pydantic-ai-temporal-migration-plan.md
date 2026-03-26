# Pydantic-AI Temporal Migration Plan

Use this plan for the durable-execution migration that replaces the current custom `LLMPort + OpenAI adapter + single activity loop` with official `pydantic-ai + Temporal`, while preserving the business contract for `JD + 寻访偏好 -> final top 5 resumes with reasons`.

## Goal

The platform keeps the same recruiter-facing flow and API shape, but the agent loop runs as a true durable Temporal workflow that uses three dedicated `pydantic-ai` Temporal agents, explicit CTS activities, deterministic round state, append-only persisted steps, and post-run Langfuse trace publication. Legacy provider/mode LLM wiring, heuristic fallback completion, and the single-activity execution path are removed.

## In-Scope Source IDs

- PRD: `G1`, `G3`, `G4`, `G6`, `JD-01`, `KW-01`, `KW-05`, `KW-07`, `SR-01`, `SR-03`, `SR-04`, `SR-06`, `SR-07`, `LI-01`, `CD-01`, `CD-02`, `CD-03`, `CD-04`, `CD-06`, `EV-01`, `PRD AC-03`, `PRD-NFR-PERFORMANCE`, `PRD-NFR-RELIABILITY`, `PRD-NFR-TRACEABILITY`, `PRD-NFR-USABILITY`
- TDD: `TDD AC-02`, `TDD AC-03`, `TDD-WF-SEARCH`, `TDD-WF-AI`, `TDD-WF-DELIVERY`, `TDD-IDEMPOTENCY-SEARCH-RUN`, `TDD-ARCH-AI-SCHEMA`, `TDD-ERR-DEGRADE`, `ADR-007`

Rules:

- Keep the public HTTP contract stable even if internals change completely.
- Do not keep the old execution path in parallel. The migration only closes when legacy symbols and config are gone.

## Explicitly Out of Scope

- New end-user workflow steps or additional business input fields.
- Generic tool ecosystems, memory systems, or a multi-agent platform unrelated to CTS shortlist generation.
- New frontend intermediate-state pages beyond the existing start-and-final-result surface.

## Allowed Write Paths

- `services/platform-api/**`
- `services/temporal-worker/**`
- `tests/**`
- `docs/PRODUCT/**`
- `docs/EXEC-PLANS/**`
- `docker-compose.yml`
- `.env.example`
- `README.md`
- `tools/ci/**`
- `.github/**`

## Forbidden Write Paths

- `docs/_generated/**`
- `libs/py/contracts-generated/**` by hand
- `libs/ts/api-client-generated/**` by hand

## Confirmed Business Flow

1. The user provides exactly two raw inputs: `JD` and `寻访偏好`.
2. The system creates one bounded `AgentRun` with default `maxRounds=3`, `roundFetchSchedule=[10,5,5]`, and `finalTopK=5`.
3. `strategy-extractor` identifies the true hiring signal and produces the first CTS query.
4. Round 1 searches CTS for 10 resumes. Later rounds search 5 resumes each.
5. CTS duplicates are removed before they enter analysis or ranking.
6. `resume-matcher` analyzes only newly admitted resumes in parallel.
7. Each round keeps the strongest candidates, records append-only steps, and `search-reflector` decides the next query or a stop condition.
8. The workflow completes with exactly 5 shortlisted resumes plus one LLM reason per resume.
9. Langfuse shows a trace tree rooted at `agent-run`, with `extract-search-strategy`, one `round-N` subtree per round, and `finalize`.

## Implementation Steps

1. Replace runtime config and service boundaries so platform-api only manages run lifecycle and no longer owns LLM execution.
2. Introduce three dedicated `TemporalAgent` definitions in `services/temporal-worker`:
   - `strategy-extractor`
   - `resume-matcher`
   - `search-reflector`
3. Rebuild `AgentRunWorkflow` on `PydanticAIWorkflow` and run the full round loop inside workflow code with explicit CTS, persistence, and Langfuse activities.
4. Remove heuristic success fallbacks. Strategy, analysis, reflection, provider, schema, and CTS errors must fail the run after bounded Temporal retry.
5. Replace the legacy pre-migration agent env names and old provider/mode semantics with `CVM_AGENT_PROFILE`, `CVM_AGENT_MODEL`, and `CVM_AGENT_MODEL_TIMEOUT_SECONDS`, while keeping `OPENAI_API_KEY` and `OPENAI_BASE_URL`.
6. Migrate deterministic tests and CI to pre-registered fake `pydantic-ai` models instead of the legacy heuristic adapter path.
7. Rewrite repo docs, CI notes, and completed-plan language so the old architecture is not presented as current.

## Acceptance Evidence

- Automated: `make validate`, `make test`, `make test-stack`, `make eval-critical`, `make temporal-visibility-smoke`
- Temporal-specific: workflow replay coverage and time-skipping integration coverage for the new durable path
- Traceability rows to update: `G1`, `G3`, `G4`, `G6`, `JD-01`, `KW-01`, `KW-05`, `KW-07`, `SR-01`, `SR-03`, `SR-04`, `SR-06`, `SR-07`, `LI-01`, `CD-01`, `CD-02`, `CD-03`, `CD-04`, `CD-06`, `EV-01`, `PRD AC-03`, `PRD-NFR-PERFORMANCE`, `PRD-NFR-RELIABILITY`, `PRD-NFR-TRACEABILITY`, `PRD-NFR-USABILITY`, `TDD AC-02`, `TDD AC-03`, `TDD-WF-SEARCH`, `TDD-WF-AI`, `TDD-WF-DELIVERY`, `TDD-IDEMPOTENCY-SEARCH-RUN`, `TDD-ARCH-AI-SCHEMA`, `TDD-ERR-DEGRADE`, `ADR-007`

Rules:

- `Repo Evidence` must be a locatable file path or symbol.
- `Validation Evidence` must be a concrete test, gate command, or manual check.
- Do not mark `implemented` or `validated` without evidence.

## Failure Standard

- The migration fails if any production path still executes the agent loop through `service.execute_agent_run`.
- The migration fails if duplicate CTS resumes can re-enter ranking after first sighting.
- The migration fails if provider/schema errors still degrade into a completed shortlist.
- The migration fails if repo docs, CI scripts, or runtime config still present the legacy pre-migration agent env names or old provider/mode terminology as active architecture.

## Required Close-Out Format

- Validated:
- Not completed:
- Assumptions:
- Next step:
