from __future__ import annotations

from cvm_platform.application.agent_tracing import NoOpAgentRunTracer


def test_noop_agent_run_tracer_supports_nested_updates() -> None:
    tracer = NoOpAgentRunTracer()

    with tracer.trace_run(
        run_id="agent_1",
        jd_text="Need Python",
        sourcing_preference_text="Prefer evals",
        model_version="gpt-5.4-mini",
        prompt_version="agent-loop-v1",
    ) as handle:
        assert handle.trace_id is None
        assert handle.trace_url is None
        with handle.start_observation(
            name="strategy",
            as_type="generation",
            input={"jdText": "Need Python"},
            metadata={"round": 1},
            model="gpt-5.4-mini",
            version="agent-loop-v1",
        ) as observation:
            observation.update(
                input={"jdText": "Need Python"},
                output={"keyword": "Python agent"},
                metadata={"phase": "extract"},
                model="gpt-5.4-mini",
                version="agent-loop-v1",
                level="DEFAULT",
                status_message="ok",
            )
            with observation.start_observation(
                name="round-1",
                as_type="chain",
                input={"roundNo": 1},
                metadata={"phase": "round"},
                level="DEFAULT",
            ) as round_observation:
                round_observation.update(output={"status": "running"})
        handle.update_root(
            output={"status": "completed"},
            metadata={"seenResumeCount": 5},
            level="DEFAULT",
            status_message="done",
        )
