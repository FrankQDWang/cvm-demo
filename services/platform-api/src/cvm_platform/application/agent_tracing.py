from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from typing import Literal, Protocol

from cvm_platform.domain.types import AgentRuntimeConfigPayload, JsonValue


TraceObservationType = Literal["agent", "chain", "tool", "span", "generation"]
TraceObservationLevel = Literal["DEBUG", "DEFAULT", "WARNING", "ERROR"]


@dataclass(frozen=True, slots=True)
class TracePromptReference:
    name: str
    label: str | None
    prompt_text: str
    prompt_type: Literal["text", "chat"] = "text"


class AgentTraceObservation(Protocol):
    def start_observation(
        self,
        *,
        name: str,
        as_type: TraceObservationType,
        input: JsonValue | None = None,
        metadata: JsonValue | None = None,
        model: str | None = None,
        version: str | None = None,
        prompt: TracePromptReference | None = None,
        usage_details: dict[str, int] | None = None,
        cost_details: dict[str, float] | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> AbstractContextManager["AgentTraceObservation"]: ...

    def update(
        self,
        *,
        input: JsonValue | None = None,
        output: JsonValue | None = None,
        metadata: JsonValue | None = None,
        model: str | None = None,
        version: str | None = None,
        prompt: TracePromptReference | None = None,
        usage_details: dict[str, int] | None = None,
        cost_details: dict[str, float] | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> None: ...


class AgentRunTraceHandle(Protocol):
    trace_id: str | None
    trace_url: str | None

    def start_observation(
        self,
        *,
        name: str,
        as_type: TraceObservationType,
        input: JsonValue | None = None,
        metadata: JsonValue | None = None,
        model: str | None = None,
        version: str | None = None,
        prompt: TracePromptReference | None = None,
        usage_details: dict[str, int] | None = None,
        cost_details: dict[str, float] | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> AbstractContextManager[AgentTraceObservation]: ...

    def update_root(
        self,
        *,
        output: JsonValue | None = None,
        metadata: JsonValue | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> None: ...


class AgentRunTracer(Protocol):
    def trace_run(
        self,
        *,
        run_id: str,
        jd_text: str,
        sourcing_preference_text: str,
        model_version: str,
        prompt_version: str,
        agent_runtime_config: AgentRuntimeConfigPayload,
    ) -> AbstractContextManager[AgentRunTraceHandle]: ...


class NoOpAgentTraceObservation:
    @contextmanager
    def start_observation(
        self,
        *,
        name: str,
        as_type: TraceObservationType,
        input: JsonValue | None = None,
        metadata: JsonValue | None = None,
        model: str | None = None,
        version: str | None = None,
        prompt: TracePromptReference | None = None,
        usage_details: dict[str, int] | None = None,
        cost_details: dict[str, float] | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> Iterator[AgentTraceObservation]:
        del (
            name,
            as_type,
            input,
            metadata,
            model,
            version,
            prompt,
            usage_details,
            cost_details,
            level,
            status_message,
        )
        yield NoOpAgentTraceObservation()

    def update(
        self,
        *,
        input: JsonValue | None = None,
        output: JsonValue | None = None,
        metadata: JsonValue | None = None,
        model: str | None = None,
        version: str | None = None,
        prompt: TracePromptReference | None = None,
        usage_details: dict[str, int] | None = None,
        cost_details: dict[str, float] | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> None:
        del input, output, metadata, model, version, prompt, usage_details, cost_details, level, status_message


class NoOpAgentRunTraceHandle:
    trace_id: str | None = None
    trace_url: str | None = None

    @contextmanager
    def start_observation(
        self,
        *,
        name: str,
        as_type: TraceObservationType,
        input: JsonValue | None = None,
        metadata: JsonValue | None = None,
        model: str | None = None,
        version: str | None = None,
        prompt: TracePromptReference | None = None,
        usage_details: dict[str, int] | None = None,
        cost_details: dict[str, float] | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> Iterator[AgentTraceObservation]:
        del (
            name,
            as_type,
            input,
            metadata,
            model,
            version,
            prompt,
            usage_details,
            cost_details,
            level,
            status_message,
        )
        yield NoOpAgentTraceObservation()

    def update_root(
        self,
        *,
        output: JsonValue | None = None,
        metadata: JsonValue | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> None:
        del output, metadata, level, status_message


class NoOpAgentRunTracer:
    @contextmanager
    def trace_run(
        self,
        *,
        run_id: str,
        jd_text: str,
        sourcing_preference_text: str,
        model_version: str,
        prompt_version: str,
        agent_runtime_config: AgentRuntimeConfigPayload,
    ) -> Iterator[AgentRunTraceHandle]:
        del run_id, jd_text, sourcing_preference_text, model_version, prompt_version, agent_runtime_config
        yield NoOpAgentRunTraceHandle()
