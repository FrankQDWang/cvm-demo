# Runtime Mode Hardening Plan

## Summary

Lock the platform's default runtime to `live + cts` for all normal local and Docker-backed execution paths. Keep deterministic and mock modes available only behind an explicit test-only escape hatch so manual local work cannot silently drift onto fake infrastructure.

## Scope

- Align the authoritative settings default with the documented local-default behavior.
- Add a shared runtime-mode guard used by both API and worker startup.
- Permit non-live startup only when `CVM_ALLOW_NON_LIVE_RUNTIME=true`.
- Restrict the escape hatch to the single supported test combination: `deterministic + mock`.
- Wire the escape hatch into deterministic CI/local harness entrypoints only.
- Add unit coverage for allowed and rejected startup configurations.

## Acceptance

- `docker compose up` keeps `api/worker` on `live + cts` unless the operator explicitly opts into the escape hatch.
- `api/worker` startup fails fast for `deterministic`, `mock`, or mixed live/mock combinations without the escape hatch.
- Deterministic harnesses invoked by `make test`, `make test-stack`, and `make eval-critical` still work via the explicit escape hatch.
- Settings defaults, docs, and startup tests agree on the expected runtime contract.
