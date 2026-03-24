from __future__ import annotations

import json
import re
import uuid
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from cvm_platform.application.policies import resume_hash
from cvm_platform.domain.types import CandidateData, ConditionPlanDraftData, EvidenceRef, SearchPageData
from cvm_platform.settings.config import Settings

from .mock_catalog import MOCK_CANDIDATES


HIGH_SIGNAL_TERMS = [
    "Context Engineering",
    "Voice Agent",
    "ReAct",
    "Reflexion",
    "Python",
    "Agent",
    "LLM",
    "Post-training",
    "后训练",
    "SFT",
    "prompt工程",
    "多模态",
    "NLP",
    "算法工程师",
]

CITY_TERMS = ["北京", "上海", "深圳", "广州", "杭州", "成都", "苏州", "武汉", "南京"]
ALLOWED_STRUCTURED_FILTER_KEYS = {
    "page",
    "pageSize",
    "location",
    "degree",
    "schoolType",
    "workExperienceRange",
    "position",
    "workContent",
    "company",
    "school",
}
PLACEHOLDER_MODEL_VERSIONS = {"", "default", "stub", "stub-1"}


class StubLLMAdapter:
    def draft_keywords(
        self,
        jd_text: str,
        model_version: str,
        prompt_version: str,
    ) -> ConditionPlanDraftData:
        must_terms: list[str] = []
        should_terms: list[str] = []

        for term in HIGH_SIGNAL_TERMS:
            if term.lower() in jd_text.lower():
                if term in {"Python", "Agent", "ReAct", "Voice Agent", "Context Engineering"}:
                    must_terms.append(term)
                else:
                    should_terms.append(term)

        if not must_terms:
            words = [token.strip(" ,.;:\n") for token in jd_text.replace("/", " ").split()]
            for word in words:
                if len(word) >= 3 and word not in must_terms:
                    must_terms.append(word)
                if len(must_terms) >= 3:
                    break

        must_terms = must_terms[:4] or ["JD", "MVP"]
        should_terms = [term for term in should_terms if term not in must_terms][:6]

        structured_filters: dict[str, Any] = {"page": 1, "pageSize": 10}

        city = next((term for term in CITY_TERMS if term in jd_text), None)
        if city:
            structured_filters["location"] = [city]

        if "硕士" in jd_text:
            structured_filters["degree"] = 3
        elif "本科" in jd_text:
            structured_filters["degree"] = 2

        if "C9" in jd_text or "985" in jd_text:
            structured_filters["schoolType"] = 3
        elif "211" in jd_text:
            structured_filters["schoolType"] = 2
        elif "双一流" in jd_text:
            structured_filters["schoolType"] = 1

        work_range_matchers = [
            (r"(10年以上|十年以上)", 6),
            (r"(5[-到~]10年|5年以上|5-8年|5年以?上)", 5),
            (r"(3[-到~]5年|3年以上)", 4),
            (r"(1[-到~]3年)", 3),
            (r"(1年以内)", 1),
        ]
        for pattern, code in work_range_matchers:
            if re.search(pattern, jd_text):
                structured_filters["workExperienceRange"] = code
                break

        if "算法工程师" in jd_text:
            structured_filters["position"] = "算法工程师"
        elif "工程师" in jd_text:
            structured_filters["position"] = "工程师"

        work_content_terms = [term for term in ["Agent", "Voice Agent", "Context Engineering", "ReAct", "Reflexion", "LLM"] if term.lower() in jd_text.lower()]
        if work_content_terms:
            structured_filters["workContent"] = " ".join(work_content_terms)

        evidence_terms = must_terms[:2] or should_terms[:2]
        evidence_refs = [EvidenceRef(label=f"JD line {index + 1}", excerpt=term) for index, term in enumerate(evidence_terms)]
        return ConditionPlanDraftData(
            must_terms=must_terms,
            should_terms=should_terms,
            exclude_terms=[],
            structured_filters=structured_filters,
            evidence_refs=evidence_refs,
        )


class OpenAILLMAdapter:
    def __init__(self, api_key: str, model: str, base_url: str = "", timeout_seconds: int = 30) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.timeout_seconds = timeout_seconds

    def draft_keywords(
        self,
        jd_text: str,
        model_version: str,
        prompt_version: str,
    ) -> ConditionPlanDraftData:
        resolved_model = self._resolve_model(model_version)
        prompt = self._build_prompt(jd_text, resolved_model, prompt_version)
        response = self._responses_request(
            {
                "model": resolved_model,
                "input": prompt,
                "max_output_tokens": 600,
            }
        )
        output_text = self._extract_output_text(response)
        return self._parse_draft(output_text)

    def _resolve_model(self, requested_model: str) -> str:
        model = requested_model.strip()
        return self.model if model.lower() in PLACEHOLDER_MODEL_VERSIONS else model

    @staticmethod
    def _build_prompt(jd_text: str, model_version: str, prompt_version: str) -> str:
        return f"""
You extract a structured candidate search condition draft from a job description.

Return JSON only. Do not wrap it in markdown fences. The JSON must match this shape:
{{
  "must_terms": ["short term"],
  "should_terms": ["short term"],
  "exclude_terms": ["short term"],
  "structured_filters": {{
    "page": 1,
    "pageSize": 10,
    "location": ["上海"],
    "degree": 2,
    "schoolType": 3,
    "workExperienceRange": 4,
    "position": "算法工程师",
    "workContent": "Agent Python"
  }},
  "evidence_refs": [
    {{"label": "JD evidence 1", "excerpt": "exact short excerpt"}}
  ]
}}

Rules:
- Keep must_terms to 1-4 items and should_terms to 0-6 items.
- Use short search terms, not full sentences.
- structured_filters may only contain: page, pageSize, location, degree, schoolType, workExperienceRange, position, workContent, company, school.
- Always include page=1 and pageSize=10 unless the JD explicitly implies something else.
- Use evidence_refs to quote short supporting excerpts from the JD.
- If the JD does not specify a filter, omit that key instead of guessing.

model_version={model_version}
prompt_version={prompt_version}

JD:
{jd_text}
""".strip()

    def _responses_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        req = urllib_request.Request(
            f"{self.base_url}/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib_request.urlopen(req, timeout=self.timeout_seconds) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib_error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI request failed with HTTP {exc.code}: {body[:500]}") from exc
        except urllib_error.URLError as exc:
            raise RuntimeError(f"OpenAI network error: {exc.reason}") from exc

    @staticmethod
    def _extract_output_text(response_body: dict[str, Any]) -> str:
        text_parts: list[str] = []
        for item in response_body.get("output", []):
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []):
                if isinstance(content, dict) and content.get("type") == "output_text":
                    text = str(content.get("text") or "").strip()
                    if text:
                        text_parts.append(text)
        if not text_parts:
            raise RuntimeError("OpenAI response did not contain output_text.")
        return "\n".join(text_parts)

    def _parse_draft(self, raw_text: str) -> ConditionPlanDraftData:
        cleaned = raw_text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or start >= end:
            raise RuntimeError(f"OpenAI response did not contain a JSON object: {raw_text[:300]}")

        payload = json.loads(cleaned[start : end + 1])
        must_terms = self._normalize_terms(payload.get("must_terms"), limit=4)
        should_terms = [term for term in self._normalize_terms(payload.get("should_terms"), limit=6) if term not in must_terms]
        exclude_terms = self._normalize_terms(payload.get("exclude_terms"), limit=4)
        structured_filters = self._normalize_structured_filters(payload.get("structured_filters"))
        evidence_refs = self._normalize_evidence_refs(payload.get("evidence_refs"), must_terms, should_terms)
        return ConditionPlanDraftData(
            must_terms=must_terms or ["JD", "MVP"],
            should_terms=should_terms,
            exclude_terms=exclude_terms,
            structured_filters=structured_filters,
            evidence_refs=evidence_refs,
        )

    @staticmethod
    def _normalize_terms(value: Any, limit: int) -> list[str]:
        if not isinstance(value, list):
            return []
        terms: list[str] = []
        seen: set[str] = set()
        for item in value:
            term = str(item or "").strip()
            lowered = term.lower()
            if not term or lowered in seen:
                continue
            seen.add(lowered)
            terms.append(term)
            if len(terms) >= limit:
                break
        return terms

    @staticmethod
    def _normalize_structured_filters(value: Any) -> dict[str, Any]:
        raw_filters = value if isinstance(value, dict) else {}
        normalized: dict[str, Any] = {"page": 1, "pageSize": 10}
        for key, item in raw_filters.items():
            if key not in ALLOWED_STRUCTURED_FILTER_KEYS:
                continue
            if key in {"page", "pageSize", "degree", "schoolType", "workExperienceRange"}:
                try:
                    normalized[key] = int(item)
                except (TypeError, ValueError):
                    continue
            elif key == "location":
                if isinstance(item, list):
                    locations = [str(location).strip() for location in item if str(location).strip()]
                    if locations:
                        normalized[key] = locations[:3]
                else:
                    location = str(item or "").strip()
                    if location:
                        normalized[key] = [location]
            else:
                text = str(item or "").strip()
                if text:
                    normalized[key] = text
        normalized["page"] = max(1, int(normalized.get("page", 1)))
        normalized["pageSize"] = max(1, int(normalized.get("pageSize", 10)))
        return normalized

    @staticmethod
    def _normalize_evidence_refs(value: Any, must_terms: list[str], should_terms: list[str]) -> list[EvidenceRef]:
        refs: list[EvidenceRef] = []
        if isinstance(value, list):
            for item in value:
                if not isinstance(item, dict):
                    continue
                label = str(item.get("label") or "").strip()
                excerpt = str(item.get("excerpt") or "").strip()
                if label and excerpt:
                    refs.append(EvidenceRef(label=label, excerpt=excerpt))
                if len(refs) >= 4:
                    break
        if refs:
            return refs
        fallback_terms = (must_terms[:2] or should_terms[:2])[:2]
        return [EvidenceRef(label=f"JD evidence {index + 1}", excerpt=term) for index, term in enumerate(fallback_terms)]


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
                if any(term in haystack for term in terms):
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


class MissingCtsCredentialsAdapter:
    def search_candidates(self, normalized_query: dict, page_no: int, page_size: int) -> SearchPageData:
        return SearchPageData(
            status="failed",
            total=0,
            page_no=page_no,
            page_size=page_size,
            candidates=[],
            upstream_request={"page": page_no, "pageSize": page_size, **normalized_query},
            upstream_response={"code": 40001, "status": "fail", "message": "CTS credentials not configured", "data": None},
            error_code="CTS_NOT_CONFIGURED",
            error_message="CTS tenant credentials are not configured.",
        )


class CtsResumeSourceAdapter:
    def __init__(self, base_url: str, tenant_key: str, tenant_secret: str, timeout_seconds: int = 20) -> None:
        self.base_url = base_url.rstrip("/")
        self.tenant_key = tenant_key
        self.tenant_secret = tenant_secret
        self.timeout_seconds = timeout_seconds

    def search_candidates(self, normalized_query: dict, page_no: int, page_size: int) -> SearchPageData:
        payload = self._build_payload(normalized_query, page_no, page_size)
        response_body: dict[str, Any] = {}
        try:
            req = urllib_request.Request(
                f"{self.base_url}/thirdCooperate/search/candidate/cts",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "tenant_key": self.tenant_key,
                    "tenant_secret": self.tenant_secret,
                    "trace_id": uuid.uuid4().hex,
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib_request.urlopen(req, timeout=self.timeout_seconds) as resp:
                response_body = json.loads(resp.read().decode("utf-8"))
        except urllib_error.HTTPError as exc:
            response_body = self._read_error_response(exc)
            return SearchPageData(
                status="failed",
                total=0,
                page_no=page_no,
                page_size=page_size,
                candidates=[],
                upstream_request=payload,
                upstream_response=response_body or {"status": "fail", "message": str(exc)},
                error_code="CTS_HTTP_ERROR",
                error_message=f"CTS HTTP error {exc.code}.",
            )
        except urllib_error.URLError as exc:
            return SearchPageData(
                status="failed",
                total=0,
                page_no=page_no,
                page_size=page_size,
                candidates=[],
                upstream_request=payload,
                upstream_response={"status": "fail", "message": str(exc.reason)},
                error_code="CTS_NETWORK_ERROR",
                error_message=f"CTS network error: {exc.reason}.",
            )

        if response_body.get("code") == 20001:
            return SearchPageData(
                status="failed",
                total=0,
                page_no=page_no,
                page_size=page_size,
                candidates=[],
                upstream_request=payload,
                upstream_response=response_body,
                error_code="CTS_AUTH_FAILED",
                error_message=response_body.get("message") or "CTS authentication failed.",
            )

        data = response_body.get("data")
        if data is None:
            return SearchPageData(
                status="failed",
                total=0,
                page_no=page_no,
                page_size=page_size,
                candidates=[],
                upstream_request=payload,
                upstream_response=response_body,
                error_code="CTS_PARAM_ANOMALY",
                error_message="CTS returned data:null. Check page and pageSize or loosen conditions.",
            )

        candidates_raw = data.get("candidates") or []
        candidates = [self._map_candidate(item) for item in candidates_raw]
        return SearchPageData(
            status="completed",
            total=int(data.get("total") or 0),
            page_no=int(data.get("page") or page_no),
            page_size=int(data.get("pageSize") or page_size),
            candidates=candidates,
            upstream_request=payload,
            upstream_response=response_body,
        )

    def _build_payload(self, normalized_query: dict, page_no: int, page_size: int) -> dict[str, Any]:
        filters = dict(normalized_query.get("structuredFilters") or {})
        keyword = normalized_query.get("keyword") or " ".join(normalized_query.get("mustTerms", []) + normalized_query.get("shouldTerms", []))
        payload = {
            "jd": normalized_query.get("jd"),
            "keyword": keyword or None,
            "school": filters.get("school"),
            "company": filters.get("company"),
            "position": filters.get("position"),
            "workContent": filters.get("workContent"),
            "location": filters.get("location"),
            "degree": filters.get("degree"),
            "schoolType": filters.get("schoolType"),
            "workExperienceRange": filters.get("workExperienceRange"),
            "page": page_no,
            "pageSize": page_size,
        }
        return {key: value for key, value in payload.items() if value not in (None, "", [])}

    @staticmethod
    def _read_error_response(exc: urllib_error.HTTPError) -> dict[str, Any]:
        try:
            return json.loads(exc.read().decode("utf-8"))
        except Exception:
            return {}

    @staticmethod
    def _map_candidate(candidate: dict[str, Any]) -> CandidateData:
        external_id = resume_hash(candidate)
        work_experience = sorted(candidate.get("workExperienceList") or [], key=lambda item: item.get("sortNum", 999))
        latest_work = work_experience[0] if work_experience else {}
        education_list = sorted(candidate.get("educationList") or [], key=lambda item: item.get("sortNum", 999))
        latest_education = education_list[0] if education_list else {}
        title = latest_work.get("title") or candidate.get("expectedJobCategory") or "匿名候选人"
        company = latest_work.get("company") or "未知公司"
        location = candidate.get("nowLocation") or candidate.get("expectedLocation") or "未知地点"
        name = candidate.get("name") or candidate.get("resumeName") or f"匿名候选人-{external_id[:6]}"
        summary_parts = [
            f"{candidate.get('workYear', 0)}年经验",
            title,
            company,
            latest_education.get("school"),
            latest_education.get("education"),
        ]
        work_summaries = candidate.get("workSummariesAll") or []
        if work_summaries:
            summary_parts.append(work_summaries[0][:120])
        summary = " | ".join(part for part in summary_parts if part)
        return CandidateData(
            external_identity_id=external_id,
            name=name,
            title=title,
            company=company,
            location=location,
            summary=summary,
            email="",
            phone="",
            resume=candidate,
        )


def build_resume_source(settings: Settings):
    if settings.resume_source_mode.lower() == "cts":
        if not settings.cts_tenant_key or not settings.cts_tenant_secret:
            return MissingCtsCredentialsAdapter()
        return CtsResumeSourceAdapter(
            base_url=settings.cts_base_url,
            tenant_key=settings.cts_tenant_key,
            tenant_secret=settings.cts_tenant_secret,
            timeout_seconds=settings.cts_timeout_seconds,
        )
    return MockResumeSourceAdapter()


def build_llm(settings: Settings):
    if settings.llm_mode.lower() == "stub":
        return StubLLMAdapter()
    if settings.llm_provider.lower() != "openai":
        raise RuntimeError(f"Unsupported CVM_LLM_PROVIDER: {settings.llm_provider}")
    if not settings.llm_api_key:
        raise RuntimeError("OPENAI_API_KEY is required when CVM_LLM_MODE is not stub.")
    return OpenAILLMAdapter(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        timeout_seconds=settings.llm_timeout_seconds,
    )
