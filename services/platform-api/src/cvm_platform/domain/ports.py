from __future__ import annotations

from typing import Protocol

from .types import ConditionPlanDraftData, NormalizedQueryPayload, SearchPageData


class LLMPort(Protocol):
    def draft_keywords(
        self,
        jd_text: str,
        model_version: str,
        prompt_version: str,
    ) -> ConditionPlanDraftData: ...


class ResumeSourcePort(Protocol):
    def search_candidates(
        self,
        normalized_query: NormalizedQueryPayload,
        page_no: int,
        page_size: int,
    ) -> SearchPageData: ...
