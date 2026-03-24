# Context Map

## Runtime Units

- `apps/web-user`: User-facing recruiting workbench.
- `apps/web-ops`: Internal monitoring web.
- `apps/web-evals`: Internal evaluation web.
- `services/platform-api`: FastAPI API and orchestration boundary.
- `services/temporal-worker`: Long-running workflow execution.
- `postgres`: Source of record for business data and projections.
- `temporal`: Local workflow engine for recoverable background runs.

## Business Contexts

- `Case & JD`: `JDCase`, `JDVersion`, `KeywordDraftJob`, `ConditionPlan`
- `Search Orchestration`: `SearchRun`, `SearchRunPageSnapshot`
- `Candidate Review`: `CaseCandidate`, `ResumeSnapshot`, `ResumeAnalysis`, `VerdictHistory`
- `Export & Audit`: `ExportJob`, `AuditEvent`
- `Ops & Evals`: `OpsSummary`, `EvalRun`

## Boundary Rules

- Domain modules are pure Python and may not import FastAPI, SQLAlchemy, or Temporal SDK.
- External CTS behavior is normalized in infrastructure adapters.
- Boundary DTOs are generated from `contracts/openapi/platform-api.openapi.yaml`.
