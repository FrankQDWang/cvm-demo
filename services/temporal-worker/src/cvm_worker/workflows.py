from __future__ import annotations

from datetime import timedelta

from temporalio import activity, workflow

with workflow.unsafe.imports_passed_through():
    from cvm_platform.infrastructure.db import SessionLocal
    from cvm_platform.infrastructure.service_factory import build_platform_service
    from cvm_platform.settings.config import settings


@activity.defn
def execute_agent_run(run_id: str) -> str:
    session = SessionLocal()
    try:
        service = build_platform_service(session, settings)
        run = service.execute_agent_run(run_id)
        return run.status
    finally:
        session.close()

@workflow.defn(name="AgentRunWorkflow")
class AgentRunWorkflow:
    @workflow.run
    async def run(self, run_id: str) -> str:
        return await workflow.execute_activity(
            execute_agent_run,
            run_id,
            start_to_close_timeout=timedelta(seconds=180),
        )
