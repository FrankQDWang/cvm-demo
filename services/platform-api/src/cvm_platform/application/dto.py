from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class CaseRecord:
    id: str
    title: str
    owner_team_id: str
    status: str
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class JDVersionRecord:
    id: str
    case_id: str
    version_no: int
    raw_text: str
    source: str
    is_active: bool
    created_at: datetime


@dataclass(slots=True)
class KeywordDraftJobRecord:
    id: str
    case_id: str
    jd_version_id: str
    status: str
    model_version: str
    prompt_version: str
    draft_payload: dict[str, Any]
    created_at: datetime
    completed_at: datetime


@dataclass(slots=True)
class ConditionPlanRecord:
    id: str
    case_id: str
    jd_version_id: str
    status: str
    must_terms: list[str]
    should_terms: list[str]
    exclude_terms: list[str]
    structured_filters: dict[str, Any]
    evidence_refs: list[dict[str, str]]
    normalized_query: dict[str, Any]
    confirmed_by: str | None
    confirmed_at: datetime | None
    created_at: datetime


@dataclass(slots=True)
class SearchRunRecord:
    id: str
    case_id: str
    plan_id: str
    status: str
    page_budget: int
    pages_completed: int
    idempotency_key: str
    workflow_id: str | None
    temporal_namespace: str | None
    temporal_task_queue: str | None
    error_code: str | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None


@dataclass(slots=True)
class SearchRunPageRecord:
    id: str
    run_id: str
    page_no: int
    status: str
    upstream_request: dict[str, Any]
    upstream_response: dict[str, Any]
    normalized_cards: list[dict[str, Any]]
    total: int
    fetched_at: datetime
    error_code: str | None
    error_message: str | None


@dataclass(slots=True)
class CandidateRecord:
    id: str
    case_id: str
    external_identity_id: str
    latest_resume_snapshot_id: str | None
    latest_verdict: str | None
    dedupe_status: str
    name: str
    title: str
    company: str
    location: str
    summary: str
    email: str
    phone: str
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class ResumeSnapshotRecord:
    id: str
    case_candidate_id: str
    source_hash: str
    payload: dict[str, Any]
    created_at: datetime


@dataclass(slots=True)
class ResumeAnalysisRecord:
    id: str
    resume_snapshot_id: str
    model_version: str
    prompt_version: str
    summary: str
    evidence_spans: list[str]
    risk_flags: list[str]
    status: str
    created_at: datetime


@dataclass(slots=True)
class VerdictHistoryRecord:
    id: str
    case_candidate_id: str
    verdict: str
    reasons: list[str]
    notes: str | None
    actor_id: str
    resume_snapshot_id: str | None
    created_at: datetime


@dataclass(slots=True)
class ExportJobRecord:
    id: str
    case_id: str
    mask_policy: str
    reason: str
    status: str
    file_path: str | None
    idempotency_key: str
    created_at: datetime
    completed_at: datetime | None


@dataclass(slots=True)
class AuditLogRecord:
    id: str
    actor_id: str
    target_type: str
    target_id: str
    action: str
    result: str
    metadata_json: dict[str, Any]
    occurred_at: datetime


@dataclass(slots=True)
class EvalRunRecord:
    id: str
    suite_id: str
    dataset_id: str
    target_version: str
    baseline_version: str | None
    status: str
    summary_metrics: dict[str, Any]
    blocking_result: bool
    created_at: datetime


@dataclass(slots=True)
class MetricRecord:
    name: str
    value: float


@dataclass(slots=True)
class OpsVersionRecord:
    api: str
    api_build_id: str
    worker_build_id: str
    external_cts: str
    temporal_namespace: str
    temporal_ui_url: str
    temporal_visibility_backend: str


@dataclass(slots=True)
class OpsSummaryRecord:
    queue: dict[str, Any]
    failures: dict[str, Any]
    latency: dict[str, Any]
    version: OpsVersionRecord
    metrics: list[MetricRecord] = field(default_factory=list)


@dataclass(slots=True)
class CandidateDetailRecord:
    candidate: CandidateRecord
    resume_snapshot: ResumeSnapshotRecord
    ai_analysis: ResumeAnalysisRecord | None
    verdict_history: list[VerdictHistoryRecord]


@dataclass(slots=True)
class KeywordDraftJobResult:
    job: KeywordDraftJobRecord
    plan: ConditionPlanRecord
