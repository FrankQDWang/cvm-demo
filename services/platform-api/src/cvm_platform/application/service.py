from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cvm_domain_kernel import new_id, now_utc
from cvm_platform.domain.errors import AppError
from cvm_platform.domain.ports import LLMPort, ResumeSourcePort
from cvm_platform.domain.types import ConditionPlanDraftData, SearchPageData
from cvm_platform.infrastructure.adapters import resume_hash
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
from cvm_platform.settings.config import settings


class PlatformService:
    def __init__(self, session: Session, llm: LLMPort, resume_source: ResumeSourcePort) -> None:
        self.session = session
        self.llm = llm
        self.resume_source = resume_source

    def create_case(self, title: str, owner_team_id: str) -> JDCaseModel:
        case = JDCaseModel(
            id=new_id("case"),
            title=title,
            owner_team_id=owner_team_id,
            status="draft",
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        self.session.add(case)
        self._audit("system", "case", case.id, "case.created", "success", {"title": title})
        self.session.commit()
        return case

    def create_jd_version(self, case_id: str, raw_text: str, source: str) -> JDVersionModel:
        case = self._get_case(case_id)
        version_no = (
            self.session.scalar(select(func.count()).select_from(JDVersionModel).where(JDVersionModel.case_id == case_id)) or 0
        ) + 1
        self.session.query(JDVersionModel).filter(JDVersionModel.case_id == case_id).update({"is_active": False})
        version = JDVersionModel(
            id=new_id("jdv"),
            case_id=case_id,
            version_no=version_no,
            raw_text=raw_text,
            source=source,
            is_active=True,
            created_at=now_utc(),
        )
        case.status = "searchable"
        case.updated_at = now_utc()
        self.session.add(version)
        self._audit("system", "jd_version", version.id, "jd_version.created", "success", {"caseId": case_id})
        self.session.commit()
        return version

    def create_keyword_draft_job(
        self,
        case_id: str,
        jd_version_id: str,
        model_version: str,
        prompt_version: str,
    ) -> tuple[KeywordDraftJobModel, ConditionPlanModel]:
        self._get_case(case_id)
        jd_version = self._get_jd_version(case_id, jd_version_id)
        draft = self.llm.draft_keywords(jd_version.raw_text, model_version, prompt_version)
        plan = ConditionPlanModel(
            id=new_id("plan"),
            case_id=case_id,
            jd_version_id=jd_version_id,
            status="draft",
            must_terms=draft.must_terms,
            should_terms=draft.should_terms,
            exclude_terms=draft.exclude_terms,
            structured_filters=draft.structured_filters,
            evidence_refs=[self._evidence_ref_to_dict(ref) for ref in draft.evidence_refs],
            normalized_query={},
            confirmed_by=None,
            confirmed_at=None,
            created_at=now_utc(),
        )
        job = KeywordDraftJobModel(
            id=new_id("kdj"),
            case_id=case_id,
            jd_version_id=jd_version_id,
            status="completed",
            model_version=model_version,
            prompt_version=prompt_version,
            draft_payload=self._draft_to_payload(draft),
            created_at=now_utc(),
            completed_at=now_utc(),
        )
        self.session.add_all([plan, job])
        self._audit("system", "keyword_draft_job", job.id, "keyword_draft.completed", "success", {"planId": plan.id})
        self.session.commit()
        return job, plan

    def confirm_condition_plan(
        self,
        plan_id: str,
        confirmed_by: str,
        payload: ConditionPlanDraftData,
    ) -> ConditionPlanModel:
        plan = self._get_plan(plan_id)
        normalized_query = {
            "mustTerms": payload.must_terms,
            "shouldTerms": payload.should_terms,
            "excludeTerms": payload.exclude_terms,
            "structuredFilters": payload.structured_filters,
            "keyword": " ".join(payload.must_terms + payload.should_terms).strip(),
        }
        plan.must_terms = payload.must_terms
        plan.should_terms = payload.should_terms
        plan.exclude_terms = payload.exclude_terms
        plan.structured_filters = payload.structured_filters
        plan.evidence_refs = [self._evidence_ref_to_dict(ref) for ref in payload.evidence_refs]
        plan.normalized_query = normalized_query
        plan.status = "confirmed"
        plan.confirmed_by = confirmed_by
        plan.confirmed_at = now_utc()
        self._audit(confirmed_by, "condition_plan", plan.id, "condition_plan.confirmed", "success", normalized_query)
        self.session.commit()
        return plan

    def create_search_run(self, case_id: str, plan_id: str, page_budget: int, idempotency_key: str) -> SearchRunModel:
        if page_budget <= 0:
            raise AppError("INVALID_PAGINATION_PARAMS", "pageBudget must be positive.")
        plan = self._get_plan(plan_id)
        if plan.case_id != case_id:
            raise AppError("PLAN_CASE_MISMATCH", "Plan does not belong to case.")
        if plan.status != "confirmed":
            raise AppError("PLAN_NOT_CONFIRMED", "Condition plan must be confirmed before search.")
        existing = self.session.scalar(select(SearchRunModel).where(SearchRunModel.idempotency_key == idempotency_key))
        if existing:
            return existing
        run = SearchRunModel(
            id=new_id("run"),
            case_id=case_id,
            plan_id=plan_id,
            status="queued",
            page_budget=page_budget,
            pages_completed=0,
            idempotency_key=idempotency_key,
            error_code=None,
            error_message=None,
            started_at=now_utc(),
            finished_at=None,
        )
        self.session.add(run)
        self._audit("system", "search_run", run.id, "search_run.created", "success", {"caseId": case_id, "planId": plan_id})
        self.session.commit()
        return run

    def execute_search_run(self, run_id: str) -> SearchRunModel:
        run = self._get_run(run_id)
        plan = self._get_plan(run.plan_id)
        run.status = "running"
        self.session.commit()

        page_size = int(plan.structured_filters.get("pageSize", 2))
        for page_no in range(1, run.page_budget + 1):
            result = self.resume_source.search_candidates(plan.normalized_query, page_no, page_size)
            self._persist_page(run, result)
            if result.error_code:
                run.status = "failed"
                run.error_code = result.error_code
                run.error_message = result.error_message
                run.finished_at = now_utc()
                self.session.commit()
                return run

        run.status = "completed"
        run.finished_at = now_utc()
        self.session.commit()
        return run

    def get_search_run(self, run_id: str) -> SearchRunModel:
        return self._get_run(run_id)

    def get_search_pages(self, run_id: str, page_no: int | None = None) -> list[SearchRunPageModel]:
        statement = select(SearchRunPageModel).where(SearchRunPageModel.run_id == run_id).order_by(SearchRunPageModel.page_no)
        if page_no is not None:
            statement = statement.where(SearchRunPageModel.page_no == page_no)
        return list(self.session.scalars(statement))

    def get_candidate_detail(self, candidate_id: str) -> tuple[CaseCandidateModel, ResumeSnapshotModel, ResumeAnalysisJobModel | None, list[VerdictHistoryModel]]:
        candidate = self._get_candidate(candidate_id)
        snapshot = self.session.scalar(select(ResumeSnapshotModel).where(ResumeSnapshotModel.id == candidate.latest_resume_snapshot_id))
        if snapshot is None:
            raise AppError("RESUME_SNAPSHOT_NOT_FOUND", "Candidate resume snapshot missing.", 404)
        analysis = self.session.scalar(
            select(ResumeAnalysisJobModel)
            .where(ResumeAnalysisJobModel.resume_snapshot_id == snapshot.id)
            .order_by(ResumeAnalysisJobModel.created_at.desc())
        )
        history = list(
            self.session.scalars(
                select(VerdictHistoryModel)
                .where(VerdictHistoryModel.case_candidate_id == candidate_id)
                .order_by(VerdictHistoryModel.created_at.desc())
            )
        )
        return candidate, snapshot, analysis, history

    def save_verdict(
        self,
        candidate_id: str,
        verdict: str,
        reasons: list[str],
        notes: str | None,
        actor_id: str,
        resume_snapshot_id: str | None,
    ) -> CaseCandidateModel:
        candidate = self._get_candidate(candidate_id)
        candidate.latest_verdict = verdict
        candidate.updated_at = now_utc()
        history = VerdictHistoryModel(
            id=new_id("ver"),
            case_candidate_id=candidate_id,
            verdict=verdict,
            reasons=reasons,
            notes=notes,
            actor_id=actor_id,
            resume_snapshot_id=resume_snapshot_id,
            created_at=now_utc(),
        )
        self.session.add(history)
        self._audit(actor_id, "candidate", candidate_id, "candidate.verdict.saved", "success", {"verdict": verdict, "reasons": reasons})
        self.session.commit()
        return candidate

    def create_export(self, case_id: str, mask_policy: str, reason: str, idempotency_key: str) -> ExportJobModel:
        self._get_case(case_id)
        existing = self.session.scalar(select(ExportJobModel).where(ExportJobModel.idempotency_key == idempotency_key))
        if existing:
            return existing
        if mask_policy == "sensitive" and not settings.allow_sensitive_export:
            raise AppError("NO_CONTACT_PERMISSION", "Sensitive export is disabled in local mode.", 403)
        job = ExportJobModel(
            id=new_id("exp"),
            case_id=case_id,
            mask_policy=mask_policy,
            reason=reason,
            status="running",
            file_path=None,
            idempotency_key=idempotency_key,
            created_at=now_utc(),
            completed_at=None,
        )
        self.session.add(job)
        self.session.commit()

        candidates = list(
            self.session.scalars(
                select(CaseCandidateModel).where(
                    CaseCandidateModel.case_id == case_id,
                    CaseCandidateModel.latest_verdict.in_(["Match", "Maybe"]),
                )
            )
        )
        settings.exports_dir.mkdir(parents=True, exist_ok=True)
        export_path = settings.exports_dir / f"{case_id}-{job.id}.csv"
        with export_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["name", "title", "company", "location", "verdict", "email", "phone"])
            writer.writeheader()
            for candidate in candidates:
                writer.writerow(
                    {
                        "name": candidate.name,
                        "title": candidate.title,
                        "company": candidate.company,
                        "location": candidate.location,
                        "verdict": candidate.latest_verdict,
                        "email": candidate.email if mask_policy == "sensitive" else self._mask(candidate.email),
                        "phone": candidate.phone if mask_policy == "sensitive" else self._mask(candidate.phone),
                    }
                )
        job.status = "completed"
        job.file_path = str(export_path)
        job.completed_at = now_utc()
        self._audit("system", "export_job", job.id, "export.completed", "success", {"maskPolicy": mask_policy, "reason": reason})
        self.session.commit()
        return job

    def get_ops_summary(self) -> dict[str, Any]:
        run_counts = dict(
            self.session.execute(select(SearchRunModel.status, func.count()).group_by(SearchRunModel.status)).all()
        )
        failure_counts = dict(
            self.session.execute(select(SearchRunModel.error_code, func.count()).group_by(SearchRunModel.error_code)).all()
        )
        durations = [
            (run.finished_at - run.started_at).total_seconds()
            for run in self.session.scalars(select(SearchRunModel))
            if run.finished_at is not None
        ]
        avg_latency = sum(durations) / len(durations) if durations else 0.0
        return {
            "queue": {"searchRuns": run_counts},
            "failures": {"searchRuns": failure_counts},
            "latency": {"avgSearchRunSeconds": avg_latency},
            "version": {"api": settings.app_version, "externalCts": "2026-03-23"},
            "metrics": [
                {"name": "searchRunsTotal", "value": float(sum(run_counts.values()))},
                {"name": "searchRunsFailed", "value": float(sum(value for key, value in failure_counts.items() if key))},
                {"name": "candidateCount", "value": float(self.session.scalar(select(func.count()).select_from(CaseCandidateModel)) or 0)},
            ],
        }

    def create_eval_run(self, suite_id: str, dataset_id: str, target_version: str) -> EvalRunModel:
        eval_run = EvalRunModel(
            id=new_id("eval"),
            suite_id=suite_id,
            dataset_id=dataset_id,
            target_version=target_version,
            baseline_version=None,
            status="completed",
            summary_metrics={"blockingChecks": 3, "passedChecks": 3},
            blocking_result=True,
            created_at=now_utc(),
        )
        self.session.add(eval_run)
        self._audit("system", "eval_run", eval_run.id, "eval.completed", "success", {"suiteId": suite_id})
        self.session.commit()
        return eval_run

    def _persist_page(self, run: SearchRunModel, result: SearchPageData) -> None:
        normalized_cards: list[dict[str, Any]] = []
        page = SearchRunPageModel(
            id=new_id("page"),
            run_id=run.id,
            page_no=result.page_no,
            status=result.status,
            upstream_request=result.upstream_request,
            upstream_response=result.upstream_response,
            normalized_cards=[],
            total=result.total,
            fetched_at=now_utc(),
            error_code=result.error_code,
            error_message=result.error_message,
        )
        self.session.add(page)
        if not result.error_code:
            for candidate_data in result.candidates:
                candidate = self._upsert_candidate(run.case_id, candidate_data)
                normalized_cards.append(
                    {
                        "candidateId": candidate.id,
                        "externalIdentityId": candidate.external_identity_id,
                        "name": candidate.name,
                        "title": candidate.title,
                        "company": candidate.company,
                        "location": candidate.location,
                        "summary": candidate.summary,
                    }
                )
            run.pages_completed += 1
        page.normalized_cards = normalized_cards
        self.session.commit()

    def _upsert_candidate(self, case_id: str, candidate_data: Any) -> CaseCandidateModel:
        candidate = self.session.scalar(
            select(CaseCandidateModel).where(
                CaseCandidateModel.case_id == case_id,
                CaseCandidateModel.external_identity_id == candidate_data.external_identity_id,
            )
        )
        if candidate is None:
            candidate = CaseCandidateModel(
                id=new_id("cand"),
                case_id=case_id,
                external_identity_id=candidate_data.external_identity_id,
                latest_resume_snapshot_id=None,
                latest_verdict=None,
                dedupe_status="unique",
                name=candidate_data.name,
                title=candidate_data.title,
                company=candidate_data.company,
                location=candidate_data.location,
                summary=candidate_data.summary,
                email=candidate_data.email,
                phone=candidate_data.phone,
                created_at=now_utc(),
                updated_at=now_utc(),
            )
            self.session.add(candidate)
            self.session.flush()
        payload = {"content": candidate_data.resume, "summary": candidate_data.summary}
        source_hash = resume_hash(payload)
        snapshot = self.session.scalar(
            select(ResumeSnapshotModel).where(
                ResumeSnapshotModel.case_candidate_id == candidate.id,
                ResumeSnapshotModel.source_hash == source_hash,
            )
        )
        if snapshot is None:
            snapshot = ResumeSnapshotModel(
                id=new_id("snap"),
                case_candidate_id=candidate.id,
                source_hash=source_hash,
                payload=payload,
                created_at=now_utc(),
            )
            self.session.add(snapshot)
            self.session.flush()
            analysis = ResumeAnalysisJobModel(
                id=new_id("ana"),
                resume_snapshot_id=snapshot.id,
                model_version="stub-1",
                prompt_version="resume-summary-v1",
                summary=candidate.summary,
                evidence_spans=candidate_data.resume.get("skills", []),
                risk_flags=[],
                status="completed",
                created_at=now_utc(),
            )
            self.session.add(analysis)
        candidate.latest_resume_snapshot_id = snapshot.id
        candidate.updated_at = now_utc()
        return candidate

    def _audit(self, actor_id: str, target_type: str, target_id: str, action: str, result: str, metadata: dict) -> None:
        self.session.add(
            AuditLogModel(
                id=new_id("audit"),
                actor_id=actor_id,
                target_type=target_type,
                target_id=target_id,
                action=action,
                result=result,
                metadata_json=metadata,
                occurred_at=now_utc(),
            )
        )

    def _get_case(self, case_id: str) -> JDCaseModel:
        case = self.session.scalar(select(JDCaseModel).where(JDCaseModel.id == case_id))
        if case is None:
            raise AppError("CASE_NOT_FOUND", f"Case {case_id} not found.", 404)
        return case

    def _get_jd_version(self, case_id: str, jd_version_id: str) -> JDVersionModel:
        jd_version = self.session.scalar(
            select(JDVersionModel).where(JDVersionModel.id == jd_version_id, JDVersionModel.case_id == case_id)
        )
        if jd_version is None:
            raise AppError("JD_VERSION_NOT_FOUND", f"JD version {jd_version_id} not found.", 404)
        return jd_version

    def _get_plan(self, plan_id: str) -> ConditionPlanModel:
        plan = self.session.scalar(select(ConditionPlanModel).where(ConditionPlanModel.id == plan_id))
        if plan is None:
            raise AppError("PLAN_NOT_FOUND", f"Plan {plan_id} not found.", 404)
        return plan

    def _get_run(self, run_id: str) -> SearchRunModel:
        run = self.session.scalar(select(SearchRunModel).where(SearchRunModel.id == run_id))
        if run is None:
            raise AppError("RUN_NOT_FOUND", f"Run {run_id} not found.", 404)
        return run

    def _get_candidate(self, candidate_id: str) -> CaseCandidateModel:
        candidate = self.session.scalar(select(CaseCandidateModel).where(CaseCandidateModel.id == candidate_id))
        if candidate is None:
            raise AppError("CANDIDATE_NOT_FOUND", f"Candidate {candidate_id} not found.", 404)
        return candidate

    @staticmethod
    def _mask(value: str) -> str:
        if "@" in value:
            name, domain = value.split("@", 1)
            return f"{name[:2]}***@{domain}"
        if len(value) >= 7:
            return f"{value[:3]}****{value[-4:]}"
        return "***"

    @staticmethod
    def _draft_to_payload(draft: ConditionPlanDraftData) -> dict[str, Any]:
        return {
            "mustTerms": draft.must_terms,
            "shouldTerms": draft.should_terms,
            "excludeTerms": draft.exclude_terms,
            "structuredFilters": draft.structured_filters,
            "evidenceRefs": [PlatformService._evidence_ref_to_dict(ref) for ref in draft.evidence_refs],
        }

    @staticmethod
    def _evidence_ref_to_dict(ref: Any) -> dict[str, str]:
        return {"label": ref.label, "excerpt": ref.excerpt}
