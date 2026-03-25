from __future__ import annotations

import json

import pytest
from hypothesis import given, strategies as st
from pydantic import ValidationError as PydanticValidationError

from cvm_platform.infrastructure.adapters import CtsResumeSourceAdapter, OpenAILLMAdapter
from cvm_platform.infrastructure.boundary_models import CtsCandidateModel, StructuredFiltersBoundaryModel


ALLOWED_FILTER_KEYS = {
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
TEXT = st.text(min_size=1, max_size=20).filter(lambda value: bool(value.strip()))


STRUCTURED_FILTERS = st.fixed_dictionaries(
    {
        "page": st.integers(min_value=1, max_value=5),
        "pageSize": st.integers(min_value=1, max_value=50),
    },
    optional={
        "location": st.lists(TEXT, min_size=1, max_size=3),
        "degree": st.integers(min_value=0, max_value=5),
        "schoolType": st.integers(min_value=0, max_value=5),
        "workExperienceRange": st.integers(min_value=0, max_value=6),
        "position": TEXT,
        "workContent": TEXT,
        "company": TEXT,
        "school": TEXT,
    },
)


OPENAI_DRAFTS = st.fixed_dictionaries(
    {
        "must_terms": st.lists(TEXT, min_size=1, max_size=4),
        "should_terms": st.lists(TEXT, max_size=8),
        "exclude_terms": st.lists(TEXT, max_size=4),
        "structured_filters": STRUCTURED_FILTERS,
        "evidence_refs": st.lists(
            st.fixed_dictionaries({"label": TEXT, "excerpt": TEXT}),
            min_size=1,
            max_size=4,
        ),
    }
)


CTS_CANDIDATES = st.fixed_dictionaries(
    {
        "activeStatus": TEXT,
        "age": st.integers(min_value=18, max_value=65),
        "educationList": st.lists(
            st.fixed_dictionaries(
                {
                    "degree": st.one_of(TEXT, st.none()),
                    "education": st.one_of(TEXT, st.none()),
                    "school": st.one_of(TEXT, st.none()),
                    "speciality": st.one_of(TEXT, st.none()),
                    "startTime": st.one_of(TEXT, st.none()),
                    "endTime": st.one_of(TEXT, st.none()),
                    "sortNum": st.one_of(st.integers(min_value=0, max_value=10), st.none()),
                }
            ),
            min_size=1,
            max_size=8,
        ),
        "expectedIndustry": TEXT,
        "expectedIndustryIds": st.lists(TEXT, min_size=1, max_size=3),
        "expectedJobCategory": TEXT,
        "expectedJobCategoryIds": st.lists(TEXT, min_size=1, max_size=3),
        "expectedLocation": TEXT,
        "expectedLocationIds": st.lists(TEXT, min_size=1, max_size=3),
        "expectedSalary": TEXT,
        "gender": TEXT,
        "jobState": TEXT,
        "nowLocation": TEXT,
        "projectNameAll": st.lists(TEXT, min_size=0, max_size=12),
        "workExperienceList": st.lists(
            st.fixed_dictionaries(
                {
                    "company": st.one_of(TEXT, st.none()),
                    "title": st.one_of(TEXT, st.none()),
                    "duration": st.one_of(TEXT, st.none()),
                    "summary": st.one_of(TEXT, st.none()),
                    "startTime": st.one_of(TEXT, st.none()),
                    "endTime": st.one_of(TEXT, st.none()),
                    "sortNum": st.one_of(st.integers(min_value=0, max_value=10), st.none()),
                }
            ),
            min_size=1,
            max_size=10,
        ),
        "workSummariesAll": st.lists(TEXT, min_size=0, max_size=12),
        "workYear": st.integers(min_value=0, max_value=40),
        "name": st.one_of(TEXT, st.none()),
        "resumeName": st.one_of(TEXT, st.none()),
    }
)


@given(STRUCTURED_FILTERS)
def test_structured_filters_round_trip(payload: dict[str, object]) -> None:
    model = StructuredFiltersBoundaryModel.model_validate(payload)
    dumped = model.model_dump(exclude_none=True)
    assert dumped["page"] >= 1
    assert dumped["pageSize"] >= 1
    assert set(dumped).issubset(ALLOWED_FILTER_KEYS)


@given(
    st.text(min_size=1, max_size=12).filter(lambda key: key not in ALLOWED_FILTER_KEYS),
    st.one_of(TEXT, st.integers(min_value=0, max_value=10)),
)
def test_structured_filters_reject_unknown_keys(extra_key: str, extra_value: str | int) -> None:
    with pytest.raises(PydanticValidationError):
        StructuredFiltersBoundaryModel.model_validate({"page": 1, "pageSize": 10, extra_key: extra_value})


@given(OPENAI_DRAFTS)
def test_openai_keyword_parser_enforces_contract_shape(payload: dict[str, object]) -> None:
    adapter = OpenAILLMAdapter(api_key="test-key", model="gpt-5.4-mini")
    draft = adapter._parse_draft(json.dumps(payload, ensure_ascii=False))
    assert 1 <= len(draft.must_terms) <= 4
    assert len(draft.should_terms) <= 6
    assert set(draft.structured_filters).issubset(ALLOWED_FILTER_KEYS)
    assert all(term not in draft.must_terms for term in draft.should_terms)


@given(CTS_CANDIDATES)
def test_cts_candidate_mapping_produces_bounded_projection(payload: dict[str, object]) -> None:
    candidate = CtsCandidateModel.model_validate(payload)
    mapped = CtsResumeSourceAdapter._map_candidate(candidate)
    projection = mapped.resume_projection

    assert mapped.external_identity_id
    assert mapped.summary
    assert len(projection["education"]) <= 5
    assert len(projection["workExperience"]) <= 8
    assert len(projection["workSummaries"]) <= 5
    assert len(projection["projectNames"]) <= 8
