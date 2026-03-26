from __future__ import annotations

import json

import pytest

from cvm_platform.infrastructure.adapters import OpenAILLMAdapter


class FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self) -> "FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_openai_adapter_uses_default_model_for_deterministic_placeholder(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout: int):
        captured["timeout"] = timeout
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeHTTPResponse(
            {
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {
                                        "must_terms": ["Python", "FastAPI"],
                                        "should_terms": ["Angular"],
                                        "exclude_terms": [],
                                        "structured_filters": {"page": 1, "pageSize": 10, "location": ["上海"]},
                                        "evidence_refs": [{"label": "JD evidence 1", "excerpt": "Need Python FastAPI"}],
                                    }
                                ),
                            }
                        ]
                    }
                ]
            }
        )

    monkeypatch.setattr("cvm_platform.infrastructure.adapters.urllib_request.urlopen", fake_urlopen)

    adapter = OpenAILLMAdapter(
        api_key="test-key",
        model="gpt-5.4-mini",
        base_url="https://api.openai.com/v1",
        timeout_seconds=12,
    )
    draft = adapter.draft_keywords(
        "Need Python FastAPI in 上海",
        model_version="deterministic",
        prompt_version="draft-v1",
    )

    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["timeout"] == 12
    assert captured["payload"]["model"] == "gpt-5.4-mini"
    assert draft.must_terms == ["Python", "FastAPI"]
    assert draft.should_terms == ["Angular"]
    assert draft.structured_filters["location"] == ["上海"]
    assert draft.evidence_refs[0].excerpt == "Need Python FastAPI"


def test_openai_adapter_honors_explicit_requested_model(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout: int):
        del timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeHTTPResponse(
            {
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {
                                        "must_terms": ["Python"],
                                        "should_terms": [],
                                        "exclude_terms": [],
                                        "structured_filters": {"page": 1, "pageSize": 10},
                                        "evidence_refs": [{"label": "JD evidence 1", "excerpt": "Need Python"}],
                                    }
                                ),
                            }
                        ]
                    }
                ]
            }
        )

    monkeypatch.setattr("cvm_platform.infrastructure.adapters.urllib_request.urlopen", fake_urlopen)

    adapter = OpenAILLMAdapter(api_key="test-key", model="gpt-5.4-mini")
    adapter.draft_keywords(
        "Need Python",
        model_version="gpt-5.4",
        prompt_version="draft-v1",
    )

    assert captured["payload"]["model"] == "gpt-5.4"
