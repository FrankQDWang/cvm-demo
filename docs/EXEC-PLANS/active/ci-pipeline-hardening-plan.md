# CI Pipeline Hardening Plan

Use this plan for the CI hardening slice that expands the repository from a single blocking workflow into a balanced PR gate, nightly regression gate, and runtime image verification path without changing product APIs or contracts.

## Goal

The repository exposes one clear blocking workflow for pull requests, one explicit nightly regression workflow for stack-backed eval and Temporal visibility checks, and one post-merge image build verification workflow. Shared CI setup is centralized so workflow drift is reduced, stack failures retain diagnostics, and local Make targets stay aligned with CI entrypoints.

## In-Scope Source IDs

- TDD: `ADR-008` partial target: codify the current self-hosted ARM64 runner policy across blocking, nightly, and build-verification workflows without introducing runner segmentation yet.
- TDD: `TDD-ERR-EVAL` partial target: add an explicit CI eval gate path that fails nightly regression when the blocking eval suite fails.
- TDD: `TDD-DAY0-GATES` partial target: strengthen the repo-local CI skeleton with shared setup, diagnostics capture, and documented workflow roles.
- TDD: `TDD-WEEK1-GATES` partial target: connect the existing blocking eval suite and runtime image verification to repo-local workflows and contributor-facing commands.

Rules:

- Only reference IDs that already exist in [Requirement Traceability](/Users/frankqdwang/Agents/cvm-demo/docs/PRODUCT/requirement-traceability.md).
- If a row is only partially addressed, keep it in scope and define the exact partial target.

## Explicitly Out of Scope

- TDD: `ADR-002`, `ADR-003`, `TDD-WF-AI`, `TDD-WF-DELIVERY`, `TDD-ARCH-CONTRACT-FIRST`
- TDD: full runner segmentation, ephemeral runner lifecycle automation, registry publish/signing, cloud deployment, and making nightly eval a PR required check

Rules:

- List nearby IDs that are easy to accidentally touch.
- If a dependency is intentionally deferred, name it here instead of hiding it in notes.

## Allowed Write Paths

- `.github/**`
- `tools/ci/**`
- `Makefile`
- `README.md`
- `docs/**`

## Forbidden Write Paths

- `docs/_generated/**`
- `contracts/**` unless the slice explicitly targets contract changes
- `libs/py/contracts-generated/**`
- `libs/ts/api-client-generated/**`
- Any path outside the allowed write set

## Preconditions and Dependencies

- Required repo state: existing `validate` workflow, `make validate`, `make test-stack`, `make eval-critical`, and `make temporal-visibility-smoke` already exist.
- Required contracts/docs: [Requirement Traceability](/Users/frankqdwang/Agents/cvm-demo/docs/PRODUCT/requirement-traceability.md), [Docs Index](/Users/frankqdwang/Agents/cvm-demo/docs/00-INDEX.md), and the existing governance plans remain the source of truth.
- Required local stack or external services: Docker must be available for stack-backed validation and runtime image verification; GitHub Actions uses the existing `self-hosted`, `Linux`, `ARM64`, `docker-cvm-demo` runner pool.
- Blocking unknowns: none; `main` is the default branch and remains the post-merge trigger for runtime image verification.

## Implementation Steps

1. Establish the current workflow baseline and identify duplicated setup, missing diagnostics capture, missing nightly eval gate, and missing runtime image verification entrypoint.
2. Add a shared composite action for CI environment setup and refactor the blocking `validate` workflow to use it with concurrency, explicit timeouts, and failure diagnostics for `test-stack`.
3. Add `nightly-regression.yml`, `build-verify.yml`, `make verify-images`, and the CI support scripts needed for compose diagnostics and explicit eval gate failure messaging.
4. Update contributor-facing docs and traceability rows so workflow intent, required checks, and validation evidence stay aligned.
5. Run the relevant automated checks and record the exact evidence for the close-out.

## Acceptance Evidence

- Automated: `make test`, `make verify-images`, `make test-stack`, `./tools/ci/run_eval_gate.sh`, `make temporal-visibility-smoke`
- Manual: inspect `.github/workflows/*.yml` to confirm `validate` remains the only PR-blocking workflow and `nightly-regression` / `build-verify` stay non-blocking by default
- Traceability rows to update: `ADR-008`, `TDD-ERR-EVAL`, `TDD-DAY0-GATES`, `TDD-WEEK1-GATES`

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

- Risk: stack-backed checks may leave containers or partial logs behind on a failed self-hosted run.
- Mitigation: always collect compose diagnostics before teardown and always run `docker compose down --remove-orphans`.

- Risk: nightly eval coverage can fail after merge without blocking PRs.
- Mitigation: keep `validate` lean for fast feedback and promote nightly checks to required status only after the new flows are stable.

## Close-Out

- Validated: `make test`; `uv run python` YAML parse for `.github/**/*.yml`; `./tools/ci/collect_compose_diagnostics.sh .artifacts/local-smoke`; `make verify-images`; stack-backed validation for `make test-stack`, `./tools/ci/run_eval_gate.sh`, and `make temporal-visibility-smoke`, with deterministic `mock + stub` injected by the test harness and CI workflow env rather than `.env`
- Not completed: runner segmentation, release publishing, and PR-blocking eval remain deferred by design.
- Assumptions: `main` is the default branch; Docker is available on the designated self-hosted runner pool; stack-backed CI jobs should stay deterministic and must not depend on live CTS or OpenAI responses.
- Next step: observe several successful nightly and main-branch runs, then decide whether `build-verify` or selected nightly checks should graduate into stricter gate status.
