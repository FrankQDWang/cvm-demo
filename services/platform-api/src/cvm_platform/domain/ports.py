from __future__ import annotations

from typing import Protocol

from .types import (
    AgentSearchStrategyData,
    CandidateData,
    ConditionPlanDraftData,
    NormalizedQueryPayload,
    ResumeMatchData,
    SearchPageData,
    SearchReflectionData,
)


class LLMPort(Protocol):
    def draft_keywords(
        self,
        jd_text: str,
        model_version: str,
        prompt_version: str,
    ) -> ConditionPlanDraftData: ...

    def extract_agent_search_strategy(
        self,
        jd_text: str,
        sourcing_preference_text: str,
        model_version: str,
        prompt_version: str,
    ) -> AgentSearchStrategyData: ...

    def analyze_resume_match(
        self,
        jd_text: str,
        sourcing_preference_text: str,
        strategy: NormalizedQueryPayload,
        candidate: CandidateData,
        model_version: str,
        prompt_version: str,
    ) -> ResumeMatchData: ...

    def reflect_search_progress(
        self,
        jd_text: str,
        sourcing_preference_text: str,
        strategy: NormalizedQueryPayload,
        round_ledger: list[dict[str, object]],
        round_no: int,
        max_rounds: int,
        new_candidate_count: int,
        seen_candidate_count: int,
        model_version: str,
        prompt_version: str,
    ) -> SearchReflectionData: ...


class ResumeSourcePort(Protocol):
    def search_candidates(
        self,
        normalized_query: NormalizedQueryPayload,
        page_no: int,
        page_size: int,
    ) -> SearchPageData: ...
