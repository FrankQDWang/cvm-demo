# Langfuse Full-Fidelity Trace Plan

Use this plan for the observability hardening work that upgrades the current end-of-run Langfuse replay from summary-only traces to full-fidelity post-run traces without breaking Temporal determinism or changing public API contracts.

## Goal

The platform keeps the current authoritative post-run trace publication model, but the final Langfuse trace now includes complete root input/output, round and step hierarchy, non-null generation and tool inputs/outputs, prompt-version linkage for the three internal prompts, per-call usage details, and persisted observability warnings when trace publication fails. Business run status must remain independent from Langfuse availability.

## In-Scope Source IDs

- PRD: `G6`, `EV-01`, `PRD-NFR-RELIABILITY`, `PRD-NFR-TRACEABILITY`
- TDD: `TDD-WF-AI`, `TDD-WF-DELIVERY`, `TDD-ERR-DEGRADE`, `ADR-007`

Rules:

- Keep the public HTTP and generated contract surfaces unchanged.
- Preserve the existing post-run replay architecture as the authoritative publication path.

## Explicitly Out of Scope

- Switching runtime prompt resolution to Langfuse Prompt Management
- Live in-progress trace completeness before workflow completion
- Redaction or masking changes for trace payloads in this phase
- Frontend/UI changes outside of existing run diagnostics surfaces

## Allowed Write Paths

- `services/platform-api/**`
- `services/temporal-worker/**`
- `tests/**`
- `docs/EXEC-PLANS/**`

## Forbidden Write Paths

- `docs/_generated/**`
- `libs/py/contracts-generated/**` by hand
- `libs/ts/api-client-generated/**` by hand

## Implementation Steps

1. Add canonical persisted trace-fact models for generation, tool, and span observations and carry them inside existing step payloads and per-candidate analysis items.
2. Persist rich execution facts for strategy extraction, search, resume analysis, reflection, shortlist progression, finalize, and stop decisions, including compiled prompt text, raw message history, structured output, model metadata, and usage.
3. Extend the tracing adapter so replayed generation observations can send prompt links, usage details, and optional cost details to Langfuse.
4. Integrate Langfuse Prompt Management linkage for `cvm.strategy-extractor`, `cvm.resume-matcher`, and `cvm.search-reflector`, using `run.promptVersion` as the prompt label selector while keeping code prompt builders authoritative.
5. Keep trace publication strictly non-blocking by persisting observability warnings when Langfuse export fails and preserving the original business run outcome.
6. Add focused regression coverage for persisted trace facts, replayed prompt/usage fields, and successful-run behavior when trace publication fails.

## Acceptance Evidence

- Automated: `uv run pytest tests/unit/test_application_agent_tracing.py tests/unit/test_agent_tracing.py tests/unit/test_agent_runs.py tests/unit/test_temporal_worker.py`
- Manual: one local workflow run against Langfuse with exported trace JSON showing non-null generation/tool inputs and outputs plus prompt linkage

Rules:

- `Repo Evidence` must point to concrete symbols or file paths.
- Do not claim completion without both persistence-path and replay-path test coverage.

## Failure Standard

- The work fails if Langfuse export can still flip a completed business run into `failed`.
- The work fails if replayed generation observations still lack input/output or prompt linkage.
- The work fails if CTS tool observations still omit upstream request/response data.
- The work fails if the implementation introduces live trace writes inside deterministic workflow code.

## Required Close-Out Format

- Validated:
- Not completed:
- Assumptions:
- Next step:
