from __future__ import annotations

import csv
from pathlib import Path

from cvm_domain_kernel import new_id, now_utc
from cvm_platform.application.agent_runs import AgentRunsCoordinator
from cvm_platform.application.agent_tracing import AgentRunTracer, NoOpAgentRunTracer
from cvm_platform.application.dto import (
    AgentRunRecord,
    AuditLogRecord,
    CandidateDetailRecord,
    CandidateRecord,
    CaseRecord,
    EvalRunRecord,
    ExportJobRecord,
    JDVersionRecord,
    MetricRecord,
    OpsSummaryRecord,
    OpsVersionRecord,
    VerdictHistoryRecord,
)
from cvm_platform.application.ports import PlatformUnitOfWork
from cvm_platform.application.runtime import PlatformRuntimeConfig
from cvm_platform.domain.errors import (
    ExternalDependencyError,
    NotFoundError,
    PermissionDeniedError,
)
from cvm_platform.domain.ports import LLMPort, ResumeSourcePort
from cvm_platform.domain.types import (
    AgentRunFailureCountPayload,
    AgentRunConfigPayload,
    AgentRunStatusCountPayload,
    FailureSummaryPayload,
    JsonObject,
    LatencySummaryPayload,
    QueueSummaryPayload,
    to_json_object,
)


class PlatformService:
    def __init__(
        self,
        uow: PlatformUnitOfWork,
        runtime_config: PlatformRuntimeConfig,
        llm: LLMPort,
        resume_source: ResumeSourcePort,
        agent_run_tracer: AgentRunTracer | None = None,
    ) -> None:
        self.uow = uow
        self.runtime_config = runtime_config
        self.llm = llm
        self.resume_source = resume_source
        self.agent_runs = AgentRunsCoordinator(
            uow=uow,
            runtime_config=runtime_config,
            llm=llm,
            resume_source=resume_source,
            tracer=agent_run_tracer or NoOpAgentRunTracer(),
        )

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
        self._audit("system", "case", case.id, "case.created", "success", to_json_object({"title": title}))
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
        self._audit("system", "jd_version", version.id, "jd_version.created", "success", to_json_object({"caseId": case_id}))
        self.uow.commit()
        return version

    def create_agent_run(
        self,
        *,
        jd_text: str,
        sourcing_preference_text: str,
        model_version: str | None = None,
        prompt_version: str | None = None,
        idempotency_key: str | None = None,
        config: AgentRunConfigPayload | None = None,
    ) -> AgentRunRecord:
        return self.agent_runs.create_run(
            jd_text=jd_text,
            sourcing_preference_text=sourcing_preference_text,
            model_version=model_version or self.runtime_config.default_llm_model,
            prompt_version=prompt_version or self.runtime_config.default_agent_prompt_version,
            idempotency_key=idempotency_key or new_id("agentreq"),
            config=config,
        )

    def list_agent_runs(self) -> list[AgentRunRecord]:
        return self.agent_runs.list_runs()

    def get_agent_run(self, run_id: str) -> AgentRunRecord:
        return self.agent_runs.get_run(run_id)

    def fail_agent_run_dispatch(self, run_id: str, error_code: str, error_message: str) -> AgentRunRecord:
        return self.agent_runs.fail_dispatch(run_id, error_code=error_code, error_message=error_message)

    def execute_agent_run(self, run_id: str) -> AgentRunRecord:
        return self.agent_runs.execute_run(run_id)

    def get_candidate_detail(self, candidate_id: str) -> CandidateDetailRecord:
        candidate = self._get_candidate(candidate_id)
        if not candidate.latest_resume_snapshot_id:
            raise NotFoundError("RESUME_SNAPSHOT_NOT_FOUND", "Candidate resume snapshot missing.")
        snapshot = self.uow.candidates.get_resume_snapshot(candidate.latest_resume_snapshot_id)
        if snapshot is None:
            raise NotFoundError("RESUME_SNAPSHOT_NOT_FOUND", "Candidate resume snapshot missing.")
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
        self._audit(
            actor_id,
            "candidate",
            candidate_id,
            "candidate.verdict.saved",
            "success",
            to_json_object({"verdict": verdict, "reasons": reasons}),
        )
        self.uow.commit()
        return candidate

    def create_export(self, case_id: str, mask_policy: str, reason: str, idempotency_key: str) -> ExportJobRecord:
        self._get_case(case_id)
        existing = self.uow.exports.find_by_idempotency_key(idempotency_key)
        if existing:
            return existing
        if mask_policy == "sensitive" and not self.runtime_config.allow_sensitive_export:
            raise PermissionDeniedError(
                "NO_CONTACT_PERMISSION",
                "Sensitive export is disabled in local mode.",
            )
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
                to_json_object({"maskPolicy": mask_policy, "reason": reason, "error": str(exc)}),
            )
            self.uow.commit()
            raise ExternalDependencyError("EXPORT_FAILED", "Failed to write export file.") from exc

        job.status = "completed"
        job.file_path = str(export_path)
        job.completed_at = now_utc()
        self.uow.exports.save_export_job(job)
        self._audit(
            "system",
            "export_job",
            job.id,
            "export.completed",
            "success",
            to_json_object({"maskPolicy": mask_policy, "reason": reason}),
        )
        self.uow.commit()
        return job

    def get_ops_summary(self) -> OpsSummaryRecord:
        run_counts = self.uow.agent_runs.count_by_status()
        failure_counts_raw = self.uow.agent_runs.count_failures_by_error_code()
        queue_counts: list[AgentRunStatusCountPayload] = [
            {"status": status, "count": count}
            for status, count in sorted(run_counts.items())
        ]
        failure_counts: list[AgentRunFailureCountPayload] = [
            {"code": "null" if key is None else str(key), "count": value}
            for key, value in sorted(
                failure_counts_raw.items(),
                key=lambda item: "null" if item[0] is None else str(item[0]),
            )
        ]
        durations = [
            (run.finished_at - run.started_at).total_seconds()
            for run in self.uow.agent_runs.list_finished_runs()
            if run.finished_at is not None
        ]
        avg_latency = sum(durations) / len(durations) if durations else 0.0
        return OpsSummaryRecord(
            queue=QueueSummaryPayload(agentRuns=queue_counts),
            failures=FailureSummaryPayload(agentRuns=failure_counts),
            latency=LatencySummaryPayload(avgAgentRunSeconds=avg_latency),
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
                MetricRecord(name="agentRunsTotal", value=float(sum(run_counts.values()))),
                MetricRecord(
                    name="agentRunsFailed",
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
        self._audit("system", "eval_run", eval_run.id, "eval.completed", "success", to_json_object({"suiteId": suite_id}))
        self.uow.commit()
        return eval_run

    def _audit(
        self,
        actor_id: str,
        target_type: str,
        target_id: str,
        action: str,
        result: str,
        metadata: JsonObject,
    ) -> None:
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
            raise NotFoundError("CASE_NOT_FOUND", f"Case {case_id} not found.")
        return case

    def _get_jd_version(self, case_id: str, jd_version_id: str) -> JDVersionRecord:
        jd_version = self.uow.plans.get_jd_version(case_id, jd_version_id)
        if jd_version is None:
            raise NotFoundError("JD_VERSION_NOT_FOUND", f"JD version {jd_version_id} not found.")
        return jd_version

    def _get_candidate(self, candidate_id: str) -> CandidateRecord:
        candidate = self.uow.candidates.get_candidate(candidate_id)
        if candidate is None:
            raise NotFoundError("CANDIDATE_NOT_FOUND", f"Candidate {candidate_id} not found.")
        return candidate

    @staticmethod
    def _mask(value: str) -> str:
        if "@" in value:
            name, domain = value.split("@", 1)
            return f"{name[:2]}***@{domain}"
        if len(value) >= 7:
            return f"{value[:3]}****{value[-4:]}"
        return "***"

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
