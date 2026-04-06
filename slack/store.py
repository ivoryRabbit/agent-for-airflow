"""In-memory store for alert thread context.

Maps Slack thread_ts → { dag_id, dag_run_id, failed_tasks }.
For production, replace with Redis or a database.
"""

from typing import Any


class ThreadStore:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    def save(
        self,
        thread_ts: str,
        dag_id: str,
        dag_run_id: str,
        failed_tasks: list[dict[str, Any]],
    ) -> None:
        self._data[thread_ts] = {
            "dag_id": dag_id,
            "dag_run_id": dag_run_id,
            "failed_tasks": failed_tasks,
        }

    def get(self, thread_ts: str) -> dict[str, Any] | None:
        return self._data.get(thread_ts)


thread_store = ThreadStore()
