from __future__ import annotations

from typing import Protocol

from .types import NormalizedQueryPayload, SearchPageData


class ResumeSourcePort(Protocol):
    def search_candidates(
        self,
        normalized_query: NormalizedQueryPayload,
        page_no: int,
        page_size: int,
    ) -> SearchPageData: ...
