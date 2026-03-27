from __future__ import annotations

from copy import deepcopy
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from cvm_platform.application.dto import AgentRunRecord
from cvm_platform.application.agent_runs import build_search_strategy, effective_agent_runtime_config
from cvm_platform.domain.types import (
    AgentRunConfigPayload,
    AgentRuntimeConfigEntryPayload,
    AgentRuntimeConfigPayload,
    AgentRunStepPayload,
    AgentShortlistCandidatePayload,
    AgentThinkingEffort,
    CandidateData,
    NormalizedQueryPayload,
    ResumeProjectionPayload,
    SearchPageData,
    SearchQueryPayload,
    StructuredFiltersPayload,
    to_json_object,
)


STRICT_MODEL_CONFIG = ConfigDict(extra="forbid", strict=True)


class StructuredFiltersModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    page: int = 1
    pageSize: int = 10
    location: list[str] | None = None
    degree: int | None = None
    schoolType: int | None = None
    workExperienceRange: int | None = None
    position: str | None = None
    workContent: str | None = None
    company: str | None = None
    school: str | None = None

    def to_payload(self) -> StructuredFiltersPayload:
        return cast(
            StructuredFiltersPayload,
            cast(object, self.model_dump(exclude_none=True)),
        )


class SearchQueryModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    keyword: str = Field(min_length=1)
    mustTerms: list[str] = Field(min_length=1)
    shouldTerms: list[str] = Field(default_factory=list)
    excludeTerms: list[str] = Field(default_factory=list)
    structuredFilters: StructuredFiltersModel = Field(default_factory=StructuredFiltersModel)

    def to_payload(self) -> SearchQueryPayload:
        return {
            "keyword": self.keyword,
            "mustTerms": list(self.mustTerms),
            "shouldTerms": list(self.shouldTerms),
            "excludeTerms": list(self.excludeTerms),
            "structuredFilters": self.structuredFilters.to_payload(),
        }


class NormalizedStrategyModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    jd: str = Field(min_length=1)
    keyword: str = Field(min_length=1)
    mustTerms: list[str] = Field(min_length=1)
    shouldTerms: list[str] = Field(default_factory=list)
    excludeTerms: list[str] = Field(default_factory=list)
    structuredFilters: StructuredFiltersModel = Field(default_factory=StructuredFiltersModel)

    @classmethod
    def from_payload(cls, payload: NormalizedQueryPayload) -> "NormalizedStrategyModel":
        return cls.model_validate(payload)

    def to_payload(self) -> NormalizedQueryPayload:
        return {
            "jd": self.jd,
            "keyword": self.keyword,
            "mustTerms": list(self.mustTerms),
            "shouldTerms": list(self.shouldTerms),
            "excludeTerms": list(self.excludeTerms),
            "structuredFilters": self.structuredFilters.to_payload(),
        }


class StrategyExtractorOutputModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    mustRequirements: list[str] = Field(min_length=1)
    coreRequirements: list[str] = Field(default_factory=list)
    bonusRequirements: list[str] = Field(default_factory=list)
    excludeSignals: list[str] = Field(default_factory=list)
    round1Query: SearchQueryModel
    summary: str = Field(min_length=1)

    def to_normalized_strategy(self, jd_text: str) -> NormalizedStrategyModel:
        return NormalizedStrategyModel.model_validate(
            build_search_strategy(
                jd_text=jd_text,
                keyword=self.round1Query.keyword,
                must_terms=list(self.round1Query.mustTerms),
                should_terms=list(self.round1Query.shouldTerms),
                exclude_terms=list(self.round1Query.excludeTerms),
                structured_filters=self.round1Query.structuredFilters.to_payload(),
            )
        )


class ResumeMatcherOutputModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    score: float = Field(ge=0.0, le=1.0)
    summary: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)


class SearchReflectorOutputModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    continueSearch: bool
    reason: str = Field(min_length=1)
    nextRoundGoal: str = Field(min_length=1)
    nextRoundQuery: SearchQueryModel

    def to_normalized_strategy(self, jd_text: str) -> NormalizedStrategyModel:
        return NormalizedStrategyModel.model_validate(
            build_search_strategy(
                jd_text=jd_text,
                keyword=self.nextRoundQuery.keyword,
                must_terms=list(self.nextRoundQuery.mustTerms),
                should_terms=list(self.nextRoundQuery.shouldTerms),
                exclude_terms=list(self.nextRoundQuery.excludeTerms),
                structured_filters=self.nextRoundQuery.structuredFilters.to_payload(),
            )
        )


class WorkerCandidateModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    externalIdentityId: str
    name: str
    title: str
    company: str
    location: str
    summary: str
    email: str
    phone: str
    resumeProjection: ResumeProjectionPayload

    @classmethod
    def from_domain(cls, candidate: CandidateData) -> "WorkerCandidateModel":
        return cls(
            externalIdentityId=candidate.external_identity_id,
            name=candidate.name,
            title=candidate.title,
            company=candidate.company,
            location=candidate.location,
            summary=candidate.summary,
            email=candidate.email,
            phone=candidate.phone,
            resumeProjection=candidate.resume_projection,
        )

    def to_domain(self) -> CandidateData:
        return CandidateData(
            external_identity_id=self.externalIdentityId,
            name=self.name,
            title=self.title,
            company=self.company,
            location=self.location,
            summary=self.summary,
            email=self.email,
            phone=self.phone,
            resume_projection=self.resumeProjection,
        )


class WorkerSearchPageModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "failed"]
    total: int
    pageNo: int
    pageSize: int
    candidates: list[WorkerCandidateModel]
    upstreamRequest: dict[str, object]
    upstreamResponse: dict[str, object]
    errorCode: str | None = None
    errorMessage: str | None = None

    @classmethod
    def from_domain(cls, page: SearchPageData) -> "WorkerSearchPageModel":
        return cls(
            status=page.status,
            total=page.total,
            pageNo=page.page_no,
            pageSize=page.page_size,
            candidates=[WorkerCandidateModel.from_domain(candidate) for candidate in page.candidates],
            upstreamRequest=cast(dict[str, object], cast(object, page.upstream_request)),
            upstreamResponse=cast(dict[str, object], cast(object, page.upstream_response)),
            errorCode=page.error_code,
            errorMessage=page.error_message,
        )


class PersistedCandidateRefModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidateId: str
    externalIdentityId: str
    resumeSnapshotId: str


class TracePromptReferenceModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    name: str = Field(min_length=1)
    label: str | None = None
    text: str = Field(min_length=1)
    type: Literal["text", "chat"] = "text"


class ObservationTraceFactModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    observationType: Literal["generation", "tool", "span"]
    input: object | None = None
    output: object | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    messageHistory: list[object] = Field(default_factory=list)
    response: object | None = None
    model: str | None = None
    version: str | None = None
    prompt: TracePromptReferenceModel | None = None
    usageDetails: dict[str, int] | None = None
    costDetails: dict[str, float] | None = None
    completionStartTime: str | None = None
    level: Literal["DEBUG", "DEFAULT", "WARNING", "ERROR"] | None = None
    statusMessage: str | None = None


class PersistCandidateSnapshotsRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    caseId: str
    candidates: list[WorkerCandidateModel]


class PersistCandidateSnapshotsResultModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persisted: list[PersistedCandidateRefModel]


class PersistResumeAnalysisItemModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidateId: str
    externalIdentityId: str
    resumeSnapshotId: str
    modelVersion: str
    promptVersion: str
    summary: str
    evidence: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    trace: ObservationTraceFactModel | None = None


class PersistResumeAnalysesRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analyses: list[PersistResumeAnalysisItemModel] = Field(default_factory=list)


class AgentRunStepModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stepNo: int
    roundNo: int | None
    stepType: str
    title: str
    status: str
    summary: str
    payload: dict[str, object]
    occurredAt: str

    @classmethod
    def from_payload(cls, payload: AgentRunStepPayload) -> "AgentRunStepModel":
        return cls(
            stepNo=payload["stepNo"],
            roundNo=payload["roundNo"],
            stepType=payload["stepType"],
            title=payload["title"],
            status=payload["status"],
            summary=payload["summary"],
            payload=cast(dict[str, object], cast(object, payload["payload"])),
            occurredAt=payload["occurredAt"],
        )

    def to_payload(self) -> AgentRunStepPayload:
        return {
            "stepNo": self.stepNo,
            "roundNo": self.roundNo,
            "stepType": self.stepType,
            "title": self.title,
            "status": self.status,
            "summary": self.summary,
            "payload": to_json_object(self.payload),
            "occurredAt": self.occurredAt,
        }

    def compact_for_workflow(self) -> "AgentRunStepModel":
        return self.model_copy(
            update={"payload": _compact_step_payload(self.stepType, self.payload)},
            deep=True,
        )


class ShortlistCandidateModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidateId: str
    externalIdentityId: str
    name: str
    title: str
    company: str
    location: str
    summary: str
    reason: str
    score: float
    sourceRound: int

    @classmethod
    def from_payload(cls, payload: AgentShortlistCandidatePayload) -> "ShortlistCandidateModel":
        return cls.model_validate(payload)

    def to_payload(self) -> AgentShortlistCandidatePayload:
        return cast(AgentShortlistCandidatePayload, cast(object, self.model_dump()))


class AgentRuntimeConfigEntryModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    modelVersion: str = Field(min_length=1)
    thinkingEffort: AgentThinkingEffort | None = None

    @classmethod
    def from_payload(cls, payload: AgentRuntimeConfigEntryPayload) -> "AgentRuntimeConfigEntryModel":
        return cls.model_validate(payload)

    def to_payload(self) -> AgentRuntimeConfigEntryPayload:
        return cast(AgentRuntimeConfigEntryPayload, cast(object, self.model_dump()))


class AgentRuntimeConfigModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    strategyExtractor: AgentRuntimeConfigEntryModel
    resumeMatcher: AgentRuntimeConfigEntryModel
    searchReflector: AgentRuntimeConfigEntryModel

    @classmethod
    def from_payload(cls, payload: AgentRuntimeConfigPayload) -> "AgentRuntimeConfigModel":
        return cls.model_validate(payload)

    def to_payload(self) -> AgentRuntimeConfigPayload:
        return cast(AgentRuntimeConfigPayload, cast(object, self.model_dump()))


class AgentRunSnapshotModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    caseId: str
    status: Literal["queued", "running", "completed", "failed"]
    jdText: str
    sourcingPreferenceText: str
    config: AgentRunConfigPayload
    currentRound: int
    modelVersion: str
    agentRuntimeConfig: AgentRuntimeConfigModel
    promptVersion: str
    workflowId: str | None
    temporalNamespace: str | None
    temporalTaskQueue: str | None
    langfuseTraceId: str | None
    langfuseTraceUrl: str | None
    steps: list[AgentRunStepModel]
    finalShortlist: list[ShortlistCandidateModel]
    seenResumeIds: list[str]
    errorCode: str | None
    errorMessage: str | None

    @classmethod
    def from_record(cls, run: AgentRunRecord) -> "AgentRunSnapshotModel":
        return cls(
            id=run.id,
            caseId=run.case_id,
            status=run.status,
            jdText=run.jd_text,
            sourcingPreferenceText=run.sourcing_preference_text,
            config=run.config,
            currentRound=run.current_round,
            modelVersion=run.model_version,
            agentRuntimeConfig=AgentRuntimeConfigModel.from_payload(
                effective_agent_runtime_config(
                    run.agent_runtime_config,
                    fallback_model_version=run.model_version,
                )
            ),
            promptVersion=run.prompt_version,
            workflowId=run.workflow_id,
            temporalNamespace=run.temporal_namespace,
            temporalTaskQueue=run.temporal_task_queue,
            langfuseTraceId=run.langfuse_trace_id,
            langfuseTraceUrl=run.langfuse_trace_url,
            steps=[AgentRunStepModel.from_payload(step) for step in run.steps],
            finalShortlist=[ShortlistCandidateModel.from_payload(item) for item in run.final_shortlist],
            seenResumeIds=list(run.seen_resume_ids),
            errorCode=run.error_code,
            errorMessage=run.error_message,
        )

    def compact_for_workflow(self) -> "AgentRunSnapshotModel":
        return self.model_copy(
            update={"steps": [step.compact_for_workflow() for step in self.steps]},
            deep=True,
        )


class RunPersistencePatchModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runId: str
    status: Literal["queued", "running", "completed", "failed"] | None = None
    currentRound: int | None = None
    appendSteps: list[AgentRunStepModel] = Field(default_factory=list)
    finalShortlist: list[ShortlistCandidateModel] | None = None
    seenResumeIds: list[str] | None = None
    errorCode: str | None = None
    errorMessage: str | None = None
    langfuseTraceId: str | None = None
    langfuseTraceUrl: str | None = None
    clearError: bool = False
    markFinished: bool = False


class CtsSearchRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    normalizedStrategy: NormalizedStrategyModel
    pageNo: int = Field(ge=1)
    pageSize: int = Field(ge=1)


class TracePublicationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    traceId: str | None = None
    traceUrl: str | None = None


def _compact_step_payload(step_type: str, payload: dict[str, object]) -> dict[str, object]:
    if step_type == "strategy":
        return _copy_selected_keys(
            payload,
            "mustRequirements",
            "coreRequirements",
            "bonusRequirements",
            "excludeSignals",
            "round1Query",
            "modelVersion",
            "thinkingEffort",
            "promptVersion",
            "executionConfig",
        )
    if step_type == "search":
        return _copy_selected_keys(
            payload,
            "roundQuery",
            "normalizedQuery",
            "pageNo",
            "pageSize",
            "offset",
            "total",
            "returnedCount",
            "candidateIds",
            "errorCode",
            "errorMessage",
        )
    if step_type == "dedupe":
        return _copy_selected_keys(
            payload,
            "admittedResumeIds",
            "duplicateResumeIds",
            "seenResumeCount",
        )
    if step_type == "analysis":
        compact_payload: dict[str, object] = {}
        analyses = payload.get("analyses", [])
        if isinstance(analyses, list):
            compact_payload["analyses"] = [
                _compact_analysis_entry(item)
                for item in analyses
                if isinstance(item, dict)
            ]
        return compact_payload
    if step_type == "shortlist":
        return _copy_selected_keys(
            payload,
            "retainedCount",
            "retainedCandidates",
            "analyzedCandidateIds",
            "analyzedCaseCandidateIds",
            "retainedCandidateIds",
            "retainedCaseCandidateIds",
        )
    if step_type == "reflection":
        return _copy_selected_keys(
            payload,
            "continueSearch",
            "reason",
            "nextRoundGoal",
            "nextRoundQuery",
            "queryDelta",
            "minimumRoundsOverrideApplied",
            "modelVersion",
            "thinkingEffort",
            "promptVersion",
            "executionConfig",
        )
    if step_type == "stop":
        return _copy_selected_keys(
            payload,
            "reason",
            "source",
            "duplicateStrategy",
        )
    if step_type == "finalize":
        return _copy_selected_keys(payload, "finalShortlist", "stopReason", "executionConfig")
    if step_type == "observability-warning":
        return _copy_selected_keys(payload, "warningCode", "terminalStatus", "errorMessage")
    return _copy_selected_keys(payload)


def _compact_analysis_entry(entry: dict[str, object]) -> dict[str, object]:
    return _copy_selected_keys(
        entry,
        "candidateId",
        "externalIdentityId",
        "name",
        "score",
        "reason",
        "evidence",
        "concerns",
        "modelVersion",
        "thinkingEffort",
        "promptVersion",
    )


def _copy_selected_keys(payload: dict[str, object], *keys: str) -> dict[str, object]:
    if not keys:
        return {}
    compacted: dict[str, object] = {}
    for key in keys:
        if key in payload:
            compacted[key] = deepcopy(payload[key])
    return compacted
