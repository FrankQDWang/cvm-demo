from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

STRICT_MODEL_CONFIG = ConfigDict(extra="forbid", strict=True)
NO_NUL_PATTERN = r"^[^\x00]*$"


class CreateCaseRequestModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    title: str = Field(min_length=1, pattern=NO_NUL_PATTERN)
    ownerTeamId: str = Field(min_length=1, pattern=NO_NUL_PATTERN)


class CreateJdVersionRequestModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    rawText: str = Field(min_length=1, pattern=NO_NUL_PATTERN)
    source: str = Field(min_length=1, pattern=NO_NUL_PATTERN)


class CreateAgentRunRequestModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    jdText: str = Field(min_length=1, pattern=NO_NUL_PATTERN)
    sourcingPreferenceText: str = Field(min_length=1, pattern=NO_NUL_PATTERN)


class SaveVerdictRequestModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    verdict: Literal["Match", "Maybe", "No"]
    reasons: list[str]
    notes: str | None = Field(default=None, pattern=NO_NUL_PATTERN)
    actorId: str = Field(min_length=1, pattern=NO_NUL_PATTERN)
    resumeSnapshotId: str | None = Field(default=None, pattern=NO_NUL_PATTERN)


class CreateExportRequestModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    caseId: str = Field(min_length=1, pattern=NO_NUL_PATTERN)
    maskPolicy: Literal["masked", "sensitive"]
    reason: str = Field(min_length=1, pattern=NO_NUL_PATTERN)
    idempotencyKey: str = Field(min_length=1, pattern=NO_NUL_PATTERN)


class CreateEvalRunRequestModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    suiteId: str = Field(min_length=1, pattern=NO_NUL_PATTERN)
    datasetId: str = Field(min_length=1, pattern=NO_NUL_PATTERN)
    targetVersion: str = Field(min_length=1, pattern=NO_NUL_PATTERN)
