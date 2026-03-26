from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, cast

from openai import AsyncOpenAI
from pydantic_ai import Agent, RunContext
from pydantic_ai.durable_exec.temporal import TemporalAgent
from pydantic_ai.exceptions import UserError
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.providers.openai import OpenAIProvider
from temporalio.common import RetryPolicy
from temporalio.workflow import ActivityConfig

from cvm_platform.application.agent_runs import build_compact_round_ledger
from cvm_platform.domain.types import CandidateData, NormalizedQueryPayload, StructuredFiltersPayload
from cvm_platform.settings.config import Settings
from cvm_worker.models import (
    AgentRunStepModel,
    NormalizedStrategyModel,
    ResumeMatcherOutputModel,
    SearchReflectorOutputModel,
    SearchQueryModel,
    StrategyExtractorOutputModel,
    StructuredFiltersModel,
    WorkerCandidateModel,
)


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
INPUT_JSON_MARKER = "INPUT_JSON:\n"


@dataclass(frozen=True, slots=True)
class AgentBundle:
    strategy_extractor: TemporalAgent[None, StrategyExtractorOutputModel]
    resume_matcher: TemporalAgent[None, ResumeMatcherOutputModel]
    search_reflector: TemporalAgent[None, SearchReflectorOutputModel]

    @property
    def all_agents(
        self,
    ) -> list[
        TemporalAgent[None, StrategyExtractorOutputModel]
        | TemporalAgent[None, ResumeMatcherOutputModel]
        | TemporalAgent[None, SearchReflectorOutputModel]
    ]:
        return [
            self.strategy_extractor,
            self.resume_matcher,
            self.search_reflector,
        ]


def build_strategy_prompt(
    *,
    jd_text: str,
    sourcing_preference_text: str,
    prompt_version: str,
) -> str:
    payload = {
        "jdText": jd_text,
        "sourcingPreferenceText": sourcing_preference_text,
        "promptVersion": prompt_version,
    }
    return (
        "你是寻访 Agent 的首轮策略提取器。\n"
        "你要从 JD 和寻访偏好里识别真正决定成败的搜索信号。\n"
        "返回结构化结果，不要输出额外解释。\n"
        "要求：\n"
        "- mustRequirements 只保留真正不能缺失的要求。\n"
        "- coreRequirements 保留强相关核心能力。\n"
        "- bonusRequirements 仅保留真实加分项。\n"
        "- excludeSignals 仅保留明确不合适的信号。\n"
        "- round1Query 只服务第一轮 CTS 宽召回，不要一次收得过窄。\n"
        "- structuredFilters 只在输入有明确依据时填写。\n"
        "- 所有内容使用简洁中文短语。\n\n"
        f"{INPUT_JSON_MARKER}{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def build_resume_match_prompt(
    *,
    jd_text: str,
    sourcing_preference_text: str,
    strategy: NormalizedStrategyModel,
    candidate: WorkerCandidateModel,
    prompt_version: str,
) -> str:
    payload = {
        "jdText": jd_text,
        "sourcingPreferenceText": sourcing_preference_text,
        "strategy": strategy.model_dump(mode="json"),
        "candidate": candidate.model_dump(mode="json"),
        "promptVersion": prompt_version,
    }
    return (
        "你要判断一份简历是否应该留在 shortlist。\n"
        "返回结构化结果，不要输出额外解释。\n"
        "要求：\n"
        "- score 必须在 0 到 1 之间。\n"
        "- summary 必须说明保留或淘汰的核心原因。\n"
        "- evidence 只能写来自候选人资料的短事实。\n"
        "- concerns 只能写明确缺口或风险。\n"
        "- 你的目标是帮助每轮保留更强的前 5 个候选。\n\n"
        f"{INPUT_JSON_MARKER}{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def build_search_reflection_prompt(
    *,
    jd_text: str,
    sourcing_preference_text: str,
    strategy: NormalizedStrategyModel,
    steps: list[AgentRunStepModel],
    min_rounds: int,
    round_no: int,
    max_rounds: int,
    new_candidate_count: int,
    seen_candidate_count: int,
    prompt_version: str,
) -> str:
    payload = {
        "jdText": jd_text,
        "sourcingPreferenceText": sourcing_preference_text,
        "strategy": strategy.model_dump(mode="json"),
        "roundLedger": build_compact_round_ledger([step.to_payload() for step in steps]),
        "minRounds": min_rounds,
        "roundNo": round_no,
        "maxRounds": max_rounds,
        "newCandidateCount": new_candidate_count,
        "seenCandidateCount": seen_candidate_count,
        "promptVersion": prompt_version,
    }
    return (
        "你是寻访 Agent 的轮次反思器。\n"
        "你会看到当前查询和 append-only 的轮次账本，只能决定下一轮是否继续以及如何改写 CTS 查询。\n"
        "返回结构化结果，不要输出额外解释。\n"
        "要求：\n"
        "- 达到 minRounds 前，不要建议停止。\n"
        "- 如果没有新增候选或候选质量不够，优先考虑放宽或改写查询。\n"
        "- 如果当前 top 5 已够强或继续搜索价值很低，可以停止。\n"
        "- nextRoundQuery 只服务下一轮，不要试图一次性满足所有约束。\n"
        "- 所有结论都必须基于当前输入和 round ledger。\n\n"
        f"{INPUT_JSON_MARKER}{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def resolve_run_model(settings: Settings, model_version: str) -> str | None:
    if settings.agent_profile.lower() != "live":
        return None
    return f"openai:{model_version}"


def build_temporal_agents(settings: Settings) -> AgentBundle:
    retry_policy = RetryPolicy(maximum_attempts=3)
    base_activity_config: ActivityConfig = {
        "start_to_close_timeout": timedelta(seconds=max(settings.agent_model_timeout_seconds + 5, 60)),
        "retry_policy": retry_policy,
    }
    model_activity_config: ActivityConfig = {
        "start_to_close_timeout": timedelta(seconds=settings.agent_model_timeout_seconds + 5),
        "retry_policy": retry_policy,
    }

    strategy_model = FunctionModel(
        function=_strategy_function,
        model_name="cvm-deterministic:strategy-extractor",
    )
    resume_model = FunctionModel(
        function=_resume_match_function,
        model_name="cvm-deterministic:resume-matcher",
    )
    reflector_model = FunctionModel(
        function=_search_reflection_function,
        model_name="cvm-deterministic:search-reflector",
    )

    strategy_agent = TemporalAgent(
        Agent(
            strategy_model,
            output_type=StrategyExtractorOutputModel,
            name="strategy-extractor",
            retries=0,
            output_retries=0,
            instrument=False,
        ),
        name="strategy-extractor",
        provider_factory=lambda run_context, provider_name: _provider_factory(
            settings=settings,
            run_context=run_context,
            provider_name=provider_name,
        ),
        activity_config=base_activity_config,
        model_activity_config=model_activity_config,
    )
    resume_agent = TemporalAgent(
        Agent(
            resume_model,
            output_type=ResumeMatcherOutputModel,
            name="resume-matcher",
            retries=0,
            output_retries=0,
            instrument=False,
        ),
        name="resume-matcher",
        provider_factory=lambda run_context, provider_name: _provider_factory(
            settings=settings,
            run_context=run_context,
            provider_name=provider_name,
        ),
        activity_config=base_activity_config,
        model_activity_config=model_activity_config,
    )
    reflector_agent = TemporalAgent(
        Agent(
            reflector_model,
            output_type=SearchReflectorOutputModel,
            name="search-reflector",
            retries=0,
            output_retries=0,
            instrument=False,
        ),
        name="search-reflector",
        provider_factory=lambda run_context, provider_name: _provider_factory(
            settings=settings,
            run_context=run_context,
            provider_name=provider_name,
        ),
        activity_config=base_activity_config,
        model_activity_config=model_activity_config,
    )
    return AgentBundle(
        strategy_extractor=strategy_agent,
        resume_matcher=resume_agent,
        search_reflector=reflector_agent,
    )


def _provider_factory(
    *,
    settings: Settings,
    run_context: RunContext[None],
    provider_name: str,
) -> OpenAIProvider:
    del run_context
    if provider_name != "openai":
        raise UserError(f"Unsupported provider for CVM agent workflow: {provider_name}")
    if not settings.openai_api_key:
        raise UserError("OPENAI_API_KEY is required when CVM_AGENT_PROFILE=live.")
    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url or None,
        max_retries=0,
        timeout=settings.agent_model_timeout_seconds,
    )
    return OpenAIProvider(openai_client=client)


def _strategy_function(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    payload = _extract_input_payload(messages)
    jd_text = str(payload["jdText"])
    sourcing_preference_text = str(payload["sourcingPreferenceText"])
    output = _deterministic_strategy_output(jd_text, sourcing_preference_text)
    return _tool_output_response(info, output.model_dump(mode="json"))


def _resume_match_function(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    payload = _extract_input_payload(messages)
    strategy = NormalizedStrategyModel.model_validate(payload["strategy"])
    candidate = WorkerCandidateModel.model_validate(payload["candidate"])
    output = _heuristic_resume_match_output(
        candidate=candidate.to_domain(),
        strategy=strategy.to_payload(),
    )
    return _tool_output_response(info, output.model_dump(mode="json"))


def _search_reflection_function(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    payload = _extract_input_payload(messages)
    strategy = NormalizedStrategyModel.model_validate(payload["strategy"])
    round_no = int(payload["roundNo"])
    max_rounds = int(payload["maxRounds"])
    new_candidate_count = int(payload["newCandidateCount"])
    output = _deterministic_reflection_output(
        strategy=strategy.to_payload(),
        round_no=round_no,
        max_rounds=max_rounds,
        new_candidate_count=new_candidate_count,
    )
    return _tool_output_response(info, output.model_dump(mode="json"))


def _tool_output_response(info: AgentInfo, payload: dict[str, Any]) -> ModelResponse:
    if not info.output_tools:
        raise UserError("Temporal agent output tool schema was not registered.")
    return ModelResponse(
        parts=[
            ToolCallPart(
                info.output_tools[0].name,
                payload,
            )
        ]
    )


def _extract_input_payload(messages: list[ModelMessage]) -> dict[str, Any]:
    prompt_text = _latest_user_prompt_text(messages)
    marker_index = prompt_text.rfind(INPUT_JSON_MARKER)
    if marker_index < 0:
        raise UserError("Agent prompt missing INPUT_JSON payload marker.")
    raw_json = prompt_text[marker_index + len(INPUT_JSON_MARKER) :].strip()
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError as exc:  # pragma: no cover - prompt builders always emit valid JSON
        raise UserError("Agent prompt payload was not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise UserError("Agent prompt payload must be a JSON object.")
    return cast(dict[str, Any], payload)


def _latest_user_prompt_text(messages: list[ModelMessage]) -> str:
    for message in reversed(messages):
        parts = getattr(message, "parts", ())
        for part in reversed(parts):
            if getattr(part, "part_kind", None) == "user-prompt":
                return cast(str, cast(UserPromptPart, part).content)
    raise UserError("Agent run did not contain a user prompt.")


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
            " ".join(
                f"{item['school']} {item['degree']} {item['major']}" for item in projection["education"]
            ),
        ]
    ).lower()


def _heuristic_resume_match_output(
    *,
    candidate: CandidateData,
    strategy: NormalizedQueryPayload,
) -> ResumeMatcherOutputModel:
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
    if candidate.resume_projection["workYear"] is not None:
        score += min(candidate.resume_projection["workYear"], 10) / 200.0
    score = max(0.0, min(score, 0.99))
    reasons: list[str] = []
    if must_hits:
        reasons.append(f"命中必须项：{', '.join(must_hits[:3])}")
    if should_hits:
        reasons.append(f"命中核心项：{', '.join(should_hits[:3])}")
    if not reasons:
        reasons.append("与目标岗位存在较强相关性")
    return ResumeMatcherOutputModel(
        score=round(score, 4),
        summary="；".join(reasons),
        evidence=must_hits[:3] + should_hits[:2],
        concerns=[f"命中排除词：{term}" for term in exclude_hits[:2]],
    )


def _deterministic_strategy_output(
    jd_text: str,
    sourcing_preference_text: str,
) -> StrategyExtractorOutputModel:
    source_text = f"{jd_text}\n{sourcing_preference_text}"
    must_terms: list[str] = []
    should_terms: list[str] = []

    for term in HIGH_SIGNAL_TERMS:
        if term.lower() in source_text.lower():
            if term in {"Python", "Agent", "ReAct", "Voice Agent", "Context Engineering"}:
                must_terms.append(term)
            else:
                should_terms.append(term)

    if not must_terms:
        words = [token.strip(" ,.;:\n") for token in source_text.replace("/", " ").split()]
        for word in words:
            if len(word) >= 3 and word not in must_terms:
                must_terms.append(word)
            if len(must_terms) >= 3:
                break

    must_terms = must_terms[:4] or ["目标岗位"]
    should_terms = [term for term in should_terms if term not in must_terms][:6]
    filters = _draft_structured_filters(source_text)
    keyword = " ".join(must_terms + should_terms).strip() or must_terms[0]
    return StrategyExtractorOutputModel(
        mustRequirements=must_terms[:4],
        coreRequirements=should_terms[:4],
        bonusRequirements=should_terms[4:6],
        excludeSignals=[],
        round1Query=SearchQueryModel(
            keyword=keyword,
            mustTerms=must_terms,
            shouldTerms=should_terms,
            excludeTerms=[],
            structuredFilters=StructuredFiltersModel.model_validate(filters),
        ),
        summary=f"已提炼出 {len(must_terms)} 个必须项，并为首轮 CTS 生成宽召回查询。",
    )


def _draft_structured_filters(source_text: str) -> StructuredFiltersPayload:
    structured_filters: StructuredFiltersPayload = {"page": 1, "pageSize": 10}
    city = next((term for term in CITY_TERMS if term in source_text), None)
    if city:
        structured_filters["location"] = [city]
    if "硕士" in source_text:
        structured_filters["degree"] = 3
    elif "本科" in source_text:
        structured_filters["degree"] = 2

    if "C9" in source_text or "985" in source_text:
        structured_filters["schoolType"] = 3
    elif "211" in source_text:
        structured_filters["schoolType"] = 2
    elif "双一流" in source_text:
        structured_filters["schoolType"] = 1

    work_range_matchers = [
        (r"(10年以上|十年以上)", 6),
        (r"(5[-到~]10年|5年以上|5-8年|5年以?上)", 5),
        (r"(3[-到~]5年|3年以上)", 4),
        (r"(1[-到~]3年)", 3),
        (r"(1年以内)", 1),
    ]
    for pattern, code in work_range_matchers:
        if re.search(pattern, source_text):
            structured_filters["workExperienceRange"] = code
            break

    if "算法工程师" in source_text:
        structured_filters["position"] = "算法工程师"
    elif "工程师" in source_text:
        structured_filters["position"] = "工程师"

    work_content_terms = [
        term
        for term in ["Agent", "Voice Agent", "Context Engineering", "ReAct", "Reflexion", "LLM"]
        if term.lower() in source_text.lower()
    ]
    if work_content_terms:
        structured_filters["workContent"] = " ".join(work_content_terms)
    return structured_filters


def _deterministic_reflection_output(
    *,
    strategy: NormalizedQueryPayload,
    round_no: int,
    max_rounds: int,
    new_candidate_count: int,
) -> SearchReflectorOutputModel:
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
    return SearchReflectorOutputModel(
        continueSearch=continue_search,
        reason=reason,
        nextRoundGoal=next_round_goal,
        nextRoundQuery=SearchQueryModel(
            keyword=keyword,
            mustTerms=must_terms,
            shouldTerms=should_terms,
            excludeTerms=list(strategy["excludeTerms"]),
            structuredFilters=StructuredFiltersModel.model_validate(filters or {"page": 1, "pageSize": 10}),
        ),
    )
