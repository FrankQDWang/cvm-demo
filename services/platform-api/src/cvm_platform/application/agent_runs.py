from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC
from typing import cast

from cvm_domain_kernel import new_id, now_utc

from cvm_platform.application.agent_tracing import (
    AgentRunTraceHandle,
    AgentRunTracer,
    AgentTraceObservation,
)
from cvm_platform.application.dto import AgentRunRecord, AuditLogRecord
from cvm_platform.application.policies import resolve_llm_model_version
from cvm_platform.application.ports import PlatformUnitOfWork
from cvm_platform.application.runtime import PlatformRuntimeConfig
from cvm_platform.domain.errors import (
    ExternalDependencyError,
    NotFoundError,
    TransientDependencyError,
    ValidationError,
)
from cvm_platform.domain.ports import LLMPort, ResumeSourcePort
from cvm_platform.domain.types import (
    AgentRunConfigPayload,
    AgentRunStepPayload,
    AgentSearchStrategyData,
    AgentShortlistCandidatePayload,
    CandidateData,
    JsonObject,
    NormalizedQueryPayload,
    SearchPageData,
    SearchReflectionData,
    SearchQueryDeltaPayload,
    SearchQueryPayload,
    StructuredFiltersPayload,
    to_json_object,
)


@dataclass(slots=True)
class _ShortlistedCandidate:
    candidate: CandidateData
    score: float
    reason: str
    source_round: int
    degraded: bool

    def to_payload(self) -> AgentShortlistCandidatePayload:
        return {
            "externalIdentityId": self.candidate.external_identity_id,
            "name": self.candidate.name,
            "title": self.candidate.title,
            "company": self.candidate.company,
            "location": self.candidate.location,
            "summary": self.candidate.summary,
            "reason": self.reason,
            "score": round(self.score, 4),
            "sourceRound": self.source_round,
        }


@dataclass(slots=True)
class _AnalyzedCandidate:
    shortlisted: _ShortlistedCandidate
    prompt_text: str
    model_version: str
    prompt_version: str
    evidence: list[str]
    concerns: list[str]


def _json_signature(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _strategy_signature(strategy: NormalizedQueryPayload) -> str:
    return _json_signature(
        {
            "keyword": strategy["keyword"].strip().lower(),
            "mustTerms": sorted(term.strip().lower() for term in strategy["mustTerms"]),
            "shouldTerms": sorted(term.strip().lower() for term in strategy["shouldTerms"]),
            "excludeTerms": sorted(term.strip().lower() for term in strategy["excludeTerms"]),
            "structuredFilters": strategy["structuredFilters"],
        }
    )


MIN_AGENT_ROUNDS = 3
MAX_AGENT_ROUNDS = 5


def _strategy_to_query_payload(strategy: NormalizedQueryPayload) -> SearchQueryPayload:
    return {
        "keyword": strategy["keyword"],
        "mustTerms": list(strategy["mustTerms"]),
        "shouldTerms": list(strategy["shouldTerms"]),
        "excludeTerms": list(strategy["excludeTerms"]),
        "structuredFilters": cast(StructuredFiltersPayload, cast(object, dict(strategy["structuredFilters"]))),
    }


def _candidate_summary_payload(shortlisted: _ShortlistedCandidate) -> JsonObject:
    return to_json_object(
        {
            "externalIdentityId": shortlisted.candidate.external_identity_id,
            "name": shortlisted.candidate.name,
            "title": shortlisted.candidate.title,
            "company": shortlisted.candidate.company,
            "location": shortlisted.candidate.location,
            "score": round(shortlisted.score, 4),
            "reason": shortlisted.reason,
            "sourceRound": shortlisted.source_round,
        }
    )


def _analyzed_candidate_trace_output(analyzed: _AnalyzedCandidate) -> JsonObject:
    return to_json_object(
        {
            "candidateId": analyzed.shortlisted.candidate.external_identity_id,
            "candidateName": analyzed.shortlisted.candidate.name,
            "score": round(analyzed.shortlisted.score, 4),
            "reason": analyzed.shortlisted.reason,
            "degraded": analyzed.shortlisted.degraded,
            "evidence": analyzed.evidence,
            "concerns": analyzed.concerns,
        }
    )


def _build_query_delta(
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


def _payload_list(value: object) -> list[object]:
    return cast(list[object], value) if isinstance(value, list) else []


def _candidate_text(candidate: CandidateData) -> str:
    resume = candidate.resume_projection
    parts = [
        candidate.name,
        candidate.title,
        candidate.company,
        candidate.location,
        candidate.summary,
        " ".join(resume["workSummaries"]),
        " ".join(resume["projectNames"]),
        " ".join(
            f"{item['company']} {item['title']} {item['summary'] or ''}"
            for item in resume["workExperience"]
        ),
        " ".join(
            f"{item['school']} {item['degree']} {item['major']}"
            for item in resume["education"]
        ),
    ]
    return " ".join(part for part in parts if part).lower()


def _heuristic_resume_match(
    *,
    candidate: CandidateData,
    strategy: NormalizedQueryPayload,
    round_no: int,
    reason_prefix: str,
) -> _AnalyzedCandidate:
    haystack = _candidate_text(candidate)
    must_hits = [term for term in strategy["mustTerms"] if term.lower() in haystack]
    should_hits = [term for term in strategy["shouldTerms"] if term.lower() in haystack]
    exclude_hits = [term for term in strategy["excludeTerms"] if term.lower() in haystack]
    score = 0.35
    if strategy["mustTerms"]:
        score += 0.35 * (len(must_hits) / max(len(strategy["mustTerms"]), 1))
    if strategy["shouldTerms"]:
        score += 0.2 * (len(should_hits) / max(len(strategy["shouldTerms"]), 1))
    if candidate.location and strategy["structuredFilters"].get("location"):
        locations = [str(item).lower() for item in strategy["structuredFilters"].get("location", [])]
        if any(location in candidate.location.lower() for location in locations):
            score += 0.05
    if exclude_hits:
        score -= 0.25
    if candidate.resume_projection["workYear"] is not None:
        score += min(candidate.resume_projection["workYear"], 10) / 200.0
    score = max(0.0, min(score, 0.99))
    reason_parts: list[str] = []
    if must_hits:
        reason_parts.append(f"命中必须项：{', '.join(must_hits[:3])}")
    if should_hits:
        reason_parts.append(f"命中核心项：{', '.join(should_hits[:3])}")
    if not reason_parts:
        reason_parts.append("与目标岗位存在启发式相关性")
    reason = f"{reason_prefix}；" + "；".join(reason_parts)
    shortlisted = _ShortlistedCandidate(
        candidate=candidate,
        score=score,
        reason=reason,
        source_round=round_no,
        degraded=True,
    )
    return _AnalyzedCandidate(
        shortlisted=shortlisted,
        prompt_text="heuristic-fallback",
        model_version="heuristic-fallback",
        prompt_version="heuristic-fallback-v1",
        evidence=must_hits[:3] + should_hits[:2],
        concerns=[f"命中排除词：{term}" for term in exclude_hits[:2]],
    )


class AgentRunsCoordinator:
    def __init__(
        self,
        *,
        uow: PlatformUnitOfWork,
        runtime_config: PlatformRuntimeConfig,
        llm: LLMPort,
        resume_source: ResumeSourcePort,
        tracer: AgentRunTracer,
    ) -> None:
        self.uow = uow
        self.runtime_config = runtime_config
        self.llm = llm
        self.resume_source = resume_source
        self.tracer = tracer

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
        resolved_model_version = resolve_llm_model_version(model_version, self.runtime_config)
        normalized_config = self._normalize_config(config)
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
                    "maxRounds": normalized_config["maxRounds"],
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

    def execute_run(self, run_id: str) -> AgentRunRecord:
        run = self.get_run(run_id)
        run.status = "running"
        run.error_code = None
        run.error_message = None
        self.uow.agent_runs.save_run(run)
        self.uow.commit()

        retained_candidates: list[_ShortlistedCandidate] = []
        strategy_offsets: dict[str, int] = {}
        no_progress_rounds = 0
        previous_shortlist_signature: tuple[str, ...] = ()
        stop_reason: str | None = None

        with self.tracer.trace_run(
            run_id=run.id,
            jd_text=run.jd_text,
            sourcing_preference_text=run.sourcing_preference_text,
            model_version=run.model_version,
            prompt_version=run.prompt_version,
        ) as trace_handle:
            run.langfuse_trace_id = trace_handle.trace_id
            run.langfuse_trace_url = trace_handle.trace_url
            self.uow.agent_runs.save_run(run)
            self.uow.commit()

            try:
                strategy = self._extract_strategy(run, trace_handle)

                for round_no, fetch_size in enumerate(run.config["roundFetchSchedule"], start=1):
                    run.current_round = round_no
                    self.uow.agent_runs.save_run(run)
                    self.uow.commit()
                    current_query = _strategy_to_query_payload(strategy)
                    with trace_handle.start_observation(
                        name=f"round-{round_no}",
                        as_type="chain",
                        input=to_json_object(
                            {
                                "roundNo": round_no,
                                "fetchSize": fetch_size,
                                "currentQuery": current_query,
                            }
                        ),
                        metadata=to_json_object(
                            {
                                "compactRoundLedger": self._build_compact_round_ledger(run),
                            }
                        ),
                    ) as round_trace:
                        search_result = self._search_round(
                            run=run,
                            round_no=round_no,
                            fetch_size=fetch_size,
                            strategy=strategy,
                            strategy_offsets=strategy_offsets,
                            trace_parent=round_trace,
                        )
                        seen_resume_count_before = len(run.seen_resume_ids)
                        new_candidates, duplicate_ids = self._dedupe_round_candidates(run, search_result.candidates)
                        dedupe_output = to_json_object(
                            {
                                "admittedCount": len(new_candidates),
                                "admittedResumeIds": [
                                    candidate.external_identity_id for candidate in new_candidates
                                ],
                                "duplicateCount": len(duplicate_ids),
                                "duplicateResumeIds": duplicate_ids,
                                "seenResumeCountAfter": len(run.seen_resume_ids),
                            }
                        )
                        with round_trace.start_observation(
                            name=f"dedupe-round-{round_no}",
                            as_type="span",
                            input=to_json_object(
                                {
                                    "candidateIds": [
                                        candidate.external_identity_id for candidate in search_result.candidates
                                    ],
                                    "seenResumeCountBefore": seen_resume_count_before,
                                }
                            ),
                            metadata=to_json_object({"currentQuery": current_query}),
                        ) as dedupe_trace:
                            dedupe_trace.update(output=dedupe_output)
                        self._append_step(
                            run,
                            round_no=round_no,
                            step_type="dedupe",
                            title=f"Round {round_no} dedupe",
                            status="completed",
                            summary=f"跳过 {len(duplicate_ids)} 份重复简历，放行 {len(new_candidates)} 份新简历进入分析。",
                            payload={
                                "admittedResumeIds": [candidate.external_identity_id for candidate in new_candidates],
                                "duplicateResumeIds": duplicate_ids,
                                "seenResumeCount": len(run.seen_resume_ids),
                            },
                        )

                        previous_retained_payload = [
                            _candidate_summary_payload(candidate) for candidate in retained_candidates
                        ]
                        analyzed_candidates = self._analyze_round_candidates(
                            run=run,
                            round_no=round_no,
                            strategy=strategy,
                            candidates=new_candidates,
                            trace_parent=round_trace,
                        )
                        retained_candidates = self._rank_candidates(
                            retained_candidates=retained_candidates,
                            analyzed_candidates=analyzed_candidates,
                            final_top_k=run.config["finalTopK"],
                        )
                        run.final_shortlist = [candidate.to_payload() for candidate in retained_candidates]
                        self.uow.agent_runs.save_run(run)
                        self.uow.commit()
                        analyzed_candidate_ids = [
                            analyzed.shortlisted.candidate.external_identity_id for analyzed in analyzed_candidates
                        ]
                        retained_candidate_ids = [
                            candidate.candidate.external_identity_id for candidate in retained_candidates
                        ]
                        retained_payload = [
                            _candidate_summary_payload(candidate) for candidate in retained_candidates
                        ]
                        dropped_candidate_ids = [
                            candidate_id
                            for candidate_id in {
                                *analyzed_candidate_ids,
                                *[payload["externalIdentityId"] for payload in previous_retained_payload],
                            }
                            if candidate_id not in set(retained_candidate_ids)
                        ]
                        shortlist_input = to_json_object(
                            {
                                "previousRetainedCandidates": previous_retained_payload,
                                "analyzedCandidates": [
                                    _analyzed_candidate_trace_output(analyzed) for analyzed in analyzed_candidates
                                ],
                                "finalTopK": run.config["finalTopK"],
                            }
                        )
                        shortlist_output = to_json_object(
                            {
                                "retainedCount": len(retained_candidates),
                                "retainedCandidates": retained_payload,
                                "droppedCount": len(dropped_candidate_ids),
                                "droppedCandidateIds": dropped_candidate_ids,
                            }
                        )
                        with round_trace.start_observation(
                            name=f"shortlist-round-{round_no}",
                            as_type="span",
                            input=shortlist_input,
                            metadata=to_json_object({"currentQuery": current_query}),
                        ) as shortlist_trace:
                            shortlist_trace.update(output=shortlist_output)
                        self._append_step(
                            run,
                            round_no=round_no,
                            step_type="shortlist",
                            title=f"Round {round_no} shortlist",
                            status="completed",
                            summary=(
                                f"第 {round_no} 轮保留了 {len(retained_candidates)} 份候选，"
                                f"本轮新增分析 {len(analyzed_candidates)} 份。"
                            ),
                            payload={
                                "retainedCount": len(retained_candidates),
                                "retainedCandidates": retained_payload,
                                "analyzedCandidateIds": analyzed_candidate_ids,
                                "retainedCandidateIds": retained_candidate_ids,
                            },
                        )

                        shortlist_signature = tuple(
                            candidate.candidate.external_identity_id for candidate in retained_candidates
                        )
                        if len(new_candidates) == 0 or shortlist_signature == previous_shortlist_signature:
                            no_progress_rounds += 1
                        else:
                            no_progress_rounds = 0
                        previous_shortlist_signature = shortlist_signature

                        should_stop, round_stop_reason = self._should_stop_after_round(
                            run=run,
                            round_no=round_no,
                            no_progress_rounds=no_progress_rounds,
                        )
                        if should_stop:
                            stop_reason = round_stop_reason
                            self._append_step(
                                run,
                                round_no=round_no,
                                step_type="stop",
                                title=f"Round {round_no} stop",
                                status="completed",
                                summary=round_stop_reason,
                                payload={"reason": round_stop_reason, "source": "rule"},
                            )
                            self._trace_stop(
                                round_trace=round_trace,
                                round_no=round_no,
                                current_query=current_query,
                                source="rule",
                                reason=round_stop_reason,
                            )
                            round_trace.update(
                                output=to_json_object(
                                    {
                                        "retainedCount": len(retained_candidates),
                                        "newCandidateCount": len(new_candidates),
                                        "continueSearch": False,
                                        "stopReason": round_stop_reason,
                                    }
                                ),
                                metadata=to_json_object(
                                    {
                                        "compactRoundLedger": self._build_compact_round_ledger(run),
                                    }
                                ),
                            )
                            break

                        reflection = self._reflect_round(
                            run=run,
                            round_no=round_no,
                            strategy=strategy,
                            retained_candidates=retained_candidates,
                            new_candidate_count=len(new_candidates),
                            trace_parent=round_trace,
                        )
                        if not reflection.continue_search:
                            stop_reason = reflection.reason
                            self._append_step(
                                run,
                                round_no=round_no,
                                step_type="stop",
                                title=f"Round {round_no} stop",
                                status="completed",
                                summary=reflection.reason,
                                payload={"reason": reflection.reason, "source": "reflection"},
                            )
                            self._trace_stop(
                                round_trace=round_trace,
                                round_no=round_no,
                                current_query=current_query,
                                source="reflection",
                                reason=reflection.reason,
                            )
                            round_trace.update(
                                output=to_json_object(
                                    {
                                        "retainedCount": len(retained_candidates),
                                        "newCandidateCount": len(new_candidates),
                                        "continueSearch": False,
                                        "stopReason": reflection.reason,
                                    }
                                ),
                                metadata=to_json_object(
                                    {
                                        "compactRoundLedger": self._build_compact_round_ledger(run),
                                    }
                                ),
                            )
                            break
                        next_strategy = self._strategy_from_reflection(run.jd_text, reflection)
                        next_query = _strategy_to_query_payload(next_strategy)
                        next_signature = _strategy_signature(next_strategy)
                        if (
                            round_no >= MIN_AGENT_ROUNDS
                            and next_signature == _strategy_signature(strategy)
                            and no_progress_rounds >= 1
                        ):
                            stop_reason = "下一轮查询与上一轮实质相同且没有新增价值，系统停止继续检索。"
                            self._append_step(
                                run,
                                round_no=round_no,
                                step_type="stop",
                                title=f"Round {round_no} duplicate strategy blocked",
                                status="completed",
                                summary=stop_reason,
                                payload={
                                    "reason": stop_reason,
                                    "source": "duplicate-strategy",
                                    "duplicateStrategy": next_query,
                                },
                            )
                            self._trace_stop(
                                round_trace=round_trace,
                                round_no=round_no,
                                current_query=current_query,
                                source="duplicate-strategy",
                                reason=stop_reason,
                            )
                            round_trace.update(
                                output=to_json_object(
                                    {
                                        "retainedCount": len(retained_candidates),
                                        "newCandidateCount": len(new_candidates),
                                        "continueSearch": False,
                                        "stopReason": stop_reason,
                                    }
                                ),
                                metadata=to_json_object(
                                    {
                                        "compactRoundLedger": self._build_compact_round_ledger(run),
                                    }
                                ),
                            )
                            break
                        strategy = next_strategy
                        round_trace.update(
                            output=to_json_object(
                                {
                                    "retainedCount": len(retained_candidates),
                                    "newCandidateCount": len(new_candidates),
                                    "continueSearch": True,
                                    "nextRoundQuery": next_query,
                                }
                            ),
                            metadata=to_json_object(
                                {
                                    "compactRoundLedger": self._build_compact_round_ledger(run),
                                }
                            ),
                        )

                run.status = "completed"
                run.finished_at = now_utc()
                self.uow.agent_runs.save_run(run)
                self._append_step(
                    run,
                    round_no=run.current_round or None,
                    step_type="finalize",
                    title="Finalize shortlist",
                    status="completed",
                    summary=f"最终 shortlist 选出了 {len(run.final_shortlist)} 份简历。",
                    payload={"finalShortlist": run.final_shortlist},
                )
                with trace_handle.start_observation(
                    name="finalize",
                    as_type="span",
                    input=to_json_object(
                        {
                            "currentRound": run.current_round,
                            "seenResumeCount": len(run.seen_resume_ids),
                            "finalShortlistCount": len(run.final_shortlist),
                        }
                    ),
                    metadata=to_json_object(
                        {
                            "compactRoundLedger": self._build_compact_round_ledger(run),
                        }
                    ),
                ) as finalize_trace:
                    finalize_trace.update(
                        output=to_json_object(
                            {
                                "status": run.status,
                                "finalShortlist": run.final_shortlist,
                                "stopReason": stop_reason,
                            }
                        )
                    )
                trace_handle.update_root(
                    output=to_json_object(
                        {
                            "status": run.status,
                            "currentRound": run.current_round,
                            "finalShortlist": run.final_shortlist,
                            "stopReason": stop_reason,
                        }
                    ),
                    metadata=to_json_object(
                        {
                            "seenResumeCount": len(run.seen_resume_ids),
                            "config": run.config,
                        }
                    ),
                )
                self._audit(
                    "system",
                    "agent_run",
                    run.id,
                    "agent_run.completed",
                    "success",
                    to_json_object(
                        {
                            "rounds": run.current_round,
                            "finalShortlistCount": len(run.final_shortlist),
                            "langfuseTraceId": run.langfuse_trace_id,
                        }
                    ),
                )
                self.uow.commit()
                return run
            except (ExternalDependencyError, TransientDependencyError, ValidationError) as exc:
                run.status = "failed"
                run.error_code = exc.code
                run.error_message = exc.message
                run.finished_at = now_utc()
                self.uow.agent_runs.save_run(run)
                trace_handle.update_root(
                    output={"status": run.status, "errorCode": exc.code, "errorMessage": exc.message},
                    level="ERROR",
                    status_message=exc.message,
                )
                self._audit(
                    "system",
                    "agent_run",
                    run.id,
                    "agent_run.failed",
                    "failure",
                    to_json_object({"errorCode": exc.code, "errorMessage": exc.message}),
                )
                self.uow.commit()
                return run

    def _normalize_config(self, config: AgentRunConfigPayload | None) -> AgentRunConfigPayload:
        raw_max_rounds = self.runtime_config.default_agent_max_rounds if config is None else config["maxRounds"]
        raw_final_top_k = self.runtime_config.default_agent_final_top_k if config is None else config["finalTopK"]
        raw_schedule = (
            list(self.runtime_config.default_agent_round_fetch_schedule)
            if config is None
            else list(config["roundFetchSchedule"])
        )
        if raw_max_rounds < MIN_AGENT_ROUNDS or raw_max_rounds > MAX_AGENT_ROUNDS:
            raise ValidationError(
                "INVALID_AGENT_CONFIG",
                f"maxRounds must be between {MIN_AGENT_ROUNDS} and {MAX_AGENT_ROUNDS}.",
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

    def _extract_strategy(self, run: AgentRunRecord, trace_handle: AgentRunTraceHandle) -> NormalizedQueryPayload:
        try:
            strategy_data = self.llm.extract_agent_search_strategy(
                run.jd_text,
                run.sourcing_preference_text,
                run.model_version,
                run.prompt_version,
            )
        except (ExternalDependencyError, TransientDependencyError) as exc:
            strategy_data = self._fallback_strategy(
                jd_text=run.jd_text,
                sourcing_preference_text=run.sourcing_preference_text,
                model_version=run.model_version,
                prompt_version=run.prompt_version,
                error_message=exc.message,
            )
        strategy = self._strategy_from_extraction(run.jd_text, strategy_data)
        round_1_query = _strategy_to_query_payload(strategy)
        with trace_handle.start_observation(
            name="extract-search-strategy",
            as_type="generation",
            input=strategy_data.prompt_text,
            metadata=to_json_object(
                {
                    "jdText": run.jd_text,
                    "sourcingPreferenceText": run.sourcing_preference_text,
                    "summary": strategy_data.summary,
                }
            ),
            model=strategy_data.model_version,
            version=strategy_data.prompt_version,
        ) as observation:
            observation.update(
                output=to_json_object(
                    {
                        "mustRequirements": strategy_data.must_requirements,
                        "coreRequirements": strategy_data.core_requirements,
                        "bonusRequirements": strategy_data.bonus_requirements,
                        "excludeSignals": strategy_data.exclude_signals,
                        "round1Query": round_1_query,
                    }
                )
            )
        self._append_step(
            run,
            round_no=None,
            step_type="strategy",
            title="Extract search strategy",
            status="completed",
            summary=strategy_data.summary,
            payload={
                "mustRequirements": strategy_data.must_requirements,
                "coreRequirements": strategy_data.core_requirements,
                "bonusRequirements": strategy_data.bonus_requirements,
                "excludeSignals": strategy_data.exclude_signals,
                "round1Query": round_1_query,
            },
        )
        return strategy

    def _search_round(
        self,
        *,
        run: AgentRunRecord,
        round_no: int,
        fetch_size: int,
        strategy: NormalizedQueryPayload,
        strategy_offsets: dict[str, int],
        trace_parent: AgentTraceObservation,
    ) -> SearchPageData:
        strategy_signature = _strategy_signature(strategy)
        offset = strategy_offsets.get(strategy_signature, 0)
        page_no = (offset // fetch_size) + 1
        with trace_parent.start_observation(
            name=f"cts-search-round-{round_no}",
            as_type="tool",
            input=to_json_object(
                {
                    "query": _strategy_to_query_payload(strategy),
                    "normalizedQuery": strategy,
                    "pageNo": page_no,
                    "pageSize": fetch_size,
                    "offset": offset,
                }
            ),
            metadata=to_json_object({"tool": "cts.search_candidates"}),
        ) as observation:
            result = self.resume_source.search_candidates(strategy, page_no, fetch_size)
            observation.update(
                output=to_json_object(
                    {
                        "status": result.status,
                        "total": result.total,
                        "returnedCount": len(result.candidates),
                        "candidateIds": [candidate.external_identity_id for candidate in result.candidates],
                        "errorCode": result.error_code,
                        "errorMessage": result.error_message,
                        "offset": offset,
                    }
                ),
                metadata=to_json_object(
                    {
                        "upstreamRequest": result.upstream_request,
                        "upstreamResponse": result.upstream_response,
                    }
                ),
                level="ERROR" if result.error_code else None,
                status_message=result.error_message,
            )
        self._append_step(
            run,
            round_no=round_no,
            step_type="search",
            title=f"Round {round_no} CTS search",
            status=result.status,
            summary=f"CTS 返回 {len(result.candidates)} 份候选（total={result.total}）。",
            payload={
                "roundQuery": _strategy_to_query_payload(strategy),
                "normalizedQuery": strategy,
                "pageNo": result.page_no,
                "pageSize": result.page_size,
                "offset": offset,
                "total": result.total,
                "returnedCount": len(result.candidates),
                "candidateIds": [candidate.external_identity_id for candidate in result.candidates],
                "errorCode": result.error_code,
                "errorMessage": result.error_message,
            },
        )
        if result.error_code:
            raise ExternalDependencyError(result.error_code, result.error_message or "CTS search failed.")
        strategy_offsets[strategy_signature] = offset + len(result.candidates)
        return result

    def _dedupe_round_candidates(
        self,
        run: AgentRunRecord,
        candidates: list[CandidateData],
    ) -> tuple[list[CandidateData], list[str]]:
        seen_ids = set(run.seen_resume_ids)
        duplicate_ids: list[str] = []
        admitted: list[CandidateData] = []
        round_seen: set[str] = set()
        for candidate in candidates:
            candidate_id = candidate.external_identity_id
            if candidate_id in seen_ids or candidate_id in round_seen:
                duplicate_ids.append(candidate_id)
                continue
            admitted.append(candidate)
            round_seen.add(candidate_id)
            seen_ids.add(candidate_id)
        run.seen_resume_ids = list(seen_ids)
        self.uow.agent_runs.save_run(run)
        self.uow.commit()
        return admitted, duplicate_ids

    def _analyze_round_candidates(
        self,
        *,
        run: AgentRunRecord,
        round_no: int,
        strategy: NormalizedQueryPayload,
        candidates: list[CandidateData],
        trace_parent: AgentTraceObservation,
    ) -> list[_AnalyzedCandidate]:
        if not candidates:
            with trace_parent.start_observation(
                name=f"analysis-round-{round_no}",
                as_type="chain",
                input=to_json_object(
                    {
                        "roundNo": round_no,
                        "candidateIds": [],
                        "currentQuery": _strategy_to_query_payload(strategy),
                    }
                ),
            ) as analysis_trace:
                analysis_trace.update(output=to_json_object({"analyzedCount": 0, "analyses": []}))
            self._append_step(
                run,
                round_no=round_no,
                step_type="analysis",
                title=f"Round {round_no} analysis",
                status="completed",
                summary="本轮没有新的候选进入分析。",
                payload={"analyses": []},
            )
            return []
        with ThreadPoolExecutor(max_workers=min(len(candidates), 4)) as executor:
            futures = [
                executor.submit(self._analyze_candidate, run, round_no, strategy, candidate)
                for candidate in candidates
            ]
            analyzed_candidates = [future.result() for future in futures]
        analyses_payload: list[JsonObject] = []
        with trace_parent.start_observation(
            name=f"analysis-round-{round_no}",
            as_type="chain",
            input=to_json_object(
                {
                    "roundNo": round_no,
                    "candidateIds": [candidate.external_identity_id for candidate in candidates],
                    "currentQuery": _strategy_to_query_payload(strategy),
                }
            ),
        ) as analysis_trace:
            for analyzed in analyzed_candidates:
                with analysis_trace.start_observation(
                    name=f"analyze-resume-{analyzed.shortlisted.candidate.external_identity_id}",
                    as_type="generation",
                    input=analyzed.prompt_text,
                    metadata=to_json_object(
                        {
                            "roundNo": round_no,
                            "candidateId": analyzed.shortlisted.candidate.external_identity_id,
                            "candidateName": analyzed.shortlisted.candidate.name,
                        }
                    ),
                    model=analyzed.model_version,
                    version=analyzed.prompt_version,
                ) as observation:
                    observation.update(output=_analyzed_candidate_trace_output(analyzed))
                analyses_payload.append(
                    {
                        "candidateId": analyzed.shortlisted.candidate.external_identity_id,
                        "name": analyzed.shortlisted.candidate.name,
                        "score": round(analyzed.shortlisted.score, 4),
                        "reason": analyzed.shortlisted.reason,
                        "degraded": analyzed.shortlisted.degraded,
                    }
                )
            analysis_trace.update(
                output=to_json_object(
                    {
                        "analyzedCount": len(analyzed_candidates),
                        "analyses": analyses_payload,
                    }
                )
            )
        self._append_step(
            run,
            round_no=round_no,
            step_type="analysis",
            title=f"Round {round_no} analysis",
            status="completed",
            summary=f"已完成 {len(analyzed_candidates)} 份新简历的匹配分析。",
            payload={"analyses": analyses_payload},
        )
        return analyzed_candidates

    def _analyze_candidate(
        self,
        run: AgentRunRecord,
        round_no: int,
        strategy: NormalizedQueryPayload,
        candidate: CandidateData,
    ) -> _AnalyzedCandidate:
        try:
            match = self.llm.analyze_resume_match(
                run.jd_text,
                run.sourcing_preference_text,
                strategy,
                candidate,
                run.model_version,
                run.prompt_version,
            )
            shortlisted = _ShortlistedCandidate(
                candidate=candidate,
                score=max(0.0, min(match.score, 0.99)),
                reason=match.summary,
                source_round=round_no,
                degraded=False,
            )
            return _AnalyzedCandidate(
                shortlisted=shortlisted,
                prompt_text=match.prompt_text,
                model_version=match.model_version,
                prompt_version=match.prompt_version,
                evidence=match.evidence,
                concerns=match.concerns,
            )
        except (ExternalDependencyError, TransientDependencyError) as exc:
            return _heuristic_resume_match(
                candidate=candidate,
                strategy=strategy,
                round_no=round_no,
                reason_prefix=f"AI 降级启发式匹配：{exc.code}",
            )

    def _rank_candidates(
        self,
        *,
        retained_candidates: list[_ShortlistedCandidate],
        analyzed_candidates: list[_AnalyzedCandidate],
        final_top_k: int,
    ) -> list[_ShortlistedCandidate]:
        merged = retained_candidates + [item.shortlisted for item in analyzed_candidates]
        merged.sort(
            key=lambda item: (
                -item.score,
                item.source_round,
                item.candidate.external_identity_id,
            )
        )
        deduped: list[_ShortlistedCandidate] = []
        seen_ids: set[str] = set()
        for candidate in merged:
            candidate_id = candidate.candidate.external_identity_id
            if candidate_id in seen_ids:
                continue
            seen_ids.add(candidate_id)
            deduped.append(candidate)
            if len(deduped) >= final_top_k:
                break
        return deduped

    def _should_stop_after_round(
        self,
        *,
        run: AgentRunRecord,
        round_no: int,
        no_progress_rounds: int,
    ) -> tuple[bool, str]:
        if round_no >= run.config["maxRounds"]:
            return True, "已达到配置的最大轮次，停止继续检索。"
        if round_no >= MIN_AGENT_ROUNDS and no_progress_rounds >= 2:
            return True, "连续两轮没有新增价值，停止继续检索。"
        return False, ""

    def _reflect_round(
        self,
        *,
        run: AgentRunRecord,
        round_no: int,
        strategy: NormalizedQueryPayload,
        retained_candidates: list[_ShortlistedCandidate],
        new_candidate_count: int,
        trace_parent: AgentTraceObservation,
    ) -> SearchReflectionData:
        round_ledger = self._build_compact_round_ledger(run)
        current_query = _strategy_to_query_payload(strategy)
        try:
            reflection = self.llm.reflect_search_progress(
                run.jd_text,
                run.sourcing_preference_text,
                strategy,
                round_ledger,
                round_no,
                run.config["maxRounds"],
                new_candidate_count,
                len(run.seen_resume_ids),
                run.model_version,
                run.prompt_version,
            )
        except (ExternalDependencyError, TransientDependencyError) as exc:
            reflection = self._fallback_reflection(
                strategy=strategy,
                round_no=round_no,
                max_rounds=run.config["maxRounds"],
                new_candidate_count=new_candidate_count,
                error_message=exc.message,
            )
        minimum_round_override_applied = False
        if not reflection.continue_search and round_no < MIN_AGENT_ROUNDS:
            reflection = SearchReflectionData(
                prompt_text=reflection.prompt_text,
                model_version=reflection.model_version,
                prompt_version=reflection.prompt_version,
                continue_search=True,
                reason=(
                    f"{reflection.reason}；未达到最少 {MIN_AGENT_ROUNDS} 轮，系统继续执行下一轮。"
                ),
                next_round_goal="继续执行直到达到最少轮次，再评估是否提前停止。",
                next_round_query=reflection.next_round_query,
            )
            minimum_round_override_applied = True
        next_strategy = self._strategy_from_reflection(run.jd_text, reflection)
        next_query = _strategy_to_query_payload(next_strategy)
        query_delta = _build_query_delta(current_query, next_query)
        with trace_parent.start_observation(
            name=f"reflect-round-{round_no}",
            as_type="generation",
            input=reflection.prompt_text,
            metadata=to_json_object(
                {
                    "roundNo": round_no,
                    "currentQuery": current_query,
                    "compactRoundLedger": round_ledger,
                    "retainedCandidateCount": len(retained_candidates),
                    "minimumRoundsOverrideApplied": minimum_round_override_applied,
                }
            ),
            model=reflection.model_version,
            version=reflection.prompt_version,
        ) as observation:
            observation.update(
                output=to_json_object(
                    {
                        "continueSearch": reflection.continue_search,
                        "reason": reflection.reason,
                        "nextRoundGoal": reflection.next_round_goal,
                        "nextRoundQuery": next_query,
                        "queryDelta": query_delta,
                    }
                )
            )
        self._append_step(
            run,
            round_no=round_no,
            step_type="reflection",
            title=f"Round {round_no} reflection",
            status="completed",
            summary=reflection.reason,
            payload={
                "continueSearch": reflection.continue_search,
                "reason": reflection.reason,
                "nextRoundGoal": reflection.next_round_goal,
                "nextRoundQuery": next_query,
                "queryDelta": query_delta,
                "minimumRoundsOverrideApplied": minimum_round_override_applied,
            },
        )
        return reflection

    def _trace_stop(
        self,
        *,
        round_trace: AgentTraceObservation,
        round_no: int,
        current_query: SearchQueryPayload,
        source: str,
        reason: str,
    ) -> None:
        with round_trace.start_observation(
            name=f"stop-round-{round_no}",
            as_type="span",
            input=to_json_object(
                {
                    "roundNo": round_no,
                    "source": source,
                    "currentQuery": current_query,
                }
            ),
            level="WARNING",
            status_message=reason,
        ) as stop_trace:
            stop_trace.update(
                output=to_json_object(
                    {
                        "source": source,
                        "reason": reason,
                    }
                )
            )

    def _append_step(
        self,
        run: AgentRunRecord,
        *,
        round_no: int | None,
        step_type: str,
        title: str,
        status: str,
        summary: str,
        payload: dict[str, object],
    ) -> None:
        occurred_at = now_utc()
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=UTC)
        step: AgentRunStepPayload = {
            "stepNo": len(run.steps) + 1,
            "roundNo": round_no,
            "stepType": step_type,
            "title": title,
            "status": status,
            "summary": summary,
            "payload": to_json_object(payload),
            "occurredAt": occurred_at.isoformat(),
        }
        run.steps = [*run.steps, step]
        self.uow.agent_runs.save_run(run)
        self.uow.commit()

    def _build_compact_round_ledger(self, run: AgentRunRecord) -> list[dict[str, object]]:
        extraction_summary = next(
            (step["payload"] for step in run.steps if step["stepType"] == "strategy" and step["roundNo"] is None),
            None,
        )
        ledger_by_round: dict[int, dict[str, object]] = {}
        for step in run.steps:
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
                admitted_resume_ids = _payload_list(step["payload"].get("admittedResumeIds", []))
                duplicate_resume_ids = _payload_list(step["payload"].get("duplicateResumeIds", []))
                round_entry["dedupe"] = {
                    "admittedCount": len(admitted_resume_ids),
                    "duplicateCount": len(duplicate_resume_ids),
                    "duplicateResumeIds": duplicate_resume_ids,
                }
            elif step["stepType"] == "analysis":
                analyses = _payload_list(step["payload"].get("analyses", []))
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

    def _strategy_from_extraction(self, jd_text: str, strategy_data: AgentSearchStrategyData) -> NormalizedQueryPayload:
        return self._build_strategy(
            jd_text=jd_text,
            keyword=strategy_data.round_1_query["keyword"],
            must_terms=strategy_data.round_1_query["mustTerms"],
            should_terms=strategy_data.round_1_query["shouldTerms"],
            exclude_terms=strategy_data.round_1_query["excludeTerms"],
            structured_filters=strategy_data.round_1_query["structuredFilters"],
        )

    def _strategy_from_reflection(self, jd_text: str, reflection: SearchReflectionData) -> NormalizedQueryPayload:
        return self._build_strategy(
            jd_text=jd_text,
            keyword=reflection.next_round_query["keyword"],
            must_terms=reflection.next_round_query["mustTerms"],
            should_terms=reflection.next_round_query["shouldTerms"],
            exclude_terms=reflection.next_round_query["excludeTerms"],
            structured_filters=reflection.next_round_query["structuredFilters"],
        )

    @staticmethod
    def _build_strategy(
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
            raise ValidationError("AGENT_SEARCH_STRATEGY_INVALID", "The extracted search strategy did not contain any keyword.")
        return {
            "jd": jd_text,
            "mustTerms": normalized_must_terms or [resolved_keyword],
            "shouldTerms": normalized_should_terms,
            "excludeTerms": normalized_exclude_terms,
            "structuredFilters": structured_filters,
            "keyword": resolved_keyword,
        }

    def _fallback_strategy(
        self,
        *,
        jd_text: str,
        sourcing_preference_text: str,
        model_version: str,
        prompt_version: str,
        error_message: str,
    ) -> AgentSearchStrategyData:
        source_text = f"{jd_text}\n{sourcing_preference_text}"
        normalized_terms = [
            token.strip(" ,.;:()[]{}")
            for token in source_text.replace("/", " ").replace("|", " ").split()
        ]
        keyword_terms: list[str] = []
        for token in normalized_terms:
            if len(token) < 2:
                continue
            if token not in keyword_terms:
                keyword_terms.append(token)
            if len(keyword_terms) >= 6:
                break
        must_terms = keyword_terms[:3] or ["目标岗位"]
        should_terms = keyword_terms[3:6]
        keyword = " ".join(must_terms + should_terms).strip()
        return AgentSearchStrategyData(
            prompt_text=f"中文启发式降级首轮策略 model={model_version} prompt={prompt_version}",
            model_version="heuristic-fallback",
            prompt_version="heuristic-fallback-v1",
            must_requirements=must_terms,
            core_requirements=should_terms,
            bonus_requirements=[],
            exclude_signals=[],
            round_1_query={
                "keyword": keyword or must_terms[0],
                "mustTerms": must_terms,
                "shouldTerms": should_terms,
                "excludeTerms": [],
                "structuredFilters": {"page": 1, "pageSize": 10},
            },
            summary=f"首轮策略提取降级，已回退到启发式首轮查询：{error_message}",
        )

    def _fallback_reflection(
        self,
        *,
        strategy: NormalizedQueryPayload,
        round_no: int,
        max_rounds: int,
        new_candidate_count: int,
        error_message: str,
    ) -> SearchReflectionData:
        continue_search = new_candidate_count > 0 and round_no < max_rounds
        filters = cast(StructuredFiltersPayload, cast(object, dict(strategy["structuredFilters"])))
        next_query: SearchQueryPayload = {
            "keyword": strategy["keyword"],
            "mustTerms": list(strategy["mustTerms"]),
            "shouldTerms": list(strategy["shouldTerms"]),
            "excludeTerms": list(strategy["excludeTerms"]),
            "structuredFilters": filters,
        }
        return SearchReflectionData(
            prompt_text="中文启发式降级反思",
            model_version="heuristic-fallback",
            prompt_version="heuristic-fallback-v1",
            continue_search=continue_search,
            reason=f"反思步骤降级，先沿当前方向继续执行：{error_message}",
            next_round_goal="在降级模式下继续收集新候选。",
            next_round_query=next_query,
        )

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
