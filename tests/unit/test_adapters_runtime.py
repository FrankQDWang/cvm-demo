from __future__ import annotations

import io
import json
from urllib import error as urllib_error

import pytest

from cvm_platform.domain.errors import ExternalDependencyError, TransientDependencyError
from cvm_platform.infrastructure.adapters import (
    CtsResumeSourceAdapter,
    MissingCtsCredentialsAdapter,
    MisconfiguredLLMAdapter,
    MockResumeSourceAdapter,
    OpenAILLMAdapter,
    StubLLMAdapter,
    build_llm,
    build_resume_source,
)
from cvm_platform.infrastructure.boundary_models import OpenAIResponsesEnvelopeModel
from cvm_platform.settings.config import Settings


class JsonHTTPResponse:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> "JsonHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class RawHTTPResponse:
    def __init__(self, body: str) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body.encode("utf-8")

    def __enter__(self) -> "RawHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def _build_http_error(code: int, body: str) -> urllib_error.HTTPError:
    return urllib_error.HTTPError(
        url="https://example.test",
        code=code,
        msg="boom",
        hdrs=None,
        fp=io.BytesIO(body.encode("utf-8")),
    )


def _normalized_query(*, keyword: str = "Python Agent") -> dict[str, object]:
    return {
        "jd": "Need Python Agent builders in Shanghai",
        "mustTerms": ["Python"],
        "shouldTerms": ["Agent"],
        "excludeTerms": [],
        "structuredFilters": {"page": 1, "pageSize": 10, "location": ["上海"]},
        "keyword": keyword,
    }


def _cts_candidate_payload() -> dict[str, object]:
    return {
        "activeStatus": "open",
        "age": 30,
        "educationList": [
            {
                "degree": "硕士",
                "education": "硕士",
                "educationCode": "1028",
                "school": "复旦大学",
                "schoolTags": [],
                "speciality": "计算机科学",
                "startTime": "2014-09",
                "endTime": "2017-06",
                "sortNum": 1,
            }
        ],
        "expectedIndustry": "AI",
        "expectedIndustryIds": ["1"],
        "expectedJobCategory": "算法工程师",
        "expectedJobCategoryIds": ["2"],
        "expectedLocation": "上海",
        "expectedLocationIds": ["310000"],
        "expectedSalary": "50k-70k",
        "gender": "M",
        "jobState": "在职",
        "nowLocation": "上海",
        "projectNameAll": ["Voice Agent Platform"],
        "workExperienceList": [
            {
                "company": "OpenAI",
                "title": "研究员",
                "duration": "3年",
                "level": 2,
                "summary": "构建多代理工作流",
                "tagNames": [],
                "startTime": "2021-01",
                "endTime": "2024-01",
                "sortNum": 1,
            }
        ],
        "workSummariesAll": ["负责 Agent 检索与评估系统"],
        "workYear": 6,
        "name": "张三",
        "resumeName": "张三简历",
    }


def test_stub_llm_adapter_extracts_high_signal_filters() -> None:
    draft = StubLLMAdapter().draft_keywords(
        "上海 985 硕士 5年以上 算法工程师 Agent ReAct LLM",
        model_version="stub-1",
        prompt_version="draft-v1",
    )

    assert "Agent" in draft.must_terms
    assert "ReAct" in draft.must_terms
    assert "LLM" in draft.should_terms
    assert "算法工程师" in draft.should_terms
    assert draft.structured_filters["location"] == ["上海"]
    assert draft.structured_filters["degree"] == 3
    assert draft.structured_filters["schoolType"] == 3
    assert draft.structured_filters["workExperienceRange"] == 5
    assert draft.structured_filters["position"] == "算法工程师"
    assert "Agent" in (draft.structured_filters["workContent"] or "")
    assert len(draft.evidence_refs) == 2


def test_stub_llm_adapter_falls_back_to_plain_terms() -> None:
    draft = StubLLMAdapter().draft_keywords(
        "Rust Elixir Phoenix distributed systems",
        model_version="stub-1",
        prompt_version="draft-v1",
    )

    assert "Rust" in draft.must_terms
    assert "Elixir" in draft.must_terms
    assert draft.structured_filters == {"page": 1, "pageSize": 10}


@pytest.mark.parametrize(
    ("error_factory", "expected_type", "expected_code"),
    [
        (
            lambda: _build_http_error(503, '{"error":"retry later"}'),
            TransientDependencyError,
            "OPENAI_HTTP_ERROR",
        ),
        (
            lambda: _build_http_error(400, '{"error":"bad request"}'),
            ExternalDependencyError,
            "OPENAI_HTTP_ERROR",
        ),
        (
            lambda: urllib_error.URLError("dns down"),
            TransientDependencyError,
            "OPENAI_NETWORK_ERROR",
        ),
    ],
)
def test_openai_adapter_surfaces_transport_failures(
    monkeypatch: pytest.MonkeyPatch,
    error_factory,
    expected_type: type[Exception],
    expected_code: str,
) -> None:
    def fake_urlopen(request, timeout: int):
        del request, timeout
        raise error_factory()

    monkeypatch.setattr("cvm_platform.infrastructure.adapters.urllib_request.urlopen", fake_urlopen)

    adapter = OpenAILLMAdapter(api_key="test-key", model="gpt-5.4-mini")
    with pytest.raises(expected_type) as exc_info:
        adapter.draft_keywords("Need Python", model_version="stub-1", prompt_version="draft-v1")

    assert getattr(exc_info.value, "code") == expected_code


def test_openai_adapter_rejects_invalid_json_and_empty_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cvm_platform.infrastructure.adapters.urllib_request.urlopen",
        lambda request, timeout: RawHTTPResponse("not-json"),
    )
    adapter = OpenAILLMAdapter(api_key="test-key", model="gpt-5.4-mini")

    with pytest.raises(ExternalDependencyError, match="valid JSON"):
        adapter.draft_keywords("Need Python", model_version="stub-1", prompt_version="draft-v1")

    with pytest.raises(ExternalDependencyError, match="output_text"):
        adapter._extract_output_text(
            OpenAIResponsesEnvelopeModel.model_validate(
                {"output": [{"content": [{"type": "message"}]}]}
            )
        )

    with pytest.raises(ExternalDependencyError, match="JSON object"):
        adapter._parse_draft("No JSON body present here")


def test_mock_and_missing_resume_sources_return_contract_failures() -> None:
    query = _normalized_query()
    invalid_page = MockResumeSourceAdapter().search_candidates(query, page_no=0, page_size=10)
    assert invalid_page.error_code == "CTS_PARAM_ANOMALY"

    filtered_page = MockResumeSourceAdapter().search_candidates(query, page_no=1, page_size=1)
    assert filtered_page.status == "completed"
    assert filtered_page.total >= 1
    assert len(filtered_page.candidates) == 1

    missing = MissingCtsCredentialsAdapter().search_candidates(query, page_no=1, page_size=10)
    assert missing.error_code == "CTS_NOT_CONFIGURED"


def test_build_resume_source_and_llm_select_expected_adapters() -> None:
    assert isinstance(build_resume_source(Settings(_env_file=None, resume_source_mode="mock")), MockResumeSourceAdapter)
    assert isinstance(
        build_resume_source(
            Settings(
                _env_file=None,
                resume_source_mode="cts",
                cts_tenant_key="tenant-key",
                cts_tenant_secret="tenant-secret",
            )
        ),
        CtsResumeSourceAdapter,
    )
    assert isinstance(
        build_resume_source(Settings(_env_file=None, resume_source_mode="cts", cts_tenant_key="", cts_tenant_secret="")),
        MissingCtsCredentialsAdapter,
    )

    llm = build_llm(Settings(_env_file=None, llm_mode="live", llm_provider="anthropic", llm_api_key="test-key"))
    assert isinstance(llm, MisconfiguredLLMAdapter)
    with pytest.raises(Exception, match="Unsupported CVM_LLM_PROVIDER"):
        llm.draft_keywords("Need Python", "gpt-5.4-mini", "draft-v1")


def test_cts_resume_source_adapter_maps_successful_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cvm_platform.infrastructure.adapters.urllib_request.urlopen",
        lambda request, timeout: JsonHTTPResponse(
            {
                "code": 200,
                "status": "ok",
                "message": "success",
                "data": {
                    "candidates": [_cts_candidate_payload()],
                    "total": 1,
                    "page": 1,
                    "pageSize": 10,
                },
                "timings": {
                    "validation": 1,
                    "configPreparation": 1,
                    "paramsPreparation": 1,
                    "apiRequest": 1,
                    "dataProcessing": 1,
                    "totalTime": 6,
                },
            }
        ),
    )

    adapter = CtsResumeSourceAdapter(
        base_url="https://cts.example.com",
        tenant_key="tenant-key",
        tenant_secret="tenant-secret",
    )
    result = adapter.search_candidates(_normalized_query(keyword=""), page_no=1, page_size=10)

    assert result.status == "completed"
    assert result.total == 1
    assert result.upstream_request["keyword"] == "Python Agent"
    assert result.candidates[0].name == "张三"
    assert result.candidates[0].title == "研究员"
    assert result.candidates[0].company == "OpenAI"
    assert result.candidates[0].resume_projection["education"][0]["school"] == "复旦大学"
    assert "Agent" in result.candidates[0].summary


def test_cts_resume_source_adapter_returns_documented_failure_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = CtsResumeSourceAdapter(
        base_url="https://cts.example.com",
        tenant_key="tenant-key",
        tenant_secret="tenant-secret",
    )

    monkeypatch.setattr(
        "cvm_platform.infrastructure.adapters.urllib_request.urlopen",
        lambda request, timeout: (_ for _ in ()).throw(_build_http_error(401, '{"status":"fail","message":"bad creds"}')),
    )
    http_error = adapter.search_candidates(_normalized_query(), page_no=1, page_size=10)
    assert http_error.error_code == "CTS_HTTP_ERROR"
    assert http_error.upstream_response["message"] == "bad creds"

    monkeypatch.setattr(
        "cvm_platform.infrastructure.adapters.urllib_request.urlopen",
        lambda request, timeout: (_ for _ in ()).throw(urllib_error.URLError("network down")),
    )
    network_error = adapter.search_candidates(_normalized_query(), page_no=1, page_size=10)
    assert network_error.error_code == "CTS_NETWORK_ERROR"

    monkeypatch.setattr(
        "cvm_platform.infrastructure.adapters.urllib_request.urlopen",
        lambda request, timeout: RawHTTPResponse("not-json"),
    )
    invalid_response = adapter.search_candidates(_normalized_query(), page_no=1, page_size=10)
    assert invalid_response.error_code == "CTS_RESPONSE_INVALID"


def test_cts_resume_source_adapter_handles_auth_and_parameter_anomalies(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = CtsResumeSourceAdapter(
        base_url="https://cts.example.com",
        tenant_key="tenant-key",
        tenant_secret="tenant-secret",
    )

    monkeypatch.setattr(
        "cvm_platform.infrastructure.adapters.urllib_request.urlopen",
        lambda request, timeout: JsonHTTPResponse(
            {
                "code": 20001,
                "status": "fail",
                "message": "tenant auth failed",
                "data": None,
            }
        ),
    )
    auth_failed = adapter.search_candidates(_normalized_query(), page_no=1, page_size=10)
    assert auth_failed.error_code == "CTS_AUTH_FAILED"

    monkeypatch.setattr(
        "cvm_platform.infrastructure.adapters.urllib_request.urlopen",
        lambda request, timeout: JsonHTTPResponse(
            {
                "code": 200,
                "status": "ok",
                "message": "success",
                "data": None,
            }
        ),
    )
    param_anomaly = adapter.search_candidates(_normalized_query(), page_no=1, page_size=10)
    assert param_anomaly.error_code == "CTS_PARAM_ANOMALY"
