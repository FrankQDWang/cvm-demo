from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter


STRICT_MODEL_CONFIG = ConfigDict(extra="forbid", strict=True)
STRICT_EXTERNAL_RESPONSE_CONFIG = ConfigDict(extra="ignore", strict=True)


class StructuredFiltersBoundaryModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    page: int = Field(default=1, ge=1)
    pageSize: int = Field(default=10, ge=1)
    location: list[str] | None = None
    degree: int | None = None
    schoolType: int | None = None
    workExperienceRange: int | None = None
    position: str | None = None
    workContent: str | None = None
    company: str | None = None
    school: str | None = None


class OpenAIKeywordDraftEvidenceModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    label: str
    excerpt: str


class OpenAIKeywordDraftModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    must_terms: list[str]
    should_terms: list[str]
    exclude_terms: list[str]
    structured_filters: StructuredFiltersBoundaryModel
    evidence_refs: list[OpenAIKeywordDraftEvidenceModel]


class OpenAIOutputTextPartModel(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    type: Literal["output_text"]
    text: str


class OpenAIContentPartModel(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    type: str
    text: str | None = None


class OpenAIOutputItemModel(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    content: list[OpenAIContentPartModel | OpenAIOutputTextPartModel]


class OpenAIResponsesEnvelopeModel(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    output: list[OpenAIOutputItemModel]


class CtsRequestModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    jd: str
    keyword: str | None = None
    school: str | None = None
    company: str | None = None
    position: str | None = None
    workContent: str | None = None
    location: list[str] | None = None
    degree: int | None = None
    schoolType: int | None = None
    workExperienceRange: int | None = None
    page: int = Field(ge=1)
    pageSize: int = Field(ge=1)


class CtsEducationItemModel(BaseModel):
    model_config = STRICT_EXTERNAL_RESPONSE_CONFIG

    degree: str | None = None
    education: str | None = None
    school: str | None = None
    speciality: str | None = None
    startTime: str | None = None
    endTime: str | None = None
    sortNum: int | None = None


class CtsWorkExperienceItemModel(BaseModel):
    model_config = STRICT_EXTERNAL_RESPONSE_CONFIG

    company: str | None = None
    title: str | None = None
    duration: str | None = None
    summary: str | None = None
    startTime: str | None = None
    endTime: str | None = None
    sortNum: int | None = None


class CtsCandidateModel(BaseModel):
    model_config = STRICT_EXTERNAL_RESPONSE_CONFIG

    activeStatus: str
    age: int
    educationList: list[CtsEducationItemModel]
    expectedIndustry: str
    expectedIndustryIds: list[str]
    expectedJobCategory: str
    expectedJobCategoryIds: list[str]
    expectedLocation: str
    expectedLocationIds: list[str]
    expectedSalary: str
    gender: str
    jobState: str
    nowLocation: str
    projectNameAll: list[str]
    workExperienceList: list[CtsWorkExperienceItemModel]
    workSummariesAll: list[str]
    workYear: int
    name: str | None = None
    resumeName: str | None = None


class CtsSearchDataModel(BaseModel):
    model_config = STRICT_EXTERNAL_RESPONSE_CONFIG

    candidates: list[CtsCandidateModel]
    total: int
    page: int | str
    pageSize: int | str


class CtsTimingsModel(BaseModel):
    model_config = STRICT_EXTERNAL_RESPONSE_CONFIG

    validation: int
    configPreparation: int
    paramsPreparation: int
    apiRequest: int
    dataProcessing: int
    totalTime: int


class CtsSearchResponseModel(BaseModel):
    model_config = STRICT_EXTERNAL_RESPONSE_CONFIG

    code: int
    status: str
    message: str
    data: CtsSearchDataModel | None
    timings: CtsTimingsModel | None = None


class TemporalDiagnosticModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    runId: str
    workflowId: str
    namespace: str
    taskQueue: str
    appStatus: str
    temporalExecutionFound: bool
    temporalExecutionStatus: str | None
    visibilityIndexed: bool
    visibilityBackend: str
    startedAt: str | None
    closedAt: str | None
    error: str | None
    temporalUiUrl: HttpUrl | str


CTS_RESPONSE_ADAPTER = TypeAdapter(CtsSearchResponseModel)
OPENAI_DRAFT_ADAPTER = TypeAdapter(OpenAIKeywordDraftModel)
