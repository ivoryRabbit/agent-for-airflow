from typing import Any

import httpx

from app.config import settings

BASE = "/api/v1"


class AirflowClient:
    def __init__(self) -> None:
        self._http = httpx.AsyncClient(
            base_url=settings.airflow_base_url,
            auth=(settings.airflow_username, settings.airflow_password),
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._http.aclose()

    # ------------------------------------------------------------------ #
    # Read                                                                 #
    # ------------------------------------------------------------------ #

    async def get_dag_run_status(self, dag_id: str, dag_run_id: str) -> dict[str, Any]:
        r = await self._http.get(f"{BASE}/dags/{dag_id}/dagRuns/{dag_run_id}")
        r.raise_for_status()
        data = r.json()
        return {
            "dag_id": data["dag_id"],
            "dag_run_id": data["dag_run_id"],
            "state": data["state"],
            "start_date": data.get("start_date"),
            "end_date": data.get("end_date"),
        }

    async def get_failed_tasks(self, dag_id: str, dag_run_id: str) -> list[dict[str, Any]]:
        r = await self._http.get(
            f"{BASE}/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances",
            params={"state": "failed"},
        )
        r.raise_for_status()
        instances = r.json().get("task_instances", [])
        return [
            {
                "task_id": t["task_id"],
                "state": t["state"],
                "start_date": t.get("start_date"),
                "end_date": t.get("end_date"),
                "try_number": t.get("try_number", 1),
            }
            for t in instances
        ]

    async def list_dags(self, only_active: bool = True) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"only_active": str(only_active).lower()}
        r = await self._http.get(f"{BASE}/dags", params=params)
        r.raise_for_status()
        return [
            {
                "dag_id": d["dag_id"],
                "is_paused": d["is_paused"],
                "schedule_interval": d.get("schedule_interval"),
                "tags": [t["name"] for t in d.get("tags", [])],
            }
            for d in r.json().get("dags", [])
        ]

    async def get_task_logs(
        self,
        dag_id: str,
        dag_run_id: str,
        task_id: str,
        try_number: int = 1,
    ) -> dict[str, Any]:
        r = await self._http.get(
            f"{BASE}/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances/{task_id}/logs/{try_number}",
            headers={"Accept": "text/plain"},
        )
        r.raise_for_status()
        return {
            "dag_id": dag_id,
            "task_id": task_id,
            "try_number": try_number,
            "logs": r.text,
        }

    async def get_dag_runs(
        self,
        dag_id: str,
        limit: int = 10,
        start_date_gte: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit, "order_by": "-execution_date"}
        if start_date_gte:
            params["start_date_gte"] = start_date_gte
        r = await self._http.get(f"{BASE}/dags/{dag_id}/dagRuns", params=params)
        r.raise_for_status()
        runs = r.json().get("dag_runs", [])
        return [
            {
                "dag_run_id": run["dag_run_id"],
                "state": run["state"],
                "start_date": run.get("start_date"),
                "end_date": run.get("end_date"),
            }
            for run in runs
        ]

    # ------------------------------------------------------------------ #
    # Write                                                                #
    # ------------------------------------------------------------------ #

    async def trigger_dag(
        self,
        dag_id: str,
        conf: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        r = await self._http.post(
            f"{BASE}/dags/{dag_id}/dagRuns",
            json={"conf": conf or {}},
        )
        r.raise_for_status()
        data = r.json()
        return {"dag_run_id": data["dag_run_id"], "state": data["state"]}

    async def clear_task(
        self,
        dag_id: str,
        dag_run_id: str,
        task_id: str,
        include_downstream: bool = False,
    ) -> dict[str, Any]:
        r = await self._http.post(
            f"{BASE}/dags/{dag_id}/clearTaskInstances",
            json={
                "dry_run": False,
                "task_ids": [task_id],
                "dag_run_id": dag_run_id,
                "include_downstream": include_downstream,
            },
        )
        r.raise_for_status()
        cleared = [t["task_id"] for t in r.json().get("task_instances", [])]
        return {"cleared_tasks": cleared}

    async def mark_task_state(
        self,
        dag_id: str,
        dag_run_id: str,
        task_id: str,
        state: str,
    ) -> dict[str, Any]:
        r = await self._http.patch(
            f"{BASE}/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances/{task_id}",
            json={"state": state},
        )
        r.raise_for_status()
        return {"dag_id": dag_id, "task_id": task_id, "state": state}

    async def set_dag_paused(self, dag_id: str, is_paused: bool) -> dict[str, Any]:
        r = await self._http.patch(
            f"{BASE}/dags/{dag_id}",
            json={"is_paused": is_paused},
        )
        r.raise_for_status()
        return {"dag_id": dag_id, "is_paused": is_paused}


_client: AirflowClient | None = None


def get_client() -> AirflowClient:
    global _client
    if _client is None:
        _client = AirflowClient()
    return _client
