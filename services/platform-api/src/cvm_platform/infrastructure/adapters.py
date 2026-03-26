from __future__ import annotations

import json
import re
import uuid
from json import JSONDecodeError
from typing import cast
from urllib import error as urllib_error
from urllib import request as urllib_request

from cvm_platform.application.policies import resume_hash
from cvm_platform.domain.ports import ResumeSourcePort
from cvm_platform.domain.errors import (
    ExternalDependencyError,
    TransientDependencyError,
)
from cvm_platform.domain.types import (
    AgentSearchStrategyData,
    CandidateData,
    ConditionPlanDraftData,
    EvidenceRef,
    JsonObject,
    NormalizedQueryPayload,
    ResumeMatchData,
    ResumeEducationItemPayload,
    ResumeProjectionPayload,
    SearchReflectionData,
    SearchQueryPayload,
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
    OpenAIAgentSearchStrategyModel,
    OpenAIKeywordDraftModel,
    OpenAIResumeMatchModel,
    OpenAIResponsesEnvelopeModel,
    OpenAISearchReflectionModel,
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
PLACEHOLDER_MODEL_VERSIONS = {"", "default", "deterministic"}


def _dump_structured_filters(model: StructuredFiltersBoundaryModel) -> StructuredFiltersPayload:
    return cast(StructuredFiltersPayload, cast(object, model.model_dump(exclude_none=True)))


def _dump_search_query(
    *,
    keyword: str,
    must_terms: list[str],
    should_terms: list[str],
    exclude_terms: list[str],
    structured_filters: StructuredFiltersBoundaryModel,
) -> SearchQueryPayload:
    normalized_must_terms = [term.strip() for term in must_terms[:4] if term.strip()]
    return {
        "keyword": keyword.strip(),
        "mustTerms": normalized_must_terms,
        "shouldTerms": [
            term.strip()
            for term in should_terms[:6]
            if term.strip() and term.strip() not in normalized_must_terms
        ],
        "excludeTerms": [term.strip() for term in exclude_terms[:4] if term.strip()],
        "structuredFilters": _dump_structured_filters(structured_filters),
    }


def _candidate_haystack(candidate: CandidateData) -> str:
    projection = candidate.resume_projection
    return " ".join(
        [
            candidate.name,
            candidate.title,
            candidate.company,
            candidate.location,
            candidate.summary,
            " ".join(projection["workSummaries"]),
            " ".join(projection["projectNames"]),
            " ".join(
                f"{item['company']} {item['title']} {item['summary'] or ''}"
                for item in projection["workExperience"]
            ),
            " ".join(f"{item['school']} {item['degree']} {item['major']}" for item in projection["education"]),
        ]
    ).lower()


def _heuristic_resume_match_data(
    *,
    candidate: CandidateData,
    strategy: NormalizedQueryPayload,
    model_version: str,
    prompt_version: str,
) -> ResumeMatchData:
    haystack = _candidate_haystack(candidate)
    must_hits = [term for term in strategy["mustTerms"] if term.lower() in haystack]
    should_hits = [term for term in strategy["shouldTerms"] if term.lower() in haystack]
    exclude_hits = [term for term in strategy["excludeTerms"] if term.lower() in haystack]
    score = 0.35
    if strategy["mustTerms"]:
        score += 0.35 * (len(must_hits) / max(len(strategy["mustTerms"]), 1))
    if strategy["shouldTerms"]:
        score += 0.2 * (len(should_hits) / max(len(strategy["shouldTerms"]), 1))
    if exclude_hits:
        score -= 0.25
    score = max(0.0, min(score, 0.99))
    reasons: list[str] = []
    if must_hits:
        reasons.append(f"命中必须项：{', '.join(must_hits[:3])}")
    if should_hits:
        reasons.append(f"命中核心项：{', '.join(should_hits[:3])}")
    if not reasons:
        reasons.append("与目标岗位存在较强相关性")
    return ResumeMatchData(
        prompt_text="heuristic-resume-match",
        model_version=model_version,
        prompt_version=prompt_version,
        score=score,
        summary="；".join(reasons),
        evidence=must_hits[:3] + should_hits[:2],
        concerns=[f"命中排除词：{term}" for term in exclude_hits[:2]],
    )


class StubLLMAdapter:
    def draft_keywords(
        self,
        jd_text: str,
        model_version: str,
        prompt_version: str,
    ) -> ConditionPlanDraftData:
        del model_version, prompt_version
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

    def extract_agent_search_strategy(
        self,
        jd_text: str,
        sourcing_preference_text: str,
        model_version: str,
        prompt_version: str,
    ) -> AgentSearchStrategyData:
        draft = self.draft_keywords(f"{jd_text}\n{sourcing_preference_text}", model_version, prompt_version)
        keyword = " ".join(draft.must_terms + draft.should_terms).strip() or draft.must_terms[0]
        round_1_filters = StructuredFiltersBoundaryModel.model_validate(
            {
                key: value
                for key, value in draft.structured_filters.items()
                if key in {"page", "pageSize", "location", "position", "company", "school"}
            }
            or {"page": 1, "pageSize": 10}
        )
        return AgentSearchStrategyData(
            prompt_text="中文启发式首轮检索计划",
            model_version=model_version,
            prompt_version=prompt_version,
            must_requirements=draft.must_terms[:4],
            core_requirements=draft.should_terms[:4],
            bonus_requirements=draft.should_terms[4:6],
            exclude_signals=draft.exclude_terms[:4],
            round_1_query=_dump_search_query(
                keyword=keyword,
                must_terms=draft.must_terms,
                should_terms=draft.should_terms,
                exclude_terms=draft.exclude_terms,
                structured_filters=round_1_filters,
            ),
            summary=f"已提炼出 {len(draft.must_terms)} 个必须项，并为首轮 CTS 生成宽召回查询。",
        )

    def analyze_resume_match(
        self,
        jd_text: str,
        sourcing_preference_text: str,
        strategy: NormalizedQueryPayload,
        candidate: CandidateData,
        model_version: str,
        prompt_version: str,
    ) -> ResumeMatchData:
        del jd_text, sourcing_preference_text
        return _heuristic_resume_match_data(
            candidate=candidate,
            strategy=strategy,
            model_version=model_version,
            prompt_version=prompt_version,
        )

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
    ) -> SearchReflectionData:
        del jd_text, sourcing_preference_text, round_ledger, seen_candidate_count
        keyword = strategy["keyword"]
        must_terms = list(strategy["mustTerms"])
        should_terms = list(strategy["shouldTerms"])
        filters = dict(strategy["structuredFilters"])
        reason = "继续沿当前方向检索更多未见候选。"
        next_round_goal = "补充更多可供排序的新候选。"
        continue_search = round_no < max_rounds
        if new_candidate_count == 0 and should_terms:
            dropped_term = should_terms[-1]
            should_terms = should_terms[:-1]
            keyword = " ".join(must_terms + should_terms).strip() or keyword
            reason = f"上一轮没有新增候选，先去掉较弱核心词“{dropped_term}”，尝试放宽召回。"
            next_round_goal = "在保持岗位主轴不变的前提下扩大召回。"
            for filter_key in ["schoolType", "workExperienceRange", "degree"]:
                filters.pop(filter_key, None)
        elif new_candidate_count == 0 and round_no + 1 >= max_rounds:
            continue_search = False
            reason = "靠近轮次上限且没有新增候选，建议停止检索。"
            next_round_goal = "停止并输出当前 shortlist。"
        return SearchReflectionData(
            prompt_text="中文启发式轮次反思",
            model_version=model_version,
            prompt_version=prompt_version,
            continue_search=continue_search,
            reason=reason,
            next_round_goal=next_round_goal,
            next_round_query={
                "keyword": keyword,
                "mustTerms": must_terms,
                "shouldTerms": should_terms,
                "excludeTerms": list(strategy["excludeTerms"]),
                "structuredFilters": cast(StructuredFiltersPayload, cast(object, filters)),
            },
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

    def extract_agent_search_strategy(
        self,
        jd_text: str,
        sourcing_preference_text: str,
        model_version: str,
        prompt_version: str,
    ) -> AgentSearchStrategyData:
        resolved_model = self._resolve_model(model_version)
        prompt = self._build_agent_search_strategy_prompt(
            jd_text=jd_text,
            sourcing_preference_text=sourcing_preference_text,
            model_version=resolved_model,
            prompt_version=prompt_version,
        )
        response = self._responses_request(
            {
                "model": resolved_model,
                "input": prompt,
                "max_output_tokens": 700,
            }
        )
        output_text = self._extract_output_text(response)
        return self._parse_agent_search_strategy(output_text, prompt, resolved_model, prompt_version)

    def analyze_resume_match(
        self,
        jd_text: str,
        sourcing_preference_text: str,
        strategy: NormalizedQueryPayload,
        candidate: CandidateData,
        model_version: str,
        prompt_version: str,
    ) -> ResumeMatchData:
        resolved_model = self._resolve_model(model_version)
        prompt = self._build_resume_match_prompt(
            jd_text=jd_text,
            sourcing_preference_text=sourcing_preference_text,
            strategy=strategy,
            candidate=candidate,
            model_version=resolved_model,
            prompt_version=prompt_version,
        )
        response = self._responses_request(
            {
                "model": resolved_model,
                "input": prompt,
                "max_output_tokens": 800,
            }
        )
        output_text = self._extract_output_text(response)
        return self._parse_resume_match(output_text, prompt, resolved_model, prompt_version)

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
    ) -> SearchReflectionData:
        resolved_model = self._resolve_model(model_version)
        prompt = self._build_search_reflection_prompt(
            jd_text=jd_text,
            sourcing_preference_text=sourcing_preference_text,
            strategy=strategy,
            round_ledger=round_ledger,
            round_no=round_no,
            max_rounds=max_rounds,
            new_candidate_count=new_candidate_count,
            seen_candidate_count=seen_candidate_count,
            model_version=resolved_model,
            prompt_version=prompt_version,
        )
        response = self._responses_request(
            {
                "model": resolved_model,
                "input": prompt,
                "max_output_tokens": 700,
            }
        )
        output_text = self._extract_output_text(response)
        return self._parse_search_reflection(output_text, prompt, resolved_model, prompt_version)

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

    @staticmethod
    def _build_agent_search_strategy_prompt(
        *,
        jd_text: str,
        sourcing_preference_text: str,
        model_version: str,
        prompt_version: str,
    ) -> str:
        return f"""
你是寻访 Agent 的首轮策略提取器。

请直接返回 JSON，不要加 Markdown 代码块。JSON 必须严格匹配这个结构：
{{
  "must_requirements": ["必须条件短语"],
  "core_requirements": ["核心能力短语"],
  "bonus_requirements": ["加分项短语"],
  "exclude_signals": ["排除信号短语"],
  "round_1_query": {{
    "keyword": "首轮 CTS 检索关键词",
    "must_terms": ["首轮必须携带的检索词"],
    "should_terms": ["首轮可携带的核心检索词"],
    "exclude_terms": ["首轮排除词"],
    "structured_filters": {{
      "page": 1,
      "pageSize": 10,
      "location": ["上海"],
      "degree": 2,
      "schoolType": 3,
      "workExperienceRange": 4,
      "position": "算法工程师",
      "workContent": "Agent Python"
    }}
  }},
  "summary": "一句中文总结"
}}

规则：
- 你要先理解职位真正需要的能力，再决定首轮 CTS 查询。
- `must_requirements` 代表业务上不能缺失的要求，限制 1-6 个短语。
- `core_requirements` 代表强相关核心能力，限制 0-8 个短语。
- `bonus_requirements` 代表加分项，限制 0-8 个短语。
- `exclude_signals` 代表明显不合适的信号，限制 0-6 个短语。
- `round_1_query` 只服务首轮召回，不要把所有条件一次性压到最窄。
- `keyword` 必须是会真正发给 CTS 的短检索串，不要写成句子。
- `must_terms` 限制 1-4 个，`should_terms` 限制 0-6 个。
- 只有在输入里有明确依据且确实适合 CTS 检索时，才填写 `structured_filters`。
- `structured_filters` 只允许包含：page, pageSize, location, degree, schoolType, workExperienceRange, position, workContent, company, school。
- 始终包含 `page=1` 和 `pageSize=10`。
- 优先抽取真正影响寻访成败的岗位能力，不要被噪音描述带偏。

model_version={model_version}
prompt_version={prompt_version}

JD:
{jd_text}

寻访偏好:
{sourcing_preference_text}
""".strip()

    @staticmethod
    def _build_resume_match_prompt(
        *,
        jd_text: str,
        sourcing_preference_text: str,
        strategy: NormalizedQueryPayload,
        candidate: CandidateData,
        model_version: str,
        prompt_version: str,
    ) -> str:
        return f"""
你要判断一份简历是否应该留在 shortlist。

请直接返回 JSON，不要加 Markdown 代码块。JSON 必须严格匹配这个结构：
{{
  "score": 0.0,
  "summary": "一句中文总结，说明为什么该保留或淘汰",
  "evidence": ["简短事实依据"],
  "concerns": ["明确风险或缺口"]
}}

规则：
- `score` 必须在 0 到 1 之间。
- `summary` 必须是简洁中文，不要空话。
- `evidence` 只能写来自候选人资料的短事实。
- `concerns` 必须是明确缺口，不要写泛泛提醒。
- 你的任务是帮助每轮从候选池里保留更强的 5 个，而不是生成长报告。

model_version={model_version}
prompt_version={prompt_version}

JD:
{jd_text}

寻访偏好:
{sourcing_preference_text}

检索策略:
{json.dumps(strategy, ensure_ascii=False, indent=2)}

候选人资料:
{json.dumps(
    {
        "externalIdentityId": candidate.external_identity_id,
        "name": candidate.name,
        "title": candidate.title,
        "company": candidate.company,
        "location": candidate.location,
        "summary": candidate.summary,
        "resumeProjection": candidate.resume_projection,
    },
    ensure_ascii=False,
    indent=2,
)}
""".strip()

    @staticmethod
    def _build_search_reflection_prompt(
        *,
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
    ) -> str:
        return f"""
你是寻访 Agent 的轮次反思器。

你会看到原始输入、当前查询和 append-only 的轮次账本。账本只追加，不能改写历史。

请直接返回 JSON，不要加 Markdown 代码块。JSON 必须严格匹配这个结构：
{{
  "continue_search": true,
  "reason": "一句中文解释为什么继续或停止",
  "next_round_goal": "下一轮检索目标",
  "next_round_query": {{
    "keyword": "下一轮 CTS 检索关键词",
    "must_terms": ["下一轮必须携带的检索词"],
    "should_terms": ["下一轮可携带的检索词"],
    "exclude_terms": ["下一轮排除词"],
    "structured_filters": {{
      "page": 1,
      "pageSize": 10,
      "location": ["上海"],
      "degree": 2,
      "schoolType": 3,
      "workExperienceRange": 4,
      "position": "算法工程师",
      "workContent": "Agent Python"
    }}
  }}
}}

规则：
- 你只能调整下一轮 CTS 查询，不能发明新工具或新流程阶段。
- 历史账本是 append-only 的，只能在它的基础上做判断。
- 如果本轮没有新增候选、重复过多、或候选质量明显不够，应优先考虑放宽或改写查询方向，而不是机械继续收紧。
- 如果当前 top 5 已经足够强，或继续搜索价值很低，可以设置 `continue_search=false`。
- `next_round_query` 只服务下一轮，不要试图一次性解决所有约束。
- `keyword` 必须是短检索串，不要写成句子。
- `must_terms` 限制 1-4 个，`should_terms` 限制 0-6 个。
- `structured_filters` 只允许包含：page, pageSize, location, degree, schoolType, workExperienceRange, position, workContent, company, school。
- 始终包含 `page=1` 和 `pageSize=10`。

model_version={model_version}
prompt_version={prompt_version}

当前轮次状态：
- round_no={round_no}
- max_rounds={max_rounds}
- new_candidate_count={new_candidate_count}
- seen_candidate_count={seen_candidate_count}

JD:
{jd_text}

寻访偏好:
{sourcing_preference_text}

当前查询:
{json.dumps(strategy, ensure_ascii=False, indent=2)}

轮次账本:
{json.dumps(round_ledger, ensure_ascii=False, indent=2)}
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
        except TimeoutError as exc:
            raise TransientDependencyError(
                "OPENAI_TIMEOUT",
                "OpenAI request timed out.",
            ) from exc
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

    @staticmethod
    def _extract_json_payload(raw_text: str) -> JsonObject:
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
        except (JSONDecodeError, ValueError) as exc:
            raise ExternalDependencyError(
                "OPENAI_RESPONSE_INVALID",
                "OpenAI response did not match the required JSON schema.",
            ) from exc
        if not isinstance(payload_json, dict):
            raise ExternalDependencyError(
                "OPENAI_RESPONSE_INVALID",
                "OpenAI response JSON must be an object.",
            )
        return to_json_object(cast(object, payload_json))

    def _parse_draft(self, raw_text: str) -> ConditionPlanDraftData:
        draft = OpenAIKeywordDraftModel.model_validate(self._extract_json_payload(raw_text))

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

    def _parse_agent_search_strategy(
        self,
        raw_text: str,
        prompt_text: str,
        model_version: str,
        prompt_version: str,
    ) -> AgentSearchStrategyData:
        payload = OpenAIAgentSearchStrategyModel.model_validate(self._extract_json_payload(raw_text))
        round_1_filters = StructuredFiltersBoundaryModel.model_validate(
            payload.round_1_query.structured_filters.model_dump(exclude_none=True)
        )
        return AgentSearchStrategyData(
            prompt_text=prompt_text,
            model_version=model_version,
            prompt_version=prompt_version,
            must_requirements=[term.strip() for term in payload.must_requirements[:6] if term.strip()],
            core_requirements=[term.strip() for term in payload.core_requirements[:8] if term.strip()],
            bonus_requirements=[term.strip() for term in payload.bonus_requirements[:8] if term.strip()],
            exclude_signals=[term.strip() for term in payload.exclude_signals[:6] if term.strip()],
            round_1_query=_dump_search_query(
                keyword=payload.round_1_query.keyword,
                must_terms=payload.round_1_query.must_terms,
                should_terms=payload.round_1_query.should_terms,
                exclude_terms=payload.round_1_query.exclude_terms,
                structured_filters=round_1_filters,
            ),
            summary=payload.summary.strip(),
        )

    def _parse_resume_match(
        self,
        raw_text: str,
        prompt_text: str,
        model_version: str,
        prompt_version: str,
    ) -> ResumeMatchData:
        payload = OpenAIResumeMatchModel.model_validate(self._extract_json_payload(raw_text))
        score = max(0.0, min(payload.score, 0.99))
        return ResumeMatchData(
            prompt_text=prompt_text,
            model_version=model_version,
            prompt_version=prompt_version,
            score=score,
            summary=payload.summary.strip(),
            evidence=[item.strip() for item in payload.evidence[:5] if item.strip()],
            concerns=[item.strip() for item in payload.concerns[:5] if item.strip()],
        )

    def _parse_search_reflection(
        self,
        raw_text: str,
        prompt_text: str,
        model_version: str,
        prompt_version: str,
    ) -> SearchReflectionData:
        payload = OpenAISearchReflectionModel.model_validate(self._extract_json_payload(raw_text))
        next_round_filters = StructuredFiltersBoundaryModel.model_validate(
            payload.next_round_query.structured_filters.model_dump(exclude_none=True)
        )
        return SearchReflectionData(
            prompt_text=prompt_text,
            model_version=model_version,
            prompt_version=prompt_version,
            continue_search=payload.continue_search,
            reason=payload.reason.strip(),
            next_round_goal=payload.next_round_goal.strip(),
            next_round_query=_dump_search_query(
                keyword=payload.next_round_query.keyword,
                must_terms=payload.next_round_query.must_terms,
                should_terms=payload.next_round_query.should_terms,
                exclude_terms=payload.next_round_query.exclude_terms,
                structured_filters=next_round_filters,
            ),
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


def build_resume_source(settings: Settings) -> ResumeSourcePort:
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
