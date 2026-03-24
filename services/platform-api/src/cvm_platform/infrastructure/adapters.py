from __future__ import annotations

from hashlib import sha1

from cvm_platform.domain.types import CandidateData, ConditionPlanDraftData, EvidenceRef, SearchPageData

from .mock_catalog import MOCK_CANDIDATES


class StubLLMAdapter:
    def draft_keywords(
        self,
        jd_text: str,
        model_version: str,
        prompt_version: str,
    ) -> ConditionPlanDraftData:
        words = [token.strip(" ,.;:\n") for token in jd_text.replace("/", " ").split()]
        unique_words: list[str] = []
        for word in words:
            if len(word) < 3:
                continue
            if word not in unique_words:
                unique_words.append(word)
        must_terms = unique_words[:3] or ["JD", "MVP"]
        should_terms = unique_words[3:6]
        structured_filters = {"page": 1, "pageSize": 2}
        evidence_refs = [EvidenceRef(label=f"JD line {index + 1}", excerpt=term) for index, term in enumerate(must_terms[:2])]
        return ConditionPlanDraftData(
            must_terms=must_terms,
            should_terms=should_terms,
            exclude_terms=[],
            structured_filters=structured_filters,
            evidence_refs=evidence_refs,
        )


class MockResumeSourceAdapter:
    def search_candidates(self, normalized_query: dict, page_no: int, page_size: int) -> SearchPageData:
        if page_no <= 0 or page_size <= 0:
            return SearchPageData(
                status="failed",
                total=0,
                page_no=page_no,
                page_size=page_size,
                candidates=[],
                upstream_request={"page": page_no, "pageSize": page_size},
                upstream_response={"code": 200, "status": "ok", "message": "parameter anomaly", "data": None},
                error_code="CTS_PARAM_ANOMALY",
                error_message="Invalid page or pageSize produced data:null in upstream contract.",
            )

        terms = [term.lower() for term in normalized_query.get("mustTerms", []) + normalized_query.get("shouldTerms", [])]
        if not terms:
            filtered = MOCK_CANDIDATES
        else:
            filtered = []
            for candidate in MOCK_CANDIDATES:
                haystack = " ".join(
                    [
                        candidate["title"],
                        candidate["company"],
                        candidate["location"],
                        candidate["summary"],
                        " ".join(candidate["resume"]["skills"]),
                    ]
                ).lower()
                if any(term.lower() in haystack for term in terms):
                    filtered.append(candidate)
        total = len(filtered)
        start = (page_no - 1) * page_size
        page_items = filtered[start : start + page_size]
        candidates = [
            CandidateData(
                external_identity_id=item["external_identity_id"],
                name=item["name"],
                title=item["title"],
                company=item["company"],
                location=item["location"],
                summary=item["summary"],
                email=item["email"],
                phone=item["phone"],
                resume=item["resume"],
            )
            for item in page_items
        ]
        upstream_data = {
            "candidates": [
                {
                    "id": item["external_identity_id"],
                    "name": item["name"],
                    "title": item["title"],
                    "company": item["company"],
                    "location": item["location"],
                }
                for item in page_items
            ],
            "total": total,
            "page": page_no,
            "pageSize": page_size,
        }
        return SearchPageData(
            status="completed",
            total=total,
            page_no=page_no,
            page_size=page_size,
            candidates=candidates,
            upstream_request={"page": page_no, "pageSize": page_size, **normalized_query},
            upstream_response={"code": 200, "status": "ok", "message": "success", "data": upstream_data},
        )


def resume_hash(payload: dict) -> str:
    return sha1(repr(sorted(payload.items())).encode("utf-8")).hexdigest()
