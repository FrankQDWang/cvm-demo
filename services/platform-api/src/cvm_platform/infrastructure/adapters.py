from __future__ import annotations

import json
import re
import uuid
from json import JSONDecodeError
from typing import cast
from urllib import error as urllib_error
from urllib import request as urllib_request

from cvm_platform.application.policies import resume_hash
from cvm_platform.domain.errors import (
    ExternalDependencyError,
    TransientDependencyError,
    ValidationError,
)
from cvm_platform.domain.types import (
    CandidateData,
    ConditionPlanDraftData,
    EvidenceRef,
    JsonObject,
    NormalizedQueryPayload,
    ResumeEducationItemPayload,
    ResumeProjectionPayload,
    ResumeWorkExperienceItemPayload,
    SearchPageData,
    StructuredFiltersPayload,
    to_json_object,
)
from cvm_platform.settings.config import Settings

from .boundary_models import (
    CtsCandidateModel,
    CtsRequestModel,
    CtsSearchResponseModel,
    OpenAIKeywordDraftModel,
    OpenAIResponsesEnvelopeModel,
    StructuredFiltersBoundaryModel,
)
from .mock_catalog import MOCK_CANDIDATES, MockCandidatePayload


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


def _dump_structured_filters(model: StructuredFiltersBoundaryModel) -> StructuredFiltersPayload:
    return cast(StructuredFiltersPayload, cast(object, model.model_dump(exclude_none=True)))


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

        structured_filters: StructuredFiltersPayload = {"page": 1, "pageSize": 10}

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
        evidence_refs = [
            EvidenceRef(label=f"JD line {index + 1}", excerpt=term)
            for index, term in enumerate(evidence_terms)
        ]
        return ConditionPlanDraftData(
            must_terms=must_terms,
            should_terms=should_terms,
            exclude_terms=[],
            structured_filters=structured_filters,
            evidence_refs=evidence_refs,
        )


class MisconfiguredLLMAdapter:
    def __init__(self, message: str) -> None:
        self.message = message

    def draft_keywords(
        self,
        jd_text: str,
        model_version: str,
        prompt_version: str,
    ) -> ConditionPlanDraftData:
        raise ValidationError("LLM_NOT_CONFIGURED", self.message)


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

    def _responses_request(self, payload: JsonObject) -> OpenAIResponsesEnvelopeModel:
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
                body = resp.read().decode("utf-8")
        except urllib_error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if 500 <= exc.code < 600:
                raise TransientDependencyError(
                    "OPENAI_HTTP_ERROR",
                    f"OpenAI request failed with HTTP {exc.code}.",
                ) from exc
            raise ExternalDependencyError(
                "OPENAI_HTTP_ERROR",
                f"OpenAI request failed with HTTP {exc.code}: {body[:500]}",
            ) from exc
        except urllib_error.URLError as exc:
            raise TransientDependencyError(
                "OPENAI_NETWORK_ERROR",
                f"OpenAI network error: {exc.reason}",
            ) from exc

        try:
            payload_json = json.loads(body)
            return OpenAIResponsesEnvelopeModel.model_validate(payload_json)
        except (JSONDecodeError, ValueError) as exc:
            raise ExternalDependencyError(
                "OPENAI_RESPONSE_INVALID",
                "OpenAI response was not valid JSON.",
            ) from exc

    @staticmethod
    def _extract_output_text(response_body: OpenAIResponsesEnvelopeModel) -> str:
        text_parts: list[str] = []
        for item in response_body.output:
            for content in item.content:
                if content.type == "output_text" and content.text:
                    text_parts.append(content.text.strip())
        if not text_parts:
            raise ExternalDependencyError(
                "OPENAI_RESPONSE_EMPTY",
                "OpenAI response did not contain output_text.",
            )
        return "\n".join(text_parts)

    def _parse_draft(self, raw_text: str) -> ConditionPlanDraftData:
        cleaned = raw_text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or start >= end:
            raise ExternalDependencyError(
                "OPENAI_RESPONSE_INVALID",
                f"OpenAI response did not contain a JSON object: {raw_text[:300]}",
            )

        try:
            payload_json = json.loads(cleaned[start : end + 1])
            draft = OpenAIKeywordDraftModel.model_validate(payload_json)
        except (JSONDecodeError, ValueError) as exc:
            raise ExternalDependencyError(
                "OPENAI_RESPONSE_INVALID",
                "OpenAI keyword draft did not match the required schema.",
            ) from exc

        filters = StructuredFiltersBoundaryModel.model_validate(
            draft.structured_filters.model_dump(exclude_none=True)
        )
        return ConditionPlanDraftData(
            must_terms=draft.must_terms[:4] or ["JD", "MVP"],
            should_terms=[term for term in draft.should_terms[:6] if term not in draft.must_terms[:4]],
            exclude_terms=draft.exclude_terms[:4],
            structured_filters=_dump_structured_filters(filters),
            evidence_refs=[
                EvidenceRef(label=ref.label, excerpt=ref.excerpt)
                for ref in draft.evidence_refs[:4]
            ],
        )


class MockResumeSourceAdapter:
    def search_candidates(
        self,
        normalized_query: NormalizedQueryPayload,
        page_no: int,
        page_size: int,
    ) -> SearchPageData:
        if page_no <= 0 or page_size <= 0:
            return SearchPageData(
                status="failed",
                total=0,
                page_no=page_no,
                page_size=page_size,
                candidates=[],
                upstream_request=to_json_object({"page": page_no, "pageSize": page_size}),
                upstream_response=to_json_object({"code": 200, "status": "ok", "message": "parameter anomaly", "data": None}),
                error_code="CTS_PARAM_ANOMALY",
                error_message="Invalid page or pageSize produced data:null in upstream contract.",
            )

        terms = [
            term.lower()
            for term in normalized_query["mustTerms"] + normalized_query["shouldTerms"]
        ]
        filtered: list[MockCandidatePayload]
        if not terms:
            filtered = list(MOCK_CANDIDATES)
        else:
            filtered = []
            for candidate in MOCK_CANDIDATES:
                haystack = " ".join(
                    [
                        candidate["title"],
                        candidate["company"],
                        candidate["location"],
                        candidate["summary"],
                        " ".join(candidate["resumeProjection"]["workSummaries"]),
                        " ".join(candidate["resumeProjection"]["projectNames"]),
                    ]
                ).lower()
                if any(term in haystack for term in terms):
                    filtered.append(candidate)
        total = len(filtered)
        start = (page_no - 1) * page_size
        page_items = filtered[start : start + page_size]
        candidates = [
            CandidateData(
                external_identity_id=str(item["external_identity_id"]),
                name=str(item["name"]),
                title=str(item["title"]),
                company=str(item["company"]),
                location=str(item["location"]),
                summary=str(item["summary"]),
                email=str(item["email"]),
                phone=str(item["phone"]),
                resume_projection=item["resumeProjection"],
            )
            for item in page_items
        ]
        upstream_data: JsonObject = {
            "candidates": [
                {
                    "id": str(item["external_identity_id"]),
                    "name": str(item["name"]),
                    "title": str(item["title"]),
                    "company": str(item["company"]),
                    "location": str(item["location"]),
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
            upstream_request=to_json_object({"page": page_no, "pageSize": page_size, **normalized_query}),
            upstream_response=to_json_object({"code": 200, "status": "ok", "message": "success", "data": upstream_data}),
        )


class MissingCtsCredentialsAdapter:
    def search_candidates(
        self,
        normalized_query: NormalizedQueryPayload,
        page_no: int,
        page_size: int,
    ) -> SearchPageData:
        return SearchPageData(
            status="failed",
            total=0,
            page_no=page_no,
            page_size=page_size,
            candidates=[],
            upstream_request=to_json_object({"page": page_no, "pageSize": page_size, **normalized_query}),
            upstream_response=to_json_object({"code": 40001, "status": "fail", "message": "CTS credentials not configured", "data": None}),
            error_code="CTS_NOT_CONFIGURED",
            error_message="CTS tenant credentials are not configured.",
        )


class CtsResumeSourceAdapter:
    def __init__(self, base_url: str, tenant_key: str, tenant_secret: str, timeout_seconds: int = 20) -> None:
        self.base_url = base_url.rstrip("/")
        self.tenant_key = tenant_key
        self.tenant_secret = tenant_secret
        self.timeout_seconds = timeout_seconds

    def search_candidates(
        self,
        normalized_query: NormalizedQueryPayload,
        page_no: int,
        page_size: int,
    ) -> SearchPageData:
        request_model = self._build_payload(normalized_query, page_no, page_size)
        payload = to_json_object(request_model.model_dump(exclude_none=True))
        response_body: JsonObject = {}
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
                raw_response: object = json.loads(resp.read().decode("utf-8"))
                response_model = CtsSearchResponseModel.model_validate(raw_response)
                response_body = to_json_object(response_model.model_dump(mode="json"))
        except urllib_error.HTTPError as exc:
            response_body = self._read_error_response(exc)
            return SearchPageData(
                status="failed",
                total=0,
                page_no=page_no,
                page_size=page_size,
                candidates=[],
                upstream_request=payload,
                upstream_response=response_body or to_json_object({"status": "fail", "message": f"HTTP {exc.code}"}),
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
                upstream_response=to_json_object({"status": "fail", "message": str(exc.reason)}),
                error_code="CTS_NETWORK_ERROR",
                error_message=f"CTS network error: {exc.reason}.",
            )
        except (JSONDecodeError, ValueError) as exc:
            return SearchPageData(
                status="failed",
                total=0,
                page_no=page_no,
                page_size=page_size,
                candidates=[],
                upstream_request=payload,
                upstream_response=response_body,
                error_code="CTS_RESPONSE_INVALID",
                error_message=f"CTS response did not match the validated schema: {exc}.",
            )

        code_value = response_body.get("code", 0)
        code = int(code_value) if isinstance(code_value, int | str) else 0
        if code == 20001:
            return SearchPageData(
                status="failed",
                total=0,
                page_no=page_no,
                page_size=page_size,
                candidates=[],
                upstream_request=payload,
                upstream_response=response_body,
                error_code="CTS_AUTH_FAILED",
                error_message=str(response_body.get("message") or "CTS authentication failed."),
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

        response_model = CtsSearchResponseModel.model_validate(response_body)
        if response_model.data is None:
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
        candidates = [self._map_candidate(item) for item in response_model.data.candidates]
        return SearchPageData(
            status="completed",
            total=response_model.data.total,
            page_no=int(response_model.data.page),
            page_size=int(response_model.data.pageSize),
            candidates=candidates,
            upstream_request=payload,
            upstream_response=to_json_object(response_model.model_dump(mode="json")),
        )

    def _build_payload(
        self,
        normalized_query: NormalizedQueryPayload,
        page_no: int,
        page_size: int,
    ) -> CtsRequestModel:
        filters = normalized_query["structuredFilters"]
        keyword = normalized_query["keyword"] or " ".join(
            normalized_query["mustTerms"] + normalized_query["shouldTerms"]
        )
        return CtsRequestModel(
            jd=normalized_query["jd"],
            keyword=keyword or None,
            school=filters.get("school"),
            company=filters.get("company"),
            position=filters.get("position"),
            workContent=filters.get("workContent"),
            location=filters.get("location"),
            degree=filters.get("degree"),
            schoolType=filters.get("schoolType"),
            workExperienceRange=filters.get("workExperienceRange"),
            page=page_no,
            pageSize=page_size,
        )

    @staticmethod
    def _read_error_response(exc: urllib_error.HTTPError) -> JsonObject:
        try:
            payload: object = json.loads(exc.read().decode("utf-8"))
        except (JSONDecodeError, UnicodeDecodeError):
            return {}
        if isinstance(payload, dict):
            return to_json_object(cast(object, payload))
        return {}

    @staticmethod
    def _map_candidate(candidate: CtsCandidateModel) -> CandidateData:
        raw_candidate = to_json_object(candidate.model_dump(mode="json"))
        external_id = resume_hash(raw_candidate)
        work_experience = sorted(
            candidate.workExperienceList,
            key=lambda item: item.sortNum if item.sortNum is not None else 999,
        )
        latest_work = work_experience[0] if work_experience else None
        title = (
            (latest_work.title if latest_work else None)
            or candidate.expectedJobCategory
            or "匿名候选人"
        )
        company = (latest_work.company if latest_work else None) or "未知公司"
        location = candidate.nowLocation or candidate.expectedLocation or "未知地点"
        name = candidate.name or candidate.resumeName or f"匿名候选人-{external_id[:6]}"
        projection = CtsResumeSourceAdapter._build_resume_projection(candidate)
        summary_parts = [
            f"{candidate.workYear}年经验",
            title,
            company,
            projection["education"][0]["school"] if projection["education"] else None,
            projection["education"][0]["degree"] if projection["education"] else None,
        ]
        if projection["workSummaries"]:
            summary_parts.append(projection["workSummaries"][0][:120])
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
            resume_projection=projection,
        )

    @staticmethod
    def _build_resume_projection(candidate: CtsCandidateModel) -> ResumeProjectionPayload:
        education_items = sorted(
            candidate.educationList,
            key=lambda item: item.sortNum if item.sortNum is not None else 999,
        )
        work_items = sorted(
            candidate.workExperienceList,
            key=lambda item: item.sortNum if item.sortNum is not None else 999,
        )
        education: list[ResumeEducationItemPayload] = [
            {
                "school": item.school or "未提供学校",
                "degree": item.degree or item.education or "学历未知",
                "major": item.speciality or "专业未知",
                "startTime": item.startTime,
                "endTime": item.endTime,
            }
            for item in education_items[:5]
        ]
        work_experience: list[ResumeWorkExperienceItemPayload] = [
            {
                "company": item.company or "未提供公司",
                "title": item.title or "职位未知",
                "duration": item.duration,
                "startTime": item.startTime,
                "endTime": item.endTime,
                "summary": item.summary,
            }
            for item in work_items[:8]
        ]
        return {
            "workYear": candidate.workYear,
            "currentLocation": candidate.nowLocation,
            "expectedLocation": candidate.expectedLocation,
            "jobState": candidate.jobState,
            "expectedSalary": candidate.expectedSalary,
            "age": candidate.age,
            "education": education,
            "workExperience": work_experience,
            "workSummaries": candidate.workSummariesAll[:5],
            "projectNames": candidate.projectNameAll[:8],
        }


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
        return MisconfiguredLLMAdapter(
            f"Unsupported CVM_LLM_PROVIDER: {settings.llm_provider}",
        )
    if not settings.llm_api_key:
        return MisconfiguredLLMAdapter(
            "OPENAI_API_KEY is required when CVM_LLM_MODE is not stub.",
        )
    return OpenAILLMAdapter(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        timeout_seconds=settings.llm_timeout_seconds,
    )
