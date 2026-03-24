from __future__ import annotations

import json

import pytest

from cvm_platform.infrastructure.adapters import OpenAILLMAdapter, StubLLMAdapter, build_llm
from cvm_platform.settings.config import Settings


class FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self) -> "FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_build_llm_returns_stub_adapter_for_stub_mode() -> None:
    adapter = build_llm(Settings(_env_file=None, llm_mode="stub"))
    assert isinstance(adapter, StubLLMAdapter)


def test_build_llm_requires_api_key_for_live_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CVM_LLM_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        build_llm(Settings(_env_file=None, llm_mode="live", llm_provider="openai", llm_api_key=""))


def test_openai_adapter_uses_configured_default_model_for_placeholder(monkeypatch: pytest.MonkeyPatch) -> None:
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

    adapter = OpenAILLMAdapter(api_key="test-key", model="gpt-5.4-mini", base_url="https://api.openai.com/v1", timeout_seconds=12)
    draft = adapter.draft_keywords("Need Python FastAPI in 上海", model_version="stub-1", prompt_version="draft-v1")

    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["timeout"] == 12
    assert captured["payload"]["model"] == "gpt-5.4-mini"
    assert draft.must_terms == ["Python", "FastAPI"]
    assert draft.should_terms == ["Angular"]
    assert draft.structured_filters["location"] == ["上海"]
    assert draft.evidence_refs[0].excerpt == "Need Python FastAPI"
