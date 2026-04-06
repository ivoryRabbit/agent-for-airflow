from typing import Any

from ..airflow_client import get_client


async def get_dag_run_status(dag_id: str, dag_run_id: str) -> dict[str, Any]:
    """Get the status of a specific DAG run."""
    return await get_client().get_dag_run_status(dag_id, dag_run_id)


async def get_failed_tasks(dag_id: str, dag_run_id: str) -> list[dict[str, Any]]:
    """Get the list of failed tasks within a DAG run."""
    return await get_client().get_failed_tasks(dag_id, dag_run_id)


async def get_task_logs(
    dag_id: str,
    dag_run_id: str,
    task_id: str,
    try_number: int = 1,
) -> dict[str, Any]:
    """Fetch execution logs for a specific task instance.

    try_number defaults to 1 (the latest attempt when the task has only been tried once).
    """
    return await get_client().get_task_logs(dag_id, dag_run_id, task_id, try_number)


async def list_dags(only_active: bool = True) -> list[dict[str, Any]]:
    """List DAGs registered in Airflow.

    only_active: if True (default), returns only unpaused DAGs.
    """
    return await get_client().list_dags(only_active)


async def get_dag_runs(
    dag_id: str,
    limit: int = 10,
    start_date_gte: str | None = None,
) -> list[dict[str, Any]]:
    """Get recent DAG runs for a given DAG.

    start_date_gte: ISO 8601 datetime string to filter runs (e.g. '2024-01-01T00:00:00+00:00').
    Used primarily for the daily operations report.
    """
    return await get_client().get_dag_runs(dag_id, limit, start_date_gte)
