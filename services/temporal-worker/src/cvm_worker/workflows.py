from __future__ import annotations

from temporalio import activity, workflow

with workflow.unsafe.imports_passed_through():
    from cvm_platform.application.service import PlatformService
    from cvm_platform.infrastructure.adapters import MockResumeSourceAdapter, StubLLMAdapter
    from cvm_platform.infrastructure.db import SessionLocal


@activity.defn
def execute_search_run(run_id: str) -> str:
    session = SessionLocal()
    try:
        service = PlatformService(session=session, llm=StubLLMAdapter(), resume_source=MockResumeSourceAdapter())
        run = service.execute_search_run(run_id)
        return run.status
    finally:
        session.close()


@workflow.defn(name="SearchRunWorkflow")
class SearchRunWorkflow:
    @workflow.run
    async def run(self, run_id: str) -> str:
        return await workflow.execute_activity(execute_search_run, run_id, start_to_close_timeout=60)
