from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Protocol, cast
from urllib.parse import urlsplit, urlunsplit

import httpx

from cvm_platform.application.agent_tracing import (
    AgentRunTraceHandle,
    AgentRunTracer,
    AgentTraceObservation,
    NoOpAgentRunTracer,
    TraceObservationType,
)
from cvm_platform.domain.types import AgentRuntimeConfigPayload, JsonValue
from cvm_platform.settings.config import Settings

try:
    from langfuse.api import Error as LangfuseApiError
    from langfuse import Langfuse
except ImportError:  # pragma: no cover - exercised only when dependency is missing
    LangfuseApiError = RuntimeError  # type: ignore[assignment]
    Langfuse = None  # type: ignore[assignment]


class _SupportsObservation(Protocol):
    def start_as_current_observation(self, **kwargs: object) -> "_SupportsObservationContext": ...
    def update(self, **kwargs: object) -> None: ...


class _SupportsObservationContext(Protocol):
    def __enter__(self) -> _SupportsObservation: ...
    def __exit__(self, exc_type: object, exc: object, exc_tb: object) -> bool | None: ...


class _SupportsLangfuseClient(Protocol):
    def start_as_current_observation(self, **kwargs: object) -> _SupportsObservationContext: ...
    def flush(self) -> None: ...
    def get_trace_url(self, *, trace_id: str) -> str: ...
    def create_trace_id(self, *, seed: str) -> str: ...


class _LangfuseObservationAdapter:
    def __init__(self, observation: _SupportsObservation) -> None:
        self._observation = observation

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
        level: str | None = None,
        status_message: str | None = None,
    ) -> Iterator[AgentTraceObservation]:
        observation_kwargs: dict[str, object] = {
            "name": name,
            "as_type": as_type,
        }
        if input is not None:
            observation_kwargs["input"] = input
        if metadata is not None:
            observation_kwargs["metadata"] = metadata
        if model is not None:
            observation_kwargs["model"] = model
        if version is not None:
            observation_kwargs["version"] = version
        if level is not None:
            observation_kwargs["level"] = level
        if status_message is not None:
            observation_kwargs["status_message"] = status_message
        with self._observation.start_as_current_observation(**observation_kwargs) as observation:
            yield _LangfuseObservationAdapter(observation)

    def update(
        self,
        *,
        input: JsonValue | None = None,
        output: JsonValue | None = None,
        metadata: JsonValue | None = None,
        model: str | None = None,
        version: str | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> None:
        update_kwargs: dict[str, object] = {}
        if input is not None:
            update_kwargs["input"] = input
        if output is not None:
            update_kwargs["output"] = output
        if metadata is not None:
            update_kwargs["metadata"] = metadata
        if model is not None:
            update_kwargs["model"] = model
        if version is not None:
            update_kwargs["version"] = version
        if level is not None:
            update_kwargs["level"] = level
        if status_message is not None:
            update_kwargs["status_message"] = status_message
        self._observation.update(**update_kwargs)


class _LangfuseAgentRunTraceHandle:
    def __init__(
        self,
        root_observation: _LangfuseObservationAdapter,
        trace_id: str | None,
        trace_url: str | None,
    ) -> None:
        self._root_observation = root_observation
        self.trace_id = trace_id
        self.trace_url = trace_url

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
        level: str | None = None,
        status_message: str | None = None,
    ) -> Iterator[AgentTraceObservation]:
        with self._root_observation.start_observation(
            name=name,
            as_type=as_type,
            input=input,
            metadata=metadata,
            model=model,
            version=version,
            level=level,
            status_message=status_message,
        ) as observation:
            yield observation

    def update_root(
        self,
        *,
        output: JsonValue | None = None,
        metadata: JsonValue | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> None:
        self._root_observation.update(
            output=output,
            metadata=metadata,
            level=level,
            status_message=status_message,
        )


class LangfuseAgentRunTracer:
    def __init__(self, client: _SupportsLangfuseClient, *, display_base_url: str | None = None) -> None:
        self._client = client
        self._display_base_url = (display_base_url or "").rstrip("/")

    def _flush_quietly(self) -> None:
        try:
            self._client.flush()
        except (RuntimeError, TypeError, ValueError):
            # Observability must never fail the business workflow.
            return

    def _build_trace_url(self, trace_id: str) -> str | None:
        try:
            internal_trace_url = self._client.get_trace_url(trace_id=trace_id)
        except (LangfuseApiError, httpx.HTTPError, RuntimeError, TypeError, ValueError):
            return None
        if not self._display_base_url:
            return internal_trace_url

        parsed_internal = urlsplit(internal_trace_url)
        parsed_display = urlsplit(self._display_base_url)
        base_path = parsed_display.path.rstrip("/")
        internal_path = parsed_internal.path or ""
        merged_path = f"{base_path}{internal_path}" if base_path else internal_path
        return urlunsplit(
            (
                parsed_display.scheme or parsed_internal.scheme,
                parsed_display.netloc or parsed_internal.netloc,
                merged_path,
                parsed_internal.query,
                parsed_internal.fragment,
            )
        )

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
        trace_id = self._client.create_trace_id(seed=run_id)
        root_input: JsonValue = {
            "runId": run_id,
            "jdText": jd_text,
            "sourcingPreferenceText": sourcing_preference_text,
        }
        root_metadata: JsonValue = {
            "modelVersion": model_version,
            "promptVersion": prompt_version,
            "agentRuntimeConfig": agent_runtime_config,
        }
        with self._client.start_as_current_observation(
            name="agent-run",
            input=root_input,
            metadata=root_metadata,
            trace_context={"trace_id": trace_id},
            version=prompt_version,
            as_type="agent",
        ) as root_observation:
            trace_url = self._build_trace_url(trace_id)
            try:
                yield _LangfuseAgentRunTraceHandle(
                    _LangfuseObservationAdapter(root_observation),
                    trace_id,
                    trace_url,
                )
            finally:
                self._flush_quietly()


def build_agent_run_tracer(settings: Settings) -> AgentRunTracer:
    if Langfuse is None:
        return NoOpAgentRunTracer()
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return NoOpAgentRunTracer()
    client = cast(
        _SupportsLangfuseClient,
        cast(
            object,
            Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
                environment=settings.langfuse_environment,
            ),
        ),
    )
    return LangfuseAgentRunTracer(client, display_base_url=settings.langfuse_base_url or None)
