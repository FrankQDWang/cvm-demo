from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from cvm_platform.domain.types import (
    AgentRunConfigPayload,
    AgentRuntimeConfigPayload,
    AgentRunStepPayload,
    AgentShortlistCandidatePayload,
    EvalSummaryMetricsPayload,
    JsonObject,
    ResumeProjectionPayload,
)

from .db import Base


class JDCaseModel(Base):
    __tablename__ = "jd_case"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    owner_team_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class JDVersionModel(Base):
    __tablename__ = "jd_version"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(64), index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    raw_text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AgentRunModel(Base):
    __tablename__ = "agent_run"
    __table_args__ = (UniqueConstraint("idempotency_key"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    jd_text: Mapped[str] = mapped_column(Text)
    sourcing_preference_text: Mapped[str] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    config: Mapped[AgentRunConfigPayload] = mapped_column(JSON)
    current_round: Mapped[int] = mapped_column(Integer, default=0)
    model_version: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(64))
    agent_runtime_config: Mapped[AgentRuntimeConfigPayload | None] = mapped_column(JSON, nullable=True)
    workflow_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    temporal_namespace: Mapped[str | None] = mapped_column(String(64), nullable=True)
    temporal_task_queue: Mapped[str | None] = mapped_column(String(128), nullable=True)
    langfuse_trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    langfuse_trace_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    steps: Mapped[list[AgentRunStepPayload]] = mapped_column(JSON)
    final_shortlist: Mapped[list[AgentShortlistCandidatePayload]] = mapped_column(JSON)
    seen_resume_ids: Mapped[list[str]] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CaseCandidateModel(Base):
    __tablename__ = "case_candidate"
    __table_args__ = (UniqueConstraint("case_id", "external_identity_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(64), index=True)
    external_identity_id: Mapped[str] = mapped_column(String(128))
    latest_resume_snapshot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latest_verdict: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dedupe_status: Mapped[str] = mapped_column(String(32), default="unique")
    name: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255))
    company: Mapped[str] = mapped_column(String(255))
    location: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ResumeSnapshotModel(Base):
    __tablename__ = "resume_snapshot"
    __table_args__ = (UniqueConstraint("case_candidate_id", "source_hash"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_candidate_id: Mapped[str] = mapped_column(String(64), index=True)
    source_hash: Mapped[str] = mapped_column(String(128))
    payload: Mapped[ResumeProjectionPayload] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ResumeAnalysisJobModel(Base):
    __tablename__ = "resume_analysis_job"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    resume_snapshot_id: Mapped[str] = mapped_column(String(64), index=True)
    model_version: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(64))
    summary: Mapped[str] = mapped_column(Text)
    evidence_spans: Mapped[list[str]] = mapped_column(JSON)
    risk_flags: Mapped[list[str]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class VerdictHistoryModel(Base):
    __tablename__ = "verdict_history"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_candidate_id: Mapped[str] = mapped_column(String(64), index=True)
    verdict: Mapped[str] = mapped_column(String(32))
    reasons: Mapped[list[str]] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[str] = mapped_column(String(64))
    resume_snapshot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ExportJobModel(Base):
    __tablename__ = "export_job"
    __table_args__ = (UniqueConstraint("idempotency_key"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(64), index=True)
    mask_policy: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32))
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLogModel(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str] = mapped_column(String(64), index=True)
    target_id: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(64))
    result: Mapped[str] = mapped_column(String(32))
    metadata_json: Mapped[JsonObject] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EvalRunModel(Base):
    __tablename__ = "eval_run"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    suite_id: Mapped[str] = mapped_column(String(64))
    dataset_id: Mapped[str] = mapped_column(String(64))
    target_version: Mapped[str] = mapped_column(String(64))
    baseline_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32))
    summary_metrics: Mapped[EvalSummaryMetricsPayload] = mapped_column(JSON)
    blocking_result: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
