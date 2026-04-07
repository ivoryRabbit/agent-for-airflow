# Tools

Python functions in `app/airflow/tools/` that the agent calls to interact with Airflow.
Each tool maps to one or more Airflow REST API v2 endpoints.

---

## Read-only Tools (agent can call autonomously)

### `list_dags`
List DAGs registered in Airflow.

**Parameters**
| Name | Type | Required | Description |
|---|---|---|---|
| `only_active` | boolean | no | If true, return only unpaused DAGs (default: true) |

**Returns**
```json
[
  {
    "dag_id": "example_pipeline",
    "is_paused": false,
    "schedule_interval": "0 2 * * *",
    "tags": ["example", "agent-test"]
  }
]
```

---

### `get_dag_run_status`
Get the status of a specific DAG run.

**Parameters**
| Name | Type | Required | Description |
|---|---|---|---|
| `dag_id` | string | yes | DAG identifier |
| `dag_run_id` | string | yes | DAG run identifier (e.g. `scheduled__2024-01-01T00:00:00+00:00`) |

**Returns**
```json
{
  "dag_id": "example_dag",
  "dag_run_id": "scheduled__2024-01-01T00:00:00+00:00",
  "state": "failed",
  "start_date": "2024-01-01T00:00:00+00:00",
  "end_date": "2024-01-01T00:05:00+00:00"
}
```

---

### `get_failed_tasks`
Get the list of failed tasks within a DAG run.

**Parameters**
| Name | Type | Required | Description |
|---|---|---|---|
| `dag_id` | string | yes | DAG identifier |
| `dag_run_id` | string | yes | DAG run identifier |

**Returns**
```json
[
  {
    "task_id": "load_data",
    "state": "failed",
    "start_date": "2024-01-01T00:01:00+00:00",
    "end_date": "2024-01-01T00:02:30+00:00",
    "try_number": 1
  }
]
```

---

### `get_task_logs`
Fetch execution logs for a specific task instance.

**Parameters**
| Name | Type | Required | Description |
|---|---|---|---|
| `dag_id` | string | yes | DAG identifier |
| `dag_run_id` | string | yes | DAG run identifier |
| `task_id` | string | yes | Task identifier |
| `try_number` | integer | no | Attempt number (default: 1) |

**Returns**
```json
{
  "dag_id": "example_dag",
  "task_id": "load_data",
  "try_number": 1,
  "logs": "...[raw log text]..."
}
```

---

### `get_dag_runs`
Get recent DAG runs for a given DAG. Used for the daily report.

**Parameters**
| Name | Type | Required | Description |
|---|---|---|---|
| `dag_id` | string | yes | DAG identifier |
| `limit` | integer | no | Number of runs to return (default: 10) |
| `start_date_gte` | string | no | ISO 8601 datetime filter |

**Returns**
```json
[
  {
    "dag_run_id": "scheduled__2024-01-01T00:00:00+00:00",
    "state": "success",
    "start_date": "2024-01-01T00:00:00+00:00",
    "end_date": "2024-01-01T00:04:00+00:00"
  }
]
```

---

## Write Tools (require explicit DE instruction)

### `trigger_dag`
Manually trigger a new DAG run.

**Parameters**
| Name | Type | Required | Description |
|---|---|---|---|
| `dag_id` | string | yes | DAG identifier |
| `conf` | object | no | Runtime configuration passed to the DAG |

**Returns**
```json
{
  "dag_run_id": "manual__2024-01-01T00:10:00+00:00",
  "state": "queued"
}
```

---

### `clear_task`
Clear a task instance to re-run it within the existing DAG run.

**Parameters**
| Name | Type | Required | Description |
|---|---|---|---|
| `dag_id` | string | yes | DAG identifier |
| `dag_run_id` | string | yes | DAG run identifier |
| `task_id` | string | yes | Task identifier |
| `include_downstream` | boolean | no | Also clear downstream tasks (default: false) |

**Returns**
```json
{
  "cleared_tasks": ["load_data", "validate_data"]
}
```

---

### `mark_task_state`
Force-set a task instance to a specific state.

**Parameters**
| Name | Type | Required | Description |
|---|---|---|---|
| `dag_id` | string | yes | DAG identifier |
| `dag_run_id` | string | yes | DAG run identifier |
| `task_id` | string | yes | Task identifier |
| `state` | string | yes | Target state: `success` or `failed` |

**Returns**
```json
{
  "dag_id": "example_dag",
  "task_id": "wait_for_sensor",
  "state": "success"
}
```

**Notes**
- Marking a task as `success` allows downstream tasks to proceed automatically.
- Most common use case: sensor timeout where DE confirms the condition is already met.
- The agent should inform DE which downstream tasks will be affected and ask whether to also clear them:
  > "Mark `wait_for_sensor` as success? Downstream tasks (`load_data`, `validate_data`) will run automatically. Should I also clear them explicitly for a fresh run?"

---

### `set_dag_paused`
Pause or unpause a DAG to prevent or allow scheduled runs.

**Parameters**
| Name | Type | Required | Description |
|---|---|---|---|
| `dag_id` | string | yes | DAG identifier |
| `is_paused` | boolean | yes | `true` to pause, `false` to unpause |

**Returns**
```json
{
  "dag_id": "example_dag",
  "is_paused": true
}
```

---

## Tool Permission Summary

| Tool | Permission | Trigger |
|---|---|---|
| `list_dags` | autonomous | @mention general question |
| `get_dag_run_status` | autonomous | on Slack alert / @mention |
| `get_failed_tasks` | autonomous | on Slack alert / @mention |
| `get_task_logs` | autonomous | on Slack alert received |
| `get_dag_runs` | autonomous | on daily report schedule / @mention |
| `trigger_dag` | DE instruction required | DE reply in Slack thread |
| `clear_task` | DE instruction required | DE reply in Slack thread |
| `mark_task_state` | DE instruction required | DE reply in Slack thread |
| `set_dag_paused` | DE instruction required | DE reply in Slack thread |
