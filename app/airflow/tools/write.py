from typing import Any

from app.airflow.client import get_client


async def trigger_dag(
    dag_id: str,
    conf: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Manually trigger a new DAG run.

    conf: optional runtime configuration passed to the DAG.
    """
    return await get_client().trigger_dag(dag_id, conf)


async def clear_task(
    dag_id: str,
    dag_run_id: str,
    task_id: str,
    include_downstream: bool = False,
) -> dict[str, Any]:
    """Clear a task instance to re-run it within the existing DAG run.

    include_downstream: if True, also clears all tasks that depend on this task.
    The agent should ask the DE whether to include downstream before calling this.
    """
    return await get_client().clear_task(dag_id, dag_run_id, task_id, include_downstream)


async def mark_task_state(
    dag_id: str,
    dag_run_id: str,
    task_id: str,
    state: str,
) -> dict[str, Any]:
    """Force-set a task instance to a specific state.

    state: 'success' or 'failed'.

    Marking a task as 'success' allows downstream tasks to proceed automatically.
    Most common use case: sensor timeout where the DE confirms the condition is already met.

    Before calling this, the agent should inform the DE which downstream tasks will
    be affected and ask whether to also clear them for a fresh run.
    """
    if state not in ("success", "failed"):
        raise ValueError(f"Invalid state '{state}'. Must be 'success' or 'failed'.")
    return await get_client().mark_task_state(dag_id, dag_run_id, task_id, state)


async def set_dag_paused(dag_id: str, is_paused: bool) -> dict[str, Any]:
    """Pause or unpause a DAG to prevent or allow scheduled runs.

    is_paused: True to pause, False to unpause.
    """
    return await get_client().set_dag_paused(dag_id, is_paused)
