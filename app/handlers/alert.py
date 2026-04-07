"""Handles new Airflow failure alerts posted to the monitored channel."""

import asyncio

from slack_sdk.web.async_client import AsyncWebClient

from app.airflow.tools import read
from app.agent import AirflowAgent
from app.parser import AirflowAlert
from app.store import thread_store

_agent = AirflowAgent()


async def handle_alert(alert: AirflowAlert, channel: str, thread_ts: str, client: AsyncWebClient) -> None:
    """Fetch failure context, run analysis, and post a summary in the alert thread."""

    # Post a placeholder so the DE sees the bot is working
    await client.chat_postMessage(
        channel=channel,
        thread_ts=thread_ts,
        text=":mag: Analyzing failure... I'll be right back.",
    )

    try:
        async def _get_failed_tasks():
            if alert.task_id:
                return [{"task_id": alert.task_id, "try_number": alert.try_number or 1}]
            return await read.get_failed_tasks(alert.dag_id, alert.dag_run_id)

        failed_tasks, analysis = await asyncio.gather(
            _get_failed_tasks(),
            _agent.analyze_failure(
                alert.dag_id,
                alert.dag_run_id,
                hint_task_id=alert.task_id,
                hint_try_number=alert.try_number,
                hint_error_msg=alert.error_msg,
            ),
        )
    except Exception as e:
        await client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=f":warning: Could not analyze failure: {e}",
        )
        return

    # Persist context so the reply handler can use it
    thread_store.save(
        thread_ts=thread_ts,
        dag_id=alert.dag_id,
        dag_run_id=alert.dag_run_id,
        failed_tasks=failed_tasks,
    )

    await client.chat_postMessage(
        channel=channel,
        thread_ts=thread_ts,
        text=analysis,
    )
