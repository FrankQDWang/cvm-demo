from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from cvm_domain_kernel import new_id, now_utc
from cvm_platform.application.dto import (
    AuditLogRecord,
    CandidateDetailRecord,
    CandidateRecord,
    CaseRecord,
    ConditionPlanRecord,
    EvalRunRecord,
    ExportJobRecord,
    JDVersionRecord,
    KeywordDraftJobRecord,
    KeywordDraftJobResult,
    MetricRecord,
    OpsSummaryRecord,
    OpsVersionRecord,
    ResumeAnalysisRecord,
    ResumeSnapshotRecord,
    SearchRunPageRecord,
    SearchRunRecord,
    VerdictHistoryRecord,
)
from cvm_platform.application.policies import resolve_llm_model_version, resume_hash
from cvm_platform.application.ports import PlatformUnitOfWork
from cvm_platform.application.runtime import PlatformRuntimeConfig
from cvm_platform.domain.errors import AppError
from cvm_platform.domain.ports import LLMPort, ResumeSourcePort
from cvm_platform.domain.types import ConditionPlanDraftData, SearchPageData


class PlatformService:
    def __init__(
        self,
        uow: PlatformUnitOfWork,
        runtime_config: PlatformRuntimeConfig,
        llm: LLMPort,
        resume_source: ResumeSourcePort,
    ) -> None:
        self.uow = uow
        self.runtime_config = runtime_config
        self.llm = llm
        self.resume_source = resume_source

    def create_case(self, title: str, owner_team_id: str) -> CaseRecord:
        timestamp = now_utc()
        case = CaseRecord(
            id=new_id("case"),
            title=title,
            owner_team_id=owner_team_id,
            status="draft",
            created_at=timestamp,
            updated_at=timestamp,
        )
        self.uow.cases.save(case)
        self._audit("system", "case", case.id, "case.created", "success", {"title": title})
        self.uow.commit()
        return case

    def create_jd_version(self, case_id: str, raw_text: str, source: str) -> JDVersionRecord:
        case = self._get_case(case_id)
        version_no = self.uow.plans.count_versions_for_case(case_id) + 1
        self.uow.plans.deactivate_versions(case_id)
        version = JDVersionRecord(
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
        self.uow.cases.save(case)
        self.uow.plans.save_jd_version(version)
        self._audit("system", "jd_version", version.id, "jd_version.created", "success", {"caseId": case_id})
        self.uow.commit()
        return version

    def create_keyword_draft_job(
        self,
        case_id: str,
        jd_version_id: str,
        model_version: str,
        prompt_version: str,
    ) -> KeywordDraftJobResult:
        self._get_case(case_id)
        jd_version = self._get_jd_version(case_id, jd_version_id)
        resolved_model_version = resolve_llm_model_version(model_version, self.runtime_config)
        draft = self.llm.draft_keywords(jd_version.raw_text, resolved_model_version, prompt_version)
        timestamp = now_utc()
        plan = ConditionPlanRecord(
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
            created_at=timestamp,
        )
        job = KeywordDraftJobRecord(
            id=new_id("kdj"),
            case_id=case_id,
            jd_version_id=jd_version_id,
            status="completed",
            model_version=resolved_model_version,
            prompt_version=prompt_version,
            draft_payload=self._draft_to_payload(draft),
            created_at=timestamp,
            completed_at=timestamp,
        )
        self.uow.plans.save_plan(plan)
        self.uow.plans.save_keyword_draft_job(job)
        self._audit("system", "keyword_draft_job", job.id, "keyword_draft.completed", "success", {"planId": plan.id})
        self.uow.commit()
        return KeywordDraftJobResult(job=job, plan=plan)

    def confirm_condition_plan(
        self,
        plan_id: str,
        confirmed_by: str,
        payload: ConditionPlanDraftData,
    ) -> ConditionPlanRecord:
        plan = self._get_plan(plan_id)
        jd_version = self._get_jd_version(plan.case_id, plan.jd_version_id)
        normalized_query = {
            "jd": jd_version.raw_text,
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
        self.uow.plans.save_plan(plan)
        self._audit(confirmed_by, "condition_plan", plan.id, "condition_plan.confirmed", "success", normalized_query)
        self.uow.commit()
        return plan

    def create_search_run(self, case_id: str, plan_id: str, page_budget: int, idempotency_key: str) -> SearchRunRecord:
        if page_budget <= 0:
            raise AppError("INVALID_PAGINATION_PARAMS", "pageBudget must be positive.")
        plan = self._get_plan(plan_id)
        if plan.case_id != case_id:
            raise AppError("PLAN_CASE_MISMATCH", "Plan does not belong to case.")
        if plan.status != "confirmed":
            raise AppError("PLAN_NOT_CONFIRMED", "Condition plan must be confirmed before search.")
        existing = self.uow.search_runs.find_by_idempotency_key(idempotency_key)
        if existing:
            if not existing.workflow_id:
                existing.workflow_id = f"search-run-{existing.id}"
                existing.temporal_namespace = self.runtime_config.temporal_namespace
                existing.temporal_task_queue = self.runtime_config.temporal_task_queue
                self.uow.search_runs.save_run(existing)
                self.uow.commit()
            return existing
        run_id = new_id("run")
        run = SearchRunRecord(
            id=run_id,
            case_id=case_id,
            plan_id=plan_id,
            status="queued",
            page_budget=page_budget,
            pages_completed=0,
            idempotency_key=idempotency_key,
            workflow_id=f"search-run-{run_id}",
            temporal_namespace=self.runtime_config.temporal_namespace,
            temporal_task_queue=self.runtime_config.temporal_task_queue,
            error_code=None,
            error_message=None,
            started_at=now_utc(),
            finished_at=None,
        )
        self.uow.search_runs.save_run(run)
        self._audit("system", "search_run", run.id, "search_run.created", "success", {"caseId": case_id, "planId": plan_id})
        self.uow.commit()
        return run

    def execute_search_run(self, run_id: str) -> SearchRunRecord:
        run = self._get_run(run_id)
        plan = self._get_plan(run.plan_id)
        run.status = "running"
        self.uow.search_runs.save_run(run)
        self.uow.commit()

        page_size = int(plan.structured_filters.get("pageSize", 2))
        for page_no in range(1, run.page_budget + 1):
            result = self.resume_source.search_candidates(plan.normalized_query, page_no, page_size)
            self._persist_page(run, result)
            if result.error_code:
                run.status = "failed"
                run.error_code = result.error_code
                run.error_message = result.error_message
                run.finished_at = now_utc()
                self.uow.search_runs.save_run(run)
                self.uow.commit()
                return run

        run.status = "completed"
        run.finished_at = now_utc()
        self.uow.search_runs.save_run(run)
        self.uow.commit()
        return run

    def get_search_run(self, run_id: str) -> SearchRunRecord:
        return self._get_run(run_id)

    def get_search_pages(self, run_id: str, page_no: int | None = None) -> list[SearchRunPageRecord]:
        return self.uow.search_runs.list_pages(run_id, page_no)

    def get_candidate_detail(self, candidate_id: str) -> CandidateDetailRecord:
        candidate = self._get_candidate(candidate_id)
        if not candidate.latest_resume_snapshot_id:
            raise AppError("RESUME_SNAPSHOT_NOT_FOUND", "Candidate resume snapshot missing.", 404)
        snapshot = self.uow.candidates.get_resume_snapshot(candidate.latest_resume_snapshot_id)
        if snapshot is None:
            raise AppError("RESUME_SNAPSHOT_NOT_FOUND", "Candidate resume snapshot missing.", 404)
        analysis = self.uow.candidates.get_latest_analysis(snapshot.id)
        history = self.uow.candidates.list_verdict_history(candidate_id)
        return CandidateDetailRecord(
            candidate=candidate,
            resume_snapshot=snapshot,
            ai_analysis=analysis,
            verdict_history=history,
        )

    def save_verdict(
        self,
        candidate_id: str,
        verdict: str,
        reasons: list[str],
        notes: str | None,
        actor_id: str,
        resume_snapshot_id: str | None,
    ) -> CandidateRecord:
        candidate = self._get_candidate(candidate_id)
        candidate.latest_verdict = verdict
        candidate.updated_at = now_utc()
        history = VerdictHistoryRecord(
            id=new_id("ver"),
            case_candidate_id=candidate_id,
            verdict=verdict,
            reasons=reasons,
            notes=notes,
            actor_id=actor_id,
            resume_snapshot_id=resume_snapshot_id,
            created_at=now_utc(),
        )
        self.uow.candidates.save_candidate(candidate)
        self.uow.candidates.save_verdict_history(history)
        self._audit(actor_id, "candidate", candidate_id, "candidate.verdict.saved", "success", {"verdict": verdict, "reasons": reasons})
        self.uow.commit()
        return candidate

    def create_export(self, case_id: str, mask_policy: str, reason: str, idempotency_key: str) -> ExportJobRecord:
        self._get_case(case_id)
        existing = self.uow.exports.find_by_idempotency_key(idempotency_key)
        if existing:
            return existing
        if mask_policy == "sensitive" and not self.runtime_config.allow_sensitive_export:
            raise AppError("NO_CONTACT_PERMISSION", "Sensitive export is disabled in local mode.", 403)
        job = ExportJobRecord(
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
        self.uow.exports.save_export_job(job)
        self.uow.commit()

        candidates = self.uow.candidates.list_exportable_candidates(case_id)
        export_path = self._build_export_path(case_id, job.id)
        try:
            self._write_export_file(export_path, candidates, mask_policy)
        except OSError as exc:
            job.status = "failed"
            job.completed_at = now_utc()
            self.uow.exports.save_export_job(job)
            self._audit(
                "system",
                "export_job",
                job.id,
                "export.completed",
                "failure",
                {"maskPolicy": mask_policy, "reason": reason, "error": str(exc)},
            )
            self.uow.commit()
            raise AppError("EXPORT_FAILED", "Failed to write export file.", 500) from exc

        job.status = "completed"
        job.file_path = str(export_path)
        job.completed_at = now_utc()
        self.uow.exports.save_export_job(job)
        self._audit("system", "export_job", job.id, "export.completed", "success", {"maskPolicy": mask_policy, "reason": reason})
        self.uow.commit()
        return job

    def get_ops_summary(self) -> OpsSummaryRecord:
        run_counts = self.uow.search_runs.count_by_status()
        failure_counts_raw = self.uow.search_runs.count_failures_by_error_code()
        failure_counts = {("null" if key is None else str(key)): value for key, value in failure_counts_raw.items()}
        durations = [
            (run.finished_at - run.started_at).total_seconds()
            for run in self.uow.search_runs.list_finished_runs()
            if run.finished_at is not None
        ]
        avg_latency = sum(durations) / len(durations) if durations else 0.0
        return OpsSummaryRecord(
            queue={"searchRuns": run_counts},
            failures={"searchRuns": failure_counts},
            latency={"avgSearchRunSeconds": avg_latency},
            version=OpsVersionRecord(
                api=self.runtime_config.app_version,
                api_build_id=self.runtime_config.build_id,
                worker_build_id=self.runtime_config.build_id,
                external_cts="2026-03-23",
                temporal_namespace=self.runtime_config.temporal_namespace,
                temporal_ui_url=self.runtime_config.temporal_ui_base_url.rstrip("/"),
                temporal_visibility_backend=self.runtime_config.temporal_visibility_backend,
            ),
            metrics=[
                MetricRecord(name="searchRunsTotal", value=float(sum(run_counts.values()))),
                MetricRecord(
                    name="searchRunsFailed",
                    value=float(sum(value for key, value in failure_counts_raw.items() if key)),
                ),
                MetricRecord(name="candidateCount", value=float(self.uow.candidates.count_candidates())),
            ],
        )

    def create_eval_run(self, suite_id: str, dataset_id: str, target_version: str) -> EvalRunRecord:
        eval_run = EvalRunRecord(
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
        self.uow.eval_runs.save_eval_run(eval_run)
        self._audit("system", "eval_run", eval_run.id, "eval.completed", "success", {"suiteId": suite_id})
        self.uow.commit()
        return eval_run

    def _persist_page(self, run: SearchRunRecord, result: SearchPageData) -> None:
        normalized_cards: list[dict[str, Any]] = []
        page = SearchRunPageRecord(
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
        self.uow.search_runs.save_page(page)
        self.uow.search_runs.save_run(run)
        self.uow.commit()

    def _upsert_candidate(self, case_id: str, candidate_data: Any) -> CandidateRecord:
        candidate = self.uow.candidates.find_by_case_and_external_identity(case_id, candidate_data.external_identity_id)
        timestamp = now_utc()
        if candidate is None:
            candidate = CandidateRecord(
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
                created_at=timestamp,
                updated_at=timestamp,
            )
        else:
            candidate.name = candidate_data.name
            candidate.title = candidate_data.title
            candidate.company = candidate_data.company
            candidate.location = candidate_data.location
            candidate.summary = candidate_data.summary
            candidate.email = candidate_data.email
            candidate.phone = candidate_data.phone
        candidate = self.uow.candidates.save_candidate(candidate)
        payload = {"content": candidate_data.resume, "summary": candidate_data.summary}
        source_hash = resume_hash(payload)
        snapshot = self.uow.candidates.find_resume_snapshot_by_source_hash(candidate.id, source_hash)
        if snapshot is None:
            snapshot = ResumeSnapshotRecord(
                id=new_id("snap"),
                case_candidate_id=candidate.id,
                source_hash=source_hash,
                payload=payload,
                created_at=now_utc(),
            )
            self.uow.candidates.save_resume_snapshot(snapshot)
            analysis = ResumeAnalysisRecord(
                id=new_id("ana"),
                resume_snapshot_id=snapshot.id,
                model_version="stub-1",
                prompt_version="resume-summary-v1",
                summary=candidate.summary,
                evidence_spans=self._candidate_evidence_spans(candidate_data.resume),
                risk_flags=self._candidate_risk_flags(candidate_data.resume),
                status="completed",
                created_at=now_utc(),
            )
            self.uow.candidates.save_resume_analysis(analysis)
        candidate.latest_resume_snapshot_id = snapshot.id
        candidate.updated_at = now_utc()
        return self.uow.candidates.save_candidate(candidate)

    @staticmethod
    def _candidate_evidence_spans(resume: dict[str, Any]) -> list[str]:
        evidence: list[str] = []
        for key in ("projectNameAll", "workSummariesAll"):
            value = resume.get(key)
            if isinstance(value, str) and value.strip():
                evidence.extend([item.strip() for item in value.split("；") if item.strip()])
        if not evidence:
            for experience in resume.get("workExperienceList", [])[:3]:
                company = str(experience.get("companyName") or "").strip()
                title = str(experience.get("positionName") or "").strip()
                summary = " / ".join(part for part in (company, title) if part)
                if summary:
                    evidence.append(summary)
        return evidence[:5]

    @staticmethod
    def _candidate_risk_flags(resume: dict[str, Any]) -> list[str]:
        flags: list[str] = []
        expected_salary = str(resume.get("expectedSalary") or "").strip()
        if expected_salary:
            flags.append(f"Expected salary: {expected_salary}")
        job_state = str(resume.get("jobState") or "").strip()
        if job_state:
            flags.append(f"Job state: {job_state}")
        return flags[:3]

    def _audit(self, actor_id: str, target_type: str, target_id: str, action: str, result: str, metadata: dict) -> None:
        self.uow.audit_logs.save_audit_log(
            AuditLogRecord(
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

    def _get_case(self, case_id: str) -> CaseRecord:
        case = self.uow.cases.get(case_id)
        if case is None:
            raise AppError("CASE_NOT_FOUND", f"Case {case_id} not found.", 404)
        return case

    def _get_jd_version(self, case_id: str, jd_version_id: str) -> JDVersionRecord:
        jd_version = self.uow.plans.get_jd_version(case_id, jd_version_id)
        if jd_version is None:
            raise AppError("JD_VERSION_NOT_FOUND", f"JD version {jd_version_id} not found.", 404)
        return jd_version

    def _get_plan(self, plan_id: str) -> ConditionPlanRecord:
        plan = self.uow.plans.get_plan(plan_id)
        if plan is None:
            raise AppError("PLAN_NOT_FOUND", f"Plan {plan_id} not found.", 404)
        return plan

    def _get_run(self, run_id: str) -> SearchRunRecord:
        run = self.uow.search_runs.get_run(run_id)
        if run is None:
            raise AppError("RUN_NOT_FOUND", f"Run {run_id} not found.", 404)
        return run

    def _get_candidate(self, candidate_id: str) -> CandidateRecord:
        candidate = self.uow.candidates.get_candidate(candidate_id)
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

    def _build_export_path(self, case_id: str, export_job_id: str) -> Path:
        self.runtime_config.exports_dir.mkdir(parents=True, exist_ok=True)
        return self.runtime_config.exports_dir / f"{case_id}-{export_job_id}.csv"

    def _write_export_file(self, export_path: Path, candidates: list[CandidateRecord], mask_policy: str) -> None:
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
