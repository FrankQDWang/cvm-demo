from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from pydantic_ai.durable_exec.temporal import PydanticAIPlugin
from temporalio.client import Client
from temporalio.worker import Worker

from cvm_platform.infrastructure.db import initialize_database
from cvm_platform.settings.config import settings
from cvm_worker.activities import (
    cts_search_candidates,
    load_agent_run_snapshot,
    persist_agent_run_patch,
    persist_candidate_snapshots,
    persist_resume_analyses,
    publish_langfuse_trace,
)
from cvm_worker.workflows import AgentRunWorkflow


logger = logging.getLogger("cvm.worker.startup")


async def run_worker() -> None:
    initialize_database()
    settings.assert_runtime_mode_allowed()
    logger.info(
        "Worker runtime ready build_id=%s temporal_namespace=%s temporal_visibility_backend=%s temporal_task_queue=%s agent_profile=%s agent_model=%s agent_min_rounds=%s agent_max_rounds=%s",
        settings.build_id,
        settings.temporal_namespace,
        settings.temporal_visibility_backend,
        settings.temporal_task_queue,
        settings.agent_profile,
        settings.agent_model,
        settings.agent_min_rounds,
        settings.agent_max_rounds,
    )
    plugin = PydanticAIPlugin()
    client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
        plugins=[plugin],
    )
    activity_executor = ThreadPoolExecutor(max_workers=8)
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[AgentRunWorkflow],
        activities=[
            load_agent_run_snapshot,
            persist_agent_run_patch,
            cts_search_candidates,
            persist_candidate_snapshots,
            persist_resume_analyses,
            publish_langfuse_trace,
        ],
        activity_executor=activity_executor,
    )
    await worker.run()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
