from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

STRICT_MODEL_CONFIG = ConfigDict(extra="forbid", strict=True)


class CreateCaseRequestModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    title: str = Field(min_length=1)
    ownerTeamId: str = Field(min_length=1)


class CreateJdVersionRequestModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    rawText: str = Field(min_length=1)
    source: str = Field(min_length=1)


class CreateAgentRunRequestModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    jdText: str = Field(min_length=1)
    sourcingPreferenceText: str = Field(min_length=1)


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
