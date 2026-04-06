"""Handles new Airflow failure alerts posted to the monitored channel."""

import asyncio
from typing import Any

from slack_sdk.web.async_client import AsyncWebClient

from app.tools import read
from slack.agent import AirflowAgent
from slack.parser import AirflowAlert
from slack.store import thread_store

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
        failed_tasks, analysis = await asyncio.gather(
            read.get_failed_tasks(alert.dag_id, alert.dag_run_id),
            _agent.analyze_failure(alert.dag_id, alert.dag_run_id),
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
