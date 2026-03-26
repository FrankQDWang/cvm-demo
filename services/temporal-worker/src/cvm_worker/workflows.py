from __future__ import annotations

from temporalio import workflow

from pydantic_ai.durable_exec.temporal import PydanticAIWorkflow

with workflow.unsafe.imports_passed_through():
    from cvm_platform.settings.config import settings
    from cvm_worker.agents import build_temporal_agents
    from cvm_worker.execution import execute_agent_run_workflow


AGENT_BUNDLE = build_temporal_agents(settings)


@workflow.defn(name="AgentRunWorkflow")
class AgentRunWorkflow(PydanticAIWorkflow):
    __pydantic_ai_agents__ = AGENT_BUNDLE.all_agents

    @workflow.run
    async def run(self, run_id: str) -> str:
        return await execute_agent_run_workflow(
            run_id=run_id,
            agents=AGENT_BUNDLE,
            runtime_settings=settings,
        )
