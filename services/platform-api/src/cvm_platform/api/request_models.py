from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cvm_platform.infrastructure.boundary_models import StructuredFiltersBoundaryModel


STRICT_MODEL_CONFIG = ConfigDict(extra="forbid", strict=True)


class EvidenceRefRequestModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    label: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)


class CreateCaseRequestModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    title: str = Field(min_length=1)
    ownerTeamId: str = Field(min_length=1)


class CreateJdVersionRequestModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    rawText: str = Field(min_length=1)
    source: str = Field(min_length=1)


class CreateKeywordDraftJobRequestModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    jdVersionId: str = Field(min_length=1)
    modelVersion: str = Field(min_length=1)
    promptVersion: str = Field(min_length=1)


class ConfirmConditionPlanRequestModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    mustTerms: list[str]
    shouldTerms: list[str]
    excludeTerms: list[str]
    structuredFilters: StructuredFiltersBoundaryModel
    evidenceRefs: list[EvidenceRefRequestModel]
    confirmedBy: str = Field(min_length=1)


class CreateSearchRunRequestModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    caseId: str = Field(min_length=1)
    planId: str = Field(min_length=1)
    pageBudget: int = Field(ge=1)
    idempotencyKey: str = Field(min_length=1)


class SaveVerdictRequestModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    verdict: Literal["Match", "Maybe", "No"]
    reasons: list[str]
    notes: str | None = None
    actorId: str = Field(min_length=1)
    resumeSnapshotId: str | None = None


class CreateExportRequestModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    caseId: str = Field(min_length=1)
    maskPolicy: Literal["masked", "sensitive"]
    reason: str = Field(min_length=1)
    idempotencyKey: str = Field(min_length=1)


class CreateEvalRunRequestModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    suiteId: str = Field(min_length=1)
    datasetId: str = Field(min_length=1)
    targetVersion: str = Field(min_length=1)
