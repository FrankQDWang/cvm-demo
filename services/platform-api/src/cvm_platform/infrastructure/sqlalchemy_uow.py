from __future__ import annotations

from dataclasses import fields
from typing import TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cvm_platform.application.dto import (
    AuditLogRecord,
    CandidateRecord,
    CaseRecord,
    ConditionPlanRecord,
    EvalRunRecord,
    ExportJobRecord,
    JDVersionRecord,
    KeywordDraftJobRecord,
    ResumeAnalysisRecord,
    ResumeSnapshotRecord,
    SearchRunPageRecord,
    SearchRunRecord,
    VerdictHistoryRecord,
)
from cvm_platform.infrastructure.models import (
    AuditLogModel,
    CaseCandidateModel,
    ConditionPlanModel,
    EvalRunModel,
    ExportJobModel,
    JDCaseModel,
    JDVersionModel,
    KeywordDraftJobModel,
    ResumeAnalysisJobModel,
    ResumeSnapshotModel,
    SearchRunModel,
    SearchRunPageModel,
    VerdictHistoryModel,
)


RecordT = TypeVar("RecordT")
ModelT = TypeVar("ModelT")


def _record_values(record: RecordT) -> dict[str, object]:
    return {field.name: getattr(record, field.name) for field in fields(type(record))}


def _to_record(record_type: type[RecordT], model: object) -> RecordT:
    return record_type(**{field.name: getattr(model, field.name) for field in fields(record_type)})


def _save_record(session: Session, model_type: type[ModelT], record: RecordT) -> RecordT:
    model = session.get(model_type, getattr(record, "id"))
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

    def save_keyword_draft_job(self, job: KeywordDraftJobRecord) -> KeywordDraftJobRecord:
        return _save_record(self.session, KeywordDraftJobModel, job)

    def get_plan(self, plan_id: str) -> ConditionPlanRecord | None:
        model = self.session.get(ConditionPlanModel, plan_id)
        return None if model is None else _to_record(ConditionPlanRecord, model)

    def save_plan(self, plan: ConditionPlanRecord) -> ConditionPlanRecord:
        return _save_record(self.session, ConditionPlanModel, plan)


class SqlAlchemySearchRunsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_idempotency_key(self, idempotency_key: str) -> SearchRunRecord | None:
        model = self.session.scalar(select(SearchRunModel).where(SearchRunModel.idempotency_key == idempotency_key))
        return None if model is None else _to_record(SearchRunRecord, model)

    def get_run(self, run_id: str) -> SearchRunRecord | None:
        model = self.session.get(SearchRunModel, run_id)
        return None if model is None else _to_record(SearchRunRecord, model)

    def save_run(self, run: SearchRunRecord) -> SearchRunRecord:
        return _save_record(self.session, SearchRunModel, run)

    def list_pages(self, run_id: str, page_no: int | None = None) -> list[SearchRunPageRecord]:
        statement = select(SearchRunPageModel).where(SearchRunPageModel.run_id == run_id).order_by(SearchRunPageModel.page_no)
        if page_no is not None:
            statement = statement.where(SearchRunPageModel.page_no == page_no)
        return [_to_record(SearchRunPageRecord, model) for model in self.session.scalars(statement)]

    def save_page(self, page: SearchRunPageRecord) -> SearchRunPageRecord:
        return _save_record(self.session, SearchRunPageModel, page)

    def count_by_status(self) -> dict[str, int]:
        rows = self.session.execute(select(SearchRunModel.status, func.count()).group_by(SearchRunModel.status)).all()
        return {str(status): int(count) for status, count in rows}

    def count_failures_by_error_code(self) -> dict[str | None, int]:
        rows = self.session.execute(
            select(SearchRunModel.error_code, func.count()).group_by(SearchRunModel.error_code)
        ).all()
        return {error_code: int(count) for error_code, count in rows}

    def list_finished_runs(self) -> list[SearchRunRecord]:
        statement = select(SearchRunModel).where(SearchRunModel.finished_at.is_not(None))
        return [_to_record(SearchRunRecord, model) for model in self.session.scalars(statement)]


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
        self.search_runs = SqlAlchemySearchRunsRepository(session)
        self.candidates = SqlAlchemyCandidatesRepository(session)
        self.exports = SqlAlchemyExportsRepository(session)
        self.eval_runs = SqlAlchemyEvalRunsRepository(session)
        self.audit_logs = SqlAlchemyAuditLogRepository(session)

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
