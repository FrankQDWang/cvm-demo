from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import cast

from cvm_domain_kernel import new_id, now_utc

from cvm_platform.application.dto import AgentRunRecord, AuditLogRecord
from cvm_platform.application.policies import resolve_agent_model_version
from cvm_platform.application.ports import PlatformUnitOfWork
from cvm_platform.application.runtime import PlatformRuntimeConfig
from cvm_platform.domain.errors import NotFoundError, ValidationError
from cvm_platform.domain.types import (
    AgentRunConfigPayload,
    AgentRunStepPayload,
    JsonObject,
    NormalizedQueryPayload,
    SearchQueryDeltaPayload,
    SearchQueryPayload,
    StructuredFiltersPayload,
    to_json_object,
)


MIN_AGENT_ROUNDS = 3
MAX_AGENT_ROUNDS = 5


def json_signature(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def strategy_signature(strategy: NormalizedQueryPayload) -> str:
    return json_signature(
        {
            "keyword": strategy["keyword"].strip().lower(),
            "mustTerms": sorted(term.strip().lower() for term in strategy["mustTerms"]),
            "shouldTerms": sorted(term.strip().lower() for term in strategy["shouldTerms"]),
            "excludeTerms": sorted(term.strip().lower() for term in strategy["excludeTerms"]),
            "structuredFilters": strategy["structuredFilters"],
        }
    )


def strategy_to_query_payload(strategy: NormalizedQueryPayload) -> SearchQueryPayload:
    return {
        "keyword": strategy["keyword"],
        "mustTerms": list(strategy["mustTerms"]),
        "shouldTerms": list(strategy["shouldTerms"]),
        "excludeTerms": list(strategy["excludeTerms"]),
        "structuredFilters": strategy["structuredFilters"],
    }


def build_query_delta(
    previous_query: SearchQueryPayload,
    next_query: SearchQueryPayload,
) -> SearchQueryDeltaPayload:
    previous_filters = dict(previous_query["structuredFilters"])
    next_filters = dict(next_query["structuredFilters"])
    changed_filters: dict[str, JsonObject] = {}
    for key in sorted(set(previous_filters) | set(next_filters)):
        before_value = previous_filters.get(key)
        after_value = next_filters.get(key)
        if before_value == after_value:
            continue
        changed_filters[key] = to_json_object({"before": before_value, "after": after_value})
    return {
        "setKeyword": next_query["keyword"] if next_query["keyword"] != previous_query["keyword"] else None,
        "addedMustTerms": [term for term in next_query["mustTerms"] if term not in previous_query["mustTerms"]],
        "removedMustTerms": [term for term in previous_query["mustTerms"] if term not in next_query["mustTerms"]],
        "addedShouldTerms": [term for term in next_query["shouldTerms"] if term not in previous_query["shouldTerms"]],
        "removedShouldTerms": [term for term in previous_query["shouldTerms"] if term not in next_query["shouldTerms"]],
        "addedExcludeTerms": [term for term in next_query["excludeTerms"] if term not in previous_query["excludeTerms"]],
        "removedExcludeTerms": [term for term in previous_query["excludeTerms"] if term not in next_query["excludeTerms"]],
        "changedStructuredFilters": to_json_object(changed_filters),
        "removedStructuredFilterKeys": [
            key for key in previous_filters.keys() if key not in next_filters
        ],
    }


def payload_list(value: object) -> list[object]:
    return cast(list[object], value) if isinstance(value, list) else []


def append_agent_run_step(
    steps: list[AgentRunStepPayload],
    *,
    round_no: int | None,
    step_type: str,
    title: str,
    status: str,
    summary: str,
    payload: dict[str, object],
    occurred_at: datetime | None = None,
) -> AgentRunStepPayload:
    timestamp = occurred_at or now_utc()
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return {
        "stepNo": len(steps) + 1,
        "roundNo": round_no,
        "stepType": step_type,
        "title": title,
        "status": status,
        "summary": summary,
        "payload": to_json_object(payload),
        "occurredAt": timestamp.isoformat(),
    }


def build_compact_round_ledger(steps: list[AgentRunStepPayload]) -> list[dict[str, object]]:
    extraction_summary = next(
        (step["payload"] for step in steps if step["stepType"] == "strategy" and step["roundNo"] is None),
        None,
    )
    ledger_by_round: dict[int, dict[str, object]] = {}
    for step in steps:
        round_no = step["roundNo"]
        if round_no is None:
            continue
        round_entry = ledger_by_round.setdefault(round_no, {"roundNo": round_no})
        if step["stepType"] == "search":
            round_entry["search"] = {
                "query": step["payload"].get("roundQuery") or step["payload"].get("normalizedQuery"),
                "returnedCount": step["payload"].get("returnedCount", 0),
            }
        elif step["stepType"] == "dedupe":
            admitted_resume_ids = payload_list(step["payload"].get("admittedResumeIds", []))
            duplicate_resume_ids = payload_list(step["payload"].get("duplicateResumeIds", []))
            round_entry["dedupe"] = {
                "admittedCount": len(admitted_resume_ids),
                "duplicateCount": len(duplicate_resume_ids),
                "duplicateResumeIds": duplicate_resume_ids,
            }
        elif step["stepType"] == "analysis":
            analyses = payload_list(step["payload"].get("analyses", []))
            round_entry["analysis"] = {
                "analyzedCount": len(analyses),
                "analyses": analyses,
            }
        elif step["stepType"] == "shortlist":
            round_entry["shortlist"] = {
                "retainedCount": step["payload"].get("retainedCount"),
                "retainedCandidates": step["payload"].get("retainedCandidates", []),
            }
        elif step["stepType"] == "reflection":
            round_entry["reflection"] = {
                "reason": step["payload"].get("reason"),
                "continueSearch": step["payload"].get("continueSearch"),
                "nextRoundGoal": step["payload"].get("nextRoundGoal"),
                "queryDelta": step["payload"].get("queryDelta"),
            }
        elif step["stepType"] == "stop":
            round_entry["stop"] = {
                "reason": step["payload"].get("reason"),
                "summary": step["summary"],
            }
    round_ledger = [ledger_by_round[round_no] for round_no in sorted(ledger_by_round)]
    if extraction_summary is None:
        return round_ledger
    return [
        {
            "extraction": {
                "mustRequirements": extraction_summary.get("mustRequirements", []),
                "coreRequirements": extraction_summary.get("coreRequirements", []),
                "bonusRequirements": extraction_summary.get("bonusRequirements", []),
                "excludeSignals": extraction_summary.get("excludeSignals", []),
                "round1Query": extraction_summary.get("round1Query", {}),
            }
        },
        *round_ledger,
    ]


def build_search_strategy(
    *,
    jd_text: str,
    keyword: str,
    must_terms: list[str],
    should_terms: list[str],
    exclude_terms: list[str],
    structured_filters: StructuredFiltersPayload,
) -> NormalizedQueryPayload:
    normalized_must_terms = [term.strip() for term in must_terms if term.strip()]
    normalized_should_terms = [
        term.strip() for term in should_terms if term.strip() and term.strip() not in normalized_must_terms
    ]
    normalized_exclude_terms = [term.strip() for term in exclude_terms if term.strip()]
    resolved_keyword = keyword.strip() or " ".join(normalized_must_terms + normalized_should_terms).strip()
    if not resolved_keyword:
        raise ValidationError(
            "AGENT_SEARCH_STRATEGY_INVALID",
            "The extracted search strategy did not contain any keyword.",
        )
    return {
        "jd": jd_text,
        "mustTerms": normalized_must_terms or [resolved_keyword],
        "shouldTerms": normalized_should_terms,
        "excludeTerms": normalized_exclude_terms,
        "structuredFilters": structured_filters,
        "keyword": resolved_keyword,
    }


def normalize_agent_run_config(
    config: AgentRunConfigPayload | None,
    runtime_config: PlatformRuntimeConfig,
) -> AgentRunConfigPayload:
    configured_min_rounds = runtime_config.default_agent_min_rounds
    raw_max_rounds = runtime_config.default_agent_max_rounds if config is None else config["maxRounds"]
    raw_final_top_k = runtime_config.default_agent_final_top_k if config is None else config["finalTopK"]
    raw_schedule = (
        list(runtime_config.default_agent_round_fetch_schedule)
        if config is None
        else list(config["roundFetchSchedule"])
    )
    if configured_min_rounds < MIN_AGENT_ROUNDS or configured_min_rounds > MAX_AGENT_ROUNDS:
        raise ValidationError(
            "INVALID_AGENT_CONFIG",
            f"Configured min rounds must be between {MIN_AGENT_ROUNDS} and {MAX_AGENT_ROUNDS}.",
        )
    if raw_max_rounds < configured_min_rounds or raw_max_rounds > MAX_AGENT_ROUNDS:
        raise ValidationError(
            "INVALID_AGENT_CONFIG",
            f"maxRounds must be between {configured_min_rounds} and {MAX_AGENT_ROUNDS}.",
        )
    if raw_final_top_k <= 0:
        raise ValidationError("INVALID_AGENT_CONFIG", "finalTopK must be positive.")
    if not raw_schedule or any(fetch_size <= 0 for fetch_size in raw_schedule):
        raise ValidationError("INVALID_AGENT_CONFIG", "roundFetchSchedule must contain positive integers.")
    normalized_schedule = raw_schedule[:raw_max_rounds]
    while len(normalized_schedule) < raw_max_rounds:
        normalized_schedule.append(normalized_schedule[-1])
    return {
        "maxRounds": raw_max_rounds,
        "roundFetchSchedule": normalized_schedule,
        "finalTopK": raw_final_top_k,
    }


class AgentRunsCoordinator:
    def __init__(
        self,
        *,
        uow: PlatformUnitOfWork,
        runtime_config: PlatformRuntimeConfig,
    ) -> None:
        self.uow = uow
        self.runtime_config = runtime_config

    def create_run(
        self,
        *,
        jd_text: str,
        sourcing_preference_text: str,
        model_version: str,
        prompt_version: str,
        idempotency_key: str,
        config: AgentRunConfigPayload | None,
    ) -> AgentRunRecord:
        existing = self.uow.agent_runs.find_by_idempotency_key(idempotency_key)
        if existing:
            if not existing.workflow_id:
                existing.workflow_id = f"agent-run-{existing.id}"
                existing.temporal_namespace = self.runtime_config.temporal_namespace
                existing.temporal_task_queue = self.runtime_config.temporal_task_queue
                self.uow.agent_runs.save_run(existing)
                self.uow.commit()
            return existing
        resolved_model_version = resolve_agent_model_version(model_version, self.runtime_config)
        normalized_config = normalize_agent_run_config(config, self.runtime_config)
        timestamp = now_utc()
        run_id = new_id("agent")
        run = AgentRunRecord(
            id=run_id,
            status="queued",
            jd_text=jd_text,
            sourcing_preference_text=sourcing_preference_text,
            idempotency_key=idempotency_key,
            config=normalized_config,
            current_round=0,
            model_version=resolved_model_version,
            prompt_version=prompt_version,
            workflow_id=f"agent-run-{run_id}",
            temporal_namespace=self.runtime_config.temporal_namespace,
            temporal_task_queue=self.runtime_config.temporal_task_queue,
            langfuse_trace_id=None,
            langfuse_trace_url=None,
            steps=[],
            final_shortlist=[],
            seen_resume_ids=[],
            error_code=None,
            error_message=None,
            created_at=timestamp,
            started_at=timestamp,
            finished_at=None,
        )
        self.uow.agent_runs.save_run(run)
        self._audit(
            "system",
            "agent_run",
            run.id,
            "agent_run.created",
            "success",
            to_json_object(
                {
                    "modelVersion": resolved_model_version,
                    "promptVersion": prompt_version,
                    "minRounds": self.runtime_config.default_agent_min_rounds,
                    "maxRounds": normalized_config["maxRounds"],
                    "roundFetchSchedule": normalized_config["roundFetchSchedule"],
                    "finalTopK": normalized_config["finalTopK"],
                }
            ),
        )
        self.uow.commit()
        return run

    def list_runs(self) -> list[AgentRunRecord]:
        return self.uow.agent_runs.list_runs()

    def get_run(self, run_id: str) -> AgentRunRecord:
        run = self.uow.agent_runs.get_run(run_id)
        if run is None:
            raise NotFoundError("AGENT_RUN_NOT_FOUND", f"Agent run {run_id} not found.")
        return run

    def fail_dispatch(self, run_id: str, *, error_code: str, error_message: str) -> AgentRunRecord:
        run = self.get_run(run_id)
        run.status = "failed"
        run.error_code = error_code
        run.error_message = error_message
        run.finished_at = now_utc()
        self.uow.agent_runs.save_run(run)
        self._audit(
            "system",
            "agent_run",
            run.id,
            "agent_run.dispatch.failed",
            "failure",
            to_json_object({"errorCode": error_code, "errorMessage": error_message}),
        )
        self.uow.commit()
        return run

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
