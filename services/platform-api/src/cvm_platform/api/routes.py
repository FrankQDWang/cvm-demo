from __future__ import annotations

from fastapi import APIRouter, Depends
from temporalio.client import Client

from cvm_contracts_generated.platform_api import (
    CandidateDetailResponse,
    ConfirmConditionPlanRequest,
    ConfirmConditionPlanResponse,
    CreateCaseRequest,
    CreateCaseResponse,
    CreateEvalRunRequest,
    CreateEvalRunResponse,
    CreateExportRequest,
    CreateExportResponse,
    CreateJdVersionRequest,
    CreateJdVersionResponse,
    CreateKeywordDraftJobRequest,
    CreateKeywordDraftJobResponse,
    CreateSearchRunRequest,
    CreateSearchRunResponse,
    EvidenceRef,
    OpsSummaryResponse,
    ResumeAnalysis,
    ResumeSnapshot,
    SaveVerdictRequest,
    SaveVerdictResponse,
    SearchRunPagesResponse,
    SearchRunStatusResponse,
    VerdictRecord,
)
from cvm_platform.api.dependencies import service_dependency
from cvm_platform.application.service import PlatformService
from cvm_platform.domain.types import ConditionPlanDraftData, EvidenceRef as DraftEvidenceRef
from cvm_platform.settings.config import settings


router = APIRouter(prefix="/api/v1")


@router.post("/cases")
def create_case(request: CreateCaseRequest, service: PlatformService = Depends(service_dependency)) -> CreateCaseResponse:
    case = service.create_case(request.title, request.ownerTeamId)
    return CreateCaseResponse(caseId=case.id, status=case.status)


@router.post("/cases/{case_id}/jd-versions")
def create_jd_version(
    case_id: str,
    request: CreateJdVersionRequest,
    service: PlatformService = Depends(service_dependency),
) -> CreateJdVersionResponse:
    version = service.create_jd_version(case_id, request.rawText, request.source)
    return CreateJdVersionResponse(jdVersionId=version.id, versionNo=version.version_no, status="active")


@router.post("/cases/{case_id}/keyword-draft-jobs")
def create_keyword_draft_job(
    case_id: str,
    request: CreateKeywordDraftJobRequest,
    service: PlatformService = Depends(service_dependency),
) -> CreateKeywordDraftJobResponse:
    job, plan = service.create_keyword_draft_job(case_id, request.jdVersionId, request.modelVersion, request.promptVersion)
    return CreateKeywordDraftJobResponse(jobId=job.id, status=job.status, planId=plan.id, draft=job.draft_payload)


@router.post("/condition-plans/{plan_id}:confirm")
def confirm_condition_plan(
    plan_id: str,
    request: ConfirmConditionPlanRequest,
    service: PlatformService = Depends(service_dependency),
) -> ConfirmConditionPlanResponse:
    payload = ConditionPlanDraftData(
        must_terms=list(request.mustTerms),
        should_terms=list(request.shouldTerms),
        exclude_terms=list(request.excludeTerms),
        structured_filters=dict(request.structuredFilters or {}),
        evidence_refs=[DraftEvidenceRef(label=ref.label, excerpt=ref.excerpt) for ref in request.evidenceRefs],
    )
    plan = service.confirm_condition_plan(plan_id, request.confirmedBy, payload)
    return ConfirmConditionPlanResponse(planId=plan.id, status=plan.status, normalizedQuery=plan.normalized_query)


@router.post("/search-runs")
async def create_search_run(
    request: CreateSearchRunRequest,
    service: PlatformService = Depends(service_dependency),
) -> CreateSearchRunResponse:
    run = service.create_search_run(request.caseId, request.planId, request.pageBudget, request.idempotencyKey)
    if settings.use_temporal:
        client = await Client.connect(settings.temporal_host)
        await client.start_workflow(
            "SearchRunWorkflow",
            run.id,
            id=f"search-run-{run.id}",
            task_queue=settings.temporal_task_queue,
        )
        return CreateSearchRunResponse(runId=run.id, status=run.status)
    executed = service.execute_search_run(run.id)
    return CreateSearchRunResponse(runId=executed.id, status=executed.status)


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
    return SearchRunPagesResponse(
        runId=run_id,
        snapshots=[
            {
                "pageNo": snapshot.page_no,
                "status": snapshot.status,
                "fetchedAt": snapshot.fetched_at.isoformat(),
                "candidates": snapshot.normalized_cards,
                "total": snapshot.total,
                "errorCode": snapshot.error_code,
                "errorMessage": snapshot.error_message,
            }
            for snapshot in snapshots
        ],
    )


@router.get("/case-candidates/{candidate_id}")
def get_case_candidate(candidate_id: str, service: PlatformService = Depends(service_dependency)) -> CandidateDetailResponse:
    candidate, snapshot, analysis, history = service.get_candidate_detail(candidate_id)
    return CandidateDetailResponse(
        candidate={
            "candidateId": candidate.id,
            "externalIdentityId": candidate.external_identity_id,
            "name": candidate.name,
            "title": candidate.title,
            "company": candidate.company,
            "location": candidate.location,
            "summary": candidate.summary,
        },
        resumeSnapshot=ResumeSnapshot(id=snapshot.id, content=snapshot.payload),
        aiAnalysis=ResumeAnalysis(
            status=analysis.status if analysis else "pending",
            summary=analysis.summary if analysis else "",
            evidenceSpans=analysis.evidence_spans if analysis else [],
            riskFlags=analysis.risk_flags if analysis else [],
        ),
        verdictHistory=[
            VerdictRecord(
                verdict=item.verdict,
                reasons=item.reasons,
                notes=item.notes,
                actorId=item.actor_id,
                createdAt=item.created_at.isoformat(),
            )
            for item in history
        ],
    )


@router.put("/case-candidates/{candidate_id}/verdict")
def save_verdict(
    candidate_id: str,
    request: SaveVerdictRequest,
    service: PlatformService = Depends(service_dependency),
) -> SaveVerdictResponse:
    candidate = service.save_verdict(
        candidate_id=candidate_id,
        verdict=request.verdict.value if hasattr(request.verdict, "value") else str(request.verdict),
        reasons=list(request.reasons),
        notes=request.notes,
        actor_id=request.actorId,
        resume_snapshot_id=request.resumeSnapshotId,
    )
    return SaveVerdictResponse(
        candidateId=candidate.id,
        latestVerdict=candidate.latest_verdict,
        updatedAt=candidate.updated_at.isoformat(),
    )


@router.post("/exports")
def create_export(
    request: CreateExportRequest,
    service: PlatformService = Depends(service_dependency),
) -> CreateExportResponse:
    export = service.create_export(request.caseId, request.maskPolicy.value if hasattr(request.maskPolicy, "value") else str(request.maskPolicy), request.reason, request.idempotencyKey)
    return CreateExportResponse(exportJobId=export.id, status=export.status, filePath=export.file_path)


@router.get("/ops/summary")
def get_ops_summary(service: PlatformService = Depends(service_dependency)) -> OpsSummaryResponse:
    return OpsSummaryResponse.model_validate(service.get_ops_summary())


@router.post("/evals/runs")
def create_eval_run(
    request: CreateEvalRunRequest,
    service: PlatformService = Depends(service_dependency),
) -> CreateEvalRunResponse:
    eval_run = service.create_eval_run(request.suiteId, request.datasetId, request.targetVersion)
    return CreateEvalRunResponse(evalRunId=eval_run.id, status=eval_run.status)
