from __future__ import annotations

from dataclasses import fields
from typing import Any, TypeVar, cast

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cvm_platform.application.dto import (
    AgentRunRecord,
    AuditLogRecord,
    CandidateRecord,
    CaseRecord,
    EvalRunRecord,
    ExportJobRecord,
    JDVersionRecord,
    ResumeAnalysisRecord,
    ResumeSnapshotRecord,
    VerdictHistoryRecord,
)
from cvm_platform.infrastructure.models import (
    AgentRunModel,
    AuditLogModel,
    CaseCandidateModel,
    EvalRunModel,
    ExportJobModel,
    JDCaseModel,
    JDVersionModel,
    ResumeAnalysisJobModel,
    ResumeSnapshotModel,
    VerdictHistoryModel,
)


RecordT = TypeVar("RecordT")
ModelT = TypeVar("ModelT")


def _record_values(record: object) -> dict[str, Any]:
    return {field.name: getattr(record, field.name) for field in fields(cast(Any, type(record)))}


def _to_record(record_type: type[RecordT], model: object) -> RecordT:
    values = {field.name: getattr(model, field.name) for field in fields(cast(Any, record_type))}
    return record_type(**values)


def _pending_model(session: Session, model_type: type[ModelT], record_id: object) -> ModelT | None:
    for pending in session.new:
        if isinstance(pending, model_type) and getattr(pending, "id", object()) == record_id:
            return pending
    return None


def _save_record(session: Session, model_type: type[ModelT], record: RecordT) -> RecordT:
    record_id = getattr(record, "id")
    model = _pending_model(session, model_type, record_id)
    if model is None:
        model = session.get(model_type, record_id)
    values = _record_values(record)
    if model is None:
        model = model_type(**values)
        session.add(model)
    else:
        for name, value in values.items():
            setattr(model, name, value)
    return record


class SqlAlchemyCasesRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, case_id: str) -> CaseRecord | None:
        model = self.session.get(JDCaseModel, case_id)
        return None if model is None else _to_record(CaseRecord, model)

    def save(self, case: CaseRecord) -> CaseRecord:
        return _save_record(self.session, JDCaseModel, case)


class SqlAlchemyPlansRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def count_versions_for_case(self, case_id: str) -> int:
        return int(
            self.session.scalar(select(func.count()).select_from(JDVersionModel).where(JDVersionModel.case_id == case_id))
            or 0
        )

    def deactivate_versions(self, case_id: str) -> None:
        self.session.query(JDVersionModel).filter(JDVersionModel.case_id == case_id).update({"is_active": False})

    def get_jd_version(self, case_id: str, jd_version_id: str) -> JDVersionRecord | None:
        model = self.session.scalar(
            select(JDVersionModel).where(JDVersionModel.id == jd_version_id, JDVersionModel.case_id == case_id)
        )
        return None if model is None else _to_record(JDVersionRecord, model)

    def save_jd_version(self, jd_version: JDVersionRecord) -> JDVersionRecord:
        return _save_record(self.session, JDVersionModel, jd_version)


class SqlAlchemyAgentRunsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_idempotency_key(self, idempotency_key: str) -> AgentRunRecord | None:
        model = self.session.scalar(select(AgentRunModel).where(AgentRunModel.idempotency_key == idempotency_key))
        return None if model is None else _to_record(AgentRunRecord, model)

    def get_run(self, run_id: str) -> AgentRunRecord | None:
        model = self.session.get(AgentRunModel, run_id)
        return None if model is None else _to_record(AgentRunRecord, model)

    def save_run(self, run: AgentRunRecord) -> AgentRunRecord:
        return _save_record(self.session, AgentRunModel, run)

    def list_runs(self) -> list[AgentRunRecord]:
        statement = select(AgentRunModel).order_by(AgentRunModel.created_at.desc())
        return [_to_record(AgentRunRecord, model) for model in self.session.scalars(statement)]

    def count_by_status(self) -> dict[str, int]:
        rows = self.session.execute(select(AgentRunModel.status, func.count()).group_by(AgentRunModel.status)).all()
        return {str(status): int(count) for status, count in rows}

    def count_failures_by_error_code(self) -> dict[str | None, int]:
        rows = self.session.execute(
            select(AgentRunModel.error_code, func.count()).group_by(AgentRunModel.error_code)
        ).all()
        return {error_code: int(count) for error_code, count in rows}

    def list_finished_runs(self) -> list[AgentRunRecord]:
        statement = select(AgentRunModel).where(AgentRunModel.finished_at.is_not(None))
        return [_to_record(AgentRunRecord, model) for model in self.session.scalars(statement)]


class SqlAlchemyCandidatesRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_case_and_external_identity(self, case_id: str, external_identity_id: str) -> CandidateRecord | None:
        model = self.session.scalar(
            select(CaseCandidateModel).where(
                CaseCandidateModel.case_id == case_id,
                CaseCandidateModel.external_identity_id == external_identity_id,
            )
        )
        return None if model is None else _to_record(CandidateRecord, model)

    def get_candidate(self, candidate_id: str) -> CandidateRecord | None:
        model = self.session.get(CaseCandidateModel, candidate_id)
        return None if model is None else _to_record(CandidateRecord, model)

    def save_candidate(self, candidate: CandidateRecord) -> CandidateRecord:
        return _save_record(self.session, CaseCandidateModel, candidate)

    def find_resume_snapshot_by_source_hash(self, candidate_id: str, source_hash: str) -> ResumeSnapshotRecord | None:
        model = self.session.scalar(
            select(ResumeSnapshotModel).where(
                ResumeSnapshotModel.case_candidate_id == candidate_id,
                ResumeSnapshotModel.source_hash == source_hash,
            )
        )
        return None if model is None else _to_record(ResumeSnapshotRecord, model)

    def get_resume_snapshot(self, snapshot_id: str) -> ResumeSnapshotRecord | None:
        model = self.session.get(ResumeSnapshotModel, snapshot_id)
        return None if model is None else _to_record(ResumeSnapshotRecord, model)

    def save_resume_snapshot(self, snapshot: ResumeSnapshotRecord) -> ResumeSnapshotRecord:
        return _save_record(self.session, ResumeSnapshotModel, snapshot)

    def get_latest_analysis(self, snapshot_id: str) -> ResumeAnalysisRecord | None:
        model = self.session.scalar(
            select(ResumeAnalysisJobModel)
            .where(ResumeAnalysisJobModel.resume_snapshot_id == snapshot_id)
            .order_by(ResumeAnalysisJobModel.created_at.desc())
        )
        return None if model is None else _to_record(ResumeAnalysisRecord, model)

    def save_resume_analysis(self, analysis: ResumeAnalysisRecord) -> ResumeAnalysisRecord:
        return _save_record(self.session, ResumeAnalysisJobModel, analysis)

    def list_verdict_history(self, candidate_id: str) -> list[VerdictHistoryRecord]:
        statement = (
            select(VerdictHistoryModel)
            .where(VerdictHistoryModel.case_candidate_id == candidate_id)
            .order_by(VerdictHistoryModel.created_at.desc())
        )
        return [_to_record(VerdictHistoryRecord, model) for model in self.session.scalars(statement)]

    def save_verdict_history(self, history: VerdictHistoryRecord) -> VerdictHistoryRecord:
        return _save_record(self.session, VerdictHistoryModel, history)

    def list_exportable_candidates(self, case_id: str) -> list[CandidateRecord]:
        statement = select(CaseCandidateModel).where(
            CaseCandidateModel.case_id == case_id,
            CaseCandidateModel.latest_verdict.in_(["Match", "Maybe"]),
        )
        return [_to_record(CandidateRecord, model) for model in self.session.scalars(statement)]

    def count_candidates(self) -> int:
        return int(self.session.scalar(select(func.count()).select_from(CaseCandidateModel)) or 0)


class SqlAlchemyExportsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_idempotency_key(self, idempotency_key: str) -> ExportJobRecord | None:
        model = self.session.scalar(select(ExportJobModel).where(ExportJobModel.idempotency_key == idempotency_key))
        return None if model is None else _to_record(ExportJobRecord, model)

    def save_export_job(self, export_job: ExportJobRecord) -> ExportJobRecord:
        return _save_record(self.session, ExportJobModel, export_job)


class SqlAlchemyEvalRunsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save_eval_run(self, eval_run: EvalRunRecord) -> EvalRunRecord:
        return _save_record(self.session, EvalRunModel, eval_run)


class SqlAlchemyAuditLogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save_audit_log(self, audit_log: AuditLogRecord) -> AuditLogRecord:
        return _save_record(self.session, AuditLogModel, audit_log)


class SqlAlchemyPlatformUnitOfWork:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.cases = SqlAlchemyCasesRepository(session)
        self.plans = SqlAlchemyPlansRepository(session)
        self.agent_runs = SqlAlchemyAgentRunsRepository(session)
        self.candidates = SqlAlchemyCandidatesRepository(session)
        self.exports = SqlAlchemyExportsRepository(session)
        self.eval_runs = SqlAlchemyEvalRunsRepository(session)
        self.audit_logs = SqlAlchemyAuditLogRepository(session)

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
