from __future__ import annotations

from datetime import UTC
from typing import Any
from urllib.parse import quote

from temporalio.api.enums.v1 import WorkflowExecutionStatus
from temporalio.client import Client
from temporalio.service import RPCError

from cvm_platform.application.dto import SearchRunRecord
from cvm_platform.settings.config import Settings


def _format_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    seconds = getattr(value, "seconds", 0)
    nanos = getattr(value, "nanos", 0)
    if seconds == 0 and nanos == 0:
        return None
    return value.ToDatetime(tzinfo=UTC).isoformat()


def _append_error(existing: str | None, message: str) -> str:
    if not existing:
        return message
    return f"{existing}; {message}"


def build_temporal_ui_url(settings: Settings, namespace: str, workflow_id: str) -> str:
    query = quote(f"WorkflowId = '{workflow_id}'", safe="")
    return f"{settings.temporal_ui_base_url.rstrip('/')}/namespaces/{namespace}/workflows?query={query}"


async def inspect_search_run(run: SearchRunRecord, settings: Settings) -> dict[str, Any]:
    workflow_id = run.workflow_id or f"search-run-{run.id}"
    namespace = run.temporal_namespace or settings.temporal_namespace
    task_queue = run.temporal_task_queue or settings.temporal_task_queue

    diagnostic: dict[str, Any] = {
        "runId": run.id,
        "workflowId": workflow_id,
        "namespace": namespace,
        "taskQueue": task_queue,
        "appStatus": run.status,
        "temporalExecutionFound": False,
        "temporalExecutionStatus": None,
        "visibilityIndexed": False,
        "visibilityBackend": settings.temporal_visibility_backend,
        "startedAt": run.started_at.isoformat() if run.started_at else None,
        "closedAt": run.finished_at.isoformat() if run.finished_at else None,
        "error": None,
        "temporalUiUrl": build_temporal_ui_url(settings, namespace, workflow_id),
    }

    client = await Client.connect(settings.temporal_host, namespace=namespace)

    try:
        description = await client.get_workflow_handle(workflow_id).describe()
        info = description.raw_description.workflow_execution_info
        diagnostic["temporalExecutionFound"] = True
        diagnostic["temporalExecutionStatus"] = WorkflowExecutionStatus.Name(int(info.status))
        diagnostic["startedAt"] = _format_timestamp(info.start_time) or diagnostic["startedAt"]
        diagnostic["closedAt"] = _format_timestamp(info.close_time) or diagnostic["closedAt"]
    except RPCError as exc:
        diagnostic["error"] = _append_error(diagnostic["error"], f"execution lookup failed: {exc.message}")
    except Exception as exc:  # pragma: no cover - defensive guard for local diagnostics
        diagnostic["error"] = _append_error(diagnostic["error"], f"execution lookup failed: {exc}")

    try:
        workflow_count = await client.count_workflows(f"WorkflowId = '{workflow_id}'")
        diagnostic["visibilityIndexed"] = workflow_count.count > 0
    except Exception as exc:  # pragma: no cover - depends on visibility backend readiness
        diagnostic["error"] = _append_error(diagnostic["error"], f"visibility query failed: {exc}")

    return diagnostic
