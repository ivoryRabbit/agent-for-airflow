"""
Example pipeline DAG for testing the Airflow AI agent.

Pipeline: wait_for_source → extract_data → transform_data → load_data → notify

Failure scenarios (controlled via Airflow Variable or dag_run conf):
    sensor   — wait_for_source times out            (default)
    extract  — extract_data raises a connection error
    load     — load_data raises a schema mismatch error
    none     — all tasks succeed

How to set the failure mode:
    Option A) Airflow Variable:
        airflow variables set example_pipeline_fail_at extract

    Option B) Trigger with conf:
        airflow dags trigger example_pipeline --conf '{"fail_at": "load"}'
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from airflow.sensors.python import PythonSensor

DAG_ID = "example_pipeline"


def _slack_failure_callback(context) -> None:
    from airflow.providers.slack.hooks.slack_webhook import SlackWebhookHook

    dag = context["dag"]
    ti = context["task_instance"]
    exception = context.get("exception")

    duration = (
        round((ti.end_date - ti.start_date).total_seconds())
        if ti.start_date and ti.end_date
        else "unknown"
    )
    error_msg = str(exception).splitlines()[0] if exception else "unknown"

    text = (
        f":red_circle: DAG *{dag.dag_id}* failed\n"
        f"• Run ID: `{context['run_id']}`\n"
        f"• Failed task: `{ti.task_id}` (attempt {ti.try_number})\n"
        f"• Execution date: `{context['data_interval_start']}`\n"
        f"• Schedule: `{dag.schedule_interval}`\n"
        f"• Owner: `{dag.owner}`\n"
        f"• Duration: {duration}s\n"
        f"• Error: {error_msg}\n"
        f"• Log: {ti.log_url}"
    )
    hook = SlackWebhookHook(slack_webhook_conn_id="slack_default")
    hook.send(text=text)


default_args = {
    "owner": "data-engineering",
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
    "email_on_failure": False,
    "on_failure_callback": _slack_failure_callback,
}


def _fail_at(**context) -> str:
    return context["dag_run"].conf.get(
        "fail_at",
        Variable.get("example_pipeline_fail_at", default_var="sensor"),
    )


# ── Tasks ──────────────────────────────────────────────────────────────────────

def _check_source_ready(**context) -> bool:
    """Sensor poke: returns True when source data is available.

    When fail_at=sensor this always returns False, causing the sensor to time out.
    """
    if _fail_at(**context) == "sensor":
        return False
    return True


def _extract_data(**context) -> None:
    if _fail_at(**context) == "extract":
        raise RuntimeError(
            "Connection to source DB refused: [Errno 111] Connection refused to 10.0.1.42:5432"
        )
    time.sleep(1)
    context["ti"].xcom_push(key="row_count", value=1000)


def _transform_data(**context) -> None:
    row_count = context["ti"].xcom_pull(task_ids="extract_data", key="row_count")
    time.sleep(1)
    context["ti"].xcom_push(key="transformed_count", value=row_count)


def _load_data(**context) -> None:
    if _fail_at(**context) == "load":
        raise ValueError(
            "Schema mismatch: column 'event_date' not found in target table 'fact_events'. "
            "Available columns: id, created_at, user_id, action"
        )
    row_count = context["ti"].xcom_pull(task_ids="transform_data", key="transformed_count")
    time.sleep(1)
    print(f"Loaded {row_count} rows successfully.")


def _notify(**context) -> None:
    print("Pipeline completed successfully.")


# ── DAG definition ─────────────────────────────────────────────────────────────

with DAG(
    dag_id=DAG_ID,
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule="0 2 * * *",
    catchup=False,
    tags=["example", "agent-test"],
) as dag:

    wait_for_source = PythonSensor(
        task_id="wait_for_source",
        python_callable=_check_source_ready,
        timeout=30,        # short for testing — triggers timeout quickly
        poke_interval=10,
        mode="poke",
    )

    extract_data = PythonOperator(
        task_id="extract_data",
        python_callable=_extract_data,
    )

    transform_data = PythonOperator(
        task_id="transform_data",
        python_callable=_transform_data,
    )

    load_data = PythonOperator(
        task_id="load_data",
        python_callable=_load_data,
    )

    notify = PythonOperator(
        task_id="notify",
        python_callable=_notify,
    )

    wait_for_source >> extract_data >> transform_data >> load_data >> notify
