from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from fastapi import APIRouter, Depends
from temporalio.client import Client
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.service import RPCError

from cvm_contracts_generated.platform_api import (
    CandidateDetailResponse,
    ConfirmConditionPlanResponse,
    CreateCaseResponse,
    CreateEvalRunResponse,
    CreateExportResponse,
    CreateJdVersionResponse,
    CreateKeywordDraftJobResponse,
    CreateSearchRunResponse,
    OpsSummaryResponse,
    SaveVerdictResponse,
    SearchRunPagesResponse,
    SearchRunStatusResponse,
    TemporalSearchRunDiagnosticResponse,
)
from cvm_platform.api.dependencies import service_dependency
from cvm_platform.api.request_models import (
    ConfirmConditionPlanRequestModel,
    CreateCaseRequestModel,
    CreateEvalRunRequestModel,
    CreateExportRequestModel,
    CreateJdVersionRequestModel,
    CreateKeywordDraftJobRequestModel,
    CreateSearchRunRequestModel,
    SaveVerdictRequestModel,
)
from cvm_platform.application.service import PlatformService
from cvm_platform.application.dto import CandidateDetailRecord, OpsSummaryRecord
from cvm_platform.domain.errors import TransientDependencyError, ValidationError
from cvm_platform.domain.types import (
    ConditionPlanDraftData,
    EvidenceRef as DraftEvidenceRef,
    StructuredFiltersPayload,
)
from cvm_platform.infrastructure.boundary_models import StructuredFiltersBoundaryModel
from cvm_platform.infrastructure.temporal_diagnostics import inspect_search_run
from cvm_platform.settings.config import settings
from pydantic import BaseModel, ValidationError as PydanticValidationError


router = APIRouter(prefix="/api/v1")


@router.post("/cases")
def create_case(request: CreateCaseRequestModel, service: PlatformService = Depends(service_dependency)) -> CreateCaseResponse:
    case = service.create_case(request.title, request.ownerTeamId)
    return CreateCaseResponse(caseId=case.id, status=case.status)


@router.post("/cases/{case_id}/jd-versions")
def create_jd_version(
    case_id: str,
    request: CreateJdVersionRequestModel,
    service: PlatformService = Depends(service_dependency),
) -> CreateJdVersionResponse:
    version = service.create_jd_version(case_id, request.rawText, request.source)
    return CreateJdVersionResponse(jdVersionId=version.id, versionNo=version.version_no, status="active")


@router.post("/cases/{case_id}/keyword-draft-jobs")
def create_keyword_draft_job(
    case_id: str,
    request: CreateKeywordDraftJobRequestModel,
    service: PlatformService = Depends(service_dependency),
) -> CreateKeywordDraftJobResponse:
    result = service.create_keyword_draft_job(case_id, request.jdVersionId, request.modelVersion, request.promptVersion)
    return CreateKeywordDraftJobResponse.model_validate(
        {
            "jobId": result.job.id,
            "status": result.job.status,
            "planId": result.plan.id,
            "draft": result.job.draft_payload,
        }
    )


@router.post("/condition-plans/{plan_id}:confirm")
def confirm_condition_plan(
    plan_id: str,
    request: ConfirmConditionPlanRequestModel,
    service: PlatformService = Depends(service_dependency),
) -> ConfirmConditionPlanResponse:
    payload = ConditionPlanDraftData(
        must_terms=list(request.mustTerms),
        should_terms=list(request.shouldTerms),
        exclude_terms=list(request.excludeTerms),
        structured_filters=_structured_filters_payload(request.structuredFilters),
        evidence_refs=[DraftEvidenceRef(label=ref.label, excerpt=ref.excerpt) for ref in request.evidenceRefs],
    )
    plan = service.confirm_condition_plan(plan_id, request.confirmedBy, payload)
    return ConfirmConditionPlanResponse.model_validate(
        {
            "planId": plan.id,
            "status": plan.status,
            "normalizedQuery": plan.normalized_query,
        }
    )


@router.post("/search-runs")
async def create_search_run(
    request: CreateSearchRunRequestModel,
    service: PlatformService = Depends(service_dependency),
) -> CreateSearchRunResponse:
    run = service.create_search_run(request.caseId, request.planId, request.pageBudget, request.idempotencyKey)
    workflow_id = run.workflow_id or f"search-run-{run.id}"
    try:
        client = await Client.connect(settings.temporal_host, namespace=settings.temporal_namespace)
        await client.start_workflow(
            "SearchRunWorkflow",
            run.id,
            id=workflow_id,
            task_queue=settings.temporal_task_queue,
        )
    except WorkflowAlreadyStartedError:
        pass
    except (RPCError, OSError, TimeoutError) as exc:
        service.fail_search_run_dispatch(
            run.id,
            "TEMPORAL_START_FAILED",
            "Temporal workflow dispatch failed.",
        )
        raise TransientDependencyError(
            "TEMPORAL_START_FAILED",
            "Temporal workflow dispatch failed.",
        ) from exc
    return CreateSearchRunResponse(runId=run.id, status=run.status)


@router.get("/search-runs/{run_id}")
def get_search_run(run_id: str, service: PlatformService = Depends(service_dependency)) -> SearchRunStatusResponse:
    run = service.get_search_run(run_id)
    progress = 0.0 if run.page_budget == 0 else run.pages_completed / run.page_budget
    return SearchRunStatusResponse(
        runId=run.id,
        status=run.status,
        progress=progress,
        pageCount=run.pages_completed,
        errorSummary=run.error_message,
    )


@router.get("/search-runs/{run_id}/pages")
def get_search_run_pages(
    run_id: str,
    pageNo: int | None = None,
    service: PlatformService = Depends(service_dependency),
) -> SearchRunPagesResponse:
    snapshots = service.get_search_pages(run_id, pageNo)
    return SearchRunPagesResponse.model_validate(
        {
            "runId": run_id,
            "snapshots": [
                {
                    "pageNo": snapshot.page_no,
                    "status": snapshot.status,
                    "fetchedAt": _isoformat_datetime(snapshot.fetched_at),
                    "candidates": snapshot.normalized_cards,
                    "total": snapshot.total,
                    "errorCode": snapshot.error_code,
                    "errorMessage": snapshot.error_message,
                }
                for snapshot in snapshots
            ],
        }
    )


@router.get("/case-candidates/{candidate_id}")
def get_case_candidate(candidate_id: str, service: PlatformService = Depends(service_dependency)) -> CandidateDetailResponse:
    detail = service.get_candidate_detail(candidate_id)
    return _candidate_detail_response(detail)


def _candidate_detail_response(detail: CandidateDetailRecord) -> CandidateDetailResponse:
    return CandidateDetailResponse.model_validate(
        {
            "candidate": {
                "candidateId": detail.candidate.id,
                "externalIdentityId": detail.candidate.external_identity_id,
                "name": detail.candidate.name,
                "title": detail.candidate.title,
                "company": detail.candidate.company,
                "location": detail.candidate.location,
                "summary": detail.candidate.summary,
            },
            "resumeView": {
                "snapshotId": detail.resume_snapshot.id,
                "projection": detail.resume_snapshot.payload,
            },
            "aiAnalysis": {
                "status": detail.ai_analysis.status if detail.ai_analysis else "pending",
                "summary": detail.ai_analysis.summary if detail.ai_analysis else "",
                "evidenceSpans": detail.ai_analysis.evidence_spans if detail.ai_analysis else [],
                "riskFlags": detail.ai_analysis.risk_flags if detail.ai_analysis else [],
            },
            "verdictHistory": [
                {
                    "verdict": item.verdict,
                    "reasons": item.reasons,
                    "notes": item.notes,
                    "actorId": item.actor_id,
                    "createdAt": _isoformat_datetime(item.created_at),
                }
                for item in detail.verdict_history
            ],
        }
    )


@router.put("/case-candidates/{candidate_id}/verdict")
def save_verdict(
    candidate_id: str,
    request: SaveVerdictRequestModel,
    service: PlatformService = Depends(service_dependency),
) -> SaveVerdictResponse:
    candidate = service.save_verdict(
        candidate_id=candidate_id,
        verdict=request.verdict,
        reasons=list(request.reasons),
        notes=request.notes,
        actor_id=request.actorId,
        resume_snapshot_id=request.resumeSnapshotId,
    )
    return SaveVerdictResponse.model_validate(
        {
            "candidateId": candidate.id,
            "latestVerdict": candidate.latest_verdict,
            "updatedAt": _isoformat_datetime(candidate.updated_at),
        }
    )


@router.post("/exports")
def create_export(
    request: CreateExportRequestModel,
    service: PlatformService = Depends(service_dependency),
) -> CreateExportResponse:
    export = service.create_export(request.caseId, request.maskPolicy, request.reason, request.idempotencyKey)
    return CreateExportResponse(exportJobId=export.id, status=export.status, filePath=export.file_path)


@router.get("/ops/summary")
def get_ops_summary(service: PlatformService = Depends(service_dependency)) -> OpsSummaryResponse:
    return _ops_summary_response(service.get_ops_summary())


def _ops_summary_response(summary: OpsSummaryRecord) -> OpsSummaryResponse:
    return OpsSummaryResponse.model_validate(
        {
            "queue": summary.queue,
            "failures": summary.failures,
            "latency": summary.latency,
            "version": {
                "api": summary.version.api,
                "apiBuildId": summary.version.api_build_id,
                "workerBuildId": summary.version.worker_build_id,
                "externalCts": summary.version.external_cts,
                "temporalNamespace": summary.version.temporal_namespace,
                "temporalUiUrl": summary.version.temporal_ui_url,
                "temporalVisibilityBackend": summary.version.temporal_visibility_backend,
            },
            "metrics": [{"name": metric.name, "value": metric.value} for metric in summary.metrics],
        }
    )


@router.get("/ops/temporal/search-runs/{run_id}")
async def get_search_run_temporal_diagnostic(
    run_id: str,
    service: PlatformService = Depends(service_dependency),
) -> TemporalSearchRunDiagnosticResponse:
    run = service.get_search_run(run_id)
    diagnostic = await inspect_search_run(run, settings)
    return TemporalSearchRunDiagnosticResponse.model_validate(diagnostic)


@router.post("/evals/runs")
def create_eval_run(
    request: CreateEvalRunRequestModel,
    service: PlatformService = Depends(service_dependency),
) -> CreateEvalRunResponse:
    eval_run = service.create_eval_run(request.suiteId, request.datasetId, request.targetVersion)
    return CreateEvalRunResponse(evalRunId=eval_run.id, status=eval_run.status)


def _structured_filters_payload(filters: object) -> StructuredFiltersPayload:
    raw_payload: dict[str, object] = {"page": 1, "pageSize": 10}
    if filters is None:
        return {"page": 1, "pageSize": 10}
    if isinstance(filters, BaseModel):
        raw_payload = cast(dict[str, object], filters.model_dump(exclude_none=True))
    elif isinstance(filters, dict):
        raw_payload = cast(dict[str, object], cast(object, filters))
    try:
        model = StructuredFiltersBoundaryModel.model_validate(raw_payload)
    except PydanticValidationError as exc:
        raise ValidationError(
            "INVALID_STRUCTURED_FILTERS",
            "structuredFilters did not match the validated schema.",
        ) from exc
    return cast(StructuredFiltersPayload, cast(object, model.model_dump(exclude_none=True)))


def _isoformat_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()
