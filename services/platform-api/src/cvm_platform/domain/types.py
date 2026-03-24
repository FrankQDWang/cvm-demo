from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class EvidenceRef:
    label: str
    excerpt: str


@dataclass(slots=True)
class ConditionPlanDraftData:
    must_terms: list[str]
    should_terms: list[str]
    exclude_terms: list[str]
    structured_filters: dict[str, Any]
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
    resume: dict[str, Any]


@dataclass(slots=True)
class SearchPageData:
    status: str
    total: int
    page_no: int
    page_size: int
    candidates: list[CandidateData]
    upstream_request: dict[str, Any]
    upstream_response: dict[str, Any]
    error_code: str | None = None
    error_message: str | None = None
