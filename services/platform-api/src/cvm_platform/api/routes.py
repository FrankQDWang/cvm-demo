from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from temporalio.client import Client
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.service import RPCError

from cvm_contracts_generated.platform_api import (
    AgentRunListResponse,
    AgentRunResponse,
    CandidateDetailResponse,
    CreateAgentRunResponse,
    CreateCaseResponse,
    CreateEvalRunResponse,
    CreateExportResponse,
    CreateJdVersionResponse,
    OpsSummaryResponse,
    SaveVerdictResponse,
    TemporalAgentRunDiagnosticResponse,
)
from cvm_platform.api.dependencies import service_dependency
from cvm_platform.api.request_models import (
    CreateAgentRunRequestModel,
    CreateCaseRequestModel,
    CreateEvalRunRequestModel,
    CreateExportRequestModel,
    CreateJdVersionRequestModel,
    SaveVerdictRequestModel,
)
from cvm_platform.application.dto import AgentRunRecord, CandidateDetailRecord, OpsSummaryRecord
from cvm_platform.application.service import PlatformService
from cvm_platform.domain.errors import TransientDependencyError
from cvm_platform.infrastructure.temporal_diagnostics import inspect_agent_run
from cvm_platform.settings.config import settings


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


@router.post("/agent-runs")
async def create_agent_run(
    request: CreateAgentRunRequestModel,
    service: PlatformService = Depends(service_dependency),
) -> CreateAgentRunResponse:
    run = service.create_agent_run(
        jd_text=request.jdText,
        sourcing_preference_text=request.sourcingPreferenceText,
        config=None,
    )
    workflow_id = run.workflow_id or f"agent-run-{run.id}"
    try:
        client = await Client.connect(settings.temporal_host, namespace=settings.temporal_namespace)
        await client.start_workflow(
            "AgentRunWorkflow",
            run.id,
            id=workflow_id,
            task_queue=settings.temporal_task_queue,
        )
    except WorkflowAlreadyStartedError:
        pass
    except (RPCError, OSError, TimeoutError) as exc:
        service.fail_agent_run_dispatch(
            run.id,
            "TEMPORAL_START_FAILED",
            "Temporal workflow dispatch failed.",
        )
        raise TransientDependencyError(
            "TEMPORAL_START_FAILED",
            "Temporal workflow dispatch failed.",
        ) from exc
    return CreateAgentRunResponse(runId=run.id, status=run.status)


@router.get("/agent-runs")
def list_agent_runs(service: PlatformService = Depends(service_dependency)) -> AgentRunListResponse:
    runs = service.list_agent_runs()
    return AgentRunListResponse.model_validate(
        {
            "runs": [
                {
                    "runId": run.id,
                    "status": run.status,
                    "currentRound": run.current_round,
                    "createdAt": _isoformat_datetime(run.created_at),
                    "finishedAt": _isoformat_datetime(run.finished_at) if run.finished_at else None,
                    "errorCode": run.error_code,
                    "errorMessage": run.error_message,
                    "langfuseTraceUrl": run.langfuse_trace_url,
                }
                for run in runs
            ]
        }
    )


@router.get("/agent-runs/{run_id}")
def get_agent_run(run_id: str, service: PlatformService = Depends(service_dependency)) -> AgentRunResponse:
    return _agent_run_response(service.get_agent_run(run_id))


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


def _agent_run_response(run: AgentRunRecord) -> AgentRunResponse:
    return AgentRunResponse.model_validate(
        {
            "runId": run.id,
            "status": run.status,
            "jdText": run.jd_text,
            "sourcingPreferenceText": run.sourcing_preference_text,
            "config": run.config,
            "currentRound": run.current_round,
            "modelVersion": run.model_version,
            "promptVersion": run.prompt_version,
            "workflowId": run.workflow_id,
            "temporalNamespace": run.temporal_namespace,
            "temporalTaskQueue": run.temporal_task_queue,
            "langfuseTraceId": run.langfuse_trace_id,
            "langfuseTraceUrl": run.langfuse_trace_url,
            "steps": [
                {
                    "stepNo": step["stepNo"],
                    "roundNo": step["roundNo"],
                    "stepType": step["stepType"],
                    "title": step["title"],
                    "status": step["status"],
                    "summary": step["summary"],
                    "payload": step["payload"],
                    "occurredAt": step["occurredAt"],
                }
                for step in run.steps
            ],
            "finalShortlist": run.final_shortlist,
            "seenResumeIds": run.seen_resume_ids,
            "errorCode": run.error_code,
            "errorMessage": run.error_message,
            "createdAt": _isoformat_datetime(run.created_at),
            "startedAt": _isoformat_datetime(run.started_at),
            "finishedAt": _isoformat_datetime(run.finished_at) if run.finished_at else None,
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


@router.get("/ops/temporal/agent-runs/{run_id}")
async def get_agent_run_temporal_diagnostic(
    run_id: str,
    service: PlatformService = Depends(service_dependency),
) -> TemporalAgentRunDiagnosticResponse:
    run = service.get_agent_run(run_id)
    diagnostic = await inspect_agent_run(run, settings)
    return TemporalAgentRunDiagnosticResponse.model_validate(diagnostic)


@router.post("/evals/runs")
def create_eval_run(
    request: CreateEvalRunRequestModel,
    service: PlatformService = Depends(service_dependency),
) -> CreateEvalRunResponse:
    eval_run = service.create_eval_run(request.suiteId, request.datasetId, request.targetVersion)
    return CreateEvalRunResponse(evalRunId=eval_run.id, status=eval_run.status)


def _isoformat_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()
