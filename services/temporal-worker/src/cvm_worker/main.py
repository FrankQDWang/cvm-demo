from __future__ import annotations

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from cvm_platform.infrastructure.db import Base, engine
from cvm_platform.settings.config import settings
from cvm_worker.workflows import SearchRunWorkflow, execute_search_run


async def run_worker() -> None:
    Base.metadata.create_all(bind=engine)
    client = await Client.connect(settings.temporal_host)
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[SearchRunWorkflow],
        activities=[execute_search_run],
    )
    await worker.run()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
