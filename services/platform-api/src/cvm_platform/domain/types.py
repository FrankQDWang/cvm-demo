from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypedDict, cast


JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject = dict[str, JsonValue]
SearchRunStatus = Literal["draft", "confirmed", "queued", "running", "completed", "failed"]


class EvidenceRefPayload(TypedDict):
    label: str
    excerpt: str


class StructuredFiltersPayload(TypedDict, total=False):
    page: int
    pageSize: int
    location: list[str]
    degree: int
    schoolType: int
    workExperienceRange: int
    position: str
    workContent: str
    company: str
    school: str


class NormalizedQueryPayload(TypedDict):
    jd: str
    mustTerms: list[str]
    shouldTerms: list[str]
    excludeTerms: list[str]
    structuredFilters: StructuredFiltersPayload
    keyword: str


class CandidateCardPayload(TypedDict):
    candidateId: str
    externalIdentityId: str
    name: str
    title: str
    company: str
    location: str
    summary: str


class ResumeEducationItemPayload(TypedDict):
    school: str
    degree: str
    major: str
    startTime: str | None
    endTime: str | None


class ResumeWorkExperienceItemPayload(TypedDict):
    company: str
    title: str
    duration: str | None
    startTime: str | None
    endTime: str | None
    summary: str | None


class ResumeProjectionPayload(TypedDict):
    workYear: int | None
    currentLocation: str | None
    expectedLocation: str | None
    jobState: str | None
    expectedSalary: str | None
    age: int | None
    education: list[ResumeEducationItemPayload]
    workExperience: list[ResumeWorkExperienceItemPayload]
    workSummaries: list[str]
    projectNames: list[str]


class ConditionPlanDraftPayload(TypedDict):
    mustTerms: list[str]
    shouldTerms: list[str]
    excludeTerms: list[str]
    structuredFilters: StructuredFiltersPayload
    evidenceRefs: list[EvidenceRefPayload]


class SearchRunStatusCountPayload(TypedDict):
    status: str
    count: int


class SearchRunFailureCountPayload(TypedDict):
    code: str
    count: int


class QueueSummaryPayload(TypedDict):
    searchRuns: list[SearchRunStatusCountPayload]


class FailureSummaryPayload(TypedDict):
    searchRuns: list[SearchRunFailureCountPayload]


class LatencySummaryPayload(TypedDict):
    avgSearchRunSeconds: float


class EvalSummaryMetricsPayload(TypedDict):
    blockingChecks: int
    passedChecks: int


@dataclass(slots=True, frozen=True)
class EvidenceRef:
    label: str
    excerpt: str


@dataclass(slots=True)
class ConditionPlanDraftData:
    must_terms: list[str]
    should_terms: list[str]
    exclude_terms: list[str]
    structured_filters: StructuredFiltersPayload
    evidence_refs: list[EvidenceRef] = field(default_factory=list)


@dataclass(slots=True)
class CandidateData:
    external_identity_id: str
    name: str
    title: str
    company: str
    location: str
    summary: str
    email: str
    phone: str
    resume_projection: ResumeProjectionPayload


@dataclass(slots=True)
class SearchPageData:
    status: SearchRunStatus
    total: int
    page_no: int
    page_size: int
    candidates: list[CandidateData]
    upstream_request: JsonObject
    upstream_response: JsonObject
    error_code: str | None = None
    error_message: str | None = None


def to_json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, dict):
        dict_value = cast(dict[object, object], value)
        return {str(key): to_json_value(item) for key, item in dict_value.items()}
    if isinstance(value, list):
        list_value = cast(list[object], value)
        return [to_json_value(item) for item in list_value]
    if isinstance(value, tuple):
        tuple_value = cast(tuple[object, ...], value)
        return [to_json_value(item) for item in tuple_value]
    raise TypeError(f"Value {value!r} is not JSON serializable.")


def to_json_object(value: object) -> JsonObject:
    if not isinstance(value, dict):
        raise TypeError(f"Value {value!r} is not a JSON object.")
    dict_value = cast(dict[object, object], value)
    return {str(key): to_json_value(item) for key, item in dict_value.items()}
