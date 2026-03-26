from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from temporalio.client import Client
from temporalio.worker import Worker

from cvm_platform.infrastructure.db import initialize_database
from cvm_platform.settings.config import settings
from cvm_worker.workflows import AgentRunWorkflow, execute_agent_run


logger = logging.getLogger("cvm.worker.startup")


async def run_worker() -> None:
    initialize_database()
    logger.info(
        "Worker runtime ready build_id=%s temporal_namespace=%s temporal_visibility_backend=%s temporal_task_queue=%s",
        settings.build_id,
        settings.temporal_namespace,
        settings.temporal_visibility_backend,
        settings.temporal_task_queue,
    )
    client = await Client.connect(settings.temporal_host, namespace=settings.temporal_namespace)
    activity_executor = ThreadPoolExecutor(max_workers=4)
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[AgentRunWorkflow],
        activities=[execute_agent_run],
        activity_executor=activity_executor,
    )
    await worker.run()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
